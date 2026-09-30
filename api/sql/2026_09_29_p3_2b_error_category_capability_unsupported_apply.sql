-- P3.2b: permit the already-classified capability_unsupported outcome.
--
-- Run only through psql with ON_ERROR_STOP=1 after the paired read-only
-- check script reports BASELINE.  This script is intentionally fail-closed:
-- it accepts only the exact P3.2 baseline or its exact target state.

BEGIN;

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '15s';

LOCK TABLE observability.orchestrator_runs IN ACCESS EXCLUSIVE MODE;

DO $$
DECLARE
    expected_baseline constant text :=
        $definition$CHECK (error_category IS NULL OR (error_category = ANY (ARRAY['routing_error'::text, 'clarification_required'::text, 'specialist_unavailable'::text, 'contract_violation'::text, 'evidence_insufficient'::text, 'research_failed'::text, 'timeout'::text, 'response_projection_error'::text, 'unexpected_exception'::text])))$definition$;
    expected_target constant text :=
        $definition$CHECK (error_category IS NULL OR (error_category = ANY (ARRAY['routing_error'::text, 'clarification_required'::text, 'specialist_unavailable'::text, 'contract_violation'::text, 'evidence_insufficient'::text, 'research_failed'::text, 'timeout'::text, 'response_projection_error'::text, 'unexpected_exception'::text, 'capability_unsupported'::text])))$definition$;
    actual_definition text;
    actual_type "char";
    actual_validated boolean;
    error_category_type regtype;
    error_category_not_null boolean;
BEGIN
    SELECT
        a.atttypid::regtype,
        a.attnotnull
    INTO
        error_category_type,
        error_category_not_null
    FROM pg_attribute a
    WHERE a.attrelid = 'observability.orchestrator_runs'::regclass
      AND a.attname = 'error_category'
      AND a.attnum > 0
      AND NOT a.attisdropped;

    IF NOT FOUND
       OR error_category_type <> 'text'::regtype
       OR error_category_not_null THEN
        RAISE EXCEPTION
            'P3.2b baseline mismatch: observability.orchestrator_runs.error_category must be nullable text';
    END IF;

    SELECT
        c.contype,
        c.convalidated,
        pg_get_constraintdef(c.oid, true)
    INTO
        actual_type,
        actual_validated,
        actual_definition
    FROM pg_constraint c
    WHERE c.conrelid = 'observability.orchestrator_runs'::regclass
      AND c.conname = 'ck_orchestrator_runs_error_category';

    IF NOT FOUND
       OR actual_type <> 'c'
       OR NOT actual_validated THEN
        RAISE EXCEPTION
            'P3.2b baseline mismatch: expected validated CHECK ck_orchestrator_runs_error_category';
    END IF;

    IF actual_definition = expected_target THEN
        RAISE NOTICE 'P3.2b target already installed; no change made';
        RETURN;
    END IF;

    IF actual_definition <> expected_baseline THEN
        RAISE EXCEPTION
            'P3.2b baseline mismatch: refusing to replace unexpected error_category CHECK definition';
    END IF;

    ALTER TABLE observability.orchestrator_runs
        DROP CONSTRAINT ck_orchestrator_runs_error_category;

    ALTER TABLE observability.orchestrator_runs
        ADD CONSTRAINT ck_orchestrator_runs_error_category
        CHECK (
            error_category IS NULL
            OR error_category IN (
                'routing_error',
                'clarification_required',
                'specialist_unavailable',
                'contract_violation',
                'evidence_insufficient',
                'research_failed',
                'timeout',
                'response_projection_error',
                'unexpected_exception',
                'capability_unsupported'
            )
        );
END;
$$;

COMMIT;
