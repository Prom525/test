import os
import re
import json
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
    if "E200" in sf:
        return "E200"
    if "E300" in sf:
        return "E300"

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
        "%d.%m.%Y",
        "%d.%m.%y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass

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
    # In jouw Excel begint de echte tabel op rij 13
    if row_nr < 13:
        return False

    if is_empty_row(row_json):
        return False

    if is_header_or_footer_row(row_json):
        return False

    locatie = row_json.get("Unnamed: 0")
    merk_type = row_json.get("Unnamed: 2")
    opmerking = row_json.get("Unnamed: 9")

    # echte data als er iets staat in locatie/type/opmerking
    if locatie is None and merk_type is None and opmerking is None:
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


def main():
    with engine.begin() as conn:
        # Veilig opnieuw opbouwen voor alleen KOLEN2
        print("[INFO] Verwijder bestaande KOLEN2 items...")
        conn.execute(text("""
            DELETE FROM sb_inspection_items_v0
            WHERE lijn_code = 'KOLEN2'
        """))

        # Werk direct vanuit staging per raw sheet
        sheets = conn.execute(text("""
            SELECT DISTINCT
                source_file,
                sheet
            FROM sb_stg_inspecties_raw
            WHERE source_file ILIKE '%Kolenopslag 2.xls%'
            ORDER BY source_file, sheet
        """)).fetchall()

        print(f"[INFO] gevonden raw sheets: {len(sheets)}")

        n_inserted = 0
        n_skipped_no_date = 0
        n_skipped_no_header_match = 0

        for source_file, raw_sheet in sheets:
            lijn_code = infer_lijn_code(source_file)
            raw_date = get_header_value(conn, source_file, raw_sheet, 9, "Unnamed: 2")
            inspected_on = parse_inspected_on(raw_date)

            if not inspected_on:
                print(f"[SKIP] geen datum gevonden voor raw_sheet={raw_sheet}")
                n_skipped_no_date += 1
                continue

            inspection_key = build_inspection_key(source_file, raw_sheet, inspected_on)

            # check of inspection header bestaat
            exists = conn.execute(text("""
                SELECT 1
                FROM sb_inspections_v0
                WHERE inspection_key = :inspection_key
                LIMIT 1
            """), {
                "inspection_key": inspection_key
            }).fetchone()

            if not exists:
                print(f"[SKIP] geen inspection header voor {inspection_key}")
                n_skipped_no_header_match += 1
                continue

            print(f"[INSPECTION] {inspection_key}")

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

            inserted_for_this_inspection = 0

            for row_nr, row_json in rows:
                if row_json is None:
                    continue

                if not isinstance(row_json, dict):
                    row_json = dict(row_json)

                if not is_data_row(row_nr, row_json):
                    continue

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
                        :row_nr,
                        :locatie,
                        :band_breedte,
                        :merk_type,
                        :demontage,
                        :reinigen,
                        :vervangen,
                        CAST(:row_json AS jsonb)
                    )
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

            print(f"  [ITEMS] {inserted_for_this_inspection}")

        print(f"[DONE] inserted items: {n_inserted}")
        print(f"[DONE] skipped no date: {n_skipped_no_date}")
        print(f"[DONE] skipped no header match: {n_skipped_no_header_match}")


if __name__ == "__main__":
    main()