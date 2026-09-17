import ast
import importlib.util
from pathlib import Path

from app.orchestrator import service
from app.orchestrator.post_phase_c_status_stage import (
    run_post_phase_c_status_stage as real_stage,
)


def _characterization():
    path = Path(__file__).with_name(
        "test_post_phase_c_clarification_status_boundary_characterization.py"
    )
    spec = importlib.util.spec_from_file_location("post_phase_c_3v1", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runtime_stage_once_dependency_identity_bindings_and_research_handoff(
    monkeypatch,
):
    characterized = _characterization()
    h = characterized._install(monkeypatch, execution_steps=(object(),), accepted=False)
    runtime_helper = service.has_service_accepted_execution
    calls = []

    def stage(*args, **kwargs):
        calls.append((args, kwargs))
        return real_stage(*args, **kwargs)

    monkeypatch.setattr(service, "run_post_phase_c_status_stage", stage)
    response = characterized._run(h)
    assert response["status"] == "error"
    assert response["clarification"] == {"required": False, "question": None}
    assert response["research"]["status"] == "not_required"
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args == (h.plan, h.results, h.typed)
    assert all(actual is expected for actual, expected in zip(
        args, (h.plan, h.results, h.typed)
    ))
    assert kwargs == {
        "has_service_accepted_execution_callable": runtime_helper,
    }


def test_runtime_monkeypatch_of_accepted_helper_is_forwarded(monkeypatch):
    characterized = _characterization()
    marker = object()
    h = characterized._install(monkeypatch, execution_steps=(object(),), accepted=marker)
    helper = service.has_service_accepted_execution
    captured = []

    def stage(*args, **kwargs):
        captured.append(kwargs["has_service_accepted_execution_callable"])
        return real_stage(*args, **kwargs)

    monkeypatch.setattr(service, "run_post_phase_c_status_stage", stage)
    assert characterized._run(h)["status"] == "ok"
    assert captured == [helper]
    helper_calls = [call for call in h.calls if call[0] == "helper"]
    assert len(helper_calls) == 1
    assert helper_calls[0][1] == (h.typed, h.results)


def test_leaf_imports_single_callsite_direct_bindings_and_semantic_boundaries():
    root = Path(__file__).parents[2]
    leaf_path = root / "app/orchestrator/post_phase_c_status_stage.py"
    leaf = ast.parse(leaf_path.read_text(encoding="utf-8"))
    imports = {alias.name for node in leaf.body if isinstance(node, ast.Import)
               for alias in node.names}
    imports |= {node.module for node in leaf.body if isinstance(node, ast.ImportFrom)}
    assert imports == {"dataclasses", "typing"}

    service_path = root / "app/orchestrator/service.py"
    tree = ast.parse(service_path.read_text(encoding="utf-8"))
    stage_calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                   and isinstance(node.func, ast.Name)
                   and node.func.id == "run_post_phase_c_status_stage"]
    assert len(stage_calls) == 1
    call = stage_calls[0]
    assert [arg.id for arg in call.args] == [
        "plan", "results", "typed_execution_results"
    ]
    assert [keyword.arg for keyword in call.keywords] == [
        "has_service_accepted_execution_callable"
    ]
    dependency = call.keywords[0].value
    while isinstance(dependency, ast.Expr):
        dependency = dependency.value
    assert isinstance(dependency, ast.Name)
    assert dependency.id == "has_service_accepted_execution"

    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name == "run_orchestrator")
    direct = {}
    for node in function.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name):
                direct[target.id] = node
    for name in ("status", "clarification"):
        assignment = direct[name]
        assert isinstance(assignment.value, ast.Attribute)
        assert isinstance(assignment.value.value, ast.Name)
        assert assignment.value.value.id == "post_phase_c_status_stage"
        assert assignment.value.attr == name
    research = direct["research"]
    assert call.lineno < direct["status"].lineno < direct["clarification"].lineno
    assert direct["clarification"].lineno < research.lineno

    imports_from_leaf = [node for node in tree.body if isinstance(node, ast.ImportFrom)
                         and node.module == "app.orchestrator.post_phase_c_status_stage"]
    assert len(imports_from_leaf) == 1
    assert [alias.name for alias in imports_from_leaf[0].names] == [
        "run_post_phase_c_status_stage"
    ]
