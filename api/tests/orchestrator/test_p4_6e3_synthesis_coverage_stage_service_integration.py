import ast
from pathlib import Path
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


def _install(monkeypatch, *, stage_error=None):
    calls = []
    plan = SimpleNamespace(
        intent="synthetic", clarification_required=False,
        clarification_question=None, execution_steps=(), research_required=False,
        requested_information=("synthetic",), multi_intent=False,
    )
    results, evidence = [], [object(), object()]
    authority_c, authority_e2, retrieved_at, returned = (object() for _ in range(4))
    runtime_builder = object()
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
        TaskEvidenceStageResult(object(), authority_c))
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

    def e2(*args, **kwargs):
        calls.append("e2")
        return P46e2GroundedSynthesisStageResult(authority_e2)

    def e3(*args, **kwargs):
        calls.append(("e3", args, kwargs))
        if stage_error is not None:
            return P46e3SynthesisCoverageStageResult(None)
        return P46e3SynthesisCoverageStageResult(returned)

    def v8(*args, **kwargs):
        calls.append(("v8", args, kwargs))
        return []

    monkeypatch.setattr(service, "run_p4_6e2_grounded_synthesis_stage", e2)
    monkeypatch.setattr(service, "run_p4_6e3_synthesis_coverage_stage", e3)
    monkeypatch.setattr(service, "build_task_grounded_synthesis_coverage_authority_canary_p4_6e3", runtime_builder)
    monkeypatch.setattr(service, "_run_intent_task_research_execution_canary_shadow", v8)
    monkeypatch.setattr(service, "assess_evidence", lambda *a, **k: (_ for _ in ()).throw(StopAtAssessment()))
    monkeypatch.setattr(service, "has_service_accepted_execution", lambda *a: True)
    return SimpleNamespace(**locals())


def test_exact_single_stage_between_e2_and_v8_and_runtime_binding(monkeypatch):
    h = _install(monkeypatch)
    with pytest.raises(StopAtAssessment):
        service._p4_15cp3c_previous_run_orchestrator(
            OrchestratorAskRequest(q="synthetic", vraag=""), sender=object())
    assert [call if isinstance(call, str) else call[0] for call in h.calls] == ["e2", "e3", "v8"]
    _, args, kwargs = h.calls[1]
    assert args == (h.plan, h.authority_c, h.authority_e2, h.evidence, h.retrieved_at)
    assert kwargs == {
        "build_task_grounded_synthesis_coverage_authority_canary_p4_6e3": h.runtime_builder,
    }
    _, v8_args, v8_kwargs = h.calls[2]
    assert all(value is not h.returned for value in v8_args)
    assert all(value is not h.returned for value in v8_kwargs.values())


def test_ordinary_stage_failure_remains_fail_open_and_reaches_v8(monkeypatch):
    h = _install(monkeypatch, stage_error=RuntimeError("stage"))
    with pytest.raises(StopAtAssessment):
        service._p4_15cp3c_previous_run_orchestrator(
            OrchestratorAskRequest(q="synthetic", vraag=""), sender=object())
    assert [call if isinstance(call, str) else call[0] for call in h.calls] == ["e2", "e3", "v8"]


def test_leaf_import_surface_and_single_service_callsite():
    root = Path(__file__).parents[2]
    leaf = ast.parse((root / "app/orchestrator/p4_6e3_synthesis_coverage_stage.py").read_text())
    imports = {
        alias.name for node in leaf.body if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module for node in leaf.body if isinstance(node, ast.ImportFrom)
    }
    assert imports == {"dataclasses", "typing"}
    service_source = (root / "app/orchestrator/service.py").read_text()
    assert service_source.count("run_p4_6e3_synthesis_coverage_stage(") == 1
    assert service_source.count(".task_grounded_synthesis_coverage_authority_p4_6e3") == 1
