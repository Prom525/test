"""Service integration contract for the extracted 3G2 recovery stage."""
from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

from app.orchestrator import service
from app.orchestrator.models import OrchestratorAskRequest
from app.orchestrator.phase_c_entry_stage import PhaseCEntryResult
from app.orchestrator.product_family_recovery_stage import ProductFamilyRecoveryResult


class BoundaryObserved(BaseException):
    pass


def _install(monkeypatch, *, stage_error=False):
    calls, captured = [], {}
    plan = SimpleNamespace(intent="synthetic_intent", clarification_required=False,
        clarification_question=None, execution_steps=(), research_required=False,
        requested_information=(), multi_intent=False)
    requirement, stamp, sender = object(), object(), object()
    initial = (object(),)
    counts = service._new_observability_counts()
    counts["phase_c_research_follow_up_specialist_calls"] = 7
    typed_results, raw_results, trace = [], [], {"attempts": []}
    entry = PhaseCEntryResult(requirement, stamp, initial, initial)

    monkeypatch.setattr(service, "_new_observability_counts", lambda: counts)
    monkeypatch.setattr(service, "run_initial_planning_stage", lambda *a, **k: plan)
    monkeypatch.setattr(service, "_record_initial_execution_observability", lambda *a: None)
    monkeypatch.setattr(service, "run_initial_execution_stage", lambda *a, **k: (
        calls.append(("initial_execution", a, k)) or SimpleNamespace(
            plan=plan, task_execution_plans_shadow=(),
            task_execution_plan_comparison_shadow=None,
            task_execution_canary_p4_6b=None, typed_execution_results=typed_results,
            results=raw_results, trace=trace, task_execution_shadow=None,
            task_planner_canary=None)))
    monkeypatch.setattr(service, "prepare_phase_c_entry", lambda *a, **k: (
        calls.append(("phase_c_entry", a, k)) or entry))

    dependencies = {
        "assess_product_family_coverage": lambda *a, **k: None,
        "recover_missing_product_families": lambda *a, **k: None,
        "normalize_execution_result_evidence": lambda *a, **k: None,
        "observability_nonnegative_int": service._observability_nonnegative_int,
    }
    monkeypatch.setattr(service, "assess_product_family_coverage",
                        dependencies["assess_product_family_coverage"])
    monkeypatch.setattr(service, "recover_missing_product_families",
                        dependencies["recover_missing_product_families"])
    monkeypatch.setattr(service, "normalize_execution_result_evidence",
                        dependencies["normalize_execution_result_evidence"])
    final_coverage, metadata = object(), object()

    def stage(*args, **kwargs):
        calls.append(("stage", args, kwargs))
        counts["phase_c_research_follow_up_specialist_calls"] += 2
        if stage_error:
            raise RuntimeError("stage failure")
        return ProductFamilyRecoveryResult(final_coverage, metadata,
                                           (initial[0], object()))

    monkeypatch.setattr(service, "run_product_family_recovery_stage", stage)

    def next_boundary(*args, **kwargs):
        captured.update(inspect.currentframe().f_back.f_locals)
        calls.append(("next_boundary", args, kwargs))
        raise BoundaryObserved("next boundary")

    monkeypatch.setattr(service, "run_task_evidence_stage", next_boundary)
    monkeypatch.setattr(service, "has_service_accepted_execution", lambda *a: True)

    def legacy_answer(*args, **kwargs):
        frame = inspect.currentframe().f_back
        while frame.f_code is not service._p4_15cp3c_previous_run_orchestrator.__code__:
            frame = frame.f_back
        captured.update(frame.f_locals)
        calls.append(("legacy_answer", args, kwargs))
        raise BoundaryObserved("legacy path")

    monkeypatch.setattr(service, "_build_user_answer", legacy_answer)
    return SimpleNamespace(calls=calls, captured=captured, plan=plan,
        requirement=requirement, stamp=stamp, sender=sender, initial=initial,
        counts=counts, typed_results=typed_results, raw_results=raw_results,
        trace=trace, dependencies=dependencies, coverage=final_coverage,
        metadata=metadata)


def _run(harness, match):
    with pytest.raises(BoundaryObserved, match=match):
        service._p4_15cp3c_previous_run_orchestrator(
            OrchestratorAskRequest(q="synthetic", vraag=""), sender=harness.sender)


def test_service_calls_stage_once_with_runtime_dependencies_and_binds_before_task_evidence(monkeypatch):
    harness = _install(monkeypatch)
    _run(harness, "next boundary")
    stages = [call for call in harness.calls if call[0] == "stage"]
    assert len(stages) == 1
    args, kwargs = stages[0][1:]
    assert args == (harness.plan, harness.requirement, harness.initial,
                    harness.initial, harness.stamp, harness.counts, harness.sender)
    assert all(kwargs[key] is value for key, value in harness.dependencies.items())
    assert [call[0] for call in harness.calls] == [
        "initial_execution", "phase_c_entry", "stage", "next_boundary"]
    assert harness.captured["product_family_coverage"] is harness.coverage
    assert harness.captured["product_family_recovery"] is harness.metadata
    assert harness.captured["working_evidence_items"][0] is harness.initial[0]


def test_stage_exception_uses_existing_outer_fail_open_and_preserves_partial_count(monkeypatch):
    harness = _install(monkeypatch, stage_error=True)
    _run(harness, "legacy path")
    assert [call[0] for call in harness.calls] == [
        "initial_execution", "phase_c_entry", "stage", "legacy_answer"]
    assert harness.captured["evidence_pipeline"] is None
    assert harness.counts["phase_c_research_follow_up_specialist_calls"] == 9
    assert harness.typed_results == [] and harness.raw_results == []
    assert harness.trace == {"attempts": []}


def test_stage_lookup_is_runtime_resolved_on_each_core_call(monkeypatch):
    harness = _install(monkeypatch)
    _run(harness, "next boundary")
    replacement = object()
    monkeypatch.setattr(service, "assess_product_family_coverage", replacement)
    harness.calls.clear()
    _run(harness, "next boundary")
    stage = next(call for call in harness.calls if call[0] == "stage")
    assert stage[2]["assess_product_family_coverage"] is replacement
