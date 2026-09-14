"""Contract tests for the mechanical observability leaf-module extraction."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.orchestrator import observability_stage, service


TIMING_KEYS = (
    "understanding", "research_requirement", "planning",
    "initial_specialist", "evidence_requirement_lookup",
    "evidence_normalization", "evidence_assessment",
    "evidence_research_gate", "evidence_research", "reconciliation",
    "synthesis", "plan_research", "presentation", "response_build", "total",
)

COUNT_KEYS = (
    "execution_attempts", "initial_specialist_calls",
    "phase_c_research_follow_up_specialist_calls",
    "plan_research_follow_up_specialist_calls",
    "research_follow_up_specialist_calls", "total_specialist_calls",
    "initial_raw_result_rows", "initial_evidence_items",
    "reconciled_evidence_items", "phase_c_ai_calls", "plan_research_ai_calls",
    "total_ai_calls", "multi_intent_queries",
    "task_execution_plan_shadow_evaluations", "task_execution_plan_shadow_tasks",
    "task_execution_plan_shadow_steps",
    "task_execution_plan_shadow_planning_errors",
    "task_execution_plan_shadow_exact_matches",
    "task_research_execution_canary_executions",
    "task_research_execution_canary_follow_up_specialist_calls",
    "public_composition_canary_evaluations",
    "public_composition_canary_enabled_requests",
    "public_composition_canary_eligible_requests",
    "public_composition_canary_activations",
    "public_composition_canary_public_answer_replacements",
    "public_composition_canary_legacy_answer_fallbacks",
    "public_composition_canary_internal_error_fallbacks",
    "task_public_composition_requests", "task_public_composition_enabled",
    "task_public_composition_eligible", "task_public_composition_authoritative",
    "task_public_composition_answer_replaced", "task_public_composition_fail_open",
    "task_public_composition_included_units",
    "task_public_composition_included_claims", "task_public_composition_blocked",
    "task_public_composition_reason_activated",
    "task_public_composition_reason_disabled",
    "task_public_composition_reason_blocked_not_multi_intent",
    "task_public_composition_reason_blocked_coverage_not_ready",
    "task_public_composition_reason_internal_error_fail_open",
    "task_public_composition_reason_blocked_other",
)


def test_leaf_module_has_explicit_small_surface_and_no_forbidden_imports():
    expected = {
        "ORCHESTRATOR_OBSERVABILITY_CONTRACT_VERSION",
        "_new_observability_counts", "_new_observability_timings",
        "_observability_get", "_observability_nonnegative_int",
        "_record_initial_execution_observability",
        "_record_public_composition_canary_release_observability",
        "_record_task_execution_plan_shadow_observability",
    }
    assert set(observability_stage.__all__) == expected
    tree = ast.parse(Path(observability_stage.__file__).read_text(encoding="utf-8"))
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert not any(
        token in name.casefold()
        for name in imports
        for token in ("fastapi", "router", "database", "sqlalchemy", "requests", "httpx")
    )


def test_exact_initial_maps_are_fresh_and_service_uses_extracted_symbols():
    timings = observability_stage._new_observability_timings()
    counts = observability_stage._new_observability_counts()
    assert timings == dict.fromkeys(TIMING_KEYS, 0)
    assert counts == dict.fromkeys(COUNT_KEYS, 0)
    assert observability_stage._new_observability_timings() is not timings
    assert observability_stage._new_observability_counts() is not counts
    for name in observability_stage.__all__:
        assert getattr(service, name) is getattr(observability_stage, name)


@pytest.mark.parametrize(("value", "expected"), [
    (None, 0), ("bad", 0), (-4, 0), ("-3", 0), (True, 0), (False, 0),
    (3.9, 3), ("5", 5), (7, 7),
])
def test_nonnegative_integer_coercion_is_exact(value, expected):
    assert observability_stage._observability_nonnegative_int(value) == expected


def test_mapping_and_attribute_access_preserves_missing_defaults():
    assert observability_stage._observability_get({"value": 3}, "value") == 3
    assert observability_stage._observability_get({}, "missing", "fallback") == "fallback"
    assert observability_stage._observability_get(SimpleNamespace(value=4), "value") == 4
    assert observability_stage._observability_get(None, "missing", 8) == 8


@pytest.mark.parametrize(
    ("trace", "expected_attempts", "expected_rows"),
    [
        ({"attempts": [{"result_count": 3}, SimpleNamespace(result_count="4")]}, 2, 7),
        (SimpleNamespace(attempts=({"result_count": 2},)), 1, 2),
        ({"attempts": None}, 0, 0),
        ({"attempts": "malformed"}, 0, 0),
        ({}, 0, 0),
        (None, 0, 0),
    ],
)
def test_initial_execution_metrics_cover_mapping_object_and_attempt_shapes(
    trace, expected_attempts, expected_rows
):
    counts = {"untouched": 91}
    results = [object(), object()]
    before = list(results)
    observability_stage._record_initial_execution_observability(
        counts, trace, results
    )
    assert counts == {
        "untouched": 91,
        "execution_attempts": expected_attempts,
        "initial_specialist_calls": 2,
        "initial_raw_result_rows": expected_rows,
    }
    assert results == before


def test_initial_execution_result_count_conversion_and_privacy_are_exact():
    sentinel = "PRIVATE-question-answer-evidence-entity-scope-specialist-token"
    attempts = [
        {"result_count": 5, "payload": sentinel},
        SimpleNamespace(result_count="6", payload=sentinel),
        {"result_count": -7},
        {"result_count": True},
        {},
        {"result_count": "invalid"},
    ]
    counts = {"preserved": 1}
    observability_stage._record_initial_execution_observability(
        counts, {"attempts": attempts, "question": sentinel}, (object(),)
    )
    assert counts == {
        "preserved": 1,
        "execution_attempts": 6,
        "initial_specialist_calls": 1,
        "initial_raw_result_rows": 11,
    }
    assert sentinel not in repr(counts)


def test_initial_execution_preserves_len_exception_for_unsuitable_results():
    with pytest.raises(TypeError):
        observability_stage._record_initial_execution_observability(
            {}, {"attempts": []}, object()
        )


def test_service_timing_wrapper_records_on_exception_and_remains_patchable(monkeypatch):
    ticks = iter((1.0, 1.025))
    monkeypatch.setattr(service, "_observability_now", lambda: next(ticks))
    timings = {}
    with pytest.raises(RuntimeError, match="sentinel"):
        service._observability_call(
            timings, "phase", lambda: (_ for _ in ()).throw(RuntimeError("sentinel"))
        )
    assert timings == {"phase": 25}


def test_task_plan_shadow_metrics_cover_normal_empty_and_malformed_contracts():
    counts = observability_stage._new_observability_counts()
    pipeline = {
        "task_execution_plans_shadow": [
            {"execution_steps": [{}, {}], "status": "ok", "question": "SECRET"},
            {"execution_steps": [{}], "status": "planning_error", "scope": "SECRET"},
            "malformed",
        ],
        "task_execution_plan_comparison_shadow": {"exact_match": True},
    }
    observability_stage._record_task_execution_plan_shadow_observability(
        counts, SimpleNamespace(multi_intent=True), pipeline
    )
    assert counts["task_execution_plan_shadow_evaluations"] == 1
    assert counts["task_execution_plan_shadow_tasks"] == 3
    assert counts["task_execution_plan_shadow_steps"] == 3
    assert counts["task_execution_plan_shadow_planning_errors"] == 1
    assert counts["task_execution_plan_shadow_exact_matches"] == 1
    unchanged = observability_stage._new_observability_counts()
    observability_stage._record_task_execution_plan_shadow_observability(
        unchanged, SimpleNamespace(multi_intent=False), None
    )
    assert unchanged == observability_stage._new_observability_counts()
    observability_stage._record_task_execution_plan_shadow_observability(None, None, None)


def test_release_metrics_are_exact_for_replaced_fallback_authority_and_statuses():
    counts = observability_stage._new_observability_counts()
    pipeline = {
        "task_research_execution_canary_shadow": [
            {"executed": True, "follow_up_specialist_calls": 2},
            {"executed": True, "follow_up_specialist_calls": -9},
            {"executed": False, "follow_up_specialist_calls": 100},
        ],
        "public_composition_canary_shadow": {
            "enabled": True, "eligible": True, "activated": False,
            "public_answer_replaced": False,
            "reason": "blocked_internal_error_fail_open",
        },
        "task_public_composition_authority_p4_6f": {
            "enabled": True, "eligible": True, "authoritative": False,
            "public_answer_replaced": False, "included_unit_count": "3",
            "included_claim_count": True,
            "reason": "blocked_missing_task_synthesis_coverage",
        },
    }
    observability_stage._record_public_composition_canary_release_observability(
        counts, SimpleNamespace(multi_intent=True), pipeline
    )
    expected = observability_stage._new_observability_counts()
    expected.update({
        "multi_intent_queries": 1,
        "task_research_execution_canary_executions": 2,
        "task_research_execution_canary_follow_up_specialist_calls": 2,
        "public_composition_canary_evaluations": 1,
        "public_composition_canary_enabled_requests": 1,
        "public_composition_canary_eligible_requests": 1,
        "public_composition_canary_legacy_answer_fallbacks": 1,
        "public_composition_canary_internal_error_fallbacks": 1,
        "task_public_composition_requests": 1,
        "task_public_composition_enabled": 1,
        "task_public_composition_eligible": 1,
        "task_public_composition_included_units": 3,
        "task_public_composition_blocked": 1,
        "task_public_composition_fail_open": 1,
        "task_public_composition_reason_blocked_coverage_not_ready": 1,
    })
    assert counts == expected


@pytest.mark.parametrize("pipeline", [None, [], "bad", {}, {"public_composition_canary_shadow": None}])
def test_release_metrics_preserve_defaults_for_missing_or_malformed_maps(pipeline):
    counts = observability_stage._new_observability_counts()
    observability_stage._record_public_composition_canary_release_observability(
        counts, SimpleNamespace(multi_intent=False), pipeline
    )
    assert counts == observability_stage._new_observability_counts()


def test_content_sentinels_never_enter_observability_output():
    sentinel = "PRIVATE-question-answer-evidence-entity-scope-specialist-token"
    counts = observability_stage._new_observability_counts()
    pipeline = {
        "question": sentinel, "answer": sentinel, "evidence": sentinel,
        "entity": sentinel, "scope": sentinel, "specialist_payload": sentinel,
        "token": sentinel,
        "task_execution_plans_shadow": [
            {"execution_steps": [], "status": "ok", "content": sentinel}
        ],
        "public_composition_canary_shadow": {
            "enabled": True, "eligible": True, "activated": True,
            "public_answer_replaced": True, "reason": sentinel,
        },
    }
    plan = SimpleNamespace(multi_intent=True, question=sentinel, entities={"x": sentinel})
    observability_stage._record_task_execution_plan_shadow_observability(counts, plan, pipeline)
    observability_stage._record_public_composition_canary_release_observability(counts, plan, pipeline)
    assert sentinel not in repr(counts)
    assert set(counts) == set(COUNT_KEYS)
