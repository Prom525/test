-- 2026_07_06_mobile_inspection_indexes.sql
-- Indexes voor PROMATI mobiel inspectieplatform

CREATE INDEX IF NOT EXISTS idx_inspection_plans_date_user
ON inspection_plans(plan_date, assigned_user_id);

CREATE INDEX IF NOT EXISTS idx_plan_items_plan
ON inspection_plan_items(plan_id);

CREATE INDEX IF NOT EXISTS idx_mobile_submissions_validation
ON mobile_inspection_submissions(validation_status, submitted_at);

CREATE INDEX IF NOT EXISTS idx_mobile_submission_items_submission
ON mobile_inspection_submission_items(submission_id);

CREATE INDEX IF NOT EXISTS idx_mobile_submission_items_asset
ON mobile_inspection_submission_items(lijn_code, band_code, scraper_position_id);

CREATE INDEX IF NOT EXISTS idx_mobile_photos_submission
ON mobile_inspection_photos(submission_id, submission_item_id);

CREATE INDEX IF NOT EXISTS idx_pdf_jobs_status
ON inspection_pdf_jobs(status, requested_at);