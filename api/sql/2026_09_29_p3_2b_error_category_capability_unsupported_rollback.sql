-- P3.2b rollback: restore the exact pre-P3.2b CHECK only when safe.
--
-- This never deletes or rewrites append-only run records.  It refuses to run
-- if any capability_unsupported record exists, because that row is not valid
-- under the legacy constraint.

BEGIN;

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '15s';

LOCK TABLE observability.orchestrator_runs IN ACCESS EXCLUSIVE MODE;

DO $$
DECLARE
    expected_target constant text :=
        $definition$CHECK (error_category IS NULL OR (error_category = ANY (ARRAY['routing_error'::text, 'clarification_required'::text, 'specialist_unavailable'::text, 'contract_violation'::text, 'evidence_insufficient'::text, 'research_failed'::text, 'timeout'::text, 'response_projection_error'::text, 'unexpected_exception'::text, 'capability_unsupported'::text])))$definition$;
    actual_definition text;
    actual_type "char";
    actual_validated boolean;
    error_category_type regtype;
    error_category_not_null boolean;
    unsupported_run_count bigint;
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
            'P3.2b rollback mismatch: observability.orchestrator_runs.error_category must be nullable text';
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
       OR NOT actual_validated
       OR actual_definition <> expected_target THEN
        RAISE EXCEPTION
            'P3.2b rollback mismatch: expected the exact validated P3.2b target CHECK';
    END IF;

    SELECT count(*)
    INTO unsupported_run_count
    FROM observability.orchestrator_runs
    WHERE error_category = 'capability_unsupported';

    IF unsupported_run_count <> 0 THEN
        RAISE EXCEPTION
            'P3.2b rollback refused: % capability_unsupported run record(s) must be retained',
            unsupported_run_count;
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
                'unexpected_exception'
            )
        );
END;
$$;

COMMIT;
