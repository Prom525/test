from __future__ import annotations

# PROMATI_SCOPE_ANALYSIS_SERVICE_V13_1
#
# Doel:
# - canonical area/installatie-scope vertalen naar een gecontroleerde bandset;
# - alleen bestaande read-only PROMATI views gebruiken;
# - count/list/analyse/rank semantiek expliciet houden;
# - "actuele geregistreerde schraperposities" NIET gelijkstellen aan
#   een volledig governed fysiek installatie-ontwerp.

import os
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.services.scope_resolver import validate_scope_code


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:5432/promati",
)

engine: Engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)


def _fetch_all(
    sql: str,
    params: dict[str, Any],
) -> list[dict[str, Any]]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(sql),
            params,
        ).mappings().all()

    return [dict(row) for row in rows]


def _fetch_one(
    sql: str,
    params: dict[str, Any],
) -> dict[str, Any] | None:
    with engine.connect() as conn:
        row = conn.execute(
            text(sql),
            params,
        ).mappings().first()

    return dict(row) if row else None


def _detect_operation(
    question: str,
) -> str:
    q = (question or "").casefold()

    if any(
        term in q
        for term in (
            "ranglijst",
            "toplijst",
            "top list",
            "hoogste prioriteit",
            "meest dringend",
            "wat moet eerst",
            "kritiek",
            "kritische",
            "prioriteit",
        )
    ):
        return "rank"

    if any(
        term in q
        for term in (
            "analyse",
            "analyseer",
            "analyseren",
            "trend",
            "slijtage",
            "patroon",
            "historie",
            "forecast",
            "levensduur",
            "ontwikkeling",
        )
    ):
        return "analyse"

    if any(
        term in q
        for term in (
            "hoeveel",
            "aantal",
            "totaal",
            "tel ",
            "tel de",
        )
    ):
        return "count"

    if any(
        term in q
        for term in (
            "welke",
            "toon",
            "lijst",
            "overzicht",
            "wat staat",
            "wat zit",
        )
    ):
        return "list"

    return "overview"


def _detect_subject(
    question: str,
) -> str:
    q = (question or "").casefold()

    if any(
        term in q
        for term in (
            "schraperpositie",
            "schraperposities",
            "schraper positie",
            "schraper posities",
            "positie",
            "posities",
            "schraper",
            "schrapers",
        )
    ):
        return "scraper_positions"

    if any(
        term in q
        for term in (
            "banden",
            "transportbanden",
            "band ",
        )
    ):
        return "bands"

    if any(
        term in q
        for term in (
            "onderhoud",
            "prioriteit",
            "kritiek",
            "vervang",
        )
    ):
        return "maintenance"

    return "inspection_scope"


def _validated_scope(
    scope_code: str,
    scope_type: str | None = None,
) -> dict[str, Any]:
    validation = validate_scope_code(
        scope_code
    )

    if not validation.get("valid"):
        return {
            "valid": False,
            "scope": None,
        }

    scope = validation.get("scope")

    if not isinstance(scope, dict):
        return {
            "valid": False,
            "scope": None,
        }

    canonical_type = str(
        scope.get("scope_type") or ""
    ).lower()

    if (
        scope_type
        and canonical_type
        and str(scope_type).lower()
        != canonical_type
    ):
        return {
            "valid": False,
            "scope": scope,
            "reason": "scope_type_conflict",
        }

    return {
        "valid": True,
        "scope": scope,
    }


def _scope_where(
    scope: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    scope_type = str(
        scope.get("scope_type") or ""
    ).lower()

    canonical_code = str(
        scope.get("canonical_code") or ""
    ).upper()

    if scope_type == "installation":
        return (
            "a.installation_code = :scope_code",
            {"scope_code": canonical_code},
        )

    if scope_type == "area":
        return (
            "a.area_code = :scope_code",
            {"scope_code": canonical_code},
        )

    raise ValueError(
        "Unsupported canonical scope_type"
    )


# PROMATI_SCOPE_SCRAPER_FAMILY_FILTER_V1
def _normalize_scraper_family(
    value: str | None,
) -> str | None:

    normalized = str(
        value
        or ""
    ).strip().upper()

    return normalized or None


def _scraper_family_sql(
    alias: str,
    scraper_family: str | None,
    params: dict[str, Any],
) -> str:

    normalized = (
        _normalize_scraper_family(
            scraper_family
        )
    )

    if normalized is None:
        return ""

    params[
        "scraper_family"
    ] = normalized

    return (
        "AND UPPER(TRIM(COALESCE("
        + alias
        + ".scraper_family::text, ''))) "
        + "= :scraper_family"
    )


def _current_summary(
    scope: dict[str, Any],
    scraper_family: str | None = None,
) -> dict[str, Any]:
    where_sql, params = _scope_where(
        scope
    )

    family_sql = _scraper_family_sql(
        "u",
        scraper_family,
        params,
    )

    return _fetch_one(
        f"""
        WITH scope_bands AS (
            SELECT DISTINCT
                a.band_code_norm
            FROM public.vw_gpt_band_asset_context a
            WHERE {where_sql}
              AND a.band_code_norm IS NOT NULL
        )
        SELECT
            COUNT(
                DISTINCT NULLIF(
                    TRIM(u.position_key_unified::text),
                    ''
                )
            ) AS n_current_positions,
            COUNT(
                DISTINCT u.band_norm
            ) AS n_bands_with_current_positions,
            COUNT(*) AS n_current_rows,
            COUNT(*) FILTER (
                WHERE u.position_key_unified IS NULL
                   OR TRIM(
                       u.position_key_unified::text
                   ) = ''
            ) AS n_null_position_keys,
            MAX(
                u.laatste_inspectiedatum
            ) AS latest_inspection_date
        FROM public.vw_scraper_wear_latest_unified_api_v1 u
        JOIN scope_bands b
          ON UPPER(
              REGEXP_REPLACE(
                  COALESCE(u.band_norm::text, ''),
                  '[^A-Z0-9]',
                  '',
                  'g'
              )
          )
           = UPPER(
              REGEXP_REPLACE(
                  COALESCE(b.band_code_norm::text, ''),
                  '[^A-Z0-9]',
                  '',
                  'g'
              )
          )
        {family_sql}
        """,
        params,
    ) or {}


def _current_positions(
    scope: dict[str, Any],
    limit: int,
    scraper_family: str | None = None,
) -> list[dict[str, Any]]:
    where_sql, params = _scope_where(
        scope
    )

    params = dict(params)
    params["limit"] = limit

    family_sql = _scraper_family_sql(
        "u",
        scraper_family,
        params,
    )

    return _fetch_all(
        f"""
        WITH scope_bands AS (
            SELECT DISTINCT
                a.band_code_norm
            FROM public.vw_gpt_band_asset_context a
            WHERE {where_sql}
              AND a.band_code_norm IS NOT NULL
        )
        SELECT
            u.lijn_code,
            u.band_norm,
            u.position_display,
            u.position_key_unified,
            u.scraper_type_norm,
            u.scraper_family,
            u.scraper_material,
            u.scraper_variant,
            u.analyse_basis,
            u.meshoogte_mm,
            u.conditie_code,
            u.mes_interpretatie,
            u.slijtage_actie_pct,
            u.betrouwbaarheid,
            u.score_bron,
            u.laatste_vervanging_datum,
            u.dagen_sinds_vervanging,
            u.replace_event,
            u.planned_replace_signal,
            u.mechanical_or_access_signal,
            u.commentaar,
            u.laatste_inspectiedatum,
            u.inspection_key,
            u.excel_position_id
        FROM public.vw_scraper_wear_latest_unified_api_v1 u
        JOIN scope_bands b
          ON UPPER(
              REGEXP_REPLACE(
                  COALESCE(u.band_norm::text, ''),
                  '[^A-Z0-9]',
                  '',
                  'g'
              )
          )
           = UPPER(
              REGEXP_REPLACE(
                  COALESCE(b.band_code_norm::text, ''),
                  '[^A-Z0-9]',
                  '',
                  'g'
              )
          )
        {family_sql}
        ORDER BY
            u.band_norm,
            u.position_key_unified,
            u.position_display,
            u.scraper_type_norm
        LIMIT :limit
        """,
        params,
    )


def _scope_bands(
    scope: dict[str, Any],
) -> list[str]:
    where_sql, params = _scope_where(
        scope
    )

    rows = _fetch_all(
        f"""
        SELECT DISTINCT
            a.band_code_norm
        FROM public.vw_gpt_band_asset_context a
        WHERE {where_sql}
          AND a.band_code_norm IS NOT NULL
        ORDER BY a.band_code_norm
        """,
        params,
    )

    return [
        str(row["band_code_norm"])
        for row in rows
        if row.get("band_code_norm")
    ]


def _wear_evidence(
    scope: dict[str, Any],
    limit: int,
    scraper_family: str | None = None,
) -> list[dict[str, Any]]:
    where_sql, params = _scope_where(
        scope
    )

    params = dict(params)
    params["limit"] = limit

    family_sql = _scraper_family_sql(
        "w",
        scraper_family,
        params,
    )

    return _fetch_all(
        f"""
        WITH scope_bands AS (
            SELECT DISTINCT
                a.band_code_norm
            FROM public.vw_gpt_band_asset_context a
            WHERE {where_sql}
              AND a.band_code_norm IS NOT NULL
        )
        SELECT
            w.lijn_code,
            w.band_norm,
            w.scraper_family,
            w.scraper_type_norm,
            w.scraper_role,
            w.physical_position_label_final,
            w.physical_position_source,
            w.laatste_meting_datum,
            w.actuele_meshoogte_mm,
            w.avg_slijtage_mm_per_dag,
            w.max_slijtage_mm_per_dag,
            w.vroege_slijtage_mm_per_dag,
            w.recente_slijtage_mm_per_dag,
            w.slijtage_curve_status,
            w.planning_prioriteit_historisch,
            w.onderhoudsadvies,
            w.inspectie_actualiteit,
            w.data_quality_flag,
            w.laatste_commentaar
        FROM public.vw_mes_band_position_wear_summary w
        JOIN scope_bands b
          ON UPPER(
              REGEXP_REPLACE(
                  COALESCE(w.band_norm::text, ''),
                  '[^A-Z0-9]',
                  '',
                  'g'
              )
          )
           = UPPER(
              REGEXP_REPLACE(
                  COALESCE(b.band_code_norm::text, ''),
                  '[^A-Z0-9]',
                  '',
                  'g'
              )
          )
        {family_sql}
        ORDER BY
            CASE w.inspectie_actualiteit
                WHEN 'LAATSTE_METING_RECENT'
                    THEN 1
                WHEN 'LAATSTE_METING_OUDER_DAN_1_JAAR'
                    THEN 2
                WHEN 'LAATSTE_METING_OUDER_DAN_2_JAAR'
                    THEN 3
                ELSE 4
            END,
            w.planning_prioriteit_historisch
                NULLS LAST,
            w.laatste_meting_datum
                DESC NULLS LAST,
            w.band_norm,
            w.scraper_role,
            w.physical_position_label_final
        LIMIT :limit
        """,
        params,
    )


def _maintenance_ranking(
    scope: dict[str, Any],
    limit: int,
    scraper_family: str | None = None,
) -> list[dict[str, Any]]:
    where_sql, params = _scope_where(
        scope
    )

    params = dict(params)
    params["limit"] = limit

    family_sql = _scraper_family_sql(
        "m",
        scraper_family,
        params,
    )

    return _fetch_all(
        f"""
        WITH scope_bands AS (
            SELECT DISTINCT
                a.band_code_norm
            FROM public.vw_gpt_band_asset_context a
            WHERE {where_sql}
              AND a.band_code_norm IS NOT NULL
        )
        SELECT
            m.planning_prioriteit_historisch,
            m.onderhoudsadvies,
            m.inspectie_actualiteit,
            m.data_quality_flag,
            m.lijn_code,
            m.band_norm,
            m.scraper_family,
            m.scraper_type_norm,
            m.scraper_role,
            m.physical_position_label_final,
            m.position_display,
            m.laatste_meting_datum,
            m.actuele_meshoogte_mm,
            m.analyse_meetpunten,
            m.bruikbare_intervallen,
            m.gewogen_slijtage_mm_per_dag,
            m.forecast_status,
            m.planning_status_6mm_historisch,
            m.dagen_tot_6mm_historisch,
            m.geschatte_vervangdatum_bij_6mm_historisch,
            m.planning_status_3mm_historisch,
            m.dagen_tot_3mm_historisch,
            m.geschatte_vervangdatum_bij_3mm_historisch
        FROM public.vw_mes_maintenance_toplist_historical m
        JOIN scope_bands b
          ON UPPER(
              REGEXP_REPLACE(
                  COALESCE(m.band_norm::text, ''),
                  '[^A-Z0-9]',
                  '',
                  'g'
              )
          )
           = UPPER(
              REGEXP_REPLACE(
                  COALESCE(b.band_code_norm::text, ''),
                  '[^A-Z0-9]',
                  '',
                  'g'
              )
          )
        {family_sql}
        ORDER BY
            m.planning_prioriteit_historisch,
            CASE m.inspectie_actualiteit
                WHEN 'LAATSTE_METING_RECENT'
                    THEN 1
                WHEN 'LAATSTE_METING_OUDER_DAN_1_JAAR'
                    THEN 2
                WHEN 'LAATSTE_METING_OUDER_DAN_2_JAAR'
                    THEN 3
                ELSE 4
            END,
            m.geschatte_vervangdatum_bij_3mm_historisch
                NULLS LAST,
            m.geschatte_vervangdatum_bij_6mm_historisch
                NULLS LAST,
            m.band_norm
        LIMIT :limit
        """,
        params,
    )


def analyze_scope_question(
    *,
    question: str,
    scope_code: str,
    scope_type: str | None = None,

    # PROMATI_SCOPE_SCRAPER_FAMILY_FILTER_V1
    scraper_family: str | None = None,

    limit: int = 50,
) -> dict[str, Any]:
    validation = _validated_scope(
        scope_code,
        scope_type=scope_type,
    )

    if not validation.get("valid"):
        return {
            "status": "clarification_required",
            "context_type": "analysis_scope",
            "message": (
                "De opgegeven PROMATI-scope kon niet "
                "canoniek worden gevalideerd."
            ),
            "scope_validation": validation,
            "write_actions_available": False,
        }

    scope = validation["scope"]

    normalized_scraper_family = (
        _normalize_scraper_family(
            scraper_family
        )
    )

    operation = _detect_operation(question)
    subject = _detect_subject(question)

    bounded_limit = max(
        1,
        min(int(limit or 50), 100),
    )

    summary = _current_summary(
        scope,
        scraper_family=(
            normalized_scraper_family
        ),
    )
    bands = _scope_bands(scope)
    current_positions = _current_positions(
        scope,
        bounded_limit,
        scraper_family=(
            normalized_scraper_family
        ),
    )

    n_positions = int(
        summary.get("n_current_positions") or 0
    )
    n_current_bands = int(
        summary.get(
            "n_bands_with_current_positions"
        ) or 0
    )

    wear_evidence: list[dict[str, Any]] = []
    maintenance_ranking: list[dict[str, Any]] = []

    # PROMATI_SCOPE_SUBJECT_AWARE_OUTPUT_V13_1
    result_items: list[dict[str, Any]] = (
        current_positions
    )

    if operation == "analyse":
        wear_evidence = _wear_evidence(
            scope,
            bounded_limit,
            scraper_family=(
                normalized_scraper_family
            ),
        )

    if operation == "rank":
        maintenance_ranking = _maintenance_ranking(
            scope,
            bounded_limit,
            scraper_family=(
                normalized_scraper_family
            ),
        )

    canonical_name = (
        scope.get("canonical_name")
        or scope.get("canonical_code")
    )

    if operation == "count":
        if subject == "bands":
            count = len(bands)
            count_semantics = (
                "canonical_bands_in_scope"
            )
            result_items = [
                {"band_code": band}
                for band in bands
            ]
            short = (
                f"{canonical_name}: "
                f"{count} canonieke banden "
                "in de huidige assetcatalogus."
            )
        else:
            count = n_positions
            count_semantics = (
                "current_registered_scraper_positions"
            )
            short = (
                f"{canonical_name}: "
                f"{count} actuele geregistreerde "
                "schraperposities in de unified "
                "inspectiesnapshot."
            )
    elif (
        operation == "list"
        and subject == "bands"
    ):
        count = len(bands)
        count_semantics = (
            "canonical_bands_in_scope"
        )
        result_items = [
            {"band_code": band}
            for band in bands
        ]
        band_text = ", ".join(bands)
        short = (
            f"{canonical_name}: "
            f"{count} canonieke banden "
            "in de huidige assetcatalogus"
            + (
                f": {band_text}."
                if band_text
                else "."
            )
        )
    elif operation == "rank":
        count = len(maintenance_ranking)
        count_semantics = (
            "historical_maintenance_ranking_rows"
        )
        short = (
            f"{canonical_name}: "
            f"{count} onderhoudsregels in de "
            "scope-ranglijst gevonden."
        )
    elif operation == "analyse":
        count = len(wear_evidence)
        count_semantics = (
            "wear_evidence_rows"
        )
        short = (
            f"{canonical_name}: "
            f"{n_positions} actuele geregistreerde "
            "schraperposities en "
            f"{len(wear_evidence)} "
            "slijtage-evidentieregels beschikbaar."
        )
    else:
        count = n_positions
        count_semantics = (
            "current_registered_scraper_positions"
        )
        short = (
            f"{canonical_name}: "
            f"{n_positions} actuele geregistreerde "
            "schraperposities over "
            f"{n_current_bands} banden."
        )

    if normalized_scraper_family:
        short = (
            short.rstrip(".")
            + " Filter: scraperfamilie "
            + normalized_scraper_family
            + "."
        )

    return {
        "status": "ok",
        "context_type": "analysis_scope",
        "intent": "scope_analysis",
        "operation": operation,
        "subject": subject,
        "scope": scope,

        # PROMATI_SCOPE_SCRAPER_FAMILY_FILTER_V1
        "filters": (
            {
                "scraper_family":
                    normalized_scraper_family
            }
            if normalized_scraper_family
            else {}
        ),

        "entities": {
            "scope_code": scope.get(
                "canonical_code"
            ),
            "scope_type": scope.get(
                "scope_type"
            ),
            "area_code": scope.get(
                "area_code"
            ),
            "installation_code": scope.get(
                "installation_code"
            ),
        },
        "count": count,
        "count_semantics": count_semantics,
        "kort_resultaat": short,
        "samenvatting": {
            "n_current_registered_positions": (
                n_positions
            ),
            "n_bands_with_current_positions": (
                n_current_bands
            ),
            "n_canonical_bands": len(bands),
            "latest_inspection_date": (
                summary.get(
                    "latest_inspection_date"
                )
            ),
            "n_null_position_keys": int(
                summary.get(
                    "n_null_position_keys"
                ) or 0
            ),
        },
        "bands": bands,
        "resultaat": result_items,
        "wear_evidence": wear_evidence,
        "maintenance_ranking": (
            maintenance_ranking
        ),
        "data_quality": {
            "position_source": (
                "vw_scraper_wear_latest_unified_api_v1"
            ),
            "position_identity": (
                "position_key_unified"
            ),
            "physical_design_catalog_complete": False,
            "semantic_note": (
                "Het positie-aantal betekent actuele "
                "geregistreerde operationele "
                "schraperposities in de unified "
                "inspectiesnapshot. Het is niet zonder "
                "meer gelijk aan het volledige fysieke "
                "ontwerp-aantal van de installatie."
            ),
        },
        "write_actions_available": False,
    }