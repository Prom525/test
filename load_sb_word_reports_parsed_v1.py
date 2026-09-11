import os
import re
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


def normalize_whitespace(value: Optional[str]) -> str:
    if value is None:
        return ""
    value = str(value).replace("\u00a0", " ")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\s*\n\s*", "\n", value)
    return value.strip()


def first_group(pattern: str, text_value: str, flags: int = re.IGNORECASE) -> Optional[str]:
    m = re.search(pattern, text_value, flags)
    if not m:
        return None
    return normalize_whitespace(m.group(1))


def parse_date(value: Optional[str]) -> Optional[str]:
    if not value:
        return None

    raw = value.strip()
    raw = raw.replace(".", "-").replace("/", "-").replace("_", "-")
    raw = re.sub(r"\s+", "", raw)

    for fmt in ("%d-%m-%Y", "%d-%m-%y"):
        try:
            dt = datetime.strptime(raw, fmt)
            if dt.year < 2000:
                dt = dt.replace(year=dt.year + 2000)
            return dt.date().isoformat()
        except ValueError:
            pass

    return None


def extract_doc_date(text_raw: str, file_name: str) -> Optional[str]:
    patterns = [
        r"Datum\s*[:|]\s*([0-3]?\d[-/.][01]?\d[-/.](?:\d{2}|\d{4}))",
        r"\bDatum\b.*?([0-3]?\d[-/.][01]?\d[-/.](?:\d{2}|\d{4}))",
    ]
    for pattern in patterns:
        value = first_group(pattern, text_raw, re.IGNORECASE | re.DOTALL)
        parsed = parse_date(value)
        if parsed:
            return parsed

    m = re.search(r"([0-3]?\d[-._][01]?\d[-._](?:20\d{2}|\d{2}))", file_name)
    if m:
        parsed = parse_date(m.group(1))
        if parsed:
            return parsed

    return None


def extract_field(text_raw: str, label: str) -> Optional[str]:
    pattern = rf"{re.escape(label)}\s*[:|]\s*(.+)"
    value = first_group(pattern, text_raw, re.IGNORECASE)
    if value:
        value = value.split("\n")[0].strip(" |")
    return value or None


def extract_header_value(text_raw: str, key: str) -> Optional[str]:
    pattern = rf"{re.escape(key)}\s*\|\s*([^\n|]+)"
    value = first_group(pattern, text_raw, re.IGNORECASE)
    return value or None


def main() -> None:
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL ontbreekt in .env")

    print(f"DATABASE_URL = {database_url}")
    engine = create_engine(database_url)

    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS sb_word_reports_parsed_v1 (
                id BIGSERIAL PRIMARY KEY,
                source_file TEXT UNIQUE,
                file_name TEXT,
                lijn_code TEXT,
                doc_date DATE,
                inspecteur TEXT,
                toezichthouder TEXT,
                uitvoeringstijd TEXT,
                werkvergunning TEXT,
                omschrijving TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))

        conn.execute(text("TRUNCATE TABLE sb_word_reports_parsed_v1 RESTART IDENTITY"))

        rows = conn.execute(text("""
            SELECT source_file, file_name, lijn_code, text_raw
            FROM sb_word_reports_raw_v1
            ORDER BY id
        """)).mappings().all()

        print(f"[INFO] bronbestanden: {len(rows)}")

        inserted = 0

        for row in rows:
            source_file = row["source_file"]
            file_name = row["file_name"]
            lijn_code = row["lijn_code"]
            text_raw = normalize_whitespace(row["text_raw"])

            doc_date = extract_doc_date(text_raw, file_name)
            inspecteur = (
                extract_header_value(text_raw, "Inspecteur")
                or extract_field(text_raw, "Inspecteur")
            )
            toezichthouder = (
                extract_header_value(text_raw, "Toezichthouder")
                or extract_field(text_raw, "Toezichthouder")
            )
            uitvoeringstijd = (
                extract_header_value(text_raw, "Uitvoeringstijd")
                or extract_field(text_raw, "Uitvoeringstijd")
            )
            werkvergunning = (
                extract_header_value(text_raw, "Werkvergunning")
                or extract_field(text_raw, "Werkvergunning")
            )
            omschrijving = (
                extract_header_value(text_raw, "Omschrijving")
                or extract_field(text_raw, "Omschrijving")
            )

            conn.execute(text("""
                INSERT INTO sb_word_reports_parsed_v1 (
                    source_file,
                    file_name,
                    lijn_code,
                    doc_date,
                    inspecteur,
                    toezichthouder,
                    uitvoeringstijd,
                    werkvergunning,
                    omschrijving
                )
                VALUES (
                    :source_file,
                    :file_name,
                    :lijn_code,
                    CAST(:doc_date AS DATE),
                    :inspecteur,
                    :toezichthouder,
                    :uitvoeringstijd,
                    :werkvergunning,
                    :omschrijving
                )
            """), {
                "source_file": source_file,
                "file_name": file_name,
                "lijn_code": lijn_code,
                "doc_date": doc_date,
                "inspecteur": inspecteur,
                "toezichthouder": toezichthouder,
                "uitvoeringstijd": uitvoeringstijd,
                "werkvergunning": werkvergunning,
                "omschrijving": omschrijving,
            })
            inserted += 1

    print(f"[DONE] parsed reports inserted: {inserted}")


if __name__ == "__main__":
    main()