import os
import re
from datetime import datetime
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL ontbreekt in .env")

print(f"DATABASE_URL = {DATABASE_URL}")
engine = create_engine(DATABASE_URL)


def extract_date(text_raw, file_name):
    # probeer datum uit tekst
    m = re.search(r"Datum:\s*\|\s*(\d{2}-\d{2}-\d{4})", text_raw)
    if m:
        return datetime.strptime(m.group(1), "%d-%m-%Y").date()

    # fallback: uit filename
    m = re.search(r"(\d{2}-\d{2}-\d{4})", file_name)
    if m:
        return datetime.strptime(m.group(1), "%d-%m-%Y").date()

    return None


def normalize_band(line):
    line = line.strip()

    # Band E441 / Band 463 / Band A463
    m = re.match(r"Band\s+([A-Z]?\d+)", line, re.I)
    if m:
        return m.group(1).upper()

    # WG061
    m = re.match(r"(WG\d+)", line, re.I)
    if m:
        return m.group(1).upper()

    return None


def parse_doc(row, conn):
    text_raw = row["text_raw"]
    file_name = row["file_name"]
    source_file = row["source_file"]
    lijn_code = row["lijn_code"]

    lines = [l.strip() for l in text_raw.split("\n") if l.strip()]

    doc_date = extract_date(text_raw, file_name)

    inspecteur = None
    toezichthouder = None
    uitvoeringstijd = None
    werkvergunning = None
    omschrijving = None

    current_band = None

    for i, line in enumerate(lines):

        # metadata
        if "Inspecteur" in line:
            inspecteur = line.split("|")[-1].strip()

        if "Toezichthouder" in line:
            toezichthouder = line.split("|")[-1].strip()

        if "Uitvoeringstijd" in line:
            uitvoeringstijd = line.split("|")[-1].strip()

        if "Werkvergunning" in line:
            werkvergunning = line.split("|")[-1].strip()

        if "Omschrijving" in line:
            omschrijving = line.split("|")[-1].strip()

        # band detectie
        band = normalize_band(line)
        if band:
            current_band = band

            conn.execute(text("""
                INSERT INTO sb_word_report_bands_v1 (source_file, band_code, band_raw)
                VALUES (:sf, :bc, :br)
                ON CONFLICT DO NOTHING
            """), {"sf": source_file, "bc": band, "br": line})

            continue

        # skip template shit
        if any(x in line.upper() for x in [
            "RISICOANALYSE", "GOUDEN REGELS", "VALGEVAAR",
            "KLEMMING", "ELEKTROKUTIE"
        ]):
            continue

        # eenvoudige check-detectie (v1)
        if "|" in line and current_band:
            parts = [p.strip() for p in line.split("|")]

            if len(parts) >= 5:
                oms = parts[1]
                ok_flag = parts[2] != ""
                nok_flag = parts[3] != ""
                opm = parts[4] if len(parts) > 4 else None
                adv = parts[5] if len(parts) > 5 else None

                if any([ok_flag, nok_flag, opm, adv]):
                    conn.execute(text("""
                        INSERT INTO sb_word_report_checks_v1
                        (source_file, band_code, omschrijving, ok_flag, nok_flag, opmerking, advies)
                        VALUES (:sf, :bc, :om, :ok, :nok, :opm, :adv)
                    """), {
                        "sf": source_file,
                        "bc": current_band,
                        "om": oms,
                        "ok": ok_flag,
                        "nok": nok_flag,
                        "opm": opm,
                        "adv": adv
                    })

    # document insert
    conn.execute(text("""
        INSERT INTO sb_word_reports_parsed_v1
        (source_file, file_name, lijn_code, doc_date, inspecteur,
         toezichthouder, uitvoeringstijd, werkvergunning, omschrijving)
        VALUES (:sf, :fn, :lc, :dt, :insp, :toez, :uitv, :wg, :oms)
        ON CONFLICT (source_file) DO NOTHING
    """), {
        "sf": source_file,
        "fn": file_name,
        "lc": lijn_code,
        "dt": doc_date,
        "insp": inspecteur,
        "toez": toezichthouder,
        "uitv": uitvoeringstijd,
        "wg": werkvergunning,
        "oms": omschrijving
    })


def run():
    with engine.begin() as conn:
        rows = conn.execute(text("""
            SELECT *
            FROM sb_word_reports_raw_v1
            WHERE lijn_code = 'KOLEN2'
        """)).mappings().all()

        for r in rows:
            parse_doc(r, conn)

    print(f"[DONE] parsed {len(rows)} docs")


if __name__ == "__main__":
    run()