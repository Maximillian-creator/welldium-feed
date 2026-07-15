"""
Welldium — gedeelde kern
========================
Welldium (welldium.com) is de B2B/practitioner-portal waar we o.a. Microbiome
Labs, Invivo en Seeking Health inkopen. De site zit áchter login, MAAR de
catalogus draait op een **Algolia-zoekindex** die met een publieke, client-side
search-key wordt bevraagd. Die key praat rechtstreeks met Algolia — los van de
login-sessie — dus deze feed heeft GEEN login/cookie/CAPTCHA nodig.

Prijslogica (afgesproken met Max):
  De prijs in Welldium/Algolia is de ADVIESVERKOOPPRIJS (RRP), EXCL. BTW.
  In het practitioner-winkelmandje gaat daar 30% af = jouw inkoop.
    price = RRP incl. BTW  = algolia_price × VAT_RATE          -> Shopify verkoopprijs
    cost  = inkoop excl. BTW = algolia_price × (1 − DISCOUNT)   -> Shopify "kostprijs per artikel"

  DIM Ultra-controle: Algolia 64,80 × 1,09 = 70,63 (= schermprijs). ✔

Voorraad:
  Er zijn twee magazijnen: Venlo (NL) en Keighley (UK). Voor onze NL-winkel telt
  Venlo. Top-level `quantity` = de Venlo-voorraad; UK-only producten (SpecialOrder)
  hebben quantity 0. available = Venlo-voorraad > 0.

Env-overrides (optioneel):
  VAT_RATE        (default 1.09)   — BTW-factor (supplementen = 9%)
  WELLDIUM_DISCOUNT (default 0.30) — practitioner-korting op de RRP
  WELLDIUM_BRANDS (default "Microbiome Labs,Invivo,Seeking Health")
  ALGOLIA_KEY / ALGOLIA_APP / ALGOLIA_INDEX — als de publieke key ooit rouleert
"""

import os
import time

import requests

# --- Algolia-config (publieke search-only key uit de welldium.com pagina-JS) ---
ALGOLIA_APP = os.environ.get("ALGOLIA_APP", "P3BCORK34C")
ALGOLIA_KEY = os.environ.get("ALGOLIA_KEY", "da47ece539a61756018c66dc55450a25")
ALGOLIA_INDEX = os.environ.get("ALGOLIA_INDEX", "products")
ALGOLIA_URL = f"https://{ALGOLIA_APP}-dsn.algolia.net/1/indexes/{ALGOLIA_INDEX}/query"

# --- Prijs/voorraad-parameters ---
VAT_RATE = float(os.environ.get("VAT_RATE", "1.09"))
DISCOUNT = float(os.environ.get("WELLDIUM_DISCOUNT", "0.30"))

# Merken die we via Welldium inkopen (exact zoals in de Algolia-facet).
DEFAULT_BRANDS = ["Microbiome Labs", "Invivo", "Seeking Health"]


def brands_from_env():
    raw = os.environ.get("WELLDIUM_BRANDS")
    if raw:
        return [b.strip() for b in raw.split(",") if b.strip()]
    return DEFAULT_BRANDS


HEADERS = {
    "X-Algolia-Application-Id": ALGOLIA_APP,
    "X-Algolia-API-Key": ALGOLIA_KEY,
    "Content-Type": "application/json",
    # Sommige Algolia-keys zijn referer-gebonden; meesturen kan geen kwaad.
    "Referer": "https://welldium.com/",
    "Origin": "https://welldium.com",
    "User-Agent": "Mozilla/5.0 (compatible; GFY-WelldiumFeed/1.0)",
}

HITS_PER_PAGE = 1000  # per merk ruim onder Algolia's paginatie-cap (max merk ~70)

# Alleen voor lokaal testen achter een SSL-onderscheppende bedrijfsproxy.
# In GitHub Actions staat dit uit en wordt het certificaat netjes geverifieerd.
VERIFY_SSL = os.environ.get("INSECURE_SSL") != "1"
if not VERIFY_SSL:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _post(params, max_retries=3):
    for attempt in range(max_retries):
        try:
            resp = requests.post(ALGOLIA_URL, headers=HEADERS,
                                 json={"params": params}, timeout=30,
                                 verify=VERIFY_SSL)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            if attempt < max_retries - 1:
                wait = (attempt + 1) * 15
                print(f"    ⚠️  Algolia-fout ({e}), opnieuw in {wait}s...")
                time.sleep(wait)
            else:
                raise


def fetch_brand(brand):
    """Alle actieve, zichtbare producten van één merk uit de Algolia-index."""
    hits = []
    page = 0
    # facetFilters als AND-groep met één merk: [["productBrand.name:<brand>"]]
    facet = f'[["productBrand.name:{brand}"]]'
    while True:
        params = (
            f"hitsPerPage={HITS_PER_PAGE}&page={page}"
            f"&facetFilters={requests.utils.quote(facet)}"
        )
        data = _post(params)
        batch = data.get("hits", [])
        hits.extend(batch)
        if page + 1 >= data.get("nbPages", 1):
            break
        page += 1
        time.sleep(0.3)
    return hits


def _leaf(cat_levels):
    """Diepste categorie-leaf, bv. 'Active Ingredients > Minerals > Magnesium' -> 'Magnesium'."""
    for key in ("categories.lvl2", "categories.lvl1", "categories.lvl0"):
        vals = cat_levels.get(key)
        if vals:
            deepest = vals[0] if isinstance(vals, list) else vals
            return deepest.split(">")[-1].strip()
    return ""


def _all_category_tags(hit):
    tags = set()
    for key in ("categories.lvl0", "categories.lvl1", "categories.lvl2"):
        vals = hit.get(key) or []
        if isinstance(vals, str):
            vals = [vals]
        for v in vals:
            for seg in v.split(">"):
                seg = seg.strip()
                if seg:
                    tags.add(seg)
    return sorted(tags)


def _images(hit):
    imgs = hit.get("productImages") or []
    imgs = sorted(imgs, key=lambda x: x.get("sortOrder", 0))
    return [i["url"] for i in imgs if i.get("url")]


def _venlo_quantity(hit):
    """NL-voorraad: Venlo-magazijn; val terug op top-level quantity."""
    stock = hit.get("stock") or {}
    venlo = stock.get("Venlo")
    if isinstance(venlo, dict) and venlo.get("available") is not None:
        return int(venlo["available"])
    q = hit.get("quantity")
    return int(q) if q is not None else 0


def normalize(hit):
    """Zet één Algolia-record om naar een uniform product-dict voor beide feeds."""
    raw_price = hit.get("price")
    if raw_price is None:
        return None
    raw_price = float(raw_price)

    price = round(raw_price * VAT_RATE, 2)            # verkoop, incl. BTW (RRP)
    cost = round(raw_price * (1 - DISCOUNT), 2)       # inkoop, excl. BTW
    qty = _venlo_quantity(hit)

    nl = (hit.get("localizations") or {}).get("nl") or {}
    brand = (hit.get("productBrand") or {}).get("name", "")

    return {
        "sku": hit.get("sku", ""),
        "barcode": "",  # niet aanwezig in de Algolia-index; Stock Sync matcht op SKU
        "title": hit.get("name", ""),
        "brand": brand,
        "vendor": brand,
        "product_type": _leaf(hit),
        "tags": ", ".join(_all_category_tags(hit)),
        "price": price,
        "cost": cost,
        "quantity": qty,
        "available": qty > 0,
        "images": _images(hit),
        "delivery_format": (hit.get("productDeliveryFormat") or {}).get("name", ""),
        "servings": hit.get("servingsPerContainer"),
        # NL-teksten
        "short_description": nl.get("shortDescription", ""),
        "description": nl.get("description", ""),
        "suggested_intake": nl.get("suggestedIntake", ""),
        "storage": nl.get("storageRequirements", ""),
        "allergens": nl.get("allergens", ""),
        "warnings": nl.get("warnings", ""),
        "nutritional_info": nl.get("nutritionalInformation", ""),
        # ruwe stockStatus voor debug
        "stock_status": (hit.get("stockStatus") or {}).get("id", ""),
    }


def fetch_products(brands=None):
    """Haalt alle producten van de opgegeven merken op en normaliseert ze."""
    brands = brands or brands_from_env()
    out = []
    for brand in brands:
        hits = fetch_brand(brand)
        active = [h for h in hits if h.get("isActive") and not h.get("isHidden")]
        print(f"  {brand}: {len(active)} actieve producten (van {len(hits)} totaal)")
        for h in active:
            p = normalize(h)
            if p and p["sku"]:
                out.append(p)
    print(f"✅ {len(out)} producten genormaliseerd\n")
    return out
