"""Characterize the service-owned P4.6E1 invocation and P4.6E2 boundary."""
from __future__ import annotations

from copy import deepcopy
import inspect
from types import SimpleNamespace

import pytest

from app.orchestrator import service
from app.orchestrator.cp13_research_semantics_stage import Cp13ResearchSemanticsStageResult
from app.orchestrator.models import OrchestratorAskRequest
from app.orchestrator.p4_6d2_research_execution_stage import P46d2ResearchExecutionStageResult
from app.orchestrator.phase_c_entry_stage import PhaseCEntryResult
from app.orchestrator.product_family_recovery_stage import ProductFamilyRecoveryResult
from app.orchestrator.task_evidence_stage import TaskEvidenceStageResult
from app.orchestrator.task_research_context_stage import TaskResearchContextStageResult
from app.orchestrator.task_research_decision_stage import TaskResearchDecisionStageResult


class StopAtE2(BaseException):
    pass


class FatalE1(BaseException):
    pass


class HostileEvidence:
    def __init__(self, error):
        self.error = error

    def __iter__(self):
        raise self.error


def _install(monkeypatch, *, evidence=None, e1_return=None, e1_error=None, units=()):
    calls, frames = [], []
    plan = SimpleNamespace(
        intent="synthetic", clarification_required=False,
        clarification_question=None, execution_steps=(), research_required=False,
        requested_information=("synthetic",), multi_intent=False,
    )
    results, typed, trace = [object()], [SimpleNamespace(value=[1])], {"attempts": []}
    authority_d2, observations = object(), [object(), object()]
    evidence = [object(), object()] if evidence is None else evidence
    retrieved_at, sender = object(), object()
    before = deepcopy((plan, typed, trace))

    monkeypatch.setattr(service, "_new_observability_counts", lambda: {})
    monkeypatch.setattr(service, "run_initial_planning_stage", lambda *a, **k: plan)
    monkeypatch.setattr(service, "_record_initial_execution_observability", lambda *a: None)
    monkeypatch.setattr(service, "run_initial_execution_stage", lambda *a, **k: SimpleNamespace(
        plan=plan, task_execution_plans_shadow=(), task_execution_plan_comparison_shadow=None,
        task_execution_canary_p4_6b=None, typed_execution_results=typed, results=results,
        trace=trace, task_execution_shadow=object(), task_planner_canary=None))
    monkeypatch.setattr(service, "prepare_phase_c_entry", lambda *a, **k:
        PhaseCEntryResult(object(), retrieved_at, (), ()))
    monkeypatch.setattr(service, "run_product_family_recovery_stage", lambda *a, **k:
        ProductFamilyRecoveryResult(object(), object(), evidence))
    monkeypatch.setattr(service, "run_task_evidence_stage", lambda *a, **k:
        TaskEvidenceStageResult(object(), object()))
    monkeypatch.setattr(service, "run_task_research_decision_stage", lambda *a, **k:
        TaskResearchDecisionStageResult(object(), object()))
    monkeypatch.setattr(service, "run_task_research_context_stage", lambda *a, **k:
        TaskResearchContextStageResult(object(), object()))
    monkeypatch.setattr(service, "run_cp13_research_semantics_stage", lambda *a, **k:
        Cp13ResearchSemanticsStageResult(object()))
    monkeypatch.setattr(service, "run_p4_6d2_research_execution_stage", lambda *a, **k:
        P46d2ResearchExecutionStageResult(authority_d2, observations))

    def e1(*args, **kwargs):
        frame = inspect.currentframe().f_back.f_locals
        current_units = frame["task_research_evidence_units_p4_6e1"]
        frames.append((frame["task_research_evidence_authority_p4_6e1"],
                       current_units, tuple(current_units)))
        calls.append(("e1", args, kwargs))
        for unit in units:
            kwargs["grounded_synthesis_observer"](unit)
        if e1_error is not None:
            raise e1_error
        return e1_return

    def e2(*args, **kwargs):
        frame = inspect.currentframe().f_back.f_locals
        calls.append(("e2", args, kwargs, frame["task_grounded_synthesis_authority_p4_6e2"]))
        raise StopAtE2("controlled E2 boundary")

    monkeypatch.setattr(service, "build_task_research_evidence_authority_canary_p4_6e1", e1)
    monkeypatch.setattr(service, "build_task_grounded_synthesis_authority_canary_p4_6e2", e2)
    monkeypatch.setattr(service, "has_service_accepted_execution", lambda *a: True)
    return SimpleNamespace(**locals())


def _run(harness):
    with pytest.raises(StopAtE2, match="controlled E2 boundary"):
        service._p4_15cp3c_previous_run_orchestrator(
            OrchestratorAskRequest(q="synthetic", vraag=""), sender=harness.sender)


@pytest.mark.parametrize("returned", [[], (), {"shape": "mapping"}, None, object()])
@pytest.mark.parametrize("unit_count", [0, 1, 3])
def test_success_exact_e1_call_units_and_unchanged_e2_handoff(monkeypatch, returned, unit_count):
    units = tuple(object() for _ in range(unit_count))
    h = _install(monkeypatch, e1_return=returned, units=units)
    _run(h)
    assert [row[0] for row in h.calls] == ["e1", "e2"]
    e1, e2 = h.calls
    assert h.frames[0][0] is None and h.frames[0][2] == ()
    assert e1[1][:3] == (h.plan, h.authority_d2, h.observations)
    assert e1[1][0] is h.plan and e1[1][1] is h.authority_d2 and e1[1][2] is h.observations
    assert isinstance(e1[1][3], tuple) and e1[1][3] is not h.evidence
    assert all(a is b for a, b in zip(e1[1][3], h.evidence))
    assert e1[2]["now"] is h.retrieved_at
    final_units = e1[2]["grounded_synthesis_observer"].__self__
    assert final_units == list(units) and all(a is b for a, b in zip(final_units, units))
    assert e2[1][0] is returned and e2[1][1] is final_units
    assert e2[3] is None
    assert deepcopy((h.plan, h.typed, h.trace)) == h.before


@pytest.mark.parametrize("source", ["tuple", "e1"])
def test_exception_resets_authority_discards_partial_units_and_reaches_e2(monkeypatch, source):
    partial = object()
    h = _install(
        monkeypatch,
        evidence=HostileEvidence(RuntimeError("tuple")) if source == "tuple" else None,
        e1_error=RuntimeError("e1") if source == "e1" else None,
        units=(partial,) if source == "e1" else (),
    )
    _run(h)
    e2 = h.calls[-1]
    assert e2[0] == "e2" and e2[1][0] is None and e2[1][1] == []
    if source == "tuple":
        assert [row[0] for row in h.calls] == ["e2"]
    else:
        old_units = h.calls[0][2]["grounded_synthesis_observer"].__self__
        assert old_units == [partial] and e2[1][1] is not old_units


def test_fallback_lists_are_fresh_across_core_calls(monkeypatch):
    h = _install(monkeypatch, e1_error=RuntimeError("e1"), units=(object(),))
    _run(h)
    first = h.calls[-1][1][1]
    _run(h)
    second = h.calls[-1][1][1]
    assert first == second == [] and first is not second
    assert h.frames[0][1] is not h.frames[1][1]


@pytest.mark.parametrize("source", ["tuple", "e1"])
def test_baseexception_propagates_without_e2(monkeypatch, source):
    fatal = FatalE1("fatal")
    h = _install(monkeypatch,
        evidence=HostileEvidence(fatal) if source == "tuple" else None,
        e1_error=fatal if source == "e1" else None)
    with pytest.raises(FatalE1) as raised:
        service._p4_15cp3c_previous_run_orchestrator(
            OrchestratorAskRequest(q="synthetic", vraag=""), sender=h.sender)
    assert raised.value is fatal and "e2" not in [row[0] for row in h.calls]
