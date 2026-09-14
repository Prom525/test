"""Characterize the service-owned task-evidence/P4.6C boundary after 3G2."""
from __future__ import annotations

from copy import deepcopy
import inspect
from types import SimpleNamespace

import pytest

from app.orchestrator import service
from app.orchestrator.models import OrchestratorAskRequest
from app.orchestrator.phase_c_entry_stage import PhaseCEntryResult
from app.orchestrator.product_family_recovery_stage import ProductFamilyRecoveryResult


class NextBoundaryObserved(BaseException):
    pass


class OrdinaryShadowError(Exception):
    pass


class OrdinaryAuthorityError(Exception):
    pass


class TupleCoercionError(Exception):
    pass


class _TupleHostileEvidence:
    def __iter__(self):
        raise TupleCoercionError("tuple coercion failed")


def _install(
    monkeypatch,
    *,
    shadow_return=(),
    authority_return=None,
    shadow_error=None,
    authority_error=None,
    working_evidence=None,
):
    calls = []
    captured = {}
    research_inputs = []
    authority_inputs = []
    shadow_inputs = []
    fallback_calls = []
    plan = SimpleNamespace(
        intent="synthetic_intent",
        clarification_required=False,
        clarification_question=None,
        execution_steps=(),
        research_required=False,
        requested_information=("synthetic",),
        multi_intent=False,
    )
    requirement = object()
    stamp = object()
    sender = object()
    initial = (object(),)
    working = [initial[0], object()] if working_evidence is None else working_evidence
    typed_results = [SimpleNamespace(status="synthetic")]
    raw_results = [{"result": {"status": "ok"}}]
    trace = {"attempts": []}
    counts = service._new_observability_counts()
    before = {
        "plan": deepcopy(vars(plan)),
        "typed": deepcopy(typed_results),
        "raw": deepcopy(raw_results),
        "trace": deepcopy(trace),
        "working": list(working) if isinstance(working, list) else None,
    }

    monkeypatch.setattr(service, "_new_observability_counts", lambda: counts)
    monkeypatch.setattr(service, "run_initial_planning_stage", lambda *a, **k: plan)
    monkeypatch.setattr(service, "_record_initial_execution_observability", lambda *a: None)

    def initial_execution(*args, **kwargs):
        calls.append(("initial_execution", args, kwargs))
        return SimpleNamespace(
            plan=plan,
            task_execution_plans_shadow=(),
            task_execution_plan_comparison_shadow=None,
            task_execution_canary_p4_6b=None,
            typed_execution_results=typed_results,
            results=raw_results,
            trace=trace,
            task_execution_shadow=None,
            task_planner_canary=None,
        )

    monkeypatch.setattr(service, "run_initial_execution_stage", initial_execution)

    entry = PhaseCEntryResult(requirement, stamp, initial, initial)

    def phase_c_entry(*args, **kwargs):
        calls.append(("phase_c_entry", args, kwargs))
        return entry

    monkeypatch.setattr(service, "prepare_phase_c_entry", phase_c_entry)

    recovery = ProductFamilyRecoveryResult(object(), object(), working)

    def recovery_stage(*args, **kwargs):
        calls.append(("recovery", args, kwargs))
        return recovery

    monkeypatch.setattr(service, "run_product_family_recovery_stage", recovery_stage)

    def shadow(actual_plan, evidence, *, now):
        calls.append(("shadow", actual_plan, evidence, now))
        shadow_inputs.append((actual_plan, evidence, now))
        if shadow_error is not None:
            raise shadow_error
        return shadow_return

    monkeypatch.setattr(service, "_assess_intent_task_evidence_shadow", shadow)

    def authority(actual_plan, evidence, *, now, shadow_assessments):
        calls.append(("authority", actual_plan, evidence, now, shadow_assessments))
        authority_inputs.append((actual_plan, evidence, now, shadow_assessments))
        if authority_error is not None:
            raise authority_error
        return authority_return

    monkeypatch.setattr(service, "build_task_evidence_authority_canary_p4_6c", authority)

    def research(shadow_assessments):
        captured.update(inspect.currentframe().f_back.f_locals)
        calls.append(("research", shadow_assessments))
        research_inputs.append(shadow_assessments)
        raise NextBoundaryObserved("research decision boundary")

    monkeypatch.setattr(service, "_derive_intent_task_research_decisions_shadow", research)
    monkeypatch.setattr(service, "has_service_accepted_execution", lambda *a: True)

    def fallback(*args, **kwargs):
        fallback_calls.append((args, kwargs))
        raise AssertionError("outer Phase-C fallback was reached")

    monkeypatch.setattr(service, "_build_user_answer", fallback)
    return SimpleNamespace(
        calls=calls,
        captured=captured,
        research_inputs=research_inputs,
        authority_inputs=authority_inputs,
        shadow_inputs=shadow_inputs,
        fallback_calls=fallback_calls,
        plan=plan,
        stamp=stamp,
        sender=sender,
        initial=initial,
        working=working,
        typed_results=typed_results,
        raw_results=raw_results,
        trace=trace,
        before=before,
    )


def _run(harness):
    with pytest.raises(NextBoundaryObserved, match="research decision boundary"):
        service._p4_15cp3c_previous_run_orchestrator(
            OrchestratorAskRequest(q="synthetic", vraag=""),
            sender=harness.sender,
        )


@pytest.mark.parametrize("shadow_return", [[], (), {"unexpected": "shape"}, None])
def test_shadow_success_is_passed_by_identity_without_copy_or_coercion(
    monkeypatch, shadow_return
):
    authority_return = object()
    harness = _install(
        monkeypatch,
        shadow_return=shadow_return,
        authority_return=authority_return,
    )
    _run(harness)

    assert [call[0] for call in harness.calls] == [
        "initial_execution", "phase_c_entry", "recovery", "shadow", "authority", "research"
    ]
    assert harness.shadow_inputs == [(harness.plan, harness.working, harness.stamp)]
    authority = harness.authority_inputs[0]
    assert authority[0] is harness.plan
    assert authority[1] == tuple(harness.working)
    assert authority[1] is not harness.working
    assert all(actual is expected for actual, expected in zip(authority[1], harness.working))
    assert authority[2] is harness.stamp
    assert authority[3] is shadow_return
    assert harness.research_inputs == [shadow_return]
    assert harness.fallback_calls == []


@pytest.mark.parametrize("authority_return", [[], (), {"unexpected": "shape"}, None, object()])
def test_authority_success_is_retained_exactly_but_not_sent_to_research(
    monkeypatch, authority_return
):
    shadow_return = object()
    harness = _install(
        monkeypatch,
        shadow_return=shadow_return,
        authority_return=authority_return,
    )
    _run(harness)

    assert harness.authority_inputs[0][3] is shadow_return
    assert harness.research_inputs == [shadow_return]
    assert harness.captured["task_evidence_authority_p4_6c"] is authority_return
    assert harness.fallback_calls == []


@pytest.mark.parametrize(
    ("shadow_error", "authority_error", "expected_shadow", "expected_authority_calls"),
    [
        (OrdinaryShadowError("shadow"), None, "default", 1),
        (None, OrdinaryAuthorityError("authority"), "return", 1),
        (OrdinaryShadowError("shadow"), OrdinaryAuthorityError("authority"), "default", 1),
    ],
)
def test_independent_local_fail_open_matrix_reaches_research_without_outer_fallback(
    monkeypatch, shadow_error, authority_error, expected_shadow, expected_authority_calls
):
    shadow_return = object()
    harness = _install(
        monkeypatch,
        shadow_return=shadow_return,
        authority_return=object(),
        shadow_error=shadow_error,
        authority_error=authority_error,
    )
    _run(harness)

    expected = harness.research_inputs[0]
    if expected_shadow == "default":
        assert expected == [] and type(expected) is list
    else:
        assert expected is shadow_return
    assert len(harness.authority_inputs) == expected_authority_calls
    assert harness.authority_inputs[0][3] is expected
    if authority_error is not None:
        assert harness.captured["task_evidence_authority_p4_6c"] is None
    assert harness.fallback_calls == []


def test_tuple_coercion_failure_is_inside_authority_try_and_research_still_receives_shadow(
    monkeypatch
):
    shadow_return = object()
    hostile = _TupleHostileEvidence()
    harness = _install(
        monkeypatch,
        shadow_return=shadow_return,
        authority_return=object(),
        working_evidence=hostile,
    )
    _run(harness)

    assert [call[0] for call in harness.calls] == [
        "initial_execution", "phase_c_entry", "recovery", "shadow", "research"
    ]
    assert harness.authority_inputs == []
    assert harness.research_inputs == [shadow_return]
    assert harness.captured["task_evidence_authority_p4_6c"] is None
    assert harness.fallback_calls == []


def test_shadow_exception_defaults_are_fresh_per_core_call(monkeypatch):
    harness = _install(
        monkeypatch,
        shadow_error=OrdinaryShadowError("shadow"),
        authority_return=object(),
    )
    _run(harness)
    _run(harness)

    first, second = harness.research_inputs
    assert first == second == []
    assert first is not second
    assert harness.authority_inputs[0][3] is first
    assert harness.authority_inputs[1][3] is second


def test_no_stage_is_duplicated_and_orchestration_does_not_mutate_inputs(monkeypatch):
    shadow_return = object()
    authority_return = object()
    harness = _install(
        monkeypatch,
        shadow_return=shadow_return,
        authority_return=authority_return,
    )
    _run(harness)

    names = [call[0] for call in harness.calls]
    assert {name: names.count(name) for name in names} == {
        "initial_execution": 1,
        "phase_c_entry": 1,
        "recovery": 1,
        "shadow": 1,
        "authority": 1,
        "research": 1,
    }
    assert vars(harness.plan) == harness.before["plan"]
    assert harness.typed_results == harness.before["typed"]
    assert harness.raw_results == harness.before["raw"]
    assert harness.trace == harness.before["trace"]
    assert harness.working == harness.before["working"]
    assert all(
        actual is expected
        for actual, expected in zip(harness.working, harness.before["working"])
    )


@pytest.mark.parametrize(
    ("target", "error"),
    [
        ("shadow", KeyboardInterrupt("shadow base exception")),
        ("authority", KeyboardInterrupt("authority base exception")),
    ],
)
def test_baseexception_is_not_swallowed_by_local_exception_boundaries(
    monkeypatch, target, error
):
    harness = _install(
        monkeypatch,
        shadow_return=object(),
        authority_return=object(),
        shadow_error=error if target == "shadow" else None,
        authority_error=error if target == "authority" else None,
    )
    with pytest.raises(KeyboardInterrupt, match=f"{target} base exception"):
        service._p4_15cp3c_previous_run_orchestrator(
            OrchestratorAskRequest(q="synthetic", vraag=""),
            sender=harness.sender,
        )
    assert harness.fallback_calls == []
