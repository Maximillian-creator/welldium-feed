"""
Welldium UPDATE-feed
====================
Lichte feed om BESTAANDE producten bij te werken: verkoopprijs, inkoopprijs,
voorraad en beschikbaarheid. Matcht in Stock Sync op SKU.

  price    = RRP incl. BTW        -> Shopify verkoopprijs
  cost     = inkoop excl. BTW     -> Shopify "kostprijs per artikel"
  quantity = Venlo (NL) voorraad

Bron: Algolia-index van welldium.com (geen login nodig). Zie welldium_common.py.
Lokaal testen: WELLDIUM_BRANDS="Invivo" python scraper.py
"""

import time
import xml.etree.ElementTree as ET
from xml.dom import minidom

import welldium_common as wc

OUTPUT_FILE = "welldium_feed.xml"


def build_xml(products):
    root = ET.Element("products")
    for p in products:
        item = ET.SubElement(root, "product")

        def add(tag, value):
            el = ET.SubElement(item, tag)
            el.text = "" if value is None else str(value)

        add("sku", p["sku"])
        add("title", p["title"])
        add("barcode", p["barcode"])
        add("price", f"{p['price']:.2f}")
        add("cost", f"{p['cost']:.2f}")
        add("available", "true" if p["available"] else "false")
        add("quantity", p["quantity"])
        add("description", p["body_html"])
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
    print("🚀 Welldium UPDATE-feed gestart\n")
    start = time.time()

    products = wc.fetch_products()
    root = build_xml(products)
    save_xml(root, OUTPUT_FILE)

    print(f"⏱️  Klaar in {time.time() - start:.0f}s — {len(products)} producten in de feed")
    print("\n📋 Feed-URL voor Stock Sync (Update):")
    print("https://raw.githubusercontent.com/Maximillian-creator/welldium-feed/main/welldium_feed.xml")


if __name__ == "__main__":
    main()
