#!/usr/bin/env python3
"""
Importeert .doc en .docx inspectierapporten recursief uit een mapstructuur,
extraheert metadata/banden/checks/schrapers/foto's en schrijft alles weg naar PostgreSQL.

Opzet:
- Oude .doc bestanden worden eerst geconverteerd naar .docx (Windows + Word vereist)
- Data gaat bewust eerst naar staging-tabellen
- Er wordt een beste-poging match gedaan naar sb_inspections_v0
- Onzekere of niet-gematchte records blijven gewoon behouden in staging

Gebruik:
    python import_inspectie_docx_doc.py \
        --root "C:\\Users\\John Koenders\\Baucotech\\Logbooks - Documenten\\Onderhouds Logboeken - Rapport Entretiens\\NL\\TATA steel\\Inspectie lijsten Tata Steel" \
        --pg-host localhost --pg-port 15432 --pg-db promati --pg-user postgres --pg-password secret \
        --photo-dir "C:\\temp\\inspectie_fotos"

Benodigd:
    pip install python-docx psycopg2-binary pywin32

Opmerking:
- Parser is bewust defensief geschreven voor semi-gestructureerde Word-documenten.
- Eerst op een kleine subset testen.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, date
from pathlib import Path
from typing import Iterable, Iterator, Optional

import psycopg2
from psycopg2.extras import execute_values
from docx import Document
from docx.document import Document as _Document
from docx.oxml.ns import qn
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph

try:
    import win32com.client  # type: ignore
except Exception:
    win32com = None


CHECK_MAP = {
    "werking schrapers": "werking_schrapers",
    "werking schraper": "werking_schrapers",
    "band algemene staat/ las": "band_algemene_staat",
    "band algemene staat/las": "band_algemene_staat",
    "band algemene staat": "band_algemene_staat",
    "band loop t.o.v. trommels.": "band_loop_tov_trommels",
    "band loop t.o.v. trommels": "band_loop_tov_trommels",
    "band loop tov trommels": "band_loop_tov_trommels",
    "vervuiling onder de band": "vervuiling_onder_band",
    "afdichting stortpunt": "afdichting_stortpunt",
    "slijttegels": "slijttegels",
    "staat van de constructie": "staat_constructie",
    "morsgoot": "morsgoot",
}

SCRAPER_PREFIXES = (
    "U", "UI", "HI", "H", "R", "RI", "TPH", "TPH HD", "TPH HDI", "TPL",
    "P", "I", "Tussenpart", "Tussenpart schraper"
)

BAND_RE = re.compile(r"^\s*Band\s+([A-Z]?[A-Z0-9]+)\s*$", re.IGNORECASE)
DATE_RE = re.compile(r"(\d{2})-(\d{2})-(\d{4})")
POSITION_RE = re.compile(r"\b(oost|west|noord|zuid)\b", re.IGNORECASE)
DIRECTION_RE = re.compile(r"\b(rev(?:ersibele)?|reversible|reversibele)\b", re.IGNORECASE)
LINE_HINTS = [
    (re.compile(r"kofa\s*1", re.IGNORECASE), "KOFA1"),
    (re.compile(r"kofa\s*2", re.IGNORECASE), "KOFA2"),
    (re.compile(r"mv\s*1|mengveld\s*1|afgraaflijn\s*mv1", re.IGNORECASE), "MV1"),
    (re.compile(r"pellet", re.IGNORECASE), "PELLET"),
    (re.compile(r"sinter", re.IGNORECASE), "SINTER"),
]


@dataclass
class CheckRow:
    check_code: str
    check_label: str
    status: str
    remark: Optional[str] = None
    advice: Optional[str] = None


@dataclass
class ScraperRow:
    scraper_raw: str
    scraper_model: Optional[str] = None
    scraper_family: Optional[str] = None
    position_hint: Optional[str] = None
    direction_hint: Optional[str] = None
    status: str = "UNKNOWN"
    remark: Optional[str] = None


@dataclass
class BandRow:
    band_code: str
    band_label: str
    sort_order: int
    checks: list[CheckRow] = field(default_factory=list)
    scrapers: list[ScraperRow] = field(default_factory=list)


@dataclass
class ParsedInspection:
    doc_key: str
    source_path: str
    source_name: str
    source_ext: str
    document_date: Optional[date]
    performed_by_raw: Optional[str]
    supervisor: Optional[str]
    description: Optional[str]
    title: Optional[str]
    line_hint: Optional[str]
    has_photos: bool
    raw_header_json: str
    bands: list[BandRow] = field(default_factory=list)
    matched_inspection_key: Optional[str] = None
    match_status: str = "UNMATCHED"
    match_note: Optional[str] = None


class DocImportError(Exception):
    pass


def normalize_space(text: Optional[str]) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def normalize_check_label(label: str) -> str:
    text = normalize_space(label).lower()
    return CHECK_MAP.get(text, re.sub(r"[^a-z0-9]+", "_", text).strip("_"))


def infer_line_hint(*parts: str) -> Optional[str]:
    blob = " ".join(p for p in parts if p)
    for pattern, code in LINE_HINTS:
        if pattern.search(blob):
            return code
    return None


def safe_parse_date(text: Optional[str]) -> Optional[date]:
    if not text:
        return None
    m = DATE_RE.search(text)
    if not m:
        return None
    dd, mm, yyyy = m.groups()
    try:
        return datetime.strptime(f"{dd}-{mm}-{yyyy}", "%d-%m-%Y").date()
    except ValueError:
        return None


def make_doc_key(path: Path, doc_date: Optional[date]) -> str:
    base = f"{path.resolve()}|{doc_date.isoformat() if doc_date else 'no_date'}"
    digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:24]
    return f"DOC|{digest}"


def convert_doc_to_docx(doc_path: Path, temp_dir: Path) -> Path:
    if win32com is None:
        raise DocImportError("pywin32/Word COM is niet beschikbaar; .doc kan niet geconverteerd worden.")

    out_path = temp_dir / f"{doc_path.stem}.converted.docx"
    word = win32com.client.DispatchEx("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    doc = None
    try:
        doc = word.Documents.Open(str(doc_path), ReadOnly=True)
        doc.SaveAs(str(out_path), FileFormat=16)  # wdFormatDocumentDefault = .docx
        return out_path
    finally:
        if doc is not None:
            doc.Close(False)
        word.Quit()


def iter_block_items(parent: _Document | _Cell) -> Iterator[Paragraph | Table]:
    if isinstance(parent, _Document):
        parent_elm = parent.element.body
    else:
        parent_elm = parent._tc

    for child in parent_elm.iterchildren():
        if child.tag.endswith("}p"):
            yield Paragraph(child, parent)
        elif child.tag.endswith("}tbl"):
            yield Table(child, parent)


def table_to_grid(table: Table) -> list[list[str]]:
    grid: list[list[str]] = []
    for row in table.rows:
        values = [normalize_space(cell.text) for cell in row.cells]
        if any(values):
            grid.append(values)
    return grid


def detect_status(row_text: str) -> str:
    text = f" {row_text.lower()} "
    has_v = " v " in text or text.strip() == "v"
    has_x = " x " in text or text.strip() == "x"
    if has_x and not has_v:
        return "NOK"
    if has_v and not has_x:
        return "OK"
    return "UNKNOWN"


def is_scraper_line(text: str) -> bool:
    t = normalize_space(text)
    if not t:
        return False
    upper = t.upper()
    return any(upper.startswith(prefix) for prefix in SCRAPER_PREFIXES)


def parse_scraper(text: str) -> ScraperRow:
    raw = normalize_space(text)
    pos = POSITION_RE.search(raw)
    direction = DIRECTION_RE.search(raw)
    family = None
    model = raw

    for prefix in sorted(SCRAPER_PREFIXES, key=len, reverse=True):
        if raw.upper().startswith(prefix.upper()):
            family = prefix.upper()
            break

    return ScraperRow(
        scraper_raw=raw,
        scraper_model=model,
        scraper_family=family,
        position_hint=pos.group(1).lower() if pos else None,
        direction_hint=direction.group(1).lower() if direction else None,
    )


def extract_header_from_paragraphs(paragraphs: list[str]) -> dict[str, Optional[str]]:
    info: dict[str, Optional[str]] = {
        "date_text": None,
        "inspecteur": None,
        "toezichthouder": None,
        "omschrijving": None,
        "title": None,
    }

    for idx, line in enumerate(paragraphs):
        low = line.lower()
        if low == "datum:" and idx + 1 < len(paragraphs):
            info["date_text"] = paragraphs[idx + 1]
        elif low == "inspecteur" and idx + 1 < len(paragraphs):
            info["inspecteur"] = paragraphs[idx + 1]
        elif low == "toezichthouder" and idx + 1 < len(paragraphs):
            info["toezichthouder"] = paragraphs[idx + 1]
        elif low == "omschrijving" and idx + 1 < len(paragraphs):
            info["omschrijving"] = paragraphs[idx + 1]

    for line in paragraphs:
        if line.lower().startswith("inspectie "):
            info["title"] = line
            break

    return info


def parse_band_table(grid: list[list[str]], band_code: str, band_label: str, sort_order: int) -> BandRow:
    band = BandRow(band_code=band_code, band_label=band_label, sort_order=sort_order)
    current_check_status = "UNKNOWN"

    for row in grid:
        row_text = " | ".join(c for c in row if c)
        if not row_text:
            continue

        first_non_empty = next((c for c in row if c), "")
        normalized_first = normalize_space(first_non_empty)
        low_first = normalized_first.lower()

        if low_first in CHECK_MAP:
            status = detect_status(row_text)
            remark = None
            advice = None
            # simpele aanpak: laatste 2 niet-standaard cellen als remark/advice proberen te pakken
            non_empty = [c for c in row if c]
            if len(non_empty) >= 4:
                tail = non_empty[-2:]
                if tail[0] not in {"V", "X"}:
                    remark = tail[0]
                if tail[-1] not in {"V", "X"} and tail[-1] != remark:
                    advice = tail[-1]
            band.checks.append(CheckRow(
                check_code=normalize_check_label(normalized_first),
                check_label=normalized_first,
                status=status,
                remark=remark,
                advice=advice,
            ))
            current_check_status = status
            continue

        if is_scraper_line(normalized_first):
            scraper = parse_scraper(normalized_first)
            scraper.status = current_check_status
            band.scrapers.append(scraper)
            continue

        # Speciale regel: soms staat opmerking los onder een check
        if band.checks and len([c for c in row if c]) <= 2 and normalized_first and normalized_first not in {"V", "X"}:
            last = band.checks[-1]
            if not last.remark:
                last.remark = normalized_first
            else:
                last.advice = normalized_first

    return band


def parse_docx(docx_path: Path, original_path: Path) -> ParsedInspection:
    doc = Document(str(docx_path))
    paras = [normalize_space(p.text) for p in doc.paragraphs if normalize_space(p.text)]
    header = extract_header_from_paragraphs(paras)
    doc_date = safe_parse_date(header.get("date_text") or original_path.name)
    source_name = original_path.name
    line_hint = infer_line_hint(source_name, header.get("omschrijving") or "", header.get("title") or "")
    has_photos = bool(doc.part._rels)

    parsed = ParsedInspection(
        doc_key=make_doc_key(original_path, doc_date),
        source_path=str(original_path),
        source_name=source_name,
        source_ext=original_path.suffix.lower(),
        document_date=doc_date,
        performed_by_raw=header.get("inspecteur"),
        supervisor=header.get("toezichthouder"),
        description=header.get("omschrijving"),
        title=header.get("title") or header.get("omschrijving"),
        line_hint=line_hint,
        has_photos=has_photos,
        raw_header_json=json.dumps(header, ensure_ascii=False),
    )

    current_band_code: Optional[str] = None
    current_band_label: Optional[str] = None
    sort_order = 0

    for block in iter_block_items(doc):
        if isinstance(block, Paragraph):
            text = normalize_space(block.text)
            if not text:
                continue
            m = BAND_RE.match(text)
            if m:
                sort_order += 1
                current_band_code = m.group(1).upper()
                current_band_label = text
        else:
            if current_band_code:
                grid = table_to_grid(block)
                if grid:
                    band = parse_band_table(grid, current_band_code, current_band_label or f"Band {current_band_code}", sort_order)
                    if band.checks or band.scrapers:
                        parsed.bands.append(band)
                current_band_code = None
                current_band_label = None

    return parsed


def ensure_tables(conn) -> None:
    sql = """
    CREATE TABLE IF NOT EXISTS stg_doc_inspections (
        doc_key text PRIMARY KEY,
        source_path text NOT NULL UNIQUE,
        source_name text NOT NULL,
        source_ext text NOT NULL,
        document_date date NULL,
        performed_by_raw text NULL,
        supervisor text NULL,
        description text NULL,
        title text NULL,
        line_hint text NULL,
        has_photos boolean NOT NULL DEFAULT false,
        raw_header_json jsonb NULL,
        matched_inspection_key text NULL,
        match_status text NOT NULL DEFAULT 'UNMATCHED',
        match_note text NULL,
        imported_at timestamptz NOT NULL DEFAULT now(),
        updated_at timestamptz NOT NULL DEFAULT now()
    );

    CREATE TABLE IF NOT EXISTS stg_doc_band_items (
        band_item_id bigserial PRIMARY KEY,
        doc_key text NOT NULL REFERENCES stg_doc_inspections(doc_key) ON DELETE CASCADE,
        band_code text NOT NULL,
        band_label text NULL,
        sort_order integer NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now(),
        UNIQUE (doc_key, band_code, sort_order)
    );

    CREATE TABLE IF NOT EXISTS stg_doc_checks (
        check_id bigserial PRIMARY KEY,
        band_item_id bigint NOT NULL REFERENCES stg_doc_band_items(band_item_id) ON DELETE CASCADE,
        check_code text NOT NULL,
        check_label text NOT NULL,
        status text NOT NULL,
        remark text NULL,
        advice text NULL,
        created_at timestamptz NOT NULL DEFAULT now(),
        UNIQUE (band_item_id, check_code)
    );

    CREATE TABLE IF NOT EXISTS stg_doc_scrapers (
        scraper_obs_id bigserial PRIMARY KEY,
        band_item_id bigint NOT NULL REFERENCES stg_doc_band_items(band_item_id) ON DELETE CASCADE,
        scraper_raw text NOT NULL,
        scraper_model text NULL,
        scraper_family text NULL,
        position_hint text NULL,
        direction_hint text NULL,
        status text NOT NULL DEFAULT 'UNKNOWN',
        remark text NULL,
        created_at timestamptz NOT NULL DEFAULT now(),
        UNIQUE (band_item_id, scraper_raw)
    );

    CREATE TABLE IF NOT EXISTS stg_doc_import_log (
        source_path text PRIMARY KEY,
        status text NOT NULL,
        message text NULL,
        imported_at timestamptz NOT NULL DEFAULT now()
    );
    """
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def match_existing_inspection(conn, parsed: ParsedInspection) -> tuple[Optional[str], str, Optional[str]]:
    """Voorzichtig matchen. Alleen exact koppelen als er precies 1 kandidaat is."""
    if not parsed.document_date:
        return None, "UNMATCHED", "geen datum gevonden"

    with conn.cursor() as cur:
        if parsed.line_hint:
            cur.execute(
                """
                SELECT inspection_key
                FROM sb_inspections_v0
                WHERE inspected_on = %s
                  AND lijn_code = %s
                ORDER BY inspection_key
                LIMIT 5
                """,
                (parsed.document_date, parsed.line_hint),
            )
            rows = cur.fetchall()
            if len(rows) == 1:
                return rows[0][0], "MATCHED", "exacte match op datum + lijn_code"
            if len(rows) > 1:
                return None, "AMBIGUOUS", f"meerdere matches op datum + lijn_code ({len(rows)})"

        cur.execute(
            """
            SELECT inspection_key, lijn_code, title
            FROM sb_inspections_v0
            WHERE inspected_on = %s
            ORDER BY inspection_key
            LIMIT 20
            """,
            (parsed.document_date,),
        )
        rows = cur.fetchall()
        if len(rows) == 1:
            return rows[0][0], "MATCHED", "exacte match op datum (enige record die dag)"
        if len(rows) == 0:
            return None, "UNMATCHED", "geen inspectie op dezelfde datum"
        return None, "AMBIGUOUS", f"meerdere inspecties op dezelfde datum ({len(rows)})"

def dedupe_checks(checks: list[CheckRow]) -> list[CheckRow]:
    """
    Voorkomt dubbele (band_item_id, check_code) waarden binnen één execute_values batch.
    Laatste niet-lege waarden winnen.
    """

    result: dict[str, CheckRow] = {}

    for check in checks or []:
        key = check.check_code

        if key not in result:
            result[key] = check
            continue

        existing = result[key]

        existing.check_label = check.check_label or existing.check_label
        existing.status = check.status or existing.status
        existing.remark = check.remark or existing.remark
        existing.advice = check.advice or existing.advice

    return list(result.values())


def dedupe_scrapers(scrapers: list[ScraperRow]) -> list[ScraperRow]:
    """
    Voorkomt dubbele (band_item_id, scraper_raw) waarden binnen één execute_values batch.
    Laatste niet-lege waarden winnen.
    """

    result: dict[str, ScraperRow] = {}

    for scraper in scrapers or []:
        key = normalize_space(scraper.scraper_raw)

        if not key:
            continue

        if key not in result:
            result[key] = scraper
            continue

        existing = result[key]

        existing.scraper_model = scraper.scraper_model or existing.scraper_model
        existing.scraper_family = scraper.scraper_family or existing.scraper_family
        existing.position_hint = scraper.position_hint or existing.position_hint
        existing.direction_hint = scraper.direction_hint or existing.direction_hint
        existing.status = scraper.status or existing.status
        existing.remark = scraper.remark or existing.remark

    return list(result.values())

def reuse_existing_doc_key_for_source_path(conn, parsed: ParsedInspection) -> None:
    """
    Als source_path al bestaat, behoud dan de bestaande doc_key.

    Waarom:
    - stg_doc_inspections.source_path is UNIQUE
    - doc_key kan wijzigen als datumextractie of padlogica verandert
    - child tables hangen aan doc_key
    """

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT doc_key
            FROM stg_doc_inspections
            WHERE source_path = %s
            """,
            (parsed.source_path,),
        )

        row = cur.fetchone()

    if row and row[0] and row[0] != parsed.doc_key:
        parsed.doc_key = row[0]

def upsert_parsed(conn, parsed: ParsedInspection) -> None:
    reuse_existing_doc_key_for_source_path(conn, parsed)

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO stg_doc_inspections (
                doc_key, source_path, source_name, source_ext, document_date,
                performed_by_raw, supervisor, description, title, line_hint,
                has_photos, raw_header_json, matched_inspection_key, match_status, match_note, updated_at
            ) VALUES (
                %(doc_key)s, %(source_path)s, %(source_name)s, %(source_ext)s, %(document_date)s,
                %(performed_by_raw)s, %(supervisor)s, %(description)s, %(title)s, %(line_hint)s,
                %(has_photos)s, %(raw_header_json)s::jsonb, %(matched_inspection_key)s, %(match_status)s, %(match_note)s, now()
            )
            ON CONFLICT (doc_key) DO UPDATE SET
                source_path = EXCLUDED.source_path,
                source_name = EXCLUDED.source_name,
                source_ext = EXCLUDED.source_ext,
                document_date = EXCLUDED.document_date,
                performed_by_raw = EXCLUDED.performed_by_raw,
                supervisor = EXCLUDED.supervisor,
                description = EXCLUDED.description,
                title = EXCLUDED.title,
                line_hint = EXCLUDED.line_hint,
                has_photos = EXCLUDED.has_photos,
                raw_header_json = EXCLUDED.raw_header_json,
                matched_inspection_key = EXCLUDED.matched_inspection_key,
                match_status = EXCLUDED.match_status,
                match_note = EXCLUDED.match_note,
                updated_at = now()
            """,
            parsed.__dict__,
        )

        cur.execute("DELETE FROM stg_doc_band_items WHERE doc_key = %s", (parsed.doc_key,))

        for band in parsed.bands:
            cur.execute(
                """
                INSERT INTO stg_doc_band_items (doc_key, band_code, band_label, sort_order)
                VALUES (%s, %s, %s, %s)
                RETURNING band_item_id
                """,
                (parsed.doc_key, band.band_code, band.band_label, band.sort_order),
            )
            band_item_id = cur.fetchone()[0]

            deduped_checks = dedupe_checks(band.checks)

            if deduped_checks:
                execute_values(
                    cur,
                    """
                    INSERT INTO stg_doc_checks (band_item_id, check_code, check_label, status, remark, advice)
                    VALUES %s
                    ON CONFLICT (band_item_id, check_code) DO UPDATE SET
                        check_label = EXCLUDED.check_label,
                        status = EXCLUDED.status,
                        remark = EXCLUDED.remark,
                        advice = EXCLUDED.advice
                    """,
                    [
                        (band_item_id, c.check_code, c.check_label, c.status, c.remark, c.advice)
                        for c in deduped_checks
                    ],
                )

            deduped_scrapers = dedupe_scrapers(band.scrapers)

            if deduped_scrapers:
                execute_values(
                    cur,
                    """
                    INSERT INTO stg_doc_scrapers (
                        band_item_id, scraper_raw, scraper_model, scraper_family,
                        position_hint, direction_hint, status, remark
                    ) VALUES %s
                    ON CONFLICT (band_item_id, scraper_raw) DO UPDATE SET
                        scraper_model = EXCLUDED.scraper_model,
                        scraper_family = EXCLUDED.scraper_family,
                        position_hint = EXCLUDED.position_hint,
                        direction_hint = EXCLUDED.direction_hint,
                        status = EXCLUDED.status,
                        remark = EXCLUDED.remark
                    """,
                    [
                        (
                            band_item_id,
                            s.scraper_raw,
                            s.scraper_model,
                            s.scraper_family,
                            s.position_hint,
                            s.direction_hint,
                            s.status,
                            s.remark,
                        )
                        for s in deduped_scrapers
                    ],
                )

        cur.execute(
            """
            INSERT INTO stg_doc_import_log (source_path, status, message, imported_at)
            VALUES (%s, %s, %s, now())
            ON CONFLICT (source_path) DO UPDATE SET
                status = EXCLUDED.status,
                message = EXCLUDED.message,
                imported_at = now()
            """,
            (parsed.source_path, "OK", f"bands={len(parsed.bands)}"),
        )
    conn.commit()


def log_failure(conn, path: Path, message: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO stg_doc_import_log (source_path, status, message, imported_at)
            VALUES (%s, %s, %s, now())
            ON CONFLICT (source_path) DO UPDATE SET
                status = EXCLUDED.status,
                message = EXCLUDED.message,
                imported_at = now()
            """,
            (str(path), "ERROR", message[:4000]),
        )
    conn.commit()


def collect_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".doc", ".docx"}:
            files.append(path)
    return sorted(files)


def connect_pg(args):
    return psycopg2.connect(
        host=args.pg_host,
        port=args.pg_port,
        dbname=args.pg_db,
        user=args.pg_user,
        password=args.pg_password,
    )


def parse_one(path: Path, temp_dir: Path) -> ParsedInspection:
    docx_path = path
    if path.suffix.lower() == ".doc":
        docx_path = convert_doc_to_docx(path, temp_dir)
    return parse_docx(docx_path, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, help="Hoofdmap met .doc/.docx bestanden")
    parser.add_argument("--pg-host", default=os.getenv("PGHOST", "localhost"))
    parser.add_argument("--pg-port", type=int, default=int(os.getenv("PGPORT", "15432")))
    parser.add_argument("--pg-db", default=os.getenv("PGDATABASE", "promati"))
    parser.add_argument("--pg-user", default=os.getenv("PGUSER", "postgres"))
    parser.add_argument("--pg-password", default=os.getenv("PGPASSWORD", ""))
    parser.add_argument("--limit", type=int, default=0, help="Alleen eerste N bestanden importeren")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )

    root = Path(args.root)
    if not root.exists():
        logging.error("Map niet gevonden: %s", root)
        return 2

    files = collect_files(root)
    if args.limit > 0:
        files = files[: args.limit]

    logging.info("%s bestanden gevonden", len(files))
    if not files:
        return 0

    conn = connect_pg(args)
    ensure_tables(conn)

    ok_count = 0
    err_count = 0
    with tempfile.TemporaryDirectory(prefix="doc_import_") as tmp:
        temp_dir = Path(tmp)
        for idx, path in enumerate(files, 1):
            logging.info("[%s/%s] %s", idx, len(files), path)
            try:
                parsed = parse_one(path, temp_dir)
                matched_key, match_status, match_note = match_existing_inspection(conn, parsed)
                parsed.matched_inspection_key = matched_key
                parsed.match_status = match_status
                parsed.match_note = match_note

                if args.dry_run:
                    logging.info(
                        "DRY-RUN %s date=%s line_hint=%s bands=%s match=%s",
                        path.name,
                        parsed.document_date,
                        parsed.line_hint,
                        len(parsed.bands),
                        parsed.match_status,
                    )
                else:
                    upsert_parsed(conn, parsed)
                ok_count += 1
            except Exception as exc:
                err_count += 1
                logging.exception("Fout bij %s", path)

                if not args.dry_run:
                    try:
                        conn.rollback()
                        log_failure(conn, path, repr(exc))
                    except Exception:
                        logging.exception("Kon fout niet loggen voor %s", path)

    logging.info("Klaar. OK=%s ERROR=%s", ok_count, err_count)
    conn.close()
    return 0 if err_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
