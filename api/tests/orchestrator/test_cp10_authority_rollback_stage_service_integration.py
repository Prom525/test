import ast
from pathlib import Path

from app.orchestrator import service


SERVICE_PATH = Path(service.__file__)
STAGE_PATH = SERVICE_PATH.with_name("cp10_authority_rollback_stage.py")


def function():
    tree = ast.parse(SERVICE_PATH.read_text(encoding="utf-8"))
    return next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name == "run_orchestrator")


def named_calls(name):
    return [node for node in ast.walk(function()) if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name) and node.func.id == name]


def test_leaf_has_only_minimal_imports_and_no_forbidden_introspection():
    source = STAGE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert {node.module for node in tree.body if isinstance(node, ast.ImportFrom)} == {
        "dataclasses", "typing"
    }
    assert "service" not in source and "importlib" not in source and "__globals__" not in source
    assert not any(isinstance(node, ast.If) and isinstance(node.test, ast.Constant)
                   and isinstance(node.test.value, bool) for node in ast.walk(tree))


def test_single_callsite_order_five_inputs_two_dependencies_and_three_bindings():
    stage_3z2a = named_calls("run_p4_6f_cp9_authority_entry_stage")
    stage_3z2b = named_calls("run_cp10_authority_rollback_stage")
    cp11 = named_calls("present_relevant_task_answer")
    assert tuple(map(len, (stage_3z2a, stage_3z2b, cp11))) == (1, 1, 1)
    assert stage_3z2a[0].lineno < stage_3z2b[0].lineno < cp11[0].lineno
    assert [arg.id for arg in stage_3z2b[0].args] == [
        "answer", "legacy_answer_before_public_composition_canary",
        "evidence_pipeline", "task_public_composition_authority_p4_6f",
        "task_coverage_gate_cp10",
    ]
    assert {keyword.arg for keyword in stage_3z2b[0].keywords} == {
        "guard_task_coverage_authority", "guard_public_composition_canary"
    }
    assignments = [node for node in function().body if isinstance(node, ast.Assign)
                   and isinstance(node.value, ast.Attribute)
                   and isinstance(node.value.value, ast.Name)
                   and node.value.value.id == "cp10_authority_rollback_stage_result"]
    assert [(node.targets[0].id, node.value.attr) for node in assignments] == [
        ("answer", "answer"), ("evidence_pipeline", "evidence_pipeline"),
        ("task_public_composition_authority_p4_6f", "task_public_composition_authority_p4_6f"),
    ]


def test_cp11_consumes_exact_post_stage_state_and_wrapper_chain_is_unchanged():
    cp11 = named_calls("present_relevant_task_answer")[0]
    assert [getattr(arg, "id", None) for arg in cp11.args] == [
        "plan", "legacy_answer_before_public_composition_canary",
        "task_coverage_gate_cp10", None,
        "task_public_composition_authority_p4_6f",
    ]
    source = SERVICE_PATH.read_text(encoding="utf-8")
    assert source.count("run_cp10_authority_rollback_stage(") == 1
    assert "response = _p4_15cp4f_previous_run_orchestrator(*args, **kwargs)" in source
    assert "response = _p4_15cp3c_previous_run_orchestrator(*args, **kwargs)" in source
