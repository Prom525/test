from __future__ import annotations

import argparse
import re
from pathlib import Path

try:
    from docx import Document
except ImportError:
    raise SystemExit("Installeer python-docx: pip install python-docx")


DEFAULT_INPUT_FILE = r"C:\ai-platform\data\rag\products\MASTER DOKUMENT.docx"
DEFAULT_OUTPUT_FOLDER = r"C:\ai-platform\data\rag\products\master"


# Hoofdstukken die we WEL willen gebruiken als product-RAG.
# De keys zijn startprefixen uit het masterdocument.
INCLUDE_SECTIONS = {
    "3.3": {
        "doc_id": "product_master_afdichtingen",
        "product": "Afdichtingen",
        "category": "afdichtingen laadzone stortpunt transportband",
    },
    "3.6": {
        "doc_id": "product_master_flexal_impact_bars",
        "product": "Flexal en Impact Bars",
        "category": "impactzone impact bars flexal belading transportband",
    },
    "3.8": {
        "doc_id": "product_master_rollen_en_steunen",
        "product": "Rollen en steunen",
        "category": "transportbandrollen gurtec rollen steunen",
    },
    "3.9": {
        "doc_id": "product_master_gurtec_hdpe_cerapro",
        "product": "GURTEC, trogstellen, Cerapro en HDPE rollen",
        "category": "gurtec trogstellen cerapro hdpe rollen onderrollen",
    },
    "3.10": {
        "doc_id": "product_master_slijtvast_materiaal",
        "product": "Slijtvast materiaal",
        "category": "slijtvast materiaal keramiek aluminiumoxide belle liner sancic",
    },
    "3.11.2": {
        "doc_id": "product_master_overkapping_transportbanden",
        "product": "Overkapping voor transportbanden",
        "category": "overkapping transportband stof regen wind bescherming",
    },
    "3.12": {
        "doc_id": "product_master_rollax_stuurrollen",
        "product": "Rollax stuurrollen",
        "category": "stuurrollen rollax bandcentrering scheefloop",
    },
    "3.13": {
        "doc_id": "product_master_trommels_transportbanden",
        "product": "Trommels voor transportbanden",
        "category": "aandrijftrommels keertrommels insnoertrommels buigingstrommels spantrommels kooitrommels",
    },
    "4.2": {
        "doc_id": "product_master_bandschrapers_technisch",
        "product": "Bandschrapers technisch",
        "category": "bandschrapers belle banne promati tph tpl kf ks cleanscrape",
    },
    "4.3": {
        "doc_id": "product_master_trommels_technisch",
        "product": "Trommels technisch",
        "category": "trommels berekening ontwerp aandrijftrommel keertrommel spantrommel",
    },
    "MASTER_SITEC": {
        "doc_id": "product_master_bandbeveiliging_sitec",
        "product": "SiTec bandbeveiliging",
        "category": "bandbeveiliging trekkoordschakelaar scheefloopschakelaar eindloopschakelaar werkschakelaar",
    },
    "MASTER_BARRIER": {
        "doc_id": "product_master_barrier_metaaldetector",
        "product": "Barrier metaaldetector",
        "category": "metaaldetectie bandbeveiliging schadepreventie",
    },
}


# Hoofdstukken die we NIET willen gebruiken.
# Proload uit masterdocument is concept en moet worden overgeslagen.
EXCLUDE_PREFIXES = [
    "3.11.1",
    "3.13.9",
    "4.1",
]

FALLBACK_TITLE_SECTIONS = {
    "product_master_bandbeveiliging_sitec": {
        "include_key": "MASTER_SITEC",
        "start_terms": [
            "Bandbeveiliging",
            "Betrouwbare beveiliging voor industriële toepassingen",
            "SiTec Trekkoordschakelaar",
            "Sitec Trekkoordschakelaar",
        ],
        "stop_terms": [
            "Impact Bars",
            "Flexal",

            "Rollen en steunen",
        ],
    },
    "product_master_barrier_metaaldetector": {
        "include_key": "MASTER_BARRIER",
        "start_terms": [
            "Metaaldetector Barrier",
            "Barrier metaaldetector",
            "BARRIER metaaldetector",
        ],
        "stop_terms": [
            "Rollen en steunen",
            "Transportbandrollen Gurtec",
            "Technische Overzichtstabel GURTEC Rollen",
        ],
    },
    "product_master_rollen_en_steunen": {
        "include_key": "3.8",
        "start_terms": [
            "Transportbandrollen Gurtec",
            "Rollen en steunen",
        ],
        "stop_terms": [
            "Technische Overzichtstabel GURTEC Rollen",
            "Trogstellen en Steunen",
            "Aluminiumoxidekeramiek",
            "Slijtvast materiaal",
        ],
    },
    "product_master_gurtec_hdpe_cerapro": {
        "include_key": "3.9",
        "start_terms": [
            "Technische Overzichtstabel GURTEC Rollen",
            "Trogstellen en Steunen",
        ],
        "stop_terms": [
            "Aluminiumoxidekeramiek",
            "Slijtvast materiaal",
            "Blu-Tec Proload",
            "Overkapping voor transportbanden",
        ],
    },
    "product_master_slijtvast_materiaal": {
        "include_key": "3.10",
        "start_terms": [
            "Aluminiumoxidekeramiek",
            "TH Scholten SC-Aluminiumoxidekeramiek",
            "Belle Liner Slijtplaten",
            "Sancic Slijtvaste Onderdelen",
        ],
        "stop_terms": [
            "Blu-Tec Proload",
            "Overkapping voor transportbanden",
            "Stuurrollen Rollax",
        ],
    },
    "product_master_overkapping_transportbanden": {
        "include_key": "3.11.2",
        "start_terms": [
            "Overkapping voor transportbanden",
        ],
        "stop_terms": [
            "Stuurrollen Rollax",
            "PROMATI AANDRIJFTROMMELS",
            "Aandrijftrommels",
        ],
    },
    "product_master_rollax_stuurrollen": {
        "include_key": "3.12",
        "start_terms": [
            "Stuurrollen Rollax",
            "Rollax",
        ],
        "stop_terms": [
            "PROMATI AANDRIJFTROMMELS",
            "Aandrijftrommels",
        ],
    },
    "product_master_trommels_transportbanden": {
        "include_key": "3.13",
        "start_terms": [
            "PROMATI AANDRIJFTROMMELS",
            "Aandrijftrommels",
            "Keertrommels",
            "Insnoertrommels",
            "Buigingstrommels",
            "Spantrommels",
            "Kooitrommels",
        ],
        "stop_terms": [
            "Wat is Promati Proload?",
            "Promati Technisch Handboek Transportbanden",
            "Technisch Handboek BLU-TEC Proload",
        ],

    },
}

def normalize_line(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def paragraph_lines(docx_path: Path) -> list[str]:
    document = Document(str(docx_path))
    lines: list[str] = []

    for para in document.paragraphs:
        text = normalize_line(para.text)
        if text:
            lines.append(text)

    return lines


def get_section_number(line: str) -> str | None:
    """
    Herkent regels zoals:
    3.3 Afdichtingen
    3.11.2 Overkapping voor transportbanden
    4.2 Belle Banne U

    Ook tolerant voor:
    - bullets
    - tabs
    - dubbele spaties
    - Word-nummering met vreemde tekens ervoor
    """
    cleaned = line.strip()
    cleaned = cleaned.replace("\t", " ")
    cleaned = re.sub(r"^[^\d]{0,5}", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)

    match = re.match(r"^(\d+(?:\.\d+)+)(?:\s+|$)", cleaned)
    if not match:
        return None

    return match.group(1)


def starts_with_prefix(section_number: str, prefixes: list[str] | set[str]) -> bool:
    for prefix in prefixes:
        if section_number == prefix or section_number.startswith(prefix + "."):
            return True
    return False


def find_matching_include(section_number: str) -> str | None:
    """
    Geeft de beste include-key terug.
    Bijvoorbeeld:
    3.11.2 -> 3.11.2
    3.11.2.1 -> 3.11.2
    3.13.4 -> 3.13
    """
    matches = []
    for prefix in INCLUDE_SECTIONS:
        if section_number == prefix or section_number.startswith(prefix + "."):
            matches.append(prefix)

    if not matches:
        return None

    return sorted(matches, key=len, reverse=True)[0]


def split_sections(lines: list[str]) -> dict[str, list[str]]:
    """
    Bouwt per include-key een lijst regels.
    Exclude-prefixes winnen altijd.
    """
    sections: dict[str, list[str]] = {key: [] for key in INCLUDE_SECTIONS}
    current_key: str | None = None
    current_excluded = False

    for line in lines:
        section_number = get_section_number(line)

        if section_number:
            if starts_with_prefix(section_number, EXCLUDE_PREFIXES):
                current_key = None
                current_excluded = True
                continue

            include_key = find_matching_include(section_number)

            if include_key:
                current_key = include_key
                current_excluded = False
                sections[current_key].append(line)
                continue

            # Nieuwe niet-productsectie gevonden: stoppen met toevoegen.
            # Belangrijk: dit voorkomt dat 3.14 of 5.x meelift.
            major_match = re.match(r"^\d+(?:\.\d+)+", section_number)
            if major_match:
                current_key = None
                current_excluded = False
                continue

        if current_key and not current_excluded:
            sections[current_key].append(line)

    return sections

def apply_fallback_title_sections(
    lines: list[str],
    sections: dict[str, list[str]],
) -> dict[str, list[str]]:
    """
    Fallback voor producthoofdstukken waarvan de Word-kop niet als
    genummerde paragraaf wordt uitgelezen, maar de titeltekst wel bestaat.
    """
    for fallback_name, cfg in FALLBACK_TITLE_SECTIONS.items():
        include_key = cfg["include_key"]

        # Alleen vullen als de normale sectie leeg is.
        if sections.get(include_key):
            continue

        collecting = False
        collected: list[str] = []

        for line in lines:
            line_clean = normalize_line(line)
            line_lower = line_clean.lower()

            if not collecting:
                if any(term.lower() in line_lower for term in cfg["start_terms"]):
                    collecting = True
                    collected.append(line_clean)
                continue

            # Stop zodra een volgende hoofdsectie begint.
            if any(term.lower() in line_lower for term in cfg["stop_terms"]):
                break

            # Proload altijd overslaan.
            if (
                "proload" in line_lower
                or "blu-tec proload" in line_lower
                or "technisch handboek blu-tec proload" in line_lower
            ):
                break

            collected.append(line_clean)

        if collected:
            sections[include_key] = collected

    return sections

def clean_section_text(lines: list[str]) -> str:
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def build_markdown(section_key: str, body: str) -> str:
    meta = INCLUDE_SECTIONS[section_key]

    return f"""Product: {meta["product"]}
Bron: MASTER DOKUMENT
Categorie: {meta["category"]}
Documenttype: master_product_extract
Status: concept_supported_product_source
Doc ID: {meta["doc_id"]}
Master sectie: {section_key}

Belangrijke RAG-regels:
- Gebruik dit document als aanvullende productbron naast website- en PDF-bronnen.
- Gebruik website- en datasheetbronnen als primaire bron wanneer deze beschikbaar zijn.
- Gebruik artikelstam/SQL voor exacte artikelnummers, prijzen en voorraad.
- Gebruik Proload-informatie uit MASTER DOKUMENT niet als bron.
- Negeer hoofdstukken 3.11.1, 3.13.9 en 4.1 voor Proload.

Inhoud:
{body}
"""


def write_sections(
    sections: dict[str, list[str]],
    output_folder: Path,
    dry_run: bool = False,
) -> int:
    output_folder.mkdir(parents=True, exist_ok=True)

    count = 0

    for section_key, lines in sections.items():
        if not lines:
            continue

        meta = INCLUDE_SECTIONS[section_key]
        body = clean_section_text(lines)

        if len(body) < 100:
            print(f"SKIP {section_key} {meta['doc_id']}: te weinig tekst")
            continue

        markdown = build_markdown(section_key, body)
        out_path = output_folder / f"{meta['doc_id']}.md"

        if dry_run:
            print(f"DRY-RUN {out_path}")
            print(f"    sectie: {section_key}")
            print(f"    product: {meta['product']}")
            print(f"    tekens: {len(markdown)}")
        else:
            out_path.write_text(markdown, encoding="utf-8")
            print(f"OK {out_path}")
            print(f"    sectie: {section_key}")
            print(f"    product: {meta['product']}")
            print(f"    tekens: {len(markdown)}")

        count += 1
        print("-" * 80)

    return count


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Knip bruikbare producthoofdstukken uit MASTER DOKUMENT naar product-RAG markdownbestanden."
    )
    parser.add_argument(
        "--input-file",
        default=DEFAULT_INPUT_FILE,
        help=f"Pad naar MASTER DOKUMENT.docx. Default: {DEFAULT_INPUT_FILE}",
    )
    parser.add_argument(
        "--output-folder",
        default=DEFAULT_OUTPUT_FOLDER,
        help=f"Outputmap. Default: {DEFAULT_OUTPUT_FOLDER}",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Toon wat gemaakt wordt zonder bestanden te schrijven.",
    )

    args = parser.parse_args()

    input_file = Path(args.input_file)
    output_folder = Path(args.output_folder)

    if not input_file.exists():
        print(f"Bestand bestaat niet: {input_file}")
        return 1

    print("Product master-RAG build gestart")
    print(f"Input: {input_file}")
    print(f"Output: {output_folder}")
    print("-" * 80)

    lines = paragraph_lines(input_file)
    print(f"Aantal paragrafen/regels gelezen: {len(lines)}")
    print("-" * 80)

    sections = split_sections(lines)
    sections = apply_fallback_title_sections(lines, sections)

    print("Gevonden secties:")
    for key, value in sections.items():
        print(f"  {key}: {len(value)} regels")
    print("-" * 80)

    count = write_sections(sections, output_folder, dry_run=args.dry_run)

    print("Klaar")
    print(f"Aantal productbestanden gemaakt: {count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())