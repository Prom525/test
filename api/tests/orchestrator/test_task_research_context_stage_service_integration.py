from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.orchestrator import service
from app.orchestrator.models import OrchestratorAskRequest
from app.orchestrator.phase_c_entry_stage import PhaseCEntryResult
from app.orchestrator.product_family_recovery_stage import ProductFamilyRecoveryResult
from app.orchestrator.task_evidence_stage import TaskEvidenceStageResult
from app.orchestrator.task_research_context_stage import TaskResearchContextStageResult
from app.orchestrator.task_research_decision_stage import TaskResearchDecisionStageResult


class Cp13Observed(BaseException):
    pass


def test_service_calls_stage_once_with_runtime_dependencies_binds_outputs_before_cp13(monkeypatch):
    calls = []
    plan = SimpleNamespace(intent="synthetic", clarification_required=False,
        clarification_question=None, execution_steps=(), research_required=False,
        requested_information=("synthetic",), multi_intent=False)
    results = [object(), object()]
    execution_shadow = object()
    decisions = object()
    research_authority = object()
    contexts = object()
    guards = object()
    context_dependency = object()
    guard_dependency = object()

    monkeypatch.setattr(service, "_new_observability_counts", lambda: {})
    monkeypatch.setattr(service, "run_initial_planning_stage", lambda *a, **k: plan)
    monkeypatch.setattr(service, "_record_initial_execution_observability", lambda *a: None)
    monkeypatch.setattr(service, "run_initial_execution_stage", lambda *a, **k: SimpleNamespace(
        plan=plan, task_execution_plans_shadow=(), task_execution_plan_comparison_shadow=None,
        task_execution_canary_p4_6b=None, typed_execution_results=[], results=results,
        trace={"attempts": []}, task_execution_shadow=execution_shadow, task_planner_canary=None))
    monkeypatch.setattr(service, "prepare_phase_c_entry", lambda *a, **k:
        PhaseCEntryResult(object(), object(), (), ()))
    monkeypatch.setattr(service, "run_product_family_recovery_stage", lambda *a, **k:
        ProductFamilyRecoveryResult(object(), object(), []))
    monkeypatch.setattr(service, "run_task_evidence_stage", lambda *a, **k:
        TaskEvidenceStageResult(object(), object()))
    monkeypatch.setattr(service, "run_task_research_decision_stage", lambda *a, **k:
        TaskResearchDecisionStageResult(decisions, research_authority))
    monkeypatch.setattr(service, "_derive_intent_task_research_contexts_shadow",
                        context_dependency)
    monkeypatch.setattr(service, "_derive_intent_task_research_call_guards_shadow",
                        guard_dependency)

    def stage(*args, **dependencies):
        calls.append(("stage", args, dependencies))
        return TaskResearchContextStageResult(contexts, guards)

    def cp13(*args, **kwargs):
        frame = __import__("inspect").currentframe().f_back.f_locals
        calls.append(("cp13", args, frame))
        raise Cp13Observed

    monkeypatch.setattr(service, "run_task_research_context_stage", stage)
    monkeypatch.setattr(service, "run_cp13_research_semantics_stage", cp13)
    monkeypatch.setattr(service, "has_service_accepted_execution", lambda *a: True)

    with pytest.raises(Cp13Observed):
        service._p4_15cp3c_previous_run_orchestrator(
            OrchestratorAskRequest(q="synthetic", vraag=""), sender=object())

    assert [call[0] for call in calls] == ["stage", "cp13"]
    stage_call, cp13_call = calls
    assert stage_call[1] == (plan, results, decisions)
    assert stage_call[1][1] is results
    assert stage_call[2]["derive_intent_task_research_contexts_shadow"] is context_dependency
    assert stage_call[2]["derive_intent_task_research_call_guards_shadow"] is guard_dependency
    assert cp13_call[1] == (plan, execution_shadow, research_authority)
    assert contexts not in cp13_call[1] and guards not in cp13_call[1]
    assert cp13_call[2]["task_research_contexts_shadow"] is contexts
    assert cp13_call[2]["task_research_call_guards_shadow"] is guards
