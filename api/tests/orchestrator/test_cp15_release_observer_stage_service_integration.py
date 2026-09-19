import ast
from pathlib import Path

from app.orchestrator import service


SERVICE_PATH = Path(service.__file__)
STAGE_PATH = SERVICE_PATH.with_name("cp15_release_observer_stage.py")


def function():
    tree = ast.parse(SERVICE_PATH.read_text(encoding="utf-8"))
    return next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name == "run_orchestrator")


def calls(name):
    return [node for node in ast.walk(function()) if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name) and node.func.id == name]


def test_leaf_minimal_imports_and_forbidden_code():
    source = STAGE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert {node.module for node in tree.body if isinstance(node, ast.ImportFrom)} == {
        "dataclasses", "typing"}
    for forbidden in ("service", "importlib", "__globals__", "lambda",
                      "logging", "metrics"):
        assert forbidden not in source


def test_one_import_callsite_order_inputs_dependency_binding_and_gate():
    source = SERVICE_PATH.read_text(encoding="utf-8")
    assert source.count("run_cp15_release_observer_stage(") == 1
    assert source.count("from app.orchestrator.cp15_release_observer_stage import") == 1
    core = function()
    all_calls = [node for node in ast.walk(core) if isinstance(node, ast.Call)]
    def named(name):
        return [node for node in all_calls if isinstance(node.func, ast.Name)
                and node.func.id == name]
    cp12, cp15, after = (named(name) for name in (
        "run_cp12_concise_composition_stage", "run_cp15_release_observer_stage",
        "run_post_cp15_observability_stage"))
    assert tuple(map(len, (cp12, cp15, after))) == (1, 1, 1)
    assert cp12[0].lineno < cp15[0].lineno < after[0].lineno
    assert [arg.id for arg in cp15[0].args] == [
        "task_execution_shadow", "evidence_pipeline"]
    assert [(kw.arg, kw.value.id) for kw in cp15[0].keywords] == [
        ("build_release_gate_cp15", "build_release_gate_cp15")]
    gate = next(node for node in core.body if isinstance(node, ast.If)
                and cp15[0] in ast.walk(node))
    assert ast.unparse(gate.test) == "isinstance(evidence_pipeline, dict)"
    call_statement = next(node for node in gate.body if cp15[0] in ast.walk(node))
    binding = gate.body[gate.body.index(call_statement) + 1]
    assert ast.unparse(binding.targets[0]) == "evidence_pipeline"
    assert ast.unparse(binding.value) == "cp15_release_observer_stage_result.evidence_pipeline"


def test_observability_wrappers_and_no_inline_duplication():
    source = SERVICE_PATH.read_text(encoding="utf-8")
    stage_source = STAGE_PATH.read_text(encoding="utf-8")
    assert "run_post_cp15_observability_stage(" in source
    assert "_record_task_execution_plan_shadow_observability(" not in stage_source
    assert "response = _p4_15cp4f_previous_run_orchestrator(*args, **kwargs)" in source
    assert "response = _p4_15cp3c_previous_run_orchestrator(*args, **kwargs)" in source
    service_body = source[source.index("def run_orchestrator("):]
    assert service_body.count('evidence_pipeline["release_gate_cp15"]') == 0
    assert stage_source.count('evidence_pipeline["release_gate_cp15"]') == 2
