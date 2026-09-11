import os
import re
from typing import Iterable, Optional, Tuple

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


TARGET_TABLE = "sb_word_report_checks_v1"
SOURCE_TABLE = "sb_word_reports_raw_v1"


KNOWN_CHECK_PREFIXES = [
    "werking schraper",
    "werking schrapers",
    "band algemene staat",
    "band loop t.o.v. trommels",
    "vervuiling onder de band",
    "afdichting stortpunt",
    "slijttegels",
    "staat van de constructie",
    "ibn in",
]

SECTION_STOP_WORDS = [
    "risicoanalyse",
    "gouden regels",
    "valgevaar",
    "klemming",
    "inbeslagname",
    "besloten ruimtes",
    "gas- explosiegevaar",
    "transport",
    "verplaatsing",
    "elektrokutie",
    "na beëindigen van het werk",
    "beschrijving werkzaamheden",
    "sectie:",
    "evb/gsl",
    "werkvergunning",
    "inspecteur",
    "toezichthouder",
    "uitvoeringstijd",
    "gelieve hier kort",
    "andere mogelijke items",
]


def norm_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def clean_text_value(s: str) -> Optional[str]:
    s = norm_spaces(s)
    if not s:
        return None
    if s.lower() in {"t", "x", "true"}:
        return None
    return s


def is_true_token(s: str) -> bool:
    return norm_spaces(s).lower() in {"x", "t", "true", "ja", "j", "ok", "v", "1"}


def looks_like_row_number(s: str) -> bool:
    return bool(re.fullmatch(r"\d{1,3}", norm_spaces(s)))


def is_band_heading(line: str) -> Optional[str]:
    s = norm_spaces(line)
    su = s.upper()

    explicit = {
        "OPVOERBAND": "OPVOERBAND",
        "UITHOUDER": "UITHOUDER",
        "WG061": "WG061",
        "WG61": "WG061",
        "WG071": "WG071",
        "WG71": "WG071",
        "STACKER 051": "STACKER051",
        "STACKER051": "STACKER051",
    }
    if su in explicit:
        return explicit[su]

    if re.fullmatch(r"BAND\s+E\s*502\s*\(STACKER\)", su):
        return "STACKER051"

    m = re.fullmatch(r"BAND\s+([AE])\s*0?(\d{3})", su)
    if m:
        return f"{m.group(1)}{m.group(2)}"

    m = re.fullmatch(r"BAND\s+0?(\d{3})", su)
    if m:
        num = m.group(1)
        if num in {"151", "441", "463", "471"}:
            return f"A{num}"

    m = re.fullmatch(r"([AE])\s*0?(\d{3})", su)
    if m:
        return f"{m.group(1)}{m.group(2)}"

    return None


def is_table_header(line: str) -> bool:
    s = norm_spaces(line).lower()
    return "omschrijving controle" in s and "ok" in s and "nok" in s


def is_section_break(line: str) -> bool:
    s = norm_spaces(line).lower()
    if not s:
        return False
    return any(x in s for x in SECTION_STOP_WORDS)


def split_pipe_line(line: str) -> list[str]:
    parts = [p.strip() for p in line.split("|")]
    while parts and parts[-1] == "":
        parts.pop()
    return parts


def normalize_description(desc: str) -> str:
    d = norm_spaces(desc)
    d = re.sub(r"^\d+\s+", "", d).strip()
    d = norm_spaces(d)
    return d


def is_scraper_type_label(desc: str) -> bool:
    d = norm_spaces(desc).upper()

    patterns = [
        r"^U\s*\d{3,4}(\s+REV)?(\s+TRIPPER)?$",
        r"^UI\s*\d{3,4}(\s+REV)?(\s+TRIPPER)?$",
        r"^RI?\s*\d{3,4}-\d{3,4}(\s+SP/M3)?$",
        r"^R\s*\d{3,4}-\d{3,4}$",
        r"^TPH(\s+HDI?|\s+HD)?\s*\d{3,4}-\d{3,4}(\s*\(.+\))?$",
        r"^H\s*\d{3,4}-\d{3,4}(\s+SP/M3)?$",
    ]
    return any(re.fullmatch(p, d) for p in patterns)


def is_real_check_description(desc: str) -> bool:
    d = norm_spaces(desc).lower()
    return any(d.startswith(prefix) for prefix in KNOWN_CHECK_PREFIXES)


def should_skip_desc(desc: str) -> bool:
    d = norm_spaces(desc).lower()
    if not d:
        return True
    if looks_like_row_number(d):
        return True
    if "omschrijving controle" in d:
        return True
    if is_scraper_type_label(desc):
        return True
    return False


def parse_pipe_row(line: str) -> Optional[Tuple[str, Optional[bool], Optional[bool], Optional[str], Optional[str]]]:
    if "|" not in line:
        return None

    parts = split_pipe_line(line)
    if len(parts) < 2:
        return None

    desc = None
    ok_raw = ""
    nok_raw = ""
    remark = ""
    advice = ""

    if looks_like_row_number(parts[0]) and len(parts) >= 5:
        desc = parts[1]
        ok_raw = parts[2] if len(parts) > 2 else ""
        nok_raw = parts[3] if len(parts) > 3 else ""
        remark = parts[4] if len(parts) > 4 else ""
        advice = " | ".join(parts[5:]) if len(parts) > 5 else ""

    elif parts[0] == "" and len(parts) >= 5:
        desc = parts[1]
        ok_raw = parts[2] if len(parts) > 2 else ""
        nok_raw = parts[3] if len(parts) > 3 else ""
        remark = parts[4] if len(parts) > 4 else ""
        advice = " | ".join(parts[5:]) if len(parts) > 5 else ""

    elif len(parts) >= 4:
        desc = parts[0]
        ok_raw = parts[1] if len(parts) > 1 else ""
        nok_raw = parts[2] if len(parts) > 2 else ""
        remark = parts[3] if len(parts) > 3 else ""
        advice = " | ".join(parts[4:]) if len(parts) > 4 else ""

    if desc is None:
        return None

    desc = normalize_description(desc)
    if should_skip_desc(desc):
        return None

    ok_flag = True if is_true_token(ok_raw) else None
    nok_flag = True if is_true_token(nok_raw) else None

    if ok_flag is None and nok_flag is None:
        if is_true_token(remark):
            ok_flag = True
            remark = ""
        elif is_true_token(advice):
            ok_flag = True
            advice = ""

    remark = clean_text_value(remark)
    advice = clean_text_value(advice)

    if not is_real_check_description(desc):
        return None

    if ok_flag is None and nok_flag is None and remark is None and advice is None:
        return None

    return desc, ok_flag, nok_flag, remark, advice


def parse_checks_from_text(
    text_raw: str,
) -> Iterable[Tuple[str, str, Optional[bool], Optional[bool], Optional[str], Optional[str]]]:
    current_band: Optional[str] = None
    inside_table = False

    for raw_line in (text_raw or "").splitlines():
        line = norm_spaces(raw_line)
        if not line:
            continue

        band = is_band_heading(line)
        if band:
            current_band = band
            inside_table = False
            continue

        if is_table_header(line):
            inside_table = True
            continue

        if is_section_break(line):
            inside_table = False
            continue

        if not inside_table:
            continue

        parsed = parse_pipe_row(raw_line)
        if not parsed:
            continue

        if not current_band:
            continue

        desc, ok_flag, nok_flag, remark, advice = parsed
        yield current_band, desc, ok_flag, nok_flag, remark, advice


def run() -> None:
    load_dotenv()

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL ontbreekt in .env")

    print(f"DATABASE_URL = {database_url}")

    engine = create_engine(database_url)

    with engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {TARGET_TABLE} (
                id BIGSERIAL PRIMARY KEY,
                source_file TEXT,
                band_code TEXT,
                omschrijving TEXT,
                ok_flag BOOLEAN,
                nok_flag BOOLEAN,
                opmerking TEXT,
                advies TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))

        print(f"[INFO] Leegmaken {TARGET_TABLE} ...")
        conn.execute(text(f"TRUNCATE TABLE {TARGET_TABLE} RESTART IDENTITY"))

        rows = conn.execute(
            text(
                f"""
                SELECT source_file, file_name, lijn_code, text_raw
                FROM {SOURCE_TABLE}
                ORDER BY id
                """
            )
        ).fetchall()

        print(f"[INFO] bronbestanden: {len(rows)}")

        insert_sql = text(
            f"""
            INSERT INTO {TARGET_TABLE}
            (
                source_file,
                band_code,
                omschrijving,
                ok_flag,
                nok_flag,
                opmerking,
                advies
            )
            VALUES
            (
                :source_file,
                :band_code,
                :omschrijving,
                :ok_flag,
                :nok_flag,
                :opmerking,
                :advies
            )
            """
        )

        inserted = 0
        parsed_rows = 0

        for row in rows:
            source_file = row.source_file
            text_raw = row.text_raw or ""

            for band_code, omschrijving, ok_flag, nok_flag, opmerking, advies in parse_checks_from_text(text_raw):
                parsed_rows += 1

                conn.execute(
                    insert_sql,
                    {
                        "source_file": source_file,
                        "band_code": band_code,
                        "omschrijving": omschrijving,
                        "ok_flag": ok_flag,
                        "nok_flag": nok_flag,
                        "opmerking": opmerking,
                        "advies": advies,
                    },
                )
                inserted += 1

    print(f"[DONE] bronbestanden: {len(rows)}")
    print(f"[DONE] parsed_rows: {parsed_rows}")
    print(f"[DONE] inserted: {inserted}")


if __name__ == "__main__":
    run()