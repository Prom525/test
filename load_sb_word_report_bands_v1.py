import os
import re
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


def normalize_band_code(raw_line: str, lijn_code: Optional[str]) -> Optional[str]:
    s = normalize_whitespace(raw_line).upper()

    if not s:
        return None

    s = s.replace("BAND ", "").strip()

    if re.fullmatch(r"WG\s*0*(\d{2,3})", s):
        n = re.fullmatch(r"WG\s*0*(\d{2,3})", s).group(1)
        return f"WG{int(n):03d}"

    if re.fullmatch(r"[EA]\s*0*(\d{3})", s):
        prefix = s[0]
        digits = re.search(r"(\d{3})", s).group(1)
        return f"{prefix}{digits}"

    if re.fullmatch(r"0*(\d{3})", s):
        digits = re.fullmatch(r"0*(\d{3})", s).group(1)
        if lijn_code == "KOLEN2":
            return f"A{digits}"
        return digits

    if "STACKER" in s:
        m = re.search(r"STACKER\s*0*(\d+)", s)
        if m:
            return f"STACKER{int(m.group(1)):03d}"
        return "STACKER"

    if "UITHOUDER" in s:
        return "UITHOUDER"

    if "OPVOERBAND" in s:
        return "OPVOERBAND"

    return None


def is_band_heading(line: str) -> bool:
    s = normalize_whitespace(line)
    if not s:
        return False

    patterns = [
        r"^Band\s+[EA]\s*\d{3}(?:\s*\(.*\))?$",
        r"^Band\s+\d{3}(?:\s*\(.*\))?$",
        r"^Band\s+Stacker(?:\s*\d+)?(?:\s*\(.*\))?$",
        r"^WG\s*\d{2,3}$",
        r"^Uithouder$",
        r"^Opvoerband$",
        r"^Stacker(?:\s*\d+)?$",
    ]
    return any(re.match(p, s, re.IGNORECASE) for p in patterns)


def extract_band_raw(line: str) -> str:
    s = normalize_whitespace(line)
    s = re.sub(r"\s*\(.*?\)\s*$", "", s).strip()
    return s


def main() -> None:
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL ontbreekt in .env")

    print(f"DATABASE_URL = {database_url}")
    engine = create_engine(database_url)

    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS sb_word_report_bands_v1 (
                id BIGSERIAL PRIMARY KEY,
                source_file TEXT,
                band_code TEXT,
                band_raw TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))

        conn.execute(text("TRUNCATE TABLE sb_word_report_bands_v1 RESTART IDENTITY"))

        rows = conn.execute(text("""
            SELECT source_file, file_name, lijn_code, text_raw
            FROM sb_word_reports_raw_v1
            ORDER BY id
        """)).mappings().all()

        print(f"[INFO] bronbestanden: {len(rows)}")

        inserted = 0

        for row in rows:
            source_file = row["source_file"]
            lijn_code = row["lijn_code"]
            text_raw = normalize_whitespace(row["text_raw"])

            seen = set()

            for line in text_raw.splitlines():
                line = normalize_whitespace(line)

                if not is_band_heading(line):
                    continue

                band_raw = extract_band_raw(line)
                band_code = normalize_band_code(band_raw, lijn_code)

                if not band_code:
                    continue

                key = (source_file, band_code)
                if key in seen:
                    continue
                seen.add(key)

                conn.execute(text("""
                    INSERT INTO sb_word_report_bands_v1 (
                        source_file,
                        band_code,
                        band_raw
                    )
                    VALUES (
                        :source_file,
                        :band_code,
                        :band_raw
                    )
                """), {
                    "source_file": source_file,
                    "band_code": band_code,
                    "band_raw": band_raw,
                })
                inserted += 1

    print(f"[DONE] band records inserted: {inserted}")


if __name__ == "__main__":
    main()