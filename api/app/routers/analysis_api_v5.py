from __future__ import annotations

import os
from typing import Optional, Literal

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

VALID_ORDER_COLUMNS = {
    "impact_score",
    "n_cases",
    "n_banden",
    "avg_delta_vervuiling",
    "avg_delta_schade",
    "avg_delta_scheefloop",
}

VALID_ORDER_DIR = {"asc", "desc"}


def safe_order_by(order_by: str, order_dir: str) -> str:
    order_by = order_by if order_by in VALID_ORDER_COLUMNS else "impact_score"
    order_dir = order_dir.lower() if order_dir.lower() in VALID_ORDER_DIR else "desc"
    return f"{order_by} {order_dir}"


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


@router.get("/health")
def analysis_health() -> dict:
    try:
        row = fetch_one("SELECT 1 AS ok", {})
        return {"status": "ok", "db": row}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/config/v7/advice")
def get_config_v7_advice(
    configuratie_type_v7: Optional[str] = Query(default=None),
    scraper_channel: Optional[str] = Query(default=None),
    advies_status: Optional[Literal["VERMIJDEN", "OPLETTEN", "ACCEPTABEL"]] = Query(default=None),
    data_quality: Optional[Literal["OK", "TE_WEINIG_DATA"]] = Query(default=None),
    confidence_level: Optional[Literal["HOOG", "MIDDEL", "LAAG"]] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
):
    conditions = ["1=1"]
    params: dict = {"limit": limit}

    if configuratie_type_v7:
        conditions.append("configuratie_type_v7 = :configuratie_type_v7")
        params["configuratie_type_v7"] = configuratie_type_v7

    if scraper_channel:
        conditions.append("scraper_channel = :scraper_channel")
        params["scraper_channel"] = scraper_channel

    if advies_status:
        conditions.append("advies_status = :advies_status")
        params["advies_status"] = advies_status

    if data_quality:
        conditions.append("data_quality = :data_quality")
        params["data_quality"] = data_quality

    if confidence_level:
        conditions.append("confidence_level = :confidence_level")
        params["confidence_level"] = confidence_level

    where_sql = " AND ".join(conditions)

    sql = f"""
        SELECT
            configuratie_type_v7,
            scraper_channel,
            scraper_type_norm,
            n_banden,
            avg_vervuiling,
            avg_schade,
            avg_scheefloop,
            avg_slijtage,
            advies_status,
            confidence_level,
            data_quality
        FROM vw_analysis_config_advice_v7_final
        WHERE {where_sql}
        ORDER BY
            CASE advies_status
                WHEN 'VERMIJDEN' THEN 1
                WHEN 'OPLETTEN' THEN 2
                ELSE 3
            END,
            CASE confidence_level
                WHEN 'HOOG' THEN 1
                WHEN 'MIDDEL' THEN 2
                ELSE 3
            END,
            avg_vervuiling DESC,
            avg_schade DESC
        LIMIT :limit
    """
    return fetch_all(sql, params)


@router.get("/config/v7/best")
def get_config_v7_best(
    data_quality: Optional[Literal["OK", "TE_WEINIG_DATA"]] = Query(default="OK"),
    limit: int = Query(default=25, ge=1, le=200),
):
    conditions = ["advies_status = 'ACCEPTABEL'"]
    params: dict = {"limit": limit}

    if data_quality:
        conditions.append("data_quality = :data_quality")
        params["data_quality"] = data_quality

    where_sql = " AND ".join(conditions)

    sql = f"""
        SELECT
            configuratie_type_v7,
            scraper_channel,
            scraper_type_norm,
            n_banden,
            avg_vervuiling,
            avg_schade,
            avg_scheefloop,
            avg_slijtage,
            advies_status,
            confidence_level,
            data_quality
        FROM vw_analysis_config_advice_v7_final
        WHERE {where_sql}
        ORDER BY
            CASE confidence_level
                WHEN 'HOOG' THEN 1
                WHEN 'MIDDEL' THEN 2
                ELSE 3
            END,
            avg_vervuiling ASC,
            avg_schade ASC,
            avg_scheefloop ASC
        LIMIT :limit
    """
    return fetch_all(sql, params)


@router.get("/config/v7/worst")
def get_config_v7_worst(
    data_quality: Optional[Literal["OK", "TE_WEINIG_DATA"]] = Query(default="OK"),
    limit: int = Query(default=25, ge=1, le=200),
):
    conditions = ["advies_status IN ('VERMIJDEN', 'OPLETTEN')"]
    params: dict = {"limit": limit}

    if data_quality:
        conditions.append("data_quality = :data_quality")
        params["data_quality"] = data_quality

    where_sql = " AND ".join(conditions)

    sql = f"""
        SELECT
            configuratie_type_v7,
            scraper_channel,
            scraper_type_norm,
            n_banden,
            avg_vervuiling,
            avg_schade,
            avg_scheefloop,
            avg_slijtage,
            advies_status,
            confidence_level,
            data_quality
        FROM vw_analysis_config_advice_v7_final
        WHERE {where_sql}
        ORDER BY
            CASE advies_status
                WHEN 'VERMIJDEN' THEN 1
                WHEN 'OPLETTEN' THEN 2
                ELSE 3
            END,
            CASE confidence_level
                WHEN 'HOOG' THEN 1
                WHEN 'MIDDEL' THEN 2
                ELSE 3
            END,
            avg_vervuiling DESC,
            avg_schade DESC,
            avg_scheefloop DESC
        LIMIT :limit
    """
    return fetch_all(sql, params)


@router.get("/config/v7/report/{configuratie_type_v7}")
def get_config_v7_report(
    configuratie_type_v7: str,
    top_n: int = Query(default=10, ge=1, le=50),
):
    advice_sql = """
        SELECT
            configuratie_type_v7,
            scraper_channel,
            scraper_type_norm,
            n_banden,
            avg_vervuiling,
            avg_schade,
            avg_scheefloop,
            avg_slijtage,
            advies_status,
            confidence_level,
            data_quality
        FROM vw_analysis_config_advice_v7_final
        WHERE configuratie_type_v7 = :configuratie_type_v7
        ORDER BY
            CASE advies_status
                WHEN 'VERMIJDEN' THEN 1
                WHEN 'OPLETTEN' THEN 2
                ELSE 3
            END,
            CASE confidence_level
                WHEN 'HOOG' THEN 1
                WHEN 'MIDDEL' THEN 2
                ELSE 3
            END,
            avg_vervuiling DESC,
            avg_schade DESC
        LIMIT :top_n
    """

    advice_rows = fetch_all(advice_sql, {"configuratie_type_v7": configuratie_type_v7, "top_n": top_n})

    summary_lines: list[str] = []

    avoid_rows = [r for r in advice_rows if r.get("advies_status") == "VERMIJDEN"]
    alert_rows = [r for r in advice_rows if r.get("advies_status") == "OPLETTEN"]
    best_rows = [r for r in advice_rows if r.get("advies_status") == "ACCEPTABEL"]

    if avoid_rows:
        top = avoid_rows[0]
        summary_lines.append(
            f"Te vermijden binnen {configuratie_type_v7}: "
            f"{top['scraper_type_norm']} op {top['scraper_channel']} "
            f"(vervuiling {top['avg_vervuiling']}, schade {top['avg_schade']}, confidence {top['confidence_level']})."
        )

    if alert_rows:
        top = alert_rows[0]
        summary_lines.append(
            f"Extra aandacht binnen {configuratie_type_v7}: "
            f"{top['scraper_type_norm']} op {top['scraper_channel']} "
            f"(vervuiling {top['avg_vervuiling']}, schade {top['avg_schade']}, confidence {top['confidence_level']})."
        )

    if best_rows:
        top = sorted(
            best_rows,
            key=lambda r: (
                0 if r.get("confidence_level") == "HOOG" else 1 if r.get("confidence_level") == "MIDDEL" else 2,
                r.get("avg_vervuiling", 999),
                r.get("avg_schade", 999),
                r.get("avg_scheefloop", 999),
            ),
        )[0]
        summary_lines.append(
            f"Beste kandidaat binnen {configuratie_type_v7}: "
            f"{top['scraper_type_norm']} op {top['scraper_channel']} "
            f"(vervuiling {top['avg_vervuiling']}, schade {top['avg_schade']}, confidence {top['confidence_level']})."
        )

    if not summary_lines:
        summary_lines.append(
            f"Voor configuratie {configuratie_type_v7} is nog geen duidelijke v7-samenvatting beschikbaar."
        )

    return {
        "configuratie_type_v7": configuratie_type_v7,
        "summary": " ".join(summary_lines),
        "advice": advice_rows,
        "note": (
            "Gebruik v7-configuratierapporten als beslissingsondersteuning. "
            "Combineer advies_status altijd met confidence_level en data_quality."
        ),
    }


@router.get("/config/v8/advice")
def get_config_v8_advice(
    configuratie_type_v8: Optional[str] = Query(default=None),
    scraper_position: Optional[Literal["PRIMARY", "SECONDARY", "TERTIARY"]] = Query(default=None),
    advies_status: Optional[Literal["VERMIJDEN", "OPLETTEN", "ACCEPTABEL"]] = Query(default=None),
    data_quality: Optional[Literal["OK", "TE_WEINIG_DATA"]] = Query(default=None),
    confidence_level: Optional[Literal["HOOG", "MIDDEL", "LAAG"]] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
):
    conditions = ["1=1"]
    params: dict = {"limit": limit}

    if configuratie_type_v8:
        conditions.append("configuratie_type_v8 = :configuratie_type_v8")
        params["configuratie_type_v8"] = configuratie_type_v8

    if scraper_position:
        conditions.append("scraper_position = :scraper_position")
        params["scraper_position"] = scraper_position

    if advies_status:
        conditions.append("advies_status = :advies_status")
        params["advies_status"] = advies_status

    if data_quality:
        conditions.append("data_quality = :data_quality")
        params["data_quality"] = data_quality

    if confidence_level:
        conditions.append("confidence_level = :confidence_level")
        params["confidence_level"] = confidence_level

    where_sql = " AND ".join(conditions)

    sql = f"""
        SELECT
            configuratie_type_v8,
            scraper_position,
            scraper_type_norm,
            n_banden,
            avg_vervuiling,
            avg_schade,
            avg_scheefloop,
            avg_slijtage,
            advies_status,
            confidence_level,
            data_quality
        FROM vw_analysis_config_advice_v8_final
        WHERE {where_sql}
        ORDER BY
            CASE advies_status
                WHEN 'VERMIJDEN' THEN 1
                WHEN 'OPLETTEN' THEN 2
                ELSE 3
            END,
            CASE confidence_level
                WHEN 'HOOG' THEN 1
                WHEN 'MIDDEL' THEN 2
                ELSE 3
            END,
            avg_vervuiling DESC,
            avg_schade DESC
        LIMIT :limit
    """
    return fetch_all(sql, params)


@router.get("/band/current/{band_code}")
def get_band_current(
    band_code: str,
    lijn_code: Optional[str] = Query(default=None),
):
    conditions = ["band_code = :band_code"]
    params: dict = {"band_code": band_code}

    if lijn_code:
        conditions.append("lijn_code = :lijn_code")
        params["lijn_code"] = lijn_code

    where_sql = " AND ".join(conditions)

    sql = f"""
        SELECT
            lijn_code,
            band_code,
            effective_date,
            scraper_position,
            scraper_type_norm,
            mes_num,
            opmerking_raw,
            activity_score
        FROM vw_scraper_position_rank_v7
        WHERE {where_sql}
        ORDER BY
            CASE scraper_position
                WHEN 'PRIMARY' THEN 1
                WHEN 'SECONDARY' THEN 2
                WHEN 'TERTIARY' THEN 3
                ELSE 9
            END
    """
    rows = fetch_all(sql, params)

    config_sql = f"""
        SELECT
            lijn_code,
            band_code,
            effective_date,
            configuratie_type_v8,
            n_total_scrapers,
            n_primary,
            n_secondary,
            n_tertiary
        FROM vw_scraper_configuration_v8
        WHERE {where_sql}
    """
    config = fetch_one(config_sql, params)

    return {
        "band_code": band_code,
        "config": config,
        "current_state": rows,
    }


@router.get("/band/history/{band_code}")
def get_band_history(
    band_code: str,
    lijn_code: Optional[str] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
):
    conditions = ["band_code = :band_code"]
    params: dict = {"band_code": band_code, "limit": limit}

    if lijn_code:
        conditions.append("lijn_code = :lijn_code")
        params["lijn_code"] = lijn_code

    where_sql = " AND ".join(conditions)

    sql = f"""
        SELECT
            lijn_code,
            band_code,
            effective_date,
            band_locatie,
            any_scraper_type,
            scraper_types_on_date,
            max_mes_num,
            min_mes_num,
            n_mesmetingen,
            vervuiling_text_hits,
            scheefloop_text_hits,
            schade_text_hits,
            opmerkingen,
            max_activity_score,
            n_actieve_regels
        FROM vw_band_history_compact_v1
        WHERE {where_sql}
        ORDER BY effective_date DESC
        LIMIT :limit
    """
    return fetch_all(sql, params)


@router.get("/band/trend/{band_code}")
def get_band_trend(
    band_code: str,
    lijn_code: Optional[str] = Query(default=None),
):
    conditions = ["band_code = :band_code"]
    params: dict = {"band_code": band_code}

    if lijn_code:
        conditions.append("lijn_code = :lijn_code")
        params["lijn_code"] = lijn_code

    where_sql = " AND ".join(conditions)

    trend_sql = f"""
        SELECT
            lijn_code,
            band_code,
            start_date,
            end_date,
            n_meetmomenten,
            start_vervuiling_text,
            end_vervuiling_text,
            start_meshoogte,
            end_meshoogte
        FROM vw_band_trend_v1
        WHERE {where_sql}
    """
    trend = fetch_one(trend_sql, params)

    history_sql = f"""
        SELECT
            lijn_code,
            band_code,
            effective_date,
            scraper_types_on_date,
            max_mes_num,
            min_mes_num,
            vervuiling_text_hits,
            scheefloop_text_hits,
            schade_text_hits,
            opmerkingen
        FROM vw_band_history_compact_v1
        WHERE {where_sql}
        ORDER BY effective_date DESC
        LIMIT 50
    """
    rows = fetch_all(history_sql, params)

    summary = "Onvoldoende trenddata beschikbaar."
    if trend:
        n_meetmomenten = trend.get("n_meetmomenten")
        s_v = trend.get("start_vervuiling_text")
        e_v = trend.get("end_vervuiling_text")
        s_m = trend.get("start_meshoogte")
        e_m = trend.get("end_meshoogte")

        parts = [f"{band_code} heeft {n_meetmomenten} meetmomenten."]
        if s_v is not None and e_v is not None:
            if e_v > s_v:
                parts.append("Vervuilingssignalen nemen toe.")
            elif e_v < s_v:
                parts.append("Vervuilingssignalen nemen af.")
            else:
                parts.append("Vervuilingssignalen zijn stabiel.")
        if s_m is not None and e_m is not None:
            if e_m < s_m:
                parts.append("Meshoogte lijkt af te nemen.")
            elif e_m > s_m:
                parts.append("Meshoogte lijkt toe te nemen.")
            else:
                parts.append("Meshoogte lijkt stabiel.")
        summary = " ".join(parts)

    return {
        "band_code": band_code,
        "trend": trend,
        "summary": summary,
        "recent_history": rows,
    }


@router.get("/band/resets/{band_code}")
def get_band_resets(
    band_code: str,
    lijn_code: Optional[str] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
):
    conditions = ["band_code = :band_code"]
    params: dict = {"band_code": band_code, "limit": limit}

    if lijn_code:
        conditions.append("lijn_code = :lijn_code")
        params["lijn_code"] = lijn_code

    where_sql = " AND ".join(conditions)

    sql = f"""
        SELECT
            lijn_code,
            band_code,
            effective_date,
            inspection_key,
            row_nr,
            scraper_type_norm,
            mes_num,
            prev_mes_num,
            opmerking_raw,
            activity_score,
            has_activity,
            flag_new_band_text,
            flag_replacement_text,
            flag_mes_jump_up,
            reset_event_type
        FROM vw_band_reset_events_v1
        WHERE {where_sql}
        ORDER BY effective_date DESC, row_nr
        LIMIT :limit
    """

    summary_sql = f"""
        SELECT
            lijn_code,
            band_code,
            COUNT(*) AS n_reset_events,
            COUNT(*) FILTER (WHERE reset_event_type = 'BAND_RESET') AS n_band_resets,
            COUNT(*) FILTER (WHERE reset_event_type = 'MES_RESET') AS n_mes_resets,
            COUNT(*) FILTER (WHERE reset_event_type = 'VERVANG_EVENT') AS n_vervang_events,
            MAX(effective_date) AS laatste_event_datum,
            MAX(effective_date) FILTER (WHERE reset_event_type = 'BAND_RESET') AS laatste_band_reset_datum
        FROM vw_band_reset_events_v1
        WHERE {where_sql}
        GROUP BY lijn_code, band_code
    """
    summary = fetch_one(summary_sql, params)

    return {
        "band_code": band_code,
        "summary": summary,
        "reset_events": fetch_all(sql, params),
    }


@router.get("/band/history-v2/{band_code}")
def get_band_history_v2(
    band_code: str,
    lijn_code: Optional[str] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
):
    conditions = ["h.band_code = :band_code"]
    params: dict = {"band_code": band_code, "limit": limit}

    if lijn_code:
        conditions.append("h.lijn_code = :lijn_code")
        params["lijn_code"] = lijn_code

    where_sql = " AND ".join(conditions)

    sql = f"""
        SELECT
            h.lijn_code,
            h.band_code,
            h.effective_date,
            h.band_locatie,
            h.scraper_types_on_date AS observed_scraper_types_on_date,
            a.active_scraper_types_on_date,
            h.max_mes_num,
            h.min_mes_num,
            h.n_mesmetingen,
            a.active_max_mes_num,
            a.active_min_mes_num,
            a.active_n_mesmetingen,
            h.opmerkingen,
            a.active_opmerkingen,
            h.max_activity_score,
            a.active_max_activity_score
        FROM vw_band_history_compact_v1 h
        LEFT JOIN vw_band_history_active_compact_v1 a
          ON a.lijn_code = h.lijn_code
         AND a.band_code = h.band_code
         AND a.effective_date = h.effective_date
        WHERE {where_sql}
        ORDER BY h.effective_date DESC
        LIMIT :limit
    """
    return fetch_all(sql, params)


@router.get("/band/trend-v3/{band_code}")
def get_band_trend_v3(
    band_code: str,
    lijn_code: Optional[str] = Query(default=None),
):
    conditions = ["band_code = :band_code"]
    params: dict = {"band_code": band_code}

    if lijn_code:
        conditions.append("lijn_code = :lijn_code")
        params["lijn_code"] = lijn_code

    where_sql = " AND ".join(conditions)

    trend_sql = f"""
        SELECT
            lijn_code,
            band_code,
            segment_id,
            start_date,
            end_date,
            n_meetmomenten_segment,
            start_meshoogte,
            end_meshoogte,
            latest_active_scraper_types,
            latest_active_opmerkingen
        FROM vw_band_trend_v3
        WHERE {where_sql}
    """
    trend = fetch_one(trend_sql, params)

    history_sql = f"""
        SELECT
            lijn_code,
            band_code,
            effective_date,
            active_scraper_types_on_date,
            active_max_mes_num,
            active_min_mes_num,
            active_n_mesmetingen,
            active_opmerkingen
        FROM vw_band_history_active_compact_v1
        WHERE {where_sql}
        ORDER BY effective_date DESC
        LIMIT 50
    """
    rows = fetch_all(history_sql, params)

    reset_sql = f"""
        SELECT
            COUNT(*) AS n_reset_events,
            COUNT(*) FILTER (WHERE reset_event_type = 'BAND_RESET') AS n_band_resets,
            MAX(effective_date) AS laatste_event_datum,
            MAX(effective_date) FILTER (WHERE reset_event_type = 'BAND_RESET') AS laatste_band_reset_datum
        FROM vw_band_reset_events_v1
        WHERE {where_sql}
    """
    reset_summary = fetch_one(reset_sql, params)

    summary = "Onvoldoende trenddata beschikbaar."
    if trend:
        s_m = trend.get("start_meshoogte")
        e_m = trend.get("end_meshoogte")
        n_seg = trend.get("n_meetmomenten_segment")
        parts = [f"{band_code} heeft {n_seg} meetmomenten in het actuele lifecycle-segment."]

        if s_m is not None and e_m is not None:
            if e_m < s_m:
                parts.append("De actieve meshoogte lijkt af te nemen binnen dit segment.")
            elif e_m > s_m:
                parts.append("De actieve meshoogte stijgt of is recent gereset binnen dit segment.")
            else:
                parts.append("De actieve meshoogte is stabiel binnen dit segment.")

        latest_types = trend.get("latest_active_scraper_types")
        if latest_types:
            parts.append(f"Laatste actieve configuratie: {latest_types}.")

        if reset_summary:
            n_band_resets = reset_summary.get("n_band_resets")
            if n_band_resets:
                parts.append(f"Aantal echte band-resets: {n_band_resets}.")

        summary = " ".join(parts)

    return {
        "band_code": band_code,
        "trend": trend,
        "reset_summary": reset_summary,
        "summary": summary,
        "recent_active_history": rows,
    }


@router.get("/band/report-v3/{band_code}")
def get_band_report_v3(
    band_code: str,
    lijn_code: Optional[str] = Query(default=None),
):
    conditions = ["band_code = :band_code"]
    params: dict = {"band_code": band_code}

    if lijn_code:
        conditions.append("lijn_code = :lijn_code")
        params["lijn_code"] = lijn_code

    where_sql = " AND ".join(conditions)

    report_sql = f"""
        SELECT
            lijn_code,
            band_code,
            segment_id,
            start_date,
            end_date,
            n_meetmomenten_segment,
            start_meshoogte,
            end_meshoogte,
            latest_active_scraper_types,
            latest_active_opmerkingen,
            n_reset_events,
            n_band_resets,
            laatste_event_datum,
            laatste_band_reset_datum,
            mes_trend_label
        FROM vw_band_history_report_v3
        WHERE {where_sql}
    """
    report = fetch_one(report_sql, params)

    current_sql = f"""
        SELECT
            lijn_code,
            band_code,
            effective_date,
            scraper_position,
            scraper_type_norm,
            mes_num,
            opmerking_raw,
            activity_score
        FROM vw_scraper_position_rank_v7
        WHERE {where_sql}
        ORDER BY
            CASE scraper_position
                WHEN 'PRIMARY' THEN 1
                WHEN 'SECONDARY' THEN 2
                WHEN 'TERTIARY' THEN 3
                ELSE 9
            END
    """
    current_state = fetch_all(current_sql, params)

    resets_sql = f"""
        SELECT
            effective_date,
            scraper_type_norm,
            mes_num,
            prev_mes_num,
            opmerking_raw,
            reset_event_type
        FROM vw_band_reset_events_v1
        WHERE {where_sql}
        ORDER BY effective_date DESC, row_nr
        LIMIT 20
    """
    recent_resets = fetch_all(resets_sql, params)

    summary = "Geen rapportdata beschikbaar."
    if report:
        parts = [
            f"Band {band_code} loopt in het actuele segment van {report['start_date']} tot {report['end_date']}.",
            f"Trendlabel: {report['mes_trend_label']}.",
        ]
        latest_types = report.get("latest_active_scraper_types")
        if latest_types:
            parts.append(f"Laatste actieve types: {latest_types}.")
        if report.get("n_band_resets") is not None:
            parts.append(f"Echte band-resets: {report['n_band_resets']}.")
        summary = " ".join(parts)

    return {
        "band_code": band_code,
        "report": report,
        "current_state": current_state,
        "recent_resets": recent_resets,
        "summary": summary,
    }


@router.get("/dataset/inspections")
def get_dataset_inspections(
    lijn_code: Optional[str] = Query(default=None),
    locatie_cluster_code: Optional[str] = Query(default=None),
    band_code: Optional[str] = Query(default=None),
    scraper_type: Optional[str] = Query(default=None),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=5000),
):
    conditions = ["1=1"]
    params: dict = {"limit": limit}

    if lijn_code:
        conditions.append("lijn_code = :lijn_code")
        params["lijn_code"] = lijn_code

    if locatie_cluster_code:
        conditions.append("locatie_cluster_code = :locatie_cluster_code")
        params["locatie_cluster_code"] = locatie_cluster_code

    if band_code:
        conditions.append("band_code_norm = :band_code")
        params["band_code"] = band_code.upper()

    if scraper_type:
        conditions.append("scraper_type_norm = :scraper_type")
        params["scraper_type"] = scraper_type.upper()

    if date_from:
        conditions.append("inspected_on >= :date_from")
        params["date_from"] = date_from

    if date_to:
        conditions.append("inspected_on <= :date_to")
        params["date_to"] = date_to

    where_sql = " AND ".join(conditions)

    sql = f"""
        SELECT
            lijn_code,
            locatie_cluster_code,
            locatie_cluster_naam,
            inspected_on,
            inspection_key,
            row_nr,
            band_code_raw,
            band_code_norm,
            band_breedte_mm,
            scraper_type_norm,
            scraper_role_guess,
            meshoogte_mm,
            mes_conditie_code,
            maintenance_marks_count,
            replace_event_text,
            has_vervuiling_signal,
            has_scheefloop_signal,
            has_mors_signal,
            has_bandprobleem_signal,
            has_toegankelijkheid_issue,
            has_nieuwe_band_signal,
            opmerking_text
        FROM vw_fact_band_scraper_inspection_v1
        WHERE {where_sql}
        ORDER BY inspected_on DESC, lijn_code, band_code_norm, row_nr
        LIMIT :limit
    """
    return fetch_all(sql, params)


@router.get("/band/{band_code}/dataset")
def get_band_dataset(
    band_code: str,
    lijn_code: Optional[str] = Query(default=None),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    limit: int = Query(default=500, ge=1, le=5000),
):
    conditions = ["band_code_norm = :band_code"]
    params: dict = {"band_code": band_code.upper(), "limit": limit}

    if lijn_code:
        conditions.append("lijn_code = :lijn_code")
        params["lijn_code"] = lijn_code

    if date_from:
        conditions.append("inspected_on >= :date_from")
        params["date_from"] = date_from

    if date_to:
        conditions.append("inspected_on <= :date_to")
        params["date_to"] = date_to

    where_sql = " AND ".join(conditions)

    sql = f"""
        SELECT
            lijn_code,
            locatie_cluster_code,
            locatie_cluster_naam,
            inspected_on,
            inspection_key,
            row_nr,
            band_code_norm,
            scraper_type_norm,
            scraper_role_guess,
            meshoogte_mm,
            mes_conditie_code,
            maintenance_marks_count,
            replace_event_text,
            has_vervuiling_signal,
            has_scheefloop_signal,
            has_mors_signal,
            has_bandprobleem_signal,
            has_toegankelijkheid_issue,
            has_nieuwe_band_signal,
            opmerking_text
        FROM vw_fact_band_scraper_inspection_v1
        WHERE {where_sql}
        ORDER BY inspected_on DESC, row_nr
        LIMIT :limit
    """
    return fetch_all(sql, params)


@router.get("/band/{band_code}/timeline")
def get_band_timeline(
    band_code: str,
    lijn_code: Optional[str] = Query(default=None),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    limit: int = Query(default=500, ge=1, le=5000),
):
    conditions = ["band_code_norm = :band_code"]
    params: dict = {"band_code": band_code.upper(), "limit": limit}

    if lijn_code:
        conditions.append("lijn_code = :lijn_code")
        params["lijn_code"] = lijn_code

    if date_from:
        conditions.append("inspected_on >= :date_from")
        params["date_from"] = date_from

    if date_to:
        conditions.append("inspected_on <= :date_to")
        params["date_to"] = date_to

    where_sql = " AND ".join(conditions)

    sql = f"""
        SELECT
            lijn_code,
            locatie_cluster_code,
            locatie_cluster_naam,
            band_code_norm,
            inspected_on,
            n_rows,
            n_scrapers,
            scraper_types_on_date,
            max_meshoogte_mm,
            min_meshoogte_mm,
            avg_meshoogte_mm,
            n_replace_events,
            n_vervuiling_signals,
            n_scheefloop_signals,
            n_mors_signals,
            n_bandprobleem_signals,
            n_toegankelijkheid_issues,
            opmerkingen
        FROM vw_analysis_band_timeline_v1
        WHERE {where_sql}
        ORDER BY inspected_on DESC
        LIMIT :limit
    """
    return fetch_all(sql, params)


@router.get("/band/{band_code}/analysis")
def get_band_analysis(
    band_code: str,
    lijn_code: Optional[str] = Query(default=None),
):
    conditions = ["band_code_norm = :band_code"]
    params: dict = {"band_code": band_code.upper()}

    if lijn_code:
        conditions.append("lijn_code = :lijn_code")
        params["lijn_code"] = lijn_code

    where_sql = " AND ".join(conditions)

    summary_sql = f"""
        SELECT
            lijn_code,
            locatie_cluster_code,
            locatie_cluster_naam,
            band_code_norm,
            eerste_inspectie,
            laatste_inspectie,
            n_inspectiedagen,
            avg_meshoogte_mm,
            max_meshoogte_mm,
            min_meshoogte_mm,
            n_replace_events,
            n_vervuiling_signals,
            n_scheefloop_signals,
            n_mors_signals,
            n_bandprobleem_signals,
            n_toegankelijkheid_issues,
            n_config_switches
        FROM vw_analysis_band_performance_v1
        WHERE {where_sql}
    """
    summary = fetch_one(summary_sql, params)

    timeline_sql = f"""
        SELECT
            inspected_on,
            scraper_types_on_date,
            avg_meshoogte_mm,
            n_replace_events,
            n_vervuiling_signals,
            n_scheefloop_signals,
            n_mors_signals,
            opmerkingen
        FROM vw_analysis_band_timeline_v1
        WHERE {where_sql}
        ORDER BY inspected_on DESC
        LIMIT 50
    """
    timeline = fetch_all(timeline_sql, params)

    switches_sql = f"""
        SELECT
            inspected_on,
            prev_scraper_types_on_date,
            scraper_types_on_date,
            is_config_switch
        FROM vw_analysis_band_switches_v1
        WHERE {where_sql}
        ORDER BY inspected_on DESC
        LIMIT 50
    """
    switches = fetch_all(switches_sql, params)

    analysis_lines: list[str] = []
    if summary:
        analysis_lines.append(
            f"Band {band_code.upper()} heeft {summary['n_inspectiedagen']} inspectiedagen tussen "
            f"{summary['eerste_inspectie']} en {summary['laatste_inspectie']}."
        )
        if summary.get("n_replace_events", 0):
            analysis_lines.append(f"Vervangevents: {summary['n_replace_events']}.")
        if summary.get("n_config_switches", 0):
            analysis_lines.append(f"Configuratiewissels: {summary['n_config_switches']}.")
        if summary.get("n_vervuiling_signals", 0):
            analysis_lines.append(f"Vervuilingssignalen: {summary['n_vervuiling_signals']}.")
        if summary.get("n_scheefloop_signals", 0):
            analysis_lines.append(f"Scheefloopsignalen: {summary['n_scheefloop_signals']}.")
        if summary.get("n_mors_signals", 0):
            analysis_lines.append(f"Morssignalen: {summary['n_mors_signals']}.")

    return {
        "band_code": band_code.upper(),
        "summary": summary,
        "analysis_summary": " ".join(analysis_lines) if analysis_lines else "Geen bandanalyse beschikbaar.",
        "timeline": timeline,
        "switches": switches,
    }


@router.get("/scraper/{scraper_type}/analysis")
def get_scraper_analysis(
    scraper_type: str,
    lijn_code: Optional[str] = Query(default=None),
    locatie_cluster_code: Optional[str] = Query(default=None),
):
    scraper_type_norm = scraper_type.upper()
    conditions = ["scraper_type_norm = :scraper_type"]
    params: dict = {"scraper_type": scraper_type_norm}

    if lijn_code:
        conditions.append("lijn_code = :lijn_code")
        params["lijn_code"] = lijn_code

    if locatie_cluster_code:
        conditions.append("locatie_cluster_code = :locatie_cluster_code")
        params["locatie_cluster_code"] = locatie_cluster_code

    where_sql = " AND ".join(conditions)

    summary_sql = f"""
        SELECT
            lijn_code,
            locatie_cluster_code,
            locatie_cluster_naam,
            scraper_type_norm,
            scraper_role_guess,
            eerste_inspectie,
            laatste_inspectie,
            n_rows,
            n_banden,
            avg_meshoogte_mm,
            max_meshoogte_mm,
            min_meshoogte_mm,
            n_replace_events,
            n_vervuiling_signals,
            n_scheefloop_signals,
            n_mors_signals,
            n_bandprobleem_signals,
            n_toegankelijkheid_issues
        FROM vw_analysis_scraper_performance_v1
        WHERE {where_sql}
        ORDER BY n_rows DESC
        LIMIT 100
    """
    summary_rows = fetch_all(summary_sql, params)

    recent_sql = f"""
        SELECT
            lijn_code,
            band_code_norm,
            inspected_on,
            meshoogte_mm,
            mes_conditie_code,
            replace_event_text,
            has_vervuiling_signal,
            has_scheefloop_signal,
            has_mors_signal,
            opmerking_text
        FROM vw_fact_band_scraper_inspection_v1
        WHERE {where_sql}
        ORDER BY inspected_on DESC, row_nr
        LIMIT 100
    """
    recent_rows = fetch_all(recent_sql, params)

    return {
        "scraper_type": scraper_type_norm,
        "summary_rows": summary_rows,
        "recent_observations": recent_rows,
    }


@router.get("/location/{locatie_code}/dataset")
def get_location_dataset(
    locatie_code: str,
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    limit: int = Query(default=500, ge=1, le=5000),
):
    conditions = [
        "(locatie_cluster_code = :locatie_code OR lijn_code = :locatie_code)"
    ]
    params: dict = {"locatie_code": locatie_code.upper(), "limit": limit}

    if date_from:
        conditions.append("inspected_on >= :date_from")
        params["date_from"] = date_from

    if date_to:
        conditions.append("inspected_on <= :date_to")
        params["date_to"] = date_to

    where_sql = " AND ".join(conditions)

    sql = f"""
        SELECT
            lijn_code,
            locatie_cluster_code,
            locatie_cluster_naam,
            inspected_on,
            inspection_key,
            row_nr,
            band_code_norm,
            scraper_type_norm,
            scraper_role_guess,
            meshoogte_mm,
            mes_conditie_code,
            replace_event_text,
            has_vervuiling_signal,
            has_scheefloop_signal,
            has_mors_signal,
            has_bandprobleem_signal,
            has_toegankelijkheid_issue,
            has_nieuwe_band_signal,
            opmerking_text
        FROM vw_fact_band_scraper_inspection_v1
        WHERE {where_sql}
        ORDER BY inspected_on DESC, lijn_code, band_code_norm, row_nr
        LIMIT :limit
    """
    return fetch_all(sql, params)


@router.get("/location/{locatie_code}/analysis")
def get_location_analysis(
    locatie_code: str,
):
    params = {"locatie_code": locatie_code.upper()}

    summary_sql = """
        SELECT
            locatie_cluster_code,
            locatie_cluster_naam,
            lijn_code,
            eerste_inspectie,
            laatste_inspectie,
            n_rows,
            n_banden,
            n_scrapertypes,
            avg_meshoogte_mm,
            max_meshoogte_mm,
            min_meshoogte_mm,
            n_replace_events,
            n_vervuiling_signals,
            n_scheefloop_signals,
            n_mors_signals,
            n_bandprobleem_signals,
            n_toegankelijkheid_issues
        FROM vw_analysis_location_performance_v1
        WHERE locatie_cluster_code = :locatie_code
           OR lijn_code = :locatie_code
        ORDER BY lijn_code
    """
    summary_rows = fetch_all(summary_sql, params)

    top_bands_sql = """
        SELECT
            lijn_code,
            band_code_norm,
            laatste_inspectie,
            n_inspectiedagen,
            n_replace_events,
            n_vervuiling_signals,
            n_scheefloop_signals,
            n_mors_signals,
            n_bandprobleem_signals,
            n_config_switches
        FROM vw_analysis_band_performance_v1
        WHERE locatie_cluster_code = :locatie_code
           OR lijn_code = :locatie_code
        ORDER BY
            n_vervuiling_signals DESC,
            n_scheefloop_signals DESC,
            n_mors_signals DESC,
            n_replace_events DESC,
            n_config_switches DESC,
            band_code_norm
        LIMIT 100
    """
    top_bands = fetch_all(top_bands_sql, params)

    top_scrapers_sql = """
        SELECT
            lijn_code,
            scraper_type_norm,
            scraper_role_guess,
            n_rows,
            n_banden,
            n_replace_events,
            n_vervuiling_signals,
            n_scheefloop_signals,
            n_mors_signals,
            n_bandprobleem_signals
        FROM vw_analysis_scraper_performance_v1
        WHERE locatie_cluster_code = :locatie_code
           OR lijn_code = :locatie_code
        ORDER BY
            n_vervuiling_signals DESC,
            n_scheefloop_signals DESC,
            n_mors_signals DESC,
            n_replace_events DESC,
            n_rows DESC
        LIMIT 100
    """
    top_scrapers = fetch_all(top_scrapers_sql, params)

    return {
        "locatie_code": locatie_code.upper(),
        "location_summary": summary_rows,
        "top_bands": top_bands,
        "top_scrapers": top_scrapers,
    }


@router.get("/sublocation/{sublocatie_code}/history")
def get_sublocation_history(
    sublocatie_code: str,
    limit: int = Query(default=500, ge=1, le=2000),
):
    sql = """
        SELECT
            lijn_code,
            band_code,
            sublocatie_code,
            sublocatie_naam,
            procesdeel,
            effective_date,
            scraper_channel,
            scraper_type_norm,
            mes_num,
            status_norm,
            vervuiling_hits,
            bandschade_hits,
            scheefloop_hits,
            opmerking_raw,
            laatste_word_opmerking
        FROM vw_band_history_daily_v1
        WHERE sublocatie_code = :sublocatie_code
        ORDER BY band_code, effective_date DESC, scraper_channel
        LIMIT :limit
    """
    return fetch_all(sql, {"sublocatie_code": sublocatie_code, "limit": limit})