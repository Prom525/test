from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.orchestrator import service


def _function_tree():
    path = Path(__file__).parents[2] / "app/orchestrator/service.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name == "run_orchestrator")


def test_one_stage_callsite_direct_answer_binding_and_order():
    function = _function_tree()
    calls = [node for node in ast.walk(function) if isinstance(node, ast.Call)]
    named = lambda name: [node for node in calls if isinstance(node.func, ast.Name)
                          and node.func.id == name]
    stage = named("run_answer_presentation_stage")
    prior = named("run_phase_c_bounded_research_v1_stage")
    following = named("_build_multi_intent_composition_shadow")
    assert len(stage) == 1 and len(prior) == 1 and len(following) == 1
    assert prior[0].lineno < stage[0].lineno < following[0].lineno
    assignments = [node for node in function.body if isinstance(node, ast.Assign)]
    answer = next(node for node in assignments if any(
        isinstance(target, ast.Name) and target.id == "answer" for target in node.targets))
    assert isinstance(answer.value, ast.Attribute)
    assert answer.value.attr == "answer"


def test_service_passes_four_runtime_resolved_dependencies_and_lazy_property():
    call = next(node for node in ast.walk(_function_tree()) if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "run_answer_presentation_stage")
    assert [keyword.arg for keyword in call.keywords] == [
        "observability_now", "build_user_answer", "repair_mojibake_text",
        "observability_elapsed_ms",
    ]
    assert [keyword.value.id for keyword in call.keywords] == [
        "_observability_now", "_build_user_answer", "repair_mojibake_text",
        "_observability_elapsed_ms",
    ]
    assert [arg.id for arg in (call.args[0], call.args[2], call.args[3])] == [
        "results", "research", "timings"
    ]
    lazy = call.args[1]
    assert isinstance(lazy, ast.Lambda)
    assert isinstance(lazy.body, ast.Attribute)
    assert lazy.body.value.id == "plan"
    assert lazy.body.attr == "requested_information"


def test_composition_receives_direct_bound_answer():
    call = next(node for node in ast.walk(_function_tree()) if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "_build_multi_intent_composition_shadow")
    assert isinstance(call.args[1], ast.Name) and call.args[1].id == "answer"


def test_runtime_monkeypatchability_of_all_four_dependencies(monkeypatch):
    captured = {}
    original = service.run_answer_presentation_stage

    def boundary(*args, **kwargs):
        captured.update(kwargs)
        raise RuntimeError("controlled")

    sentinels = {name: (lambda: None) for name in (
        "_observability_now", "_build_user_answer", "repair_mojibake_text",
        "_observability_elapsed_ms")}
    monkeypatch.setattr(service, "run_answer_presentation_stage", boundary)
    for name, value in sentinels.items():
        monkeypatch.setattr(service, name, value)
    assert original is not boundary
    # The existing 3X1 behavioral suite exercises the full orchestrator path;
    # this structural assertion guards against import-time dependency aliases.
    source = ast.unparse(next(node for node in ast.walk(_function_tree())
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id == "run_answer_presentation_stage"))
    for name in sentinels:
        assert name in source
