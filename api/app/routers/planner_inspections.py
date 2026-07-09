from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.db import engine


router = APIRouter(
    prefix="/planner",
    tags=["planner-inspections"],
)


class PlannerInspectionPlanItemIn(BaseModel):
    sort_order: int | None = None
    scope_type: str

    customer_id: str | None = None
    site_id: str | None = None
    basisunit_code: str | None = None
    sub_area_code: str | None = None

    lijn_code: str | None = None
    band_code: str | None = None
    side: str | None = None
    component_type: str | None = None
    transfer_point_id: str | None = None

    scraper_position_id: str | None = None
    scraper_position: str | None = None
    scraper_role: str | None = None
    scraper_type: str | None = None
    scraper_family: str | None = None

    bulk_material_type: str | None = None

    previous_inspection_date: str | None = None
    previous_meshoogte_mm: float | None = None
    previous_condition_code: str | None = None
    previous_value_display: str | None = None
    previous_comment: str | None = None
    previous_advice: str | None = None

    required_measurements: list[dict[str, Any]] = Field(default_factory=list)
    required_photos: bool = False

    priority: int | None = None
    planner_note: str | None = None


class PlannerInspectionPlanIn(BaseModel):
    plan_date: str

    customer_id: str
    customer_name: str
    site_id: str
    site_name: str

    basisunit_code: str | None = None
    sub_area_code: str | None = None

    assigned_user_id: str | None = None
    assigned_user_name: str | None = None

    created_by: str
    remarks: str | None = None

    items: list[PlannerInspectionPlanItemIn] = Field(default_factory=list)


@router.post("/inspection-plans")
def create_inspection_plan(payload: PlannerInspectionPlanIn):
    """
    Planner maakt een inspectieplan met planregels.
    Status blijft DRAFT totdat het plan gepubliceerd wordt.
    """

    if not payload.items:
        raise HTTPException(
            status_code=400,
            detail="Inspectieplan moet minimaal 1 planregel bevatten.",
        )

    import json

    with engine.begin() as conn:
        plan_row = conn.execute(
            text("""
                INSERT INTO inspection_plans (
                    plan_date,
                    customer_id,
                    customer_name,
                    site_id,
                    site_name,
                    basisunit_code,
                    sub_area_code,
                    assigned_user_id,
                    assigned_user_name,
                    status,
                    created_by,
                    remarks
                )
                VALUES (
                    :plan_date,
                    :customer_id,
                    :customer_name,
                    :site_id,
                    :site_name,
                    :basisunit_code,
                    :sub_area_code,
                    :assigned_user_id,
                    :assigned_user_name,
                    'DRAFT',
                    :created_by,
                    :remarks
                )
                RETURNING plan_id
            """),
            {
                "plan_date": payload.plan_date,
                "customer_id": payload.customer_id,
                "customer_name": payload.customer_name,
                "site_id": payload.site_id,
                "site_name": payload.site_name,
                "basisunit_code": payload.basisunit_code,
                "sub_area_code": payload.sub_area_code,
                "assigned_user_id": payload.assigned_user_id,
                "assigned_user_name": payload.assigned_user_name,
                "created_by": payload.created_by,
                "remarks": payload.remarks,
            },
        ).mappings().first()

        if not plan_row:
            raise HTTPException(status_code=500, detail="Kon inspectieplan niet aanmaken.")

        plan_id = plan_row["plan_id"]

        for idx, item in enumerate(payload.items, start=1):
            conn.execute(
                text("""
                    INSERT INTO inspection_plan_items (
                        plan_id,
                        sort_order,
                        scope_type,
                        customer_id,
                        site_id,
                        basisunit_code,
                        sub_area_code,
                        lijn_code,
                        band_code,
                        side,
                        component_type,
                        transfer_point_id,
                        scraper_position_id,
                        scraper_position,
                        scraper_role,
                        scraper_type,
                        scraper_family,
                        bulk_material_type,
                        previous_inspection_date,
                        previous_meshoogte_mm,
                        previous_condition_code,
                        previous_value_display,
                        previous_comment,
                        previous_advice,
                        required_measurements,
                        required_photos,
                        priority,
                        planner_note,
                        status
                    )
                    VALUES (
                        :plan_id,
                        :sort_order,
                        :scope_type,
                        :customer_id,
                        :site_id,
                        :basisunit_code,
                        :sub_area_code,
                        :lijn_code,
                        :band_code,
                        :side,
                        :component_type,
                        :transfer_point_id,
                        :scraper_position_id,
                        :scraper_position,
                        :scraper_role,
                        :scraper_type,
                        :scraper_family,
                        :bulk_material_type,
                        :previous_inspection_date,
                        :previous_meshoogte_mm,
                        :previous_condition_code,
                        :previous_value_display,
                        :previous_comment,
                        :previous_advice,
                        CAST(:required_measurements AS jsonb),
                        :required_photos,
                        :priority,
                        :planner_note,
                        'PLANNED'
                    )
                """),
                {
                    **item.model_dump(exclude={"required_measurements"}),
                    "plan_id": str(plan_id),
                    "sort_order": item.sort_order or idx,
                    "required_measurements": json.dumps(item.required_measurements),
                },
            )

    return {
        "status": "ok",
        "plan_id": str(plan_id),
        "plan_status": "DRAFT",
        "item_count": len(payload.items),
    }


@router.get("/inspection-plans")
def list_inspection_plans(limit: int = 50):
    """
    Lijst met inspectieplannen voor planner.
    """

    with engine.begin() as conn:
        rows = conn.execute(
            text("""
                SELECT
                    p.*,
                    COUNT(i.plan_item_id)::int AS item_count
                FROM inspection_plans p
                LEFT JOIN inspection_plan_items i
                       ON i.plan_id = p.plan_id
                GROUP BY p.plan_id
                ORDER BY p.plan_date DESC, p.created_at DESC
                LIMIT :limit
            """),
            {"limit": limit},
        ).mappings().all()

    return {
        "status": "ok",
        "count": len(rows),
        "results": [dict(r) for r in rows],
    }


@router.get("/inspection-plans/{plan_id}")
def get_inspection_plan(plan_id: UUID):
    """
    Detail van inspectieplan inclusief planregels.
    """

    with engine.begin() as conn:
        plan = conn.execute(
            text("""
                SELECT *
                FROM inspection_plans
                WHERE plan_id = :plan_id
            """),
            {"plan_id": str(plan_id)},
        ).mappings().first()

        if not plan:
            raise HTTPException(status_code=404, detail="Inspectieplan niet gevonden.")

        items = conn.execute(
            text("""
                SELECT
                    i.*,
                    i.scraper_type AS planned_scraper_type,
                    ep.band_breedte_effective_raw AS belt_width_raw,
                    ep.band_breedte_effective_num AS belt_width_mm,
                    ep.scraper_type_effective_raw AS reference_scraper_type,
                    ep.scraper_type_effective_norm AS reference_scraper_type_norm,
                    ep.scraper_family AS reference_scraper_family,
                    ep.scraper_role AS reference_scraper_role
                FROM inspection_plan_items i
                LEFT JOIN LATERAL (
                    SELECT
                        p.band_breedte_effective_raw,
                        p.band_breedte_effective_num,
                        p.scraper_type_effective_raw,
                        p.scraper_type_effective_norm,
                        p.scraper_family,
                        p.scraper_role,
                        p.scraper_seq_in_block
                    FROM sb_excel_positions_v1 p
                    WHERE
                        UPPER(COALESCE(p.band_locatie_norm, '')) =
                        UPPER(REPLACE(COALESCE(i.band_code, ''), ' ', ''))
                    ORDER BY
                        CASE
                            WHEN UPPER(COALESCE(p.band_key, '')) =
                                 UPPER(CONCAT_WS(
                                     '|',
                                     NULLIF(i.customer_id, ''),
                                     NULLIF(i.site_id, ''),
                                     NULLIF(i.sub_area_code, ''),
                                     REPLACE(COALESCE(i.band_code, ''), ' ', '')
                                 ))
                            THEN 0
                            ELSE 1
                        END,
                        CASE
                            WHEN UPPER(COALESCE(p.scraper_role, '')) =
                                 UPPER(COALESCE(i.scraper_role, ''))
                            THEN 0
                            ELSE 1
                        END,
                        p.scraper_seq_in_block NULLS LAST
                    LIMIT 1
                ) ep ON true
                WHERE i.plan_id = :plan_id
                  AND i.status IN (
                      'PLANNED',
                      'SKIPPED',
                      'INSPECTED',
                      'NOT_ACCESSIBLE',
                      'NEEDS_RECHECK',
                      'SUBMITTED'
                  )
                ORDER BY i.sort_order NULLS LAST, i.created_at, i.plan_item_id
            """),
            {"plan_id": str(plan_id)},
        ).mappings().all()

    return {
        "plan": dict(plan),
        "items": [dict(r) for r in items],
    }


@router.post("/inspection-plans/{plan_id}/publish")
def publish_inspection_plan(plan_id: UUID):
    """
    Publiceert inspectieplan zodat de mobiele app het later kan downloaden.
    """

    with engine.begin() as conn:
        item_count = conn.execute(
            text("""
                SELECT COUNT(*)::int
                FROM inspection_plan_items
                WHERE plan_id = :plan_id
            """),
            {"plan_id": str(plan_id)},
        ).scalar_one()

        if item_count == 0:
            raise HTTPException(
                status_code=400,
                detail="Inspectieplan kan niet gepubliceerd worden zonder planregels.",
            )

        row = conn.execute(
            text("""
                UPDATE inspection_plans
                SET
                    status = 'PUBLISHED',
                    published_at = now(),
                    updated_at = now()
                WHERE plan_id = :plan_id
                  AND status IN ('DRAFT', 'READY_FOR_REVIEW')
                RETURNING plan_id, status, published_at
            """),
            {"plan_id": str(plan_id)},
        ).mappings().first()

        if not row:
            raise HTTPException(
                status_code=400,
                detail="Inspectieplan kan niet gepubliceerd worden. Controleer status.",
            )

    return {
        "status": "ok",
        "plan_id": str(row["plan_id"]),
        "plan_status": row["status"],
        "published_at": row["published_at"],
        "item_count": item_count,
    }


@router.get("/mobile-download/inspection-plans")
def list_published_plans_for_mobile(
    assigned_user_id: str | None = None,
    limit: int = 50,
):
    """
    Voor de mobiele app: haal gepubliceerde inspectieplannen op.
    Later gebruiken we dit voor offline synchronisatie.
    """

    sql = """
        SELECT
            p.*,
            COUNT(i.plan_item_id)::int AS item_count
        FROM inspection_plans p
        LEFT JOIN inspection_plan_items i
               ON i.plan_id = p.plan_id
                WHERE p.status IN ('PUBLISHED', 'DOWNLOADED', 'IN_PROGRESS', 'PARTLY_SUBMITTED', 'SUBMITTED')
    """

    params: dict[str, Any] = {"limit": limit}

    if assigned_user_id:
        sql += " AND p.assigned_user_id = :assigned_user_id"
        params["assigned_user_id"] = assigned_user_id

    sql += """
        GROUP BY p.plan_id
        ORDER BY p.plan_date ASC, p.created_at ASC
        LIMIT :limit
    """

    with engine.begin() as conn:
        rows = conn.execute(text(sql), params).mappings().all()

    return {
        "status": "ok",
        "count": len(rows),
        "results": [dict(r) for r in rows],
    }

class MobilePlanDownloadedIn(BaseModel):
    user_id: str
    device_id: str


@router.get("/mobile-download/inspection-plans/{plan_id}")
def get_published_plan_for_mobile(plan_id: UUID):
    """
    Voor de mobiele app: download volledig inspectieplan inclusief planregels.
    """

    with engine.begin() as conn:
        plan = conn.execute(
            text("""
                SELECT *
                FROM inspection_plans
                WHERE plan_id = :plan_id
                  AND status IN (
                      'PUBLISHED',
                      'DOWNLOADED',
                      'IN_PROGRESS',
                      'PARTLY_SUBMITTED',
                      'SUBMITTED'
                  )
            """),
            {"plan_id": str(plan_id)},
        ).mappings().first()

        if not plan:
            raise HTTPException(
                status_code=404,
                detail="Gepubliceerd inspectieplan niet gevonden voor mobiele download.",
            )

        items = conn.execute(
            text("""
                SELECT
                    i.*,
                    i.scraper_type AS planned_scraper_type,
                    ep.band_breedte_effective_raw AS belt_width_raw,
                    ep.band_breedte_effective_num AS belt_width_mm,
                    ep.scraper_type_effective_raw AS reference_scraper_type,
                    ep.scraper_type_effective_norm AS reference_scraper_type_norm,
                    ep.scraper_family AS reference_scraper_family,
                    ep.scraper_role AS reference_scraper_role
                FROM inspection_plan_items i
                LEFT JOIN LATERAL (
                    SELECT
                        p.band_breedte_effective_raw,
                        p.band_breedte_effective_num,
                        p.scraper_type_effective_raw,
                        p.scraper_type_effective_norm,
                        p.scraper_family,
                        p.scraper_role,
                        p.scraper_seq_in_block
                    FROM sb_excel_positions_v1 p
                    WHERE
                        UPPER(COALESCE(p.band_locatie_norm, '')) =
                        UPPER(REPLACE(COALESCE(i.band_code, ''), ' ', ''))
                    ORDER BY
                        CASE
                            WHEN UPPER(COALESCE(p.band_key, '')) =
                                 UPPER(CONCAT_WS(
                                     '|',
                                     NULLIF(i.customer_id, ''),
                                     NULLIF(i.site_id, ''),
                                     NULLIF(i.sub_area_code, ''),
                                     REPLACE(COALESCE(i.band_code, ''), ' ', '')
                                 ))
                            THEN 0
                            ELSE 1
                        END,
                        CASE
                            WHEN UPPER(COALESCE(p.scraper_role, '')) =
                                 UPPER(COALESCE(i.scraper_role, ''))
                            THEN 0
                            ELSE 1
                        END,
                        p.scraper_seq_in_block NULLS LAST
                    LIMIT 1
                ) ep ON true
                WHERE i.plan_id = :plan_id
                  AND i.status IN (
                      'PLANNED',
                      'SKIPPED',
                      'INSPECTED',
                      'NOT_ACCESSIBLE',
                      'NEEDS_RECHECK',
                      'SUBMITTED'
                  )
                ORDER BY i.sort_order NULLS LAST, i.created_at, i.plan_item_id
            """),
            {"plan_id": str(plan_id)},
        ).mappings().all()

    return {
        "status": "ok",
        "plan": dict(plan),
        "items": [dict(r) for r in items],
        "item_count": len(items),
        "download_mode": "offline_cache_ready",
    }


@router.post("/mobile-download/inspection-plans/{plan_id}/downloaded")
def mark_plan_downloaded_by_mobile(plan_id: UUID, payload: MobilePlanDownloadedIn):
    """
    Mobiele app meldt dat het plan offline is gedownload.
    """

    with engine.begin() as conn:
        row = conn.execute(
            text("""
                UPDATE inspection_plans
                SET
                    status = CASE
                        WHEN status = 'PUBLISHED' THEN 'DOWNLOADED'
                        ELSE status
                    END,
                    updated_at = now()
                WHERE plan_id = :plan_id
                  AND assigned_user_id = :user_id
                  AND status IN (
                      'PUBLISHED',
                      'DOWNLOADED',
                      'IN_PROGRESS',
                      'PARTLY_SUBMITTED',
                      'SUBMITTED'
                  )
                RETURNING plan_id, status
            """),
            {
                "plan_id": str(plan_id),
                "user_id": payload.user_id,
            },
        ).mappings().first()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="Plan niet gevonden of niet toegewezen aan deze gebruiker.",
            )

    return {
        "status": "ok",
        "plan_id": str(row["plan_id"]),
        "plan_status": row["status"],
        "user_id": payload.user_id,
        "device_id": payload.device_id,
    }