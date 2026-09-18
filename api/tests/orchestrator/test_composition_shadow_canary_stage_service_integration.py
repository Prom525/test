import ast
from pathlib import Path

from app.orchestrator import service


SERVICE_PATH = Path(service.__file__)
STAGE_PATH = SERVICE_PATH.with_name("composition_shadow_canary_stage.py")


def _service_function():
    tree = ast.parse(SERVICE_PATH.read_text(encoding="utf-8"))
    return next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "run_orchestrator"
    )


def test_stage_has_minimal_imports_and_no_service_dependency():
    tree = ast.parse(STAGE_PATH.read_text(encoding="utf-8"))
    imports = {
        node.module for node in tree.body if isinstance(node, ast.ImportFrom)
    }
    assert imports == {"dataclasses", "typing"}
    assert not any(module and module.startswith("app.orchestrator.service") for module in imports)


def test_exact_single_callsite_runtime_dependencies_order_and_direct_bindings():
    function = _service_function()
    calls = [node for node in ast.walk(function) if isinstance(node, ast.Call)]
    named = lambda name: [
        node for node in calls if isinstance(node.func, ast.Name) and node.func.id == name
    ]
    stage, presentation, authority_entry = (
        named("run_composition_shadow_canary_stage"),
        named("run_answer_presentation_stage"),
        named("run_p4_6f_cp9_authority_entry_stage"),
    )
    assert len(stage) == len(presentation) == len(authority_entry) == 1
    assert presentation[0].lineno < stage[0].lineno < authority_entry[0].lineno
    assert [arg.id for arg in stage[0].args] == ["plan", "answer", "evidence_pipeline"]
    assert {kw.arg: kw.value.id for kw in stage[0].keywords} == {
        "build_multi_intent_composition_shadow": "_build_multi_intent_composition_shadow",
        "maybe_apply_public_composition_canary": "_maybe_apply_public_composition_canary",
        "public_composition_canary_enabled": "_public_composition_canary_enabled",
    }
    assignments = [
        node for node in function.body
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Attribute)
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "composition_shadow_canary_stage_result"
    ]
    assert [(node.targets[0].id, node.value.attr) for node in assignments] == [
        ("answer", "answer"),
        ("legacy_answer_before_public_composition_canary", "legacy_answer_before_public_composition_canary"),
        ("evidence_pipeline", "evidence_pipeline"),
    ]


def test_p46f_handoff_and_wrapper_chain_remain_in_service():
    source = SERVICE_PATH.read_text(encoding="utf-8")
    assert source.count("run_composition_shadow_canary_stage(") == 1
    assert source.count("run_p4_6f_cp9_authority_entry_stage(") == 1
    assert "response = _p4_15cp4f_previous_run_orchestrator(*args, **kwargs)" in source
