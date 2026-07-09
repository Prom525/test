from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from app.db import engine


router = APIRouter(
    prefix="/validation",
    tags=["validation"],
)


class ValidationActionIn(BaseModel):
    validated_by: str
    note: str | None = None


@router.get("/queue")
def get_validation_queue(limit: int = 50):
    """
    Planner-validatiewachtrij.
    Toont mobiele submissions die nog beoordeeld moeten worden.
    """

    with engine.begin() as conn:
        rows = conn.execute(
            text("""
                SELECT *
                FROM vw_mobile_validation_queue
                WHERE validation_status IN (
                    'WAITING_FOR_PLANNER_VALIDATION',
                    'VALIDATION_IN_PROGRESS',
                    'NEEDS_CORRECTION',
                    'APPROVED',
                    'READY_FOR_PROMOTION',
                    'PROMOTION_FAILED'
                )
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


@router.get("/submissions/{submission_id}")
def get_validation_submission(submission_id: UUID):
    """
    Detail van 1 mobiele submission inclusief items en validatieproblemen.
    """

    with engine.begin() as conn:
        submission = conn.execute(
            text("""
                SELECT *
                FROM vw_mobile_validation_queue
                WHERE submission_id = :submission_id
            """),
            {"submission_id": str(submission_id)},
        ).mappings().first()

        if not submission:
            raise HTTPException(status_code=404, detail="Submission niet gevonden.")

        submission_extra = conn.execute(
            text("""
                SELECT raw_payload
                FROM mobile_inspection_submissions
                WHERE submission_id = :submission_id
            """),
            {"submission_id": str(submission_id)},
        ).mappings().first()

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

    submission_dict = dict(submission)

    if submission_extra and submission_extra.get("raw_payload"):
        raw_payload = submission_extra["raw_payload"]
        submission_dict["raw_payload"] = raw_payload

        if isinstance(raw_payload, dict):
            submission_dict["second_monteur_name"] = raw_payload.get(
                "second_monteur_name"
            )

    return {
        "submission": submission_dict,
        "items": [dict(r) for r in items],
        "validation_issues": [dict(r) for r in issues],
    }


@router.post("/submissions/{submission_id}/start")
def start_validation(submission_id: UUID, payload: ValidationActionIn):
    """
    Zet submission op VALIDATION_IN_PROGRESS.
    """

    with engine.begin() as conn:
        row = conn.execute(
            text("""
                UPDATE mobile_inspection_submissions
                SET
                    validation_status = 'VALIDATION_IN_PROGRESS',
                    validated_by = :validated_by,
                    validation_notes = :note,
                    updated_at = now()
                WHERE submission_id = :submission_id
                  AND validation_status IN (
                      'WAITING_FOR_PLANNER_VALIDATION',
                      'NEEDS_CORRECTION',
                      'PROMOTION_FAILED'
                  )
                RETURNING submission_id, validation_status
            """),
            {
                "submission_id": str(submission_id),
                "validated_by": payload.validated_by,
                "note": payload.note,
            },
        ).mappings().first()

        if not row:
            raise HTTPException(
                status_code=400,
                detail="Submission kan niet naar VALIDATION_IN_PROGRESS worden gezet.",
            )

    return {
        "status": "ok",
        "submission_id": str(row["submission_id"]),
        "validation_status": row["validation_status"],
    }


@router.post("/submissions/{submission_id}/approve")
def approve_submission(submission_id: UUID, payload: ValidationActionIn):
    """
    Planner keurt mobiele submission goed.
    Alleen toegestaan als validation_issue_count = 0 en item_count > 0.
    Schrijft nog NIET naar sb_inspections_v0.
    Werkt ook gekoppelde inspection_plans en inspection_plan_items bij.
    """

    with engine.begin() as conn:
        queue_row = conn.execute(
            text("""
                SELECT *
                FROM vw_mobile_validation_queue
                WHERE submission_id = :submission_id
            """),
            {"submission_id": str(submission_id)},
        ).mappings().first()

        if not queue_row:
            raise HTTPException(status_code=404, detail="Submission niet gevonden.")

        if queue_row["validation_status"] == "APPROVED":
            return {
                "status": "already_approved",
                "submission_id": str(submission_id),
                "validation_status": "APPROVED",
                "write_target": "mobile_staging_only",
                "next_step": "ready_for_promotion_later",
            }

        if queue_row["validation_status"] == "PROMOTED_TO_CANONICAL_DB":
            raise HTTPException(
                status_code=400,
                detail="Submission is al gepromoveerd en kan niet opnieuw worden goedgekeurd.",
            )

        if queue_row["validation_status"] in ("REJECTED", "NEEDS_CORRECTION"):
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Submission kan in deze status niet worden goedgekeurd.",
                    "current_validation_status": queue_row["validation_status"],
                },
            )

        if not queue_row["ready_for_planner_approval"]:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Submission is niet klaar voor planner-goedkeuring.",
                    "item_count": queue_row["item_count"],
                    "validation_issue_count": queue_row["validation_issue_count"],
                },
            )

        row = conn.execute(
            text("""
                UPDATE mobile_inspection_submissions
                SET
                    validation_status = 'APPROVED',
                    validated_by = :validated_by,
                    validated_at = now(),
                    validation_notes = :note,
                    updated_at = now()
                WHERE submission_id = :submission_id
                RETURNING submission_id, validation_status
            """),
            {
                "submission_id": str(submission_id),
                "validated_by": payload.validated_by,
                "note": payload.note,
            },
        ).mappings().first()

        if not row:
            raise HTTPException(
                status_code=400,
                detail="Submission kon niet worden goedgekeurd.",
            )

        # 1. Zet mobiele submission-items op APPROVED
        conn.execute(
            text("""
                UPDATE mobile_inspection_submission_items
                SET
                    validation_status = 'APPROVED',
                    validator_note = COALESCE(:note, validator_note)
                WHERE submission_id = :submission_id
            """),
            {
                "submission_id": str(submission_id),
                "note": payload.note,
            },
        )

        # 2. Zet gekoppelde planregels op APPROVED
        conn.execute(
            text("""
                UPDATE inspection_plan_items pi
                SET
                    status = 'APPROVED',
                    updated_at = now()
                FROM mobile_inspection_submission_items mi
                WHERE mi.plan_item_id = pi.plan_item_id
                  AND mi.submission_id = :submission_id
                  AND mi.plan_item_id IS NOT NULL
                  AND pi.status IN (
                      'SUBMITTED',
                      'PLANNED',
                      'INSPECTED',
                      'NEEDS_RECHECK',
                      'NOT_ACCESSIBLE',
                      'SKIPPED'
                  )
            """),
            {"submission_id": str(submission_id)},
        )

        # 3. Zet gekoppeld plan op APPROVED als alle planregels approved/promoted zijn
        plan_id = conn.execute(
            text("""
                SELECT plan_id
                FROM mobile_inspection_submissions
                WHERE submission_id = :submission_id
            """),
            {"submission_id": str(submission_id)},
        ).scalar()

        if plan_id:
            plan_counts = conn.execute(
                text("""
                    SELECT
                        COUNT(*)::int AS total_items,
                        COUNT(*) FILTER (
                            WHERE status IN ('APPROVED', 'PROMOTED')
                        )::int AS approved_items
                    FROM inspection_plan_items
                    WHERE plan_id = :plan_id
                """),
                {"plan_id": str(plan_id)},
            ).mappings().first()

            if plan_counts:
                next_plan_status = (
                    "APPROVED"
                    if plan_counts["total_items"] > 0
                    and plan_counts["approved_items"] >= plan_counts["total_items"]
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
                              'SUBMITTED',
                              'PARTLY_SUBMITTED',
                              'VALIDATION_IN_PROGRESS',
                              'DOWNLOADED',
                              'IN_PROGRESS',
                              'PUBLISHED'
                          )
                    """),
                    {
                        "plan_id": str(plan_id),
                        "next_plan_status": next_plan_status,
                    },
                )

    return {
        "status": "ok",
        "submission_id": str(row["submission_id"]),
        "validation_status": row["validation_status"],
        "write_target": "mobile_staging_only",
        "next_step": "ready_for_promotion_later",
    }


@router.post("/submissions/{submission_id}/needs-correction")
def needs_correction_submission(submission_id: UUID, payload: ValidationActionIn):
    """
    Planner stuurt submission terug voor correctie.
    """

    with engine.begin() as conn:
        row = conn.execute(
            text("""
                UPDATE mobile_inspection_submissions
                SET
                    validation_status = 'NEEDS_CORRECTION',
                    validated_by = :validated_by,
                    validation_notes = :note,
                    updated_at = now()
                WHERE submission_id = :submission_id
                  AND validation_status <> 'PROMOTED_TO_CANONICAL_DB'
                RETURNING submission_id, validation_status
            """),
            {
                "submission_id": str(submission_id),
                "validated_by": payload.validated_by,
                "note": payload.note,
            },
        ).mappings().first()

        if not row:
            raise HTTPException(
                status_code=400,
                detail="Submission kan niet naar NEEDS_CORRECTION worden gezet.",
            )

        conn.execute(
            text("""
                UPDATE mobile_inspection_submission_items
                SET validation_status = 'NEEDS_CORRECTION',
                    validator_note = :note
                WHERE submission_id = :submission_id
            """),
            {
                "submission_id": str(submission_id),
                "note": payload.note,
            },
        )

    return {
        "status": "ok",
        "submission_id": str(row["submission_id"]),
        "validation_status": row["validation_status"],
    }

@router.post("/submissions/{submission_id}/promote")
def promote_submission_to_canonical(submission_id: UUID, payload: ValidationActionIn):
    """
    Promoveert een APPROVED mobiele submission naar de bestaande canonieke inspectietabellen.

    Schrijft naar:
    - sb_inspections_v0
    - sb_inspection_items_v0

    Alleen toegestaan bij:
    - validation_status = APPROVED
    - geen validatieproblemen
    - minimaal 1 item
    """

    canonical_key = f"MOBILE|{submission_id}"
    source_file = f"MOBILE:{submission_id}"
    sheet = "MOBILE_INSPECTION"

    with engine.begin() as conn:
        queue_row = conn.execute(
            text("""
                SELECT *
                FROM vw_mobile_validation_queue
                WHERE submission_id = :submission_id
            """),
            {"submission_id": str(submission_id)},
        ).mappings().first()

        if not queue_row:
            raise HTTPException(status_code=404, detail="Submission niet gevonden.")

        if queue_row["validation_status"] == "PROMOTED_TO_CANONICAL_DB":
            return {
                "status": "already_promoted",
                "submission_id": str(submission_id),
                "canonical_inspection_key": queue_row["canonical_inspection_key"],
                "write_target": "canonical_db",
            }

        if queue_row["validation_status"] != "APPROVED":
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Alleen APPROVED submissions mogen gepromoveerd worden.",
                    "current_validation_status": queue_row["validation_status"],
                },
            )

        if not queue_row["ready_for_planner_approval"]:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Submission is niet klaar voor promotie.",
                    "item_count": queue_row["item_count"],
                    "validation_issue_count": queue_row["validation_issue_count"],
                },
            )

        header_rows = conn.execute(
            text("""
                WITH first_item AS (
                    SELECT lijn_code
                    FROM mobile_inspection_submission_items
                    WHERE submission_id = :submission_id
                    ORDER BY submitted_at, submission_item_id
                    LIMIT 1
                ),
                item_count AS (
                    SELECT COUNT(*)::int AS row_count
                    FROM mobile_inspection_submission_items
                    WHERE submission_id = :submission_id
                )
                INSERT INTO sb_inspections_v0 (
                    inspection_key,
                    lijn_code,
                    source_file,
                    sheet,
                    sheet_kind,
                    inspected_on,
                    inspected_on_source,
                    performed_by,
                    title,
                    row_count,
                    sheet_norm,
                    customer_code,
                    site_code
                )
                SELECT
                    :canonical_key,
                    COALESCE(
                        NULLIF(first_item.lijn_code, ''),
                        NULLIF(s.sub_area_code, ''),
                        NULLIF(s.basisunit_code, ''),
                        'MOBILE'
                    ) AS lijn_code,
                    :source_file,
                    :sheet,
                    'MOBILE',
                    COALESCE(
                        s.offline_completed_at::date,
                        s.offline_started_at::date,
                        s.submitted_at::date
                    ) AS inspected_on,
                    'mobile_inspection_submissions',
                    COALESCE(s.user_name, s.user_id),
                    CONCAT(
                        'Mobiele inspectie ',
                        COALESCE(s.site_name, s.site_id, ''),
                        ' ',
                        COALESCE(s.sub_area_code, s.basisunit_code, '')
                    ),
                    item_count.row_count,
                    :sheet,
                    s.customer_id,
                    s.site_id
                FROM mobile_inspection_submissions s
                CROSS JOIN item_count
                LEFT JOIN first_item ON true
                WHERE s.submission_id = :submission_id
                ON CONFLICT (inspection_key) DO NOTHING
                RETURNING id
            """),
            {
                "submission_id": str(submission_id),
                "canonical_key": canonical_key,
                "source_file": source_file,
                "sheet": sheet,
            },
        ).mappings().all()

        item_rows = conn.execute(
            text("""
                WITH s AS (
                    SELECT *
                    FROM mobile_inspection_submissions
                    WHERE submission_id = :submission_id
                ),
                numbered_items AS (
                    SELECT
                        i.*,
                        ROW_NUMBER() OVER (
                            ORDER BY i.submitted_at, i.submission_item_id
                        )::int AS canonical_row_nr
                    FROM mobile_inspection_submission_items i
                    WHERE i.submission_id = :submission_id
                )
                INSERT INTO sb_inspection_items_v0 (
                    inspection_key,
                    lijn_code,
                    source_file,
                    sheet,
                    section_idx,
                    row_nr,
                    locatie,
                    band_breedte,
                    merk_type,
                    demontage,
                    reinigen,
                    vervangen,
                    row_json,
                    customer_code,
                    site_code
                )
                SELECT
                    :canonical_key,
                    COALESCE(
                        NULLIF(i.lijn_code, ''),
                        NULLIF(s.sub_area_code, ''),
                        NULLIF(s.basisunit_code, ''),
                        'MOBILE'
                    ) AS lijn_code,
                    :source_file,
                    :sheet,
                    1 AS section_idx,
                    i.canonical_row_nr AS row_nr,
                    COALESCE(
                        NULLIF(i.band_code, ''),
                        NULLIF(i.scraper_position_id, ''),
                        NULLIF(i.scraper_position, ''),
                        NULLIF(i.lijn_code, ''),
                        'MOBILE'
                    ) AS locatie,
                    NULL AS band_breedte,
                    i.scraper_type AS merk_type,
                    (
                        LOWER(COALESCE(i.raw_payload #>> '{actions,demontage}', 'false'))
                            IN ('true', 't', '1', 'x', 'v', 'ja')
                        OR LOWER(COALESCE(i.raw_payload -> 'excel_action_mapping' ->> 'Unnamed: 3', ''))
                            IN ('x', 'v', 'true', 't', '1', 'ja')
                    ) AS demontage,
                    (
                        LOWER(COALESCE(i.raw_payload #>> '{actions,reinigen}', 'false'))
                            IN ('true', 't', '1', 'x', 'v', 'ja')
                        OR LOWER(COALESCE(i.raw_payload -> 'excel_action_mapping' ->> 'Unnamed: 4', ''))
                            IN ('x', 'v', 'true', 't', '1', 'ja')
                    ) AS reinigen,
                    (
                        COALESCE(i.replaced, false)
                        OR LOWER(COALESCE(i.raw_payload #>> '{actions,vervangen}', 'false'))
                            IN ('true', 't', '1', 'x', 'v', 'ja')
                        OR LOWER(COALESCE(i.raw_payload -> 'excel_action_mapping' ->> 'Unnamed: 5', ''))
                            IN ('x', 'v', 'true', 't', '1', 'ja')
                    ) AS vervangen,
                    jsonb_build_object(
                        'source', 'mobile_inspection',
                        'mobile_submission_id', s.submission_id::text,
                        'mobile_submission_item_id', i.submission_item_id::text,
                        'client_submission_id', s.client_submission_id::text,
                        'client_item_id', i.client_item_id::text,

                        'scope_type', i.scope_type,
                        'lijn_code', i.lijn_code,
                        'band_code', i.band_code,
                        'side', i.side,
                        'component_type', i.component_type,

                        'scraper_position_id', i.scraper_position_id,
                        'scraper_position', i.scraper_position,
                        'scraper_role', i.scraper_role,
                        'scraper_type', i.scraper_type,
                        'scraper_family', i.scraper_family,

                        'measurement_type', i.measurement_type,
                        'measurement_value_num', i.measurement_value_num,
                        'measurement_value_text', i.measurement_value_text,
                        'meshoogte_mm', i.meshoogte_mm,

                        'Unnamed: 3',
                            CASE
                                WHEN LOWER(COALESCE(i.raw_payload #>> '{actions,demontage}', 'false'))
                                    IN ('true', 't', '1', 'x', 'v', 'ja')
                                  OR LOWER(COALESCE(i.raw_payload -> 'excel_action_mapping' ->> 'Unnamed: 3', ''))
                                    IN ('x', 'v', 'true', 't', '1', 'ja')
                                    THEN 'X'
                                ELSE NULL
                            END,

                        'Unnamed: 4',
                            CASE
                                WHEN LOWER(COALESCE(i.raw_payload #>> '{actions,reinigen}', 'false'))
                                    IN ('true', 't', '1', 'x', 'v', 'ja')
                                  OR LOWER(COALESCE(i.raw_payload -> 'excel_action_mapping' ->> 'Unnamed: 4', ''))
                                    IN ('x', 'v', 'true', 't', '1', 'ja')
                                    THEN 'X'
                                ELSE NULL
                            END,

                        'Unnamed: 5',
                            CASE
                                WHEN COALESCE(i.replaced, false)
                                  OR LOWER(COALESCE(i.raw_payload #>> '{actions,vervangen}', 'false'))
                                    IN ('true', 't', '1', 'x', 'v', 'ja')
                                  OR LOWER(COALESCE(i.raw_payload -> 'excel_action_mapping' ->> 'Unnamed: 5', ''))
                                    IN ('x', 'v', 'true', 't', '1', 'ja')
                                    THEN 'X'
                                ELSE NULL
                            END,

                        'Unnamed: 6',
                            CASE
                                WHEN LOWER(COALESCE(i.raw_payload #>> '{actions,montage}', 'false'))
                                    IN ('true', 't', '1', 'x', 'v', 'ja')
                                  OR LOWER(COALESCE(i.raw_payload -> 'excel_action_mapping' ->> 'Unnamed: 6', ''))
                                    IN ('x', 'v', 'true', 't', '1', 'ja')
                                    THEN 'X'
                                ELSE NULL
                            END,

                        'Unnamed: 7',
                            CASE
                                WHEN LOWER(COALESCE(i.raw_payload #>> '{actions,afstellen}', 'false'))
                                    IN ('true', 't', '1', 'x', 'v', 'ja')
                                  OR LOWER(COALESCE(i.raw_payload -> 'excel_action_mapping' ->> 'Unnamed: 7', ''))
                                    IN ('x', 'v', 'true', 't', '1', 'ja')
                                    THEN 'X'
                                ELSE NULL
                            END,

                        'Unnamed: 8',
                            CASE
                                WHEN i.meshoogte_mm IS NOT NULL
                                    THEN i.meshoogte_mm::text
                                WHEN i.measurement_value_num IS NOT NULL
                                    THEN i.measurement_value_num::text
                                ELSE NULL
                            END,

                        'condition_code', i.condition_code,
                        'status', i.status,
                        'severity', i.severity,
                        'opmerking', i.opmerking,
                        'action_required', i.action_required,
                        'action_type', i.action_type,
                        'replaced', i.replaced,
                        'asset_match_status', i.asset_match_status,

                        'Klantgegevens ', i.opmerking
                    ) AS row_json,
                    s.customer_id,
                    s.site_id
                FROM numbered_items i
                CROSS JOIN s
                ON CONFLICT (inspection_key, section_idx, row_nr) DO NOTHING
                RETURNING id
            """),
            {
                "submission_id": str(submission_id),
                "canonical_key": canonical_key,
                "source_file": source_file,
                "sheet": sheet,
            },
        ).mappings().all()

        conn.execute(
            text("""
                UPDATE mobile_inspection_submissions
                SET
                    validation_status = 'PROMOTED_TO_CANONICAL_DB',
                    promoted_at = now(),
                    canonical_inspection_key = :canonical_key,
                    validated_by = COALESCE(validated_by, :validated_by),
                    validation_notes = CONCAT_WS(E'\n', validation_notes, :note),
                    updated_at = now()
                WHERE submission_id = :submission_id
            """),
            {
                "submission_id": str(submission_id),
                "canonical_key": canonical_key,
                "validated_by": payload.validated_by,
                "note": payload.note,
            },
        )

        conn.execute(
            text("""
                UPDATE mobile_inspection_submission_items
                SET
                    validation_status = 'PROMOTED_TO_CANONICAL_DB',
                    validator_note = COALESCE(:note, validator_note)
                WHERE submission_id = :submission_id
            """),
            {
                "submission_id": str(submission_id),
                "note": payload.note,
            },
        )

        # 6. Zet gekoppelde planregels op PROMOTED
        conn.execute(
            text("""
                UPDATE inspection_plan_items pi
                SET
                    status = 'PROMOTED',
                    updated_at = now()
                FROM mobile_inspection_submission_items mi
                WHERE mi.plan_item_id = pi.plan_item_id
                  AND mi.submission_id = :submission_id
                  AND mi.plan_item_id IS NOT NULL
                  AND pi.status IN (
                      'SUBMITTED',
                      'APPROVED'
                  )
            """),
            {"submission_id": str(submission_id)},
        )

        # 7. Zet gekoppeld plan op PROMOTED als alle planregels promoted zijn
        plan_id = conn.execute(
            text("""
                SELECT plan_id
                FROM mobile_inspection_submissions
                WHERE submission_id = :submission_id
            """),
            {"submission_id": str(submission_id)},
        ).scalar()

        if plan_id:
            plan_counts = conn.execute(
                text("""
                    SELECT
                        COUNT(*)::int AS total_items,
                        COUNT(*) FILTER (
                            WHERE status = 'PROMOTED'
                        )::int AS promoted_items
                    FROM inspection_plan_items
                    WHERE plan_id = :plan_id
                """),
                {"plan_id": str(plan_id)},
            ).mappings().first()

            if plan_counts:
                next_plan_status = (
                    "PROMOTED"
                    if plan_counts["total_items"] > 0
                    and plan_counts["promoted_items"] >= plan_counts["total_items"]
                    else "APPROVED"
                )

                conn.execute(
                    text("""
                        UPDATE inspection_plans
                        SET
                            status = :next_plan_status,
                            updated_at = now()
                        WHERE plan_id = :plan_id
                          AND status IN (
                              'SUBMITTED',
                              'PARTLY_SUBMITTED',
                              'APPROVED',
                              'VALIDATION_IN_PROGRESS'
                          )
                    """),
                    {
                        "plan_id": str(plan_id),
                        "next_plan_status": next_plan_status,
                    },
                )

        canonical_item_count = conn.execute(
            text("""
                SELECT COUNT(*)::int
                FROM sb_inspection_items_v0
                WHERE inspection_key = :canonical_key
            """),
            {"canonical_key": canonical_key},
        ).scalar_one()

    return {
        "status": "ok",
        "submission_id": str(submission_id),
        "canonical_inspection_key": canonical_key,
        "header_inserted_count": len(header_rows),
        "item_inserted_count": len(item_rows),
        "canonical_item_count": canonical_item_count,
        "validation_status": "PROMOTED_TO_CANONICAL_DB",
        "write_target": "canonical_db",
    }