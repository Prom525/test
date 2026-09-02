from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
# from openai import OpenAI   # of Azure OpenAI, afhankelijk van jouw setup
from .chatdb import _validate_sql
from sqlalchemy import text
from ..db import engine

router = APIRouter(prefix="/chatdb", tags=["chatdb"])

class NLQuery(BaseModel):
    vraag: str
    max_rows: int = 500
    timeout_ms: int = 6000

# TODO: vervang dit met een echte LLM-call (ChatGPT 5.2) + schema prompt
def _mock_nl2sql(vraag: str) -> str:
    # Enkel voorbeeld – vervang door echte prompt + LLM respons:
    if "machines in plant a" in vraag.lower():
        return "SELECT * FROM machines WHERE locatie = 'Plant A'"
    return "SELECT * FROM machines LIMIT 10"

@router.post("/nl2sql")
def nl2sql(q: NLQuery):
    # 1) Genereer SQL (in productie: bel ChatGPT/Azure OpenAI met schema uit /chatdb/schema)
    sql = _mock_nl2sql(q.vraag)

    # 2) Valideer SQL (alleen veilige SELECT)
    _validate_sql(sql)

    # 3) Apply limieten
    safe_sql = f"SET LOCAL statement_timeout = {q.timeout_ms}; {sql}"
    if " limit " not in sql.lower():
        safe_sql += f" LIMIT {q.max_rows}"

    # 4) Uitvoeren
    try:
        with engine.connect() as conn:
            result = conn.execute(text(safe_sql))
            rows = [dict(r._mapping) for r in result]
            return {"sql": sql, "rows": rows}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))