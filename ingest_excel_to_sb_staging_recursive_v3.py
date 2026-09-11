import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


BASE_DIR = Path(
    r"C:\Users\John Koenders\Baucotech\Logbooks - Documenten\Onderhouds Logboeken - Rapport Entretiens\NL\TATA steel"
)

ALLOWED_EXTENSIONS = {".xls", ".xlsx", ".xlsm", ".xlsb"}

SOURCE_SITE_RULES = [
    {
        "contains": r"\NL\TATA steel",
        "customer_code": "TATA_STEEL",
        "site_code": "IJMUIDEN",
    },
    {
        "contains": r"\BE\ArcelorMittal Gent",
        "customer_code": "ARCELORMITTAL",
        "site_code": "GENT",
    },
]

def build_database_url() -> str:
    load_dotenv()

    db_url = os.getenv("DATABASE_URL")
    if db_url:
        return db_url

    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "SterkWachtwoord123")
    dbname = os.getenv("POSTGRES_DB", "promati")

    # Let op: postgres draait bij jou op hostpoort 15432
    return f"postgresql://{user}:{password}@localhost:15432/{dbname}"

DATABASE_URL = build_database_url()
print("DATABASE_URL =", DATABASE_URL)

engine = create_engine(DATABASE_URL, future=True)

def infer_customer_site_from_path(path: Path) -> tuple[str, str]:
    source = str(path).replace("/", "\\")

    for rule in SOURCE_SITE_RULES:
        if rule["contains"].lower() in source.lower():
            return rule["customer_code"], rule["site_code"]

    raise ValueError(
        f"Geen customer/site mapping gevonden voor bestand: {source}. "
        "Voeg dit pad toe aan SOURCE_SITE_RULES."
    )

def is_null_like(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except Exception:
        return False


def clean_value(value: Any) -> Any:
    if is_null_like(value):
        return None

    if isinstance(value, float):
        if math.isnan(value):
            return None
        # Houd integers netjes als int
        if value.is_integer():
            return int(value)
        return value

    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat(sep=" ")

    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass

    return value


def clean_row_dict(row_dict: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in row_dict.items():
        cleaned[str(key)] = clean_value(value)
    return cleaned


def should_skip_file(path: Path) -> bool:
    if path.suffix.lower() not in ALLOWED_EXTENSIONS:
        return True

    # Alleen totaal.xlsx in map Lijsten GSL overslaan
    if path.name.lower() == "totaal.xlsx" and path.parent.name.lower() == "lijsten gsl":
        return True

    return False

def dataframe_sheet_hash(df: pd.DataFrame) -> tuple[str, int, int]:
    """
    Maakt een stabiele hash van één Excel-tabblad.
    Return: sheet_hash, row_count, last_row_nr
    """
    df = df.copy()
    df.columns = [str(col) for col in df.columns]

    parts: list[str] = []
    row_count = 0
    last_row_nr = 0

    for row_nr, (_, row) in enumerate(df.iterrows(), start=1):
        row_json = clean_row_dict(row.to_dict())
        payload = json.dumps(row_json, ensure_ascii=False, sort_keys=True, default=str)
        parts.append(f"{row_nr}:{payload}")
        row_count += 1
        last_row_nr = row_nr

    raw = "|".join(parts)
    return hashlib.md5(raw.encode("utf-8")).hexdigest(), row_count, last_row_nr

def iter_excel_files(base_dir: Path) -> list[Path]:
    files: list[Path] = []

    for child in sorted(base_dir.iterdir()):
        if not child.is_dir():
            continue

        if not child.name.lower().startswith("lijsten"):
            continue

        for path in child.rglob("*"):
            if path.is_file() and not should_skip_file(path):
                files.append(path)

    return sorted(files)


def read_workbook(path: Path) -> dict[str, pd.DataFrame]:
    ext = path.suffix.lower()

    if ext == ".xls":
        return pd.read_excel(path, sheet_name=None, engine="xlrd")
    if ext in {".xlsx", ".xlsm"}:
        return pd.read_excel(path, sheet_name=None, engine="openpyxl")
    if ext == ".xlsb":
        return pd.read_excel(path, sheet_name=None, engine="pyxlsb")

    raise ValueError(f"Niet ondersteund bestandstype: {path}")


def process_file(path: Path, mode: str = "incremental") -> tuple[int, int, int]:
    source_file = str(path)
    customer_code, site_code = infer_customer_site_from_path(path)

    print(f"[FILE] {source_file}")
    print(f"  [CUSTOMER] {customer_code}")
    print(f"  [SITE] {site_code}")

    try:
        sheets = read_workbook(path)
    except Exception as exc:
        print(f"  [ERROR] lezen workbook mislukt: {exc}")
        return (0, 0, 0)

    inserted_rows = 0
    sheet_count = 0
    processed_sheets = 0

    with engine.begin() as conn:
        for sheet_name, df in sheets.items():
            if df is None:
                continue

            sheet_count += 1

            # Pandas levert soms MultiIndex-kolommen; maak alles string
            df = df.copy()
            df.columns = [str(col) for col in df.columns]

            sheet_name_str = str(sheet_name)
            sheet_hash, row_count_for_hash, last_row_nr = dataframe_sheet_hash(df)

            existing = conn.execute(
                text("""
                    SELECT sheet_hash
                    FROM inspection_source_sheet_index
                    WHERE customer_code = :customer_code
                      AND site_code = :site_code
                      AND source_file = :source_file
                      AND sheet = :sheet
                """),
                {
                    "customer_code": customer_code,
                    "site_code": site_code,
                    "source_file": source_file,
                    "sheet": sheet_name_str,
                },
            ).scalar()

            if mode == "incremental" and existing == sheet_hash:
                print(f"  [SKIP UNCHANGED] {sheet_name_str}")
                continue

            change_status = "NEW_SHEET" if existing is None else "CHANGED_SHEET"
            print(f"  [SHEET] {sheet_name_str} [{change_status}]")

            processed_sheets += 1

            # Alleen oude stagingregels van dit ene tabblad verwijderen
            conn.execute(
                text("""
                    DELETE FROM sb_stg_inspecties_raw
                    WHERE customer_code = :customer_code
                      AND site_code = :site_code
                      AND source_file = :source_file
                      AND sheet = :sheet
                """),
                {
                    "customer_code": customer_code,
                    "site_code": site_code,
                    "source_file": source_file,
                    "sheet": sheet_name_str,
                },
            )

            row_counter = 0

            for row_nr, (_, row) in enumerate(df.iterrows(), start=1):
                row_json = clean_row_dict(row.to_dict())

                payload = {
                    "row": row_json
                }

                conn.execute(
                    text("""
                        INSERT INTO sb_stg_inspecties_raw (
                            customer_code,
                            site_code,
                            source_file,
                            sheet,
                            row_nr,
                            data
                        )
                        VALUES (
                            :customer_code,
                            :site_code,
                            :source_file,
                            :sheet,
                            :row_nr,
                            CAST(:data AS jsonb)
                        )
                    """),
                    {
                        "customer_code": customer_code,
                        "site_code": site_code,
                        "source_file": source_file,
                        "sheet": sheet_name_str,
                        "row_nr": row_nr,
                        "data": json.dumps(payload, ensure_ascii=False, default=str),
                    },
                )

                row_counter += 1
                inserted_rows += 1

            print(f"    [ROWS] {row_counter}")

            # Sheet-index bijwerken
            conn.execute(
                text("""
                    INSERT INTO inspection_source_sheet_index (
                        customer_code,
                        site_code,
                        source_file,
                        sheet,
                        sheet_norm,
                        sheet_hash,
                        row_count,
                        last_row_nr,
                        last_seen_at,
                        import_status
                    )
                    VALUES (
                        :customer_code,
                        :site_code,
                        :source_file,
                        :sheet,
                        lower(regexp_replace(coalesce(:sheet, ''), '\\s+', ' ', 'g')),
                        :sheet_hash,
                        :row_count,
                        :last_row_nr,
                        now(),
                        :import_status
                    )
                    ON CONFLICT (customer_code, site_code, source_file, sheet)
                    DO UPDATE SET
                        sheet_norm = excluded.sheet_norm,
                        sheet_hash = excluded.sheet_hash,
                        row_count = excluded.row_count,
                        last_row_nr = excluded.last_row_nr,
                        last_seen_at = now(),
                        import_status = excluded.import_status
                """),
                {
                    "customer_code": customer_code,
                    "site_code": site_code,
                    "source_file": source_file,
                    "sheet": sheet_name_str,
                    "sheet_hash": sheet_hash,
                    "row_count": row_count_for_hash,
                    "last_row_nr": last_row_nr,
                    "import_status": change_status,
                },
            )

    return (sheet_count, processed_sheets, inserted_rows)


def main(mode: str = "incremental") -> None:
    if not BASE_DIR.exists():
        raise FileNotFoundError(f"BASE_DIR bestaat niet: {BASE_DIR}")

    files = iter_excel_files(BASE_DIR)

    print(f"[INFO] mode: {mode}")
    print(f"[INFO] gevonden Excel-bestanden: {len(files)}")
    if not files:
        return

    total_files = 0
    total_sheets = 0
    total_processed_sheets = 0
    total_rows = 0

    for path in files:
        total_files += 1
        sheet_count, processed_sheets, row_count = process_file(path, mode=mode)
        total_sheets += sheet_count
        total_processed_sheets += processed_sheets
        total_rows += row_count

    print("[DONE]")
    print(f"  bestanden : {total_files}")
    print(f"  sheets    : {total_sheets}")
    print(f"  verwerkt  : {total_processed_sheets}")
    print(f"  rows      : {total_rows}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Ingest Excel logboeken naar sb_stg_inspecties_raw"
    )
    parser.add_argument(
        "--mode",
        choices=["incremental", "full-rebuild"],
        default="incremental",
        help="incremental = alleen nieuwe/gewijzigde sheets; full-rebuild = alle sheets opnieuw",
    )
    args = parser.parse_args()

    main(mode=args.mode)