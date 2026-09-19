import ast
from pathlib import Path

from app.orchestrator import service


SERVICE_PATH = Path(service.__file__)
STAGE_PATH = SERVICE_PATH.with_name("cp12_concise_composition_stage.py")


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
        "dataclasses", "typing",
    }
    for forbidden in ("service", "importlib", "__globals__", "lambda",
                      "logging", "metrics"):
        assert forbidden not in source


def test_one_import_callsite_order_profile_inputs_dependency_and_bindings():
    source = SERVICE_PATH.read_text(encoding="utf-8")
    assert source.count("run_cp12_concise_composition_stage(") == 1
    assert source.count("from app.orchestrator.cp12_concise_composition_stage import") == 1
    cp11, cp12, cp15 = (calls(name) for name in (
        "run_cp11_presentation_stage", "run_cp12_concise_composition_stage",
        "build_release_gate_cp15"))
    assert tuple(map(len, (cp11, cp12, cp15))) == (1, 1, 1)
    assert cp11[0].lineno < cp12[0].lineno < cp15[0].lineno
    assert [arg.id for arg in cp12[0].args] == [
        "answer", "legacy_answer_before_public_composition_canary",
        "cp12_response_profile", "task_coverage_gate_cp10",
        "task_presenter_cp11", "evidence_pipeline",
        "task_public_composition_authority_p4_6f",
    ]
    assert [(kw.arg, kw.value.id) for kw in cp12[0].keywords] == [
        ("compose_concise_public_answer", "compose_concise_public_answer")]
    gate = next(node for node in function().body if isinstance(node, ast.If)
                and any(isinstance(child, ast.Call)
                        and isinstance(child.func, ast.Name)
                        and child.func.id == "run_cp12_concise_composition_stage"
                        for child in ast.walk(node)))
    assert ast.unparse(gate.test) == "isinstance(evidence_pipeline, dict)"
    profile = next(node for node in gate.body if isinstance(node, ast.Assign)
                   and isinstance(node.targets[0], ast.Name)
                   and node.targets[0].id == "cp12_response_profile")
    assert profile.lineno < cp12[0].lineno
    assert ast.unparse(profile.value) == "getattr(payload, 'response_profile', 'compact')"
    bindings = [node for node in gate.body if isinstance(node, ast.Assign)
                and isinstance(node.value, ast.Attribute)
                and isinstance(node.value.value, ast.Name)
                and node.value.value.id == "cp12_concise_composition_stage_result"]
    assert [(node.targets[0].id, node.value.attr) for node in bindings] == [
        ("answer", "answer"), ("evidence_pipeline", "evidence_pipeline"),
        ("task_concise_composer_cp12", "task_concise_composer_cp12"),
        ("task_public_composition_authority_p4_6f",
         "task_public_composition_authority_p4_6f"),
    ]


def test_service_gate_cp15_handoff_wrappers_and_no_inline_duplication():
    source = SERVICE_PATH.read_text(encoding="utf-8")
    cp15 = calls("build_release_gate_cp15")[0]
    assert [arg.id for arg in cp15.args] == ["task_execution_shadow", "evidence_pipeline"]
    assert "response = _p4_15cp4f_previous_run_orchestrator(*args, **kwargs)" in source
    assert "response = _p4_15cp3c_previous_run_orchestrator(*args, **kwargs)" in source
    service_body = source[source.index("def run_orchestrator("):]
    assert service_body.count("compose_concise_public_answer(") == 0
    assert STAGE_PATH.read_text(encoding="utf-8").count(
        "compose_concise_public_answer(") == 1
