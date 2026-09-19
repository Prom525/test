import ast
from pathlib import Path

from app.orchestrator import service


SERVICE_PATH = Path(service.__file__)
STAGE_PATH = SERVICE_PATH.with_name("post_cp15_observability_stage.py")


def function():
    tree = ast.parse(SERVICE_PATH.read_text(encoding="utf-8"))
    return next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name == "run_orchestrator")


def named(function_node, name):
    return [node for node in ast.walk(function_node) if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name) and node.func.id == name]


def test_leaf_minimal_imports_and_forbidden_code():
    source = STAGE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert {node.module for node in tree.body if isinstance(node, ast.ImportFrom)} == {
        "typing"}
    for forbidden in ("service", "importlib", "__globals__", "lambda",
                      "logging", "metrics"):
        assert forbidden not in source


def test_one_import_callsite_without_assignment_order_inputs_and_dependencies():
    source = SERVICE_PATH.read_text(encoding="utf-8")
    assert source.count("run_post_cp15_observability_stage(") == 1
    assert source.count("from app.orchestrator.post_cp15_observability_stage import") == 1
    core = function()
    cp15 = named(core, "run_cp15_release_observer_stage")
    stage = named(core, "run_post_cp15_observability_stage")
    assert tuple(map(len, (cp15, stage))) == (1, 1)
    clocks = [node for node in core.body if isinstance(node, ast.Assign)
              and any(ast.unparse(target) == "response_build_started"
                      for target in node.targets)]
    assert len(clocks) == 1 and cp15[0].lineno < stage[0].lineno < clocks[0].lineno
    statement = next(node for node in core.body if stage[0] in ast.walk(node))
    assert isinstance(statement, ast.Expr) and statement.value is stage[0]
    assert [ast.unparse(arg) for arg in stage[0].args] == [
        "counts", "plan", "evidence_pipeline"]
    assert [(kw.arg, ast.unparse(kw.value)) for kw in stage[0].keywords] == [
        ("record_task_execution_plan_shadow_observability",
         "_record_task_execution_plan_shadow_observability"),
        ("record_public_composition_canary_release_observability",
         "_record_public_composition_canary_release_observability"),
    ]
    assert ast.unparse(clocks[0].value) == "_observability_now()"


def test_wrappers_and_no_inline_duplication():
    source = SERVICE_PATH.read_text(encoding="utf-8")
    stage_source = STAGE_PATH.read_text(encoding="utf-8")
    core_source = source[source.index("def run_orchestrator("):]
    assert core_source.count("_record_task_execution_plan_shadow_observability(") == 0
    assert core_source.count(
        "_record_public_composition_canary_release_observability(") == 0
    assert stage_source.count("record_task_execution_plan_shadow_observability(") == 1
    assert stage_source.count(
        "record_public_composition_canary_release_observability(") == 1
    assert "response = _p4_15cp4f_previous_run_orchestrator(*args, **kwargs)" in source
    assert "response = _p4_15cp3c_previous_run_orchestrator(*args, **kwargs)" in source
