import ast
import importlib.util
from pathlib import Path

import pytest

from app.orchestrator import service
from app.orchestrator.phase_c_assessment_gate_stage import (
    PhaseCAssessmentGateStageResult,
)


def _characterization():
    path = Path(__file__).with_name(
        "test_phase_c_assessment_research_gate_boundary_characterization.py")
    spec = importlib.util.spec_from_file_location("phase_c_3q1", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runtime_dependencies_direct_bindings_and_unchanged_bounded_research(monkeypatch):
    characterized = _characterization()
    h = characterized._install(monkeypatch)
    assessment, gated = object(), object()
    stage_calls = []

    def stage(*args, **kwargs):
        stage_calls.append((args, kwargs))
        return PhaseCAssessmentGateStageResult(assessment, gated)

    monkeypatch.setattr(service, "run_phase_c_assessment_gate_stage", stage)
    characterized._run(h)
    assert len(stage_calls) == 1
    args, kwargs = stage_calls[0]
    assert args == (h.timings, h.requirement_set, h.working_evidence_items,
                    h.retrieved_at, h.task_research_semantics_cp13)
    assert kwargs == {
        "_observability_call": service._observability_call,
        "assess_evidence": service.assess_evidence,
        "decide_research_requirement": service.decide_research_requirement,
        "gate_legacy_generic_research": service.gate_legacy_generic_research,
    }
    consumer = next(row for row in h.calls if row[0] == "consumer")
    assert consumer[1][0] is gated and consumer[1][1] is h.plan
    assert isinstance(consumer[1][2], list) and consumer[1][2] is not h.results
    assert all(a is b for a, b in zip(consumer[1][2], h.results))
    assert consumer[2] == {"sender": h.sender}
    assert not any(row[0] in {"assessment", "decision", "legacy_gate"} for row in h.calls)


@pytest.mark.parametrize("fatal", [False, True])
def test_stage_exception_keeps_outer_exception_boundary(monkeypatch, fatal):
    characterized = _characterization()
    error = characterized.Fatal("fatal") if fatal else RuntimeError("ordinary")
    h = characterized._install(monkeypatch)

    def stage(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(service, "run_phase_c_assessment_gate_stage", stage)
    raised = characterized._run(
        h, characterized.Fatal if fatal else characterized.StopOnLegacyPath)
    if fatal:
        assert raised is error
    names = [row[0] for row in h.calls]
    assert "consumer" not in names
    assert ("legacy_path" in names) is (not fatal)


def test_leaf_import_surface_single_ordered_callsite_and_direct_bindings():
    root = Path(__file__).parents[2]
    leaf = ast.parse(
        (root / "app/orchestrator/phase_c_assessment_gate_stage.py").read_text())
    imports = {alias.name for node in leaf.body if isinstance(node, ast.Import)
               for alias in node.names}
    imports |= {node.module for node in leaf.body if isinstance(node, ast.ImportFrom)}
    assert imports == {"dataclasses", "typing"}

    tree = ast.parse((root / "app/orchestrator/service.py").read_text())
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Name)
             and node.func.id == "run_phase_c_assessment_gate_stage"]
    assert len(calls) == 1
    call = calls[0]
    assert [arg.id for arg in call.args] == [
        "timings", "requirement_set", "working_evidence_items", "retrieved_at",
        "task_research_semantics_cp13"]
    assert [keyword.arg for keyword in call.keywords] == [
        "_observability_call", "assess_evidence", "decide_research_requirement",
        "gate_legacy_generic_research"]
    assignments = {target.id: node.value for node in ast.walk(tree)
                   if isinstance(node, ast.Assign) and len(node.targets) == 1
                   for target in node.targets if isinstance(target, ast.Name)}
    for name in ("initial_assessment", "research_decision"):
        value = assignments[name]
        assert isinstance(value, ast.Attribute)
        assert value.value.id == "phase_c_assessment_gate_stage"
        assert value.attr == name
    bounded = next(node for node in ast.walk(tree) if isinstance(node, ast.Call)
                   and isinstance(node.func, ast.Name)
                   and node.func.id == "run_phase_c_bounded_research_stage")
    assert call.lineno < bounded.lineno
    assert isinstance(bounded.args[4], ast.Name)
    assert bounded.args[4].id == "results"
