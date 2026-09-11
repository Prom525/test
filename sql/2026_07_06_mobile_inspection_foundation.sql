-- 2026_07_06_mobile_inspection_foundation.sql
-- Basis voor PROMATI mobiel inspectieplatform
-- Maakt alleen nieuwe staging/planning/pdf-tabellen aan
-- Schrijft NIET naar sb_inspections_v0 of sb_inspection_items_v0

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS inspection_plans (
    plan_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_date date NOT NULL,
    customer_id text NOT NULL,
    customer_name text NOT NULL,
    site_id text NOT NULL,
    site_name text NOT NULL,
    basisunit_code text,
    sub_area_code text,
    assigned_user_id text,
    assigned_user_name text,
    status text NOT NULL DEFAULT 'DRAFT',
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    published_at timestamptz,
    closed_at timestamptz,
    remarks text
);

CREATE TABLE IF NOT EXISTS inspection_plan_items (
    plan_item_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id uuid NOT NULL REFERENCES inspection_plans(plan_id) ON DELETE CASCADE,

    sort_order int,
    scope_type text NOT NULL,

    customer_id text,
    site_id text,
    basisunit_code text,
    sub_area_code text,
    lijn_code text,
    band_code text,

    side text,
    component_type text,
    transfer_point_id text,

    scraper_position_id text,
    scraper_position text,
    scraper_role text,
    scraper_type text,
    scraper_family text,

    bulk_material_type text,

    previous_inspection_date date,
    previous_meshoogte_mm numeric,
    previous_condition_code text,
    previous_value_display text,
    previous_comment text,
    previous_advice text,

    required_measurements jsonb NOT NULL DEFAULT '[]'::jsonb,
    required_photos boolean NOT NULL DEFAULT false,

    priority int,
    planner_note text,
    status text NOT NULL DEFAULT 'PLANNED',

    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS mobile_inspection_submissions (
    submission_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    client_submission_id uuid UNIQUE NOT NULL,

    plan_id uuid REFERENCES inspection_plans(plan_id),
    user_id text NOT NULL,
    user_name text,
    device_id text NOT NULL,

    customer_id text,
    customer_name text,
    site_id text,
    site_name text,
    basisunit_code text,
    sub_area_code text,

    offline_started_at timestamptz,
    offline_completed_at timestamptz,
    submitted_at timestamptz NOT NULL DEFAULT now(),

    status text NOT NULL DEFAULT 'SUBMITTED',
    validation_status text NOT NULL DEFAULT 'WAITING_FOR_PLANNER_VALIDATION',

    validated_by text,
    validated_at timestamptz,
    promoted_at timestamptz,
    canonical_inspection_key text UNIQUE,

    raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    validation_notes text,

    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS mobile_inspection_submission_items (
    submission_item_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id uuid NOT NULL REFERENCES mobile_inspection_submissions(submission_id) ON DELETE CASCADE,
    client_item_id uuid UNIQUE NOT NULL,

    plan_item_id uuid REFERENCES inspection_plan_items(plan_item_id),

    scope_type text NOT NULL,

    lijn_code text,
    band_code text,
    side text,
    component_type text,
    transfer_point_id text,

    scraper_position_id text,
    scraper_position text,
    scraper_role text,
    scraper_type text,
    scraper_family text,

    measurement_type text,
    measurement_value_num numeric,
    measurement_value_text text,
    meshoogte_mm numeric,
    condition_code text,

    status text,
    severity text,
    opmerking text,
    action_required boolean,
    action_type text,
    replaced boolean,

    ambient_temperature_c numeric,
    relative_humidity_pct numeric,
    material_moisture_pct numeric,
    material_condition text,
    belt_load text,
    production_state text,

    asset_match_status text NOT NULL DEFAULT 'MATCHED',

    offline_created_at timestamptz,
    submitted_at timestamptz NOT NULL DEFAULT now(),

    validation_status text NOT NULL DEFAULT 'WAITING_FOR_PLANNER_VALIDATION',
    validator_note text,

    raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS mobile_inspection_photos (
    photo_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    client_photo_id uuid UNIQUE NOT NULL,

    submission_id uuid NOT NULL REFERENCES mobile_inspection_submissions(submission_id) ON DELETE CASCADE,
    submission_item_id uuid REFERENCES mobile_inspection_submission_items(submission_item_id) ON DELETE CASCADE,

    file_name text,
    content_type text,
    storage_bucket text,
    storage_key text,
    thumbnail_key text,

    taken_at timestamptz,
    uploaded_at timestamptz NOT NULL DEFAULT now(),

    gps_lat numeric,
    gps_lon numeric,

    status text NOT NULL DEFAULT 'UPLOADED',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS inspection_pdf_jobs (
    pdf_job_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id uuid REFERENCES mobile_inspection_submissions(submission_id),
    inspection_key text,
    report_template_code text NOT NULL DEFAULT 'PROMATI_INSPECTION_DEFAULT',
    status text NOT NULL DEFAULT 'QUEUED',
    requested_by text,
    requested_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    finished_at timestamptz,
    error_message text,
    output_file_id text,
    output_url text
);