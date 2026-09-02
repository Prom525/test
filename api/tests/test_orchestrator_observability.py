from __future__ import annotations

import itertools
import json
from types import SimpleNamespace
from unittest.mock import patch

from app.orchestrator import service


class _JsonModel:
    def __init__(
        self,
        **values,
    ):
        self.__dict__.update(
            values
        )

    def model_dump(
        self,
        mode="python",
    ):
        del mode
        return dict(
            self.__dict__
        )

    def json(self):
        return json.dumps(
            self.__dict__
        )


def _plan():
    return _JsonModel(
        intent="diagnostics",
        clarification_required=False,
        clarification_question=None,
        execution_steps=[
            _JsonModel(
                step_id="step-1"
            ),
            _JsonModel(
                step_id="step-2"
            ),
        ],
        research_required=True,
        requested_information=[],
    )


def _run(
    *,
    include_trace=False,
    fail_phase_c=False,
):
    plan = _plan()

    results = [
        {
            "step_id": "step-1",
            "domain": "inspection",
            "action": "analysis_assistant",
            "endpoint": "/analysis/assistant/ask",
            "accepted": True,
            "result": {
                "status": "ok",
                "value": 1,
            },
        },
        {
            "step_id": "step-2",
            "domain": "technical",
            "action": "technical_assistant",
            "endpoint": "/technical/assistant/ask",
            "accepted": True,
            "result": {
                "status": "ok",
                "value": 2,
            },
        },
    ]

    trace = _JsonModel(
        attempts=[
            _JsonModel(
                result_count=3,
                duration_ms=11,
            ),
            _JsonModel(
                result_count=7,
                duration_ms=13,
            ),
        ],
        fallback_used=False,
        clarification_used=False,
    )

    def execute_plan(
        observed_plan,
        sender=None,
        shadow_observer=None,
    ):
        del sender

        assert observed_plan is plan

        if shadow_observer is not None:
            shadow_observer(
                SimpleNamespace(
                    step_id="step-1"
                )
            )
            shadow_observer(
                SimpleNamespace(
                    step_id="step-2"
                )
            )

        return (
            results,
            trace,
        )

    requirement_set = (
        SimpleNamespace(
            requirement_set_id="req-set-obs",
            intent="diagnostics",
        )
    )

    assessment = {
        "status": "insufficient",
        "requirement_results": [],
        "missing_required_requirement_ids": [
            "REQ_A",
        ],
        "conflicting_requirement_ids": [],
    }

    decision = {
        "status": "required",
        "research_required": True,
        "target_requirement_ids": [
            "REQ_A",
        ],
    }

    research_execution = {
        "status": "completed",
        "research_performed": True,
        "initial_results": results,
        "combined_results": results,
        "agent_metadata": {
            "follow_up_specialist_calls": 2,
            "total_ai_calls_used": 3,
        },
    }

    reconciliation = {
        "status": "improved",
        "research_status": "completed",
        "initial_evidence_items": [
            {
                "evidence_id": "e1",
            },
            {
                "evidence_id": "e2",
            },
        ],
        "reconciled_evidence_items": [
            {
                "evidence_id": "e1",
            },
            {
                "evidence_id": "e2",
            },
            {
                "evidence_id": "e3",
            },
            {
                "evidence_id": "e4",
            },
        ],
        "added_evidence_ids": [
            "e3",
            "e4",
        ],
        "discarded_result_count": 0,
        "initial_assessment": assessment,
        "reconciled_assessment": {
            **assessment,
            "status": "sufficient",
            "missing_required_requirement_ids": [],
        },
        "reasons": [],
    }

    synthesis = {
        "status": "complete",
        "claims": [],
        "warnings": [],
    }

    plan_research = {
        "status": "ok",
        "answer": "research answer",
        "ai_calls_used": 0,
        "agent": {
            "follow_up_specialist_calls": 1,
            "total_ai_calls_used": 2,
        },
    }

    ticks = itertools.count(
        start=0.0,
        step=0.01,
    )

    def next_tick():
        return next(
            ticks
        )

    def assess_side_effect(
        *args,
        **kwargs,
    ):
        del args, kwargs

        if fail_phase_c:
            raise RuntimeError(
                "forced-assessment-failure"
            )

        return assessment

    patches = (
        patch.object(
            service,
            "_observability_now",
            side_effect=next_tick,
        ),
        patch.object(
            service,
            "understand_query",
            return_value=plan,
        ),
        patch.object(
            service,
            "assess_research_requirement",
            return_value=plan,
        ),
        patch.object(
            service,
            "build_execution_plan",
            return_value=plan,
        ),
        patch.object(
            service,
            "execute_plan",
            side_effect=execute_plan,
        ),
        patch.object(
            service,
            "get_requirement_set",
            return_value=requirement_set,
        ),
        patch.object(
            service,
            "normalize_execution_result_evidence",
            return_value=(
                {
                    "evidence_id": "normalized"
                },
            ),
        ),
        patch.object(
            service,
            "assess_evidence",
            side_effect=assess_side_effect,
        ),
        patch.object(
            service,
            "decide_research_requirement",
            return_value=decision,
        ),
        patch.object(
            service,
            "execute_bounded_research",
            return_value=research_execution,
        ),
        patch.object(
            service,
            "reconcile_evidence",
            return_value=reconciliation,
        ),
        patch.object(
            service,
            "synthesize_grounded_evidence",
            return_value=synthesis,
        ),
        patch.object(
            service,
            "_research_agent_enabled",
            return_value=True,
        ),
        patch.object(
            service,
            "run_bounded_research_agent",
            return_value=plan_research,
        ),
        patch.object(
            service,
            "_build_user_answer",
            return_value="legacy answer",
        ),
        patch.object(
            service,
            "repair_mojibake_text",
            side_effect=lambda value: value,
        ),
    )

    with patches[0], \
         patches[1], \
         patches[2], \
         patches[3], \
         patches[4], \
         patches[5], \
         patches[6], \
         patches[7], \
         patches[8], \
         patches[9], \
         patches[10], \
         patches[11], \
         patches[12], \
         patches[13], \
         patches[14], \
         patches[15]:

        response = service.run_orchestrator(
            SimpleNamespace(
                q=None,
                vraag="testvraag",
                include_trace=include_trace,
                conversation_context=None,
            )
        )

    return response


def test_observability_uses_existing_runtime_signals():
    response = _run(
        include_trace=False
    )

    assert response["status"] == "ok"
    assert response["answer"] == "research answer"
    assert response["trace"] is None

    observability = response[
        "observability"
    ]

    assert (
        observability["contract_version"]
        == "promati.orchestrator.observability.v1"
    )

    counts = observability[
        "counts"
    ]

    assert counts[
        "execution_attempts"
    ] == 2

    assert counts[
        "initial_specialist_calls"
    ] == 2

    assert counts[
        "initial_raw_result_rows"
    ] == 10

    assert counts[
        "initial_evidence_items"
    ] == 2

    assert counts[
        "reconciled_evidence_items"
    ] == 4

    assert counts[
        "phase_c_research_follow_up_specialist_calls"
    ] == 2

    assert counts[
        "plan_research_follow_up_specialist_calls"
    ] == 1

    assert counts[
        "research_follow_up_specialist_calls"
    ] == 3

    assert counts[
        "total_specialist_calls"
    ] == 5

    assert counts[
        "phase_c_ai_calls"
    ] == 3

    assert counts[
        "plan_research_ai_calls"
    ] == 2

    assert counts[
        "total_ai_calls"
    ] == 5


def test_observability_timings_are_compact_nonnegative_ms():
    response = _run(
        include_trace=False
    )

    timings = response[
        "observability"
    ]["timings_ms"]

    expected = {
        "understanding",
        "research_requirement",
        "planning",
        "initial_specialist",
        "evidence_requirement_lookup",
        "evidence_normalization",
        "evidence_assessment",
        "evidence_research_gate",
        "evidence_research",
        "reconciliation",
        "synthesis",
        "plan_research",
        "presentation",
        "response_build",
        "total",
    }

    assert set(
        timings
    ) == expected

    for value in timings.values():
        assert isinstance(
            value,
            int,
        )
        assert value >= 0

    assert timings[
        "total"
    ] > 0


def test_observability_survives_phase_c_fail_open():
    response = _run(
        include_trace=False,
        fail_phase_c=True,
    )

    assert response[
        "evidence_pipeline"
    ] is None

    observability = response[
        "observability"
    ]

    counts = observability[
        "counts"
    ]

    assert counts[
        "initial_specialist_calls"
    ] == 2

    assert counts[
        "initial_evidence_items"
    ] == 2

    assert counts[
        "phase_c_ai_calls"
    ] == 0

    assert counts[
        "plan_research_ai_calls"
    ] == 2

    assert counts[
        "total_ai_calls"
    ] == 2


def test_observability_coexists_with_full_trace():
    response = _run(
        include_trace=True
    )

    assert response[
        "trace"
    ] is not None

    assert (
        response[
            "observability"
        ][
            "counts"
        ][
            "execution_attempts"
        ]
        == 2
    )