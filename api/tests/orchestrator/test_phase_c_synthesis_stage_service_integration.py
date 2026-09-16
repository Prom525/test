import ast
import importlib.util
from pathlib import Path

import pytest

from app.orchestrator import service
from app.orchestrator.phase_c_synthesis_stage import PhaseCSynthesisStageResult


def _characterization():
    path = Path(__file__).with_name(
        "test_phase_c_synthesis_boundary_characterization.py"
    )
    spec = importlib.util.spec_from_file_location("phase_c_3t1_for_3t2", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runtime_dependencies_direct_binding_pipeline_handoff_and_order(monkeypatch):
    characterized = _characterization()
    reconciliation = object()
    h = characterized._install(monkeypatch, reconciliation=reconciliation)
    synthesis = object()
    calls = []

    def stage(*args, **kwargs):
        calls.append((args, kwargs))
        return PhaseCSynthesisStageResult(synthesis)

    monkeypatch.setattr(service, "run_phase_c_synthesis_stage", stage)
    characterized._run(h)

    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args == (h.base.base.h.timings, reconciliation)
    assert args[0] is h.base.base.h.timings
    assert args[1] is reconciliation
    assert kwargs == {
        "observability_call": service._observability_call,
        "synthesize_grounded_evidence_callable": (
            service.synthesize_grounded_evidence
        ),
    }
    assert not [row for row in h.calls if row[0] == "synthesis_callable"]
    pipeline = [row for row in h.calls if row[0] == "pipeline"]
    assert len(pipeline) == 1
    assert pipeline[0][1][0]["synthesis"] is synthesis


@pytest.mark.parametrize("fatal", [False, True])
def test_stage_exception_preserves_outer_fail_open_and_baseexception(monkeypatch, fatal):
    characterized = _characterization()
    h = characterized._install(monkeypatch)
    error = characterized.Fatal("fatal") if fatal else RuntimeError("ordinary")

    def stage(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(service, "run_phase_c_synthesis_stage", stage)
    raised = characterized._run(
        h,
        characterized.Fatal if fatal else h.base.base.characterized.StopOnLegacyPath,
    )
    if fatal:
        assert raised is error
    assert not [row for row in h.calls if row[0] == "pipeline"]
    assert ("legacy_path" in [row[0] for row in h.base.base.h.calls]) is (not fatal)


def test_leaf_imports_single_ordered_callsite_direct_binding_and_no_duplicates():
    root = Path(__file__).parents[2]
    leaf = ast.parse(
        (root / "app/orchestrator/phase_c_synthesis_stage.py").read_text()
    )
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
            "run_phase_c_reconciliation_stage",
            "run_phase_c_synthesis_stage",
            "_evidence_pipeline_to_dict",
        )
    }
    assert len(named_calls["run_phase_c_reconciliation_stage"]) == 1
    assert len(named_calls["run_phase_c_synthesis_stage"]) == 1
    stage_call = named_calls["run_phase_c_synthesis_stage"][0]
    assert [arg.id for arg in stage_call.args] == ["timings", "reconciliation"]
    assert [keyword.arg for keyword in stage_call.keywords] == [
        "observability_call", "synthesize_grounded_evidence_callable"
    ]
    assignment = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "synthesis"
                for target in node.targets)
        and isinstance(node.value, ast.Attribute)
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "phase_c_synthesis_stage"
    )
    assert assignment.value.attr == "synthesis"
    assert not [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_observability_call"
        and len(node.args) > 2
        and isinstance(node.args[2], ast.Name)
        and node.args[2].id == "synthesize_grounded_evidence"
    ]
    assert (
        named_calls["run_phase_c_reconciliation_stage"][0].lineno
        < stage_call.lineno
        < named_calls["_evidence_pipeline_to_dict"][0].lineno
    )
