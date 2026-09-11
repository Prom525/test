
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from ..db import engine

router = APIRouter(prefix="/plugin", tags=["plugin"]) 

ALLOWED_PREFIXES = ("select", "with")
BLOCKED_KEYWORDS = (
    "drop","truncate","delete","update","insert","alter","create",
    "grant","revoke","execute","copy","attach","vacuum"
)

class QueryIn(BaseModel):
    sql: str
    max_rows: int = Field(500, ge=1, le=5000)
    timeout_ms: int = Field(6000, ge=100, le=30000)

def _validate_sql(sql: str):
    s = sql.strip().lower()
    if not s.startswith(ALLOWED_PREFIXES):
        raise HTTPException(status_code=400, detail="Alleen SELECT/CTE queries toegestaan.")
    for kw in BLOCKED_KEYWORDS:
        if f" {kw} " in f" {s} ":
            raise HTTPException(status_code=400, detail=f"Keyword '{kw}' is niet toegestaan.")

@router.get("/schema")
def plugin_schema():
    sql = (
        "SELECT table_name, column_name, data_type "
        "FROM information_schema.columns "
        "WHERE table_schema = 'public' "
        "ORDER BY table_name, ordinal_position;"
    )
    with engine.connect() as conn:
        res = conn.execute(text(sql))
        rows = [dict(r._mapping) for r in res]
        return {"columns": rows}

@router.post("/sql")
def plugin_sql(q: QueryIn):
    _validate_sql(q.sql)
    safe_sql = f"SET LOCAL statement_timeout = {q.timeout_ms}; {q.sql}"
    if " limit " not in q.sql.lower():
        safe_sql += f" LIMIT {q.max_rows}"
    try:
        with engine.connect() as conn:
            res = conn.execute(text(safe_sql))
            rows = [dict(r._mapping) for r in res]
            return {"rows": rows}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
