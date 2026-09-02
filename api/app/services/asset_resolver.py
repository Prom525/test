from __future__ import annotations

import re
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine

ASSET_CONTEXT_VIEW = "public.vw_gpt_band_asset_context"


def normalize_asset_code(value: Optional[str]) -> Optional[str]:
    """
    Canonieke normalisatie voor band- en installatiecodes.

    Voorbeelden:
    R 5   -> R5
    R-5   -> R5
    e 401 -> E401
    MV-2  -> MV2
    """
    if value is None:
        return None

    normalized = re.sub(
        r"[^A-Za-z0-9]",
        "",
        str(value).strip(),
    ).upper()

    return normalized or None


def _fetch_candidates(
    band_code_norm: str,
    installation_code_norm: Optional[str],
    db_engine: Optional[Engine],
) -> list[dict[str, Any]]:
    conditions = [
        "band_code_norm = :band_code_norm",
    ]

    params: dict[str, Any] = {
        "band_code_norm": band_code_norm,
    }

    if installation_code_norm:
        conditions.append(
            """
            upper(
                regexp_replace(
                    installation_code,
                    '[^A-Za-z0-9]',
                    '',
                    'g'
                )
            ) = :installation_code_norm
            """
        )
        params["installation_code_norm"] = installation_code_norm

    where_sql = " AND ".join(conditions)

    sql = text(
        f"""
        SELECT
            customer_code,
            site_code,

            area_code,
            area_name,
            area_source,
            area_confidence,

            installation_code,
            installation_name,
            process_area,

            band_code,
            band_code_norm,
            band_code_display,

            history_mapping_warning

        FROM {ASSET_CONTEXT_VIEW}

        WHERE {where_sql}

        ORDER BY
            customer_code,
            site_code,
            area_code,
            installation_code,
            band_code_norm
        """
    )

    engine_to_use = db_engine

    if engine_to_use is None:
        from app.db import engine as default_engine
        engine_to_use = default_engine

    with engine_to_use.connect() as conn:
        rows = conn.execute(
            sql,
            params,
        ).mappings().all()

    return [
        dict(row)
        for row in rows
    ]


def resolve_asset(
    band_code: Optional[str],
    installation_code: Optional[str] = None,
    db_engine: Optional[Engine] = None,
) -> dict[str, Any]:
    """
    Resolveert een band naar de canonieke asset-context.

    Status:
    - resolved  : exact één asset
    - not_found : geen asset
    - ambiguous : meerdere assets

    Deze functie doet uitsluitend SELECTs.
    """
    band_code_norm = normalize_asset_code(band_code)
    installation_code_norm = normalize_asset_code(
        installation_code
    )

    if not band_code_norm:
        return {
            "status": "not_found",
            "input_band_code": band_code,
            "normalized_band_code": None,
            "input_installation_code": installation_code,
            "normalized_installation_code": installation_code_norm,
            "match_count": 0,
            "asset_context": None,
            "candidates": [],
        }

    candidates = _fetch_candidates(
        band_code_norm=band_code_norm,
        installation_code_norm=installation_code_norm,
        db_engine=db_engine,
    )

    match_count = len(candidates)

    if match_count == 0:
        return {
            "status": "not_found",
            "input_band_code": band_code,
            "normalized_band_code": band_code_norm,
            "input_installation_code": installation_code,
            "normalized_installation_code": installation_code_norm,
            "match_count": 0,
            "asset_context": None,
            "candidates": [],
        }

    if match_count > 1:
        return {
            "status": "ambiguous",
            "input_band_code": band_code,
            "normalized_band_code": band_code_norm,
            "input_installation_code": installation_code,
            "normalized_installation_code": installation_code_norm,
            "match_count": match_count,
            "asset_context": None,
            "candidates": candidates,
        }

    return {
        "status": "resolved",
        "input_band_code": band_code,
        "normalized_band_code": band_code_norm,
        "input_installation_code": installation_code,
        "normalized_installation_code": installation_code_norm,
        "match_count": 1,
        "asset_context": candidates[0],
        "candidates": [],
    }
