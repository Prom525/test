#!/usr/bin/env python3
"""
promote_to_inspections_v1.py

Promotes grouped rows from sb_stg_inspecties_raw into sb_inspections_v0 with:
- inspected_on derived from, in order:
  1) sheet name if dd-mm-yy(/yyyy)
  2) preferred: scan column C in first rows (incl. row 9)
  3) fallback: scan "Datum" rows and parse date from Unnamed 1..4
  4) week-sheet + inferred year
  5) year-only sheet name -> 1 Jan of that year

Run:
  $env:DB_URL = "postgresql://postgres:SterkWachtwoord123@127.0.0.1:15432/promati"
  python .\promote_to_inspections_v1.py
"""

import logging
import os
import re
import argparse
from datetime import datetime, date, timezone, timedelta

from sqlalchemy import create_engine, text

DB_URL = os.environ.get(
    "DB_URL",
    "postgresql://postgres:SterkWachtwoord123@127.0.0.1:15432/promati",
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("promote_to_inspections_v1")

RE_SHEET_DATE = re.compile(r"^\s*(\d{2})-(\d{2})-(\d{2,4})\s*$")
RE_WEEK_ANY = re.compile(r"^\s*week\s*\d+\s*$", re.I)
RE_WEEK_EXTRACT = re.compile(r"(?i)\bweek\b\W*0*(\d{1,2})\b")
RE_YEAR_ONLY = re.compile(r"^\s*((?:19|20)\d{2})\s*$")
RE_YEAR_ANY = re.compile(r"\b((?:19|20)\d{2})\b")

DATE_FORMATS = (
    "%d-%m-%Y",
    "%d-%m-%y",
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d/%m/%y",
    "%d.%m.%Y",
    "%d.%m.%y",
)

def parse_sheet_date(sheet: str) -> date | None:
    m = RE_SHEET_DATE.match(sheet or "")
    if not m:
        return None
    d, mth, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if y < 100:
        y = 2000 + y if y <= 79 else 1900 + y
    try:
        return date(y, mth, d)
    except ValueError:
        return None

def parse_year_only_sheet(sheet: str) -> date | None:
    m = RE_YEAR_ONLY.match(sheet or "")
    if not m:
        return None
    y = int(m.group(1))
    try:
        return date(y, 1, 1)
    except ValueError:
        return None

def extract_year_from_text(raw: str | None) -> int | None:
    if not raw:
        return None
    m = RE_YEAR_ANY.search(str(raw))
    if not m:
        return None
    y = int(m.group(1))
    return y if 1900 <= y <= 2100 else None

def parse_week_sheet(sheet: str, year: int | None) -> date | None:
    if not sheet or year is None:
        return None
    m = RE_WEEK_EXTRACT.search(sheet)
    if not m:
        return None
    week_no = int(m.group(1))
    if not (1 <= week_no <= 53):
        return None
    try:
        # ISO week, maandag van de week
        return datetime.strptime(f"{year} {week_no} 1", "%G %V %u").date()
    except ValueError:
        return None

def sheet_kind(sheet: str) -> str:
    if parse_sheet_date(sheet):
        return "date"
    if RE_WEEK_ANY.match(sheet or "") or RE_WEEK_EXTRACT.search(sheet or ""):
        return "week"
    if parse_year_only_sheet(sheet):
        return "year"
    return "other"

def normalize_sheet(sheet: str) -> str:
    s = (sheet or "").strip()
    s = re.sub(r"\s+", " ", s)
    m = RE_WEEK_EXTRACT.search(s)
    if m:
        wk = int(m.group(1))
        return f"week {wk}"
    return s

def ms_epoch_to_date(ms: int) -> date:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date()

def excel_serial_to_date(n: int) -> date | None:
    if n < 20000 or n > 80000:
        return None
    base = date(1899, 12, 30)
    return base + timedelta(days=int(n))

def parse_date_string(raw: str) -> date | None:
    raw = (raw or "").strip()
    if not raw:
        return None

    # probeer eerst directe formats
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue

    # haal een datumfragment uit tekst zoals "Datum: 12-03-01"
    m = re.search(r"(\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})", raw)
    if m:
        frag = m.group(1)
        for fmt in DATE_FORMATS:
            try:
                return datetime.strptime(frag, fmt).date()
            except ValueError:
                continue

    return None

def parse_any_date_value(raw) -> tuple[date | None, str | None]:
    """
    Try to parse a value that may be:
    - epoch-ms (12-13 digits)
    - Excel serial (4-6 digits)
    - date string
    Returns (date, source_tag_suffix)
    """
    s = "" if raw is None else str(raw).strip()
    if not s:
        return None, None

    digits = re.sub(r"[^0-9]", "", s)
    if re.fullmatch(r"\d{12,13}", digits or ""):
        return ms_epoch_to_date(int(digits)), "epoch"
    if re.fullmatch(r"\d{4,6}", digits or ""):
        d = excel_serial_to_date(int(digits))
        if d:
            return d, "excel_serial"

    d = parse_date_string(s)
    if d:
        return d, "string"

    return None, None

def ensure_schema(conn) -> None:
    conn.execute(text("""
      create table if not exists sb_inspections_v0 (
        id bigserial primary key,
        inspection_key text unique,
        lijn_code text not null,
        source_file text not null,
        sheet text not null,
        sheet_norm text,
        sheet_kind text,
        inspected_on date,
        inspected_on_source text,
        performed_by text,
        title text,
        row_count int,
        created_at timestamptz default now()
      )
    """))
    conn.execute(text("alter table sb_inspections_v0 add column if not exists sheet_norm text"))
    conn.execute(text("alter table sb_inspections_v0 add column if not exists sheet_kind text"))
    conn.execute(text("alter table sb_inspections_v0 add column if not exists inspected_on_source text"))
    conn.execute(text("alter table sb_inspections_v0 add column if not exists performed_by text"))
    conn.execute(text("alter table sb_inspections_v0 add column if not exists title text"))
    conn.execute(text("alter table sb_inspections_v0 add column if not exists row_count int"))
    conn.execute(text("alter table sb_inspections_v0 add column if not exists customer_code text"))
    conn.execute(text("alter table sb_inspections_v0 add column if not exists site_code text"))
    conn.execute(text("alter table sb_inspections_v0 add column if not exists last_seen_batch_id bigint"))

def main(mode: str = "incremental") -> None:
    engine = create_engine(DB_URL)

    if mode == "full-rebuild":
        q_groups = text("""
          select customer_code, site_code, lijn_code, source_file, sheet, count(*) as row_count
          from sb_stg_inspecties_raw
          where customer_code is not null
            and site_code is not null
            and lijn_code is not null
            and source_file is not null
            and sheet is not null
          group by customer_code, site_code, lijn_code, source_file, sheet
          order by customer_code, site_code, lijn_code, source_file, sheet
        """)
    else:
        q_groups = text("""
          select
              r.customer_code,
              r.site_code,
              r.lijn_code,
              r.source_file,
              r.sheet,
              count(*) as row_count
          from sb_stg_inspecties_raw r
          join vw_changed_inspection_sheets_todo_v1 c
            on c.customer_code = r.customer_code
           and c.site_code = r.site_code
           and c.source_file = r.source_file
           and c.sheet = r.sheet
          where r.customer_code is not null
            and r.site_code is not null
            and r.lijn_code is not null
            and r.source_file is not null
            and r.sheet is not null
          group by r.customer_code, r.site_code, r.lijn_code, r.source_file, r.sheet
          order by r.customer_code, r.site_code, r.lijn_code, r.source_file, r.sheet
        """)

    # scan kolom C in de eerste regels, niet alleen row 9
    q_col_c_scan = text("""
      select
        row_nr,
        trim(coalesce(data->'row'->>'Unnamed: 2','')) as c2_raw
      from sb_stg_inspecties_raw
      where lijn_code = :lijn_code
        and source_file = :source_file
        and sheet = :sheet
        and row_nr between 0 and 25
      order by
        case when row_nr = 9 then 0 else 1 end,
        row_nr
    """)

    # Fallback: scan "Datum" rows
    q_datum_rows = text("""
      select
        row_nr,
        trim(coalesce(data->'row'->>'Unnamed: 1','')) as u1,
        trim(coalesce(data->'row'->>'Unnamed: 2','')) as u2,
        trim(coalesce(data->'row'->>'Unnamed: 3','')) as u3,
        trim(coalesce(data->'row'->>'Unnamed: 4','')) as u4
      from sb_stg_inspecties_raw
      where lijn_code=:lijn_code and source_file=:source_file and sheet=:sheet
        and lower(trim(coalesce(data->'row'->>'Unnamed: 0',''))) like 'datum%'
      order by row_nr
      limit 50
    """)

    q_performed_by = text("""
      select trim(coalesce(data->'row'->>'Unnamed: 3','')) as v
      from sb_stg_inspecties_raw
      where lijn_code=:lijn_code and source_file=:source_file and sheet=:sheet
        and lower(trim(coalesce(data->'row'->>'Unnamed: 0',''))) like 'uitgevoerd door%'
      order by row_nr
      limit 1
    """)

    q_title = text("""
      select trim(coalesce(data->'row'->>'Unnamed: 0','')) as v
      from sb_stg_inspecties_raw
      where lijn_code=:lijn_code and source_file=:source_file and sheet=:sheet
        and row_nr = 5
        and coalesce(data->'row'->>'Unnamed: 0','') <> ''
      limit 1
    """)

    upsert = text("""
      insert into sb_inspections_v0
        (inspection_key, customer_code, site_code, lijn_code, source_file, sheet, sheet_norm, sheet_kind,
         inspected_on, inspected_on_source, performed_by, title, row_count)
      values
        (:inspection_key, :customer_code, :site_code, :lijn_code, :source_file, :sheet, :sheet_norm, :sheet_kind,
         :inspected_on, :inspected_on_source, :performed_by, :title, :row_count)
      on conflict (inspection_key) do update
        set customer_code = excluded.customer_code,
            site_code = excluded.site_code,
            sheet_norm = excluded.sheet_norm,
            sheet_kind = excluded.sheet_kind,
            inspected_on = excluded.inspected_on,
            inspected_on_source = excluded.inspected_on_source,
            performed_by = excluded.performed_by,
            title = excluded.title,
            row_count = excluded.row_count
    """)

    total = 0
    no_date = 0

    with engine.begin() as conn:
        ensure_schema(conn)

        groups = conn.execute(q_groups).fetchall()
        logger.info("groups: %s", len(groups))

        if mode == "incremental" and not groups:
            logger.info("INCREMENTAL: geen changed sheets gevonden. Niets te doen.")
            return

        for customer_code, site_code, lijn_code, source_file, sheet, row_count in groups:
            sk = sheet_kind(sheet)
            sn = normalize_sheet(sheet)

            inspected: date | None = None
            source: str | None = None

            logger.info("Parsing file=%s | sheet=%s", source_file, sheet)

            # 1) exacte datum uit sheetnaam
            inspected = parse_sheet_date(sheet)
            if inspected:
                source = "sheet"

            # 2) scan kolom C in eerste regels, met row 9 als voorkeur
            col_c_candidate: date | None = None
            col_c_candidate_source: str | None = None
            if not inspected:
                rows_c = conn.execute(
                    q_col_c_scan,
                    {"lijn_code": lijn_code, "source_file": source_file, "sheet": sheet},
                ).fetchall()

                for r in rows_c:
                    d, tag = parse_any_date_value(r.c2_raw or "")
                    if d:
                        col_c_candidate = d
                        col_c_candidate_source = f"column_c_r{int(r.row_nr)}_{tag}"
                        break

                if col_c_candidate:
                    inspected = col_c_candidate
                    source = col_c_candidate_source

            # 3) fallback: scan "Datum" rows
            if not inspected:
                rows = conn.execute(
                    q_datum_rows,
                    {"lijn_code": lijn_code, "source_file": source_file, "sheet": sheet},
                ).fetchall()

                candidates: list[tuple[date, str]] = []
                for r in rows:
                    for raw_val in (r.u1, r.u2, r.u3, r.u4):
                        d, tag = parse_any_date_value(raw_val or "")
                        if d and tag:
                            candidates.append((d, f"datum_row_r{int(r.row_nr)}_{tag}"))

                if candidates:
                    best_d, best_tag = max(candidates, key=lambda x: x[0])
                    inspected = best_d
                    source = best_tag

            # 4) week-sheet + inferred year
            if not inspected and sk == "week":
                inferred_year = extract_year_from_text(sheet)
                if inferred_year is None and col_c_candidate is not None:
                    inferred_year = col_c_candidate.year
                if inferred_year is None:
                    inferred_year = extract_year_from_text(source_file)

                week_dt = parse_week_sheet(sheet, inferred_year)
                if week_dt:
                    inspected = week_dt
                    source = f"sheet_week_{inferred_year}"

            # 5) year-only sheetnaam
            if not inspected:
                year_dt = parse_year_only_sheet(sheet)
                if year_dt:
                    inspected = year_dt
                    source = "sheet_year_only"

            performed = conn.execute(
                q_performed_by,
                {"lijn_code": lijn_code, "source_file": source_file, "sheet": sheet},
            ).scalar()
            performed = (performed or "").strip() or None

            title = conn.execute(
                q_title,
                {"lijn_code": lijn_code, "source_file": source_file, "sheet": sheet},
            ).scalar()
            title = (title or "").strip() or None

            if inspected:
                logger.info(
                    "Datum gevonden: file=%s | sheet=%s | inspected_on=%s | source=%s",
                    source_file, sheet, inspected.isoformat(), source
                )
            else:
                no_date += 1
                logger.warning(
                    "GEEN DATUM: file=%s | sheet=%s | kind=%s",
                    source_file, sheet, sk
                )

            if inspected:
                key = (
                    f"{customer_code}|{site_code}|"
                    f"{source_file}|{sn}|{inspected.isoformat()}"
                )
            else:
                no_date += 1
                logger.warning(
                    "SKIP HEADER ZONDER DATUM: file=%s | sheet=%s | kind=%s",
                    source_file, sheet, sk
                )
                continue

            conn.execute(
                upsert,
                {
                    "inspection_key": key,
                    "customer_code": customer_code,
                    "site_code": site_code,
                    "lijn_code": lijn_code,
                    "source_file": source_file,
                    "sheet": sheet,
                    "sheet_norm": sn,
                    "sheet_kind": sk,
                    "inspected_on": inspected,
                    "inspected_on_source": source,
                    "performed_by": performed,
                    "title": title,
                    "row_count": int(row_count),
                },
            )

            total += 1
            if total % 250 == 0:
                logger.info("processed %s/%s", total, len(groups))

    logger.info("DONE inspections upserted: %s", total)
    logger.info("DONE inspections without date: %s", no_date)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Promote Excel inspection headers naar sb_inspections_v0"
    )
    parser.add_argument(
        "--mode",
        choices=["incremental", "full-rebuild"],
        default="incremental",
        help="incremental = alleen changed sheets; full-rebuild = volledige herbouw",
    )
    args = parser.parse_args()

    main(mode=args.mode)