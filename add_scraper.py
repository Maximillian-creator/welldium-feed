"""
Welldium ADD-feed
=================
Volledige productinfo om met Stock Sync NIEUWE producten aan te maken.
Bron: Algolia-index van welldium.com (geen login nodig). Zie welldium_common.py.

  price  = RRP incl. BTW        -> Shopify verkoopprijs
  cost   = inkoop excl. BTW     -> Shopify "kostprijs per artikel"
  quantity = Venlo (NL) voorraad

Voorraad zit ook in de add-feed, maar zet in Stock Sync de ADD-koppeling op
"alleen nieuwe producten aanmaken" — de dagelijkse voorraad loopt via de
update-feed (scraper.py), zodat één bron de stand bepaalt.

Lokaal testen: WELLDIUM_BRANDS="Invivo" python add_scraper.py
"""

import time
import xml.etree.ElementTree as ET
from xml.dom import minidom
from html import escape

import welldium_common as wc

OUTPUT_FILE = "welldium_add_feed.xml"


def build_description_html(p):
    """Rijke NL-beschrijving uit de Algolia-localizations."""
    parts = []
    if p.get("short_description"):
        parts.append(f"<p>{escape(p['short_description'])}</p>")
    if p.get("description"):
        parts.append(f"<p>{escape(p['description'])}</p>")
    if p.get("suggested_intake"):
        parts.append(f"<p><strong>Dosering:</strong> {escape(p['suggested_intake'])}</p>")
    if p.get("nutritional_info"):
        parts.append(f"<p><strong>Voedingswaarde:</strong> {escape(p['nutritional_info'])}</p>")
    if p.get("allergens"):
        parts.append(f"<p><strong>Allergenen:</strong> {escape(p['allergens'])}</p>")
    if p.get("warnings"):
        parts.append(f"<p><strong>Waarschuwingen:</strong> {escape(p['warnings'])}</p>")
    if p.get("storage"):
        parts.append(f"<p><strong>Bewaren:</strong> {escape(p['storage'])}</p>")
    return "\n".join(parts)


def build_xml(products):
    root = ET.Element("products")
    for p in products:
        item = ET.SubElement(root, "product")

        def add(tag, value):
            el = ET.SubElement(item, tag)
            el.text = "" if value is None else str(value)

        add("handle", p["sku"])            # geen slug in de index; SKU als stabiele handle
        add("title", p["title"])
        add("vendor", p["vendor"])
        add("brand", p["brand"])
        add("product_type", p["product_type"])
        add("tags", p["tags"])
        add("sku", p["sku"])
        add("barcode", p["barcode"])
        add("price", f"{p['price']:.2f}")
        add("cost", f"{p['cost']:.2f}")
        add("available", "true" if p["available"] else "false")
        add("quantity", p["quantity"])
        add("description", build_description_html(p))
        add("nutritional_info", p["nutritional_info"])
        add("delivery_format", p["delivery_format"])
        add("servings", p["servings"])

        images_el = ET.SubElement(item, "images")
        for src in p["images"]:
            img = ET.SubElement(images_el, "image")
            add_src = ET.SubElement(img, "src")
            add_src.text = src
        add("image_links", ",".join(p["images"]))
    return root


def save_xml(root, filepath):
    xml_str = ET.tostring(root, encoding="unicode")
    pretty = minidom.parseString(xml_str).toprettyxml(indent="  ")
    lines = pretty.split("\n")
    if lines[0].startswith("<?xml"):
        lines[0] = '<?xml version="1.0" encoding="UTF-8"?>'
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\n💾 XML opgeslagen: {filepath}")


def main():
    print("🚀 Welldium ADD-feed gestart\n")
    start = time.time()

    products = wc.fetch_products()
    root = build_xml(products)
    save_xml(root, OUTPUT_FILE)

    print(f"⏱️  Klaar in {time.time() - start:.0f}s — {len(products)} producten in de feed")
    print("\n📋 Feed-URL voor Stock Sync (Add products):")
    print("https://raw.githubusercontent.com/Maximillian-creator/welldium-feed/main/welldium_add_feed.xml")


if __name__ == "__main__":
    main()
