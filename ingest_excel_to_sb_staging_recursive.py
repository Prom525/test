# ingest_excel_to_sb_staging_recursive.py
import os
import re
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

# --- Config ---
DB_URL = os.environ.get("DB_URL", "postgresql://app:app_pw@localhost:15432/appdb")

# Zet deze naar jouw root map (waar submappen onder hangen)
ROOT_DIR = Path(r"C:\ai-platform\data")  # <-- PAS AAN

# Welke extensies meenemen
EXTS = {".xls", ".xlsx"}

# Optioneel: herkenbare lijncodes in pad/naam (breid uit indien nodig)
LINE_CODES = ["MV1", "MV2", "EO1", "BR1"]

# --- Helpers ---
def guess_lijn_code(path: str) -> str:
    up = path.upper()
    m = re.search(r"\b(" + "|".join(LINE_CODES) + r")\b", up)
    return m.group(1) if m else "UNKNOWN"

def iter_excel_files(root: Path):
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in EXTS:
            yield p

def main():
    if not ROOT_DIR.exists():
        raise SystemExit(f"ROOT_DIR bestaat niet: {ROOT_DIR}")

    engine = create_engine(DB_URL)

    # We slaan zowel absolute als relatieve broninformatie op in het JSON veld "data"
    ins = text("""
      insert into sb_stg_inspecties_raw (lijn_code, source_file, sheet, row_nr, data)
      values (:lijn_code, :source_file, :sheet, :row_nr, cast(:data as jsonb))
    """)

    total_rows = 0
    total_files = 0

    with engine.begin() as conn:
        for file_path in iter_excel_files(ROOT_DIR):
            total_files += 1

            abs_path = str(file_path)
            rel_path = str(file_path.relative_to(ROOT_DIR))  # submap pad binnen ROOT_DIR
            lijn_code = guess_lijn_code(abs_path)

            print(f"\n[{total_files}] Loading: {abs_path}")
            print(f"    rel_path: {rel_path}")
            print(f"    lijn_code: {lijn_code}")

            # Kies engine expliciet per extensie (handig als pandas ooit twijfelt)
            if file_path.suffix.lower() == ".xls":
                xls = pd.ExcelFile(abs_path, engine="xlrd")
            else:
                xls = pd.ExcelFile(abs_path, engine="openpyxl")

            for sheet in xls.sheet_names:
                df = xls.parse(sheet).dropna(how="all")
                print(f"    Sheet '{sheet}': {len(df)} rows")

                for i, row in df.iterrows():
                    # Data per rij: kolommen + broncontext
                    row_dict = row.to_dict()

                    # pandas kan NaN bevatten; to_json maakt daar null van
                    row_json = pd.Series(row_dict).to_json(force_ascii=False)

                    # We voegen broncontext toe door een JSON object te bouwen:
                    # (Omdat row_json een JSON string is, maken we een wrapper met context via string concat in SQL is lastig.
                    # Daarom doen we wrapper als dict->json hier.)
                    # Simpel: we zetten de rij in "row" en context in "source".
                    data_obj = {
                        "source": {
                            "abs_path": abs_path,
                            "rel_path": rel_path,
                            "filename": file_path.name,
                        },
                        "sheet": sheet,
                        "row": row_dict,
                    }

                    # pandas NaN opruimen: row_dict kan NaN bevatten; convert via pandas json roundtrip
                    data_clean = pd.Series(data_obj).to_json(force_ascii=False)

                    conn.execute(ins, {
                        "lijn_code": lijn_code,
                        "source_file": abs_path,   # <-- HIER bewaar je het volledige pad in source_file
                        "sheet": sheet,
                        "row_nr": int(i),
                        "data": data_clean
                    })
                    total_rows += 1

            print(f"    Done: {abs_path}")

    print(f"\nDONE. Files processed: {total_files}, rows inserted: {total_rows}")

if __name__ == "__main__":
    main()