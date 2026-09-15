from __future__ import annotations

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


class P46d2Observed(BaseException):
    pass


def test_core_calls_stage_once_with_runtime_dependency_and_forwards_identity(monkeypatch):
    calls = []
    plan = SimpleNamespace(intent="synthetic", clarification_required=False,
        clarification_question=None, execution_steps=(), research_required=False,
        requested_information=("synthetic",), multi_intent=False)
    result_values = [object(), object()]
    results = list(result_values)
    execution_shadow, research_authority = object(), object()
    contexts, guards, sender = object(), object(), object()
    cp13_dependency, cp13_sentinel = object(), object()

    monkeypatch.setattr(service, "_new_observability_counts", lambda: {})
    monkeypatch.setattr(service, "run_initial_planning_stage", lambda *a, **k: plan)
    monkeypatch.setattr(service, "_record_initial_execution_observability", lambda *a: None)
    monkeypatch.setattr(service, "run_initial_execution_stage", lambda *a, **k: SimpleNamespace(
        plan=plan, task_execution_plans_shadow=(), task_execution_plan_comparison_shadow=None,
        task_execution_canary_p4_6b=None, typed_execution_results=[], results=results,
        trace={"attempts": []}, task_execution_shadow=execution_shadow,
        task_planner_canary=None))
    monkeypatch.setattr(service, "prepare_phase_c_entry", lambda *a, **k:
        PhaseCEntryResult(object(), object(), (), ()))
    monkeypatch.setattr(service, "run_product_family_recovery_stage", lambda *a, **k:
        ProductFamilyRecoveryResult(object(), object(), []))
    monkeypatch.setattr(service, "run_task_evidence_stage", lambda *a, **k:
        TaskEvidenceStageResult(object(), object()))
    monkeypatch.setattr(service, "run_task_research_decision_stage", lambda *a, **k:
        TaskResearchDecisionStageResult(object(), research_authority))
    monkeypatch.setattr(service, "run_task_research_context_stage", lambda *a, **k:
        TaskResearchContextStageResult(contexts, guards))
    monkeypatch.setattr(service, "build_task_research_semantics", cp13_dependency)

    def stage(*args, **dependencies):
        calls.append(("stage", args, dependencies))
        return Cp13ResearchSemanticsStageResult(cp13_sentinel)

    def p4(*args, **kwargs):
        calls.append(("p4.6d2", args, kwargs))
        raise P46d2Observed("controlled stop")

    monkeypatch.setattr(service, "run_cp13_research_semantics_stage", stage)
    monkeypatch.setattr(service, "run_task_research_execution_authority_canary_p4_6d2", p4)
    monkeypatch.setattr(service, "has_service_accepted_execution", lambda *a: True)

    with pytest.raises(P46d2Observed, match="controlled stop"):
        service._p4_15cp3c_previous_run_orchestrator(
            OrchestratorAskRequest(q="synthetic", vraag=""), sender=sender)

    assert [call[0] for call in calls] == ["stage", "p4.6d2"]
    stage_call, p4_call = calls
    assert stage_call[1] == (plan, execution_shadow, research_authority)
    assert all(actual is expected for actual, expected in zip(
        stage_call[1], (plan, execution_shadow, research_authority)))
    assert stage_call[2] == {"build_task_research_semantics": cp13_dependency}
    assert p4_call[1][0] is plan
    assert p4_call[1][1] is not results
    assert all(a is b for a, b in zip(p4_call[1][1], result_values))
    assert p4_call[1][2:] == (research_authority, contexts, guards)
    assert p4_call[2]["sender"] is sender
    assert callable(p4_call[2]["evidence_observer"])
    assert p4_call[2]["evidence_observer"].__name__ == "append"
    assert p4_call[2]["task_research_semantics_cp13"] is cp13_sentinel
