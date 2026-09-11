import json
import os
from pathlib import Path

import pandas as pd
import psycopg2
from psycopg2.extras import Json


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:SterkWachtwoord123@localhost:15432/promati",
)

FILES = [
    {
        "path": r"C:\ai-platform\data\odoo\huidig.xlsx",
        "pipeline_type": "huidig",
    },
    {
        "path": r"C:\ai-platform\data\odoo\verloren.xlsx",
        "pipeline_type": "verloren",
    },
]


def clean_value(v):
    if pd.isna(v):
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return str(v).strip()


def load_file(conn, file_path: str, pipeline_type: str):
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Bestand niet gevonden: {file_path}")

    df = pd.read_excel(path)
    df = df.where(pd.notnull(df), None)

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO crm.odoo_import_batch (source_file, pipeline_type)
            VALUES (%s, %s)
            RETURNING batch_id
            """,
            (str(path), pipeline_type),
        )
        batch_id = cur.fetchone()[0]

        for idx, row in df.iterrows():
            raw = {str(k): clean_value(v) for k, v in row.to_dict().items()}

            cur.execute(
                """
                INSERT INTO crm.odoo_opportunity_raw
                    (batch_id, source_file, pipeline_type, row_nr, raw_json)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    batch_id,
                    str(path),
                    pipeline_type,
                    int(idx) + 2,
                    Json(raw),
                ),
            )

    conn.commit()
    print(f"[OK] {file_path} geladen als {pipeline_type}: {len(df)} regels")


def main():
    with psycopg2.connect(DATABASE_URL) as conn:
        for f in FILES:
            load_file(conn, f["path"], f["pipeline_type"])


if __name__ == "__main__":
    main()