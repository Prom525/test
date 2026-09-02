from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from ..db import engine

router = APIRouter(prefix="/chatdb", tags=["chatdb"])

@router.get("/schema")
def get_schema():
    sql = """
    SELECT table_schema, table_name, column_name, data_type
    FROM information_schema.columns
    WHERE table_schema NOT IN ('pg_catalog','information_schema')
    ORDER BY table_schema, table_name, ordinal_position;
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            rows = [dict(r._mapping) for r in result]
            return {"columns": rows}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))