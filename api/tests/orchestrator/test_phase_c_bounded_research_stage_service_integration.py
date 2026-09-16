import ast
import importlib.util
from pathlib import Path

import pytest

from app.orchestrator import service
from app.orchestrator.models import OrchestratorAskRequest
from app.orchestrator.phase_c_bounded_research_stage import (
    PhaseCBoundedResearchStageResult,
)


def _characterization():
    path = Path(__file__).with_name(
        "test_phase_c_bounded_research_metrics_boundary_characterization.py")
    spec = importlib.util.spec_from_file_location("phase_c_3r1", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runtime_dependencies_single_call_and_unchanged_reconciliation(monkeypatch):
    characterized = _characterization()
    h = characterized._install(monkeypatch, metadata=None)
    execution = object()
    calls = []

    def stage(*args, **kwargs):
        calls.append((args, kwargs))
        return PhaseCBoundedResearchStageResult(execution)

    monkeypatch.setattr(service, "run_phase_c_bounded_research_stage", stage)
    characterized._run(h)
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args == (h.h.timings, h.h.counts, h.decision, h.h.plan,
                    h.h.results, h.h.sender)
    assert kwargs == {
        "_observability_call": service._observability_call,
        "_observability_get": service._observability_get,
        "_observability_nonnegative_int": service._observability_nonnegative_int,
        "execute_bounded_research": service.execute_bounded_research,
    }
    reconciliation = next(row for row in h.calls if row[0] == "reconcile")
    assert reconciliation[1][0] is h.h.requirement_set
    assert reconciliation[1][1] is h.h.working_evidence_items
    assert reconciliation[1][3] is execution
    assert reconciliation[2] == {"retrieved_at": h.h.retrieved_at,
                                  "target_entity_ids": None,
                                  "now": h.h.retrieved_at}
    assert not [row for row in h.calls if row[0] == "execute"]


@pytest.mark.parametrize("fatal", [False, True])
def test_stage_exception_keeps_outer_fail_open_and_baseexception_boundary(monkeypatch, fatal):
    characterized = _characterization()
    h = characterized._install(monkeypatch)
    error = characterized.Fatal("fatal") if fatal else RuntimeError("ordinary")

    def stage(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(service, "run_phase_c_bounded_research_stage", stage)
    raised = characterized._run(
        h, characterized.Fatal if fatal else h.characterized.StopOnLegacyPath)
    if fatal:
        assert raised is error
    assert not [row for row in h.calls if row[0] == "reconcile"]
    assert ("legacy_path" in [row[0] for row in h.h.calls]) is (not fatal)


def test_leaf_import_surface_single_ordered_callsite_and_direct_binding():
    root = Path(__file__).parents[2]
    leaf = ast.parse((root / "app/orchestrator/phase_c_bounded_research_stage.py").read_text())
    imports = {alias.name for node in leaf.body if isinstance(node, ast.Import)
               for alias in node.names}
    imports |= {node.module for node in leaf.body if isinstance(node, ast.ImportFrom)}
    assert imports == {"dataclasses", "typing"}

    tree = ast.parse((root / "app/orchestrator/service.py").read_text())
    stage_calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                   and isinstance(node.func, ast.Name)
                   and node.func.id == "run_phase_c_bounded_research_stage"]
    assert len(stage_calls) == 1
    call = stage_calls[0]
    assert [arg.id for arg in call.args] == [
        "timings", "counts", "research_decision", "plan", "results", "sender"]
    assert [keyword.arg for keyword in call.keywords] == [
        "_observability_call", "_observability_get",
        "_observability_nonnegative_int", "execute_bounded_research"]
    assignments = [node for node in ast.walk(tree) if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name)
                           and target.id == "research_execution"
                           for target in node.targets)]
    direct = next(node.value for node in assignments if isinstance(node.value, ast.Attribute))
    assert direct.value.id == "phase_c_bounded_research_stage"
    assert direct.attr == "research_execution"
    reconciliations = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                       and isinstance(node.func, ast.Name)
                       and node.func.id == "_observability_call"
                       and len(node.args) > 2
                       and isinstance(node.args[2], ast.Name)
                       and node.args[2].id == "reconcile_evidence"]
    assert len(reconciliations) == 1
    assert call.lineno < reconciliations[0].lineno
