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


class StopAtE1(BaseException):
    pass


def test_core_calls_stage_once_with_runtime_dependency_and_binds_e1_inputs(monkeypatch):
    calls = []
    plan = SimpleNamespace(
        intent="synthetic", clarification_required=False,
        clarification_question=None, execution_steps=(), research_required=False,
        requested_information=("synthetic",), multi_intent=False,
    )
    authority_d1, contexts, guards, sender, cp13 = (object() for _ in range(5))
    results = [object(), object()]
    authority_d2, observations = object(), [object(), object()]
    evidence = [object(), object()]
    retrieved_at = object()

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
        TaskResearchDecisionStageResult(object(), authority_d1))
    monkeypatch.setattr(service, "run_task_research_context_stage", lambda *a, **k:
        TaskResearchContextStageResult(contexts, guards))
    monkeypatch.setattr(service, "run_cp13_research_semantics_stage", lambda *a, **k:
        Cp13ResearchSemanticsStageResult(cp13))
    runtime_d2 = object()
    monkeypatch.setattr(service, "run_task_research_execution_authority_canary_p4_6d2", runtime_d2)

    def stage(*args, **kwargs):
        calls.append(("stage", args, kwargs))
        return P46d2ResearchExecutionStageResult(authority_d2, observations)

    def e1(*args, **kwargs):
        calls.append(("e1", args, kwargs))
        raise StopAtE1

    monkeypatch.setattr(service, "run_p4_6d2_research_execution_stage", stage)
    monkeypatch.setattr(service, "build_task_research_evidence_authority_canary_p4_6e1", e1)
    monkeypatch.setattr(service, "has_service_accepted_execution", lambda *a: True)

    with pytest.raises(StopAtE1):
        service._p4_15cp3c_previous_run_orchestrator(
            OrchestratorAskRequest(q="synthetic", vraag=""), sender=sender)

    assert [row[0] for row in calls] == ["stage", "e1"]
    stage_call, e1_call = calls
    assert stage_call[1] == (plan, results, authority_d1, contexts, guards, sender, cp13)
    assert stage_call[2] == {
        "run_task_research_execution_authority_canary_p4_6d2": runtime_d2}
    assert e1_call[1][0] is plan and e1_call[1][1] is authority_d2
    assert e1_call[1][2] is observations
    assert isinstance(e1_call[1][3], tuple)
    assert all(a is b for a, b in zip(e1_call[1][3], evidence))
    assert e1_call[2]["now"] is retrieved_at
    observer = e1_call[2]["grounded_synthesis_observer"]
    assert observer.__self__ == [] and observer.__self__ is not observations
