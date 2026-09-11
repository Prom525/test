import os
import json
import pandas as pd
from sqlalchemy import create_engine, text

ROOT_DIR = r"C:\Users\John Koenders\Baucotech\Logbooks - Documenten\Onderhouds Logboeken - Rapport Entretiens\NL\TATA steel\Lijsten GSL"

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:SterkWachtwoord123@localhost:15432/promati"
)

print("DATABASE_URL =", DATABASE_URL)

engine = create_engine(DATABASE_URL, future=True)


def process_file(path: str):
    print(f"[FILE] {path}")

    xls = pd.ExcelFile(path)

    with engine.begin() as conn:
        for sheet in xls.sheet_names:
            print(f"  [SHEET] {sheet}")

            df = pd.read_excel(
                path,
                sheet_name=sheet,
                header=None,
                dtype=object
            )

            print(f"    [ROWS] {len(df)}")

            for idx, row in df.iterrows():
                row_dict = {}
                for k, v in row.to_dict().items():
                    key = f"Unnamed: {k}"
                    if pd.isna(v):
                        row_dict[key] = None
                    else:
                        row_dict[key] = v

                payload = {"row": row_dict}

                conn.execute(text("""
                    INSERT INTO sb_stg_inspecties_raw (
                        lijn_code,
                        source_file,
                        sheet,
                        row_nr,
                        data
                    )
                    VALUES (
                        :lijn_code,
                        :source_file,
                        :sheet,
                        :row_nr,
                        CAST(:data AS jsonb)
                    )
                """), {
                    "lijn_code": "UNKNOWN",
                    "source_file": path,
                    "sheet": sheet,
                    "row_nr": int(idx + 1),
                    "data": json.dumps(payload, default=str)
                })


def walk():
    found = 0

    for root, _, files in os.walk(ROOT_DIR):
        for f in files:
            path = os.path.join(root, f)

            if not f.lower().endswith((".xls", ".xlsx")):
                continue

            # tijdelijk alleen KOLEN2 testen
            if "Kolenopslag 2.xls" not in path:
                continue

            found += 1
            process_file(path)

    print(f"[DONE] aantal gevonden bestanden: {found}")


if __name__ == "__main__":
    walk()