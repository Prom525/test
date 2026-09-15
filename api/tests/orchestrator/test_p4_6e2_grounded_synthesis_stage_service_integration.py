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


class StopAtE3(BaseException):
    pass


def test_core_calls_stage_once_binds_result_and_keeps_e3_tuple_zone(monkeypatch):
    calls = []
    plan = SimpleNamespace(
        intent="synthetic", clarification_required=False,
        clarification_question=None, execution_steps=(), research_required=False,
        requested_information=("synthetic",), multi_intent=False,
    )
    sender, results = object(), []
    authority_d2, observations = object(), [object()]
    authority_e1, units = object(), [object(), object()]
    authority_p4_6c, retrieved_at = object(), object()
    evidence = [object(), object()]
    sentinel = object()

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
    runtime_e2 = object()
    monkeypatch.setattr(service, "build_task_grounded_synthesis_authority_canary_p4_6e2", runtime_e2)

    def stage(*args, **kwargs):
        calls.append(("stage", args, kwargs))
        return P46e2GroundedSynthesisStageResult(sentinel)

    def e3(*args, **kwargs):
        calls.append(("e3", args, kwargs))
        raise StopAtE3("controlled E3 boundary")

    monkeypatch.setattr(service, "run_p4_6e2_grounded_synthesis_stage", stage)
    monkeypatch.setattr(service, "build_task_grounded_synthesis_coverage_authority_canary_p4_6e3", e3)
    monkeypatch.setattr(service, "has_service_accepted_execution", lambda *a: True)

    with pytest.raises(StopAtE3, match="controlled E3 boundary"):
        service._p4_15cp3c_previous_run_orchestrator(
            OrchestratorAskRequest(q="synthetic", vraag=""), sender=sender)

    assert [call[0] for call in calls] == ["stage", "e3"]
    stage_call, e3_call = calls
    assert stage_call[1] == (authority_e1, units)
    assert stage_call[1][0] is authority_e1 and stage_call[1][1] is units
    assert stage_call[2] == {
        "build_task_grounded_synthesis_authority_canary_p4_6e2": runtime_e2,
    }
    assert e3_call[1][0] is plan
    assert e3_call[1][1] is authority_p4_6c
    assert e3_call[1][2] is sentinel
    assert isinstance(e3_call[1][3], tuple) and e3_call[1][3] is not evidence
    assert all(actual is expected for actual, expected in zip(e3_call[1][3], evidence))
    assert e3_call[2] == {"now": retrieved_at}
