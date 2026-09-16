"""Characterize the service-owned V8 invocation boundary after P4.6E3."""
from types import SimpleNamespace

import pytest

from app.orchestrator import service
from app.orchestrator.cp13_research_semantics_stage import Cp13ResearchSemanticsStageResult
from app.orchestrator.models import OrchestratorAskRequest
from app.orchestrator.p4_6d2_research_execution_stage import P46d2ResearchExecutionStageResult
from app.orchestrator.p4_6e1_research_evidence_stage import P46e1ResearchEvidenceStageResult
from app.orchestrator.p4_6e2_grounded_synthesis_stage import P46e2GroundedSynthesisStageResult
from app.orchestrator.p4_6e3_synthesis_coverage_stage import P46e3SynthesisCoverageStageResult
from app.orchestrator.phase_c_entry_stage import PhaseCEntryResult
from app.orchestrator.product_family_recovery_stage import ProductFamilyRecoveryResult
from app.orchestrator.task_evidence_stage import TaskEvidenceStageResult
from app.orchestrator.task_research_context_stage import TaskResearchContextStageResult
from app.orchestrator.task_research_decision_stage import TaskResearchDecisionStageResult


class StopAtAssessment(BaseException):
    pass


class Fatal(BaseException):
    pass


class ExplodingIterable:
    def __init__(self, error): self.error = error
    def __iter__(self): raise self.error
    def __len__(self): return 1


def _install(monkeypatch, *, results=None, evidence=None, v8_return=None, v8_error=None):
    calls = []
    plan = SimpleNamespace(intent="synthetic", clarification_required=False,
        clarification_question=None, execution_steps=(), research_required=False,
        requested_information=("synthetic",), multi_intent=False)
    results = [{"result": {}}, {"result": {}}] if results is None else results
    evidence = [object(), object()] if evidence is None else evidence
    contexts, guards, sender, retrieved_at = [object()], [object()], object(), object()
    typed_results, trace = [object()], {"marker": object()}
    monkeypatch.setattr(service, "run_initial_planning_stage", lambda *a, **k: plan)
    monkeypatch.setattr(service, "_model_to_dict", lambda value: {})
    monkeypatch.setattr(service, "_record_initial_execution_observability", lambda *a: None)
    monkeypatch.setattr(service, "run_initial_execution_stage", lambda *a, **k: SimpleNamespace(
        plan=plan, task_execution_plans_shadow=(), task_execution_plan_comparison_shadow=None,
        task_execution_canary_p4_6b=None, typed_execution_results=typed_results, results=results,
        trace=trace, task_execution_shadow=object(), task_planner_canary=None))
    monkeypatch.setattr(service, "prepare_phase_c_entry", lambda *a, **k:
        PhaseCEntryResult(object(), retrieved_at, (), ()))
    monkeypatch.setattr(service, "run_product_family_recovery_stage", lambda *a, **k:
        ProductFamilyRecoveryResult(object(), object(), evidence))
    monkeypatch.setattr(service, "run_task_evidence_stage", lambda *a, **k: TaskEvidenceStageResult(object(), object()))
    monkeypatch.setattr(service, "run_task_research_decision_stage", lambda *a, **k: TaskResearchDecisionStageResult(object(), object()))
    monkeypatch.setattr(service, "run_task_research_context_stage", lambda *a, **k: TaskResearchContextStageResult(contexts, guards))
    monkeypatch.setattr(service, "run_cp13_research_semantics_stage", lambda *a, **k: Cp13ResearchSemanticsStageResult(object()))
    monkeypatch.setattr(service, "run_p4_6d2_research_execution_stage", lambda *a, **k: P46d2ResearchExecutionStageResult(object(), []))
    monkeypatch.setattr(service, "run_p4_6e1_research_evidence_stage", lambda *a, **k: P46e1ResearchEvidenceStageResult(object(), []))
    monkeypatch.setattr(service, "run_p4_6e2_grounded_synthesis_stage", lambda *a, **k: P46e2GroundedSynthesisStageResult(object()))
    monkeypatch.setattr(service, "run_p4_6e3_synthesis_coverage_stage", lambda *a, **k: P46e3SynthesisCoverageStageResult(object()))

    def v8(*args, **kwargs):
        calls.append(("v8", args, kwargs))
        kwargs["evidence_reassessment_observer"]("partial-r")
        kwargs["grounded_synthesis_observer"]("partial-g")
        if v8_error is not None: raise v8_error
        return v8_return

    def assess(*args, **kwargs):
        frame = __import__("inspect").currentframe().f_back
        while "task_research_execution_canary_shadow" not in frame.f_locals:
            frame = frame.f_back
        frame = frame.f_locals
        calls.append(("assessment", args, kwargs,
            frame["task_research_execution_canary_shadow"],
            frame["task_research_evidence_reassessment_shadow"],
            frame["task_grounded_synthesis_shadow"]))
        raise StopAtAssessment

    monkeypatch.setattr(service, "_run_intent_task_research_execution_canary_shadow", v8)
    monkeypatch.setattr(service, "assess_evidence", assess)
    monkeypatch.setattr(service, "_observability_call", lambda timings, key, fn, *a, **k: fn(*a, **k))
    monkeypatch.setattr(service, "has_service_accepted_execution", lambda *a: True)
    return SimpleNamespace(**locals())


def _run(h):
    with pytest.raises(StopAtAssessment):
        service._p4_15cp3c_previous_run_orchestrator(OrchestratorAskRequest(q="synthetic", vraag=""), sender=h.sender)


@pytest.mark.parametrize("returned", [{"x": 1}, [1], (1,), None, object()])
def test_exact_runtime_call_inputs_fresh_observers_and_unconverted_success(monkeypatch, returned):
    h = _install(monkeypatch, v8_return=returned)
    _run(h)
    v8, assessment = h.calls
    assert v8[1][0] is h.plan
    assert isinstance(v8[1][1], list) and v8[1][1] is not h.results
    assert all(a is b for a, b in zip(v8[1][1], h.results))
    assert v8[1][2] is h.contexts and v8[1][3] is h.guards
    assert v8[2]["sender"] is h.sender
    assert isinstance(v8[2]["initial_evidence_items"], tuple)
    assert all(a is b for a, b in zip(v8[2]["initial_evidence_items"], h.evidence))
    assert v8[2]["reassessment_now"] is h.retrieved_at
    assert assessment[3] is returned and assessment[4:] == (["partial-r"], ["partial-g"])
    assert assessment[1][1] is h.evidence and assessment[2]["now"] is h.retrieved_at


def test_each_core_call_uses_three_fresh_lists(monkeypatch):
    h = _install(monkeypatch, v8_return=object())
    defaults_by_call = []

    def v8(*args, **kwargs):
        frame = __import__("inspect").currentframe().f_back.f_locals
        defaults_by_call.append((
            frame["task_research_execution_canary_shadow"],
            frame["task_research_evidence_reassessment_shadow"],
            frame["task_grounded_synthesis_shadow"],
        ))
        return object()

    monkeypatch.setattr(service, "_run_intent_task_research_execution_canary_shadow", v8)
    _run(h); _run(h)
    assert len(defaults_by_call) == 2
    assert all(value == [] for call in defaults_by_call for value in call)
    assert len({id(value) for value in defaults_by_call[0]}) == 3
    assert len({id(value) for value in defaults_by_call[1]}) == 3
    assert all(
        first is not second
        for first, second in zip(defaults_by_call[0], defaults_by_call[1])
    )


def test_v8_exception_discards_all_partial_observations_and_assesses(monkeypatch):
    h = _install(monkeypatch, v8_error=RuntimeError("v8"))
    _run(h)
    assessment = h.calls[-1]
    assert assessment[3:] == ([], [], [])


@pytest.mark.parametrize("where", ["results", "evidence", "call", "observer"])
def test_baseexception_propagates_and_prevents_assessment(monkeypatch, where):
    fatal = Fatal(where)
    h = _install(monkeypatch,
        results=ExplodingIterable(fatal) if where == "results" else None,
        evidence=ExplodingIterable(fatal) if where == "evidence" else None,
        v8_error=fatal if where == "call" else None)
    if where == "observer":
        def v8(*args, **kwargs):
            kwargs["evidence_reassessment_observer"] = lambda value: (_ for _ in ()).throw(fatal)
            kwargs["evidence_reassessment_observer"]("x")
        monkeypatch.setattr(service, "_run_intent_task_research_execution_canary_shadow", v8)
    with pytest.raises(Fatal) as raised:
        service._p4_15cp3c_previous_run_orchestrator(OrchestratorAskRequest(q="synthetic", vraag=""), sender=h.sender)
    assert raised.value is fatal and not any(row[0] == "assessment" for row in h.calls)


def test_separate_evidence_coercions_can_skip_e3_and_v8_then_assess(monkeypatch):
    h = _install(monkeypatch, evidence=ExplodingIterable(RuntimeError("tuple")))
    _run(h)
    assert [row[0] for row in h.calls] == ["assessment"]
