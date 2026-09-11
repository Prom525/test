import os
import re
import json
from datetime import datetime
from pathlib import PureWindowsPath

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:SterkWachtwoord123@localhost:15432/promati"
)

ROOT_PATH = r"C:\Users\John Koenders\Baucotech\Logbooks - Documenten\Onderhouds Logboeken - Rapport Entretiens\NL\TATA steel"

print("DATABASE_URL =", DATABASE_URL)
engine = create_engine(DATABASE_URL, future=True)


def normalize_sheet(sheet: str) -> str:
    s = " ".join((sheet or "").strip().lower().split())
    m = re.search(r"week\s*(\d{1,2})", s)
    if m:
        return f"week {int(m.group(1)):02d}"
    return s


def parse_inspected_on(raw_value):
    if raw_value is None:
        return None

    s = str(raw_value).strip()
    if not s or s.lower() == "none":
        return None

    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d-%m-%y",
        "%d/%m/%Y",
        "%d/%m/%y",
        "%d.%m.%Y",
        "%d.%m.%y",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(s, fmt)
            if dt.year < 2000:
                dt = dt.replace(year=dt.year + 2000)
            return dt.date()
        except ValueError:
            pass

    return None


def parse_date_from_sheet_name(sheet: str):
    s = (sheet or "").strip()

    # bv 28-05-14 / 30-09-25
    m = re.fullmatch(r"(\d{1,2})-(\d{1,2})-(\d{2,4})", s)
    if m:
        d, mth, y = m.groups()
        y = int(y)
        if y < 100:
            y += 2000
        try:
            return datetime(y, int(mth), int(d)).date()
        except ValueError:
            return None

    # bv 9+10-05-17 -> neem eerste dag = 09-05-2017
    m = re.fullmatch(r"(\d{1,2})\+\d{1,2}-(\d{1,2})-(\d{2,4})", s)
    if m:
        d, mth, y = m.groups()
        y = int(y)
        if y < 100:
            y += 2000
        try:
            return datetime(y, int(mth), int(d)).date()
        except ValueError:
            return None

    return None


def x_to_bool(v):
    if v is None:
        return False
    return str(v).strip().upper() == "X"


def clean_json_dict(row_json: dict) -> dict:
    cleaned = {}
    for k, v in row_json.items():
        cleaned[k] = None if v is None else v
    return cleaned


def is_empty_row(row_json: dict) -> bool:
    return all(v is None for v in row_json.values())


def is_header_or_footer_row(row_json: dict) -> bool:
    locatie = row_json.get("Unnamed: 0")
    merk_type = row_json.get("Unnamed: 2")

    if locatie is None:
        return False

    loc = str(locatie).strip()

    bad_exact = {
        "",
        "Locatie",
        "Datum                :",
        "Uitgevoerd door   :",
        "Handtekening Opdrachtgever:",
        "Naam ",
        "Kontaktpersoon",
        "Adres",
        "PC + Plaats",
        "Tel. / Fax ",
        "Klantgegevens ",
    }

    if loc in bad_exact:
        return True

    if loc.lower().startswith("onderhouds-rapport"):
        return True

    if "Handtekening" in loc:
        return True

    if loc == "Locatie" and merk_type == "Merk + Type":
        return True

    return False


def is_data_row(row_nr: int, row_json: dict) -> bool:
    if row_nr < 13:
        return False

    if is_empty_row(row_json):
        return False

    if is_header_or_footer_row(row_json):
        return False

    locatie = row_json.get("Unnamed: 0")
    merk_type = row_json.get("Unnamed: 2")
    opmerking = row_json.get("Unnamed: 9")
    klantgegevens = row_json.get("Klantgegevens ")

    if locatie is None and merk_type is None and opmerking is None and klantgegevens is None:
        return False

    return True


def get_header_value(conn, source_file: str, raw_sheet: str, row_nr: int, key: str):
    row = conn.execute(text("""
        SELECT data->'row' AS row_json
        FROM sb_stg_inspecties_raw
        WHERE source_file = :source_file
          AND sheet = :sheet
          AND row_nr = :row_nr
        LIMIT 1
    """), {
        "source_file": source_file,
        "sheet": raw_sheet,
        "row_nr": row_nr
    }).fetchone()

    if not row or row[0] is None:
        return None

    row_json = row[0]
    return row_json.get(key)


def build_inspection_key(source_file: str, raw_sheet: str, inspected_on):
    sheet_norm = normalize_sheet(raw_sheet)
    return f"{source_file}|{sheet_norm}|{inspected_on.isoformat()}"


def is_target_excel_source(source_file: str) -> bool:
    if not source_file:
        return False

    sf = source_file.lower()

    if ROOT_PATH.lower() not in sf:
        return False

    if not sf.endswith((".xls", ".xlsx", ".xlsm")):
        return False

    if os.path.basename(sf) == "totaal.xlsx":
        return False

    parts = [p.lower() for p in PureWindowsPath(source_file).parts]
    return any(part.startswith("lijsten") for part in parts)


def infer_lijn_code_from_source(source_file: str) -> str:
    sf = (source_file or "").upper()

    mappings = [
        ("KOLENOPSLAG 2", "KOLEN2"),
        ("KOFA 1", "KOFA1"),
        ("KOFA1", "KOFA1"),
        ("KOFA 2", "KOFA2"),
        ("KOFA2", "KOFA2"),
        ("MENGVELD 1", "MV1"),
        ("MV1", "MV1"),
        ("MENGVELD 2", "MV2"),
        ("MV2", "MV2"),
        ("EO-1", "EO1"),
        ("EO 1", "EO1"),
        ("EO1", "EO1"),
        ("E200", "EO1"),
        ("E300", "EO1"),
        ("PEFA", "PEFA"),
        ("SIFA", "SIFA"),
        ("HOO6", "HOO6"),
        ("HOO 6", "HOO6"),
        ("HOO7", "HOO7"),
        ("HOO 7", "HOO7"),
        ("GSL", "GSL"),
    ]

    for needle, code in mappings:
        if needle in sf:
            return code

    return "UNKNOWN"


def get_existing_inspection(conn, source_file: str, raw_sheet: str):
    sheet_norm = normalize_sheet(raw_sheet)

    row = conn.execute(text("""
        SELECT inspection_key, lijn_code, inspected_on
        FROM sb_inspections_v0
        WHERE source_file = :source_file
          AND lower(trim(sheet)) = :sheet_norm
        ORDER BY inspected_on NULLS LAST
        LIMIT 1
    """), {
        "source_file": source_file,
        "sheet_norm": sheet_norm
    }).fetchone()

    return row


def main():
    with engine.begin() as conn:
        print("[INFO] Volledig opnieuw opbouwen sb_inspection_items_v0 ...")
        conn.execute(text("TRUNCATE TABLE sb_inspection_items_v0"))

        sheets = conn.execute(text("""
            SELECT DISTINCT source_file, sheet
            FROM sb_stg_inspecties_raw
            ORDER BY source_file, sheet
        """)).fetchall()

        target_sheets = [
            (source_file, sheet)
            for source_file, sheet in sheets
            if is_target_excel_source(source_file)
        ]

        print(f"[INFO] gevonden raw sheets totaal: {len(sheets)}")
        print(f"[INFO] doel-sheets (Lijsten*, excl. totaal.xlsx): {len(target_sheets)}")

        n_inserted = 0
        n_skipped_no_date = 0
        n_skipped_no_header_match = 0
        n_skipped_duplicate_in_run = 0

        seen_rows = set()

        for source_file, raw_sheet in target_sheets:
            existing = get_existing_inspection(conn, source_file, raw_sheet)

            inspection_key = None
            lijn_code = infer_lijn_code_from_source(source_file)
            inspected_on = None

            if existing:
                inspection_key = existing[0]
                if existing[1]:
                    lijn_code = existing[1]
                inspected_on = existing[2]

            if inspection_key is None:
                raw_date = get_header_value(conn, source_file, raw_sheet, 9, "Unnamed: 2")
                inspected_on = parse_inspected_on(raw_date)

                if not inspected_on:
                    inspected_on = parse_date_from_sheet_name(raw_sheet)

                if not inspected_on:
                    print(f"[SKIP] geen datum gevonden voor raw_sheet={raw_sheet} | file={source_file}")
                    n_skipped_no_date += 1
                    continue

                inspection_key = build_inspection_key(source_file, raw_sheet, inspected_on)

            print(f"[INSPECTION] {inspection_key} | lijn_code={lijn_code}")

            rows = conn.execute(text("""
                SELECT
                    row_nr,
                    data->'row' AS row_json
                FROM sb_stg_inspecties_raw
                WHERE source_file = :source_file
                  AND sheet = :sheet
                ORDER BY row_nr
            """), {
                "source_file": source_file,
                "sheet": raw_sheet
            }).fetchall()

            if not rows:
                continue

            inserted_for_this_inspection = 0

            for row_nr, row_json in rows:
                if row_json is None:
                    continue

                if not isinstance(row_json, dict):
                    row_json = dict(row_json)

                if not is_data_row(row_nr, row_json):
                    continue

                dedupe_key = (inspection_key, 1, row_nr)
                if dedupe_key in seen_rows:
                    n_skipped_duplicate_in_run += 1
                    continue

                seen_rows.add(dedupe_key)

                row_json_clean = clean_json_dict(row_json)

                locatie = row_json_clean.get("Unnamed: 0")
                band_breedte = row_json_clean.get("Unnamed: 1")
                merk_type = row_json_clean.get("Unnamed: 2")

                demontage = x_to_bool(row_json_clean.get("Unnamed: 3"))
                reinigen = x_to_bool(row_json_clean.get("Unnamed: 4"))
                vervangen = x_to_bool(row_json_clean.get("Unnamed: 5"))

                conn.execute(text("""
                    INSERT INTO sb_inspection_items_v0 (
                        inspection_key,
                        lijn_code,
                        source_file,
                        sheet,
                        section_idx,
                        row_nr,
                        locatie,
                        band_breedte,
                        merk_type,
                        demontage,
                        reinigen,
                        vervangen,
                        row_json
                    )
                    VALUES (
                        :inspection_key,
                        :lijn_code,
                        :source_file,
                        :sheet,
                        1,
                        :row_nr,
                        :locatie,
                        :band_breedte,
                        :merk_type,
                        :demontage,
                        :reinigen,
                        :vervangen,
                        CAST(:row_json AS jsonb)
                    )
                    ON CONFLICT (inspection_key, section_idx, row_nr)
                    DO NOTHING
                """), {
                    "inspection_key": inspection_key,
                    "lijn_code": lijn_code,
                    "source_file": source_file,
                    "sheet": normalize_sheet(raw_sheet),
                    "row_nr": row_nr,
                    "locatie": locatie,
                    "band_breedte": None if band_breedte is None else str(band_breedte),
                    "merk_type": merk_type,
                    "demontage": demontage,
                    "reinigen": reinigen,
                    "vervangen": vervangen,
                    "row_json": json.dumps(row_json_clean, ensure_ascii=False, default=str)
                })

                inserted_for_this_inspection += 1
                n_inserted += 1

            if inserted_for_this_inspection == 0:
                print(f"  [WARN] 0 items voor deze inspection")
            else:
                print(f"  [ITEMS] {inserted_for_this_inspection}")

        print(f"[DONE] inserted items: {n_inserted}")
        print(f"[DONE] skipped no date: {n_skipped_no_date}")
        print(f"[DONE] skipped no header match: {n_skipped_no_header_match}")
        print(f"[DONE] skipped duplicates in run: {n_skipped_duplicate_in_run}")


if __name__ == "__main__":
    main()