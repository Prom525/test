import csv
import os
from pathlib import Path
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL")
MANUAL = Path(r"C:\ai-platform\api\product_mapping_manual.csv")

def norm(v):
    return (v or "").strip()

def main():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL ontbreekt")

    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

    with MANUAL.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    created_or_found = 0
    linked = 0
    skipped = 0

    with engine.begin() as conn:
        for row in rows:
            action = norm(row.get("action")).lower()

            # Alleen de regels verwerken die we eerder bewust op skip zetten,
            # behalve echte master/demo/vragenlijsten.
            if action != "skip":
                skipped += 1
                continue

            doc_id = norm(row.get("doc_id"))
            brand = norm(row.get("brand"))
            model = norm(row.get("model"))
            variant = norm(row.get("variant")) or "standaard"
            category = norm(row.get("category"))
            title = norm(row.get("title"))

            if not doc_id or not brand or not model:
                skipped += 1
                continue

            lower_title = title.lower()
            lower_category = category.lower()
            lower_variant = variant.lower()

            # Niet als product opnemen
            if (
                "master dokument" in lower_title
                or "mini-inspectie" in lower_title
                or "vragenlijst" in lower_title
                or "questionnaire" in lower_variant
                or "vragenlijst" in lower_variant
                or lower_category in {"demo_docs", "vragenlijsten"}
            ):
                skipped += 1
                continue

            product = conn.execute(text("""
                INSERT INTO generic_product (
                    brand,
                    model,
                    category,
                    variant,
                    status,
                    notes
                )
                VALUES (
                    :brand,
                    :model,
                    :category,
                    :variant,
                    'concept',
                    :notes
                )
                ON CONFLICT (brand, model, category, variant)
                DO UPDATE SET
                    notes = COALESCE(generic_product.notes, EXCLUDED.notes)
                RETURNING generic_product_id
            """), {
                "brand": brand,
                "model": model,
                "category": category,
                "variant": variant,
                "notes": f"Concept generiek product uit bulk-import. Bron: {title}",
            }).mappings().first()

            generic_product_id = int(product["generic_product_id"])
            created_or_found += 1

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
                    'bulk_product_document',
                    'concept',
                    0.80
                )
                ON CONFLICT (generic_product_id, doc_id)
                DO UPDATE SET
                    source_role = EXCLUDED.source_role,
                    status = EXCLUDED.status,
                    confidence = EXCLUDED.confidence
            """), {
                "generic_product_id": generic_product_id,
                "doc_id": int(doc_id),
            })

            linked += 1

    print(f"Generic products aangemaakt/gevonden: {created_or_found}")
    print(f"Documentlinks aangemaakt/bijgewerkt: {linked}")
    print(f"Overgeslagen: {skipped}")

if __name__ == "__main__":
    main()