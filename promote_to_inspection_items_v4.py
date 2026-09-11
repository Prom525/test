import os
import json
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:SterkWachtwoord123@localhost:15432/promati"
)

print("DATABASE_URL =", DATABASE_URL)

engine = create_engine(DATABASE_URL, future=True)


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


def x_to_bool(v):
    if v is None:
        return False
    return str(v).strip().upper() == "X"


def is_data_row(row_json: dict) -> bool:
    locatie = row_json.get("Unnamed: 0")
    merk_type = row_json.get("Unnamed: 2")

    # lege regel
    if all(v is None for v in row_json.values()):
        return False

    # header / metadata / titel / footer
    bad_locaties = {
        None,
        "",
        "Locatie",
        "Datum                :",
        "Uitgevoerd door   :",
        "Handtekening Opdrachtgever:",
        "Onderhouds-Rapport Kolenopslag 2",
        "Onderhouds-Rapport Opwerplijn Mengveld 1",
    }

    if locatie in bad_locaties:
        return False

    if isinstance(locatie, str):
        loc = locatie.strip()
        if loc in bad_locaties:
            return False
        if "Handtekening" in loc:
            return False
        if loc.lower().startswith("onderhouds-rapport"):
            return False

    # kolomkopregel
    if locatie == "Locatie" and merk_type == "Merk + Type":
        return False

    # echte dataregel heeft meestal locatie of type
    if locatie is None and merk_type is None:
        return False

    return True


def clean_json_dict(row_json: dict) -> dict:
    cleaned = {}
    for k, v in row_json.items():
        if v is None:
            cleaned[k] = None
        else:
            cleaned[k] = v
    return cleaned


def main():
    with engine.begin() as conn:
        inspections = conn.execute(text("""
            SELECT
                inspection_key,
                lijn_code,
                source_file,
                sheet,
                inspected_on
            FROM sb_inspections_v0
            WHERE source_file ILIKE '%Kolenopslag 2.xls%'
            ORDER BY inspected_on, inspection_key
        """)).fetchall()

        print(f"[INFO] gevonden inspections: {len(inspections)}")

        n_inserted = 0

        for inspection_key, lijn_code, source_file, sheet, inspected_on in inspections:
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
                "sheet": sheet
            }).fetchall()

            for row_nr, row_json in rows:
                if row_json is None:
                    continue

                # psycopg2 geeft vaak al dict terug, maar voor de zekerheid:
                if not isinstance(row_json, dict):
                    row_json = dict(row_json)

                if not is_data_row(row_json):
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
                    "lijn_code": infer_lijn_code(source_file) if lijn_code == "UNKNOWN" else lijn_code,
                    "source_file": source_file,
                    "sheet": sheet,
                    "row_nr": row_nr,
                    "locatie": locatie,
                    "band_breedte": None if band_breedte is None else str(band_breedte),
                    "merk_type": merk_type,
                    "demontage": demontage,
                    "reinigen": reinigen,
                    "vervangen": vervangen,
                    "row_json": json.dumps(row_json_clean, ensure_ascii=False, default=str)
                })

                n_inserted += 1

        print(f"[DONE] inserted items: {n_inserted}")


if __name__ == "__main__":
    main()