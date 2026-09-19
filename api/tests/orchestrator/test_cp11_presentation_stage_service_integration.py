import ast
from pathlib import Path

from app.orchestrator import service


SERVICE_PATH = Path(service.__file__)
STAGE_PATH = SERVICE_PATH.with_name("cp11_presentation_stage.py")


def function():
    tree = ast.parse(SERVICE_PATH.read_text(encoding="utf-8"))
    return next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name == "run_orchestrator")


def calls(name):
    return [node for node in ast.walk(function()) if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name) and node.func.id == name]


def test_leaf_imports_and_forbidden_code():
    source = STAGE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert {node.module for node in tree.body if isinstance(node, ast.ImportFrom)} == {
        "dataclasses", "typing"
    }
    for forbidden in ("service", "importlib", "__globals__", "lambda"):
        assert forbidden not in source
    assert not any(isinstance(node, ast.If) and isinstance(node.test, ast.Constant)
                   and isinstance(node.test.value, bool) for node in ast.walk(tree))


def test_single_callsite_order_inputs_dependency_and_bindings():
    cp10 = calls("run_cp10_authority_rollback_stage")
    cp11 = calls("run_cp11_presentation_stage")
    cp12 = calls("compose_concise_public_answer")
    assert tuple(map(len, (cp10, cp11, cp12))) == (1, 1, 1)
    assert cp10[0].lineno < cp11[0].lineno < cp12[0].lineno
    assert [arg.id for arg in cp11[0].args] == [
        "plan", "legacy_answer_before_public_composition_canary",
        "task_coverage_gate_cp10", "evidence_pipeline",
        "task_public_composition_authority_p4_6f",
    ]
    assert [(kw.arg, kw.value.id) for kw in cp11[0].keywords] == [
        ("present_relevant_task_answer", "present_relevant_task_answer")
    ]
    gate = next(node for node in function().body if isinstance(node, ast.If)
                and any(isinstance(child, ast.Call)
                        and isinstance(child.func, ast.Name)
                        and child.func.id == "run_cp11_presentation_stage"
                        for child in ast.walk(node)))
    assert ast.unparse(gate.test) == "isinstance(evidence_pipeline, dict)"
    bindings = [node for node in gate.body if isinstance(node, ast.Assign)
                and isinstance(node.value, ast.Attribute)
                and isinstance(node.value.value, ast.Name)
                and node.value.value.id == "cp11_presentation_stage_result"]
    assert [(node.targets[0].id, node.value.attr) for node in bindings] == [
        ("answer", "answer"), ("evidence_pipeline", "evidence_pipeline"),
        ("task_presenter_cp11", "task_presenter_cp11"),
        ("task_public_composition_authority_p4_6f",
         "task_public_composition_authority_p4_6f"),
    ]


def test_cp12_remains_in_service_and_consumes_post_stage_state():
    cp12 = calls("compose_concise_public_answer")[0]
    assert [arg.id for arg in cp12.args] == [
        "answer", "legacy_answer_before_public_composition_canary"
    ]
    assert {kw.arg: getattr(kw.value, "id", None) for kw in cp12.keywords} == {
        "response_profile": None,
        "task_coverage_gate_cp10": "task_coverage_gate_cp10",
        "task_presenter_cp11": "task_presenter_cp11",
    }
    source = SERVICE_PATH.read_text(encoding="utf-8")
    assert source.count("run_cp11_presentation_stage(") == 1
    assert "response = _p4_15cp4f_previous_run_orchestrator(*args, **kwargs)" in source
    assert "response = _p4_15cp3c_previous_run_orchestrator(*args, **kwargs)" in source
