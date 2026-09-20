import ast
from pathlib import Path

from app.orchestrator import service


SERVICE_PATH = Path(service.__file__)
STAGE_PATH = SERVICE_PATH.with_name("final_observability_envelope_stage.py")


def core():
    tree = ast.parse(SERVICE_PATH.read_text(encoding="utf-8"))
    return next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name == "run_orchestrator")


def calls(function, name):
    return [node for node in ast.walk(function) if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name) and node.func.id == name]


def test_leaf_has_minimal_imports_and_forbidden_surfaces_absent():
    source = STAGE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert {node.module for node in tree.body if isinstance(node, ast.ImportFrom)} == {
        "dataclasses", "typing"}
    for forbidden in ("service", "importlib", "__globals__", "inspect", "logging",
                      "copy", "deepcopy", "try:", "except"):
        assert forbidden not in source


def test_unique_callsite_inputs_dependency_and_direct_binding():
    source = SERVICE_PATH.read_text(encoding="utf-8")
    function = core()
    stage = calls(function, "run_final_observability_envelope_stage")
    assert len(stage) == 1
    assert source.count("run_final_observability_envelope_stage(") == 1
    assert source.count("from app.orchestrator.final_observability_envelope_stage import") == 1
    assert [ast.unparse(arg) for arg in stage[0].args] == [
        "response", "timings", "counts", "run_started",
        "ORCHESTRATOR_OBSERVABILITY_CONTRACT_VERSION",
    ]
    assert [(keyword.arg, ast.unparse(keyword.value))
            for keyword in stage[0].keywords] == [
        ("observability_elapsed_ms", "_observability_elapsed_ms")]
    bindings = [node for node in function.body if isinstance(node, ast.Assign)
                and ast.unparse(node.targets[0]) == "response"]
    assert ast.unparse(bindings[-1].value) == (
        "final_observability_envelope_stage_result.response")


def test_order_wrappers_return_and_no_inline_duplication():
    source = SERVICE_PATH.read_text(encoding="utf-8")
    function = core()
    response_stage = calls(function, "run_final_response_build_stage")[0]
    envelope_stage = calls(function, "run_final_observability_envelope_stage")[0]
    final_return = next(node for node in function.body if isinstance(node, ast.Return)
                        and ast.unparse(node.value) == "response")
    assert response_stage.lineno < envelope_stage.lineno < final_return.lineno
    assert not any(isinstance(node, ast.Assign)
                   and ast.unparse(node.targets[0]) in {
                       "timings['total']", "response['observability']"}
                   for node in function.body)
    assert "response = _p4_15cp4f_previous_run_orchestrator(*args, **kwargs)" in source
    assert "response = _p4_15cp3c_previous_run_orchestrator(*args, **kwargs)" in source
