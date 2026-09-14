from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.orchestrator import service
from app.orchestrator.models import OrchestratorAskRequest
from app.orchestrator.phase_c_entry_stage import PhaseCEntryResult
from app.orchestrator.product_family_recovery_stage import ProductFamilyRecoveryResult
from app.orchestrator.task_evidence_stage import TaskEvidenceStageResult


class BoundaryObserved(BaseException):
    pass


def test_service_runtime_dependencies_bind_both_outputs_and_research_gets_only_shadow(
    monkeypatch,
):
    calls = []
    plan = SimpleNamespace(
        intent="synthetic", clarification_required=False,
        clarification_question=None, execution_steps=(), research_required=False,
        requested_information=("synthetic",), multi_intent=False,
    )
    stamp = object()
    evidence = [object()]
    shadow_output = object()
    authority_output = object()

    monkeypatch.setattr(service, "_new_observability_counts", lambda: {})
    monkeypatch.setattr(service, "run_initial_planning_stage", lambda *a, **k: plan)
    monkeypatch.setattr(service, "_record_initial_execution_observability", lambda *a: None)
    monkeypatch.setattr(service, "run_initial_execution_stage", lambda *a, **k: SimpleNamespace(
        plan=plan, task_execution_plans_shadow=(),
        task_execution_plan_comparison_shadow=None, task_execution_canary_p4_6b=None,
        typed_execution_results=[], results=[], trace={"attempts": []},
        task_execution_shadow=None, task_planner_canary=None,
    ))
    monkeypatch.setattr(service, "prepare_phase_c_entry", lambda *a, **k: PhaseCEntryResult(object(), stamp, tuple(evidence), tuple(evidence)))
    monkeypatch.setattr(service, "run_product_family_recovery_stage", lambda *a, **k: ProductFamilyRecoveryResult(object(), object(), evidence))

    def shadow(*args, **kwargs):
        calls.append(("shadow_dependency", args, kwargs))
        return object()

    def authority(*args, **kwargs):
        calls.append(("authority_dependency", args, kwargs))
        return object()

    monkeypatch.setattr(service, "_assess_intent_task_evidence_shadow", shadow)
    monkeypatch.setattr(service, "build_task_evidence_authority_canary_p4_6c", authority)

    def stage(actual_plan, actual_evidence, actual_stamp, **dependencies):
        calls.append(("stage", actual_plan, actual_evidence, actual_stamp, dependencies))
        assert dependencies["assess_intent_task_evidence_shadow"] is shadow
        assert dependencies["build_task_evidence_authority_canary_p4_6c"] is authority
        return TaskEvidenceStageResult(shadow_output, authority_output)

    monkeypatch.setattr(service, "run_task_evidence_stage", stage)

    def research(value):
        calls.append(("research", value))
        frame = __import__("inspect").currentframe().f_back.f_locals
        assert frame["task_evidence_assessments_shadow"] is shadow_output
        assert frame["task_evidence_authority_p4_6c"] is authority_output
        raise BoundaryObserved

    monkeypatch.setattr(service, "_derive_intent_task_research_decisions_shadow", research)
    monkeypatch.setattr(service, "has_service_accepted_execution", lambda *a: True)

    with pytest.raises(BoundaryObserved):
        service._p4_15cp3c_previous_run_orchestrator(
            OrchestratorAskRequest(q="synthetic", vraag=""), sender=object()
        )

    assert [call[0] for call in calls] == ["stage", "research"]
    assert calls[0][1] is plan
    assert calls[0][2] is evidence
    assert calls[0][3] is stamp
    assert calls[1][1] is shadow_output
