from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.orchestrator import service
from app.orchestrator.models import OrchestratorAskRequest
from app.orchestrator.phase_c_entry_stage import PhaseCEntryResult
from app.orchestrator.product_family_recovery_stage import ProductFamilyRecoveryResult
from app.orchestrator.task_evidence_stage import TaskEvidenceStageResult
from app.orchestrator.task_research_decision_stage import (
    TaskResearchDecisionStageResult,
)


class ContextBoundaryObserved(BaseException):
    pass


def test_service_runtime_dependencies_bind_outputs_and_context_gets_shadow_only(
    monkeypatch,
):
    calls = []
    plan = SimpleNamespace(
        intent="synthetic", clarification_required=False,
        clarification_question=None, execution_steps=(), research_required=False,
        requested_information=("synthetic",), multi_intent=False,
    )
    results = [object(), object()]
    stamp = object()
    working_evidence = [object()]
    evidence_shadow = object()
    evidence_authority = object()
    decisions_output = object()
    authority_output = object()

    monkeypatch.setattr(service, "_new_observability_counts", lambda: {})
    monkeypatch.setattr(service, "run_initial_planning_stage", lambda *a, **k: plan)
    monkeypatch.setattr(service, "_record_initial_execution_observability", lambda *a: None)
    monkeypatch.setattr(service, "run_initial_execution_stage", lambda *a, **k: SimpleNamespace(
        plan=plan, task_execution_plans_shadow=(),
        task_execution_plan_comparison_shadow=None, task_execution_canary_p4_6b=None,
        typed_execution_results=[], results=results, trace={"attempts": []},
        task_execution_shadow=None, task_planner_canary=None,
    ))
    monkeypatch.setattr(service, "prepare_phase_c_entry", lambda *a, **k:
                        PhaseCEntryResult(object(), stamp, tuple(working_evidence),
                                          tuple(working_evidence)))
    monkeypatch.setattr(service, "run_product_family_recovery_stage", lambda *a, **k:
                        ProductFamilyRecoveryResult(object(), object(), working_evidence))
    monkeypatch.setattr(service, "run_task_evidence_stage", lambda *a, **k:
                        TaskEvidenceStageResult(evidence_shadow, evidence_authority))

    def shadow_dependency(*args, **kwargs):
        raise AssertionError("stage owns dependency execution")

    def authority_dependency(*args, **kwargs):
        raise AssertionError("stage owns dependency execution")

    monkeypatch.setattr(service, "_derive_intent_task_research_decisions_shadow",
                        shadow_dependency)
    monkeypatch.setattr(service, "build_task_research_authority_canary_p4_6d1",
                        authority_dependency)

    def stage(actual_shadow, actual_authority, **dependencies):
        calls.append(("stage", actual_shadow, actual_authority, dependencies))
        return TaskResearchDecisionStageResult(decisions_output, authority_output)

    monkeypatch.setattr(service, "run_task_research_decision_stage", stage)

    def context(actual_plan, actual_results, actual_decisions):
        frame = __import__("inspect").currentframe().f_back.f_locals
        calls.append(("context", actual_plan, actual_results, actual_decisions, frame))
        raise ContextBoundaryObserved

    monkeypatch.setattr(service, "_derive_intent_task_research_contexts_shadow", context)
    monkeypatch.setattr(service, "has_service_accepted_execution", lambda *a: True)

    with pytest.raises(ContextBoundaryObserved):
        service._p4_15cp3c_previous_run_orchestrator(
            OrchestratorAskRequest(q="synthetic", vraag=""), sender=object()
        )

    assert [call[0] for call in calls] == ["stage", "context"]
    stage_call, context_call = calls
    assert stage_call[1] is evidence_shadow
    assert stage_call[2] is evidence_authority
    assert stage_call[3]["derive_intent_task_research_decisions_shadow"] is shadow_dependency
    assert stage_call[3]["build_task_research_authority_canary_p4_6d1"] is authority_dependency
    assert context_call[1] is plan
    assert context_call[2] is not results
    assert all(actual is expected for actual, expected in zip(context_call[2], results))
    assert context_call[3] is decisions_output
    assert context_call[4]["task_research_decisions_shadow"] is decisions_output
    assert context_call[4]["task_research_authority_p4_6d1"] is authority_output
