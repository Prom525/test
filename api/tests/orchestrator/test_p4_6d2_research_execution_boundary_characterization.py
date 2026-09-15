"""Characterize the service-owned P4.6D2 invocation and P4.6E1 boundary."""
from __future__ import annotations

from copy import deepcopy
import inspect
from types import SimpleNamespace

import pytest

from app.orchestrator import service
from app.orchestrator.cp13_research_semantics_stage import Cp13ResearchSemanticsStageResult
from app.orchestrator.models import OrchestratorAskRequest
from app.orchestrator.phase_c_entry_stage import PhaseCEntryResult
from app.orchestrator.product_family_recovery_stage import ProductFamilyRecoveryResult
from app.orchestrator.task_evidence_stage import TaskEvidenceStageResult
from app.orchestrator.task_research_context_stage import TaskResearchContextStageResult
from app.orchestrator.task_research_decision_stage import TaskResearchDecisionStageResult


class E1Boundary(BaseException):
    pass


class FatalD2(BaseException):
    pass


class ExplodingResults:
    def __iter__(self):
        raise RuntimeError("result iteration")


class FatalResults:
    def __iter__(self):
        raise FatalD2("fatal result iteration")


class ExplodingEvidence(list):
    def __iter__(self):
        raise RuntimeError("working evidence iteration")


def _install(monkeypatch, *, results=None, evidence_values=None, d2_return=None,
             d2_error=None, observations=()):
    calls, d2_frames, e1_frames = [], [], []
    plan = SimpleNamespace(
        intent="synthetic", clarification_required=False, clarification_question=None,
        execution_steps=(), research_required=False,
        requested_information=("synthetic",), multi_intent=False,
    )
    result_values = [SimpleNamespace(value=[1]), SimpleNamespace(value=[2])]
    results = list(result_values) if results is None else results
    typed_results = [SimpleNamespace(value=[3])]
    trace = {"attempts": [SimpleNamespace(value=[4])]}
    retrieved_at = object()
    evidence_values = ([SimpleNamespace(value=[5]), SimpleNamespace(value=[6])]
                       if evidence_values is None else evidence_values)
    task_execution_shadow = SimpleNamespace(value=[7])
    evidence_shadow, evidence_authority = object(), object()
    decisions, research_authority = object(), object()
    contexts, guards, cp13, sender = object(), object(), object(), object()
    tracked = (plan, typed_results, trace, task_execution_shadow)
    before = deepcopy(tracked)

    monkeypatch.setattr(service, "_new_observability_counts", lambda: {})
    monkeypatch.setattr(service, "run_initial_planning_stage", lambda *a, **k: plan)
    monkeypatch.setattr(service, "_record_initial_execution_observability", lambda *a: None)
    monkeypatch.setattr(service, "run_initial_execution_stage", lambda *a, **k: SimpleNamespace(
        plan=plan, task_execution_plans_shadow=(),
        task_execution_plan_comparison_shadow=None, task_execution_canary_p4_6b=None,
        typed_execution_results=typed_results, results=results, trace=trace,
        task_execution_shadow=task_execution_shadow, task_planner_canary=None))
    monkeypatch.setattr(service, "prepare_phase_c_entry", lambda *a, **k:
        PhaseCEntryResult(object(), retrieved_at, (), ()))
    monkeypatch.setattr(service, "run_product_family_recovery_stage", lambda *a, **k:
        ProductFamilyRecoveryResult(object(), object(), evidence_values))
    monkeypatch.setattr(service, "run_task_evidence_stage", lambda *a, **k:
        TaskEvidenceStageResult(evidence_shadow, evidence_authority))
    monkeypatch.setattr(service, "run_task_research_decision_stage", lambda *a, **k:
        TaskResearchDecisionStageResult(decisions, research_authority))
    monkeypatch.setattr(service, "run_task_research_context_stage", lambda *a, **k:
        TaskResearchContextStageResult(contexts, guards))
    monkeypatch.setattr(service, "run_cp13_research_semantics_stage", lambda *a, **k:
        Cp13ResearchSemanticsStageResult(cp13))

    def d2(*args, **kwargs):
        frame = inspect.currentframe().f_back.f_locals
        current = frame["task_research_execution_observations_p4_6d2"]
        d2_frames.append((frame["task_research_execution_authority_p4_6d2"], current))
        calls.append(("d2", args, kwargs))
        for observation in observations:
            kwargs["evidence_observer"](observation)
        if d2_error is not None:
            raise d2_error
        return d2_return

    def e1(*args, **kwargs):
        frame = inspect.currentframe().f_back.f_locals
        e1_frames.append(frame["task_research_evidence_units_p4_6e1"])
        calls.append(("e1", args, kwargs))
        raise E1Boundary("controlled stop before E1 internals")

    monkeypatch.setattr(service, "run_task_research_execution_authority_canary_p4_6d2", d2)
    monkeypatch.setattr(service, "build_task_research_evidence_authority_canary_p4_6e1", e1)
    monkeypatch.setattr(service, "has_service_accepted_execution", lambda *a: True)
    return SimpleNamespace(**locals())


def _run(harness):
    with pytest.raises(E1Boundary, match="controlled stop"):
        service._p4_15cp3c_previous_run_orchestrator(
            OrchestratorAskRequest(q="synthetic", vraag=""), sender=harness.sender)


@pytest.mark.parametrize("value", [[], (), {"shape": "mapping"}, None, object()])
@pytest.mark.parametrize("observation_count", [0, 1, 3])
def test_success_preserves_return_and_exact_d2_to_e1_contract(
    monkeypatch, value, observation_count,
):
    observations = tuple(object() for _ in range(observation_count))
    harness = _install(monkeypatch, d2_return=value, observations=observations)
    _run(harness)
    assert [row[0] for row in harness.calls] == ["d2", "e1"]
    d2, e1 = harness.calls
    assert harness.d2_frames[0][0] is None
    observation_list = harness.d2_frames[0][1]
    assert observation_list == list(observations)
    assert all(a is b for a, b in zip(observation_list, observations))
    assert d2[1][0] is harness.plan
    assert d2[1][1] is not harness.results
    assert all(a is b for a, b in zip(d2[1][1], harness.result_values))
    assert d2[1][2:] == (harness.research_authority, harness.contexts, harness.guards)
    assert d2[2]["sender"] is harness.sender
    assert d2[2]["evidence_observer"].__self__ is observation_list
    assert d2[2]["task_research_semantics_cp13"] is harness.cp13
    assert e1[1][0] is harness.plan and e1[1][1] is value
    assert e1[1][2] is observation_list
    assert isinstance(e1[1][3], tuple)
    assert all(a is b for a, b in zip(e1[1][3], harness.evidence_values))
    assert e1[2]["now"] is harness.retrieved_at
    assert e1[2]["grounded_synthesis_observer"].__self__ is harness.e1_frames[0]
    assert harness.e1_frames[0] == []


@pytest.mark.parametrize("source", ["list", "runner"])
def test_ordinary_exception_resets_authority_and_discards_observations(monkeypatch, source):
    marker = object()
    harness = _install(
        monkeypatch,
        results=ExplodingResults() if source == "list" else None,
        d2_error=RuntimeError("runner") if source == "runner" else None,
        observations=(marker,) if source == "runner" else (),
    )
    _run(harness)
    assert [row[0] for row in harness.calls] == (["e1"] if source == "list" else ["d2", "e1"])
    e1 = harness.calls[-1]
    assert e1[1][1] is None
    assert e1[1][2] == []
    if source == "runner":
        assert harness.d2_frames[0][1] == [marker]
        assert e1[1][2] is not harness.d2_frames[0][1]


def test_fallback_values_are_fresh_and_inputs_are_not_mutated_across_calls(monkeypatch):
    harness = _install(monkeypatch, d2_error=RuntimeError("runner"), observations=(object(),))
    _run(harness)
    first = harness.calls[-1][1][2]
    _run(harness)
    second = harness.calls[-1][1][2]
    assert first == second == [] and first is not second
    assert harness.e1_frames[0] is not harness.e1_frames[1]
    assert harness.tracked == harness.before
    assert [row[0] for row in harness.calls].count("d2") == 2
    assert [row[0] for row in harness.calls].count("e1") == 2


@pytest.mark.parametrize("source", ["list", "runner"])
def test_baseexception_propagates_and_never_reaches_e1(monkeypatch, source):
    fatal = FatalD2("fatal runner")
    harness = _install(
        monkeypatch, results=FatalResults() if source == "list" else None,
        d2_error=fatal if source == "runner" else None)
    with pytest.raises(FatalD2):
        service._p4_15cp3c_previous_run_orchestrator(
            OrchestratorAskRequest(q="synthetic", vraag=""), sender=harness.sender)
    assert "e1" not in [row[0] for row in harness.calls]


def test_tuple_of_working_evidence_is_e1_argument_evaluation_not_d2(monkeypatch):
    harness = _install(monkeypatch, d2_return=object())
    _run(harness)
    assert len(harness.calls) == 2
    assert harness.calls[0][0] == "d2" and harness.calls[1][0] == "e1"
    assert harness.calls[1][1][3] is not harness.evidence_values


def test_working_evidence_tuple_exception_is_caught_by_e1_zone(monkeypatch):
    harness = _install(monkeypatch, evidence_values=ExplodingEvidence(), d2_return=object())
    e2_calls = []

    def stop_at_e2(*args, **kwargs):
        e2_calls.append((args, kwargs))
        raise E1Boundary("controlled stop after E1-zone fallback")

    monkeypatch.setattr(
        service, "build_task_grounded_synthesis_authority_canary_p4_6e2", stop_at_e2)
    _run(harness)
    assert [row[0] for row in harness.calls] == ["d2"]
    assert len(e2_calls) == 1 and e2_calls[0][0] == (None, [])
