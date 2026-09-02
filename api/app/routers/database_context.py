from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text

from app.db import engine

router = APIRouter(
    prefix="/analysis/context/database",
    tags=["database-context"],
)


def fetch_all(sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    with engine.begin() as conn:
        result = conn.execute(text(sql), params or {})
        return [dict(row._mapping) for row in result]


def table_exists(schema: str, table: str) -> bool:
    rows = fetch_all(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = :schema
          AND table_name = :table
          AND table_type = 'BASE TABLE'
        LIMIT 1
        """,
        {"schema": schema, "table": table},
    )
    return len(rows) > 0


@router.get("/catalog")
def get_database_catalog():
    tables = fetch_all(
        """
        SELECT
            table_schema,
            table_name
        FROM information_schema.tables
        WHERE table_type = 'BASE TABLE'
          AND table_schema IN ('public', 'rfq')
        ORDER BY table_schema, table_name
        """
    )

    columns = fetch_all(
        """
        SELECT
            table_schema,
            table_name,
            column_name,
            data_type,
            ordinal_position
        FROM information_schema.columns
        WHERE table_schema IN ('public', 'rfq')
        ORDER BY table_schema, table_name, ordinal_position
        """
    )

    catalog: dict[str, Any] = {}

    for table in tables:
        schema = table["table_schema"]
        name = table["table_name"]

        catalog.setdefault(schema, {})
        catalog[schema][name] = {
            "columns": []
        }

    for col in columns:
        schema = col["table_schema"]
        table = col["table_name"]

        if schema in catalog and table in catalog[schema]:
            catalog[schema][table]["columns"].append({
                "name": col["column_name"],
                "data_type": col["data_type"],
            })

    return {
        "status": "ok",
        "context_type": "database_catalog",
        "schemas": catalog,
        "write_actions_available": False,
    }


@router.get("/table/{schema}/{table}")
def get_database_table_sample(
    schema: str,
    table: str,
    limit: int = Query(default=25, ge=1, le=100),
):
    allowed_schemas = {"public", "rfq"}

    if schema not in allowed_schemas:
        raise HTTPException(
            status_code=403,
            detail="Schema not allowed",
        )

    if not table_exists(schema, table):
        raise HTTPException(
            status_code=404,
            detail="Table not found",
        )

    columns = fetch_all(
        """
        SELECT
            column_name,
            data_type,
            ordinal_position
        FROM information_schema.columns
        WHERE table_schema = :schema
          AND table_name = :table
        ORDER BY ordinal_position
        """,
        {"schema": schema, "table": table},
    )

    row_count_result = fetch_all(
        f'SELECT COUNT(*)::int AS row_count FROM "{schema}"."{table}"'
    )
    row_count = row_count_result[0]["row_count"] if row_count_result else 0

    sample_rows = fetch_all(
        f'SELECT * FROM "{schema}"."{table}" LIMIT :limit',
        {"limit": limit},
    )

    return {
        "status": "ok",
        "context_type": "database_table_sample",
        "schema": schema,
        "table": table,
        "row_count": row_count,
        "columns": [
            {
                "name": col["column_name"],
                "data_type": col["data_type"],
            }
            for col in columns
        ],
        "sample_limit": limit,
        "sample_rows": sample_rows,
        "write_actions_available": False,
    }