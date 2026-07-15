# Welldium feeds → Stock Sync

Haalt de catalogus van leverancier **Welldium** (`welldium.com`) op en genereert
twee XML-feeds voor [Stock Sync](https://stock-sync.com). Beide draaien
automatisch via GitHub Actions; je hoeft niets handmatig te doen.

Merken in deze feed: **Microbiome Labs**, **Invivo**, **Seeking Health**
(instelbaar, zie onder).

| Feed | Script | Output | Doel | Schema |
|---|---|---|---|---|
| **Update-feed** | `scraper.py` | `welldium_feed.xml` | Prijs + kostprijs + voorraad van **bestaande** producten | 2× per dag (06:00 + 18:00 UTC) |
| **Add-feed** | `add_scraper.py` | `welldium_add_feed.xml` | **Nieuwe** producten aanmaken met álle info | 1× per week (ma 04:00 UTC) |

## Feed-URL's (Stock Sync)

```
Update:  https://raw.githubusercontent.com/Maximillian-creator/welldium-feed/main/welldium_feed.xml
Add:     https://raw.githubusercontent.com/Maximillian-creator/welldium-feed/main/welldium_add_feed.xml
```

## Waarom geen login nodig?

Welldium is een practitioner-portal áchter login, maar de catalogus draait op een
**Algolia-zoekindex** die de site bevraagt met een **publieke, client-side
search-key** (staat in de pagina-JS van welldium.com). Die key praat rechtstreeks
met Algolia — los van je login-sessie — dus deze feed heeft **geen inloggegevens,
cookie of CAPTCHA** nodig. Config staat bovenaan `welldium_common.py`.

## Prijs & voorraad

De prijs in Welldium/Algolia is de **adviesverkoopprijs (RRP), excl. BTW**. In het
practitioner-winkelmandje gaat daar **30%** af = jouw inkoop.

| Feld | Berekening | Shopify-doel |
|---|---|---|
| `price` | `algolia_price × 1,09` (BTW) | **verkoopprijs** (RRP incl. BTW, 1-op-1) |
| `cost` | `algolia_price × 0,70` (−30%) | **kostprijs per artikel** (inkoop excl. BTW) |
| `quantity` | Venlo (NL) magazijn-voorraad | voorraad |
| `available` | `quantity > 0` | beschikbaar |

> Controle: DIM Ultra staat op 64,80 in de index → ×1,09 = **70,63** = de prijs op
> het scherm. ✔
>
> **Geen BTW-opslag in Stock Sync instellen** — `price` is al incl. BTW.
> **Geen EAN/barcode** in de Algolia-index; Stock Sync matcht op **SKU**.

### Afbeeldingen

De ruwe Azure-blob-URL's worden geserveerd als `application/octet-stream`, waardoor
Shopify ze weigert ("Mediaverwerking mislukt"). Daarom lopen alle afbeeldingen in de
feed via de **Nuxt-image-proxy** van welldium.com (`/_ipx/w_1200&q_90/…`), die
dezelfde afbeelding mét de juiste content-type (`image/webp`) serveert. Shopify haalt
'm bij import één keer op en zet 'm daarna op z'n eigen CDN. Bestandsnamen met spaties
e.d. worden percent-geëncodeerd. Instelbaar via `IPX_PREFIX`.

### Verzendbeperkingen

Sommige producten mogen door ingrediëntenregelgeving niet naar Nederland worden
verzonden (Algolia-veld `restrictedCountries`, bv. `["NL"]`). Die worden
**automatisch uit beide feeds gelaten**. Instelbaar via `SHIP_COUNTRY` (default `NL`).

## Velden in de add-feed

Per `<product>`: `handle` (= SKU), `title`, `vendor`, `brand`, `product_type`
(diepste categorie), `tags` (categorie-hiërarchie), `sku`, `barcode` (leeg),
`price`, `cost`, `available`, `quantity`, `description` en een `<images>`-blok +
`image_links` (komma-gescheiden).

Het **`description`-veld bevat álle productinfo** in één blok (zodat je alleen
dit naar Body HTML hoeft te mappen): productvoordelen, kenmerken (Vegan/
hypoallergeen), ingrediënten (supplement facts — uit het curated NL-veld, of
opgebouwd uit het gestructureerde `productIngredients` als dat leeg is), overige
ingrediënten, dosering, allergenen, waarschuwingen, bewaren en vorm/porties.
De losse velden `nutritional_info`, `delivery_format` en `servings` blijven óók
apart beschikbaar mocht je ze los willen mappen.

## Stock Sync mapping (Add products)

Nieuwe koppeling, type **"Add Products"**, bronformaat XML, record-pad
`/products/product`, groepeer op **Handle**.

| Stock Sync veld | XPath |
|---|---|
| Handle | `handle` |
| Title | `title` |
| Body HTML / Description | `description` |
| Vendor | `vendor` (of `brand`) |
| Type | `product_type` |
| Tags | `tags` |
| Variant SKU | `sku` |
| Variant Price | `price` *(incl. BTW)* |
| Cost per item | `cost` *(excl. BTW)* |
| Image Src *(meerdere)* | `images/image/src` |
| (Available) | `available` |

**Voorkom botsingen met de update-feed:** zet de add-koppeling op **alleen nieuwe
producten aanmaken**. De dagelijkse voorraad/prijs loopt via de update-feed.

> **Let op — overlap met supplementhub-feed:** Microbiome Labs en Invivo lopen nu
> óók via de supplementhub-feed. Welldium is je échte inkoopkanaal (juiste prijs +
> voorraad). Regel in Stock Sync welke feed prioriteit heeft, of haal deze merken
> uit de supplementhub-koppeling, zodat twee feeds niet over dezelfde SKU's vechten.

## Lokaal draaien / testen

```bash
pip install -r requirements.txt
python scraper.py                          # volledige update-feed
python add_scraper.py                      # volledige add-feed
WELLDIUM_BRANDS="Invivo" python scraper.py # één merk (snel testen)
INSECURE_SSL=1 python scraper.py           # achter een SSL-onderscheppende proxy
```

Op Windows lokaal: zet `PYTHONIOENCODING=utf-8` als de console de emoji's niet aankan.

### Instelbare parameters (env)

| Variabele | Default | Betekenis |
|---|---|---|
| `WELLDIUM_BRANDS` | `Microbiome Labs,Invivo,Seeking Health` | merken in de feed |
| `WELLDIUM_DISCOUNT` | `0.30` | practitioner-korting op de RRP |
| `VAT_RATE` | `1.09` | BTW-factor (supplementen = 9%) |
| `SHIP_COUNTRY` | `NL` | producten met verzendbeperking voor dit land worden overgeslagen |
| `ALGOLIA_APP` / `ALGOLIA_KEY` / `ALGOLIA_INDEX` | ingebouwd | als de publieke key ooit rouleert |
