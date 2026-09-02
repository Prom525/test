from __future__ import annotations

import re
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from ..db import engine

router = APIRouter(prefix="/plugin", tags=["plugin"])


# =========================================================
# Config
# =========================================================

SAFE_PREFIXES = ("select", "with")

BLOCKED_KEYWORDS = (
    " drop ", " truncate ", " delete ", " update ", " insert ",
    " alter ", " create ", " grant ", " revoke ", " execute ",
    " copy ", " attach ", " vacuum ", " cascade "
)

# Alleen deze views/tables mogen via /plugin/sql bevraagd worden.
# Voeg hier later eventueel meer read-only objecten aan toe.
ALLOWED_OBJECTS = {
    # Mes / forecast
    "vw_meshoogte_latest_per_scraper_clean",
    "vw_mes_lifecycle_cycles_clean",
    "vw_mes_cycle_analysis_clean",

    # Inspectie / analyse
    "vw_fact_inspection_combined_v2",
    "vw_fact_inspection_excel_v2",
    "vw_all_replacement_advice",
    "vw_mes_replace_events_norm",
    "sb_inspections_v0",
    "sb_inspection_items_v0",

    # Product / scraper
    "scraper_product",
    "scraper_rule",
    "scraper_rule_action",
    "scraper_rule_condition",
    "scraper_capability",
    "scraper_case",
    "scraper_preset",

    # Band / materiaal
    "dim_bands",
    "dim_materials",
    "bridge_band_material",
}

PREFERRED_SCHEMA_OBJECTS = [
    {
        "name": "vw_meshoogte_latest_per_scraper_clean",
        "description": "Laatste gemeten meshoogte per schraper.",
        "preferred_columns": [
            "laatste_meting_datum",
            "lijn_code",
            "locatie",
            "band_norm",
            "scraper_family",
            "scraper_type_norm",
            "position_hint",
            "meshoogte_mm",
            "commentaar",
        ],
    },
    {
        "name": "vw_mes_lifecycle_cycles_clean",
        "description": "Tijdreeks van meshoogte per schraper, opgeschoond naar 1 meetpunt per dag.",
        "preferred_columns": [
            "inspected_on",
            "lijn_code",
            "locatie",
            "band_norm",
            "scraper_family",
            "scraper_type_norm",
            "position_hint",
            "meshoogte_mm",
            "commentaar",
            "replace_event",
            "cycle_id",
        ],
    },
    {
        "name": "vw_mes_cycle_analysis_clean",
        "description": "Forecast per slijtagecyclus met vervanggrens bij 3 mm.",
        "preferred_columns": [
            "lijn_code",
            "band_norm",
            "scraper_type_norm",
            "position_hint",
            "cycle_start",
            "cycle_end",
            "meetpunten",
            "start_meshoogte_mm",
            "eind_meshoogte_mm",
            "slijtage_mm_per_dag",
            "geschatte_dagen_tot_3mm",
            "geschatte_vervangdatum_bij_3mm",
            "status_3mm",
        ],
    },
    {
        "name": "vw_all_replacement_advice",
        "description": "Actuele vervangadviezen op basis van interval/logica.",
        "preferred_columns": [
            "lijn_code",
            "band_norm",
            "scraper_family",
            "scraper_type_norm",
            "next_due_date",
            "days_to_due",
            "typical_mes_qty",
            "status",
        ],
    },
]


# =========================================================
# Models
# =========================================================

class QueryIn(BaseModel):
    sql: str
    max_rows: int = Field(500, ge=1, le=5000)
    timeout_ms: int = Field(6000, ge=100, le=30000)


# =========================================================
# Helpers
# =========================================================

def _normalize_sql(sql: str) -> str:
    return re.sub(r"\s+", " ", (sql or "").strip()).strip()


def _validate_readonly_sql(sql: str) -> None:
    s = f" {_normalize_sql(sql).lower()} "

    if not s.strip().startswith(SAFE_PREFIXES):
        raise HTTPException(status_code=400, detail="Alleen SELECT/WITH queries zijn toegestaan.")

    for kw in BLOCKED_KEYWORDS:
        if kw in s:
            raise HTTPException(status_code=400, detail=f"Keyword '{kw.strip()}' is niet toegestaan.")


def _extract_referenced_objects(sql: str) -> set[str]:
    """
    Eenvoudige parser:
    zoekt objectnamen na FROM / JOIN.
    Voldoende voor onze use case.
    """
    norm = _normalize_sql(sql).lower()
    matches = re.findall(r"\b(?:from|join)\s+([a-zA-Z0-9_\.]+)", norm, flags=re.IGNORECASE)
    objects: set[str] = set()

    for m in matches:
        obj = m.split(".")[-1].strip('"')
        if obj:
            objects.add(obj)
    return objects


def _validate_allowed_objects(sql: str) -> None:
    refs = _extract_referenced_objects(sql)
    if not refs:
        return

    disallowed = sorted(r for r in refs if r not in ALLOWED_OBJECTS)
    if disallowed:
        raise HTTPException(
            status_code=400,
            detail=f"Niet-toegestane objecten in query: {', '.join(disallowed)}",
        )


def _apply_limit(sql: str, max_rows: int) -> str:
    s = re.sub(r";\s*$", "", sql.strip(), flags=re.IGNORECASE)
    if re.search(r"\blimit\b", s, re.IGNORECASE):
        return s
    return f"{s} LIMIT {max_rows}"


def _run_select(sql: str, max_rows: int = 500, timeout_ms: int = 6000) -> list[dict[str, Any]]:
    _validate_readonly_sql(sql)
    _validate_allowed_objects(sql)

    safe_sql = _apply_limit(sql, max_rows=max_rows)

    try:
        with engine.begin() as conn:
            conn.execute(text(f"SET LOCAL statement_timeout = {int(timeout_ms)}"))
            res = conn.execute(text(safe_sql))
            return [dict(r._mapping) for r in res]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


def _quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _opt_eq(col: str, value: Optional[str]) -> str:
    if value is None or str(value).strip() == "":
        return ""
    return f" AND {col} = {_quote(str(value).strip())} "


def _opt_date_from(col: str, value: Optional[str]) -> str:
    if value is None or str(value).strip() == "":
        return ""
    return f" AND {col} >= DATE {_quote(str(value).strip())} "


def _opt_date_to(col: str, value: Optional[str]) -> str:
    if value is None or str(value).strip() == "":
        return ""
    return f" AND {col} <= DATE {_quote(str(value).strip())} "


# =========================================================
# Generic schema/sql endpoints
# =========================================================

@router.get("/schema")
def plugin_schema():
    """
    GPT-vriendelijk schema-overzicht:
    - voorkeursviews met beschrijving
    - kolommen van alleen toegestane objecten
    """
    sql = """
    SELECT
        table_name,
        column_name,
        data_type,
        ordinal_position
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = ANY(:table_names)
    ORDER BY table_name, ordinal_position
    """

    table_names = sorted(ALLOWED_OBJECTS)

    with engine.begin() as conn:
        res = conn.execute(text(sql), {"table_names": table_names})
        rows = [dict(r._mapping) for r in res]

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["table_name"], []).append(
            {
                "column_name": row["column_name"],
                "data_type": row["data_type"],
                "ordinal_position": row["ordinal_position"],
            }
        )

    preferred = []
    for item in PREFERRED_SCHEMA_OBJECTS:
        preferred.append(
            {
                "name": item["name"],
                "description": item["description"],
                "preferred_columns": item["preferred_columns"],
                "columns": grouped.get(item["name"], []),
            }
        )

    return {
        "preferred_objects": preferred,
        "allowed_objects": sorted(ALLOWED_OBJECTS),
    }


@router.post("/sql")
def plugin_sql(q: QueryIn):
    rows = _run_select(q.sql, max_rows=q.max_rows, timeout_ms=q.timeout_ms)
    return {"rows": rows}


# =========================================================
# Business endpoints - meshoogte / lifecycle / forecast
# =========================================================

@router.get("/mes/latest")
def mes_latest(
    lijn_code: Optional[str] = Query(None),
    band_norm: Optional[str] = Query(None),
    scraper_type_norm: Optional[str] = Query(None),
    position_hint: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=200),
):
    sql = f"""
    SELECT
        laatste_meting_datum,
        lijn_code,
        locatie,
        band_norm,
        scraper_family,
        scraper_type_norm,
        position_hint,
        meshoogte_mm,
        commentaar
    FROM vw_meshoogte_latest_per_scraper_clean
    WHERE 1=1
      {_opt_eq("lijn_code", lijn_code)}
      {_opt_eq("band_norm", band_norm)}
      {_opt_eq("scraper_type_norm", scraper_type_norm)}
      {_opt_eq("position_hint", position_hint)}
    ORDER BY laatste_meting_datum DESC, lijn_code, band_norm, scraper_type_norm
    """
    rows = _run_select(sql, max_rows=limit)
    return {"rows": rows}


@router.get("/mes/lifecycle")
def mes_lifecycle(
    lijn_code: Optional[str] = Query(None),
    band_norm: Optional[str] = Query(None),
    scraper_type_norm: Optional[str] = Query(None),
    position_hint: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None, description="YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="YYYY-MM-DD"),
    limit: int = Query(100, ge=1, le=1000),
):
    sql = f"""
    SELECT
        inspected_on,
        lijn_code,
        locatie,
        band_norm,
        scraper_family,
        scraper_type_norm,
        position_hint,
        meshoogte_mm,
        commentaar,
        replace_event,
        cycle_id
    FROM vw_mes_lifecycle_cycles_clean
    WHERE 1=1
      {_opt_eq("lijn_code", lijn_code)}
      {_opt_eq("band_norm", band_norm)}
      {_opt_eq("scraper_type_norm", scraper_type_norm)}
      {_opt_eq("position_hint", position_hint)}
      {_opt_date_from("inspected_on", date_from)}
      {_opt_date_to("inspected_on", date_to)}
    ORDER BY lijn_code, band_norm, scraper_type_norm, position_hint, inspected_on
    """
    rows = _run_select(sql, max_rows=limit)
    return {"rows": rows}


@router.get("/mes/forecast")
def mes_forecast(
    lijn_code: Optional[str] = Query(None),
    band_norm: Optional[str] = Query(None),
    scraper_type_norm: Optional[str] = Query(None),
    status_3mm: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None, description="Filter op cycle_end vanaf datum YYYY-MM-DD"),
    limit: int = Query(50, ge=1, le=500),
):
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
    WHERE meetpunten >= 3
      {_opt_eq("lijn_code", lijn_code)}
      {_opt_eq("band_norm", band_norm)}
      {_opt_eq("scraper_type_norm", scraper_type_norm)}
      {_opt_eq("status_3mm", status_3mm)}
      {_opt_date_from("cycle_end", date_from)}
    ORDER BY
      CASE status_3mm
        WHEN 'NU VERVANGEN' THEN 1
        WHEN 'BINNEN 30 DAGEN' THEN 2
        WHEN 'BINNEN 60 DAGEN' THEN 3
        ELSE 4
      END,
      geschatte_vervangdatum_bij_3mm ASC NULLS LAST
    """
    rows = _run_select(sql, max_rows=limit)
    return {"rows": rows}


@router.get("/mes/risk")
def mes_risk(
    lijn_code: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=200),
):
    sql = f"""
    SELECT
        lijn_code,
        band_norm,
        scraper_type_norm,
        position_hint,
        eind_meshoogte_mm,
        geschatte_dagen_tot_3mm,
        geschatte_vervangdatum_bij_3mm,
        status_3mm
    FROM vw_mes_cycle_analysis_clean
    WHERE meetpunten >= 3
      AND status_3mm IN ('NU VERVANGEN', 'BINNEN 30 DAGEN', 'BINNEN 60 DAGEN')
      {_opt_eq("lijn_code", lijn_code)}
    ORDER BY
      CASE status_3mm
        WHEN 'NU VERVANGEN' THEN 1
        WHEN 'BINNEN 30 DAGEN' THEN 2
        WHEN 'BINNEN 60 DAGEN' THEN 3
        ELSE 4
      END,
      geschatte_vervangdatum_bij_3mm ASC NULLS LAST
    """
    rows = _run_select(sql, max_rows=limit)
    return {"rows": rows}


@router.get("/replacement/actual")
def replacement_actual(
    lijn_code: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=200),
):
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
    WHERE status IN ('OVERDUE', 'BINNEN_2_WEKEN', 'BINNEN_1_MAAND')
      {_opt_eq("lijn_code", lijn_code)}
    ORDER BY
      CASE status
        WHEN 'OVERDUE' THEN 1
        WHEN 'BINNEN_2_WEKEN' THEN 2
        WHEN 'BINNEN_1_MAAND' THEN 3
        ELSE 4
      END,
      next_due_date ASC NULLS LAST
    """
    rows = _run_select(sql, max_rows=limit)
    return {"rows": rows}