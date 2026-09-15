"""Characterize the service-owned P4.6E2 invocation and P4.6E3 boundary."""
import inspect
from types import SimpleNamespace

import pytest

from app.orchestrator import service
from app.orchestrator.cp13_research_semantics_stage import Cp13ResearchSemanticsStageResult
from app.orchestrator.models import OrchestratorAskRequest
from app.orchestrator.p4_6d2_research_execution_stage import P46d2ResearchExecutionStageResult
from app.orchestrator.p4_6e1_research_evidence_stage import P46e1ResearchEvidenceStageResult
from app.orchestrator.phase_c_entry_stage import PhaseCEntryResult
from app.orchestrator.product_family_recovery_stage import ProductFamilyRecoveryResult
from app.orchestrator.task_evidence_stage import TaskEvidenceStageResult
from app.orchestrator.task_research_context_stage import TaskResearchContextStageResult
from app.orchestrator.task_research_decision_stage import TaskResearchDecisionStageResult


class StopAtE3(BaseException):
    pass


class FatalE2(BaseException):
    pass


class HostileEvidence:
    def __init__(self, error):
        self.error = error

    def __iter__(self):
        raise self.error


def _install(monkeypatch, *, e2_return=None, e2_error=None, evidence=None):
    calls = []
    plan = SimpleNamespace(
        intent="synthetic", clarification_required=False,
        clarification_question=None, execution_steps=(), research_required=False,
        requested_information=("synthetic",), multi_intent=False,
    )
    results, sender = [], object()
    authority_d2, observations = object(), [object()]
    authority_e1, units = object(), [object(), object()]
    authority_p4_6c, retrieved_at = object(), object()
    evidence = [object(), object()] if evidence is None else evidence
    before = (tuple(results), tuple(observations), tuple(units))

    monkeypatch.setattr(service, "run_initial_planning_stage", lambda *a, **k: plan)
    monkeypatch.setattr(service, "_model_to_dict", lambda value: {})
    monkeypatch.setattr(service, "_record_initial_execution_observability", lambda *a: None)
    monkeypatch.setattr(service, "run_initial_execution_stage", lambda *a, **k: SimpleNamespace(
        plan=plan, task_execution_plans_shadow=(), task_execution_plan_comparison_shadow=None,
        task_execution_canary_p4_6b=None, typed_execution_results=[], results=results,
        trace={}, task_execution_shadow=object(), task_planner_canary=None))
    monkeypatch.setattr(service, "prepare_phase_c_entry", lambda *a, **k:
        PhaseCEntryResult(object(), retrieved_at, (), ()))
    monkeypatch.setattr(service, "run_product_family_recovery_stage", lambda *a, **k:
        ProductFamilyRecoveryResult(object(), object(), evidence))
    monkeypatch.setattr(service, "run_task_evidence_stage", lambda *a, **k:
        TaskEvidenceStageResult(object(), authority_p4_6c))
    monkeypatch.setattr(service, "run_task_research_decision_stage", lambda *a, **k:
        TaskResearchDecisionStageResult(object(), object()))
    monkeypatch.setattr(service, "run_task_research_context_stage", lambda *a, **k:
        TaskResearchContextStageResult(object(), object()))
    monkeypatch.setattr(service, "run_cp13_research_semantics_stage", lambda *a, **k:
        Cp13ResearchSemanticsStageResult(object()))
    monkeypatch.setattr(service, "run_p4_6d2_research_execution_stage", lambda *a, **k:
        P46d2ResearchExecutionStageResult(authority_d2, observations))
    monkeypatch.setattr(service, "run_p4_6e1_research_evidence_stage", lambda *a, **k:
        P46e1ResearchEvidenceStageResult(authority_e1, units))

    def e2(*args, **kwargs):
        frame = inspect.currentframe().f_back.f_locals
        calls.append(("e2", args, kwargs,
                      frame["task_grounded_synthesis_authority_p4_6e2"]))
        if e2_error is not None:
            raise e2_error
        return e2_return

    def e3(*args, **kwargs):
        frame = inspect.currentframe().f_back.f_locals
        calls.append(("e3", args, kwargs,
                      frame["task_grounded_synthesis_coverage_authority_p4_6e3"]))
        raise StopAtE3("controlled E3 boundary")

    monkeypatch.setattr(service, "build_task_grounded_synthesis_authority_canary_p4_6e2", e2)
    monkeypatch.setattr(service, "build_task_grounded_synthesis_coverage_authority_canary_p4_6e3", e3)
    monkeypatch.setattr(service, "has_service_accepted_execution", lambda *a: True)
    return SimpleNamespace(**locals())


def _run(harness):
    with pytest.raises(StopAtE3, match="controlled E3 boundary"):
        service._p4_15cp3c_previous_run_orchestrator(
            OrchestratorAskRequest(q="synthetic", vraag=""), sender=harness.sender)


@pytest.mark.parametrize("returned", [[], (), {"shape": "mapping"}, None, object()])
def test_e2_once_preserves_return_identity_and_exact_e3_handoff(monkeypatch, returned):
    h = _install(monkeypatch, e2_return=returned)
    _run(h)
    assert [row[0] for row in h.calls] == ["e2", "e3"]
    e2, e3 = h.calls
    assert e2[3] is None
    assert e2[1] == (h.authority_e1, h.units)
    assert e2[1][0] is h.authority_e1 and e2[1][1] is h.units
    assert e3[3] is None
    assert e3[1][0] is h.plan
    assert e3[1][1] is h.authority_p4_6c
    assert e3[1][2] is returned
    assert isinstance(e3[1][3], tuple) and e3[1][3] is not h.evidence
    assert all(a is b for a, b in zip(e3[1][3], h.evidence))
    assert e3[2] == {"now": h.retrieved_at}
    assert (tuple(h.results), tuple(h.observations), tuple(h.units)) == h.before


def test_e2_exception_fails_open_to_none_and_e3_remains_reachable(monkeypatch):
    h = _install(monkeypatch, e2_error=RuntimeError("e2"))
    _run(h)
    assert [row[0] for row in h.calls] == ["e2", "e3"]
    assert h.calls[1][1][2] is None


def test_e2_baseexception_propagates_without_e3(monkeypatch):
    fatal = FatalE2("fatal")
    h = _install(monkeypatch, e2_error=fatal)
    with pytest.raises(FatalE2) as raised:
        service._p4_15cp3c_previous_run_orchestrator(
            OrchestratorAskRequest(q="synthetic", vraag=""), sender=h.sender)
    assert raised.value is fatal
    assert [row[0] for row in h.calls] == ["e2"]


@pytest.mark.parametrize("error_type", [RuntimeError, KeyboardInterrupt])
def test_working_evidence_tuple_conversion_belongs_to_e3_zone(monkeypatch, error_type):
    error = error_type("tuple")
    h = _install(monkeypatch, e2_return=object(), evidence=HostileEvidence(error))
    if error_type is RuntimeError:
        service._p4_15cp3c_previous_run_orchestrator(
            OrchestratorAskRequest(q="synthetic", vraag=""), sender=h.sender)
    else:
        with pytest.raises(error_type) as raised:
            service._p4_15cp3c_previous_run_orchestrator(
                OrchestratorAskRequest(q="synthetic", vraag=""), sender=h.sender)
        assert raised.value is error
    assert [row[0] for row in h.calls] == ["e2"]


def test_fresh_e2_and_e3_locals_and_no_duplicate_stage_execution(monkeypatch):
    marker = object()
    h = _install(monkeypatch, e2_return=marker)
    _run(h)
    _run(h)
    assert [row[0] for row in h.calls] == ["e2", "e3", "e2", "e3"]
    assert all(row[3] is None for row in h.calls)
