import ast
import importlib.util
from pathlib import Path

import pytest

from app.orchestrator import service
from app.orchestrator.phase_c_reconciliation_stage import (
    PhaseCReconciliationStageResult,
)


def _characterization():
    path = Path(__file__).with_name(
        "test_phase_c_reconciliation_metrics_boundary_characterization.py")
    spec = importlib.util.spec_from_file_location("phase_c_3s1_for_3s2", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runtime_dependencies_direct_binding_same_synthesis_object_and_order(
        monkeypatch):
    characterized = _characterization()
    source_reconciliation = object()
    h = characterized._install(
        monkeypatch, reconciliation=source_reconciliation)
    stage_reconciliation = object()
    calls = []

    def stage(*args, **kwargs):
        calls.append((args, kwargs))
        return PhaseCReconciliationStageResult(stage_reconciliation)

    monkeypatch.setattr(service, "run_phase_c_reconciliation_stage", stage)
    characterized._run(h)
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args == (
        h.base.h.timings,
        h.base.h.counts,
        h.base.h.requirement_set,
        h.base.h.working_evidence_items,
        h.initial_assessment,
        h.research_execution,
        h.base.h.retrieved_at,
    )
    assert all(
        actual is expected
        for actual, expected in zip(args, (
            h.base.h.timings,
            h.base.h.counts,
            h.base.h.requirement_set,
            h.base.h.working_evidence_items,
            h.initial_assessment,
            h.research_execution,
            h.base.h.retrieved_at,
        ))
    )
    assert kwargs == {
        "observability_call": service._observability_call,
        "observability_get": service._observability_get,
        "reconcile_evidence_callable": service.reconcile_evidence,
    }
    assert not [row for row in h.boundary_calls if row[0] in {"reconcile", "get"}]
    synthesis = [row for row in h.boundary_calls if row[0] == "synthesis"]
    assert len(synthesis) == 1
    assert synthesis[0][1][0] is stage_reconciliation


@pytest.mark.parametrize("fatal", [False, True])
def test_stage_exception_keeps_outer_fail_open_and_baseexception_boundary(
        monkeypatch, fatal):
    characterized = _characterization()
    h = characterized._install(monkeypatch)
    error = characterized.Fatal("fatal") if fatal else RuntimeError("ordinary")

    def stage(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(service, "run_phase_c_reconciliation_stage", stage)
    raised = characterized._run(
        h,
        characterized.Fatal if fatal else h.base.characterized.StopOnLegacyPath,
    )
    if fatal:
        assert raised is error
    assert not [row for row in h.boundary_calls if row[0] == "synthesis"]
    assert ("legacy_path" in [row[0] for row in h.base.h.calls]) is (not fatal)


def test_leaf_imports_single_ordered_callsite_direct_binding_and_no_duplicates():
    root = Path(__file__).parents[2]
    leaf = ast.parse(
        (root / "app/orchestrator/phase_c_reconciliation_stage.py").read_text())
    imports = {
        alias.name
        for node in leaf.body if isinstance(node, ast.Import)
        for alias in node.names
    }
    imports |= {
        node.module for node in leaf.body if isinstance(node, ast.ImportFrom)
    }
    assert imports == {"dataclasses", "typing"}

    tree = ast.parse((root / "app/orchestrator/service.py").read_text())
    named_calls = {
        name: [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == name
        ]
        for name in (
            "run_phase_c_bounded_research_stage",
            "run_phase_c_reconciliation_stage",
        )
    }
    assert len(named_calls["run_phase_c_bounded_research_stage"]) == 1
    assert len(named_calls["run_phase_c_reconciliation_stage"]) == 1
    stage_call = named_calls["run_phase_c_reconciliation_stage"][0]
    assert [arg.id for arg in stage_call.args] == [
        "timings", "counts", "requirement_set", "working_evidence_items",
        "initial_assessment", "research_execution", "retrieved_at",
    ]
    assert [keyword.arg for keyword in stage_call.keywords] == [
        "observability_call", "observability_get", "reconcile_evidence_callable",
    ]
    assignment = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "reconciliation"
                for target in node.targets)
        and isinstance(node.value, ast.Attribute)
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "phase_c_reconciliation_stage"
    )
    assert assignment.value.attr == "reconciliation"
    synthesis_calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_observability_call"
        and len(node.args) > 2
        and isinstance(node.args[2], ast.Name)
        and node.args[2].id == "synthesize_grounded_evidence"
    ]
    assert len(synthesis_calls) == 1
    assert (
        named_calls["run_phase_c_bounded_research_stage"][0].lineno
        < stage_call.lineno
        < synthesis_calls[0].lineno
    )
