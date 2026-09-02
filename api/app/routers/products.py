from __future__ import annotations

import os
import json
import re
from typing import Any, Optional

from fastapi import APIRouter, Query, HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from ..text_encoding import repair_mojibake_data

router = APIRouter(prefix="/products", tags=["products"])


def _get_engine() -> Engine:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL ontbreekt")
    return create_engine(db_url, pool_pre_ping=True)


ENGINE = _get_engine()


def _rows_to_dicts(result) -> list[dict[str, Any]]:
    cols = list(result.keys())
    return [repair_mojibake_data(dict(zip(cols, row))) for row in result.fetchall()]


@router.get("")
def list_products(
    slot: Optional[str] = Query(default=None, description="Filter op allowed slot: primary, secondary, tertiary"),
    active_only: bool = Query(default=True),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    """
    Productlijst uit scraper_product.
    Filter optioneel op slot via allowed_slots.
    """
    if slot:
        sql = text("""
            select
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
            from scraper_product
            where (:active_only = false or active = true)
              and :slot = any(allowed_slots)
            order by brand, model
            limit :limit offset :offset
        """)
        params = {
            "slot": slot,
            "active_only": active_only,
            "limit": limit,
            "offset": offset,
        }
    else:
        sql = text("""
            select
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
            from scraper_product
            where (:active_only = false or active = true)
            order by brand, model
            limit :limit offset :offset
        """)
        params = {
            "active_only": active_only,
            "limit": limit,
            "offset": offset,
        }

    with ENGINE.begin() as conn:
        rows = conn.execute(sql, params)

    return _rows_to_dicts(rows)


@router.get("/slots")
def list_slots():
    """
    Laat alle unieke allowed slots zien die in scraper_product voorkomen.
    Handig om te controleren welke filters geldig zijn.
    """
    sql = text("""
        select distinct unnest(allowed_slots)::text as slot
        from scraper_product
        where allowed_slots is not null
        order by slot
    """)

    with ENGINE.begin() as conn:
        rows = conn.execute(sql)

    return _rows_to_dicts(rows)


# ---------------------------------------------------------------------------
# Odoo / GPT product-configurator endpoints
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Product search V2 helpers
# ---------------------------------------------------------------------------

_PRODUCT_SEARCH_V2_FAMILIES = {
    "belle banne u": ("Belle Banne U", "BB-U"),
    "belle banne h": ("Belle Banne H", "BB-H"),
    "belle banne p": ("Belle Banne P", "BB-P"),
    "belle banne r": ("Belle Banne R", "BB-R"),
    "belle banne a": ("Belle Banne A", "BB-A"),
    "promati kf": ("Promati KF", "PROM-KF"),
    "promati ks": ("Promati KS", "PROM-KS"),
    "tph hd": ("Promati TPH HD", "PROM-TPH-HD"),
    "tph nd": ("Promati TPH ND", "PROM-TPH-ND"),
    "clean scrape": ("CleanScrape", "CLEAN-SCRAPE"),
    "cleanscrape": ("CleanScrape", "CLEAN-SCRAPE"),
}


_PRODUCT_SEARCH_V2_WIDTHS = {
    400, 500, 600, 650, 750, 800, 900,
    1000, 1200, 1400, 1500, 1600,
    1800, 2000, 2200, 2400, 2600,
    2800, 3200,
}


def _search_v2_consume(
    value: str,
    pattern: str,
) -> str:
    return re.sub(
        pattern,
        " ",
        value,
        flags=re.IGNORECASE,
    )


def _parse_product_search_v2(q: str) -> dict[str, Any]:
    """
    Parse productzoektekst naar gestructureerde V2-intent.
    """

    original = q.strip()
    work = original.lower()

    family_name = None
    family_code = None

    for phrase, values in _PRODUCT_SEARCH_V2_FAMILIES.items():
        if phrase in work:
            family_name, family_code = values
            work = work.replace(phrase, " ")
            break

    requirements: list[dict[str, str]] = []

    def add_requirement(
        option_type: str,
        option_value: str,
    ) -> None:
        item = {
            "type": option_type,
            "value": option_value,
        }

        if item not in requirements:
            requirements.append(item)

    # -------------------------------------------------------
    # Material: specifieke RVS-grade vóór generiek RVS
    # -------------------------------------------------------

    if re.search(
        r"\b(?:rvs|inox|stainless)[ _-]*316\b",
        work,
    ):
        add_requirement("material", "RVS 316")

        work = _search_v2_consume(
            work,
            r"\b(?:rvs|inox|stainless)[ _-]*316\b",
        )

    elif re.search(
        r"\b(?:rvs|inox|stainless)[ _-]*304\b",
        work,
    ):
        add_requirement("material", "RVS 304")

        work = _search_v2_consume(
            work,
            r"\b(?:rvs|inox|stainless)[ _-]*304\b",
        )

    elif re.search(
        r"\b(?:rvs|inox|stainless)\b",
        work,
    ):
        add_requirement("material", "RVS")

        work = _search_v2_consume(
            work,
            r"\b(?:rvs|inox|stainless)\b",
        )

    # -------------------------------------------------------
    # Compliance
    # -------------------------------------------------------

    if re.search(
        r"\bfood(?:[ _-]?grade)?\b|"
        r"\bvoeding(?:sgeschikt)?\b|"
        r"\bvoedingsgeschikt\b",
        work,
    ):
        add_requirement(
            "compliance_grade",
            "food_grade",
        )

        work = _search_v2_consume(
            work,
            r"\bfood(?:[ _-]?grade)?\b|"
            r"\bvoeding(?:sgeschikt)?\b|"
            r"\bvoedingsgeschikt\b",
        )

    # -------------------------------------------------------
    # Service life
    # -------------------------------------------------------

    if re.search(
        r"\blong[ _-]?life\b",
        work,
    ):
        add_requirement(
            "service_life_grade",
            "long_life",
        )

        work = _search_v2_consume(
            work,
            r"\blong[ _-]?life\b",
        )

    # -------------------------------------------------------
    # Temperature
    # -------------------------------------------------------

    if re.search(
        r"\bhoge[ _-]?temp(?:eratuur)?\b|"
        r"\bhigh[ _-]?temp(?:erature)?\b|"
        r"\bheat[ _-]?resistant\b|"
        r"\bht\b",
        work,
    ):
        add_requirement(
            "temperature_grade",
            "HT",
        )

        work = _search_v2_consume(
            work,
            r"\bhoge[ _-]?temp(?:eratuur)?\b|"
            r"\bhigh[ _-]?temp(?:erature)?\b|"
            r"\bheat[ _-]?resistant\b|"
            r"\bht\b",
        )

    # -------------------------------------------------------
    # Blade execution
    # -------------------------------------------------------

    if re.search(
        r"\bpur?\b|\bpolyurethaan\b",
        work,
    ):
        add_requirement(
            "blade_execution",
            "PUR",
        )

        work = _search_v2_consume(
            work,
            r"\bpur?\b|\bpolyurethaan\b",
        )

    if re.search(
        r"\balumina\b",
        work,
    ):
        add_requirement(
            "blade_execution",
            "ALUMINA",
        )

        work = _search_v2_consume(
            work,
            r"\balumina\b",
        )

    if re.search(
        r"\bm3\b",
        work,
    ):
        add_requirement(
            "blade_execution",
            "M3",
        )

        work = _search_v2_consume(
            work,
            r"\bm3\b",
        )

    # -------------------------------------------------------
    # Execution
    # -------------------------------------------------------

    if re.search(
        r"\bcompact\b",
        work,
    ):
        add_requirement(
            "execution",
            "compact",
        )

        work = _search_v2_consume(
            work,
            r"\bcompact\b",
        )

    # -------------------------------------------------------
    # Width / secondary dimension
    # -------------------------------------------------------

    hard_width = None
    soft_dimension = None

    # Expliciete bandbreedte = hard
    match = re.search(
        r"\bbandbreedte\s*(\d{3,4})\b",
        work,
    )

    if match:
        width = int(match.group(1))

        if width in _PRODUCT_SEARCH_V2_WIDTHS:
            hard_width = width

        work = _search_v2_consume(
            work,
            r"\bbandbreedte\s*\d{3,4}\b",
        )

    # Bijvoorbeeld 800-750:
    # eerste getal hard, tweede soft
    if hard_width is None:
        match = re.search(
            r"\b(\d{3,4})\s*[-/]\s*(\d{3,4})\b",
            work,
        )

        if match:
            first = int(match.group(1))
            second = int(match.group(2))

            if first in _PRODUCT_SEARCH_V2_WIDTHS:
                hard_width = first

            soft_dimension = str(second)

            work = _search_v2_consume(
                work,
                r"\b\d{3,4}\s*[-/]\s*\d{3,4}\b",
            )

    # Eén los getal:
    # TPH = soft dimension; overige families = hard width
    if hard_width is None:
        numbers = re.findall(
            r"\b\d{3,4}\b",
            work,
        )

        if len(numbers) == 1:
            number_text = numbers[0]
            number = int(number_text)

            if number in _PRODUCT_SEARCH_V2_WIDTHS:
                if family_code in {
                    "PROM-TPH-HD",
                    "PROM-TPH-ND",
                }:
                    soft_dimension = str(number)
                else:
                    hard_width = number

            work = _search_v2_consume(
                work,
                rf"\b{re.escape(number_text)}\b",
            )

    # -------------------------------------------------------
    # Alleen resterende inhoudstermen
    # -------------------------------------------------------

    tokens = re.findall(
        r"[a-z0-9]+",
        work.lower(),
    )

    stop_words = {
        "mm",
        "voor",
        "met",
        "van",
        "het",
        "een",
        "type",
    }

    residual_terms = [
        token
        for token in tokens
        if len(token) >= 3
        and token not in stop_words
    ]

    has_pur = any(
        requirement["type"] == "blade_execution"
        and requirement["value"] == "PUR"
        for requirement in requirements
    )

    has_pur_specialization = any(
        requirement["type"]
        in {
            "compliance_grade",
            "service_life_grade",
            "temperature_grade",
        }
        for requirement in requirements
    )

    generic_pur = (
        has_pur
        and not has_pur_specialization
    )

    return {
        "query": original,
        "detected_family": family_name,
        "detected_family_code": family_code,
        "hard_width": hard_width,
        "soft_dimension": soft_dimension,
        "requirements": requirements,
        "residual_terms": residual_terms,
        "generic_pur": generic_pur,
    }

@router.get("/search")
def search_product_context(
    q: str = Query(..., min_length=2, description="Zoektekst, bv. 'Belle Banne U 800 frame RVS'"),
    limit: int = Query(default=25, ge=1, le=100),
):
    """
    Zoekt in vw_gpt_product_search.
    Familie-bewust zoeken voor GPT-productvragen.
    """

    q_clean = q.strip()
    q_lower = q_clean.lower()

    known_families = {
        "belle banne u": "Belle Banne U",
        "belle banne h": "Belle Banne H",
        "belle banne p": "Belle Banne P",
        "belle banne r": "Belle Banne R",
        "belle banne a": "Belle Banne A",
        "promati kf": "Promati KF",
        "promati ks": "Promati KS",
        "tph hd": "Promati TPH HD",
        "tph nd": "Promati TPH ND",
        "clean scrape": "CleanScrape",
        "cleanscrape": "CleanScrape",
    }

    detected_family = None
    for key, value in known_families.items():
        if key in q_lower:
            detected_family = value
            break

    width_match = re.search(
        r"\b(400|500|600|650|750|800|900|1000|1200|1400|1500|1600|1800|2000|2200|2400|2600|2800|3200)\b",
        q_lower,
    )
    detected_width = int(width_match.group(1)) if width_match else None

    detected_option = None
    if "rvs" in q_lower or "inox" in q_lower or "stainless" in q_lower:
        detected_option = "RVS"
    elif "pu" in q_lower or "polyurethaan" in q_lower:
        detected_option = "PU"
    elif "food" in q_lower or "voeding" in q_lower:
        detected_option = "food_grade"
    elif "long life" in q_lower or "longlife" in q_lower:
        detected_option = "long_life"

    terms = [t.strip() for t in q_lower.split() if len(t.strip()) >= 3]

    sql = text("""
        select
            family_name,
            family_code,
            brand,
            internal_ref,
            product_name,
            article_role,
            component_type,
            option_type,
            option_value,
            belt_width_mm,
            sale_price,
            available_qty,
            product_category,
            (
                case when :family_name is not null and family_name = :family_name then 100 else 0 end +
                case when :belt_width_mm is not null and belt_width_mm = :belt_width_mm then 50 else 0 end +
                case when :option_value is not null and option_value = :option_value then 30 else 0 end +
                case when search_text ilike '%' || :q || '%' then 20 else 0 end
            ) as match_score
        from vw_gpt_product_search
        where (:family_name is null or family_name = :family_name)
          and (:belt_width_mm is null or belt_width_mm = :belt_width_mm)
          and (:option_value is null or option_value = :option_value)
          and (
              :term_count = 0
              or search_text ilike any (
                  select '%' || value || '%'
                  from jsonb_array_elements_text(cast(:terms as jsonb))
              )
          )
        order by match_score desc, family_name, belt_width_mm, component_type, internal_ref
        limit :limit
    """)

    params = {
        "q": q_clean,
        "family_name": detected_family,
        "belt_width_mm": detected_width,
        "option_value": detected_option,
        "terms": json.dumps(terms),
        "term_count": len(terms),
        "limit": limit,
    }

    with ENGINE.begin() as conn:
        rows = conn.execute(sql, params).mappings().all()

    return {
        "status": "ok",
        "context_type": "product_search",
        "query": q,
        "detected_family": detected_family,
        "detected_width": detected_width,
        "detected_option": detected_option,
        "count": len(rows),
        "results": [repair_mojibake_data(dict(r)) for r in rows],
        "write_actions_available": False,
    }


@router.get("/search-v2")
def search_product_context_v2(
    q: str = Query(
        ...,
        min_length=2,
        description=(
            "V2 productzoektekst met multi-option ondersteuning, "
            "bv. 'TPH HD 800-750 PUR RVS'"
        ),
    ),
    limit: int = Query(
        default=25,
        ge=1,
        le=100,
    ),
):
    """
    Parallelle V2-productzoeking via vw_gpt_product_search_v2.
    Bestaande /products/search blijft ongewijzigd.
    """

    parsed = _parse_product_search_v2(q)

    requirements = parsed["requirements"]
    residual_terms = parsed["residual_terms"]

    sql = text("""
        WITH base AS (
            SELECT
                v.*,

                NOT EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(
                        CAST(:requirements AS jsonb)
                    ) req

                    WHERE NOT (
                        CASE
                            WHEN req->>'type' = 'material'
                             AND req->>'value' = 'RVS'
                            THEN EXISTS (
                                SELECT 1
                                FROM jsonb_array_elements_text(
                                    COALESCE(
                                        v.options -> 'material',
                                        '[]'::jsonb
                                    )
                                ) x(value)

                                WHERE x.value = 'RVS'
                                   OR x.value LIKE 'RVS %'
                            )

                            ELSE EXISTS (
                                SELECT 1
                                FROM jsonb_array_elements_text(
                                    COALESCE(
                                        v.options -> (req->>'type'),
                                        '[]'::jsonb
                                    )
                                ) x(value)

                                WHERE x.value = req->>'value'
                            )
                        END
                    )
                ) AS all_options_match,

                NOT EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements_text(
                        CAST(:residual_terms AS jsonb)
                    ) t(value)

                    WHERE v.search_text NOT ILIKE
                        '%' || t.value || '%'
                ) AS all_residual_terms_match

            FROM vw_gpt_product_search_v2 v
        ),

        eligible AS (
            SELECT
                *,

                CASE
                    WHEN :generic_pur
                     AND NOT (
                            options ? 'compliance_grade'
                         OR options ? 'service_life_grade'
                         OR options ? 'temperature_grade'
                     )
                    THEN 15
                    ELSE 0
                END AS plain_pur_bonus,

                CASE
                    WHEN :soft_dimension IS NOT NULL
                     AND search_text ILIKE
                         '%' || :soft_dimension || '%'
                    THEN 20
                    ELSE 0
                END AS soft_dimension_bonus

            FROM base

            WHERE
                (
                    :family_code IS NULL
                    OR family_code = :family_code
                )

              AND (
                    :hard_width IS NULL
                    OR belt_width_mm = :hard_width
              )

              AND all_options_match
              AND all_residual_terms_match
        )

        SELECT
            stg_article_id,
            family_name,
            family_code,
            brand,
            internal_ref,
            product_name,
            article_role,
            component_type,
            option_type,
            option_value,
            belt_width_mm,
            sale_price,
            available_qty,
            expected_qty,
            uom,
            product_category,

            options,
            option_facts,

            exposed_fact_count,
            validated_fact_count,
            candidate_fact_count,
            option_type_count,
            review_count,
            has_review,

            plain_pur_bonus,
            soft_dimension_bonus,

            (
                CASE
                    WHEN :family_code IS NOT NULL
                    THEN 100
                    ELSE 0
                END
                +
                CASE
                    WHEN :hard_width IS NOT NULL
                    THEN 50
                    ELSE 0
                END
                +
                (:requirement_count * 40)
                +
                plain_pur_bonus
                +
                soft_dimension_bonus
                +
                CASE
                    WHEN :residual_count > 0
                    THEN 10
                    ELSE 0
                END
            ) AS match_score

        FROM eligible

        ORDER BY
            match_score DESC,

            CASE article_role
                WHEN 'complete_system' THEN 1
                WHEN 'assembly' THEN 2
                WHEN 'component' THEN 3
                WHEN 'wear_part' THEN 4
                ELSE 5
            END,

            belt_width_mm NULLS LAST,
            internal_ref

        LIMIT :limit
    """)

    params = {
        "family_code":
            parsed["detected_family_code"],

        "hard_width":
            parsed["hard_width"],

        "soft_dimension":
            parsed["soft_dimension"],

        "requirements":
            json.dumps(requirements),

        "requirement_count":
            len(requirements),

        "residual_terms":
            json.dumps(residual_terms),

        "residual_count":
            len(residual_terms),

        "generic_pur":
            parsed["generic_pur"],

        "limit":
            limit,
    }

    with ENGINE.begin() as conn:
        rows = conn.execute(
            sql,
            params,
        ).mappings().all()

    return {
        "status": "ok",
        "context_type": "product_search_v2",
        "query": q,

        "detected_family":
            parsed["detected_family"],

        "detected_family_code":
            parsed["detected_family_code"],

        "hard_width":
            parsed["hard_width"],

        "soft_dimension":
            parsed["soft_dimension"],

        "requirements":
            requirements,

        "residual_terms":
            residual_terms,

        "generic_pur":
            parsed["generic_pur"],

        "count":
            len(rows),

        "results":
            [repair_mojibake_data(dict(row)) for row in rows],

        "source_view":
            "vw_gpt_product_search_v2",

        "write_actions_available":
            False,
    }

@router.get("/family-context")
def get_product_family_context(
    family_name: Optional[str] = Query(default=None, description="Productfamilie, bijvoorbeeld Belle Banne U"),
    family_code: Optional[str] = Query(default=None, description="Productfamiliecode, bijvoorbeeld BB-U"),
    q: Optional[str] = Query(default=None, description="Vrije zoektekst, bijvoorbeeld 'U schraper voordelen'"),
    limit: int = Query(default=25, ge=1, le=100),
):
    """
    Productfamilie-context: toepassing, voordelen, beperkingen en selectieadvies.
    Gebruikt vw_gpt_product_family_context.
    """

    detected_family_code = family_code
    q_lower = (q or "").lower()

    family_aliases = {
        "belle banne u": "BB-U",
        "u schraper": "BB-U",
        "u-schraper": "BB-U",
        "belle banne h": "BB-H",
        "h schraper": "BB-H",
        "h-schraper": "BB-H",
        "belle banne p": "BB-P",
        "p schraper": "BB-P",
        "p-schraper": "BB-P",
        "belle banne r": "BB-R",
        "r schraper": "BB-R",
        "r-schraper": "BB-R",
        "promati kf": "PROM-KF",
        "kf schraper": "PROM-KF",
        "promati ks": "PROM-KS",
        "ks schraper": "PROM-KS",
        "tph hd": "PROM-TPH-HD",
        "tph nd": "PROM-TPH-ND",
    }

    if not detected_family_code and q:
        for alias, code in family_aliases.items():
            if alias in q_lower:
                detected_family_code = code
                break

    # Als familie herkend is, zoeken we direct op familie.
    # Anders zoeken we op losse termen.
    terms = []
    if q and not detected_family_code:
        terms = [t.strip() for t in q_lower.split() if len(t.strip()) >= 3]

    sql = text("""
        select
            family_name,
            family_code,
            brand,
            main_category,
            position_hint,
            product_type,
            scraper_position,
            short_description,
            application_profile,
            strengths,
            limitations,
            selection_advice,
            maintenance_notes,
            speed_max_mps,
            temp_max_c,
            bidirectional_ok,
            source_note,
            updated_at
        from vw_gpt_product_family_context
        where (:family_name is null or family_name = :family_name)
          and (:family_code is null or family_code = :family_code)
          and (
              :term_count = 0
              or concat_ws(' ',
                    family_name,
                    family_code,
                    brand,
                    product_type,
                    scraper_position,
                    short_description,
                    application_profile,
                    strengths,
                    limitations,
                    selection_advice,
                    maintenance_notes
                 ) ilike any (
                    select '%' || value || '%'
                    from jsonb_array_elements_text(cast(:terms as jsonb))
                 )
          )
        order by family_name
        limit :limit
    """)

    params = {
        "family_name": family_name,
        "family_code": detected_family_code,
        "terms": json.dumps(terms),
        "term_count": len(terms),
        "limit": limit,
    }

    with ENGINE.begin() as conn:
        rows = conn.execute(sql, params).mappings().all()

    selection_terms = [
        "kies",
        "kiezen",
        "keuze",
        "verschil",
        "vergelijk",
        "welke schraper",
        "carryback",
        "beperkte inbouwruimte",
        "inbouwruimte",
        "reverserend",
        "bidirectioneel",
        "primair",
        "secundair",
    ]

    include_selection_matrix = bool(
        q and any(term in q_lower for term in selection_terms)
    )

    selection_rows = []

    if include_selection_matrix:
        matrix_sql = text("""
            select
                family_code,
                family_name,
                brand,
                scraper_position,
                position_hint,
                selection_class,
                bidirectional_ok,
                speed_max_mps,
                temp_max_c,
                best_for,
                avoid_when,
                compare_to,
                short_description,
                selection_advice
            from vw_gpt_belt_cleaner_selection_matrix
            order by
                case
                    when scraper_position = 'primary' then 1
                    when scraper_position = 'secondary' then 2
                    else 9
                end,
                selection_class,
                family_code
        """)

        with ENGINE.begin() as conn:
            selection_rows = conn.execute(matrix_sql).mappings().all()

    return {
        "status": "ok",
        "context_type": "product_family_context",
        "query": q,
        "detected_family_code": detected_family_code,
        "count": len(rows),
        "results": [repair_mojibake_data(dict(r)) for r in rows],
        "selection_matrix_included": include_selection_matrix,
        "selection_matrix": [dict(r) for r in selection_rows],
        "write_actions_available": False,
    }


@router.get("/belt-cleaners/config/summary")
def belt_cleaner_config_summary(
    family_name: Optional[str] = Query(default=None),
    family_code: Optional[str] = Query(default=None),
    belt_width_mm: Optional[int] = Query(default=None),
):
    """
    Samenvatting per componentgroep.
    Gebruikt vw_gpt_belt_cleaner_config_summary.
    """
    sql = text("""
        select
            family_name,
            family_code,
            belt_width_mm,
            component_group,
            article_count,
            available_options,
            min_sale_price,
            max_sale_price
        from vw_gpt_belt_cleaner_config_summary
        where (:family_name is null or family_name = :family_name)
          and (:family_code is null or family_code = :family_code)
          and (:belt_width_mm is null or belt_width_mm = :belt_width_mm)
        order by family_name, belt_width_mm, component_group
    """)

    params = {
        "family_name": family_name,
        "family_code": family_code,
        "belt_width_mm": belt_width_mm,
    }

    with ENGINE.begin() as conn:
        rows = conn.execute(sql, params).mappings().all()

    return {
        "status": "ok",
        "context_type": "belt_cleaner_config_summary",
        "count": len(rows),
        "results": [repair_mojibake_data(dict(r)) for r in rows],
        "write_actions_available": False,
    }


@router.get("/belt-cleaners/config/options")
def belt_cleaner_config_options(
    family_name: Optional[str] = Query(default=None),
    family_code: Optional[str] = Query(default=None),
    belt_width_mm: Optional[int] = Query(default=None),
    component_group: Optional[str] = Query(default=None),
    option_value: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
):
    """
    Detailartikelen voor bandschraperconfiguratie.
    Gebruikt vw_gpt_belt_cleaner_config_options.
    """
    sql = text("""
        select
            family_name,
            family_code,
            belt_width_mm,
            component_group,
            option_value,
            internal_ref,
            product_name,
            sale_price,
            available_qty,
            expected_qty,
            uom
        from vw_gpt_belt_cleaner_config_options
        where (:family_name is null or family_name = :family_name)
          and (:family_code is null or family_code = :family_code)
          and (:belt_width_mm is null or belt_width_mm = :belt_width_mm)
          and (:component_group is null or component_group = :component_group)
          and (:option_value is null or option_value = :option_value)
        order by family_name, belt_width_mm, component_group, option_value, internal_ref
        limit :limit
    """)

    params = {
        "family_name": family_name,
        "family_code": family_code,
        "belt_width_mm": belt_width_mm,
        "component_group": component_group,
        "option_value": option_value,
        "limit": limit,
    }

    with ENGINE.begin() as conn:
        rows = conn.execute(sql, params).mappings().all()

    return {
        "status": "ok",
        "context_type": "belt_cleaner_config_options",
        "count": len(rows),
        "results": [repair_mojibake_data(dict(r)) for r in rows],
        "write_actions_available": False,
    }


@router.get("/belt-cleaners/config/choice")
def belt_cleaner_choice_options(
    family_name: Optional[str] = Query(default=None),
    family_code: Optional[str] = Query(default=None),
    belt_width_mm: Optional[int] = Query(default=None),
    choice_type: Optional[str] = Query(default=None, description="standard, rvs, special"),
    component_group: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
):
    """
    Keuze-view voor standard/rvs/special.
    Gebruikt vw_gpt_belt_cleaner_choice_options.
    """
    sql = text("""
        select
            family_name,
            family_code,
            belt_width_mm,
            choice_type,
            component_group,
            option_value,
            internal_ref,
            product_name,
            sale_price,
            available_qty,
            expected_qty,
            uom
        from vw_gpt_belt_cleaner_choice_options
        where (:family_name is null or family_name = :family_name)
          and (:family_code is null or family_code = :family_code)
          and (:belt_width_mm is null or belt_width_mm = :belt_width_mm)
          and (:choice_type is null or choice_type = :choice_type)
          and (:component_group is null or component_group = :component_group)
        order by family_name, belt_width_mm, choice_type, component_group, internal_ref
        limit :limit
    """)

    params = {
        "family_name": family_name,
        "family_code": family_code,
        "belt_width_mm": belt_width_mm,
        "choice_type": choice_type,
        "component_group": component_group,
        "limit": limit,
    }

    with ENGINE.begin() as conn:
        rows = conn.execute(sql, params).mappings().all()

        default_sql = text("""
            select
                family_name,
                family_code,
                belt_width_mm,
                choice_type,
                component_group,
                option_value,
                internal_ref,
                product_name,
                sale_price,
                available_qty,
                expected_qty,
                uom
            from vw_gpt_belt_cleaner_default_proposal
            where (:family_name is null or family_name = :family_name)
              and (:family_code is null or family_code = :family_code)
              and (:belt_width_mm is null or belt_width_mm = :belt_width_mm)
            order by
                case choice_type
                    when 'standard' then 1
                    when 'rvs' then 2
                    when 'special' then 3
                    else 9
                end,
                component_group,
                internal_ref
        """)

        default_rows = conn.execute(default_sql, {
            "family_name": family_name,
            "family_code": family_code,
            "belt_width_mm": belt_width_mm,
        }).mappings().all()

        summary_sql = text("""
            select
                family_name,
                family_code,
                belt_width_mm,
                jsonb_array_length(articles) as article_count,
                articles
            from vw_gpt_belt_cleaner_proposal_summary
            where (:family_name is null or family_name = :family_name)
              and (:family_code is null or family_code = :family_code)
              and (:belt_width_mm is null or belt_width_mm = :belt_width_mm)
            order by family_name, belt_width_mm
        """)

        summary_rows = conn.execute(summary_sql, {
            "family_name": family_name,
            "family_code": family_code,
            "belt_width_mm": belt_width_mm,
        }).mappings().all()

    return {
        "status": "ok",
        "context_type": "belt_cleaner_choice_options",
        "count": len(rows),
        "results": [repair_mojibake_data(dict(r)) for r in rows],
        "default_proposal_count": len(default_rows),
        "default_proposal": [dict(r) for r in default_rows],
        "proposal_summary_count": len(summary_rows),
        "proposal_summary": [dict(r) for r in summary_rows],
        "write_actions_available": False,
    }


@router.get("/{product_id}")
def get_product(product_id: int):
    sql = text("""
        select
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
        from scraper_product
        where product_id = :product_id
        limit 1
    """)

    with ENGINE.begin() as conn:
        row = conn.execute(sql, {"product_id": product_id}).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Product niet gevonden")

    return repair_mojibake_data(dict(row))


@router.get("/{product_id}/knowledge")
def get_product_knowledge(product_id: int):
    """
    Product + gekoppelde RAG-documenten + aantal chunks.
    Gebruikt product_document_link als koppeltabel.
    """

    product_sql = text("""
        select
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
        from scraper_product
        where product_id = :product_id
        limit 1
    """)

    docs_sql = text("""
        select
            pdl.id as link_id,
            pdl.product_id,
            pdl.doc_id,
            pdl.source_role,
            pdl.brand,
            pdl.model,
            pdl.variant,
            pdl.status,
            pdl.confidence,
            pdl.created_at,

            d.title,
            d.filename,
            d.content_type,
            d.minio_bucket,
            d.minio_key,

            count(c.chunk_id)::int as chunk_count

        from product_document_link pdl

        left join sb_docs_v0 d
            on d.doc_id = pdl.doc_id

        left join sb_doc_chunks_v0 c
            on c.doc_id = pdl.doc_id

        where pdl.product_id = :product_id

        group by
            pdl.id,
            pdl.product_id,
            pdl.doc_id,
            pdl.source_role,
            pdl.brand,
            pdl.model,
            pdl.variant,
            pdl.status,
            pdl.confidence,
            pdl.created_at,
            d.title,
            d.filename,
            d.content_type,
            d.minio_bucket,
            d.minio_key

        order by
            pdl.variant,
            pdl.source_role,
            d.title
    """)

    sales_sql = text("""
        select
            product_id,
            pitch,
            pros,
            cons,
            best_for,
            objections,
            cross_sell
        from scraper_product_sales
        where product_id = :product_id
        limit 1
    """)

    with ENGINE.begin() as conn:
        product = conn.execute(
            product_sql,
            {"product_id": product_id},
        ).mappings().first()

        if not product:
            raise HTTPException(status_code=404, detail="Product niet gevonden")

        docs = conn.execute(
            docs_sql,
            {"product_id": product_id},
        ).mappings().all()

        sales = conn.execute(
            sales_sql,
            {"product_id": product_id},
        ).mappings().first()

    return {
        "status": "ok",
        "product": dict(product),
        "sales_context": dict(sales) if sales else None,
        "knowledge_documents": [dict(r) for r in docs],
        "document_count": len(docs),
        "write_actions_available": False,
    }


@router.get("/by-model/{model}")
def get_product_by_model(model: str):
    sql = text("""
        select
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
        from scraper_product
        where lower(model) = lower(:model)
        limit 1
    """)

    with ENGINE.begin() as conn:
        row = conn.execute(sql, {"model": model}).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Product niet gevonden")

    return repair_mojibake_data(dict(row))


@router.get("/{product_id}/gpt-context")
def get_product_gpt_context(product_id: int):
    """
    Compacte GPT-context voor productvragen.
    Combineert scraper_product, scraper_product_sales en product_document_link.
    """

    product_sql = text("""
        select
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
        from scraper_product
        where product_id = :product_id
        limit 1
    """)

    sales_sql = text("""
        select
            product_id,
            pitch,
            pros,
            cons,
            best_for,
            objections,
            cross_sell
        from scraper_product_sales
        where product_id = :product_id
        limit 1
    """)

    docs_sql = text("""
        select
            pdl.doc_id,
            pdl.source_role,
            pdl.variant,
            pdl.status,
            pdl.confidence,
            d.title,
            d.filename,
            count(c.chunk_id)::int as chunk_count
        from product_document_link pdl
        left join sb_docs_v0 d on d.doc_id = pdl.doc_id
        left join sb_doc_chunks_v0 c on c.doc_id = pdl.doc_id
        where pdl.product_id = :product_id
        group by
            pdl.doc_id,
            pdl.source_role,
            pdl.variant,
            pdl.status,
            pdl.confidence,
            d.title,
            d.filename
        order by pdl.variant, d.title
    """)

    with ENGINE.begin() as conn:
        product = conn.execute(product_sql, {"product_id": product_id}).mappings().first()
        if not product:
            raise HTTPException(status_code=404, detail="Product niet gevonden")

        sales = conn.execute(sales_sql, {"product_id": product_id}).mappings().first()
        docs = conn.execute(docs_sql, {"product_id": product_id}).mappings().all()

    product = dict(product)
    sales = dict(sales) if sales else None
    docs = [dict(r) for r in docs]

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
        "product_id": product_id,
        "product_identity": identity,
        "technical_summary": ". ".join(technical_parts),
        "sales_summary": sales.get("pitch") if sales else None,
        "sales_context": sales,
        "documents": docs,
        "recommended_answer_style": (
            "Antwoord kort en praktisch. Gebruik technische limieten uit productdata "
            "en verwijs bij detailvragen naar gekoppelde documenten/RAG."
        ),
        "write_actions_available": False,
    }