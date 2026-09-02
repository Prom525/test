BEGIN;

ALTER TABLE observability.orchestrator_runs
    ADD COLUMN health_contract_version text;

ALTER TABLE observability.orchestrator_runs
    ADD COLUMN health_status text;

ALTER TABLE observability.orchestrator_runs
    ADD COLUMN error_category text;


ALTER TABLE observability.orchestrator_runs
    ADD CONSTRAINT ck_orchestrator_runs_health_status
    CHECK (
        health_status IS NULL
        OR health_status IN (
            'healthy',
            'attention',
            'error'
        )
    );


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


CREATE INDEX
    ix_orchestrator_runs_error_category_recorded
ON observability.orchestrator_runs (
    error_category,
    recorded_at DESC
);


COMMIT;
