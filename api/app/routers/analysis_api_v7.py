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
    "postgresql+psycopg2://postgres:5432/promati",
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

SIGNAL_TERMS = [
    "band",
    "scheef",
    "scheefloop",
    "trommel",
    "splice",
    "vervuil",
    "mors",
    "morsgoot",
    "nat",
    "materiaalopbouw",
    "uithouder",
    "druk",
    "lager",
    "frame",
    "steun",
    "niet zichtbaar",
    "niet toegankelijk",
    "steiger",
    "mes",
    "vervang",
    "cassette",
    "hosch",
]


def fetch_all(sql: str, params: dict) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
    return [dict(r) for r in rows]


def fetch_one(sql: str, params: dict) -> Optional[dict]:
    with engine.connect() as conn:
        row = conn.execute(text(sql), params).mappings().first()
    return dict(row) if row else None


class AssistantAskRequest(BaseModel):
    vraag: str
    lijn_code: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    band_code: Optional[str] = None
    scraper_type: Optional[str] = None
    limit: int = 20


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


def extract_scraper_type(vraag: str, explicit_scraper_type: Optional[str] = None) -> Optional[str]:
    if explicit_scraper_type:
        return re.sub(r"\s+", " ", explicit_scraper_type.strip()).upper()

    m = SCRAPER_PATTERN.search(vraag or "")
    if not m:
        return None
    return re.sub(r"\s+", " ", m.group(0).strip()).upper()


def build_date_filters(
    date_from: Optional[str],
    date_to: Optional[str],
    column: str,
) -> tuple[list[str], dict]:
    conditions: list[str] = []
    params: dict[str, Any] = {}

    if date_from:
        conditions.append(f"{column} >= :date_from")
        params["date_from"] = date_from

    if date_to:
        conditions.append(f"{column} <= :date_to")
        params["date_to"] = date_to

    return conditions, params


def detect_intent(
    vraag: str,
    band_code: Optional[str],
    lijn_code: Optional[str],
    scraper_type: Optional[str],
) -> str:
    q = (vraag or "").lower()

    if any(w in q for w in ["onderhoudslijst", "actielijst", "meest dringend", "planning", "prioriteit"]):
        return "maintenance_positions"

    if any(w in q for w in ["forecast", "3 mm", "3mm", "wanneer vervangen", "dagen tot", "levensduur"]):
        return "forecast"

    if any(w in q for w in ["vervanglijst", "overdue", "binnen_2_weken", "binnen 2 weken", "binnen 1 maand"]):
        return "replacement"

    if any(w in q for w in ["laatste meshoogte", "actuele meshoogte", "laatste stand"]):
        return "latest_mes"

    if any(w in q for w in ["lifecycle", "slijtage", "meshoogteverloop", "historie", "tijdlijn"]):
        if band_code:
            return "band_lifecycle"
        if scraper_type:
            return "scraper_lifecycle"
        return "lifecycle"

    if band_code:
        return "band"

    if scraper_type:
        return "scraper"

    if lijn_code:
        return "location"

    if any(w in q for w in ["dataset", "overzicht", "hoeveel", "samenvatting", "summary", "totaal"]):
        return "dataset"

    return "dataset"


def summarize_dataset_question(
    lijn_code: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
) -> dict:
    conditions = ["1=1"]
    params: dict[str, Any] = {}

    if lijn_code:
        conditions.append("lijn_code = :lijn_code")
        params["lijn_code"] = lijn_code

    date_conditions, date_params = build_date_filters(date_from, date_to, "effective_date")
    conditions.extend(date_conditions)
    params.update(date_params)

    where_sql = " AND ".join(conditions)

    sql = f"""
        SELECT
            COUNT(*) AS n_rows,
            COUNT(*) FILTER (WHERE record_type = 'POSITION') AS n_positions,
            COUNT(*) FILTER (WHERE record_type = 'OBSERVATION') AS n_observations,
            COUNT(*) FILTER (WHERE mes_num IS NOT NULL) AS n_mesmetingen,
            COUNT(*) FILTER (WHERE vervangen = TRUE) AS n_vervang_rows,
            COUNT(*) FILTER (WHERE opmerking_raw IS NOT NULL) AS n_opmerkingen,
            COUNT(DISTINCT lijn_code) AS n_lijnen,
            COUNT(DISTINCT band_locatie_norm) FILTER (WHERE band_locatie_norm IS NOT NULL) AS n_bandcodes,
            MIN(effective_date) AS eerste_datum,
            MAX(effective_date) AS laatste_datum
        FROM vw_inspection_full_dataset_v1
        WHERE {where_sql}
    """
    summary = fetch_one(sql, params)

    return {
        "intent": "dataset",
        "entities": {"lijn_code": lijn_code},
        "resultaat": summary,
        "antwoord": (
            f"Dataset bevat {summary['n_rows']} regels van {summary['eerste_datum']} tot {summary['laatste_datum']}."
            if summary else "Ik vind geen dataset-samenvatting."
        ),
    }


def summarize_band_question(
    band_code: str,
    lijn_code: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
) -> dict:
    conditions = ["band_code = :band_code"]
    params: dict[str, Any] = {"band_code": band_code}

    if lijn_code:
        conditions.append("lijn_code = :lijn_code")
        params["lijn_code"] = lijn_code

    date_conditions, date_params = build_date_filters(date_from, date_to, "effective_date")
    conditions.extend(date_conditions)
    params.update(date_params)

    where_sql = " AND ".join(conditions)

    summary_sql = f"""
        SELECT *
        FROM vw_band_performance_v1
        WHERE {where_sql}
    """
    summary = fetch_one(summary_sql, params)

    trend_sql = f"""
        SELECT *
        FROM vw_band_signal_trend_v1
        WHERE {where_sql}
        ORDER BY effective_date DESC
        LIMIT 20
    """
    trend = fetch_all(trend_sql, params)

    recent_sql = """
        SELECT
            inspection_key,
            lijn_code,
            effective_date,
            source_file,
            sheet,
            row_nr,
            scraper_type_effective_norm,
            mes_num,
            vervangen,
            reinigen,
            demontage,
            montage,
            afstellen,
            hosch_flag,
            opmerking_raw
        FROM vw_inspection_full_dataset_v1
        WHERE band_locatie_norm = :band_code
          AND (:lijn_code IS NULL OR lijn_code = :lijn_code)
          AND (:date_from IS NULL OR effective_date >= :date_from)
          AND (:date_to IS NULL OR effective_date <= :date_to)
        ORDER BY effective_date DESC, row_nr
        LIMIT 20
    """
    recent_rows = fetch_all(
        recent_sql,
        {
            "band_code": band_code,
            "lijn_code": lijn_code,
            "date_from": date_from,
            "date_to": date_to,
        },
    )

    answer = f"Ik vind geen performance-data voor band {band_code}."
    if summary:
        parts = [
            f"Band {band_code} heeft {summary['n_rows']} regels tussen {summary['eerste_datum']} en {summary['laatste_datum']}.",
            f"Mesmetingen: {summary['n_mesmetingen']}, gemiddelde {summary['avg_mes_num']}.",
        ]
        signal_parts = []
        if summary.get("n_vervangen"):
            signal_parts.append(f"vervangingen {summary['n_vervangen']}")
        if summary.get("n_vervuiling"):
            signal_parts.append(f"vervuiling {summary['n_vervuiling']}")
        if summary.get("n_mors"):
            signal_parts.append(f"mors {summary['n_mors']}")
        if summary.get("n_scheefloop"):
            signal_parts.append(f"scheefloop {summary['n_scheefloop']}")
        if signal_parts:
            parts.append("Signalen: " + ", ".join(signal_parts) + ".")
        answer = " ".join(parts)

    return {
        "intent": "band",
        "entities": {"band_code": band_code, "lijn_code": lijn_code},
        "antwoord": answer,
        "summary": summary,
        "trend": trend,
        "recent_rows": recent_rows,
    }


def summarize_location_question(
    lijn_code: str,
    date_from: Optional[str],
    date_to: Optional[str],
) -> dict:
    params: dict[str, Any] = {"lijn_code": lijn_code}

    summary = fetch_one(
        """
        SELECT *
        FROM vw_location_performance_v1
        WHERE lijn_code = :lijn_code
        """,
        params,
    )

    bands = fetch_all(
        """
        SELECT *
        FROM vw_band_performance_v1
        WHERE lijn_code = :lijn_code
        ORDER BY n_rows DESC, band_code
        LIMIT 20
        """,
        params,
    )

    answer = f"Ik vind geen locatie-data voor {lijn_code}."
    if summary:
        parts = [
            f"Locatie {lijn_code} heeft {summary['n_rows']} regels tussen {summary['eerste_datum']} en {summary['laatste_datum']}.",
            f"Er zijn {summary['n_banden']} banden en {summary['n_scraper_types']} scrapertypes.",
        ]
        if summary.get("n_mesmetingen"):
            parts.append(f"Mesmetingen: {summary['n_mesmetingen']} met gemiddeld {summary['avg_mes_num']}.")
        signal_parts = []
        if summary.get("n_vervangen"):
            signal_parts.append(f"vervanging {summary['n_vervangen']}")
        if summary.get("n_vervuiling"):
            signal_parts.append(f"vervuiling {summary['n_vervuiling']}")
        if summary.get("n_mors"):
            signal_parts.append(f"mors {summary['n_mors']}")
        if summary.get("n_scheefloop"):
            signal_parts.append(f"scheefloop {summary['n_scheefloop']}")
        if signal_parts:
            parts.append("Signalen: " + ", ".join(signal_parts) + ".")
        answer = " ".join(parts)

    return {
        "intent": "location",
        "entities": {"lijn_code": lijn_code},
        "antwoord": answer,
        "summary": summary,
        "bands": bands,
    }


def summarize_scraper_question(
    scraper_type: str,
    lijn_code: Optional[str],
) -> dict:
    conditions = ["scraper_type = :scraper_type"]
    params: dict[str, Any] = {"scraper_type": scraper_type}

    if lijn_code:
        conditions.append("lijn_code = :lijn_code")
        params["lijn_code"] = lijn_code

    where_sql = " AND ".join(conditions)

    sql = f"""
        SELECT *
        FROM vw_scraper_performance_v1
        WHERE {where_sql}
        ORDER BY lijn_code
        LIMIT 20
    """
    rows = fetch_all(sql, params)

    answer = f"Ik vind geen performance-data voor scrapertype {scraper_type}."
    if rows:
        total_rows = sum(r.get("n_rows", 0) or 0 for r in rows)
        total_bands = sum(r.get("n_banden", 0) or 0 for r in rows)
        answer = (
            f"Scrapertype {scraper_type} komt {total_rows} keer voor "
            f"over {len(rows)} locatie-selecties en {total_bands} bandkoppelingen."
        )

    return {
        "intent": "scraper",
        "entities": {"scraper_type": scraper_type, "lijn_code": lijn_code},
        "antwoord": answer,
        "rows": rows,
    }


def latest_meshoogte(
    lijn_code: Optional[str],
    band_code: Optional[str],
    scraper_type: Optional[str],
    limit: int,
) -> dict:
    conditions = ["1=1"]
    params: dict[str, Any] = {"limit": limit}

    if lijn_code:
        conditions.append("lijn_code = :lijn_code")
        params["lijn_code"] = lijn_code

    if band_code:
        conditions.append("band_norm = :band_code")
        params["band_code"] = band_code

    if scraper_type:
        conditions.append("scraper_type_norm = :scraper_type")
        params["scraper_type"] = scraper_type

    where_sql = " AND ".join(conditions)

    sql = f"""
        SELECT
            laatste_meting_datum,
            lijn_code,
            band_norm,
            scraper_family,
            scraper_type_norm,
            position_hint,
            meshoogte_mm,
            commentaar
        FROM vw_meshoogte_latest_per_scraper_clean
        WHERE {where_sql}
        ORDER BY laatste_meting_datum DESC NULLS LAST, lijn_code, band_norm, position_hint
        LIMIT :limit
    """
    rows = fetch_all(sql, params)

    return {
        "intent": "latest_mes",
        "rows": rows,
        "antwoord": f"{len(rows)} laatste meshoogte-regels gevonden." if rows else "Geen laatste meshoogtes gevonden.",
    }


def lifecycle_analysis(
    lijn_code: Optional[str],
    band_code: Optional[str],
    scraper_type: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
    limit: int,
) -> dict:
    conditions = ["1=1"]
    params: dict[str, Any] = {"limit": limit}

    if lijn_code:
        conditions.append("lijn_code = :lijn_code")
        params["lijn_code"] = lijn_code

    if band_code:
        conditions.append("band_norm = :band_code")
        params["band_code"] = band_code

    if scraper_type:
        conditions.append("scraper_type_norm = :scraper_type")
        params["scraper_type"] = scraper_type

    date_conditions, date_params = build_date_filters(date_from, date_to, "inspected_on")
    conditions.extend(date_conditions)
    params.update(date_params)

    where_sql = " AND ".join(conditions)

    sql = f"""
        SELECT
            inspected_on,
            lijn_code,
            band_norm,
            scraper_type_norm,
            position_hint,
            meshoogte_mm,
            replace_event,
            cycle_id,
            commentaar
        FROM vw_mes_lifecycle_cycles_clean
        WHERE {where_sql}
        ORDER BY inspected_on DESC NULLS LAST, lijn_code, band_norm, position_hint
        LIMIT :limit
    """
    rows = fetch_all(sql, params)

    replace_events = sum(1 for r in rows if r.get("replace_event"))
    mes_values = [r.get("meshoogte_mm") for r in rows if r.get("meshoogte_mm") is not None]

    unusual = False
    unusual_reasons: list[str] = []
    if len(mes_values) >= 3 and min(mes_values) <= 3:
        unusual_reasons.append("lage meshoogte in lifecycle")
    if replace_events >= 2:
        unusual_reasons.append("meerdere vervangevents")
    unusual = len(unusual_reasons) > 0

    return {
        "intent": "lifecycle",
        "antwoord": f"{len(rows)} lifecycle-regels gevonden.",
        "rows": rows,
        "ongewone_slijtage": unusual,
        "waarom": unusual_reasons,
    }


def forecast_3mm(
    lijn_code: Optional[str],
    band_code: Optional[str],
    scraper_type: Optional[str],
    limit: int,
) -> dict:
    conditions = ["meetpunten >= 3"]
    params: dict[str, Any] = {"limit": limit}

    if lijn_code:
        conditions.append("lijn_code = :lijn_code")
        params["lijn_code"] = lijn_code

    if band_code:
        conditions.append("band_norm = :band_code")
        params["band_code"] = band_code

    if scraper_type:
        conditions.append("scraper_type_norm = :scraper_type")
        params["scraper_type"] = scraper_type

    where_sql = " AND ".join(conditions)

    sql = f"""
        SELECT
            lijn_code,
            band_norm,
            scraper_type_norm,
            position_hint,
            cycle_start,
            cycle_end,
            meetpunten,
            start_meshoogte_mm,
            eind_meshoogte_mm,
            slijtage_mm_per_dag,
            geschatte_dagen_tot_3mm,
            geschatte_vervangdatum_bij_3mm,
            status_3mm
        FROM vw_mes_cycle_analysis_clean
        WHERE {where_sql}
        ORDER BY
            CASE status_3mm
                WHEN 'NU VERVANGEN' THEN 1
                WHEN 'BINNEN 30 DAGEN' THEN 2
                WHEN 'BINNEN 60 DAGEN' THEN 3
                ELSE 4
            END,
            geschatte_vervangdatum_bij_3mm ASC NULLS LAST
        LIMIT :limit
    """
    rows = fetch_all(sql, params)

    return {
        "intent": "forecast",
        "antwoord": f"{len(rows)} forecast-regels gevonden.",
        "rows": rows,
    }


def maintenance_positions(
    lijn_code: Optional[str],
    band_code: Optional[str],
    limit: int,
) -> dict:
    conditions = ["cycle_end >= DATE '2024-01-01'"]
    params: dict[str, Any] = {"limit": limit}

    if lijn_code:
        conditions.append("lijn_code = :lijn_code")
        params["lijn_code"] = lijn_code

    if band_code:
        conditions.append("band_norm = :band_code")
        params["band_code"] = band_code

    where_sql = " AND ".join(conditions)

    sql = f"""
        SELECT
            lijn_code,
            band_norm,
            position_hint,
            scraper_types,
            cycle_start,
            cycle_end,
            meetpunten,
            avg_meshoogte_mm,
            start_meshoogte_mm,
            eind_meshoogte_mm,
            slijtage_mm_per_dag,
            geschatte_dagen_tot_3mm,
            geschatte_vervangdatum_bij_3mm,
            status_3mm,
            prioriteit
        FROM vw_mes_maintenance_positions_latest
        WHERE {where_sql}
        ORDER BY prioriteit, geschatte_vervangdatum_bij_3mm NULLS LAST, lijn_code, band_norm
        LIMIT :limit
    """
    rows = fetch_all(sql, params)

    return {
        "intent": "maintenance_positions",
        "antwoord": f"{len(rows)} onderhoudsposities gevonden.",
        "rows": rows,
    }


def maintenance_planning(limit: int) -> dict:
    sql = """
        SELECT
            lijn_code,
            COUNT(*) AS n_posities,
            COUNT(*) FILTER (WHERE prioriteit = 1) AS nu_vervangen,
            COUNT(*) FILTER (WHERE prioriteit = 2) AS binnen_30_dagen,
            COUNT(*) FILTER (WHERE prioriteit = 3) AS binnen_60_dagen,
            COUNT(*) FILTER (WHERE prioriteit = 4) AS ok
        FROM vw_mes_maintenance_positions_latest
        WHERE cycle_end >= DATE '2024-01-01'
        GROUP BY lijn_code
        ORDER BY nu_vervangen DESC, binnen_30_dagen DESC, binnen_60_dagen DESC, lijn_code
        LIMIT :limit
    """
    rows = fetch_all(sql, {"limit": limit})

    return {
        "intent": "maintenance_planning",
        "antwoord": f"{len(rows)} lijnen in onderhoudsplanning.",
        "rows": rows,
    }


def replacement_advice(
    lijn_code: Optional[str],
    limit: int,
) -> dict:
    conditions = ["status IN ('OVERDUE','BINNEN_2_WEKEN','BINNEN_1_MAAND')"]
    params: dict[str, Any] = {"limit": limit}

    if lijn_code:
        conditions.append("lijn_code = :lijn_code")
        params["lijn_code"] = lijn_code

    where_sql = " AND ".join(conditions)

    sql = f"""
        SELECT
            lijn_code,
            band_norm,
            scraper_family,
            scraper_type_norm,
            next_due_date,
            days_to_due,
            typical_mes_qty,
            status
        FROM vw_all_replacement_advice
        WHERE {where_sql}
        ORDER BY
            CASE status
                WHEN 'OVERDUE' THEN 1
                WHEN 'BINNEN_2_WEKEN' THEN 2
                WHEN 'BINNEN_1_MAAND' THEN 3
                ELSE 4
            END,
            next_due_date ASC NULLS LAST
        LIMIT :limit
    """
    rows = fetch_all(sql, params)

    return {
        "intent": "replacement",
        "antwoord": f"{len(rows)} vervangadviezen gevonden.",
        "rows": rows,
    }


def band_deep_analysis(
    band_code: str,
    lijn_code: Optional[str],
    limit: int,
) -> dict:
    lifecycle = lifecycle_analysis(
        lijn_code=lijn_code,
        band_code=band_code,
        scraper_type=None,
        date_from=None,
        date_to=None,
        limit=limit,
    )
    forecast = forecast_3mm(
        lijn_code=lijn_code,
        band_code=band_code,
        scraper_type=None,
        limit=limit,
    )
    latest = latest_meshoogte(
        lijn_code=lijn_code,
        band_code=band_code,
        scraper_type=None,
        limit=limit,
    )

    note_terms = []
    for term in SIGNAL_TERMS:
        note_terms.append(f"LOWER(COALESCE(commentaar, '')) LIKE '%{term}%'")

    notes_sql = f"""
        SELECT
            inspected_on,
            lijn_code,
            band_norm,
            scraper_type_norm,
            position_hint,
            meshoogte_mm,
            replace_event,
            cycle_id,
            commentaar
        FROM vw_mes_lifecycle_cycles_clean
        WHERE band_norm = :band_code
          AND (:lijn_code IS NULL OR lijn_code = :lijn_code)
          AND ({' OR '.join(note_terms)})
        ORDER BY inspected_on DESC NULLS LAST
        LIMIT :limit
    """
    note_rows = fetch_all(notes_sql, {"band_code": band_code, "lijn_code": lijn_code, "limit": limit})

    abnormal = lifecycle.get("ongewone_slijtage", False)
    hypotheses: list[str] = []
    if abnormal:
        hypotheses.append("mogelijk afstellingsprobleem of snelle slijtage")
    if any("scheef" in (r.get("commentaar") or "").lower() for r in note_rows):
        hypotheses.append("mogelijk bandloop of scheefloop")
    if any("vervuil" in (r.get("commentaar") or "").lower() for r in note_rows):
        hypotheses.append("mogelijk vervuiling of carryback")
    if any("trommel" in (r.get("commentaar") or "").lower() for r in note_rows):
        hypotheses.append("mogelijk trommel- of bandconditie")

    answer_parts = [
        f"Analyse voor band {band_code}.",
        f"Laatste meshoogtes: {len(latest['rows'])}, lifecycle-regels: {len(lifecycle['rows'])}, forecast-regels: {len(forecast['rows'])}.",
    ]
    if abnormal:
        answer_parts.append("Ongewone slijtage: ja.")
    else:
        answer_parts.append("Ongewone slijtage: niet duidelijk zichtbaar.")
    if hypotheses:
        answer_parts.append("Mogelijke oorzaak: " + ", ".join(dict.fromkeys(hypotheses)) + ".")

    return {
        "intent": "band_deep_analysis",
        "antwoord": " ".join(answer_parts),
        "latest_meshoogte": latest["rows"],
        "lifecycle": lifecycle["rows"],
        "forecast_3mm": forecast["rows"],
        "relevante_opmerkingen": note_rows,
        "ongewone_slijtage": abnormal,
        "mogelijke_oorzaken": list(dict.fromkeys(hypotheses)),
    }


@router.get("/health")
def analysis_health() -> dict:
    try:
        row = fetch_one("SELECT 1 AS ok", {})
        return {"status": "ok", "db": row}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/dataset/summary")
def get_dataset_summary(
    lijn_code: Optional[str] = Query(default=None),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
):
    return summarize_dataset_question(
        lijn_code=normalize_code(lijn_code),
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/dataset/full")
def get_full_dataset(
    lijn_code: Optional[str] = Query(default=None),
    band_code: Optional[str] = Query(default=None),
    scraper_type: Optional[str] = Query(default=None),
    record_type: Optional[Literal["POSITION", "OBSERVATION"]] = Query(default=None),
    data_quality_flag: Optional[str] = Query(default=None),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    limit: int = Query(default=500, ge=1, le=10000),
):
    conditions = ["1=1"]
    params: dict = {"limit": limit}

    if lijn_code:
        conditions.append("lijn_code = :lijn_code")
        params["lijn_code"] = normalize_code(lijn_code)

    if band_code:
        conditions.append("band_locatie_norm = :band_code")
        params["band_code"] = normalize_code(band_code)

    if scraper_type:
        conditions.append("scraper_type_effective_norm = :scraper_type")
        params["scraper_type"] = re.sub(r"\s+", " ", scraper_type.strip()).upper()

    if record_type:
        conditions.append("record_type = :record_type")
        params["record_type"] = record_type

    if data_quality_flag:
        conditions.append("data_quality_flag = :data_quality_flag")
        params["data_quality_flag"] = data_quality_flag

    if date_from:
        conditions.append("effective_date >= :date_from")
        params["date_from"] = date_from

    if date_to:
        conditions.append("effective_date <= :date_to")
        params["date_to"] = date_to

    where_sql = " AND ".join(conditions)

    sql = f"""
        SELECT
            inspection_key,
            lijn_code,
            effective_date,
            source_file,
            sheet,
            row_nr,
            record_type,
            data_quality_flag,
            band_locatie_norm,
            locatie_effective,
            scraper_type_effective_norm,
            scraper_family,
            scraper_material,
            mes_num,
            mes_code,
            mes_interpretatie,
            demontage,
            reinigen,
            vervangen,
            montage,
            afstellen,
            hosch_flag,
            opmerking_raw,
            record_role,
            parse_confidence
        FROM vw_inspection_full_dataset_v1
        WHERE {where_sql}
        ORDER BY effective_date DESC, lijn_code, inspection_key, row_nr
        LIMIT :limit
    """
    return fetch_all(sql, params)


@router.get("/band/{band_code}/performance-v1")
def get_band_performance_v1(
    band_code: str,
    lijn_code: Optional[str] = Query(default=None),
):
    return summarize_band_question(
        band_code=normalize_code(band_code),
        lijn_code=normalize_code(lijn_code),
        date_from=None,
        date_to=None,
    )


@router.get("/band/{band_code}/analysis-v10")
def get_band_analysis_v10(
    band_code: str,
    lijn_code: Optional[str] = Query(default=None),
):
    return summarize_band_question(
        band_code=normalize_code(band_code),
        lijn_code=normalize_code(lijn_code),
        date_from=None,
        date_to=None,
    )


@router.get("/band/{band_code}/analysis-v7")
def get_band_analysis_v7(
    band_code: str,
    lijn_code: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
):
    return band_deep_analysis(
        band_code=normalize_code(band_code),
        lijn_code=normalize_code(lijn_code),
        limit=limit,
    )


@router.get("/band/{band_code}/timeline-v10")
def get_band_timeline_v10(
    band_code: str,
    lijn_code: Optional[str] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=5000),
):
    conditions = ["band_code = :band_code"]
    params: dict = {"band_code": normalize_code(band_code), "limit": limit}

    if lijn_code:
        conditions.append("lijn_code = :lijn_code")
        params["lijn_code"] = normalize_code(lijn_code)

    where_sql = " AND ".join(conditions)

    sql = f"""
        SELECT *
        FROM vw_band_signal_trend_v1
        WHERE {where_sql}
        ORDER BY effective_date DESC
        LIMIT :limit
    """
    return fetch_all(sql, params)


@router.get("/location/{locatie_code}/performance-v1")
def get_location_performance_v1(
    locatie_code: str,
):
    return summarize_location_question(
        lijn_code=normalize_code(locatie_code),
        date_from=None,
        date_to=None,
    )


@router.get("/location/{locatie_code}/analysis-v10")
def get_location_analysis_v10(
    locatie_code: str,
):
    return summarize_location_question(
        lijn_code=normalize_code(locatie_code),
        date_from=None,
        date_to=None,
    )


@router.get("/scraper/{scraper_type}/performance-v1")
def get_scraper_performance_v1(
    scraper_type: str,
    lijn_code: Optional[str] = Query(default=None),
):
    return summarize_scraper_question(
        scraper_type=re.sub(r"\s+", " ", scraper_type.strip()).upper(),
        lijn_code=normalize_code(lijn_code),
    )


@router.get("/scraper/{scraper_type}/analysis-v10")
def get_scraper_analysis_v10(
    scraper_type: str,
    lijn_code: Optional[str] = Query(default=None),
):
    return summarize_scraper_question(
        scraper_type=re.sub(r"\s+", " ", scraper_type.strip()).upper(),
        lijn_code=normalize_code(lijn_code),
    )


@router.get("/mes/latest")
def get_meshoogte_latest(
    lijn_code: Optional[str] = Query(default=None),
    band_code: Optional[str] = Query(default=None),
    scraper_type: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
):
    return latest_meshoogte(
        lijn_code=normalize_code(lijn_code),
        band_code=normalize_code(band_code),
        scraper_type=extract_scraper_type("", scraper_type),
        limit=limit,
    )


@router.get("/mes/lifecycle")
def get_mes_lifecycle(
    lijn_code: Optional[str] = Query(default=None),
    band_code: Optional[str] = Query(default=None),
    scraper_type: Optional[str] = Query(default=None),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=500),
):
    return lifecycle_analysis(
        lijn_code=normalize_code(lijn_code),
        band_code=normalize_code(band_code),
        scraper_type=extract_scraper_type("", scraper_type),
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )


@router.get("/mes/forecast-3mm")
def get_mes_forecast_3mm(
    lijn_code: Optional[str] = Query(default=None),
    band_code: Optional[str] = Query(default=None),
    scraper_type: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
):
    return forecast_3mm(
        lijn_code=normalize_code(lijn_code),
        band_code=normalize_code(band_code),
        scraper_type=extract_scraper_type("", scraper_type),
        limit=limit,
    )


@router.get("/replacement/advice")
def get_replacement_advice(
    lijn_code: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
):
    return replacement_advice(
        lijn_code=normalize_code(lijn_code),
        limit=limit,
    )


@router.get("/maintenance/positions")
def get_maintenance_positions(
    lijn_code: Optional[str] = Query(default=None),
    band_code: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
):
    return maintenance_positions(
        lijn_code=normalize_code(lijn_code),
        band_code=normalize_code(band_code),
        limit=limit,
    )


@router.get("/maintenance/planning")
def get_maintenance_planning(
    limit: int = Query(default=20, ge=1, le=200),
):
    return maintenance_planning(limit=limit)


@router.post("/assistant/ask")
def analysis_assistant_ask(payload: AssistantAskRequest):
    vraag = (payload.vraag or "").strip()
    if not vraag:
        raise HTTPException(status_code=400, detail="vraag is verplicht")

    lijn_code = extract_lijn_code(vraag, payload.lijn_code)
    band_code = normalize_code(payload.band_code) if payload.band_code else extract_band_code(vraag)
    scraper_type = extract_scraper_type(vraag, payload.scraper_type)
    intent = detect_intent(vraag, band_code, lijn_code, scraper_type)
    limit = max(1, min(payload.limit, 50))

    if intent == "maintenance_positions":
        return maintenance_positions(lijn_code=lijn_code, band_code=band_code, limit=limit)

    if intent == "forecast":
        return forecast_3mm(lijn_code=lijn_code, band_code=band_code, scraper_type=scraper_type, limit=limit)

    if intent == "replacement":
        return replacement_advice(lijn_code=lijn_code, limit=limit)

    if intent == "latest_mes":
        return latest_meshoogte(lijn_code=lijn_code, band_code=band_code, scraper_type=scraper_type, limit=limit)

    if intent in {"lifecycle", "band_lifecycle", "scraper_lifecycle"}:
        return lifecycle_analysis(
            lijn_code=lijn_code,
            band_code=band_code,
            scraper_type=scraper_type,
            date_from=payload.date_from,
            date_to=payload.date_to,
            limit=limit,
        )

    if intent == "band" and band_code:
        return band_deep_analysis(
            band_code=band_code,
            lijn_code=lijn_code,
            limit=limit,
        )

    if intent == "scraper" and scraper_type:
        return summarize_scraper_question(
            scraper_type=scraper_type,
            lijn_code=lijn_code,
        )

    if intent == "location" and lijn_code:
        return summarize_location_question(
            lijn_code=lijn_code,
            date_from=payload.date_from,
            date_to=payload.date_to,
        )

    return summarize_dataset_question(
        lijn_code=lijn_code,
        date_from=payload.date_from,
        date_to=payload.date_to,
    )