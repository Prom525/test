from __future__ import annotations

import os
import re
from typing import Optional, Any

from fastapi import APIRouter, Query, HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


router = APIRouter(prefix="/technical", tags=["technical"])


_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise RuntimeError("DATABASE_URL environment variable is not set")
        _engine = create_engine(database_url, pool_pre_ping=True)
    return _engine


def _build_search_terms(q: str) -> list[str]:
    stopwords = {
        "hoe", "wat", "waarom", "waar", "wanneer", "welke", "welk",
        "ik", "je", "jij", "we", "wij", "de", "het", "een", "en",
        "of", "in", "op", "bij", "voor", "van", "met", "te", "is",
        "zijn", "bepaal", "bereken", "berekenen"
    }

    cleaned = re.sub(r"[^a-zA-Z0-9À-ÿ_/.-]+", " ", q.lower())

    terms = []
    for part in cleaned.split():
        part = part.strip(" ?!.,;:()[]{}")
        if len(part) >= 3 and part not in stopwords:
            terms.append(part)

    return terms


@router.get("/context")
def get_technical_context(
    q: str = Query(..., min_length=2),
    topic_group: Optional[str] = Query(None),
    source_code: Optional[str] = Query(None),
    item_type: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:

    terms = _build_search_terms(q)

    sql = text("""
        with base as (
            select
                item_type,
                item_id,
                source_code,
                source_title,
                topic_group,
                component_type,
                problem_type,
                chapter_no,
                chapter_title,
                title,
                page_start,
                page_end,
                summary_nl,
                key_points_nl,
                structured_data,
                search_text,
                lower(
                    coalesce(search_text, '') || ' ' ||
                    coalesce(title, '') || ' ' ||
                    coalesce(summary_nl, '') || ' ' ||
                    coalesce(key_points_nl, '') || ' ' ||
                    coalesce(structured_data::text, '')
                ) as haystack
            from vw_gpt_technical_context
            where (:topic_group is null or topic_group = :topic_group)
              and (:source_code is null or source_code = :source_code)
              and (:item_type is null or item_type = :item_type)
        )
        select
            item_type,
            item_id,
            source_code,
            source_title,
            topic_group,
            component_type,
            problem_type,
            chapter_no,
            chapter_title,
            title,
            page_start,
            page_end,
            summary_nl,
            key_points_nl,
            structured_data
        from base
        where
            haystack ilike any(:term_patterns)
        order by
            (
                case when item_type = 'formula' then 100 else 0 end
                +
                case when title ilike :full_q_like then 300 else 0 end
                +
                case when search_text ilike :full_q_like then 250 else 0 end
                +
                case when structured_data::text ilike :full_q_like then 150 else 0 end
                +
                (
                    select coalesce(sum(
                        case
                            when base.title ilike ('%' || term || '%') then 80
                            when base.search_text ilike ('%' || term || '%') then 60
                            when base.structured_data::text ilike ('%' || term || '%') then 40
                            when base.haystack ilike ('%' || term || '%') then 20
                            else 0
                        end
                    ), 0)
                    from unnest(:terms) as term
                )
            ) desc,
            case item_type
                when 'formula' then 1
                when 'fact' then 2
                when 'table' then 3
                when 'section' then 4
                else 9
            end,
            source_code,
            page_start nulls last,
            title
        limit :limit
    """)

    params = {
        "full_q_like": f"%{q}%",
        "term_patterns": [f"%{term}%" for term in terms],
        "terms": terms,
        "topic_group": topic_group,
        "source_code": source_code,
        "item_type": item_type,
        "limit": limit,
    }

    try:
        with get_engine().connect() as conn:
            rows = conn.execute(sql, params).mappings().all()

        return {
            "status": "ok",
            "query": q,
            "terms": terms,
            "topic_group": topic_group,
            "source_code": source_code,
            "item_type": item_type,
            "count": len(rows),
            "results": [dict(row) for row in rows],
        }

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))