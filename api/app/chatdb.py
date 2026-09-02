from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from ..db import engine

router = APIRouter(prefix="/chatdb", tags=["chatdb"])

class QueryIn(BaseModel):
    sql: str

@router.post("/sql")
def run_sql(query: QueryIn):
    try:
        with engine.connect() as conn:
            result = conn.execute(text(query.sql))
            rows = [dict(row._mapping) for row in result]
            return {"rows": rows}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/schema")
def get_schema():
    with engine.connect() as conn:
        result = conn.execute(text("""
            select table_name, column_name, data_type
            from information_schema.columns
            where table_schema not in ('pg_catalog', 'information_schema')
            order by table_name, ordinal_position
        """))
        rows = [dict(row._mapping) for row in result]
        return {"rows": rows}