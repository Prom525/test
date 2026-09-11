from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.engine import Engine

# Pas dit aan naar hoe jij nu je Engine/DB dependency doet
# Ik ga uit van een dependency `get_engine()` die een SQLAlchemy Engine geeft.
from .deps import get_engine  # <-- maak/gebruik jouw bestaande deps

# Pas dit aan naar hoe jij nu auth doet.
# Ik ga uit van: request heeft JWT claims al geverifieerd en je kunt roles lezen.
from .security import require_role  # <-- zie verderop: helper

router = APIRouter(prefix="/lijn-mapping", tags=["lijn-mapping"])


class LijnMappingIn(BaseModel):
    source_file: str = Field(..., min_length=3)
    lijn_code: str = Field(..., min_length=1, max_length=32)
    note: Optional[str] = Field(None, max_length=500)


class LijnMappingOut(BaseModel):
    source_file: str
    lijn_code: str
    note: Optional[str] = None


@router.post("/upsert", response_model=LijnMappingOut)
def upsert_mapping(
    payload: LijnMappingIn,
    engine: Engine = Depends(get_engine),
    _=Depends(require_role("admin")),
):
    sql = text("""
        insert into sb_sourcefile_to_lijn (source_file, lijn_code, note)
        values (:source_file, :lijn_code, :note)
        on conflict (source_file) do update
          set lijn_code = excluded.lijn_code,
              note = excluded.note
        returning source_file, lijn_code, note
    """)

    with engine.begin() as conn:
        row = conn.execute(sql, payload.model_dump()).mappings().first()
        if not row:
            raise HTTPException(status_code=500, detail="Upsert failed")
        return dict(row)


@router.post("/bulk-upsert")
def bulk_upsert(
    payload: List[LijnMappingIn],
    engine: Engine = Depends(get_engine),
    _=Depends(require_role("admin")),
):
    if len(payload) == 0:
        return {"status": "ok", "upserted": 0}

    sql = text("""
        insert into sb_sourcefile_to_lijn (source_file, lijn_code, note)
        values (:source_file, :lijn_code, :note)
        on conflict (source_file) do update
          set lijn_code = excluded.lijn_code,
              note = excluded.note
    """)

    with engine.begin() as conn:
        conn.execute(sql, [p.model_dump() for p in payload])
    return {"status": "ok", "upserted": len(payload)}


@router.get("", response_model=List[LijnMappingOut])
def list_mappings(
    q: Optional[str] = None,
    limit: int = 200,
    engine: Engine = Depends(get_engine),
    _=Depends(require_role("admin")),
):
    limit = max(1, min(limit, 1000))
    if q:
        sql = text("""
            select source_file, lijn_code, note
            from sb_sourcefile_to_lijn
            where lower(source_file) like lower(:q)
               or lower(lijn_code)   like lower(:q)
            order by source_file
            limit :limit
        """)
        params = {"q": f"%{q}%", "limit": limit}
    else:
        sql = text("""
            select source_file, lijn_code, note
            from sb_sourcefile_to_lijn
            order by source_file
            limit :limit
        """)
        params = {"limit": limit}

    with engine.begin() as conn:
        rows = conn.execute(sql, params).mappings().all()
    return [dict(r) for r in rows]


@router.post("/apply")
def apply_mapping(
    engine: Engine = Depends(get_engine),
    _=Depends(require_role("admin")),
):
    """
    Apply mapping to both inspections and items where lijn_code='UNKNOWN'.
    Safe + deterministic.
    """
    upd_items = text("""
        update sb_inspection_items_v0 i
        set lijn_code = m.lijn_code
        from sb_sourcefile_to_lijn m
        where i.lijn_code = 'UNKNOWN'
          and i.source_file = m.source_file
    """)
    upd_ins = text("""
        update sb_inspections_v0 ins
        set lijn_code = m.lijn_code
        from sb_sourcefile_to_lijn m
        where ins.lijn_code = 'UNKNOWN'
          and ins.source_file = m.source_file
    """)

    with engine.begin() as conn:
        r1 = conn.execute(upd_items)
        r2 = conn.execute(upd_ins)

    # r1.rowcount / r2.rowcount werkt meestal, maar niet altijd met sommige drivers
    return {"status": "ok", "items_updated": getattr(r1, "rowcount", None), "inspections_updated": getattr(r2, "rowcount", None)}