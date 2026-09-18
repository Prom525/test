import ast
import importlib.util
from pathlib import Path

import pytest

from app.orchestrator import service


SERVICE_PATH = Path(service.__file__)
STAGE_PATH = SERVICE_PATH.with_name("p4_6f_cp9_authority_entry_stage.py")


class ResponseProfileProbe:
    def __init__(self, wrapped, value=None, error=None):
        self.wrapped = wrapped
        self.value = value
        self.error = error
        self.reads = 0

    @property
    def response_profile(self):
        self.reads += 1
        if self.error is not None:
            raise self.error
        return self.value

    def __getattr__(self, name):
        return getattr(self.wrapped, name)


class Fatal(BaseException):
    pass


def _boundary_characterization():
    path = Path(__file__).with_name(
        "test_p4_6f_authority_entry_boundary_characterization.py"
    )
    spec = importlib.util.spec_from_file_location("authority_3z1a_for_3z2a", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _function():
    tree = ast.parse(SERVICE_PATH.read_text(encoding="utf-8"))
    return next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "run_orchestrator"
    )


def test_leaf_has_minimal_imports_and_no_service_dependency():
    tree = ast.parse(STAGE_PATH.read_text(encoding="utf-8"))
    imports = {node.module for node in tree.body if isinstance(node, ast.ImportFrom)}
    assert imports == {"dataclasses", "typing"}
    assert not any(
        isinstance(node, ast.If)
        and isinstance(node.test, ast.Constant)
        and isinstance(node.test.value, bool)
        for node in ast.walk(tree)
    )


def test_single_callsite_order_inputs_dependencies_and_six_bindings():
    function = _function()
    calls = [node for node in ast.walk(function) if isinstance(node, ast.Call)]
    named = lambda name: [
        node for node in calls
        if isinstance(node.func, ast.Name) and node.func.id == name
    ]
    stage_3y2 = named("run_composition_shadow_canary_stage")
    stage = named("run_p4_6f_cp9_authority_entry_stage")
    cp10 = named("guard_task_coverage_authority")
    assert len(stage_3y2) == len(stage) == len(cp10) == 1
    assert stage_3y2[0].lineno < stage[0].lineno < cp10[0].lineno
    assert [arg.id for arg in stage[0].args] == [
        "plan", "answer", "legacy_answer_before_public_composition_canary",
        "evidence_pipeline", "task_execution_shadow", "cp11_debug_response",
    ]
    stage_statement = next(
        node for node in function.body if stage[0].lineno <= node.lineno
    )
    debug_bindings = [
        node for node in function.body[:function.body.index(stage_statement)]
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "cp11_debug_response"
            for target in node.targets
        )
    ]
    assert len(debug_bindings) == 1
    comparison = debug_bindings[0].value
    assert isinstance(comparison, ast.Compare)
    assert isinstance(comparison.left, ast.Call)
    assert isinstance(comparison.left.func, ast.Name)
    assert comparison.left.func.id == "getattr"
    assert [arg.id if isinstance(arg, ast.Name) else arg.value for arg in comparison.left.args] == [
        "payload", "response_profile", None,
    ]
    assert isinstance(comparison.ops[0], ast.Eq)
    assert comparison.comparators[0].value == "debug"
    source = SERVICE_PATH.read_text(encoding="utf-8")
    assert "cp11_debug_response_holder" not in source
    assert not any(
        isinstance(node, ast.Lambda)
        and any(
            isinstance(child, ast.Attribute) and child.attr == "append"
            for child in ast.walk(node)
        )
        for node in ast.walk(function)
    )
    assert {keyword.arg for keyword in stage[0].keywords} == {
        "build_task_coverage_gate_status", "build_task_research_semantics",
        "build_public_multi_intent_composition_authority_canary_p4_6f",
        "guard_public_composition_authority", "guard_public_composition_canary",
    }
    assignments = [
        node for node in function.body
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Attribute)
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "p4_6f_cp9_authority_entry_stage_result"
    ]
    assert [(node.targets[0].id, node.value.attr) for node in assignments] == [
        ("answer", "answer"), ("evidence_pipeline", "evidence_pipeline"),
        ("task_research_semantics_cp13", "task_research_semantics_cp13"),
        ("task_coverage_gate_cp10", "task_coverage_gate_cp10"),
        ("task_public_composition_authority_p4_6f", "task_public_composition_authority_p4_6f"),
        ("task_authority_gate_cp9", "task_authority_gate_cp9"),
    ]


def test_cp10_receives_stage_state_and_wrappers_remain():
    source = SERVICE_PATH.read_text(encoding="utf-8")
    assert source.count("run_p4_6f_cp9_authority_entry_stage(") == 1
    assert "guard_task_coverage_authority(\n                answer," in source
    assert "task_coverage_gate_cp10," in source
    assert "response = _p4_15cp4f_previous_run_orchestrator(*args, **kwargs)" in source


@pytest.mark.parametrize("profile,coerced", [("debug", True), ("DEBUG", False)])
def test_response_profile_property_is_read_once_and_case_sensitive(
    monkeypatch, profile, coerced
):
    boundary = _boundary_characterization()
    h = boundary._install(
        monkeypatch, pipeline_factory=[], stop_at_coverage=not coerced
    )
    probe = ResponseProfileProbe(h.payload, value=profile)
    h.payload = probe
    local = boundary._locals(boundary._run(h))
    assert probe.reads == 1
    assert local["cp11_debug_response"] is coerced
    assert isinstance(local["evidence_pipeline"], dict) is coerced


@pytest.mark.parametrize(
    "failure_type", [RuntimeError, Fatal]
)
def test_response_profile_exception_propagates_once_before_stage_dependencies(
    monkeypatch, failure_type
):
    boundary = _boundary_characterization()
    failure = failure_type("profile failure")
    h = boundary._install(monkeypatch, pipeline_factory=[])
    probe = ResponseProfileProbe(h.payload, error=failure)
    h.payload = probe
    with pytest.raises(failure_type) as raised:
        service._p4_15cp3c_previous_run_orchestrator(h.payload, sender=object())
    assert raised.value is failure
    assert probe.reads == 1
    assert not any(
        boundary._calls(h, name)
        for name in ("coverage", "cp13", "authority", "cp9")
    )
