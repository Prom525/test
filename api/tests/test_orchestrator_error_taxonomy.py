from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import BackgroundTasks

from app.orchestrator import error_taxonomy
from app.orchestrator import run_logging
from app.routers import orchestrator_api


EXPECTED_CATEGORIES = (
    "routing_error",
    "clarification_required",
    "specialist_unavailable",
    "contract_violation",
    "evidence_insufficient",
    "research_failed",
    "timeout",
    "response_projection_error",
    "unexpected_exception",
)


def test_taxonomy_contract_is_exact():

    assert (
        error_taxonomy.ERROR_CATEGORIES
        == EXPECTED_CATEGORIES
    )

    assert (
        error_taxonomy
        .HEALTH_CONTRACT_VERSION
        == "promati.orchestrator.health.v1"
    )


def test_normal_response_is_healthy():

    health = (
        error_taxonomy
        .classify_response(
            {
                "status":
                    "ok",

                "clarification": {
                    "required":
                        False,
                },

                "research": {
                    "status":
                        "not_required",
                },
            }
        )
    )

    assert health == {
        "contract_version":
            "promati.orchestrator.health.v1",

        "status":
            "healthy",

        "category":
            None,
    }


def test_clarification_is_attention():

    health = (
        error_taxonomy
        .classify_response(
            {
                "status":
                    "clarification_required",

                "clarification": {
                    "required":
                        True,
                },
            }
        )
    )

    assert (
        health["status"]
        == "attention"
    )

    assert (
        health["category"]
        == "clarification_required"
    )


def test_specialist_unavailable_is_error():

    health = (
        error_taxonomy
        .classify_response(
            {
                "status":
                    "error",

                "results": [
                    {
                        "accepted":
                            False,

                        "result": {
                            "status":
                                "unavailable",
                        },
                    }
                ],
            }
        )
    )

    assert (
        health["category"]
        == "specialist_unavailable"
    )


def test_contract_violation_is_error():

    health = (
        error_taxonomy
        .classify_response(
            {
                "status":
                    "error",

                "results": [
                    {
                        "result": {
                            "status":
                                "contract_violation",
                        },
                    }
                ],
            }
        )
    )

    assert (
        health["category"]
        == "contract_violation"
    )


def test_evidence_insufficient_is_attention():

    health = (
        error_taxonomy
        .classify_response(
            {
                "status":
                    "ok",

                "evidence_pipeline": {
                    "reconciliation": {
                        "reconciled_assessment": {
                            "status":
                                "insufficient",
                        }
                    }
                },
            }
        )
    )

    assert (
        health["status"]
        == "attention"
    )

    assert (
        health["category"]
        == "evidence_insufficient"
    )


def test_research_failure_is_error():

    health = (
        error_taxonomy
        .classify_response(
            {
                "status":
                    "ok",

                "research": {
                    "status":
                        "failed",
                },
            }
        )
    )

    assert (
        health["category"]
        == "research_failed"
    )


def test_timeout_exception_is_classified():

    health = (
        error_taxonomy
        .classify_exception(
            TimeoutError(
                "synthetic"
            )
        )
    )

    assert (
        health["category"]
        == "timeout"
    )


def test_projection_exception_is_classified():

    def _build_user_answer():
        raise RuntimeError(
            "synthetic"
        )

    try:

        _build_user_answer()

    except RuntimeError as exc:

        health = (
            error_taxonomy
            .classify_exception(
                exc
            )
        )

    assert (
        health["category"]
        == "response_projection_error"
    )


def test_unexpected_exception_is_classified():

    health = (
        error_taxonomy
        .classify_exception(
            RuntimeError(
                "synthetic"
            )
        )
    )

    assert (
        health["category"]
        == "unexpected_exception"
    )


def test_top_level_error_falls_back_to_routing_error():

    health = (
        error_taxonomy
        .classify_response(
            {
                "status":
                    "error",
            }
        )
    )

    assert (
        health["category"]
        == "routing_error"
    )


def test_run_log_record_contains_health_metadata():

    record = (
        run_logging
        .build_orchestrator_run_record(
            {
                "status":
                    "clarification_required",

                "clarification": {
                    "required":
                        True,
                },

                "observability": {
                    "contract_version":
                        "promati.orchestrator.observability.v1",

                    "timings_ms": {
                        "total":
                            10,
                    },

                    "counts":
                        {},
                },
            }
        )
    )

    assert (
        record[
            "health_contract_version"
        ]
        == "promati.orchestrator.health.v1"
    )

    assert (
        record[
            "health_status"
        ]
        == "attention"
    )

    assert (
        record[
            "error_category"
        ]
        == "clarification_required"
    )


def test_router_logs_uncaught_exception_and_reraises():

    background_tasks = (
        BackgroundTasks()
    )

    persisted = []


    def fake_persist(
        response,
    ):

        persisted.append(
            response
        )

        return True


    with patch.object(
        orchestrator_api,
        "run_orchestrator",
        side_effect=TimeoutError(
            "synthetic"
        ),
    ), patch.object(
        orchestrator_api,
        "persist_orchestrator_run",
        side_effect=fake_persist,
    ):

        with pytest.raises(
            TimeoutError
        ):

            orchestrator_api.orchestrator_ask(
                SimpleNamespace(),
                background_tasks,
            )


    assert len(
        persisted
    ) == 1

    assert (
        persisted[0][
            "health"
        ][
            "category"
        ]
        == "timeout"
    )

    assert len(
        background_tasks.tasks
    ) == 0
