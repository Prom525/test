-- P3.2b read-only preflight and verification.
-- The output contains only schema metadata and aggregate category counts.

BEGIN READ ONLY;

SET LOCAL statement_timeout = '5s';

WITH expected AS (
    SELECT
        $$CHECK (error_category IS NULL OR (error_category = ANY (ARRAY['routing_error'::text, 'clarification_required'::text, 'specialist_unavailable'::text, 'contract_violation'::text, 'evidence_insufficient'::text, 'research_failed'::text, 'timeout'::text, 'response_projection_error'::text, 'unexpected_exception'::text])))$$::text AS baseline_definition,
        $$CHECK (error_category IS NULL OR (error_category = ANY (ARRAY['routing_error'::text, 'clarification_required'::text, 'specialist_unavailable'::text, 'contract_violation'::text, 'evidence_insufficient'::text, 'research_failed'::text, 'timeout'::text, 'response_projection_error'::text, 'unexpected_exception'::text, 'capability_unsupported'::text])))$$::text AS target_definition
), metadata AS (
    SELECT
        a.atttypid::regtype::text AS error_category_type,
        NOT a.attnotnull AS error_category_is_nullable,
        c.contype::text AS constraint_type,
        c.convalidated,
        pg_get_constraintdef(c.oid, true) AS constraint_definition
    FROM pg_class t
    JOIN pg_namespace n
      ON n.oid = t.relnamespace
    LEFT JOIN pg_attribute a
      ON a.attrelid = t.oid
     AND a.attname = 'error_category'
     AND a.attnum > 0
     AND NOT a.attisdropped
    LEFT JOIN pg_constraint c
      ON c.conrelid = t.oid
     AND c.conname = 'ck_orchestrator_runs_error_category'
    WHERE n.nspname = 'observability'
      AND t.relname = 'orchestrator_runs'
      AND t.relkind IN ('r', 'p')
)
SELECT
    current_database() AS database_name,
    current_schema() AS current_schema,
    CASE
        WHEN error_category_type = 'text'
         AND error_category_is_nullable
         AND constraint_type = 'c'
         AND convalidated
         AND constraint_definition = baseline_definition THEN 'BASELINE'
        WHEN error_category_type = 'text'
         AND error_category_is_nullable
         AND constraint_type = 'c'
         AND convalidated
         AND constraint_definition = target_definition THEN 'TARGET'
        ELSE 'DRIFT_OR_MISSING'
    END AS migration_state,
    error_category_type,
    error_category_is_nullable,
    constraint_type,
    convalidated,
    constraint_definition
FROM metadata
CROSS JOIN expected;

SELECT
    COALESCE(error_category, '<NULL>') AS error_category,
    count(*) AS run_count
FROM observability.orchestrator_runs
GROUP BY error_category
ORDER BY error_category;

COMMIT;
