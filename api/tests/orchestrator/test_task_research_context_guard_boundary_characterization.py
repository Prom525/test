"""Characterize the research-context/call-guard boundary immediately after 3I2."""
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
from app.orchestrator.task_research_decision_stage import TaskResearchDecisionStageResult


class Cp13Observed(BaseException):
    pass


class OrdinaryContextError(Exception):
    pass


class OrdinaryGuardError(Exception):
    pass


class OrdinaryListError(Exception):
    pass


class FatalBoundaryError(BaseException):
    pass


class _Results:
    def __init__(self, values, error=None):
        self.values = values
        self.error = error
        self.iterations = 0

    def __iter__(self):
        self.iterations += 1
        if self.error is not None:
            raise self.error
        return iter(self.values)


def _install(monkeypatch, *, context_return=(), guard_return=(), context_error=None,
             guard_error=None, results_error=None):
    calls = []
    frames = []
    context_defaults = []
    guard_defaults = []
    plan = SimpleNamespace(
        intent="synthetic", clarification_required=False,
        clarification_question=None, execution_steps=(), research_required=False,
        requested_information=("synthetic",), multi_intent=False,
    )
    result_values = [object(), object()]
    results = _Results(result_values, results_error)
    typed_results = [SimpleNamespace(status="synthetic")]
    trace = {"attempts": []}
    stamp = object()
    initial_evidence = (object(),)
    working_evidence = [initial_evidence[0], object()]
    task_execution_shadow = object()
    evidence_shadow = object()
    evidence_authority = object()
    decisions = object()
    research_authority = object()
    sender = object()
    before = {
        "plan": deepcopy(vars(plan)), "typed": deepcopy(typed_results),
        "trace": deepcopy(trace), "working": list(working_evidence),
        "result_values": list(result_values),
    }

    monkeypatch.setattr(service, "_new_observability_counts", lambda: {})
    monkeypatch.setattr(service, "run_initial_planning_stage", lambda *a, **k: plan)
    monkeypatch.setattr(service, "_record_initial_execution_observability", lambda *a: None)

    def execution(*args, **kwargs):
        calls.append(("execution", args, kwargs))
        return SimpleNamespace(
            plan=plan, task_execution_plans_shadow=(),
            task_execution_plan_comparison_shadow=None,
            task_execution_canary_p4_6b=None, typed_execution_results=typed_results,
            results=results, trace=trace, task_execution_shadow=task_execution_shadow,
            task_planner_canary=None,
        )

    monkeypatch.setattr(service, "run_initial_execution_stage", execution)

    def phase_c(*args, **kwargs):
        calls.append(("phase_c", args, kwargs))
        return PhaseCEntryResult(object(), stamp, initial_evidence, initial_evidence)

    monkeypatch.setattr(service, "prepare_phase_c_entry", phase_c)

    def recovery(*args, **kwargs):
        calls.append(("recovery", args, kwargs))
        return ProductFamilyRecoveryResult(object(), object(), working_evidence)

    monkeypatch.setattr(service, "run_product_family_recovery_stage", recovery)

    def evidence(*args, **kwargs):
        calls.append(("evidence", args, kwargs))
        return TaskEvidenceStageResult(evidence_shadow, evidence_authority)

    monkeypatch.setattr(service, "run_task_evidence_stage", evidence)

    def decision(actual_shadow, actual_authority, **dependencies):
        calls.append(("3i2", actual_shadow, actual_authority, dependencies))
        return TaskResearchDecisionStageResult(decisions, research_authority)

    monkeypatch.setattr(service, "run_task_research_decision_stage", decision)

    def context(actual_plan, actual_results, actual_decisions):
        caller = inspect.currentframe().f_back.f_locals
        context_defaults.append(caller["task_research_contexts_shadow"])
        calls.append(("context", actual_plan, actual_results, actual_decisions))
        if context_error is not None:
            raise context_error
        return context_return

    monkeypatch.setattr(service, "_derive_intent_task_research_contexts_shadow", context)

    def guard(actual_contexts):
        caller = inspect.currentframe().f_back.f_locals
        guard_defaults.append(caller["task_research_call_guards_shadow"])
        calls.append(("guard", actual_contexts))
        if guard_error is not None:
            raise guard_error
        return guard_return

    monkeypatch.setattr(service, "_derive_intent_task_research_call_guards_shadow", guard)

    def cp13(*args):
        frames.append(dict(inspect.currentframe().f_back.f_locals))
        calls.append(("cp13", *args))
        raise Cp13Observed("controlled stop at CP13")

    monkeypatch.setattr(service, "build_task_research_semantics", cp13)
    monkeypatch.setattr(service, "has_service_accepted_execution", lambda *a: True)
    monkeypatch.setattr(
        service, "_build_user_answer",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("outer fallback reached")),
    )
    return SimpleNamespace(**locals())


def _run(harness):
    with pytest.raises(Cp13Observed, match="controlled stop at CP13"):
        service._p4_15cp3c_previous_run_orchestrator(
            OrchestratorAskRequest(q="synthetic", vraag=""), sender=harness.sender
        )


@pytest.mark.parametrize("context_return", [[], (), {"shape": "mapping"}, None, object()])
@pytest.mark.parametrize("guard_return", [[], (), {"shape": "mapping"}, None, object()])
def test_success_preserves_identity_arguments_order_and_cp13_boundary(
    monkeypatch, context_return, guard_return
):
    harness = _install(monkeypatch, context_return=context_return, guard_return=guard_return)
    _run(harness)

    assert [call[0] for call in harness.calls] == [
        "execution", "phase_c", "recovery", "evidence", "3i2", "context", "guard", "cp13"
    ]
    context_call, guard_call, cp13_call = harness.calls[5:]
    assert context_call[1] is harness.plan
    assert context_call[2] is not harness.results
    assert all(a is b for a, b in zip(context_call[2], harness.result_values))
    assert context_call[3] is harness.decisions
    assert guard_call[1] is context_return
    assert cp13_call[1:] == (harness.plan, harness.task_execution_shadow,
                             harness.research_authority)
    assert harness.frames[0]["task_research_contexts_shadow"] is context_return
    assert harness.frames[0]["task_research_call_guards_shadow"] is guard_return
    assert harness.context_defaults == [[]]
    assert harness.guard_defaults == [[]]


@pytest.mark.parametrize("source", ["list", "context"])
def test_context_zone_ordinary_exception_uses_fresh_fallback_and_still_calls_guard_and_cp13(
    monkeypatch, source
):
    error = OrdinaryListError("list") if source == "list" else OrdinaryContextError("context")
    harness = _install(
        monkeypatch, results_error=error if source == "list" else None,
        context_error=error if source == "context" else None, guard_return=object(),
    )
    _run(harness)

    fallback = harness.calls[-2][1]
    assert fallback == [] and type(fallback) is list
    assert harness.frames[0]["task_research_contexts_shadow"] is fallback
    assert [c[0] for c in harness.calls].count("context") == (source == "context")
    assert [c[0] for c in harness.calls].count("guard") == 1
    assert [c[0] for c in harness.calls].count("cp13") == 1


@pytest.mark.parametrize("context_fails", [False, True])
def test_guard_ordinary_exception_is_independent_and_cp13_sees_fresh_guard_fallback(
    monkeypatch, context_fails
):
    context_return = object()
    harness = _install(
        monkeypatch, context_return=context_return,
        context_error=OrdinaryContextError("context") if context_fails else None,
        guard_error=OrdinaryGuardError("guard"),
    )
    _run(harness)

    actual_context = harness.calls[-2][1]
    if context_fails:
        assert actual_context == [] and type(actual_context) is list
    else:
        assert actual_context is context_return
    assert harness.frames[0]["task_research_contexts_shadow"] is actual_context
    guard_fallback = harness.frames[0]["task_research_call_guards_shadow"]
    assert guard_fallback == [] and type(guard_fallback) is list


def test_defaults_are_fresh_across_independent_core_calls(monkeypatch):
    harness = _install(
        monkeypatch, context_error=OrdinaryContextError("context"),
        guard_error=OrdinaryGuardError("guard"),
    )
    _run(harness)
    _run(harness)
    contexts = [frame["task_research_contexts_shadow"] for frame in harness.frames]
    guards = [frame["task_research_call_guards_shadow"] for frame in harness.frames]
    assert contexts[0] == contexts[1] == [] and contexts[0] is not contexts[1]
    assert guards[0] == guards[1] == [] and guards[0] is not guards[1]
    assert harness.context_defaults[0] is not harness.context_defaults[1]
    assert harness.guard_defaults[0] is not harness.guard_defaults[1]


@pytest.mark.parametrize("source", ["list", "context", "guard"])
def test_baseexception_is_not_swallowed(monkeypatch, source):
    fatal = FatalBoundaryError(source)
    harness = _install(
        monkeypatch, results_error=fatal if source == "list" else None,
        context_error=fatal if source == "context" else None,
        guard_error=fatal if source == "guard" else None,
    )
    with pytest.raises(FatalBoundaryError, match=source):
        service._p4_15cp3c_previous_run_orchestrator(
            OrchestratorAskRequest(q="synthetic", vraag=""), sender=harness.sender
        )
    names = [call[0] for call in harness.calls]
    assert names.count("context") == (source != "list")
    assert names.count("guard") == (source == "guard")
    assert "cp13" not in names


def test_no_duplicate_calls_or_mutation(monkeypatch):
    harness = _install(monkeypatch, context_return=object(), guard_return=object())
    _run(harness)
    names = [call[0] for call in harness.calls]
    assert all(names.count(name) == 1 for name in names)
    assert vars(harness.plan) == harness.before["plan"]
    assert harness.typed_results == harness.before["typed"]
    assert harness.trace == harness.before["trace"]
    assert harness.working_evidence == harness.before["working"]
    assert harness.result_values == harness.before["result_values"]
    assert harness.frames[0]["retrieved_at"] is harness.stamp
    assert harness.frames[0]["task_research_decisions_shadow"] is harness.decisions
    assert harness.frames[0]["task_research_authority_p4_6d1"] is harness.research_authority
