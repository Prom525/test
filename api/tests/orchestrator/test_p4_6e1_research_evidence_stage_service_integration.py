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


class StopAtE2(BaseException):
    pass


def test_core_calls_stage_once_with_runtime_dependency_and_binds_exact_e2_inputs(monkeypatch):
    calls = []
    plan = SimpleNamespace(
        intent="synthetic", clarification_required=False,
        clarification_question=None, execution_steps=(), research_required=False,
        requested_information=("synthetic",), multi_intent=False,
    )
    results, sender = [object()], object()
    authority_d2, observations = object(), [object(), object()]
    evidence, retrieved_at = [object(), object()], object()
    authority_e1, units = object(), [object(), object()]

    monkeypatch.setattr(service, "_new_observability_counts", lambda: {})
    monkeypatch.setattr(service, "run_initial_planning_stage", lambda *a, **k: plan)
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
        TaskEvidenceStageResult(object(), object()))
    monkeypatch.setattr(service, "run_task_research_decision_stage", lambda *a, **k:
        TaskResearchDecisionStageResult(object(), object()))
    monkeypatch.setattr(service, "run_task_research_context_stage", lambda *a, **k:
        TaskResearchContextStageResult(object(), object()))
    monkeypatch.setattr(service, "run_cp13_research_semantics_stage", lambda *a, **k:
        Cp13ResearchSemanticsStageResult(object()))
    monkeypatch.setattr(service, "run_p4_6d2_research_execution_stage", lambda *a, **k:
        P46d2ResearchExecutionStageResult(authority_d2, observations))
    runtime_e1 = object()
    monkeypatch.setattr(service, "build_task_research_evidence_authority_canary_p4_6e1", runtime_e1)

    def stage(*args, **kwargs):
        calls.append(("stage", args, kwargs))
        return P46e1ResearchEvidenceStageResult(authority_e1, units)

    def e2(*args, **kwargs):
        frame = __import__("inspect").currentframe().f_back.f_locals
        calls.append(("e2", args, kwargs, frame["task_grounded_synthesis_authority_p4_6e2"]))
        raise StopAtE2

    monkeypatch.setattr(service, "run_p4_6e1_research_evidence_stage", stage)
    monkeypatch.setattr(service, "build_task_grounded_synthesis_authority_canary_p4_6e2", e2)
    monkeypatch.setattr(service, "has_service_accepted_execution", lambda *a: True)

    with pytest.raises(StopAtE2):
        service._p4_15cp3c_previous_run_orchestrator(
            OrchestratorAskRequest(q="synthetic", vraag=""), sender=sender)

    assert [row[0] for row in calls] == ["stage", "e2"]
    stage_call, e2_call = calls
    assert stage_call[1] == (plan, authority_d2, observations, evidence, retrieved_at)
    assert all(stage_call[1][index] is expected for index, expected in enumerate(
        (plan, authority_d2, observations, evidence, retrieved_at)))
    assert stage_call[2] == {
        "build_task_research_evidence_authority_canary_p4_6e1": runtime_e1}
    assert e2_call[1][0] is authority_e1 and e2_call[1][1] is units
    assert e2_call[3] is None
