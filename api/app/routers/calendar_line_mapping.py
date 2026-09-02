# api/app/routers/calendar_line_mapping.py

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.engine import Engine

from ..deps import get_engine, require_role

router = APIRouter(prefix="/calendar-line-mapping", tags=["calendar-line-mapping"])


# -----------------------------
# Models
# -----------------------------
class CalendarLineMappingIn(BaseModel):
    line_name: str = Field(..., min_length=1, description="Line naam zoals in sb_maintenance_calendar_v0.line_name")
    lijn_code: str = Field(..., min_length=1, max_length=32)
    note: Optional[str] = Field(None, max_length=500)


class CalendarLineMappingOut(BaseModel):
    line_name: str
    lijn_code: str
    note: Optional[str] = None


class CalendarLineSuggestionOut(BaseModel):
    line_name: str
    cells: int
    performed_cells: int
    blocked_cells: int


class CalendarLineMappingBulkIn(BaseModel):
    """
    Wrapper zodat request body een object is (Actions kan slecht overweg met 'array as root').
    """
    items: List[CalendarLineMappingIn] = Field(default_factory=list)


# -----------------------------
# Helpers
# -----------------------------
def ensure_table(conn) -> None:
    conn.execute(text("""
        create table if not exists sb_calendar_line_to_lijn (
          line_name text primary key,
          lijn_code text not null,
          note text,
          created_at timestamptz default now()
        )
    """))


# -----------------------------
# Endpoints
# -----------------------------
@router.get("", response_model=List[CalendarLineMappingOut])
def list_mappings(
    q: Optional[str] = Query(None, description="Filter op line_name of lijn_code"),
    limit: int = Query(200, ge=1, le=1000),
    engine: Engine = Depends(get_engine),
    _=Depends(require_role("admin")),
):
    if q:
        sql = text("""
            select line_name, lijn_code, note
            from sb_calendar_line_to_lijn
            where lower(line_name) like lower(:q)
               or lower(lijn_code) like lower(:q)
            order by line_name
            limit :limit
        """)
        params = {"q": f"%{q}%", "limit": limit}
    else:
        sql = text("""
            select line_name, lijn_code, note
            from sb_calendar_line_to_lijn
            order by line_name
            limit :limit
        """)
        params = {"limit": limit}

    with engine.begin() as conn:
        ensure_table(conn)
        rows = conn.execute(sql, params).mappings().all()
    return [dict(r) for r in rows]


@router.post("/upsert", response_model=CalendarLineMappingOut)
def upsert_mapping(
    payload: CalendarLineMappingIn,
    engine: Engine = Depends(get_engine),
    _=Depends(require_role("admin")),
):
    sql = text("""
        insert into sb_calendar_line_to_lijn (line_name, lijn_code, note)
        values (:line_name, :lijn_code, :note)
        on conflict (line_name) do update
          set lijn_code = excluded.lijn_code,
              note = excluded.note
        returning line_name, lijn_code, note
    """)
    with engine.begin() as conn:
        ensure_table(conn)
        row = conn.execute(sql, payload.model_dump()).mappings().first()
        if not row:
            raise HTTPException(status_code=500, detail="Upsert failed")
        return dict(row)


@router.post("/bulk-upsert")
def bulk_upsert(
    payload: CalendarLineMappingBulkIn,
    engine: Engine = Depends(get_engine),
    _=Depends(require_role("admin")),
):
    items = payload.items or []
    if not items:
        return {"status": "ok", "upserted": 0}

    sql = text("""
        insert into sb_calendar_line_to_lijn (line_name, lijn_code, note)
        values (:line_name, :lijn_code, :note)
        on conflict (line_name) do update
          set lijn_code = excluded.lijn_code,
              note = excluded.note
    """)

    with engine.begin() as conn:
        ensure_table(conn)
        conn.execute(sql, [p.model_dump() for p in items])

    return {"status": "ok", "upserted": len(items)}


@router.get("/suggestions", response_model=List[CalendarLineSuggestionOut])
def suggestions(
    limit: int = Query(50, ge=1, le=500),
    engine: Engine = Depends(get_engine),
    _=Depends(require_role("admin")),
):
    """
    Laat kalender line_names zien die nog NIET gemapt zijn in sb_calendar_line_to_lijn.
    Handig om snel bulk te mappen.
    """
    sql = text("""
        with agg as (
          select
            line_name,
            count(*)::int as cells,
            sum(case when performed then 1 else 0 end)::int as performed_cells,
            sum(case when blocked then 1 else 0 end)::int as blocked_cells
          from sb_maintenance_calendar_v0
          where line_name is not null and trim(line_name) <> ''
          group by line_name
        )
        select a.line_name, a.cells, a.performed_cells, a.blocked_cells
        from agg a
        left join sb_calendar_line_to_lijn m
          on m.line_name = a.line_name
        where m.line_name is null
        order by a.cells desc, a.line_name
        limit :limit
    """)

    with engine.begin() as conn:
        ensure_table(conn)
        rows = conn.execute(sql, {"limit": limit}).mappings().all()
    return [dict(r) for r in rows]