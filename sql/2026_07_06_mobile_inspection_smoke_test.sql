-- 2026_07_06_mobile_inspection_smoke_test.sql
-- Veilige test: maakt tijdelijke testdata aan en doet daarna ROLLBACK

BEGIN;

-- ------------------------------------------------------------
-- 1. Geldige mobiele submission
-- ------------------------------------------------------------
WITH s AS (
    INSERT INTO mobile_inspection_submissions (
        client_submission_id,
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
        offline_completed_at
    )
    VALUES (
        '11111111-1111-1111-1111-111111111111',
        'test-user',
        'Test Monteur',
        'test-device-001',
        'TATA_STEEL',
        'TATA Steel',
        'IJMUIDEN',
        'IJmuiden',
        'GSL',
        'MV2',
        now(),
        now()
    )
    RETURNING submission_id
)
INSERT INTO mobile_inspection_submission_items (
    submission_id,
    client_item_id,
    scope_type,
    lijn_code,
    band_code,
    scraper_position_id,
    scraper_position,
    scraper_role,
    scraper_type,
    scraper_family,
    measurement_type,
    meshoogte_mm,
    condition_code,
    status,
    severity,
    opmerking,
    action_required,
    replaced,
    asset_match_status,
    offline_created_at
)
SELECT
    submission_id,
    '22222222-2222-2222-2222-222222222222',
    'SCRAPER_POSITION',
    'MV2',
    'E950',
    'E950_SEC_01',
    'Secundair',
    'SECUNDAIR',
    'R 1200-1050 SP/M3',
    'R',
    'MESHOOGTE',
    5.0,
    'OK',
    'OK',
    'LOW',
    'Smoke test geldige inspectieregel',
    false,
    false,
    'MATCHED',
    now()
FROM s;


-- ------------------------------------------------------------
-- 2. Ongeldige mobiele submission
-- ------------------------------------------------------------
WITH s AS (
    INSERT INTO mobile_inspection_submissions (
        client_submission_id,
        user_id,
        user_name,
        device_id,
        customer_id,
        customer_name,
        site_id,
        site_name,
        offline_started_at
    )
    VALUES (
        '33333333-3333-3333-3333-333333333333',
        'test-user',
        'Test Monteur',
        'test-device-001',
        '',
        '',
        '',
        '',
        NULL
    )
    RETURNING submission_id
)
INSERT INTO mobile_inspection_submission_items (
    submission_id,
    client_item_id,
    scope_type,
    lijn_code,
    band_code,
    measurement_type,
    asset_match_status
)
SELECT
    submission_id,
    '44444444-4444-4444-4444-444444444444',
    'SCRAPER_POSITION',
    '',
    '',
    'MESHOOGTE',
    'PENDING_MAPPING'
FROM s;


-- ------------------------------------------------------------
-- 3. Resultaat validatiequeue
-- Verwacht:
-- geldige submission: ready_for_planner_approval = true
-- ongeldige submission: ready_for_planner_approval = false
-- ------------------------------------------------------------
SELECT
    client_submission_id,
    item_count,
    validation_issue_count,
    ready_for_planner_approval
FROM vw_mobile_validation_queue
WHERE client_submission_id IN (
    '11111111-1111-1111-1111-111111111111',
    '33333333-3333-3333-3333-333333333333'
)
ORDER BY client_submission_id;


-- ------------------------------------------------------------
-- 4. Validatieproblemen van ongeldige submission
-- ------------------------------------------------------------
SELECT
    s.client_submission_id,
    v.issue_scope,
    v.issue_code,
    v.issue_message
FROM vw_mobile_submission_validation_issues v
JOIN mobile_inspection_submissions s
  ON s.submission_id = v.submission_id
WHERE s.client_submission_id = '33333333-3333-3333-3333-333333333333'
ORDER BY v.issue_scope, v.issue_code;


-- Alles terugdraaien: er blijft geen testdata staan
ROLLBACK;