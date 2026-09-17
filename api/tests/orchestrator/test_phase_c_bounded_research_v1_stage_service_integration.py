import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.orchestrator import service
from app.orchestrator.phase_c_bounded_research_v1_stage import (
    run_phase_c_bounded_research_v1_stage as real_stage,
)


def _characterization():
    path = Path(__file__).with_name(
        "test_phase_c_bounded_research_v1_boundary_characterization.py"
    )
    spec = importlib.util.spec_from_file_location("phase_c_3w1_for_3w2", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runtime_stage_once_all_dependencies_monkeypatchable_and_answer_handoff(
    monkeypatch,
):
    characterized = _characterization()
    research = {"agent": {"total_ai_calls_used": 3}, "answer": None}
    h = characterized._install(monkeypatch, research_return=research)
    runtime_dependencies = (
        service._research_agent_enabled,
        service._observability_call,
        service._observability_nonnegative_int,
        service.run_bounded_research_agent,
        service.run_bounded_research,
    )
    calls = []

    def stage(*args, **kwargs):
        calls.append((args, kwargs))
        return real_stage(*args, **kwargs)

    monkeypatch.setattr(service, "run_phase_c_bounded_research_v1_stage", stage)
    with pytest.raises(characterized.StopAtAnswer):
        service._p4_15cp3c_previous_run_orchestrator(
            characterized.OrchestratorAskRequest(q="synthetic", vraag=""),
            sender=h.sender,
        )
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args[:5] == (h.h.plan, h.h.results, "ok", h.clarification, h.sender)
    assert all(actual is expected for actual, expected in zip(
        args[:5], (h.h.plan, h.h.results, "ok", h.clarification, h.sender)
    ))
    assert tuple(kwargs.values()) == runtime_dependencies
    assert list(kwargs) == [
        "_research_agent_enabled",
        "_observability_call",
        "_observability_nonnegative_int",
        "run_bounded_research_agent",
        "run_bounded_research",
    ]
    answer_call = characterized._call(h, "answer")[0]
    assert answer_call[1] == (h.h.results,)
    assert answer_call[1][0] is h.h.results
    assert answer_call[2] == {"requested_information": h.requested_information}


def test_ast_single_callsite_exact_order_direct_bindings_and_unchanged_wrappers():
    path = Path(__file__).parents[2] / "app/orchestrator/service.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name == "run_orchestrator")
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Name)
             and node.func.id == "run_phase_c_bounded_research_v1_stage"]
    assert len(calls) == 1
    call = calls[0]
    assert [arg.id for arg in call.args] == [
        "plan", "results", "status", "clarification", "sender", "timings", "counts"
    ]
    assert [keyword.arg for keyword in call.keywords] == [
        "_research_agent_enabled", "_observability_call",
        "_observability_nonnegative_int", "run_bounded_research_agent",
        "run_bounded_research",
    ]
    assert [keyword.value.id for keyword in call.keywords] == [
        "_research_agent_enabled", "_observability_call",
        "_observability_nonnegative_int", "run_bounded_research_agent",
        "run_bounded_research",
    ]

    top_assignments = {}
    for node in function.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name):
                top_assignments[target.id] = node
    status = top_assignments["status"]
    clarification = top_assignments["clarification"]
    research = top_assignments["research"]
    agent = top_assignments["plan_research_agent"]
    answer_stage_call = min(
        [
            node for node in ast.walk(function)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "run_answer_presentation_stage"
            and node.lineno > call.lineno
        ],
        key=lambda node: node.lineno,
    )
    assert status.lineno < clarification.lineno < call.lineno
    assert call.lineno < research.lineno < agent.lineno < answer_stage_call.lineno
    for name, attribute in (("research", "research"),
                            ("plan_research_agent", "plan_research_agent")):
        value = top_assignments[name].value
        assert isinstance(value, ast.Attribute)
        assert isinstance(value.value, ast.Name)
        assert value.value.id == "phase_c_bounded_research_v1_stage"
        assert value.attr == attribute

    wrapper_names = {
            "_p4_15cp3c_previous_run_orchestrator",
            "_p4_15cp4b_previous_run_orchestrator",
            "_p4_15cp4f_previous_run_orchestrator",
    }
    wrapper_bindings = {
        node.targets[0].id: node.value.id
        for node in tree.body
        if isinstance(node, ast.Assign) and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id in wrapper_names
        and isinstance(node.value, ast.Name)
    }
    assert set(wrapper_bindings) == {
        "_p4_15cp3c_previous_run_orchestrator",
        "_p4_15cp4b_previous_run_orchestrator",
        "_p4_15cp4f_previous_run_orchestrator",
    }
    assert set(wrapper_bindings.values()) == {"run_orchestrator"}


def test_exactly_one_leaf_import_and_protected_3w1_hash():
    root = Path(__file__).parents[2]
    tree = ast.parse((root / "app/orchestrator/service.py").read_text(encoding="utf-8"))
    imports = [node for node in tree.body if isinstance(node, ast.ImportFrom)
               and node.module == "app.orchestrator.phase_c_bounded_research_v1_stage"]
    assert len(imports) == 1
    assert [alias.name for alias in imports[0].names] == [
        "run_phase_c_bounded_research_v1_stage"
    ]
    import hashlib
    protected = Path(__file__).with_name(
        "test_phase_c_bounded_research_v1_boundary_characterization.py"
    )
    assert hashlib.sha256(protected.read_bytes().replace(b"\r\n", b"\n")).hexdigest() == (
        "9d097cc0890144c43ecbe90082d97d3f72a2efe907809241ee5068c84fed8907"
    )
