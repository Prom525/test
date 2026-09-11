import os
import re
import json
from datetime import datetime
from pathlib import PureWindowsPath
from collections import defaultdict

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


def normalize_spaces(s: str) -> str:
    return " ".join((s or "").strip().split())


def normalize_sheet(sheet: str) -> str:
    s = normalize_spaces((sheet or "").lower())

    # week  38 / week38 / week   01 / Week 01 -> week 38 / week 1
    m = re.fullmatch(r"week\s*(\d{1,2})", s)
    if m:
        return f"week {int(m.group(1))}"

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
    s = normalize_spaces(sheet)

    # 28-05-14
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

    # 9+10-05-17 -> neem eerste dag
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
    return {k: (None if v is None else v) for k, v in row_json.items()}


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

    return not (locatie is None and merk_type is None and opmerking is None and klantgegevens is None)


def build_inspection_key(source_file: str, raw_sheet: str, inspected_on):
    return f"{source_file}|{normalize_sheet(raw_sheet)}|{inspected_on.isoformat()}"


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


def load_inspection_lookup(conn):
    rows = conn.execute(text("""
        SELECT
            source_file,
            sheet,
            inspection_key,
            lijn_code,
            inspected_on
        FROM sb_inspections_v0
    """)).fetchall()

    lookup = {}
    by_file = defaultdict(list)

    for source_file, sheet, inspection_key, lijn_code, inspected_on in rows:
        key = (source_file, normalize_sheet(sheet))
        record = {
            "inspection_key": inspection_key,
            "lijn_code": lijn_code,
            "inspected_on": inspected_on,
            "sheet": sheet,
        }
        lookup[key] = record
        by_file[source_file].append(record)

    return lookup, by_file


def load_raw_grouped(conn):
    rows = conn.execute(text("""
        SELECT
            source_file,
            sheet,
            row_nr,
            data->'row' AS row_json
        FROM sb_stg_inspecties_raw
        ORDER BY source_file, sheet, row_nr
    """)).fetchall()

    grouped = defaultdict(list)
    for source_file, sheet, row_nr, row_json in rows:
        grouped[(source_file, sheet)].append((row_nr, row_json))

    return grouped


def find_header_date(rows):
    # probeer eerst row 9, daarna eerste 15 regels breed zoeken
    for row_nr, row_json in rows:
        if row_nr > 15:
            break
        if not row_json:
            continue

        candidates = []
        if isinstance(row_json, dict):
            candidates.extend(row_json.values())

        for value in candidates:
            dt = parse_inspected_on(value)
            if dt:
                return dt

    return None


def main():
    with engine.begin() as conn:
        print("[INFO] Volledig opnieuw opbouwen sb_inspection_items_v0 ...")
        conn.execute(text("TRUNCATE TABLE sb_inspection_items_v0"))

        inspection_lookup, inspection_by_file = load_inspection_lookup(conn)
        raw_grouped = load_raw_grouped(conn)

        target_keys = [
            (source_file, sheet)
            for (source_file, sheet) in raw_grouped.keys()
            if is_target_excel_source(source_file)
        ]
        target_keys.sort()

        print(f"[INFO] doel-sheets (Lijsten*, excl. totaal.xlsx): {len(target_keys)}")

        n_inserted = 0
        n_skipped_no_date = 0
        n_skipped_no_match = 0
        n_skipped_duplicate_in_run = 0

        skipped_examples = []

        seen_rows = set()

        for source_file, raw_sheet in target_keys:
            rows = raw_grouped[(source_file, raw_sheet)]
            sheet_norm = normalize_sheet(raw_sheet)

            inspection_key = None
            inspected_on = None
            lijn_code = infer_lijn_code_from_source(source_file)

            # 1) exacte match op normalized sheet
            hit = inspection_lookup.get((source_file, sheet_norm))
            if hit:
                inspection_key = hit["inspection_key"]
                inspected_on = hit["inspected_on"]
                if hit["lijn_code"]:
                    lijn_code = hit["lijn_code"]

            # 2) datum uit headerregels zoeken
            if inspection_key is None:
                inspected_on = find_header_date(rows)

            # 3) datum uit sheetnaam
            if inspection_key is None and not inspected_on:
                inspected_on = parse_date_from_sheet_name(raw_sheet)

            # 4) zelf key bouwen als datum gevonden
            if inspection_key is None and inspected_on:
                inspection_key = build_inspection_key(source_file, raw_sheet, inspected_on)

            if inspection_key is None:
                n_skipped_no_date += 1
                if len(skipped_examples) < 50:
                    skipped_examples.append((source_file, raw_sheet))
                continue

            inserted_for_this_sheet = 0

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
                    "sheet": sheet_norm,
                    "row_nr": row_nr,
                    "locatie": locatie,
                    "band_breedte": None if band_breedte is None else str(band_breedte),
                    "merk_type": merk_type,
                    "demontage": demontage,
                    "reinigen": reinigen,
                    "vervangen": vervangen,
                    "row_json": json.dumps(row_json_clean, ensure_ascii=False, default=str),
                })

                inserted_for_this_sheet += 1
                n_inserted += 1

            if inserted_for_this_sheet == 0:
                n_skipped_no_match += 1

        print(f"[DONE] inserted items: {n_inserted}")
        print(f"[DONE] skipped no date/match: {n_skipped_no_date}")
        print(f"[DONE] skipped empty sheets: {n_skipped_no_match}")
        print(f"[DONE] skipped duplicates in run: {n_skipped_duplicate_in_run}")

        if skipped_examples:
            print("[INFO] eerste skipped voorbeelden:")
            for source_file, raw_sheet in skipped_examples[:20]:
                print(f"  - {raw_sheet} | {source_file}")


if __name__ == "__main__":
    main()