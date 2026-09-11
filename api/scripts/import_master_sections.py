import csv
import os
import re
import tempfile
from pathlib import Path

import requests
from docx import Document
from sqlalchemy import create_engine, text


API_BASE = os.getenv("API_BASE", "http://localhost:8000")
DATABASE_URL = os.getenv("DATABASE_URL")

MASTER_DOCX_PATH = Path(
    os.getenv(
        "MASTER_DOCX_PATH",
        r"C:\ai-platform\demo_docs\MASTER DOKUMENT.docx",
    )
)

OUT_MANIFEST = Path(r"C:\ai-platform\api\master_section_import_manifest.csv")


# Let op:
# target_type:
#   scraper = koppelen aan product_document_link
#   generic = koppelen aan generic_product_document_link
SECTION_RULES = [
    {
        "label": "Belle Banne U",
        "pattern": r"(Belle\s+Banne\s+U|Onderschraper\s*[–-]\s*Belle\s+Banne\s+U)",
        "brand": "Belle Banne",
        "model": "U",
        "category": "Bandschraper",
        "variant": "master_section",
        "target_type": "scraper",
        "target_id": 2,
    },
    {
        "label": "Belle Banne R",
        "pattern": r"(Belle\s+Banne\s+R|Onderschraper\s*[–-]\s*Belle\s+Banne\s+R)",
        "brand": "Belle Banne",
        "model": "R",
        "category": "Bandschraper",
        "variant": "master_section",
        "target_type": "scraper",
        "target_id": 3,
    },
    {
        "label": "Belle Banne P",
        "pattern": r"(Belle\s+Banne\s+P|Onderschraper\s*[–-]\s*Belle\s+Banne\s+P)",
        "brand": "Belle Banne",
        "model": "P",
        "category": "Bandschraper",
        "variant": "master_section",
        "target_type": "generic",
        "target_id": 1,
    },
    {
        "label": "Belle Banne H",
        "pattern": r"(Belle\s+Banne\s+H|Kopschraper\s*[–-]\s*Belle\s+Banne\s+H)",
        "brand": "Belle Banne",
        "model": "H",
        "category": "Bandschraper",
        "variant": "master_section",
        "target_type": "scraper",
        "target_id": 1,
    },
    {
        "label": "Belle Banne RV",
        "pattern": r"(Belle\s+Banne\s+RV|Bandschraper\s+RV)",
        "brand": "Belle Banne",
        "model": "RV",
        "category": "Bandschraper",
        "variant": "master_section",
        "target_type": "generic",
        "target_id": 2,
    },
    {
        "label": "Promati TPH",
        "pattern": r"(Promati\s+TPH|Bandschraper\s+TPH)",
        "brand": "Promati",
        "model": "TPH",
        "category": "Bandschraper",
        "variant": "master_section",
        "target_type": "scraper",
        "target_id": 4,
    },
    {
        "label": "Promati TPL",
        "pattern": r"(Promati\s+TPL|Bandschraper\s+TPL)",
        "brand": "Promati",
        "model": "TPL",
        "category": "Bandschraper",
        "variant": "master_section",
        "target_type": "scraper",
        "target_id": 5,
    },
    {
        "label": "Impact Bars",
        "pattern": r"(Impact\s+Bars|Impactbars)",
        "brand": "Promati",
        "model": "Impact Bars",
        "category": "Afdichting",
        "variant": "master_section",
        "target_type": "generic",
        "target_id": 24,
    },
    {
        "label": "Transportbandrollen",
        "pattern": r"(Transportbandrollen|Rollen\s+en\s+Steunen)",
        "brand": "Promati",
        "model": "Transportbandrollen",
        "category": "Rollen en steunen",
        "variant": "master_section",
        "target_type": "generic",
        "target_id": 14,
    },
    {
        "label": "Cerapro-ringen",
        "pattern": r"(Cerapro|Cerapro-ringen)",
        "brand": "Promati",
        "model": "Cerapro-ringen",
        "category": "Rollen en steunen",
        "variant": "master_section",
        "target_type": "generic",
        "target_id": 18,
    },
    {
        "label": "HDPE Rollen",
        "pattern": r"(HDPE\s+Rollen|HDPE-rollen)",
        "brand": "Promati",
        "model": "HDPE Rollen",
        "category": "Rollen en steunen",
        "variant": "master_section",
        "target_type": "generic",
        "target_id": 17,
    },
    {
        "label": "Belle Liner",
        "pattern": r"(Belle\s+Liner)",
        "brand": "Belle Banne",
        "model": "Belle Liner",
        "category": "Slijtplaten",
        "variant": "master_section",
        "target_type": "generic",
        "target_id": 4,
    },
    {
        "label": "Sancic",
        "pattern": r"(Sancic)",
        "brand": "Sancic",
        "model": "Sancic",
        "category": "Slijtplaten",
        "variant": "master_section",
        "target_type": "generic",
        "target_id": 5,
    },
    {
        "label": "BLU-TEC Proload",
        "pattern": r"(BLU[-\s]?TEC\s+Proload|Blu[-\s]?Tec\s+Proload|Proload)",
        "brand": "BLU-TEC",
        "model": "Proload",
        "category": "Ontstoffingssysteem - Stofdicht Stortpunt",
        "variant": "master_section",
        "target_type": "generic",
        "target_id": 8,
    },
    {
        "label": "Rollax",
        "pattern": r"(Rollax)",
        "brand": "Rollax",
        "model": "Rollax",
        "category": "Stuurrollen",
        "variant": "master_section",
        "target_type": "generic",
        "target_id": 25,
    },
    {
        "label": "Transportbandtrommels",
        "pattern": r"(Transportbandtrommels|Trommels\s+en\s+Lagers)",
        "brand": "Promati",
        "model": "Transportbandtrommels",
        "category": "Trommels en lagers",
        "variant": "master_section",
        "target_type": "generic",
        "target_id": 19,
    },
]


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def paragraph_is_heading(paragraph) -> bool:
    style_name = (paragraph.style.name or "").lower()
    text_value = paragraph.text.strip()

    if not text_value:
        return False

    if "heading" in style_name or "kop" in style_name:
        return True

    # Fallback voor documenten waar kopstijlen niet netjes zijn gebruikt.
    if re.match(r"^\d+(\.\d+){1,4}\s+", text_value):
        return True

    return False


def load_blocks(docx_path: Path) -> list[dict]:
    doc = Document(str(docx_path))
    blocks = []

    for p in doc.paragraphs:
        text_value = p.text.strip()
        if not text_value:
            continue

        blocks.append({
            "text": text_value,
            "is_heading": paragraph_is_heading(p),
            "style": p.style.name if p.style else "",
        })

    return blocks


def find_section_blocks(blocks: list[dict], pattern: str) -> list[dict]:
    regex = re.compile(pattern, re.IGNORECASE)

    start_idx = None
    for i, block in enumerate(blocks):
        if regex.search(block["text"]):
            start_idx = i
            break

    if start_idx is None:
        return []

    # Stop bij volgende duidelijke heading van hetzelfde documentniveau.
    # Simpel en veilig: pak maximaal tot de volgende heading nadat de sectie gestart is.
    end_idx = len(blocks)
    for j in range(start_idx + 1, len(blocks)):
        if blocks[j]["is_heading"]:
            # Alleen stoppen als er al wat bodytekst is verzameld.
            if j > start_idx + 2:
                end_idx = j
                break

    return blocks[start_idx:end_idx]


def write_section_docx(section: dict, blocks: list[dict], out_path: Path):
    doc = Document()
    doc.add_heading(f"MASTER DOKUMENT - {section['label']}", level=1)

    doc.add_paragraph(f"Bron: MASTER DOKUMENT")
    doc.add_paragraph(f"Product: {section['brand']} {section['model']}")
    doc.add_paragraph(f"Categorie: {section['category']}")
    doc.add_paragraph("Bronrol: master_section")

    for block in blocks:
        if block["is_heading"]:
            doc.add_heading(block["text"], level=2)
        else:
            doc.add_paragraph(block["text"])

    doc.save(str(out_path))


def get_existing_doc_id(conn, title: str, filename: str):
    row = conn.execute(text("""
        SELECT doc_id
        FROM sb_docs_v0
        WHERE title = :title
          AND filename = :filename
        ORDER BY created_at DESC
        LIMIT 1
    """), {
        "title": title,
        "filename": filename,
    }).mappings().first()

    return int(row["doc_id"]) if row else None


def ingest_docx(path: Path, section: dict) -> int:
    title = f"MASTER DOKUMENT - {section['label']}"

    with path.open("rb") as f:
        files = {
            "file": (
                path.name,
                f,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        }
        data = {
            "title": title,
            "brand": section["brand"],
            "model": section["model"],
            "category": section["category"],
            "variant": section["variant"],
            "language": "nl",
            "document_type": "master_section",
            "status": "concept",
        }

        response = requests.post(
            f"{API_BASE}/rag/ingest-product-document",
            files=files,
            data=data,
            timeout=120,
        )

    response.raise_for_status()
    payload = response.json()
    return int(payload["doc_id"])


def link_scraper_doc(conn, product_id: int, doc_id: int, section: dict):
    conn.execute(text("""
        INSERT INTO product_document_link (
            product_id,
            doc_id,
            source_role,
            brand,
            model,
            variant,
            status,
            confidence
        )
        VALUES (
            :product_id,
            :doc_id,
            'master_section',
            :brand,
            :model,
            :variant,
            'concept',
            0.75
        )
        ON CONFLICT (product_id, doc_id, variant)
        DO UPDATE SET
            source_role = EXCLUDED.source_role,
            brand = EXCLUDED.brand,
            model = EXCLUDED.model,
            status = EXCLUDED.status,
            confidence = EXCLUDED.confidence
    """), {
        "product_id": product_id,
        "doc_id": doc_id,
        "brand": section["brand"],
        "model": section["model"],
        "variant": section["variant"],
    })


def link_generic_doc(conn, generic_product_id: int, doc_id: int):
    conn.execute(text("""
        INSERT INTO generic_product_document_link (
            generic_product_id,
            doc_id,
            source_role,
            status,
            confidence
        )
        VALUES (
            :generic_product_id,
            :doc_id,
            'master_section',
            'concept',
            0.75
        )
        ON CONFLICT (generic_product_id, doc_id)
        DO UPDATE SET
            source_role = EXCLUDED.source_role,
            status = EXCLUDED.status,
            confidence = EXCLUDED.confidence
    """), {
        "generic_product_id": generic_product_id,
        "doc_id": doc_id,
    })


def main():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL ontbreekt")

    if not MASTER_DOCX_PATH.exists():
        raise FileNotFoundError(f"MASTER DOKUMENT niet gevonden: {MASTER_DOCX_PATH}")

    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    blocks = load_blocks(MASTER_DOCX_PATH)

    results = []

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        with engine.begin() as conn:
            for section in SECTION_RULES:
                found_blocks = find_section_blocks(blocks, section["pattern"])

                if not found_blocks:
                    results.append({
                        "label": section["label"],
                        "status": "not_found",
                        "doc_id": "",
                        "target_type": section["target_type"],
                        "target_id": section["target_id"],
                        "chunks_or_blocks": 0,
                    })
                    print(f"NIET GEVONDEN: {section['label']}")
                    continue

                filename = f"master_section_{slugify(section['label'])}.docx"
                title = f"MASTER DOKUMENT - {section['label']}"
                temp_docx = tmpdir / filename

                existing_doc_id = get_existing_doc_id(conn, title, filename)

                if existing_doc_id:
                    doc_id = existing_doc_id
                    status = "existing_doc_linked"
                else:
                    write_section_docx(section, found_blocks, temp_docx)
                    doc_id = ingest_docx(temp_docx, section)
                    status = "ingested_and_linked"

                if section["target_type"] == "scraper":
                    link_scraper_doc(
                        conn=conn,
                        product_id=int(section["target_id"]),
                        doc_id=doc_id,
                        section=section,
                    )
                elif section["target_type"] == "generic":
                    link_generic_doc(
                        conn=conn,
                        generic_product_id=int(section["target_id"]),
                        doc_id=doc_id,
                    )
                else:
                    raise ValueError(f"Onbekend target_type: {section['target_type']}")

                results.append({
                    "label": section["label"],
                    "status": status,
                    "doc_id": doc_id,
                    "target_type": section["target_type"],
                    "target_id": section["target_id"],
                    "chunks_or_blocks": len(found_blocks),
                })

                print(
                    f"OK: {section['label']} -> {section['target_type']} "
                    f"{section['target_id']} doc_id={doc_id} ({status})"
                )

    with OUT_MANIFEST.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "label",
                "status",
                "doc_id",
                "target_type",
                "target_id",
                "chunks_or_blocks",
            ],
        )
        writer.writeheader()
        writer.writerows(results)

    print("")
    print(f"Klaar. Manifest geschreven naar: {OUT_MANIFEST}")


if __name__ == "__main__":
    main()