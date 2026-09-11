import csv
import os
from pathlib import Path
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:promati@localhost:5432/promati"
)

MANIFEST = Path(r"C:\ai-platform\api\product_import_manifest.csv")

# Handmatige eerste mapping. Later kunnen we dit slimmer maken.
PRODUCT_MAP = {
    ("belle banne", "u", "standaard"): 2,
    ("belle banne", "u", "rev"): 12,
    ("belle banne", "h", "standaard"): 1,
    ("belle banne", "r", "standaard"): 3,
    ("promati", "tph", "standaard"): 4,
    ("promati", "tpl", "standaard"): 5,
}


def norm(v):
    return (v or "").strip().lower()


def main():
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

    linked = 0
    missing = []

    with MANIFEST.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    with engine.begin() as conn:
        for row in rows:
            if row.get("status") != "ok":
                continue

            doc_id = row.get("doc_id")
            if not doc_id:
                continue

            brand = row.get("brand") or ""
            model = row.get("model") or ""
            variant = row.get("variant") or "standaard"
            title = row.get("title") or ""
            category = row.get("category") or ""

            key = (norm(brand), norm(model), norm(variant))
            product_id = PRODUCT_MAP.get(key)

            if not product_id:
                missing.append({
                    "doc_id": doc_id,
                    "title": title,
                    "brand": brand,
                    "model": model,
                    "variant": variant,
                    "category": category,
                })
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
                    'bulk_product_document',
                    :brand,
                    :model,
                    :variant,
                    'concept',
                    0.80
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
                "doc_id": int(doc_id),
                "brand": brand,
                "model": model,
                "variant": variant,
            })

            linked += 1

    print(f"Gekoppeld: {linked}")
    print(f"Nog te mappen: {len(missing)}")

    if missing:
        out = Path(r"C:\ai-platform\api\product_mapping_todo.csv")
        with out.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["doc_id", "title", "brand", "model", "variant", "category"]
            )
            writer.writeheader()
            writer.writerows(missing)

        print(f"Todo geschreven naar: {out}")


if __name__ == "__main__":
    main()