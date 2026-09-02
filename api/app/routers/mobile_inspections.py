from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.db import engine


router = APIRouter(
    prefix="/mobile",
    tags=["mobile-inspections"],
)


class MobileInspectionItemIn(BaseModel):
    client_item_id: UUID
    plan_item_id: UUID | None = None

    scope_type: str

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

    measurement_type: str | None = None
    measurement_value_num: float | None = None
    measurement_value_text: str | None = None
    meshoogte_mm: float | None = None
    condition_code: str | None = None

    status: str | None = None
    severity: str | None = None
    opmerking: str | None = None
    action_required: bool | None = None
    action_type: str | None = None
    replaced: bool | None = None

    ambient_temperature_c: float | None = None
    relative_humidity_pct: float | None = None
    material_moisture_pct: float | None = None
    material_condition: str | None = None
    belt_load: str | None = None
    production_state: str | None = None

    asset_match_status: str = "MATCHED"
    offline_created_at: str | None = None

    raw_payload: dict[str, Any] = Field(default_factory=dict)


class MobileInspectionSubmissionIn(BaseModel):
    client_submission_id: UUID

    plan_id: UUID | None = None
    user_id: str
    user_name: str | None = None
    device_id: str

    customer_id: str | None = None
    customer_name: str | None = None
    site_id: str | None = None
    site_name: str | None = None
    basisunit_code: str | None = None
    sub_area_code: str | None = None

    offline_started_at: str | None = None
    offline_completed_at: str | None = None

    raw_payload: dict[str, Any] = Field(default_factory=dict)
    items: list[MobileInspectionItemIn] = Field(default_factory=list)


@router.post("/inspection-submissions")
def create_mobile_submission(payload: MobileInspectionSubmissionIn):
    """
    Ontvangt mobiele inspectie uit app.
    Schrijft alleen naar mobile staging/wachtrij.
    Schrijft NIET naar sb_inspections_v0 of sb_inspection_items_v0.
    """

    if not payload.items:
        raise HTTPException(
            status_code=400,
            detail="Submission moet minimaal 1 item bevatten.",
        )

    insert_submission_sql = text("""
        INSERT INTO mobile_inspection_submissions (
            client_submission_id,
            plan_id,
            user_id,
            user_name,
            device_id,
            customer_id,
            customer_name,
            site_id,
            site_name,
            basisunit_code,
            sub_area_code,
            offline_started_at,
            offline_completed_at,
            raw_payload
        )
        VALUES (
            :client_submission_id,
            :plan_id,
            :user_id,
            :user_name,
            :device_id,
            :customer_id,
            :customer_name,
            :site_id,
            :site_name,
            :basisunit_code,
            :sub_area_code,
            :offline_started_at,
            :offline_completed_at,
            CAST(:raw_payload AS jsonb)
        )
        ON CONFLICT (client_submission_id)
        DO UPDATE SET
            updated_at = now()
        RETURNING submission_id
    """)

    insert_item_sql = text("""
        INSERT INTO mobile_inspection_submission_items (
            submission_id,
            client_item_id,
            plan_item_id,
            scope_type,
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
            measurement_type,
            measurement_value_num,
            measurement_value_text,
            meshoogte_mm,
            condition_code,
            status,
            severity,
            opmerking,
            action_required,
            action_type,
            replaced,
            ambient_temperature_c,
            relative_humidity_pct,
            material_moisture_pct,
            material_condition,
            belt_load,
            production_state,
            asset_match_status,
            offline_created_at,
            raw_payload
        )
        VALUES (
            :submission_id,
            :client_item_id,
            :plan_item_id,
            :scope_type,
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
            :measurement_type,
            :measurement_value_num,
            :measurement_value_text,
            :meshoogte_mm,
            :condition_code,
            :status,
            :severity,
            :opmerking,
            :action_required,
            :action_type,
            :replaced,
            :ambient_temperature_c,
            :relative_humidity_pct,
            :material_moisture_pct,
            :material_condition,
            :belt_load,
            :production_state,
            :asset_match_status,
            :offline_created_at,
            CAST(:raw_payload AS jsonb)
        )
        ON CONFLICT (client_item_id)
        DO NOTHING
    """)

    import json

    with engine.begin() as conn:
        existing_submission = conn.execute(
            text("""
                SELECT submission_id
                FROM mobile_inspection_submissions
                WHERE client_submission_id = :client_submission_id
            """),
            {"client_submission_id": str(payload.client_submission_id)},
        ).mappings().first()

        if existing_submission:
            queue_row = conn.execute(
                text("""
                    SELECT *
                    FROM vw_mobile_validation_queue
                    WHERE submission_id = :submission_id
                """),
                {"submission_id": existing_submission["submission_id"]},
            ).mappings().first()

            return {
                "status": "ok",
                "idempotent": True,
                "message": "Submission was al ontvangen. Bestaande submission teruggegeven.",
                "submission_id": str(existing_submission["submission_id"]),
                "validation_status": queue_row["validation_status"] if queue_row else None,
                "item_count": queue_row["item_count"] if queue_row else None,
                "validation_issue_count": queue_row["validation_issue_count"] if queue_row else None,
                "ready_for_planner_approval": queue_row["ready_for_planner_approval"] if queue_row else None,
                "write_target": "mobile_staging_only",
            }

        submission_params = payload.model_dump(exclude={"items"})
        submission_params["client_submission_id"] = str(payload.client_submission_id)
        submission_params["plan_id"] = str(payload.plan_id) if payload.plan_id else None
        submission_params["raw_payload"] = json.dumps(payload.raw_payload)

        row = conn.execute(insert_submission_sql, submission_params).mappings().first()

        if not row:
            raise HTTPException(status_code=500, detail="Kon submission niet opslaan.")

        submission_id = row["submission_id"]

        submitted_plan_item_ids: list[str] = []

        for item in payload.items:
            item_params = item.model_dump()
            item_params["submission_id"] = submission_id
            item_params["client_item_id"] = str(item.client_item_id)
            item_params["plan_item_id"] = str(item.plan_item_id) if item.plan_item_id else None
            item_params["raw_payload"] = json.dumps(item.raw_payload)

            conn.execute(insert_item_sql, item_params)

            if item.plan_item_id:
                submitted_plan_item_ids.append(str(item.plan_item_id))

        if payload.plan_id and submitted_plan_item_ids:
            for submitted_plan_item_id in submitted_plan_item_ids:
                conn.execute(
                    text("""
                        UPDATE inspection_plan_items
                        SET
                            status = 'SUBMITTED',
                            updated_at = now()
                        WHERE plan_id = CAST(:plan_id AS uuid)
                          AND plan_item_id = CAST(:plan_item_id AS uuid)
                          AND status IN (
                              'PLANNED',
                              'INSPECTED',
                              'NEEDS_RECHECK',
                              'NOT_ACCESSIBLE',
                              'SKIPPED'
                          )
                    """),
                    {
                        "plan_id": str(payload.plan_id),
                        "plan_item_id": submitted_plan_item_id,
                    },
                )

            plan_counts = conn.execute(
                text("""
                    SELECT
                        COUNT(*)::int AS total_items,
                        COUNT(*) FILTER (
                            WHERE status IN (
                                'SUBMITTED',
                                'APPROVED',
                                'PROMOTED'
                            )
                        )::int AS submitted_items
                    FROM inspection_plan_items
                    WHERE plan_id = :plan_id
                """),
                {"plan_id": str(payload.plan_id)},
            ).mappings().first()

            if plan_counts:
                next_plan_status = (
                    "SUBMITTED"
                    if plan_counts["total_items"] > 0
                    and plan_counts["submitted_items"] >= plan_counts["total_items"]
                    else "PARTLY_SUBMITTED"
                )

                conn.execute(
                    text("""
                        UPDATE inspection_plans
                        SET
                            status = :next_plan_status,
                            updated_at = now()
                        WHERE plan_id = :plan_id
                          AND status IN (
                              'PUBLISHED',
                              'DOWNLOADED',
                              'IN_PROGRESS',
                              'PARTLY_SUBMITTED'
                          )
                    """),
                    {
                        "plan_id": str(payload.plan_id),
                        "next_plan_status": next_plan_status,
                    },
                )

        queue_row = conn.execute(
            text("""
                SELECT *
                FROM vw_mobile_validation_queue
                WHERE submission_id = :submission_id
            """),
            {"submission_id": submission_id},
        ).mappings().first()

    return {
        "status": "ok",
        "submission_id": str(submission_id),
        "validation_status": queue_row["validation_status"] if queue_row else None,
        "item_count": queue_row["item_count"] if queue_row else None,
        "validation_issue_count": queue_row["validation_issue_count"] if queue_row else None,
        "ready_for_planner_approval": queue_row["ready_for_planner_approval"] if queue_row else None,
        "write_target": "mobile_staging_only",
    }


@router.get("/inspection-submissions/{submission_id}")
def get_mobile_submission(submission_id: UUID):
    with engine.begin() as conn:
        submission = conn.execute(
            text("""
                SELECT *
                FROM mobile_inspection_submissions
                WHERE submission_id = :submission_id
            """),
            {"submission_id": str(submission_id)},
        ).mappings().first()

        if not submission:
            raise HTTPException(status_code=404, detail="Submission niet gevonden.")

        items = conn.execute(
            text("""
                SELECT *
                FROM mobile_inspection_submission_items
                WHERE submission_id = :submission_id
                ORDER BY submitted_at, submission_item_id
            """),
            {"submission_id": str(submission_id)},
        ).mappings().all()

        issues = conn.execute(
            text("""
                SELECT *
                FROM vw_mobile_submission_validation_issues
                WHERE submission_id = :submission_id
                ORDER BY issue_scope, issue_code
            """),
            {"submission_id": str(submission_id)},
        ).mappings().all()

    return {
        "submission": dict(submission),
        "items": [dict(r) for r in items],
        "validation_issues": [dict(r) for r in issues],
    }


@router.get("/validation-queue")
def get_mobile_validation_queue(limit: int = 50):
    with engine.begin() as conn:
        rows = conn.execute(
            text("""
                SELECT *
                FROM vw_mobile_validation_queue
                ORDER BY submitted_at DESC
                LIMIT :limit
            """),
            {"limit": limit},
        ).mappings().all()

    return {
        "status": "ok",
        "count": len(rows),
        "results": [dict(r) for r in rows],
    }