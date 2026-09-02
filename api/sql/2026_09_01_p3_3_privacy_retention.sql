BEGIN;


ALTER TABLE observability.orchestrator_runs
    ADD COLUMN privacy_contract_version text;


ALTER TABLE observability.orchestrator_runs
    ADD CONSTRAINT
        ck_orchestrator_runs_privacy_contract
    CHECK (
        privacy_contract_version IS NULL
        OR privacy_contract_version =
            'promati.orchestrator.privacy.v1'
    );


CREATE OR REPLACE FUNCTION
    observability.guard_orchestrator_runs_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN

    IF TG_OP = 'UPDATE' THEN

        RAISE EXCEPTION
            'observability.orchestrator_runs is append-only; UPDATE is forbidden'
            USING ERRCODE = '55000';

    END IF;


    IF TG_OP = 'DELETE' THEN

        IF COALESCE(
            current_setting(
                'promati.observability_retention',
                true
            ),
            ''
        ) <> 'on' THEN

            RAISE EXCEPTION
                'observability.orchestrator_runs DELETE requires controlled retention context'
                USING ERRCODE = '55000';

        END IF;


        RETURN OLD;

    END IF;


    IF TG_OP = 'TRUNCATE' THEN

        RAISE EXCEPTION
            'observability.orchestrator_runs TRUNCATE is forbidden'
            USING ERRCODE = '55000';

    END IF;


    RETURN OLD;

END;
$$;


CREATE TRIGGER
    trg_orchestrator_runs_append_only
BEFORE UPDATE OR DELETE
ON observability.orchestrator_runs
FOR EACH ROW
EXECUTE FUNCTION
    observability.guard_orchestrator_runs_mutation();


CREATE TRIGGER
    trg_orchestrator_runs_no_truncate
BEFORE TRUNCATE
ON observability.orchestrator_runs
FOR EACH STATEMENT
EXECUTE FUNCTION
    observability.guard_orchestrator_runs_mutation();


CREATE OR REPLACE FUNCTION
    observability.purge_orchestrator_runs(
        retain_days integer DEFAULT 90
    )
RETURNS integer
LANGUAGE plpgsql
AS $$
DECLARE
    deleted_count integer;
BEGIN

    IF retain_days < 7
       OR retain_days > 3650 THEN

        RAISE EXCEPTION
            'retain_days must be between 7 and 3650';

    END IF;


    PERFORM set_config(
        'promati.observability_retention',
        'on',
        true
    );


    DELETE FROM
        observability.orchestrator_runs
    WHERE
        recorded_at
        < now()
          - make_interval(
                days => retain_days
            );


    GET DIAGNOSTICS
        deleted_count = ROW_COUNT;


    RETURN deleted_count;

END;
$$;


COMMENT ON FUNCTION
    observability.purge_orchestrator_runs(integer)
IS
    'Controlled P3.3 retention entrypoint. Default retention: 90 days.';


COMMENT ON COLUMN
    observability.orchestrator_runs.privacy_contract_version
IS
    'Privacy contract applied at persistence time. NULL identifies pre-P3.3 rows.';


COMMIT;
