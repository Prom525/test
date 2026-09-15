"""Characterize the service-owned P4.6E3 invocation and following V8 boundary."""
import inspect
from types import SimpleNamespace

import pytest

from app.orchestrator import service
from app.orchestrator.cp13_research_semantics_stage import Cp13ResearchSemanticsStageResult
from app.orchestrator.models import OrchestratorAskRequest
from app.orchestrator.p4_6d2_research_execution_stage import P46d2ResearchExecutionStageResult
from app.orchestrator.p4_6e1_research_evidence_stage import P46e1ResearchEvidenceStageResult
from app.orchestrator.p4_6e2_grounded_synthesis_stage import P46e2GroundedSynthesisStageResult
from app.orchestrator.phase_c_entry_stage import PhaseCEntryResult
from app.orchestrator.product_family_recovery_stage import ProductFamilyRecoveryResult
from app.orchestrator.task_evidence_stage import TaskEvidenceStageResult
from app.orchestrator.task_research_context_stage import TaskResearchContextStageResult
from app.orchestrator.task_research_decision_stage import TaskResearchDecisionStageResult


class StopAfterE3(BaseException):
    pass


class FatalE3(BaseException):
    pass


class HostileEvidence:
    def __init__(self, error):
        self.error = error

    def __iter__(self):
        raise self.error

    def __len__(self):
        return 2


def _install(monkeypatch, *, returned=None, error=None, evidence=None):
    calls = []
    plan = SimpleNamespace(
        intent="synthetic", clarification_required=False,
        clarification_question=None, execution_steps=(), research_required=False,
        requested_information=("synthetic",), multi_intent=False,
    )
    results, typed_results, trace, sender = [], [], {}, object()
    evidence = [object(), object()] if evidence is None else evidence
    authority_c, authority_e2, retrieved_at = object(), object(), object()
    stage_markers = [object() for _ in range(7)]

    monkeypatch.setattr(service, "run_initial_planning_stage", lambda *a, **k: plan)
    monkeypatch.setattr(service, "_model_to_dict", lambda value: {})
    monkeypatch.setattr(service, "_record_initial_execution_observability", lambda *a: None)
    monkeypatch.setattr(service, "run_initial_execution_stage", lambda *a, **k: SimpleNamespace(
        plan=plan, task_execution_plans_shadow=(), task_execution_plan_comparison_shadow=None,
        task_execution_canary_p4_6b=None, typed_execution_results=typed_results, results=results,
        trace=trace, task_execution_shadow=stage_markers[0], task_planner_canary=None))
    monkeypatch.setattr(service, "prepare_phase_c_entry", lambda *a, **k:
        PhaseCEntryResult(stage_markers[1], retrieved_at, (), ()))
    monkeypatch.setattr(service, "run_product_family_recovery_stage", lambda *a, **k:
        ProductFamilyRecoveryResult(stage_markers[2], stage_markers[3], evidence))
    monkeypatch.setattr(service, "run_task_evidence_stage", lambda *a, **k:
        TaskEvidenceStageResult(stage_markers[4], authority_c))
    monkeypatch.setattr(service, "run_task_research_decision_stage", lambda *a, **k:
        TaskResearchDecisionStageResult(object(), object()))
    monkeypatch.setattr(service, "run_task_research_context_stage", lambda *a, **k:
        TaskResearchContextStageResult(object(), object()))
    monkeypatch.setattr(service, "run_cp13_research_semantics_stage", lambda *a, **k:
        Cp13ResearchSemanticsStageResult(object()))
    monkeypatch.setattr(service, "run_p4_6d2_research_execution_stage", lambda *a, **k:
        P46d2ResearchExecutionStageResult(object(), []))
    monkeypatch.setattr(service, "run_p4_6e1_research_evidence_stage", lambda *a, **k:
        P46e1ResearchEvidenceStageResult(object(), []))
    monkeypatch.setattr(service, "run_p4_6e2_grounded_synthesis_stage", lambda *a, **k:
        P46e2GroundedSynthesisStageResult(authority_e2))

    def e3(*args, **kwargs):
        frame = inspect.currentframe().f_back.f_locals
        calls.append(("e3", args, kwargs, frame["task_grounded_synthesis_coverage_authority_p4_6e3"]))
        if error is not None:
            raise error
        return returned

    def v8(*args, **kwargs):
        frame = inspect.currentframe().f_back.f_locals
        calls.append(("v8", args, kwargs, frame["task_grounded_synthesis_coverage_authority_p4_6e3"]))
        raise StopAfterE3("controlled following boundary")

    monkeypatch.setattr(service, "build_task_grounded_synthesis_coverage_authority_canary_p4_6e3", e3)
    monkeypatch.setattr(service, "_run_intent_task_research_execution_canary_shadow", v8)
    monkeypatch.setattr(service, "has_service_accepted_execution", lambda *a: True)
    before = (tuple(results), tuple(typed_results), dict(trace), tuple(evidence) if isinstance(evidence, list) else None)
    return SimpleNamespace(**locals())


def _run(harness):
    with pytest.raises(StopAfterE3, match="controlled following boundary"):
        service._p4_15cp3c_previous_run_orchestrator(
            OrchestratorAskRequest(q="synthetic", vraag=""), sender=harness.sender)


@pytest.mark.parametrize("returned", [{"shape": "dict"}, [], (), None, object()])
def test_e3_called_once_after_e2_and_preserves_every_return_shape(monkeypatch, returned):
    h = _install(monkeypatch, returned=returned)
    _run(h)
    assert [call[0] for call in h.calls] == ["e3", "v8"]
    e3, v8 = h.calls
    assert e3[3] is None
    assert e3[1][:3] == (h.plan, h.authority_c, h.authority_e2)
    assert e3[1][0] is h.plan and e3[1][1] is h.authority_c and e3[1][2] is h.authority_e2
    assert isinstance(e3[1][3], tuple) and e3[1][3] is not h.evidence
    assert all(actual is expected for actual, expected in zip(e3[1][3], h.evidence))
    assert e3[2] == {"now": h.retrieved_at}
    assert v8[3] is returned
    assert all(value is not returned for value in v8[1])
    assert all(value is not returned for value in v8[2].values())
    assert (tuple(h.results), tuple(h.typed_results), dict(h.trace), tuple(h.evidence)) == h.before


def test_e3_exception_fails_open_to_none_and_reaches_v8(monkeypatch):
    h = _install(monkeypatch, error=RuntimeError("e3"))
    _run(h)
    assert [call[0] for call in h.calls] == ["e3", "v8"]
    assert h.calls[1][3] is None


@pytest.mark.parametrize("at", ["iteration", "call"])
def test_baseexception_propagates_and_prevents_v8(monkeypatch, at):
    fatal = FatalE3(at)
    h = _install(monkeypatch, error=fatal if at == "call" else None,
                 evidence=HostileEvidence(fatal) if at == "iteration" else None)
    with pytest.raises(FatalE3) as raised:
        service._p4_15cp3c_previous_run_orchestrator(
            OrchestratorAskRequest(q="synthetic", vraag=""), sender=h.sender)
    assert raised.value is fatal
    assert [call[0] for call in h.calls] == (["e3"] if at == "call" else [])


def test_iteration_exception_skips_e3_and_v8_calls_then_reaches_assessment(monkeypatch):
    h = _install(monkeypatch, evidence=HostileEvidence(RuntimeError("tuple")))
    monkeypatch.setattr(
        service,
        "assess_evidence",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            StopAfterE3("controlled following boundary")
        ),
    )
    _run(h)
    assert h.calls == []


def test_each_core_invocation_has_fresh_none_local_and_no_duplicate_boundaries(monkeypatch):
    marker = object()
    h = _install(monkeypatch, returned=marker)
    _run(h)
    _run(h)
    assert [call[0] for call in h.calls] == ["e3", "v8", "e3", "v8"]
    assert h.calls[0][3] is h.calls[2][3] is None
    assert h.calls[1][3] is h.calls[3][3] is marker
