from pathlib import Path
from sqlalchemy import create_engine, text
import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://promati:promati@localhost:5432/promati"
)

RAG_DIR = Path(r"C:\ai-platform\Rag\org")

DOC_META = {
    "rag_org_hondenpolicy": {
        "titel": "Hondenpolicy op de werkvloer",
        "categorie": "HR",
        "taak_code": "HONDEN_POLICY",
    },
    "rag_org_sociale_media_policy": {
        "titel": "Sociale media policy",
        "categorie": "HR",
        "taak_code": "SOCIALE_MEDIA_POLICY",
    },
    "rag_org_laptop_policy": {
        "titel": "Laptop policy",
        "categorie": "HR / IT",
        "taak_code": "LAPTOP_POLICY",
    },
    "rag_org_mobiele_telefoon_policy": {
        "titel": "Mobiele telefoon policy",
        "categorie": "HR / IT",
        "taak_code": "MOBIELE_TELEFOON_POLICY",
    },
    "rag_org_car_policy": {
        "titel": "Car policy / bedrijfswagenpolicy",
        "categorie": "HR / Fleet",
        "taak_code": "CAR_POLICY",
    },
}

def main():
    if not RAG_DIR.exists():
        raise RuntimeError(f"RAG-map bestaat niet: {RAG_DIR}")

    engine = create_engine(DATABASE_URL)

    md_files = sorted(RAG_DIR.glob("rag_org_*.md"))

    if not md_files:
        print(f"Geen .md bestanden gevonden in {RAG_DIR}")
        return

    with engine.begin() as conn:
        for path in md_files:
            doc_id = path.stem
            inhoud_md = path.read_text(encoding="utf-8")

            meta = DOC_META.get(doc_id, {
                "titel": doc_id.replace("_", " ").title(),
                "categorie": "Org",
                "taak_code": None,
            })

            conn.execute(text("""
                INSERT INTO org_rag_documenten (
                    doc_id,
                    titel,
                    categorie,
                    taak_code,
                    inhoud_md,
                    actief,
                    aangemaakt_op,
                    bijgewerkt_op
                )
                VALUES (
                    :doc_id,
                    :titel,
                    :categorie,
                    :taak_code,
                    :inhoud_md,
                    TRUE,
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                )
                ON CONFLICT (doc_id) DO UPDATE
                SET
                    titel = EXCLUDED.titel,
                    categorie = EXCLUDED.categorie,
                    taak_code = EXCLUDED.taak_code,
                    inhoud_md = EXCLUDED.inhoud_md,
                    actief = TRUE,
                    bijgewerkt_op = CURRENT_TIMESTAMP
            """), {
                "doc_id": doc_id,
                "titel": meta["titel"],
                "categorie": meta["categorie"],
                "taak_code": meta["taak_code"],
                "inhoud_md": inhoud_md,
            })

            print(f"OK: {doc_id} bijgewerkt vanuit {path.name}")

    print("Klaar. Ververs /org-admin/rag-docs en publiceer de documenten.")

if __name__ == "__main__":
    main()