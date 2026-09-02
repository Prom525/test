from __future__ import annotations

import re
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text

from app.db import engine
from datetime import date, timedelta
from app.routers.analysis_api_v10 import enrich_performance_6mm

router = APIRouter(
    prefix="/analysis/context",
    tags=["promati-context"],
)


def fetch_all(sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    with engine.begin() as conn:
        rows = conn.execute(text(sql), params or {}).mappings().all()
    return [dict(r) for r in rows]


def fetch_one(sql: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
    with engine.begin() as conn:
        row = conn.execute(text(sql), params or {}).mappings().first()
    return dict(row) if row else None

def normalize_code(value: str | None) -> str | None:
    if value is None:
        return None
    return re.sub(r"\s+", "", value).upper()


def normalize_scraper_type(value: str | None) -> str | None:
    if not value:
        return None
    return re.sub(r"\s+", " ", value.strip()).upper()


def normalize_scraper_type_canonical(value: str | None) -> str | None:
    if not value:
        return None

    s = normalize_scraper_type(value)
    s_compact = re.sub(r"[^A-Z0-9]", "", s)

    if s_compact in {"U140LBVB", "U1400LBVB"}:
        return "U 1400 LB/VB"

    if s_compact in {"U140VB", "U1400VB"}:
        return "U 1400 VB"

    if s_compact in {"U140LB", "U1400LB"}:
        return "U 1400 LB"

    # A210 / bekende U-varianten
    if s_compact in {"U140INOX", "U1400INOX"}:
        return "U 1400 INOX"

    if s_compact in {"U140", "U1400"}:
        return "U 1400"

    if s_compact in {"U160", "U1600"}:
        return "U 1600"

    if s_compact in {"U180", "U1800"}:
        return "U 1800"

    if s_compact in {"U65", "UI65"}:
        return "U 650"

    # TPH-varianten
    if s_compact.startswith("TPH1400"):
        if "HDI" in s_compact:
            return "TPH 1400 HDI"
        if "HD" in s_compact:
            return "TPH 1400 HD"
        return "TPH 1400"

    return s


def normalize_accessory_name(value: str | None) -> str | None:
    if not value:
        return None

    compact = re.sub(r"[^A-Z0-9]", "", value.upper())

    if compact == "DUOSEAL":
        return "DUO-SEAL"

    if "SANCIC" in compact:
        return "SANCIC"

    if "SLIJTTEGEL" in compact or "SLIJTTEGELS" in compact:
        return "SLIJTTEGELS"

    if "TUSSENPARTSCHRAPER" in compact or "TUSSEPARTSCHRAPER" in compact:
        return "TUSSENPARTSCHRAPER"

    if "CLEANSCRAPE" in compact or "CLEANSCAPE" in compact:
        return "CLEANSCRAPE"

    if compact in {"INSPECTIELUIK"}:
        return "INSPECTIE LUIK"

    return None


def split_scrapers_and_accessories(scraper_types_raw: str | None) -> tuple[list[str], list[str]]:
    scrapers: list[str] = []
    accessories: list[str] = []

    for part in (scraper_types_raw or "").split("|"):
        item = part.strip()
        if not item:
            continue

        accessory = normalize_accessory_name(item)
        if accessory:
            accessories.append(accessory)
        else:
            clean = normalize_scraper_type_canonical(item) or item
            scrapers.append(clean)

    return sorted(set(scrapers)), sorted(set(accessories))


def clean_band_performance_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None

    clean = dict(row)

    raw_scraper_types = clean.get("scraper_types")
    scrapers, accessories = split_scrapers_and_accessories(raw_scraper_types)

    clean["scraper_types_raw"] = raw_scraper_types
    clean["scraper_types_clean"] = " | ".join(scrapers)
    clean["scraper_types"] = clean["scraper_types_clean"]
    clean["position_accessories"] = accessories

    # Extra context voor line/belt overzicht:
    # - accessoire-only: er staan wel raw waarden, maar geen echte schrapers
    # - unknown/observatie-only: bandcode is ONBEKEND of er zijn geen position rows
    clean["is_accessory_only"] = bool(accessories and not scrapers)
    clean["is_unknown_band"] = clean.get("band_code") in ("ONBEKEND", "", None)
    clean["is_observation_only"] = bool((clean.get("n_position_rows") or 0) == 0)
    clean["is_position_only"] = bool(
        clean["is_accessory_only"]
        or clean["is_unknown_band"]
        or clean["is_observation_only"]
    )

    if clean["is_accessory_only"]:
        clean["context_note"] = "Alleen position/accessory data; geen echte schraperconfiguratie."
    elif clean["is_unknown_band"]:
        clean["context_note"] = "Onbekende of niet-herkende bandcode; niet leidend als bandconfiguratie."
    elif clean["is_observation_only"]:
        clean["context_note"] = "Alleen observatieregels; geen position rows."
    else:
        clean["context_note"] = "Normale bandconfiguratie."

    return clean


def clean_band_performance_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        clean
        for row in rows
        if (clean := clean_band_performance_row(row)) is not None
    ]


def clean_lifecycle_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    result: list[dict[str, Any]] = []

    for row in rows:
        clean = dict(row)

        raw_type = clean.get("scraper_type_norm")
        clean_type = normalize_scraper_type_canonical(raw_type)

        if clean_type:
            clean["scraper_type_norm_raw"] = raw_type
            clean["scraper_type_norm"] = clean_type

        key = (
            clean.get("lijn_code"),
            clean.get("band_norm"),
            clean.get("scraper_type_norm"),
            clean.get("position_hint"),
            clean.get("cycle_id"),
            clean.get("inspected_on"),
            clean.get("meshoogte_mm"),
            clean.get("replace_event"),
        )

        if key in seen:
            continue

        seen.add(key)
        result.append(clean)

    return result


def clean_forecast_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    result: list[dict[str, Any]] = []

    for row in rows:
        clean = dict(row)

        raw_type = clean.get("scraper_type_norm")
        clean_type = normalize_scraper_type_canonical(raw_type)

        if clean_type:
            clean["scraper_type_norm_raw"] = raw_type
            clean["scraper_type_norm"] = clean_type

        key = (
            clean.get("lijn_code"),
            clean.get("band_norm"),
            clean.get("scraper_type_norm"),
            clean.get("position_hint"),
            clean.get("cycle_start"),
            clean.get("cycle_end"),
        )

        if key in seen:
            continue

        seen.add(key)
        clean = enrich_performance_6mm(clean)
        result.append(clean)

    return result


def clean_maintenance_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    result: list[dict[str, Any]] = []

    for row in rows:
        clean = dict(row)

        raw_scraper_types = clean.get("scraper_types")
        scrapers, accessories = split_scrapers_and_accessories(raw_scraper_types)

        clean["scraper_types_raw"] = raw_scraper_types
        clean["scraper_types_clean"] = " | ".join(scrapers)
        clean["scraper_types"] = clean["scraper_types_clean"]
        clean["position_accessories"] = accessories

        key = (
            clean.get("lijn_code"),
            clean.get("band_norm"),
            clean.get("position_hint"),
            clean.get("scraper_types_clean"),
            clean.get("cycle_start"),
            clean.get("cycle_end"),
        )

        if key in seen:
            continue

        seen.add(key)
        clean = enrich_performance_6mm(clean)
        result.append(clean)

    return result


def get_excel_clean_scraper_context(
    lijn_code: str | None,
    band_code: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    conditions = ["1=1"]
    params: dict[str, Any] = {"limit": limit}

    if lijn_code:
        conditions.append("lijn_code = :lijn_code")
        params["lijn_code"] = normalize_code(lijn_code)

    if band_code:
        conditions.append("""
            REPLACE(
                UPPER(COALESCE(band_locatie_norm, locatie_raw, '')),
                ' ',
                ''
            ) = :band_code
        """)
        params["band_code"] = normalize_code(band_code)

    where_sql = " AND ".join(conditions)

    scrapers = fetch_all(
        f"""
        SELECT
            lijn_code,
            COALESCE(band_locatie_norm, locatie_raw) AS band_code,
            scraper_type_norm_clean,
            scraper_family_clean,
            scraper_mount_status_clean,
            COUNT(*) AS n
        FROM public.vw_excel_positions_clean_v1
        WHERE {where_sql}
          AND is_false_positive = false
          AND is_position_accessory = false
          AND scraper_mount_status_clean NOT IN ('GEEN_SCHRAPER', 'POSITION_ACCESSORY')
          AND scraper_type_norm_clean IS NOT NULL
          AND TRIM(scraper_type_norm_clean) <> ''
        GROUP BY
            lijn_code,
            COALESCE(band_locatie_norm, locatie_raw),
            scraper_type_norm_clean,
            scraper_family_clean,
            scraper_mount_status_clean
        ORDER BY n DESC, scraper_type_norm_clean
        LIMIT :limit
        """,
        params,
    )

    accessories = fetch_all(
        f"""
        SELECT
            lijn_code,
            COALESCE(band_locatie_norm, locatie_raw) AS band_code,
            scraper_type_norm_clean AS accessory_name,
            accessory_type,
            scraper_mount_status_clean,
            COUNT(*) AS n
        FROM public.vw_excel_positions_clean_v1
        WHERE {where_sql}
          AND is_position_accessory = true
        GROUP BY
            lijn_code,
            COALESCE(band_locatie_norm, locatie_raw),
            scraper_type_norm_clean,
            accessory_type,
            scraper_mount_status_clean
        ORDER BY n DESC, accessory_name
        LIMIT :limit
        """,
        params,
    )

    return {
        "scrapers_excel_clean": scrapers,
        "scraper_names_excel_clean": sorted({
            row.get("scraper_type_norm_clean")
            for row in scrapers
            if row.get("scraper_type_norm_clean")
        }),
        "position_accessories_excel_clean": accessories,
        "position_accessory_names_excel_clean": sorted({
            row.get("accessory_name")
            for row in accessories
            if row.get("accessory_name")
        }),
    }

def enrich_replacement_advice_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []

    for row in rows:
        clean = dict(row)

        days_to_due = clean.get("days_to_due")
        n_intervals = clean.get("n_intervals")
        median_interval_days = clean.get("median_interval_days")
        last_replace_date = clean.get("last_replace_date")
        band_norm = clean.get("band_norm")
        scraper_type_norm = clean.get("scraper_type_norm")

        clean_type = normalize_scraper_type_canonical(scraper_type_norm)
        if clean_type:
            clean["scraper_type_norm_raw"] = scraper_type_norm
            clean["scraper_type_norm"] = clean_type

        if days_to_due is None:
            clean["overdue_age_bucket"] = "ONBEKEND"
        elif days_to_due >= 0:
            clean["overdue_age_bucket"] = "NIET_OVERDUE"
        elif days_to_due >= -90:
            clean["overdue_age_bucket"] = "OVERDUE_0_90_DAGEN"
        elif days_to_due >= -365:
            clean["overdue_age_bucket"] = "OVERDUE_90_365_DAGEN"
        else:
            clean["overdue_age_bucket"] = "OVERDUE_MEER_DAN_1_JAAR"

        possible_reasons: list[str] = []

        if days_to_due is not None and days_to_due < -365:
            possible_reasons.append(
                "Lang overdue volgens historisch vervanginterval; controleer of vervanging wel geregistreerd is."
            )

        if n_intervals is not None and n_intervals < 3:
            possible_reasons.append(
                "Weinig historische vervangintervallen; voorspelling kan onbetrouwbaar zijn."
            )

        if median_interval_days is not None and median_interval_days < 60:
            possible_reasons.append(
                "Kort historisch median interval; kleine registratieverschillen kunnen snel overdue geven."
            )

        if not band_norm:
            possible_reasons.append(
                "Geen band_norm; koppeling naar band/locatie is onzeker."
            )

        if scraper_type_norm and clean.get("scraper_type_norm_raw") != clean.get("scraper_type_norm"):
            possible_reasons.append(
                "Scrapernaam is gecanonicaliseerd; controleer naamvarianten in brondata."
            )

        if not last_replace_date:
            possible_reasons.append(
                "Geen laatste vervangdatum gevonden."
            )

        clean["possible_reasons"] = possible_reasons
        if clean["overdue_age_bucket"] == "OVERDUE_90_365_DAGEN":
            possible_reasons.append(
                "Meer dan 90 dagen overdue; controleer of mes bewust laag is blijven staan of vervanging ontbreekt."
            )

        if clean["overdue_age_bucket"] == "OVERDUE_0_90_DAGEN":
            possible_reasons.append(
                "Recent overdue; mogelijk normaal opvolgmoment of planning controleren."
            )
        clean["needs_review"] = bool(
            clean["overdue_age_bucket"] in {
                "OVERDUE_90_365_DAGEN",
                "OVERDUE_MEER_DAN_1_JAAR",
            }
            or (n_intervals is not None and n_intervals < 3)
        )

        enriched.append(clean)

    return enriched

def normalize_scraper_for_compare(value: str | None) -> str | None:
    clean = normalize_scraper_type_canonical(value)
    if not clean:
        return None
    return re.sub(r"[^A-Z0-9]", "", clean.upper())

def detect_hosch_replacement_from_inspections(rows: list[dict[str, Any]]) -> dict[str, Any]:
    hosch_rows = []

    for row in rows:
        text = " ".join([
            str(row.get("commentaar") or ""),
            str(row.get("scraper_type_raw") or ""),
        ]).upper()

        if "HOSCH" in text or "HOCH" in text:
            hosch_rows.append(row)

    hosch_rows_deduped = dedupe_recent_inspections(hosch_rows)

    return {
        "has_hosch_signal": bool(hosch_rows),
        "hosch_signal_count": len(hosch_rows_deduped),
        "hosch_signal_raw_count": len(hosch_rows),
        "latest_hosch_signal_date": hosch_rows[0].get("document_date") if hosch_rows else None,
        "latest_hosch_signal_comment": hosch_rows[0].get("commentaar") if hosch_rows else None,
        "likely_current_status": "CONCURRENT_HOSCH" if hosch_rows else "UNKNOWN",
        "evidence": hosch_rows_deduped[:10],
    }

def dedupe_recent_inspections(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    result: list[dict[str, Any]] = []

    for row in rows:
        key = (
            row.get("document_date"),
            row.get("band_code"),
            row.get("locatie_raw"),
            row.get("scraper_type_raw"),
            row.get("meshoogte_mm"),
            row.get("mes_vervangen"),
            row.get("commentaar"),
            row.get("status"),
        )

        if key in seen:
            continue

        seen.add(key)
        result.append(row)

    return result

@router.get("/belt/{band_code}")
def get_belt_context(
    band_code: str,
    lijn_code: Optional[str] = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
):
    band_code_norm = band_code.replace(" ", "").upper()
    lijn_code_norm = lijn_code.replace(" ", "").upper() if lijn_code else None

    performance = fetch_one(
        """
        SELECT *
        FROM vw_band_performance_v1
        WHERE band_code = :band_code
          AND (:lijn_code IS NULL OR lijn_code = :lijn_code)
        LIMIT 1
        """,
        {"band_code": band_code_norm, "lijn_code": lijn_code_norm},
    )

    latest_mes = fetch_all(
        """
        SELECT *
        FROM vw_meshoogte_latest_per_scraper_clean
        WHERE band_norm = :band_code
          AND (:lijn_code IS NULL OR lijn_code = :lijn_code)
        ORDER BY laatste_meting_datum DESC NULLS LAST
        LIMIT :limit
        """,
        {"band_code": band_code_norm, "lijn_code": lijn_code_norm, "limit": limit},
    )

    lifecycle = fetch_all(
        """
        SELECT *
        FROM vw_mes_lifecycle_cycles_clean
        WHERE band_norm = :band_code
          AND (:lijn_code IS NULL OR lijn_code = :lijn_code)
        ORDER BY inspected_on DESC NULLS LAST
        LIMIT :limit
        """,
        {"band_code": band_code_norm, "lijn_code": lijn_code_norm, "limit": limit},
    )

    forecast = fetch_all(
        """
        SELECT *
        FROM vw_mes_cycle_analysis_clean
        WHERE band_norm = :band_code
          AND (:lijn_code IS NULL OR lijn_code = :lijn_code)
          AND meetpunten >= 3
          AND cycle_end >= CURRENT_DATE - INTERVAL '2 years'
        ORDER BY
          CASE status_3mm
            WHEN 'NU VERVANGEN' THEN 1
            WHEN 'BINNEN 30 DAGEN' THEN 2
            WHEN 'BINNEN 60 DAGEN' THEN 3
            ELSE 4
          END,
          geschatte_vervangdatum_bij_3mm ASC NULLS LAST
        LIMIT :limit
        """,
        {"band_code": band_code_norm, "lijn_code": lijn_code_norm, "limit": limit},
    )

    maintenance = fetch_all(
        """
        SELECT *
        FROM vw_mes_maintenance_positions_latest
        WHERE band_norm = :band_code
          AND (:lijn_code IS NULL OR lijn_code = :lijn_code)
          AND cycle_end >= CURRENT_DATE - INTERVAL '2 years'
        ORDER BY
          prioriteit,
          geschatte_vervangdatum_bij_3mm ASC NULLS LAST,
          position_hint
        LIMIT :limit
        """,
        {"band_code": band_code_norm, "lijn_code": lijn_code_norm, "limit": limit},
    )

    inspection_rows = fetch_all(
        """
        SELECT
            inspection_key,
            document_date,
            line_hint,
            band_code,
            locatie_raw,
            scraper_type_raw,
            meshoogte_mm,
            mes_vervangen,
            commentaar,
            check_code,
            status,
            source_file,
            source_system
        FROM vw_fact_inspection_combined_v2
        WHERE REPLACE(COALESCE(band_code, locatie_raw, ''), ' ', '') = :band_code
          AND (:lijn_code IS NULL OR line_hint = :lijn_code)
        ORDER BY document_date DESC NULLS LAST
        LIMIT :limit
        """,
        {"band_code": band_code_norm, "lijn_code": lijn_code_norm, "limit": limit},
    )

    scraper_status = fetch_all(
        """
        SELECT *
        FROM vw_band_scraper_api_v1
        WHERE band_locatie = :band_code
          AND (:lijn_code IS NULL OR lijn_code = :lijn_code)
        ORDER BY inspection_key DESC
        LIMIT :limit
        """,
        {"band_code": band_code_norm, "lijn_code": lijn_code_norm, "limit": limit},
    )

    performance_clean = clean_band_performance_row(performance)

    latest_mes_clean = clean_lifecycle_rows(latest_mes)
    lifecycle_clean = clean_lifecycle_rows(lifecycle)
    forecast_clean = clean_forecast_rows(forecast)

    excel_clean_context = get_excel_clean_scraper_context(
        lijn_code=lijn_code_norm,
        band_code=band_code_norm,
        limit=limit,
    )

    return {
        "status": "ok",
        "context_type": "belt_context",
        "band_code": band_code_norm,
        "lijn_code": lijn_code_norm,

        "performance": performance_clean,
        "performance_raw": performance,

        "latest_meshoogte": latest_mes_clean,
        "latest_meshoogte_raw_count": len(latest_mes),

        "lifecycle": lifecycle_clean,
        "lifecycle_raw_count": len(lifecycle),

        "forecast_3mm": forecast_clean,
        "forecast_3mm_raw_count": len(forecast),

        "recent_inspections": inspection_rows,

        "scraper_status_historisch": scraper_status[:5],
        "scraper_status_raw_count": len(scraper_status),

        "schrapers_excel_clean": excel_clean_context.get("scrapers_excel_clean", []),
        "position_accessories": excel_clean_context.get("position_accessory_names_excel_clean", []),
        "position_accessories_detail": excel_clean_context.get("position_accessories_excel_clean", []),

        "maintenance_positions": clean_maintenance_rows(maintenance),
        "maintenance_summary": {
            "n_total": len(maintenance),
            "n_binnen_60_dagen": sum(1 for r in maintenance if r.get("status_3mm") == "BINNEN 60 DAGEN"),
            "n_check_trend": sum(1 for r in maintenance if r.get("status_3mm") == "CHECK_TREND"),
            "n_te_weinig_meetpunten": sum(1 for r in maintenance if r.get("status_3mm") == "TE_WEINIG_MEETPUNTEN"),
        },

        "datakwaliteit": {
            "heeft_excel_clean_context": bool(excel_clean_context.get("scrapers_excel_clean") or excel_clean_context.get("position_accessories_excel_clean")),
            "gebruik_clean_context_als_leidend": True,
        },

        "write_actions_available": False,
    }


@router.get("/line/{lijn_code}")
def get_line_context(
    lijn_code: str,
    limit: int = Query(default=25, ge=1, le=100),
):
    lijn_code_norm = lijn_code.replace(" ", "").upper()

    location_performance = fetch_one(
        """
        SELECT *
        FROM vw_location_performance_v1
        WHERE lijn_code = :lijn_code
        LIMIT 1
        """,
        {"lijn_code": lijn_code_norm},
    )

    bands = fetch_all(
        """
        SELECT *
        FROM vw_band_performance_v1
        WHERE lijn_code = :lijn_code
        ORDER BY n_rows DESC, band_code
        LIMIT :limit
        """,
        {"lijn_code": lijn_code_norm, "limit": limit},
    )

    bands_clean = clean_band_performance_rows(bands)

    bands_position_only = [
        row for row in bands_clean
        if row.get("is_position_only")
    ]

    bands_operational = [
        row for row in bands_clean
        if not row.get("is_position_only")
    ]

    maintenance = fetch_all(
        """
        SELECT *
        FROM vw_mes_maintenance_positions_latest
        WHERE lijn_code = :lijn_code
          AND cycle_end >= CURRENT_DATE - INTERVAL '2 years'
        ORDER BY prioriteit, geschatte_vervangdatum_bij_3mm NULLS LAST
        LIMIT :limit
        """,
        {"lijn_code": lijn_code_norm, "limit": limit},
    )

    maintenance_clean = clean_maintenance_rows(maintenance)

    replacements = fetch_all(
        """
        SELECT *
        FROM vw_all_replacement_advice
        WHERE lijn_code = :lijn_code
          AND next_due_date >= CURRENT_DATE - INTERVAL '2 years'
          AND NULLIF(TRIM(COALESCE(band_norm, '')), '') IS NOT NULL
        ORDER BY
          CASE status
            WHEN 'OVERDUE' THEN 1
            WHEN 'BINNEN_2_WEKEN' THEN 2
            WHEN 'BINNEN_1_MAAND' THEN 3
            ELSE 4
          END,
          next_due_date ASC NULLS LAST
        LIMIT :limit
        """,
        {"lijn_code": lijn_code_norm, "limit": limit},
    )

    replacements_enriched = enrich_replacement_advice_rows(replacements)

    scraper_summary = fetch_all(
        """
        SELECT
            lijn_code,
            scraper_status,
            COUNT(*) AS n_banden,
            SUM(n_schrapers_aanwezig) AS totaal_schrapers_aanwezig,
            SUM(n_schrapers_actief) AS totaal_schrapers_actief
        FROM vw_band_scraper_api_v1
        WHERE lijn_code = :lijn_code
        GROUP BY lijn_code, scraper_status
        ORDER BY scraper_status
        """,
        {"lijn_code": lijn_code_norm},
    )

    excel_clean_context = get_excel_clean_scraper_context(
        lijn_code=lijn_code_norm,
        band_code=None,
        limit=limit,
    )

    return {
        "status": "ok",
        "context_type": "line_context",
        "lijn_code": lijn_code_norm,

        "location_performance": location_performance,

        "bands": bands_operational,
        "bands_position_only": bands_position_only,
        "bands_raw_count": len(bands),
        "bands_operational_count": len(bands_operational),
        "bands_position_only_count": len(bands_position_only),

        "maintenance_positions": maintenance_clean,
        "maintenance_positions_raw_count": len(maintenance),

        "replacement_advice_recent": replacements_enriched,
        "replacement_advice_recent_count": len(replacements_enriched),
        "replacement_advice_review_summary": {
            "overdue_meer_dan_1_jaar": sum(
                1 for r in replacements_enriched
                if r.get("overdue_age_bucket") == "OVERDUE_MEER_DAN_1_JAAR"
            ),
            "overdue_90_365_dagen": sum(
                1 for r in replacements_enriched
                if r.get("overdue_age_bucket") == "OVERDUE_90_365_DAGEN"
            ),
            "overdue_0_90_dagen": sum(
                1 for r in replacements_enriched
                if r.get("overdue_age_bucket") == "OVERDUE_0_90_DAGEN"
            ),
            "niet_overdue": sum(
                1 for r in replacements_enriched
                if r.get("overdue_age_bucket") == "NIET_OVERDUE"
            ),
            "needs_review": sum(
                1 for r in replacements_enriched
                if r.get("needs_review")
            ),
        },
        "replacement_advice_note": (
            "Gefilterd op next_due_date binnen de laatste 2 jaar en alleen records met band_norm. "
            "Overdue-regels worden niet onderdrukt, omdat lang laagstaande messen bewust onderzocht moeten worden."
        ),

        "scraper_summary_historisch": scraper_summary,

        "schrapers_excel_clean": excel_clean_context.get("scrapers_excel_clean", []),
        "position_accessories": excel_clean_context.get("position_accessory_names_excel_clean", []),
        "position_accessories_detail": excel_clean_context.get("position_accessories_excel_clean", []),

        "datakwaliteit": {
            "heeft_excel_clean_context": bool(excel_clean_context.get("scrapers_excel_clean") or excel_clean_context.get("position_accessories_excel_clean")),
            "gebruik_clean_context_als_leidend": True,
            "raw_band_performance_is_opgeschoond_in_output": True,
            "maintenance_gefilterd_op_laatste_2_jaar": True,
            "replacement_advice_gefilterd_op_laatste_2_jaar": True,
        },

        "write_actions_available": False,
    }


@router.get("/replacement-investigation")
def get_replacement_investigation(
    lijn_code: str = Query(...),
    band_code: str = Query(...),
    scraper_type: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
) -> dict[str, Any]:
    lijn_code_norm = normalize_code(lijn_code)
    band_code_norm = normalize_code(band_code)
    scraper_compare = normalize_scraper_for_compare(scraper_type)

    replacement_rows = fetch_all(
        """
        SELECT *
        FROM vw_all_replacement_advice
        WHERE lijn_code = :lijn_code
          AND REPLACE(UPPER(COALESCE(band_norm, '')), ' ', '') = :band_code
        ORDER BY
          CASE status
            WHEN 'OVERDUE' THEN 1
            WHEN 'BINNEN_2_WEKEN' THEN 2
            WHEN 'BINNEN_1_MAAND' THEN 3
            ELSE 4
          END,
          days_to_due ASC NULLS LAST,
          next_due_date ASC NULLS LAST
        LIMIT :limit
        """,
        {
            "lijn_code": lijn_code_norm,
            "band_code": band_code_norm,
            "limit": limit,
        },
    )

    replacement_rows = enrich_replacement_advice_rows(replacement_rows)

    if scraper_compare:
        replacement_rows = [
            row for row in replacement_rows
            if normalize_scraper_for_compare(row.get("scraper_type_norm")) == scraper_compare
               or normalize_scraper_for_compare(row.get("scraper_type_norm_raw")) == scraper_compare
        ]

    latest_mes = fetch_all(
        """
        SELECT
            lijn_code,
            band_norm,
            scraper_family,
            scraper_type_norm,
            position_hint,
            laatste_meting_datum,
            meshoogte_mm,
            commentaar
        FROM vw_meshoogte_latest_per_scraper_clean
        WHERE lijn_code = :lijn_code
          AND REPLACE(UPPER(COALESCE(band_norm, '')), ' ', '') = :band_code
        ORDER BY laatste_meting_datum DESC NULLS LAST
        LIMIT :limit
        """,
        {
            "lijn_code": lijn_code_norm,
            "band_code": band_code_norm,
            "limit": limit,
        },
    )

    latest_mes = clean_lifecycle_rows(latest_mes)

    if scraper_compare:
        latest_mes = [
            row for row in latest_mes
            if normalize_scraper_for_compare(row.get("scraper_type_norm")) == scraper_compare
               or normalize_scraper_for_compare(row.get("scraper_type_norm_raw")) == scraper_compare
        ]

    lifecycle = fetch_all(
        """
        SELECT
            lijn_code,
            band_norm,
            scraper_type_norm,
            position_hint,
            cycle_id,
            inspected_on,
            meshoogte_mm,
            replace_event,
            commentaar
        FROM vw_mes_cycle_points_v1
        WHERE lijn_code = :lijn_code
          AND REPLACE(UPPER(COALESCE(band_norm, '')), ' ', '') = :band_code
        ORDER BY inspected_on DESC NULLS LAST
        LIMIT :limit
        """,
        {
            "lijn_code": lijn_code_norm,
            "band_code": band_code_norm,
            "limit": limit,
        },
    )

    lifecycle = clean_lifecycle_rows(lifecycle)

    if scraper_compare:
        lifecycle = [
            row for row in lifecycle
            if normalize_scraper_for_compare(row.get("scraper_type_norm")) == scraper_compare
               or normalize_scraper_for_compare(row.get("scraper_type_norm_raw")) == scraper_compare
        ]

    forecast = fetch_all(
        """
        SELECT *
        FROM vw_mes_cycle_analysis_clean
        WHERE lijn_code = :lijn_code
          AND REPLACE(UPPER(COALESCE(band_norm, '')), ' ', '') = :band_code
          AND meetpunten >= 3
          AND cycle_end >= CURRENT_DATE - INTERVAL '2 years'
        ORDER BY cycle_end DESC NULLS LAST
        LIMIT :limit
        """,
        {
            "lijn_code": lijn_code_norm,
            "band_code": band_code_norm,
            "limit": limit,
        },
    )

    forecast = clean_forecast_rows(forecast)

    if scraper_compare:
        forecast = [
            row for row in forecast
            if normalize_scraper_for_compare(row.get("scraper_type_norm")) == scraper_compare
               or normalize_scraper_for_compare(row.get("scraper_type_norm_raw")) == scraper_compare
        ]

    recent_inspections = fetch_all(
        """
        SELECT
            inspection_key,
            document_date,
            line_hint,
            band_code,
            locatie_raw,
            scraper_type_raw,
            meshoogte_mm,
            mes_vervangen,
            commentaar,
            check_code,
            status,
            source_file,
            source_system
        FROM vw_fact_inspection_combined_v2
        WHERE REPLACE(UPPER(COALESCE(band_code, locatie_raw, '')), ' ', '') = :band_code
          AND (:lijn_code IS NULL OR line_hint = :lijn_code)
        ORDER BY document_date DESC NULLS LAST
        LIMIT :limit
        """,
        {
            "lijn_code": lijn_code_norm,
            "band_code": band_code_norm,
            "limit": limit,
        },
    )

    hosch_diagnose = detect_hosch_replacement_from_inspections(recent_inspections)

    recent_inspections_summary = dedupe_recent_inspections(recent_inspections)

    scraper_variants = sorted({
        row.get("scraper_type_norm")
        for row in latest_mes + lifecycle + forecast + replacement_rows
        if row.get("scraper_type_norm")
    } | {
        row.get("scraper_type_norm_raw")
        for row in latest_mes + lifecycle + forecast + replacement_rows
        if row.get("scraper_type_norm_raw")
    })

    review_findings: list[str] = []

    if replacement_rows:
        worst = replacement_rows[0]
        review_findings.append(
            f"Replacement advice status: {worst.get('status')} met days_to_due={worst.get('days_to_due')}."
        )

        if worst.get("possible_reasons"):
            review_findings.extend(worst.get("possible_reasons") or [])

    if latest_mes:
        m = latest_mes[0]
        review_findings.append(
            f"Laatste mesmeting: {m.get('meshoogte_mm')} mm op {m.get('laatste_meting_datum')}."
        )

    if forecast:
        f = forecast[0]
        review_findings.append(
            f"Laatste forecastcyclus: {f.get('cycle_start')} t/m {f.get('cycle_end')}, status_3mm={f.get('status_3mm')}."
        )

    if not replacement_rows:
        review_findings.append(
            "Geen replacement advice gevonden voor deze band/schraper-combinatie."
        )

    if not latest_mes:
        review_findings.append(
            "Geen laatste mesmeting gevonden voor deze band/schraper-combinatie."
        )

    if hosch_diagnose.get("has_hosch_signal"):
        review_findings.append(
            "Recente inspecties vermelden Hosch; deze Promati-schraper is mogelijk vervangen door een concurrent-schraper."
        )

    return {
        "status": "ok",
        "context_type": "replacement_investigation",
        "lijn_code": lijn_code_norm,
        "band_code": band_code_norm,
        "scraper_type_filter": scraper_type,
        "scraper_type_filter_norm": normalize_scraper_type_canonical(scraper_type),

        "review_findings": review_findings,

        "replacement_advice": replacement_rows,
        "latest_meshoogte": latest_mes,
        "forecast_3mm": forecast,
        "lifecycle_points": lifecycle,
        "recent_inspections": recent_inspections,
        "hosch_diagnose": hosch_diagnose,
        "replacement_advice_is_actionable": not hosch_diagnose.get("has_hosch_signal"),

        "recent_inspections": recent_inspections_summary,
        "recent_inspections_raw_count": len(recent_inspections),
        "recent_inspections_detail": recent_inspections[:25],
        "recent_inspections_detail_raw_count": len(recent_inspections),

        "scraper_variants_seen": scraper_variants,

        "diagnose": {
            "has_replacement_advice": bool(replacement_rows),
            "has_latest_meshoogte": bool(latest_mes),
            "has_forecast": bool(forecast),
            "has_lifecycle_points": bool(lifecycle),
            "has_recent_inspections": bool(recent_inspections),
            "possible_name_variant_issue": len(scraper_variants) > 1,
        },
        "write_actions_available": False,
    }


@router.get("/product/scrapers")
def get_scraper_product_context(
    slot: Optional[str] = Query(default=None),
    active_only: bool = Query(default=True),
):
    rows = fetch_all(
        """
        SELECT
            product_id,
            brand,
            model,
            position_hint,
            bidirectional_ok,
            speed_max_mps,
            temp_max_c,
            space_compact,
            active,
            notes,
            allowed_slots
        FROM scraper_product
        WHERE (:active_only = false OR active = true)
          AND (:slot IS NULL OR :slot = ANY(allowed_slots))
        ORDER BY brand, model
        """,
        {"slot": slot, "active_only": active_only},
    )

    return {
        "status": "ok",
        "context_type": "scraper_product_context",
        "slot": slot,
        "products": rows,
        "write_actions_available": False,
    }


@router.get("/system")
def get_system_context():
    return {
        "status": "ok",
        "context_type": "system_context",
        "available_contexts": [
            "/analysis/context/rfq/{rfq_id}/positions/{position_id}",
            "/analysis/context/rfq/{rfq_id}/positions/{position_id}/engineering-review",
            "/analysis/context/rfq/search",
            "/analysis/context/belt/{band_code}",
            "/analysis/context/line/{lijn_code}",
            "/analysis/context/replacement-investigation",
            "/analysis/context/product/scrapers",
            "/analysis/context/database/catalog",
            "/analysis/context/database/table/{schema}/{table}",
            "/diagnostics/overview",
        ],
        "write_actions_available": False,
    }


@router.get("/product/{product_id}/gpt-context")
def get_product_gpt_context_for_actions(product_id: int):
    """
    GPT-context voor productvragen.
    Bedoeld voor PromatiGPT Actions.
    Combineert scraper_product, scraper_product_sales en gekoppelde RAG-documenten.
    """

    product = fetch_one("""
        SELECT
            product_id,
            brand,
            model,
            position_hint,
            bidirectional_ok,
            speed_max_mps,
            temp_max_c,
            space_compact,
            active,
            notes,
            allowed_slots
        FROM scraper_product
        WHERE product_id = :product_id
        LIMIT 1
    """, {"product_id": product_id})

    if not product:
        raise HTTPException(status_code=404, detail="Product niet gevonden")

    sales = fetch_one("""
        SELECT
            product_id,
            pitch,
            pros,
            cons,
            best_for,
            objections,
            cross_sell
        FROM scraper_product_sales
        WHERE product_id = :product_id
        LIMIT 1
    """, {"product_id": product_id})

    documents = fetch_all("""
        SELECT
            pdl.doc_id,
            pdl.source_role,
            pdl.variant,
            pdl.status,
            pdl.confidence,
            d.title,
            d.filename,
            d.content_type,
            COUNT(c.chunk_id)::int AS chunk_count
        FROM product_document_link pdl
        LEFT JOIN sb_docs_v0 d
            ON d.doc_id = pdl.doc_id
        LEFT JOIN sb_doc_chunks_v0 c
            ON c.doc_id = pdl.doc_id
        WHERE pdl.product_id = :product_id
        GROUP BY
            pdl.doc_id,
            pdl.source_role,
            pdl.variant,
            pdl.status,
            pdl.confidence,
            d.title,
            d.filename,
            d.content_type
        ORDER BY pdl.variant, d.title
    """, {"product_id": product_id})

    identity = f"{product.get('brand')} {product.get('model')}".strip()

    technical_parts = []

    if product.get("position_hint"):
        technical_parts.append(f"positie/toepassing: {product['position_hint']}")

    if product.get("bidirectional_ok") is not None:
        technical_parts.append(
            "geschikt voor twee draairichtingen"
            if product["bidirectional_ok"]
            else "voor één draairichting"
        )

    if product.get("speed_max_mps") is not None:
        technical_parts.append(f"max. bandsnelheid {product['speed_max_mps']} m/s")

    if product.get("temp_max_c") is not None:
        technical_parts.append(f"max. temperatuur {product['temp_max_c']} °C")

    if product.get("notes"):
        technical_parts.append(product["notes"])

    return {
        "status": "ok",
        "context_type": "product_gpt_context",
        "product_id": product_id,
        "product_identity": identity,
        "technical_summary": ". ".join(technical_parts),
        "sales_summary": sales.get("pitch") if sales else None,
        "product": product,
        "sales_context": sales,
        "knowledge_documents": documents,
        "document_count": len(documents),
        "rag_query_hint": {
            "endpoint": "/rag/query",
            "recommended_filters": {
                "doc_ids": [
                    str(d.get("doc_id"))
                    for d in documents
                    if d.get("doc_id")
                ],
                "brand": product.get("brand"),
                "model": product.get("model"),
            },
            "instruction": (
                "Gebruik voor detailvragen eerst de gekoppelde doc_id's. "
                "Gebruik productdata voor harde limieten zoals bandsnelheid, temperatuur, draairichting en positie. "
                "Gebruik master_section alleen als aanvullende uitleg of commerciële context."
            ),
        },
        "recommended_answer_style": (
            "Antwoord kort en praktisch. Gebruik productdata voor harde limieten. "
            "Gebruik gekoppelde RAG-documenten voor detailvragen."
        ),
        "write_actions_available": False,
    }


@router.get("/generic-product/{generic_product_id}/gpt-context")
def get_generic_product_gpt_context(generic_product_id: int):
    product = fetch_one("""
        SELECT
            generic_product_id,
            brand,
            model,
            category,
            variant,
            status,
            notes,
            created_at
        FROM generic_product
        WHERE generic_product_id = :generic_product_id
        LIMIT 1
    """, {"generic_product_id": generic_product_id})

    if not product:
        raise HTTPException(status_code=404, detail="Generiek product niet gevonden")

    documents = fetch_all("""
        SELECT
            gpdl.doc_id,
            gpdl.source_role,
            gpdl.status,
            gpdl.confidence,
            d.title,
            d.filename,
            d.content_type,
            COUNT(c.chunk_id)::int AS chunk_count
        FROM generic_product_document_link gpdl
        LEFT JOIN sb_docs_v0 d
            ON d.doc_id = gpdl.doc_id
        LEFT JOIN sb_doc_chunks_v0 c
            ON c.doc_id = gpdl.doc_id
        WHERE gpdl.generic_product_id = :generic_product_id
        GROUP BY
            gpdl.doc_id,
            gpdl.source_role,
            gpdl.status,
            gpdl.confidence,
            d.title,
            d.filename,
            d.content_type
        ORDER BY d.title
    """, {"generic_product_id": generic_product_id})

    identity = f"{product.get('brand')} {product.get('model')}".strip()

    return {
        "status": "ok",
        "context_type": "generic_product_gpt_context",
        "generic_product_id": generic_product_id,
        "product_identity": identity,
        "category": product.get("category"),
        "variant": product.get("variant"),
        "product": product,
        "knowledge_documents": documents,
        "document_count": len(documents),
        "technical_summary": product.get("notes"),
        "rag_query_hint": {
            "endpoint": "/rag/query",
            "recommended_filters": {
                "doc_ids": [
                    str(d.get("doc_id"))
                    for d in documents
                    if d.get("doc_id")
                ],
                "brand": product.get("brand"),
                "model": product.get("model"),
                "category": product.get("category"),
            },
            "instruction": (
                "Gebruik voor detailvragen eerst de gekoppelde doc_id's. "
                "Vraag alleen bredere RAG-context op als het antwoord niet in deze documenten zit."
            ),
        },
        "recommended_answer_style": (
            "Antwoord kort en praktisch. Gebruik gekoppelde RAG-documenten voor details. "
            "Noem ontbrekende technische limieten expliciet als ze niet in de context staan."
        ),
        "write_actions_available": False,
    }


@router.get("/product-search")
def product_search(
    q: str = Query(..., min_length=2),
    limit: int = Query(default=20, ge=1, le=100),
):
    scraper_rows = fetch_all("""
        SELECT
            'scraper_product' AS source_table,
            product_id::bigint AS id,
            brand,
            model,
            NULL::text AS category,
            position_hint,
            active,
            notes,
            (
                COALESCE(brand,'') || ' ' ||
                COALESCE(model,'') || ' ' ||
                COALESCE(position_hint,'') || ' ' ||
                COALESCE(notes,'')
            ) AS search_text
        FROM scraper_product
        WHERE
            UPPER(COALESCE(brand,'')) LIKE UPPER(:q)
            OR UPPER(COALESCE(model,'')) LIKE UPPER(:q)
            OR UPPER(COALESCE(position_hint,'')) LIKE UPPER(:q)
            OR UPPER(COALESCE(notes,'')) LIKE UPPER(:q)
        LIMIT :limit
    """, {"q": f"%{q}%", "limit": limit})

    generic_rows = fetch_all("""
        SELECT
            'generic_product' AS source_table,
            generic_product_id::bigint AS id,
            brand,
            model,
            category,
            NULL::text AS position_hint,
            (status <> 'archived') AS active,
            notes,
            (
                COALESCE(brand,'') || ' ' ||
                COALESCE(model,'') || ' ' ||
                COALESCE(category,'') || ' ' ||
                COALESCE(variant,'') || ' ' ||
                COALESCE(notes,'')
            ) AS search_text
        FROM generic_product
        WHERE
            UPPER(COALESCE(brand,'')) LIKE UPPER(:q)
            OR UPPER(COALESCE(model,'')) LIKE UPPER(:q)
            OR UPPER(COALESCE(category,'')) LIKE UPPER(:q)
            OR UPPER(COALESCE(variant,'')) LIKE UPPER(:q)
            OR UPPER(COALESCE(notes,'')) LIKE UPPER(:q)
        LIMIT :limit
    """, {"q": f"%{q}%", "limit": limit})

    rows = scraper_rows + generic_rows

    cleaned = []
    for row in rows[:limit]:
        cleaned.append({
            "source_table": row.get("source_table"),
            "id": row.get("id"),
            "brand": row.get("brand"),
            "model": row.get("model"),
            "category": row.get("category"),
            "position_hint": row.get("position_hint"),
            "active": row.get("active"),
            "notes": row.get("notes"),
        })

    return {
        "status": "ok",
        "context_type": "product_search",
        "query": q,
        "results_count": len(cleaned),
        "results": cleaned,
        "next_step": (
            "Gebruik source_table='scraper_product' met "
            "/analysis/context/product/{id}/gpt-context. "
            "Gebruik source_table='generic_product' met "
            "/analysis/context/generic-product/{id}/gpt-context."
        ),
        "write_actions_available": False,
    }