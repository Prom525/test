"""Characterize the research-decision/P4.6D1 boundary after 3H2."""
from __future__ import annotations

from copy import deepcopy
import inspect
from types import SimpleNamespace

import pytest

from app.orchestrator import service
from app.orchestrator.models import OrchestratorAskRequest
from app.orchestrator.phase_c_entry_stage import PhaseCEntryResult
from app.orchestrator.product_family_recovery_stage import ProductFamilyRecoveryResult
from app.orchestrator.task_evidence_stage import TaskEvidenceStageResult


class ContextBoundaryObserved(BaseException):
    pass


class GuardBoundaryObserved(BaseException):
    pass


class OrdinaryShadowError(Exception):
    pass


class OrdinaryAuthorityError(Exception):
    pass


class ListResultsError(Exception):
    pass


class _HostileResults:
    def __init__(self):
        self.iterations = 0

    def __iter__(self):
        self.iterations += 1
        if self.iterations == 1:
            raise ListResultsError("list(results)")
        return iter(())


def _install(
    monkeypatch,
    *,
    shadow_return=(),
    authority_return=None,
    shadow_error=None,
    authority_error=None,
    raw_results=None,
):
    actual_context_stage = service.run_task_research_context_stage
    calls = []
    frames = []
    context_inputs = []
    stage_outputs = []
    shadow_entry_defaults = []
    authority_entry_defaults = []
    plan = SimpleNamespace(
        intent="synthetic",
        clarification_required=False,
        clarification_question=None,
        execution_steps=(),
        research_required=False,
        requested_information=("synthetic",),
        multi_intent=False,
    )
    sender = object()
    stamp = object()
    initial_evidence = (object(),)
    working_evidence = [initial_evidence[0], object()]
    typed_results = [SimpleNamespace(status="synthetic")]
    results = [object(), object()] if raw_results is None else raw_results
    trace = {"attempts": []}
    evidence_shadow = object()
    evidence_authority = object()
    before = {
        "plan": deepcopy(vars(plan)),
        "typed": deepcopy(typed_results),
        "results": list(results) if isinstance(results, list) else None,
        "trace": deepcopy(trace),
        "working": list(working_evidence),
    }

    monkeypatch.setattr(service, "_new_observability_counts", lambda: {})
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
            results=results,
            trace=trace,
            task_execution_shadow=None,
            task_planner_canary=None,
        )

    monkeypatch.setattr(service, "run_initial_execution_stage", initial_execution)

    def phase_c_entry(*args, **kwargs):
        calls.append(("phase_c_entry", args, kwargs))
        return PhaseCEntryResult(object(), stamp, initial_evidence, initial_evidence)

    monkeypatch.setattr(service, "prepare_phase_c_entry", phase_c_entry)

    def recovery(*args, **kwargs):
        calls.append(("product_recovery", args, kwargs))
        return ProductFamilyRecoveryResult(object(), object(), working_evidence)

    monkeypatch.setattr(service, "run_product_family_recovery_stage", recovery)

    def evidence_stage(actual_plan, actual_evidence, actual_stamp, **dependencies):
        calls.append(("task_evidence_stage", actual_plan, actual_evidence, actual_stamp, dependencies))
        output = TaskEvidenceStageResult(evidence_shadow, evidence_authority)
        stage_outputs.append(output)
        return output

    monkeypatch.setattr(service, "run_task_evidence_stage", evidence_stage)

    def shadow(actual_evidence_shadow):
        shadow_entry_defaults.append(
            inspect.currentframe().f_back.f_locals["task_research_decisions_shadow"]
        )
        calls.append(("research_decision_shadow", actual_evidence_shadow))
        assert actual_evidence_shadow is evidence_shadow
        if shadow_error is not None:
            raise shadow_error
        return shadow_return

    monkeypatch.setattr(service, "_derive_intent_task_research_decisions_shadow", shadow)

    def authority(actual_evidence_authority, actual_shadow):
        authority_entry_defaults.append(
            inspect.currentframe().f_back.f_locals["task_research_authority_p4_6d1"]
        )
        calls.append(("p4_6d1", actual_evidence_authority, actual_shadow))
        if authority_error is not None:
            raise authority_error
        return authority_return

    monkeypatch.setattr(service, "build_task_research_authority_canary_p4_6d1", authority)

    def context(actual_plan, actual_results, actual_shadow):
        calls.append(("research_context", actual_plan, actual_results, actual_shadow))
        context_inputs.append((actual_plan, actual_results, actual_shadow))
        raise ContextBoundaryObserved("next research context boundary")

    monkeypatch.setattr(service, "_derive_intent_task_research_contexts_shadow", context)

    def context_stage(*args, **dependencies):
        frames.append(dict(inspect.currentframe().f_back.f_locals))
        return actual_context_stage(*args, **dependencies)

    monkeypatch.setattr(service, "run_task_research_context_stage", context_stage)
    monkeypatch.setattr(service, "has_service_accepted_execution", lambda *a: True)
    monkeypatch.setattr(
        service,
        "_build_user_answer",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("outer fallback reached")),
    )
    return SimpleNamespace(**locals())


def _run(harness):
    with pytest.raises(ContextBoundaryObserved, match="next research context boundary"):
        service._p4_15cp3c_previous_run_orchestrator(
            OrchestratorAskRequest(q="synthetic", vraag=""), sender=harness.sender
        )


@pytest.mark.parametrize(
    "shadow_return", [[], (), {"shape": "mapping"}, None, object()]
)
def test_shadow_success_is_unmodified_and_p4_6d1_receives_exact_stage_and_shadow_objects(
    monkeypatch, shadow_return
):
    authority_return = object()
    harness = _install(monkeypatch, shadow_return=shadow_return, authority_return=authority_return)
    _run(harness)

    assert [call[0] for call in harness.calls] == [
        "initial_execution", "phase_c_entry", "product_recovery",
        "task_evidence_stage", "research_decision_shadow", "p4_6d1", "research_context",
    ]
    assert harness.calls[4][1] is harness.evidence_shadow
    assert harness.shadow_entry_defaults[0] == []
    assert type(harness.shadow_entry_defaults[0]) is list
    assert harness.calls[5][1] is harness.evidence_authority
    assert harness.calls[5][2] is shadow_return
    assert harness.authority_entry_defaults == [None]
    assert harness.frames[0]["task_research_decisions_shadow"] is shadow_return
    assert harness.frames[0]["task_research_authority_p4_6d1"] is authority_return
    assert harness.context_inputs[0][2] is shadow_return


@pytest.mark.parametrize(
    "authority_return", [[], (), {"shape": "mapping"}, None, object()]
)
def test_authority_success_is_retained_by_identity_but_never_sent_to_context(
    monkeypatch, authority_return
):
    shadow_return = object()
    harness = _install(monkeypatch, shadow_return=shadow_return, authority_return=authority_return)
    _run(harness)

    assert harness.frames[0]["task_research_authority_p4_6d1"] is authority_return
    assert harness.context_inputs[0][2] is shadow_return
    assert all(authority_return is not value for value in harness.context_inputs[0])


@pytest.mark.parametrize(
    ("shadow_error", "authority_error", "shadow_survives"),
    [
        (OrdinaryShadowError("shadow"), None, False),
        (None, OrdinaryAuthorityError("authority"), True),
        (OrdinaryShadowError("shadow"), OrdinaryAuthorityError("authority"), False),
    ],
)
def test_independent_exception_fail_open_matrix_reaches_context(
    monkeypatch, shadow_error, authority_error, shadow_survives
):
    shadow_return = object()
    harness = _install(
        monkeypatch, shadow_return=shadow_return, authority_return=object(),
        shadow_error=shadow_error, authority_error=authority_error,
    )
    _run(harness)

    actual_shadow = harness.context_inputs[0][2]
    if shadow_survives:
        assert actual_shadow is shadow_return
    else:
        assert actual_shadow == [] and type(actual_shadow) is list
    assert harness.calls[5][2] is actual_shadow
    if authority_error is not None:
        assert harness.frames[0]["task_research_authority_p4_6d1"] is None


def test_defaults_are_fresh_across_independent_core_calls(monkeypatch):
    harness = _install(
        monkeypatch,
        shadow_error=OrdinaryShadowError("shadow"),
        authority_error=OrdinaryAuthorityError("authority"),
    )
    _run(harness)
    _run(harness)

    first_shadow, second_shadow = (entry[2] for entry in harness.context_inputs)
    assert first_shadow == second_shadow == []
    assert first_shadow is not second_shadow
    assert harness.shadow_entry_defaults[0] is not harness.shadow_entry_defaults[1]
    assert harness.frames[0]["task_research_authority_p4_6d1"] is None
    assert harness.frames[1]["task_research_authority_p4_6d1"] is None


@pytest.mark.parametrize("target", ["shadow", "authority"])
def test_baseexception_is_not_swallowed_by_either_local_boundary(monkeypatch, target):
    fatal = KeyboardInterrupt(target)
    harness = _install(
        monkeypatch,
        shadow_return=object(),
        authority_return=object(),
        shadow_error=fatal if target == "shadow" else None,
        authority_error=fatal if target == "authority" else None,
    )
    with pytest.raises(KeyboardInterrupt, match=target):
        service._p4_15cp3c_previous_run_orchestrator(
            OrchestratorAskRequest(q="synthetic", vraag=""), sender=harness.sender
        )
    assert not harness.context_inputs
    assert sum(call[0] == "research_decision_shadow" for call in harness.calls) == 1
    assert sum(call[0] == "p4_6d1" for call in harness.calls) == (target == "authority")


def test_context_gets_same_plan_fresh_ordered_results_copy_and_shadow_only(monkeypatch):
    shadow_return = object()
    authority_return = object()
    harness = _install(monkeypatch, shadow_return=shadow_return, authority_return=authority_return)
    _run(harness)

    actual_plan, actual_results, actual_shadow = harness.context_inputs[0]
    assert actual_plan is harness.plan
    assert actual_results is not harness.results
    assert len(actual_results) == len(harness.results)
    assert all(actual is expected for actual, expected in zip(actual_results, harness.results))
    assert actual_shadow is shadow_return
    assert authority_return is not actual_shadow


def test_no_duplicate_calls_or_input_mutation(monkeypatch):
    harness = _install(monkeypatch, shadow_return=object(), authority_return=object())
    _run(harness)

    names = [call[0] for call in harness.calls]
    assert all(names.count(name) == 1 for name in names)
    assert vars(harness.plan) == harness.before["plan"]
    assert harness.typed_results == harness.before["typed"]
    assert harness.results == harness.before["results"]
    assert harness.trace == harness.before["trace"]
    assert harness.working_evidence == harness.before["working"]
    assert harness.stamp is harness.frames[0]["retrieved_at"]
    result = harness.stage_outputs[0]
    assert result.task_evidence_assessments_shadow is harness.evidence_shadow
    assert result.task_evidence_authority_p4_6c is harness.evidence_authority


def test_list_results_failure_belongs_to_context_fail_open_zone(monkeypatch):
    harness = _install(
        monkeypatch,
        shadow_return=object(),
        authority_return=object(),
        raw_results=_HostileResults(),
    )
    guard_frames = []

    def guard(value):
        guard_frames.append(dict(inspect.currentframe().f_back.f_locals))
        raise GuardBoundaryObserved("after context fail-open")

    monkeypatch.setattr(service, "_derive_intent_task_research_call_guards_shadow", guard)
    with pytest.raises(GuardBoundaryObserved, match="after context fail-open"):
        service._p4_15cp3c_previous_run_orchestrator(
            OrchestratorAskRequest(q="synthetic", vraag=""), sender=harness.sender
        )

    assert [call[0] for call in harness.calls] == [
        "initial_execution", "phase_c_entry", "product_recovery",
        "task_evidence_stage", "research_decision_shadow", "p4_6d1",
    ]
    assert sum(call[0] == "research_decision_shadow" for call in harness.calls) == 1
    assert sum(call[0] == "p4_6d1" for call in harness.calls) == 1
    assert not harness.context_inputs
    assert harness.raw_results.iterations == 1
    assert guard_frames[0]["task_research_contexts_shadow"] == []
    assert type(guard_frames[0]["task_research_contexts_shadow"]) is list
