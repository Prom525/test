from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.db import SessionLocal


OPERABILITY_CONTRACT_VERSION = (
    "promati.diagnostics.operability.v1"
)


WINDOW_HOURS = (
    24,
    168,
)


def _mapping(
    row: Any,
) -> dict[str, Any]:

    return (
        dict(
            row
        )
        if row is not None
        else {}
    )


def _window_snapshot(
    db: Any,
    hours: int,
) -> dict[str, Any]:

    parameters = {
        "hours":
            int(
                hours
            ),
    }


    summary = _mapping(
        db.execute(
            text(
                """
                SELECT
                    COUNT(*)::integer
                        AS total_runs,

                    COUNT(*) FILTER (
                        WHERE health_status = 'healthy'
                    )::integer
                        AS healthy_runs,

                    COUNT(*) FILTER (
                        WHERE health_status = 'attention'
                    )::integer
                        AS attention_runs,

                    COUNT(*) FILTER (
                        WHERE health_status = 'error'
                    )::integer
                        AS error_runs,

                    COUNT(*) FILTER (
                        WHERE health_status IS NULL
                    )::integer
                        AS unclassified_health_runs,

                    COUNT(*) FILTER (
                        WHERE clarification_required
                    )::integer
                        AS clarification_runs,

                    COUNT(*) FILTER (
                        WHERE research_required
                    )::integer
                        AS research_required_runs,

                    COALESCE(
                        SUM(total_ai_calls),
                        0
                    )::integer
                        AS total_ai_calls,

                    COALESCE(
                        SUM(total_specialist_calls),
                        0
                    )::integer
                        AS total_specialist_calls

                FROM
                    observability.orchestrator_runs

                WHERE
                    recorded_at >=
                        now()
                        - make_interval(
                            hours => :hours
                        )
                """
            ),
            parameters,
        )
        .mappings()
        .first()
    )


    latency = _mapping(
        db.execute(
            text(
                """
                SELECT
                    COUNT(*)::integer
                        AS sample_count,

                    COALESCE(
                        ROUND(
                            AVG(
                                service_duration_ms
                            )
                        ),
                        0
                    )::bigint
                        AS avg_ms,

                    COALESCE(
                        ROUND(
                            percentile_cont(0.50)
                            WITHIN GROUP (
                                ORDER BY
                                    service_duration_ms
                            )
                        ),
                        0
                    )::bigint
                        AS p50_ms,

                    COALESCE(
                        ROUND(
                            percentile_cont(0.95)
                            WITHIN GROUP (
                                ORDER BY
                                    service_duration_ms
                            )
                        ),
                        0
                    )::bigint
                        AS p95_ms,

                    COALESCE(
                        MAX(
                            service_duration_ms
                        ),
                        0
                    )::bigint
                        AS max_ms,

                    COALESCE(
                        ROUND(
                            percentile_cont(0.95)
                            WITHIN GROUP (
                                ORDER BY
                                    response_bytes
                            )
                        ),
                        0
                    )::bigint
                        AS response_bytes_p95

                FROM
                    observability.orchestrator_runs

                WHERE
                    recorded_at >=
                        now()
                        - make_interval(
                            hours => :hours
                        )
                """
            ),
            parameters,
        )
        .mappings()
        .first()
    )


    health = [
        dict(
            row
        )
        for row
        in db.execute(
            text(
                """
                SELECT
                    COALESCE(
                        health_status,
                        'historical_null'
                    ) AS health_status,

                    COALESCE(
                        error_category,
                        'none'
                    ) AS error_category,

                    COUNT(*)::integer
                        AS run_count

                FROM
                    observability.orchestrator_runs

                WHERE
                    recorded_at >=
                        now()
                        - make_interval(
                            hours => :hours
                        )

                GROUP BY
                    health_status,
                    error_category

                ORDER BY
                    run_count DESC,
                    health_status,
                    error_category
                """
            ),
            parameters,
        )
        .mappings()
        .all()
    ]


    routing = [
        dict(
            row
        )
        for row
        in db.execute(
            text(
                """
                SELECT
                    COALESCE(
                        primary_domain,
                        'none'
                    ) AS primary_domain,

                    COALESCE(
                        intent,
                        'none'
                    ) AS intent,

                    COALESCE(
                        status,
                        'none'
                    ) AS status,

                    COUNT(*)::integer
                        AS run_count

                FROM
                    observability.orchestrator_runs

                WHERE
                    recorded_at >=
                        now()
                        - make_interval(
                            hours => :hours
                        )

                GROUP BY
                    primary_domain,
                    intent,
                    status

                ORDER BY
                    run_count DESC,
                    primary_domain,
                    intent,
                    status

                LIMIT 20
                """
            ),
            parameters,
        )
        .mappings()
        .all()
    ]


    research = [
        dict(
            row
        )
        for row
        in db.execute(
            text(
                """
                SELECT
                    research_required,

                    COALESCE(
                        research_status,
                        'none'
                    ) AS research_status,

                    COUNT(*)::integer
                        AS run_count,

                    COALESCE(
                        SUM(
                            total_ai_calls
                        ),
                        0
                    )::integer
                        AS total_ai_calls,

                    COALESCE(
                        SUM(
                            research_follow_up_specialist_calls
                        ),
                        0
                    )::integer
                        AS follow_up_specialist_calls

                FROM
                    observability.orchestrator_runs

                WHERE
                    recorded_at >=
                        now()
                        - make_interval(
                            hours => :hours
                        )

                GROUP BY
                    research_required,
                    research_status

                ORDER BY
                    run_count DESC,
                    research_required,
                    research_status
                """
            ),
            parameters,
        )
        .mappings()
        .all()
    ]


    latency_by_route = [
        dict(
            row
        )
        for row
        in db.execute(
            text(
                """
                SELECT
                    COALESCE(
                        primary_domain,
                        'none'
                    ) AS primary_domain,

                    COALESCE(
                        intent,
                        'none'
                    ) AS intent,

                    COUNT(*)::integer
                        AS run_count,

                    COALESCE(
                        ROUND(
                            AVG(
                                service_duration_ms
                            )
                        ),
                        0
                    )::bigint
                        AS avg_ms,

                    COALESCE(
                        ROUND(
                            percentile_cont(0.95)
                            WITHIN GROUP (
                                ORDER BY
                                    service_duration_ms
                            )
                        ),
                        0
                    )::bigint
                        AS p95_ms,

                    COALESCE(
                        MAX(
                            service_duration_ms
                        ),
                        0
                    )::bigint
                        AS max_ms

                FROM
                    observability.orchestrator_runs

                WHERE
                    recorded_at >=
                        now()
                        - make_interval(
                            hours => :hours
                        )

                GROUP BY
                    primary_domain,
                    intent

                ORDER BY
                    p95_ms DESC,
                    run_count DESC

                LIMIT 20
                """
            ),
            parameters,
        )
        .mappings()
        .all()
    ]


    return {
        "hours":
            int(
                hours
            ),

        "summary":
            summary,

        "latency":
            latency,

        "health":
            health,

        "routing":
            routing,

        "research":
            research,

        "latency_by_route":
            latency_by_route,
    }


def build_operability_snapshot(
) -> dict[str, Any]:

    db = SessionLocal()

    try:

        windows = {
            "24h":
                _window_snapshot(
                    db,
                    24,
                ),

            "7d":
                _window_snapshot(
                    db,
                    168,
                ),
        }


        retention = _mapping(
            db.execute(
                text(
                    """
                    SELECT
                        policy_name,
                        contract_version,
                        retention_days,
                        last_attempt_at,
                        last_success_at,
                        next_due_at,
                        last_deleted_count,
                        last_status,
                        last_sqlstate

                    FROM
                        observability.orchestrator_retention_state

                    WHERE
                        policy_name =
                            'orchestrator_runs'
                    """
                )
            )
            .mappings()
            .first()
        )


        older_than_90d = int(
            db.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM
                        observability.orchestrator_runs
                    WHERE
                        recorded_at
                        < now()
                          - interval '90 days'
                    """
                )
            ).scalar()
            or 0
        )


        return {
            "contract_version":
                OPERABILITY_CONTRACT_VERSION,

            "status":
                "ok",

            "windows":
                windows,

            "retention":
                retention,

            "older_than_90d":
                older_than_90d,
        }


    finally:

        db.rollback()
        db.close()
