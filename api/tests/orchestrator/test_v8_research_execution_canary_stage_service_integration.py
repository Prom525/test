import ast
from pathlib import Path


def _service_tree():
    root = Path(__file__).parents[2]
    return root, ast.parse((root / "app/orchestrator/service.py").read_text())


def test_leaf_import_surface_and_single_service_callsite():
    root, service = _service_tree()
    leaf = ast.parse((root / "app/orchestrator/v8_research_execution_canary_stage.py").read_text())
    imports = {alias.name for node in leaf.body if isinstance(node, ast.Import) for alias in node.names}
    imports |= {node.module for node in leaf.body if isinstance(node, ast.ImportFrom)}
    assert imports == {"dataclasses", "typing"}
    calls = [node for node in ast.walk(service) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Name)
             and node.func.id == "run_v8_research_execution_canary_stage"]
    assert len(calls) == 1
    assert [keyword.arg for keyword in calls[0].keywords] == [
        "_run_intent_task_research_execution_canary_shadow"]
    assert isinstance(calls[0].keywords[0].value, ast.Name)
    assert calls[0].keywords[0].value.id == "_run_intent_task_research_execution_canary_shadow"


def test_stage_order_three_direct_bindings_and_unchanged_assessment_inputs():
    _, tree = _service_tree()
    core = min((node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name == "run_orchestrator"), key=lambda node: node.lineno)
    calls = [(node.lineno, node.func.id) for node in ast.walk(core) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Name)]
    e3 = next(line for line, name in calls if name == "run_p4_6e3_synthesis_coverage_stage")
    v8 = next(line for line, name in calls if name == "run_v8_research_execution_canary_stage")
    assessment = next(node.lineno for node in ast.walk(core)
                      if isinstance(node, ast.Call)
                      and isinstance(node.func, ast.Name)
                      and node.func.id == "_observability_call"
                      and len(node.args) > 2 and isinstance(node.args[2], ast.Name)
                      and node.args[2].id == "assess_evidence")
    assert e3 < v8 < assessment
    assignments = {target.id: node.value for node in ast.walk(core)
                   if isinstance(node, ast.Assign) and len(node.targets) == 1
                   for target in node.targets if isinstance(target, ast.Name)}
    expected = {
        "task_research_execution_canary_shadow",
        "task_research_evidence_reassessment_shadow",
        "task_grounded_synthesis_shadow",
    }
    for name in expected:
        value = assignments[name]
        assert isinstance(value, ast.Attribute)
        assert isinstance(value.value, ast.Name)
        assert value.value.id == "v8_research_execution_canary_stage"
        assert value.attr == name
    assess_call = next(node for node in ast.walk(core) if isinstance(node, ast.Call)
                       and isinstance(node.func, ast.Name) and node.func.id == "_observability_call"
                       and len(node.args) > 2 and isinstance(node.args[2], ast.Name)
                       and node.args[2].id == "assess_evidence")
    assert [arg.id for arg in assess_call.args[3:] if isinstance(arg, ast.Name)] == [
        "requirement_set", "working_evidence_items"]
    assert [(kw.arg, kw.value.id if isinstance(kw.value, ast.Name) else None)
            for kw in assess_call.keywords] == [("target_entity_ids", None), ("now", "retrieved_at")]
