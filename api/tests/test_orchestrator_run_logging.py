from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import BackgroundTasks

from app.orchestrator import run_logging
from app.routers import orchestrator_api


def _response():
    return {
        "status":
            "ok",

        "context_type":
            "orchestrator",

        "question":
            "SECRET QUESTION",

        "answer":
            "SECRET ANSWER",

        "query_plan": {
            "original_question":
                "SECRET ORIGINAL",

            "normalized_question":
                "SECRET NORMALIZED",

            "query_class":
                "inspection",

            "primary_domain":
                "inspection",

            "domains": [
                "inspection"
            ],

            "intent":
                "replacement_advice",

            "entities": {
                "band":
                    "SECRET ENTITY"
            },

            "clarification_required":
                False,

            "research_required":
                True,
        },

        "research": {
            "status":
                "completed",

            "required":
                True,
        },

        "clarification": {
            "required":
                False,
        },

        "trace": {
            "secret":
                "SECRET TRACE"
        },

        "results": [
            {
                "result":
                    "SECRET SPECIALIST"
            }
        ],

        "observability": {
            "contract_version":
                "promati.orchestrator.observability.v1",

            "timings_ms": {
                "total":
                    123,

                "planning":
                    10,
            },

            "counts": {
                "execution_attempts":
                    2,

                "initial_specialist_calls":
                    2,

                "research_follow_up_specialist_calls":
                    1,

                "total_specialist_calls":
                    3,

                "initial_raw_result_rows":
                    20,

                "initial_evidence_items":
                    4,

                "reconciled_evidence_items":
                    5,

                "total_ai_calls":
                    1,
            },
        },
    }


def test_record_contains_no_raw_content():

    record = (
        run_logging
        .build_orchestrator_run_record(
            _response()
        )
    )

    serialized = json.dumps(
        record,
        ensure_ascii=False,
    )

    for secret in (
        "SECRET QUESTION",
        "SECRET ANSWER",
        "SECRET ORIGINAL",
        "SECRET NORMALIZED",
        "SECRET ENTITY",
        "SECRET TRACE",
        "SECRET SPECIALIST",
    ):

        assert secret not in serialized


    assert (
        record[
            "run_log_contract_version"
        ]
        == "promati.orchestrator.run_log.v1"
    )

    assert (
        record[
            "primary_domain"
        ]
        == "inspection"
    )

    assert (
        record[
            "intent"
        ]
        == "replacement_advice"
    )

    assert (
        record[
            "service_duration_ms"
        ]
        == 123
    )

    assert (
        record[
            "total_specialist_calls"
        ]
        == 3
    )

    assert (
        record[
            "total_ai_calls"
        ]
        == 1
    )

    assert (
        record[
            "response_bytes"
        ]
        > 0
    )


def test_persistence_is_fail_open():

    with patch.object(
        run_logging,
        "SessionLocal",
        side_effect=RuntimeError(
            "forced-db-failure"
        ),
    ):

        assert (
            run_logging
            .persist_orchestrator_run(
                _response()
            )
            is False
        )


def test_persistence_commits_single_insert():

    session = MagicMock()

    with patch.object(
        run_logging,
        "SessionLocal",
        return_value=session,
    ):

        assert (
            run_logging
            .persist_orchestrator_run(
                _response()
            )
            is True
        )


    assert (
        session.execute.call_count
        == 1
    )

    assert (
        session.commit.call_count
        == 1
    )

    assert (
        session.close.call_count
        == 1
    )


def test_router_schedules_background_logging():

    background_tasks = (
        BackgroundTasks()
    )

    fake_response = (
        _response()
    )

    with patch.object(
        orchestrator_api,
        "run_orchestrator",
        return_value=fake_response,
    ):

        result = (
            orchestrator_api
            .orchestrator_ask(
                SimpleNamespace(),
                background_tasks,
            )
        )


    assert (
        result
        is fake_response
    )

    assert len(
        background_tasks.tasks
    ) == 1

    task = (
        background_tasks
        .tasks[0]
    )

    assert (
        task.func
        is run_logging.persist_orchestrator_run
    )
