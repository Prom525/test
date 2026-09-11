import csv
import os
from pathlib import Path
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL")
MANUAL = Path(r"C:\ai-platform\api\product_mapping_manual.csv")

def norm(v):
    return (v or "").strip()

def next_product_id(conn):
    return conn.execute(
        text("SELECT COALESCE(MAX(product_id), 0) + 1 FROM scraper_product")
    ).scalar()

def main():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL ontbreekt")

    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

    with MANUAL.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    linked = 0
    created = 0
    skipped = 0

    with engine.begin() as conn:
        for row in rows:
            action = norm(row.get("action")).lower()
            if action == "skip":
                skipped += 1
                continue

            doc_id = int(norm(row["doc_id"]))
            brand = norm(row["brand"])
            model = norm(row["model"])
            variant = norm(row.get("variant")) or "standaard"
            category = norm(row.get("category"))

            product_id_raw = norm(row.get("product_id"))

            if action == "create_product":
                product_id = next_product_id(conn)

                conn.execute(text("""
                    INSERT INTO scraper_product (
                        product_id,
                        brand,
                        model,
                        position_hint,
                        bidirectional_ok,
                        speed_max_mps,
                        temp_max_c,
                        space_compact,
                        active,
                        notes,
                        allowed_slots
                    )
                    VALUES (
                        :product_id,
                        :brand,
                        :model,
                        'unknown',
                        false,
                        null,
                        null,
                        false,
                        true,
                        :notes,
                        ARRAY['secondary']::scraper_slot[]
                    )
                """), {
                    "product_id": product_id,
                    "brand": brand.lower().replace(" ", "_"),
                    "model": model,
                    "notes": f"Concept product aangemaakt uit bulk-import. Category: {category}. Controle nodig.",
                })

                created += 1

            elif action == "link_existing":
                product_id = int(product_id_raw)

            else:
                skipped += 1
                continue

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
                    'manual_mapping',
                    :brand,
                    :model,
                    :variant,
                    'concept',
                    0.90
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
                "brand": brand,
                "model": model,
                "variant": variant,
            })

            linked += 1

    print(f"Gelinkt: {linked}")
    print(f"Nieuwe concept-producten: {created}")
    print(f"Overgeslagen: {skipped}")

if __name__ == "__main__":
    main()