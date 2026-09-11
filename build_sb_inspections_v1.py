import os
import re
from datetime import datetime, date
from pathlib import PureWindowsPath
from collections import defaultdict, Counter

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
            if dt.year < 100:
                dt = dt.replace(year=dt.year + 2000)
            elif dt.year < 2000:
                dt = dt.replace(year=dt.year + 2000)
            return dt.date()
        except ValueError:
            pass

    return None


def parse_explicit_date_from_sheet_name(sheet: str):
    s = normalize_spaces(sheet)

    # 28-05-14 / 30-09-2025
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

    # 05 & 06-03-24 / 13 & 14-11-23 -> neem eerste dag
    m = re.fullmatch(r"(\d{1,2})\s*&\s*\d{1,2}-(\d{1,2})-(\d{2,4})", s)
    if m:
        d, mth, y = m.groups()
        y = int(y)
        if y < 100:
            y += 2000
        try:
            return datetime(y, int(mth), int(d)).date()
        except ValueError:
            return None

    # 11&13-09-18 -> neem eerste dag
    m = re.fullmatch(r"(\d{1,2})&\d{1,2}-(\d{1,2})-(\d{2,4})", s)
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


def parse_week_from_sheet_name(sheet: str):
    s = normalize_spaces((sheet or "").lower())
    m = re.fullmatch(r"week\s*(\d{1,2})", s)
    if m:
        week = int(m.group(1))
        if 1 <= week <= 53:
            return week
    return None


def iso_week_to_date(year: int, week: int):
    try:
        return date.fromisocalendar(year, week, 1)
    except ValueError:
        return None


def extract_year_candidates_from_text(text_value: str):
    text_value = text_value or ""
    years = []
    for m in re.findall(r"\b(20\d{2})\b", text_value):
        y = int(m)
        if 2005 <= y <= 2035:
            years.append(y)
    return years


def infer_year_from_source_file(source_file: str):
    sf = source_file or ""
    candidates = extract_year_candidates_from_text(sf)
    if candidates:
        return Counter(candidates).most_common(1)[0][0]
    return None


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
    for row_nr, row_json in rows:
        if row_nr > 15:
            break
        if not row_json or not isinstance(row_json, dict):
            continue

        for value in row_json.values():
            dt = parse_inspected_on(value)
            if dt:
                return dt

    return None


def determine_workbook_year(source_file, sheets_for_file, raw_grouped):
    years = []

    for raw_sheet in sheets_for_file:
        explicit_dt = parse_explicit_date_from_sheet_name(raw_sheet)
        if explicit_dt:
            years.append(explicit_dt.year)
            continue

        rows = raw_grouped.get((source_file, raw_sheet), [])
        header_dt = find_header_date(rows)
        if header_dt:
            years.append(header_dt.year)

    file_year = infer_year_from_source_file(source_file)
    if file_year:
        years.append(file_year)

    if years:
        return Counter(years).most_common(1)[0][0]

    return None


def extract_report_title(source_file: str, raw_sheet: str):
    base = os.path.basename(source_file)
    return f"{base} | {raw_sheet}"


def main():
    with engine.begin() as conn:
        print("[INFO] Leegmaken sb_inspections_v0 ...")
        conn.execute(text("TRUNCATE TABLE sb_inspections_v0 RESTART IDENTITY CASCADE"))

        raw_grouped = load_raw_grouped(conn)

        target_keys = [
            (source_file, sheet)
            for (source_file, sheet) in raw_grouped.keys()
            if is_target_excel_source(source_file)
        ]
        target_keys.sort()

        print(f"[INFO] doel-sheets (Lijsten*, excl. totaal.xlsx): {len(target_keys)}")

        sheets_by_file = defaultdict(list)
        for source_file, raw_sheet in target_keys:
            sheets_by_file[source_file].append(raw_sheet)

        workbook_year_by_file = {}
        for source_file, sheets_for_file in sheets_by_file.items():
            workbook_year_by_file[source_file] = determine_workbook_year(
                source_file=source_file,
                sheets_for_file=sheets_for_file,
                raw_grouped=raw_grouped,
            )

        inserted = 0
        skipped_no_date = 0
        skipped_examples = []

        for source_file, raw_sheet in target_keys:
            rows = raw_grouped[(source_file, raw_sheet)]
            sheet_norm = normalize_sheet(raw_sheet)

            inspected_on = None

            # 1. headerdatum
            inspected_on = find_header_date(rows)

            # 2. expliciete datum uit sheetnaam
            if inspected_on is None:
                inspected_on = parse_explicit_date_from_sheet_name(raw_sheet)

            # 3. weeknummer + workbookjaar
            if inspected_on is None:
                week_no = parse_week_from_sheet_name(raw_sheet)
                if week_no is not None:
                    inferred_year = workbook_year_by_file.get(source_file)
                    if inferred_year is not None:
                        inspected_on = iso_week_to_date(inferred_year, week_no)

            if inspected_on is None:
                skipped_no_date += 1
                if len(skipped_examples) < 30:
                    skipped_examples.append((source_file, raw_sheet))
                continue

            inspection_key = build_inspection_key(source_file, raw_sheet, inspected_on)
            lijn_code = infer_lijn_code_from_source(source_file)
            title = extract_report_title(source_file, raw_sheet)

            conn.execute(text("""
                INSERT INTO sb_inspections_v0 (
                    inspection_key,
                    source_file,
                    sheet,
                    lijn_code,
                    title,
                    inspected_on,
                    performed_by
                )
                VALUES (
                    :inspection_key,
                    :source_file,
                    :sheet,
                    :lijn_code,
                    :title,
                    :inspected_on,
                    NULL
                )
                ON CONFLICT (inspection_key) DO NOTHING
            """), {
                "inspection_key": inspection_key,
                "source_file": source_file,
                "sheet": sheet_norm,
                "lijn_code": lijn_code,
                "title": title,
                "inspected_on": inspected_on,
            })

            inserted += 1

        print(f"[DONE] inserted inspections: {inserted}")
        print(f"[DONE] skipped no date: {skipped_no_date}")

        if skipped_examples:
            print("[INFO] eerste skipped voorbeelden:")
            for source_file, raw_sheet in skipped_examples:
                print(f"  - {raw_sheet} | {source_file}")


if __name__ == "__main__":
    main()