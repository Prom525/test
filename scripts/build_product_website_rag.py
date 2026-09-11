from __future__ import annotations

import argparse
import re
from pathlib import Path

try:
    import requests
except ImportError:
    raise SystemExit("Installeer requests: pip install requests")

try:
    from bs4 import BeautifulSoup
except ImportError:
    raise SystemExit("Installeer beautifulsoup4: pip install beautifulsoup4")


DEFAULT_OUTPUT_FOLDER = r"C:\ai-platform\data\rag\products\website"


PRODUCT_PAGES = [
    {
        "doc_id": "product_proload_website_nl",
        "product": "Proload",
        "category": "stofbestrijding laadzone stortpunt transfer point",
        "url": "https://www.promati.com/promati-products/proload-blu-tec-proload/",
    },
    {
        "doc_id": "product_flexal_website_nl",
        "product": "Flexal",
        "category": "impactzone impact bars laadzone",
        "url": "https://www.promati.com/promati-products/flexal/",
    },
    {
        "doc_id": "product_impact_bars_website_nl",
        "product": "Impact Bars",
        "category": "impactzone impact bars transportband ondersteuning",
        "url": "https://www.promati.com/promati-products/impact-bars/",
    },
    {
        "doc_id": "product_blu_tec_impact_bars_website_nl",
        "product": "BLU-TEC impact bars en steunen",
        "category": "impactzone impact bars BLU-TEC",
        "url": "https://www.promati.com/promati-products/impact-bars-steunen-voor-transportbanden/",
    },
    {
        "doc_id": "product_afdichtingen_transportbanden_website_nl",
        "product": "Afdichtingen transportbanden",
        "category": "afdichtingen laadzone stortpunt",
        "url": "https://www.promati.com/promati-products/afdichtingen-transportbanden/",
    },
    {
        "doc_id": "product_snel_klemsysteem_afdichtingen_website_nl",
        "product": "Snel klemsysteem voor afdichtingen",
        "category": "afdichtingen klemsysteem Duo-Seal",
        "url": "https://www.promati.com/promati-products/snel-klemsysteem-voor-afdichtingen/",
    },
    {
        "doc_id": "product_duo_seal_website_nl",
        "product": "Duo-Seal",
        "category": "afdichtingen stortpunt normale toepassingen",
        "url": "https://www.promati.com/promati-products/duo-seal-afdichtingssystemen/",
    },
    {
        "doc_id": "product_tri_seal_website_nl",
        "product": "Tri-Seal",
        "category": "afdichtingen stortpunt zware toepassingen",
        "url": "https://www.promati.com/promati-products/tri-seal-afdichtingssystemen/",
    },
    {
        "doc_id": "product_multi_seal_website_nl",
        "product": "Multi-Seal",
        "category": "afdichtingen stortpunt zware toepassingen",
        "url": "https://www.promati.com/promati-products/multi-seal-afdichtingssystemen/",
    },
    {
        "doc_id": "product_bandschrapers_website_nl",
        "product": "Bandschrapers",
        "category": "bandschrapers belt cleaners",
        "url": "https://www.promati.com/promati-products/bandschrapers/",
    },
    {
        "doc_id": "product_rollen_en_steunen_website_nl",
        "product": "Rollen en steunen",
        "category": "rollen steunen Gurtec HDPE Cerapro",
        "url": "https://www.promati.com/promati-products/rollen-en-steunen/",
    },
    {
        "doc_id": "product_ploegschraper_website_nl",
        "product": "Ploegschraper",
        "category": "bandschraper diagonaal keertrommel binnenzijde band",
        "url": "https://www.promati.com/promati-products/ploegschraper/",
    },
    {
        "doc_id": "product_trommels_website_nl",
        "product": "Trommels voor transportbanden",
        "category": "trommels aandrijftrommels keertrommels transportband",
        "url": "https://www.promati.com/promati-products/trommels-voor-transportbanden/",
    },
    {
        "doc_id": "product_stofbestrijding_website_nl",
        "product": "Stofbestrijding op transportbanden",
        "category": "stofbestrijding laadzone transfer point",
        "url": "https://www.promati.com/promati-products/stofbestrijding-op-transportbanden/",
    },
]


def clean_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines).strip()


def extract_page_text(url: str) -> tuple[str, str]:
    response = requests.get(
        url,
        timeout=30,
        headers={
            "User-Agent": "PromatiGPT-RAG-Importer/1.0",
        },
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    for tag in soup(["script", "style", "noscript", "svg", "form"]):
        tag.decompose()

    title = soup.title.get_text(" ", strip=True) if soup.title else ""

    main = soup.find("main")
    if main is None:
        main = soup.find("article")
    if main is None:
        main = soup.body or soup

    text = main.get_text("\n", strip=True)
    return title, clean_text(text)


def build_markdown(page: dict, title: str, text: str) -> str:
    return f"""Product: {page["product"]}
Bron: Promati website
Categorie: {page["category"]}
Documenttype: website_product_page
Status: approved_source
URL: {page["url"]}
Doc ID: {page["doc_id"]}

Belangrijke RAG-regels:
- Gebruik dit document als actuele websitebron voor productkennis.
- Gebruik artikelstam/SQL voor exacte artikelnummers, prijzen en voorraad.
- Gebruik dit document voor algemene uitleg, voordelen, toepassingsgebied, beperkingen en selectieadvies.
- Gebruik Proload-informatie uit MASTER DOKUMENT voorlopig niet als bron.

Website titel:
{title}

Website tekst:
{text}
"""


def write_product_pages(output_folder: Path, dry_run: bool = False) -> int:
    output_folder.mkdir(parents=True, exist_ok=True)

    count = 0

    for page in PRODUCT_PAGES:
        doc_id = page["doc_id"]
        out_path = output_folder / f"{doc_id}.md"

        print(f"Ophalen: {page['url']}")
        try:
            title, text = extract_page_text(page["url"])
        except Exception as exc:
            print(f"FOUT {doc_id}: {exc}")
            continue

        if not text or len(text) < 80:
            print(f"WAARSCHUWING {doc_id}: weinig tekst gevonden ({len(text)} tekens)")

        markdown = build_markdown(page, title, text)

        if dry_run:
            print(f"DRY-RUN {out_path}")
            print(f"    titel: {title}")
            print(f"    tekens: {len(markdown)}")
        else:
            out_path.write_text(markdown, encoding="utf-8")
            print(f"OK {out_path}")
            print(f"    tekens: {len(markdown)}")

        count += 1
        print("-" * 80)

    return count


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Maak product-RAG markdownbestanden van Promati websitepagina's."
    )
    parser.add_argument(
        "--output-folder",
        default=DEFAULT_OUTPUT_FOLDER,
        help=f"Outputmap. Default: {DEFAULT_OUTPUT_FOLDER}",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Haal pagina's op maar schrijf geen bestanden.",
    )

    args = parser.parse_args()
    output_folder = Path(args.output_folder)

    print("Product website-RAG build gestart")
    print(f"Output: {output_folder}")
    print(f"Aantal pagina's: {len(PRODUCT_PAGES)}")
    print("-" * 80)

    count = write_product_pages(output_folder, dry_run=args.dry_run)

    print("Klaar")
    print(f"Aantal verwerkt: {count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())