from __future__ import annotations

import os
import re
from typing import Optional, Literal, Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

router = APIRouter(prefix="/analysis", tags=["analysis"])

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:SterkWachtwoord123@postgres:5432/promati",
)

engine: Engine = create_engine(DATABASE_URL, pool_pre_ping=True)

KNOWN_LIJN_CODES = {
    "GSL",
    "MV1",
    "MV2",
    "KOFA1",
    "KOFA2",
    "EO1",
    "PEFA",
    "SIFA",
    "HOO6",
    "HOO7",
    "KOLEN2",
}

BAND_CODE_PATTERN = re.compile(r"\b([A-Z]{1,3}\s?[0-9]{1,4})\b", re.IGNORECASE)
SCRAPER_PATTERN = re.compile(
    r"\b(UI|TPH|TPL|RI|RV|AF|H|U)\s*[0-9]{2,4}(?:[-/][0-9]{2,4})?(?:\s+[A-Z0-9/]+)*\b",
    re.IGNORECASE,
)


def fetch_all(sql: str, params: dict) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
    return [dict(r) for r in rows]


def fetch_one(sql: str, params: dict) -> Optional[dict]:
    with engine.connect() as conn:
        row = conn.execute(text(sql), params).mappings().first()
    return dict(row) if row else None


class GPTQueryRequest(BaseModel):
    vraag: str
    lijn_code: Optional[str] = None
    scraper_position: Optional[str] = None
    min_abs_impact: float = 0.03
    limit: int = 15


class AssistantAskRequest(BaseModel):
    vraag: str
    lijn_code: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    limit: int = 100


def normalize_code(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return re.sub(r"\s+", "", value).upper()


def extract_band_code(vraag: str) -> Optional[str]:
    matches = BAND_CODE_PATTERN.findall(vraag or "")
    if not matches:
        return None

    cleaned = []
    for m in matches:
        code = normalize_code(m)
        if code in KNOWN_LIJN_CODES:
            continue
        cleaned.append(code)

    return cleaned[0] if cleaned else None


def extract_lijn_code(vraag: str, explicit_lijn_code: Optional[str]) -> Optional[str]:
    if explicit_lijn_code:
        return normalize_code(explicit_lijn_code)

    vraag_up = (vraag or "").upper()
    for code in sorted(KNOWN_LIJN_CODES, key=len, reverse=True):
        if code in vraag_up:
            return code
    return None


def extract_scraper_type(vraag: str) -> Optional[str]:
    m = SCRAPER_PATTERN.search(vraag or "")
    if not m:
        return None
    return re.sub(r"\s+", " ", m.group(0).strip()).upper()


def detect_intent(
    vraag: str,
    band_code: Optional[str],
    lijn_code: Optional[str],
    scraper_type: Optional[str],
) -> str:
    q = (vraag or "").lower()

    if band_code:
        return "band"
    if scraper_type:
        return "scraper"
    if lijn_code:
        return "location"
    if any(w in q for w in ["dataset", "overzicht", "hoeveel", "samenvatting", "summary", "totaal"]):
        return "dataset"
    return "dataset"


def build_date_filters(
    date_from: Optional[str],
    date_to: Optional[str],
    alias: str = "",
) -> tuple[list[str], dict]:
    conditions: list[str] = []
    params: dict[str, Any] = {}

    prefix = f"{alias}." if alias else ""

    if date_from:
        conditions.append(f"{prefix}effective_date >= :date_from")
        params["date_from"] = date_from

    if date_to:
        conditions.append(f"{prefix}effective_date <= :date_to")
        params["date_to"] = date_to

    return conditions, params


def summarize_band_question(
    band_code: str,
    lijn_code: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
) -> dict:
    conditions = ["band_locatie_norm = :band_code"]
    params: dict[str, Any] = {"band_code": band_code}

    if lijn_code:
        conditions.append("lijn_code = :lijn_code")
        params["lijn_code"] = lijn_code

    date_conditions, date_params = build_date_filters(date_from, date_to)
    conditions.extend(date_conditions)
    params.update(date_params)

    where_sql = " AND ".join(conditions)

    summary_sql = f"""
        SELECT
            band_locatie_norm,
            MIN(effective_date) AS eerste_datum,
            MAX(effective_date) AS laatste_datum,
            COUNT(*) AS n_rows,
            COUNT(*) FILTER (WHERE record_type = 'POSITION') AS n_positions,
            COUNT(*) FILTER (WHERE record_type = 'OBSERVATION') AS n_observations,
            COUNT(*) FILTER (WHERE mes_num IS NOT NULL) AS n_mesmetingen,
            AVG(mes_num)::numeric(10,2) AS avg_mes_num,
            MAX(mes_num) AS max_mes_num,
            MIN(mes_num) AS min_mes_num,
            COUNT(*) FILTER (WHERE vervangen = TRUE) AS n_vervangen,
            COUNT(*) FILTER (WHERE reinigen = TRUE) AS n_reinigen,
            COUNT(*) FILTER (WHERE demontage = TRUE) AS n_demontage,
            COUNT(*) FILTER (WHERE montage = TRUE) AS n_montage,
            COUNT(*) FILTER (WHERE afstellen = TRUE) AS n_afstellen,
            COUNT(*) FILTER (WHERE hosch_flag = TRUE) AS n_hosch,
            COUNT(*) FILTER (WHERE opmerking_raw ILIKE '%vervuil%') AS n_vervuiling,
            COUNT(*) FILTER (WHERE opmerking_raw ILIKE '%scheef%') AS n_scheefloop,
            COUNT(*) FILTER (WHERE opmerking_raw ILIKE '%mors%') AS n_mors,
            COUNT(DISTINCT scraper_type_effective_norm) FILTER (
                WHERE scraper_type_effective_norm IS NOT NULL
            ) AS n_scraper_types,
            STRING_AGG(DISTINCT scraper_type_effective_norm, ' | ')
                FILTER (WHERE scraper_type_effective_norm IS NOT NULL) AS scraper_types
        FROM vw_inspection_full_dataset_v1
        WHERE {where_sql}
        GROUP BY band_locatie_norm
    """
    summary = fetch_one(summary_sql, params)

    timeline_sql = f"""
        SELECT
            effective_date,
            COUNT(*) AS n_rows,
            AVG(mes_num)::numeric(10,2) AS avg_mes_num,
            COUNT(*) FILTER (WHERE vervangen = TRUE) AS n_vervangen,
            COUNT(*) FILTER (WHERE opmerking_raw ILIKE '%vervuil%') AS n_vervuiling,