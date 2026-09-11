import os
import re
from datetime import datetime
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:SterkWachtwoord123@localhost:15432/promati"
)

print("DATABASE_URL =", DATABASE_URL)

engine = create_engine(DATABASE_URL, future=True)


def normalize_sheet(sheet: str) -> str:
    s = " ".join((sheet or "").strip().lower().split())
    m = re.search(r"week\s*(\d{1,2})", s)
    if m:
        return f"week {int(m.group(1)):02d}"
    return s


def infer_lijn_code(source_file: str) -> str:
    sf = (source_file or "").upper()

    if "KOLENOPSLAG 2" in sf:
        return "KOLEN2"
    if "KOFA1" in sf:
        return "KOFA1"
    if "KOFA2" in sf:
        return "KOFA2"
    if "MV1" in sf:
        return "MV1"
    if "MV2" in sf:
        return "MV2"
    if "EO1" in sf:
        return "EO1"

    return "UNKNOWN"


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
    ]

    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass

    return None


def get_header_value(conn, source_file: str, sheet: str, row_nr: int, key: str):
    row = conn.execute(text("""
        SELECT data->'row' AS row_json
        FROM sb_stg_inspecties_raw
        WHERE source_file = :source_file
          AND sheet = :sheet
          AND row_nr = :row_nr
        LIMIT 1
    """), {
        "source_file": source_file,
        "sheet": sheet,
        "row_nr": row_nr
    }).fetchone()

    if not row or row[0] is None:
        return None

    row_json = row[0]
    return row_json.get(key)


def main():
    with engine.begin() as conn:

        groups = conn.execute(text("""
            SELECT DISTINCT source_file, sheet
            FROM sb_stg_inspecties_raw
            WHERE source_file ILIKE '%Kolenopslag 2.xls%'
            ORDER BY source_file, sheet
        """)).fetchall()

        print(f"[INFO] gevonden sheets: {len(groups)}")

        for source_file, sheet in groups:
            lijn_code = infer_lijn_code(source_file)
            sheet_norm = normalize_sheet(sheet)

            title = get_header_value(conn, source_file, sheet, 7, "Unnamed: 0")
            raw_date = get_header_value(conn, source_file, sheet, 9, "Unnamed: 2")
            performed_by = get_header_value(conn, source_file, sheet, 10, "Unnamed: 2")

            inspected_on = parse_inspected_on(raw_date)

            if not inspected_on:
                print(f"[SKIP] geen datum gevonden voor sheet={sheet}")
                continue

            inspection_key = f"{source_file}|{sheet_norm}|{inspected_on.isoformat()}"

            if not title:
                title = "Onderhouds-Rapport Kolenopslag 2"

            print(
                f"[UPSERT] {inspection_key} | lijn={lijn_code} | title={title} | performed_by={performed_by}"
            )

            conn.execute(text("""
                INSERT INTO sb_inspections_v0 (
                    inspection_key,
                    lijn_code,
                    inspected_on,
                    title,
                    source_file,
                    sheet
                )
                VALUES (
                    :inspection_key,
                    :lijn_code,
                    :inspected_on,
                    :title,
                    :source_file,
                    :sheet
                )
                ON CONFLICT (inspection_key)
                DO UPDATE SET
                    lijn_code    = EXCLUDED.lijn_code,
                    inspected_on = EXCLUDED.inspected_on,
                    title        = EXCLUDED.title,
                    source_file  = EXCLUDED.source_file,
                    sheet        = EXCLUDED.sheet
            """), {
                "inspection_key": inspection_key,
                "lijn_code": lijn_code,
                "inspected_on": inspected_on,
                "title": title,
                "source_file": source_file,
                "sheet": sheet_norm
            })

    print("[DONE] promote_to_inspections_v2 klaar")


if __name__ == "__main__":
    main()