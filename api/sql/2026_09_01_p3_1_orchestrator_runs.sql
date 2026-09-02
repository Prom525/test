BEGIN;

CREATE SCHEMA IF NOT EXISTS observability;

CREATE TABLE IF NOT EXISTS observability.orchestrator_runs (
    run_id uuid PRIMARY KEY,

    recorded_at timestamptz
        NOT NULL
        DEFAULT now(),

    run_log_contract_version text
        NOT NULL,

    observability_contract_version text,

    operation_id text
        NOT NULL,

    status text
        NOT NULL,

    context_type text,

    query_class text,

    primary_domain text,

    intent text,

    domains jsonb
        NOT NULL
        DEFAULT '[]'::jsonb,

    clarification_required boolean
        NOT NULL
        DEFAULT false,

    research_required boolean
        NOT NULL
        DEFAULT false,

    research_status text,

    service_duration_ms integer
        NOT NULL
        DEFAULT 0
        CHECK (
            service_duration_ms >= 0
        ),

    execution_attempts integer
        NOT NULL
        DEFAULT 0
        CHECK (
            execution_attempts >= 0
        ),

    initial_specialist_calls integer
        NOT NULL
        DEFAULT 0
        CHECK (
            initial_specialist_calls >= 0
        ),

    research_follow_up_specialist_calls integer
        NOT NULL
        DEFAULT 0
        CHECK (
            research_follow_up_specialist_calls >= 0
        ),

    total_specialist_calls integer
        NOT NULL
        DEFAULT 0
        CHECK (
            total_specialist_calls >= 0
        ),

    initial_raw_result_rows integer
        NOT NULL
        DEFAULT 0
        CHECK (
            initial_raw_result_rows >= 0
        ),

    initial_evidence_items integer
        NOT NULL
        DEFAULT 0
        CHECK (
            initial_evidence_items >= 0
        ),

    reconciled_evidence_items integer
        NOT NULL
        DEFAULT 0
        CHECK (
            reconciled_evidence_items >= 0
        ),

    total_ai_calls integer
        NOT NULL
        DEFAULT 0
        CHECK (
            total_ai_calls >= 0
        ),

    response_bytes integer
        NOT NULL
        DEFAULT 0
        CHECK (
            response_bytes >= 0
        ),

    timings_ms jsonb
        NOT NULL
        DEFAULT '{}'::jsonb,

    counts jsonb
        NOT NULL
        DEFAULT '{}'::jsonb
);


CREATE INDEX IF NOT EXISTS
    ix_orchestrator_runs_recorded_at
ON observability.orchestrator_runs (
    recorded_at DESC
);


CREATE INDEX IF NOT EXISTS
    ix_orchestrator_runs_status_recorded
ON observability.orchestrator_runs (
    status,
    recorded_at DESC
);


CREATE INDEX IF NOT EXISTS
    ix_orchestrator_runs_domain_intent_recorded
ON observability.orchestrator_runs (
    primary_domain,
    intent,
    recorded_at DESC
);


COMMENT ON TABLE
    observability.orchestrator_runs
IS
    'PROMATI P3.1 append-only application run log. '
    'Retention and database-level mutation policy '
    'are defined in P3.3.';


COMMIT;
