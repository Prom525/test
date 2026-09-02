from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from ..db import engine
import re  # voor robuuste LIMIT-detectie

router = APIRouter(prefix="/chatdb", tags=["chatdb"])

@router.get("/schema")
def get_schema():
    """
    Geeft database schema overzicht:
    - tabellen
    - kolommen
    - datatype
    """
    sql = """
    SELECT
        c.table_schema,
        c.table_name,
        c.column_name,
        c.data_type,
        c.is_nullable,
        c.ordinal_position
    FROM information_schema.columns c
    WHERE c.table_schema NOT IN ('pg_catalog', 'information_schema')
    ORDER BY c.table_schema, c.table_name, c.ordinal_position
    """

    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            rows = [dict(r._mapping) for r in result]
            return {"rows": rows}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Statement types die we toestaan
ALLOWED_PREFIXES = ("select", "with", "insert", "create")

# Blocklist – bewust GEEN ' replace ' meer
BLOCKED_KEYWORDS = (
    " drop ", " truncate ",
    " alter ", " grant ", " revoke ",
    " execute ", " copy ", " attach ", " vacuum ",
    " cascade "
)

# Whitelist voor schrijven – voeg hier je tabellen toe die inserts mogen krijgen
ALLOWED_WRITE_TABLES = {
    "org_units", "org_relations",
    "mt_members", "mt_members_v2",
    "functions", "functions_v2",
    "function_tasks", "function_kpis",
    "market_segments",
    "target_accounts", "target_accounts_v2",
    "account_notes", "account_notes_v2",
    "products", "products_v2",
    "product_variants", "product_variants_v2",
    "processes", "process_steps",
    "reliability_packs", "reliability_pack_items"
}

class QueryIn(BaseModel):
    sql: str
    max_rows: int = Field(500, ge=1, le=5000)
    timeout_ms: int = Field(6000, ge=100, le=30000)

def _starts_with_any(s: str, prefixes: tuple[str, ...]) -> bool:
    sl = s.strip().lower()
    return any(sl.startswith(p) for p in prefixes)

def _validate_sql(sql: str):
    s = f" {sql.strip().lower()} "

    # Alleen SELECT/WITH/INSERT/CREATE
    if not _starts_with_any(sql, ALLOWED_PREFIXES):
        raise HTTPException(400, "Alleen SELECT/WITH/INSERT/CREATE zijn toegestaan.")

    # Blokkeer echte DELETE-statements (maar niet 'ON DELETE ...' in FKs)
    if s.lstrip().startswith("delete"):
        raise HTTPException(400, "DELETE statements zijn niet toegestaan.")

    # Blocklist (zonder plain ' replace ')
    for kw in BLOCKED_KEYWORDS:
        if kw in s:
            raise HTTPException(400, f"Keyword '{kw.strip()}' is niet toegestaan.")

    # INSERT – forceer tabel-whitelist
    if s.lstrip().startswith("insert"):
        try:
            after_into = s.split("insert into", 1)[1].strip()
            table = after_into.split()[0].strip('";()')
        except Exception:
            raise HTTPException(400, "Kon doel-tabel in INSERT niet bepalen.")
        if table not in ALLOWED_WRITE_TABLES:
            raise HTTPException(400, f"Schrijven naar tabel '{table}' is niet toegestaan.")

    # CREATE toestaan voor TABLE, VIEW, MATERIALIZED VIEW/INDEX (+ OR REPLACE VIEW)
    if s.lstrip().startswith("create"):
        allowed_creates = (
            s.lstrip().startswith("create table")
            or s.lstrip().startswith("create view")
            or s.lstrip().startswith("create materialized view")
            or s.lstrip().startswith("create or replace view")
            or s.lstrip().startswith("create index")
            or s.lstrip().startswith("create unique index")
        )
        if not allowed_creates:
            raise HTTPException(400, "Alleen CREATE [TABLE|VIEW|MATERIALIZED VIEW|INDEX] is toegestaan.")

    return True

@router.post("/sql")
def run_sql(query: QueryIn):
    _validate_sql(query.sql)
    s = query.sql.strip()
    is_select = s.lower().startswith(("select", "with"))

    try:
        # Altijd transactie: SET LOCAL werkt dan en we scheiden statements
        with engine.begin() as conn:
            # 1) Zet statement timeout (losse execute)
            conn.execute(text(f"SET LOCAL statement_timeout = {query.timeout_ms}"))

            if is_select:
                # 2) SELECT – trailing ';' strippen en robuuste LIMIT-detectie
                sql = re.sub(r';\s*$', '', s, flags=re.IGNORECASE)
                has_limit = re.search(r'\blimit\b', sql, re.IGNORECASE) is not None
                if not has_limit:
                    sql += f" LIMIT {query.max_rows}"
                result = conn.execute(text(sql))
                rows = [dict(r._mapping) for r in result]
                return {"rows": rows}

            # 2) DDL/DML – voer exact het statement uit
            conn.execute(text(s))
            return {"status": "ok"}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))