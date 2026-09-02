from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

router = APIRouter(prefix="/inspecties", tags=["inspecties"])


def _get_engine() -> Engine:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL is not set")
    # psycopg2 driver werkt vaak standaard; laat hem implicit
    return create_engine(db_url, pool_pre_ping=True)


@router.get("")
def list_inspecties(limit: int = Query(20, ge=1, le=200)) -> list[dict[str, Any]]:
    """
    Laatste inspecties (zoals in sb_inspections_v0).
    """
    try:
        engine = _get_engine()
        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT
                      id,
                      inspection_key,
                      lijn_code,
                      inspected_on,
                      performed_by,
                      title
                    FROM sb_inspections_v0
                    ORDER BY inspected_on DESC NULLS LAST, id DESC
                    LIMIT :limit
                    """
                ),
                {"limit": limit},
            ).mappings().all()
            return [dict(r) for r in rows]
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Ik kon de inspecties niet ophalen.")


@router.get("/stats/per-jaar")
def stats_per_jaar() -> list[dict[str, Any]]:
    """
    Aantal inspecties per jaar.
    """
    try:
        engine = _get_engine()
        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT
                      EXTRACT(YEAR FROM inspected_on)::int AS jaar,
                      COUNT(*)::int AS aantal
                    FROM sb_inspections_v0
                    WHERE inspected_on IS NOT NULL
                    GROUP BY 1
                    ORDER BY 1 DESC
                    """
                )
            ).mappings().all()
            return [dict(r) for r in rows]
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Ik kon de statistiek niet ophalen.")


@router.get("/stats/per-maand")
def stats_per_maand() -> list[dict[str, Any]]:
    """
    Aantal inspecties per maand (jaar+maand).
    """
    try:
        engine = _get_engine()
        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT
                      EXTRACT(YEAR FROM inspected_on)::int AS jaar,
                      EXTRACT(MONTH FROM inspected_on)::int AS maand,
                      COUNT(*)::int AS aantal
                    FROM sb_inspections_v0
                    WHERE inspected_on IS NOT NULL
                    GROUP BY 1, 2
                    ORDER BY jaar DESC, maand DESC
                    """
                )
            ).mappings().all()
            return [dict(r) for r in rows]
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Ik kon de statistiek niet ophalen.")


@router.get("/stats/top-lijnen")
def stats_top_lijnen(limit: int = Query(10, ge=1, le=100)) -> list[dict[str, Any]]:
    """
    Top lijnen op aantal inspecties.
    """
    try:
        engine = _get_engine()
        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT
                      COALESCE(lijn_code, 'UNKNOWN') AS lijn_code,
                      COUNT(*)::int AS aantal
                    FROM sb_inspections_v0
                    GROUP BY 1
                    ORDER BY aantal DESC, lijn_code ASC
                    LIMIT :limit
                    """
                ),
                {"limit": limit},
            ).mappings().all()
            return [dict(r) for r in rows]
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Ik kon de statistiek niet ophalen.")