from fastapi import APIRouter
from sqlalchemy import text
from app.db import engine

router = APIRouter(prefix="/inspecties", tags=["inspecties"])


# ---------------------------------------------------
# Laatste inspecties
# ---------------------------------------------------

@router.get("")
def list_inspecties():

    sql = """
    select
        id,
        lijn_code,
        inspected_on,
        title
    from sb_inspections_v0
    order by inspected_on desc nulls last, created_at desc
    limit 20
    """

    with engine.begin() as conn:
        rows = conn.execute(text(sql)).mappings().all()

    return rows


# ---------------------------------------------------
# Inspecties per lijn
# ---------------------------------------------------

@router.get("/lijn/{lijn_code}")
def inspecties_per_lijn(lijn_code: str):

    sql = """
    select
        id,
        lijn_code,
        inspected_on,
        title
    from sb_inspections_v0
    where lijn_code = :lijn
    order by inspected_on desc nulls last
    limit 20
    """

    with engine.begin() as conn:
        rows = conn.execute(text(sql), {"lijn": lijn_code}).mappings().all()

    return rows


# ---------------------------------------------------
# Inspectie details
# ---------------------------------------------------

@router.get("/{inspection_key}")
def inspectie_details(inspection_key: str):

    sql_inspection = """
    select *
    from sb_inspections_v0
    where inspection_key = :key
    """

    sql_items = """
    select *
    from sb_inspection_items_v0
    where inspection_key = :key
    """

    with engine.begin() as conn:

        inspection = conn.execute(
            text(sql_inspection),
            {"key": inspection_key}
        ).mappings().first()

        items = conn.execute(
            text(sql_items),
            {"key": inspection_key}
        ).mappings().all()

    return {
        "inspection": inspection,
        "items": items
    }