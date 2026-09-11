-- 2026_07_06_mobile_inspection_validation_rules.sql
-- Validatieregels en validatieviews voor mobiele inspecties
-- Readiness-controle vóór planner-goedkeuring en promotie

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_inspection_plans_status'
    ) THEN
        ALTER TABLE inspection_plans
        ADD CONSTRAINT chk_inspection_plans_status
        CHECK (
            status IN (
                'DRAFT',
                'READY_FOR_REVIEW',
                'PUBLISHED',
                'DOWNLOADED',
                'IN_PROGRESS',
                'PARTLY_SUBMITTED',
                'SUBMITTED',
                'VALIDATION_IN_PROGRESS',
                'APPROVED',
                'PROMOTED',
                'REPORT_GENERATED',
                'CLOSED',
                'CANCELLED'
            )
        );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_inspection_plan_items_scope_type'
    ) THEN
        ALTER TABLE inspection_plan_items
        ADD CONSTRAINT chk_inspection_plan_items_scope_type
        CHECK (
            scope_type IN (
                'BAND',
                'BAND_SIDE_COMPONENT',
                'SCRAPER_POSITION',
                'TRANSFER_POINT',
                'PERFORMANCE_MEASUREMENT',
                'ENVIRONMENT_MEASUREMENT',
                'LOCATION_OBSERVATION'
            )
        );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_inspection_plan_items_status'
    ) THEN
        ALTER TABLE inspection_plan_items
        ADD CONSTRAINT chk_inspection_plan_items_status
        CHECK (
            status IN (
                'PLANNED',
                'SKIPPED',
                'INSPECTED',
                'NOT_ACCESSIBLE',
                'NEEDS_RECHECK',
                'SUBMITTED',
                'APPROVED',
                'REJECTED',
                'PROMOTED'
            )
        );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_mobile_submissions_validation_status'
    ) THEN
        ALTER TABLE mobile_inspection_submissions
        ADD CONSTRAINT chk_mobile_submissions_validation_status
        CHECK (
            validation_status IN (
                'WAITING_FOR_PLANNER_VALIDATION',
                'VALIDATION_IN_PROGRESS',
                'NEEDS_CORRECTION',
                'REJECTED',
                'APPROVED',
                'READY_FOR_PROMOTION',
                'PROMOTION_FAILED',
                'PROMOTED_TO_CANONICAL_DB'
            )
        );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_mobile_items_validation_status'
    ) THEN
        ALTER TABLE mobile_inspection_submission_items
        ADD CONSTRAINT chk_mobile_items_validation_status
        CHECK (
            validation_status IN (
                'WAITING_FOR_PLANNER_VALIDATION',
                'VALIDATION_IN_PROGRESS',
                'NEEDS_CORRECTION',
                'REJECTED',
                'APPROVED',
                'READY_FOR_PROMOTION',
                'PROMOTION_FAILED',
                'PROMOTED_TO_CANONICAL_DB'
            )
        );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_mobile_items_scope_type'
    ) THEN
        ALTER TABLE mobile_inspection_submission_items
        ADD CONSTRAINT chk_mobile_items_scope_type
        CHECK (
            scope_type IN (
                'BAND',
                'BAND_SIDE_COMPONENT',
                'SCRAPER_POSITION',
                'TRANSFER_POINT',
                'PERFORMANCE_MEASUREMENT',
                'ENVIRONMENT_MEASUREMENT',
                'LOCATION_OBSERVATION'
            )
        );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_pdf_jobs_status'
    ) THEN
        ALTER TABLE inspection_pdf_jobs
        ADD CONSTRAINT chk_pdf_jobs_status
        CHECK (
            status IN (
                'QUEUED',
                'RUNNING',
                'FAILED',
                'GENERATED',
                'PUBLISHED'
            )
        );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_mobile_submission_promoted_requires_key'
    ) THEN
        ALTER TABLE mobile_inspection_submissions
        ADD CONSTRAINT chk_mobile_submission_promoted_requires_key
        CHECK (
            validation_status <> 'PROMOTED_TO_CANONICAL_DB'
            OR canonical_inspection_key IS NOT NULL
        );
    END IF;
END $$;


CREATE OR REPLACE VIEW vw_mobile_submission_validation_issues AS

SELECT
    s.submission_id,
    NULL::uuid AS submission_item_id,
    'HEADER'::text AS issue_scope,
    'CUSTOMER_MISSING'::text AS issue_code,
    'Klant ontbreekt op mobiele inspectie.'::text AS issue_message
FROM mobile_inspection_submissions s
WHERE COALESCE(TRIM(s.customer_id), '') = ''
   OR COALESCE(TRIM(s.customer_name), '') = ''

UNION ALL

SELECT
    s.submission_id,
    NULL::uuid AS submission_item_id,
    'HEADER'::text AS issue_scope,
    'SITE_MISSING'::text AS issue_code,
    'Locatie/site ontbreekt op mobiele inspectie.'::text AS issue_message
FROM mobile_inspection_submissions s
WHERE COALESCE(TRIM(s.site_id), '') = ''
   OR COALESCE(TRIM(s.site_name), '') = ''

UNION ALL

SELECT
    s.submission_id,
    NULL::uuid AS submission_item_id,
    'HEADER'::text AS issue_scope,
    'INSPECTION_DATE_MISSING'::text AS issue_code,
    'Inspectiedatum ontbreekt: offline_started_at en offline_completed_at zijn leeg.'::text AS issue_message
FROM mobile_inspection_submissions s
WHERE s.offline_started_at IS NULL
  AND s.offline_completed_at IS NULL

UNION ALL

SELECT
    i.submission_id,
    i.submission_item_id,
    'ITEM'::text AS issue_scope,
    'LIJN_CODE_MISSING'::text AS issue_code,
    'Lijn_code ontbreekt of is UNKNOWN.'::text AS issue_message
FROM mobile_inspection_submission_items i
WHERE COALESCE(TRIM(i.lijn_code), '') = ''
   OR UPPER(TRIM(i.lijn_code)) = 'UNKNOWN'
   OR UPPER(TRIM(i.lijn_code)) = 'ONBEKEND'

UNION ALL

SELECT
    i.submission_id,
    i.submission_item_id,
    'ITEM'::text AS issue_scope,
    'BAND_CODE_MISSING'::text AS issue_code,
    'Band_code ontbreekt of is UNKNOWN.'::text AS issue_message
FROM mobile_inspection_submission_items i
WHERE COALESCE(TRIM(i.band_code), '') = ''
   OR UPPER(TRIM(i.band_code)) = 'UNKNOWN'
   OR UPPER(TRIM(i.band_code)) = 'ONBEKEND'

UNION ALL

SELECT
    i.submission_id,
    i.submission_item_id,
    'ITEM'::text AS issue_scope,
    'SCRAPER_POSITION_MISSING'::text AS issue_code,
    'Schraperpositie ontbreekt bij scope_type SCRAPER_POSITION.'::text AS issue_message
FROM mobile_inspection_submission_items i
WHERE i.scope_type = 'SCRAPER_POSITION'
  AND COALESCE(TRIM(i.scraper_position_id), TRIM(i.scraper_position), '') = ''

UNION ALL

SELECT
    i.submission_id,
    i.submission_item_id,
    'ITEM'::text AS issue_scope,
    'MESHOOGTE_MISSING'::text AS issue_code,
    'Measurement_type is MESHOOGTE maar meshoogte_mm ontbreekt.'::text AS issue_message
FROM mobile_inspection_submission_items i
WHERE UPPER(COALESCE(i.measurement_type, '')) = 'MESHOOGTE'
  AND i.meshoogte_mm IS NULL
  AND i.measurement_value_num IS NULL

UNION ALL

SELECT
    i.submission_id,
    i.submission_item_id,
    'ITEM'::text AS issue_scope,
    'ASSET_PENDING_MAPPING'::text AS issue_code,
    'Assetmapping staat nog op PENDING_MAPPING.'::text AS issue_message
FROM mobile_inspection_submission_items i
WHERE i.asset_match_status = 'PENDING_MAPPING'

UNION ALL

SELECT
    i.submission_id,
    i.submission_item_id,
    'ITEM'::text AS issue_scope,
    'EMPTY_ITEM'::text AS issue_code,
    'Inspectieregel bevat geen status, meting, opmerking, actie of vervanging.'::text AS issue_message
FROM mobile_inspection_submission_items i
WHERE i.status IS NULL
  AND i.measurement_value_num IS NULL
  AND i.measurement_value_text IS NULL
  AND i.meshoogte_mm IS NULL
  AND i.condition_code IS NULL
  AND i.opmerking IS NULL
  AND i.action_required IS NULL
  AND i.replaced IS NULL;


CREATE OR REPLACE VIEW vw_mobile_validation_queue AS
SELECT
    s.submission_id,
    s.client_submission_id,
    s.plan_id,
    s.user_id,
    s.user_name,
    s.device_id,
    s.customer_id,
    s.customer_name,
    s.site_id,
    s.site_name,
    s.basisunit_code,
    s.sub_area_code,
    s.submitted_at,
    s.validation_status,
    s.validated_by,
    s.validated_at,
    s.promoted_at,
    s.canonical_inspection_key,

    COUNT(i.submission_item_id)::int AS item_count,
    COUNT(v.issue_code)::int AS validation_issue_count,

    CASE
        WHEN COUNT(i.submission_item_id) = 0 THEN false
        WHEN COUNT(v.issue_code) > 0 THEN false
        WHEN s.validation_status IN ('REJECTED', 'NEEDS_CORRECTION', 'PROMOTED_TO_CANONICAL_DB') THEN false
        ELSE true
    END AS ready_for_planner_approval

FROM mobile_inspection_submissions s
LEFT JOIN mobile_inspection_submission_items i
       ON i.submission_id = s.submission_id
LEFT JOIN vw_mobile_submission_validation_issues v
       ON v.submission_id = s.submission_id
GROUP BY
    s.submission_id,
    s.client_submission_id,
    s.plan_id,
    s.user_id,
    s.user_name,
    s.device_id,
    s.customer_id,
    s.customer_name,
    s.site_id,
    s.site_name,
    s.basisunit_code,
    s.sub_area_code,
    s.submitted_at,
    s.validation_status,
    s.validated_by,
    s.validated_at,
    s.promoted_at,
    s.canonical_inspection_key;