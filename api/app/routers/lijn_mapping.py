# C:\ai-platform\api\app\routers\lijn_mapping.py

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.engine import Engine

from ..deps import get_engine, require_role

router = APIRouter(prefix="/lijn-mapping", tags=["lijn-mapping"])


# -----------------------------
# Models
# -----------------------------
class LijnMappingIn(BaseModel):
    source_file: str = Field(
        ...,
        min_length=3,
        description="Volledig pad (zoals in DB opgeslagen). Let op: exact match vereist.",
    )
    lijn_code: str = Field(..., min_length=1, max_length=32, description="Doel lijn_code")
    note: Optional[str] = Field(None, max_length=500, description="Optionele toelichting")


class LijnMappingOut(BaseModel):
    source_file: str
    lijn_code: str
    note: Optional[str] = None


class LijnMappingBulkIn(BaseModel):
    """
    Wrapper zodat request body een object is (Actions kan slecht overweg met 'array as root').
    """
    items: List[LijnMappingIn] = Field(default_factory=list)


class SuggestionOut(BaseModel):
    source_file: str
    n_items_unknown: int


class ApplyOut(BaseModel):
    status: str
    items_updated: Optional[int] = None
    inspections_updated: Optional[int] = None


class ApplyFromItemsOut(BaseModel):
    status: str
    inspections_updated: Optional[int] = None


# -----------------------------
# Endpoints
# -----------------------------
@router.get("", response_model=List[LijnMappingOut])
def list_mappings(
    q: Optional[str] = Query(None, description="Filter op (deel van) source_file of lijn_code"),
    limit: int = Query(200, ge=1, le=1000),
    engine: Engine = Depends(get_engine),
    _=Depends(require_role("admin")),
):
    """
    Lijst alle mappings uit sb_sourcefile_to_lijn.

    Optioneel filter:
    - q matcht op source_file of lijn_code (case-insensitive, contains)
    """
    if q:
        sql = text(
            """
            select source_file, lijn_code, note
            from sb_sourcefile_to_lijn
            where lower(source_file) like lower(:q)
               or lower(lijn_code) like lower(:q)
            order by source_file
            limit :limit
            """
        )
        params = {"q": f"%{q}%", "limit": limit}
    else:
        sql = text(
            """
            select source_file, lijn_code, note
            from sb_sourcefile_to_lijn
            order by source_file
            limit :limit
            """
        )
        params = {"limit": limit}

    with engine.begin() as conn:
        rows = conn.execute(sql, params).mappings().all()
    return [dict(r) for r in rows]


@router.post("/upsert", response_model=LijnMappingOut)
def upsert_mapping(
    payload: LijnMappingIn,
    engine: Engine = Depends(get_engine),
    _=Depends(require_role("admin")),
):
    """
    Upsert 1 mapping (source_file is primary key).
    """
    sql = text(
        """
        insert into sb_sourcefile_to_lijn (source_file, lijn_code, note)
        values (:source_file, :lijn_code, :note)
        on conflict (source_file) do update
          set lijn_code = excluded.lijn_code,
              note = excluded.note
        returning source_file, lijn_code, note
        """
    )
    with engine.begin() as conn:
        row = conn.execute(sql, payload.model_dump()).mappings().first()

    if not row:
        raise HTTPException(status_code=500, detail="Upsert failed")
    return dict(row)


@router.post("/bulk-upsert")
def bulk_upsert(
    payload: LijnMappingBulkIn,
    engine: Engine = Depends(get_engine),
    _=Depends(require_role("admin")),
):
    """
    Bulk upsert mappings.
    """
    items = payload.items or []
    if not items:
        return {"status": "ok", "upserted": 0}

    sql = text(
        """
        insert into sb_sourcefile_to_lijn (source_file, lijn_code, note)
        values (:source_file, :lijn_code, :note)
        on conflict (source_file) do update
          set lijn_code = excluded.lijn_code,
              note = excluded.note
        """
    )

    with engine.begin() as conn:
        conn.execute(sql, [p.model_dump() for p in items])

    return {"status": "ok", "upserted": len(items)}


@router.delete("/{source_file:path}")
def delete_mapping(
    source_file: str,
    engine: Engine = Depends(get_engine),
    _=Depends(require_role("admin")),
):
    """
    Verwijder mapping op source_file.

    Let op: in URL moet source_file URL-encoded worden (slashes/backslashes/spaces).
    """
    sql = text("delete from sb_sourcefile_to_lijn where source_file = :source_file")
    with engine.begin() as conn:
        r = conn.execute(sql, {"source_file": source_file})
    return {"status": "ok", "deleted": getattr(r, "rowcount", None)}


@router.get("/suggestions", response_model=List[SuggestionOut])
def unknown_suggestions(
    limit: int = Query(30, ge=1, le=500),
    engine: Engine = Depends(get_engine),
    _=Depends(require_role("admin")),
):
    """
    Geeft de top 'UNKNOWN' source_files zodat je snel kunt mappen.
    Gebaseerd op sb_inspection_items_v0 (meestal het meest relevant).

    Output:
    - source_file
    - n_items_unknown
    """
    sql = text(
        """
        select source_file, count(*)::int as n_items_unknown
        from sb_inspection_items_v0
        where lijn_code = 'UNKNOWN'
        group by source_file
        order by n_items_unknown desc
        limit :limit
        """
    )
    with engine.begin() as conn:
        rows = conn.execute(sql, {"limit": limit}).mappings().all()
    return [dict(r) for r in rows]


@router.post("/apply", response_model=ApplyOut)
def apply_mapping(
    engine: Engine = Depends(get_engine),
    _=Depends(require_role("admin")),
):
    """
    Past mapping toe op:
    - sb_inspection_items_v0 waar lijn_code='UNKNOWN'
    - sb_inspections_v0 waar lijn_code='UNKNOWN'

    Idempotent: je kunt dit vaker draaien.
    """
    upd_items = text(
        """
        update sb_inspection_items_v0 i
        set lijn_code = m.lijn_code
        from sb_sourcefile_to_lijn m
        where i.lijn_code = 'UNKNOWN'
          and i.source_file = m.source_file
        """
    )
    upd_inspections = text(
        """
        update sb_inspections_v0 ins
        set lijn_code = m.lijn_code
        from sb_sourcefile_to_lijn m
        where ins.lijn_code = 'UNKNOWN'
          and ins.source_file = m.source_file
        """
    )

    with engine.begin() as conn:
        r1 = conn.execute(upd_items)
        r2 = conn.execute(upd_inspections)

    return {
        "status": "ok",
        "items_updated": getattr(r1, "rowcount", None),
        "inspections_updated": getattr(r2, "rowcount", None),
    }


@router.post("/apply-from-items", response_model=ApplyFromItemsOut)
def apply_from_items(
    engine: Engine = Depends(get_engine),
    _=Depends(require_role("admin")),
):
    """
    Zet sb_inspections_v0.lijn_code op basis van sb_inspection_items_v0:

    - Alleen waar inspections nog UNKNOWN zijn
    - Neemt per inspection_key de meest voorkomende lijn_code uit items
      (ties: alfabetisch op lijn_code)
    """
    sql = text(
        """
        with votes as (
          select
            inspection_key,
            lijn_code,
            count(*) as cnt
          from sb_inspection_items_v0
          where lijn_code is not null
            and lijn_code <> 'UNKNOWN'
          group by inspection_key, lijn_code
        ),
        winners as (
          select inspection_key, lijn_code
          from (
            select
              inspection_key,
              lijn_code,
              cnt,
              row_number() over (
                partition by inspection_key
                order by cnt desc, lijn_code asc
              ) as rn
            from votes
          ) x
          where rn = 1
        )
        update sb_inspections_v0 ins
        set lijn_code = w.lijn_code
        from winners w
        where ins.inspection_key = w.inspection_key
          and ins.lijn_code = 'UNKNOWN'
        """
    )

    with engine.begin() as conn:
        r = conn.execute(sql)

    return {"status": "ok", "inspections_updated": getattr(r, "rowcount", None)}