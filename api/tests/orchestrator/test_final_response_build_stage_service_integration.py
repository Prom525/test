import ast
from pathlib import Path

from app.orchestrator import service


SERVICE_PATH = Path(service.__file__)
STAGE_PATH = SERVICE_PATH.with_name("final_response_build_stage.py")


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
    for forbidden in ("service", "importlib", "__globals__", "inspect", "logging"):
        assert forbidden not in source


def test_unique_callsite_fifteen_inputs_five_dependencies_and_direct_binding():
    source = SERVICE_PATH.read_text(encoding="utf-8")
    function = core()
    stage = calls(function, "run_final_response_build_stage")
    assert len(stage) == 1
    assert source.count("run_final_response_build_stage(") == 1
    assert source.count("from app.orchestrator.final_response_build_stage import") == 1
    assert [ast.unparse(arg) for arg in stage[0].args] == [
        "payload", "cp11_debug_response", "evidence_pipeline",
        "task_coverage_gate_cp10", "results", "plan", "status", "answer",
        "question", "research", "clarification", "task_execution_shadow",
        "task_planner_canary", "trace", "timings"]
    assert [kw.arg for kw in stage[0].keywords] == [
        "observability_now", "compact_evidence_pipeline_for_public_response",
        "compact_results_for_public_response", "model_to_dict",
        "observability_elapsed_ms"]
    response = next(node for node in function.body if isinstance(node, ast.Assign)
                    and ast.unparse(node.targets[0]) == "response")
    assert ast.unparse(response.value) == "final_response_build_stage_result.response"


def test_order_total_envelope_wrappers_and_no_inline_duplication():
    source = SERVICE_PATH.read_text(encoding="utf-8")
    function = core()
    post = calls(function, "run_post_cp15_observability_stage")[0]
    stage = calls(function, "run_final_response_build_stage")[0]
    total = next(node for node in function.body if isinstance(node, ast.Assign)
                 and ast.unparse(node.targets[0]) == "timings['total']")
    assert post.lineno < stage.lineno < total.lineno
    assert ast.unparse(total.value) == "_observability_elapsed_ms(run_started)"
    assert 'response["observability"] = {' in source
    core_source = source[source.index("def run_orchestrator("):]
    assert "response_build_started" not in core_source
    assert "debug_response = cp11_debug_response" not in core_source
    assert "response = _p4_15cp4f_previous_run_orchestrator(*args, **kwargs)" in source
    assert "response = _p4_15cp3c_previous_run_orchestrator(*args, **kwargs)" in source
