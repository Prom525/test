BEGIN;


CREATE TABLE
    observability.orchestrator_retention_state (
        policy_name text PRIMARY KEY,

        contract_version text NOT NULL,

        retention_days integer NOT NULL,

        last_attempt_at timestamptz,

        last_success_at timestamptz,

        next_due_at timestamptz NOT NULL,

        last_deleted_count integer NOT NULL
            DEFAULT 0,

        last_status text NOT NULL
            DEFAULT 'never',

        last_sqlstate text,

        updated_at timestamptz NOT NULL
            DEFAULT now(),

        CONSTRAINT
            ck_orchestrator_retention_policy
        CHECK (
            policy_name = 'orchestrator_runs'
        ),

        CONSTRAINT
            ck_orchestrator_retention_contract
        CHECK (
            contract_version =
                'promati.orchestrator.retention_gate.v1'
        ),

        CONSTRAINT
            ck_orchestrator_retention_days
        CHECK (
            retention_days
            BETWEEN 7 AND 3650
        ),

        CONSTRAINT
            ck_orchestrator_retention_deleted_count
        CHECK (
            last_deleted_count >= 0
        ),

        CONSTRAINT
            ck_orchestrator_retention_status
        CHECK (
            last_status IN (
                'never',
                'ok',
                'failed'
            )
        ),

        CONSTRAINT
            ck_orchestrator_retention_sqlstate
        CHECK (
            last_sqlstate IS NULL
            OR last_sqlstate ~ '^[0-9A-Z]{5}$'
        )
    );


INSERT INTO
    observability.orchestrator_retention_state (
        policy_name,
        contract_version,
        retention_days,
        next_due_at
    )
VALUES (
    'orchestrator_runs',
    'promati.orchestrator.retention_gate.v1',
    90,
    now()
);


CREATE OR REPLACE FUNCTION
    observability.run_orchestrator_retention_if_due(
        retain_days integer DEFAULT 90
    )
RETURNS jsonb
LANGUAGE plpgsql
AS $$
DECLARE
    v_state
        observability.orchestrator_retention_state%ROWTYPE;

    v_deleted integer := 0;

    v_now timestamptz := now();
BEGIN

    IF retain_days < 7
       OR retain_days > 3650 THEN

        RAISE EXCEPTION
            'retain_days must be between 7 and 3650';

    END IF;


    INSERT INTO
        observability.orchestrator_retention_state (
            policy_name,
            contract_version,
            retention_days,
            next_due_at
        )
    VALUES (
        'orchestrator_runs',
        'promati.orchestrator.retention_gate.v1',
        retain_days,
        v_now
    )
    ON CONFLICT (
        policy_name
    )
    DO NOTHING;


    SELECT
        s.*
    INTO
        v_state
    FROM
        observability.orchestrator_retention_state s
    WHERE
        s.policy_name =
            'orchestrator_runs'
    FOR UPDATE;


    IF v_state.next_due_at > v_now THEN

        RETURN jsonb_build_object(
            'contract_version',
                'promati.orchestrator.retention_gate.v1',

            'executed',
                false,

            'status',
                'not_due',

            'deleted_count',
                0,

            'next_due_at',
                v_state.next_due_at
        );

    END IF;


    UPDATE
        observability.orchestrator_retention_state
    SET
        retention_days =
            retain_days,

        last_attempt_at =
            v_now,

        next_due_at =
            v_now + interval '1 day',

        updated_at =
            v_now
    WHERE
        policy_name =
            'orchestrator_runs';


    BEGIN

        v_deleted :=
            observability.purge_orchestrator_runs(
                retain_days
            );


        UPDATE
            observability.orchestrator_retention_state
        SET
            last_success_at =
                v_now,

            last_deleted_count =
                v_deleted,

            last_status =
                'ok',

            last_sqlstate =
                NULL,

            updated_at =
                v_now
        WHERE
            policy_name =
                'orchestrator_runs';


        RETURN jsonb_build_object(
            'contract_version',
                'promati.orchestrator.retention_gate.v1',

            'executed',
                true,

            'status',
                'ok',

            'deleted_count',
                v_deleted,

            'next_due_at',
                v_now + interval '1 day'
        );


    EXCEPTION
        WHEN OTHERS THEN

            UPDATE
                observability.orchestrator_retention_state
            SET
                last_deleted_count =
                    0,

                last_status =
                    'failed',

                last_sqlstate =
                    SQLSTATE,

                updated_at =
                    v_now
            WHERE
                policy_name =
                    'orchestrator_runs';


            RETURN jsonb_build_object(
                'contract_version',
                    'promati.orchestrator.retention_gate.v1',

                'executed',
                    true,

                'status',
                    'failed',

                'deleted_count',
                    0,

                'sqlstate',
                    SQLSTATE,

                'next_due_at',
                    v_now + interval '1 day'
            );

    END;

END;
$$;


COMMENT ON FUNCTION
    observability.run_orchestrator_retention_if_due(integer)
IS
    'P3.3b fail-open daily gate for the existing 90-day orchestrator retention policy.';


CREATE OR REPLACE FUNCTION
    observability.trigger_orchestrator_retention_gate()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN

    PERFORM
        observability.run_orchestrator_retention_if_due(
            90
        );


    RETURN NULL;


EXCEPTION
    WHEN OTHERS THEN

        -- Fail-open:
        -- retention failure must never reject
        -- a valid observability INSERT.
        RETURN NULL;

END;
$$;


CREATE TRIGGER
    trg_orchestrator_runs_retention_gate
AFTER INSERT
ON observability.orchestrator_runs
FOR EACH STATEMENT
EXECUTE FUNCTION
    observability.trigger_orchestrator_retention_gate();


COMMENT ON TABLE
    observability.orchestrator_retention_state
IS
    'Operational P3.3b retention state only; no raw question, answer, entity, scope or evidence data.';


COMMIT;
