from __future__ import annotations

from dataclasses import fields
from pathlib import Path
import ast

import pytest

from app.orchestrator.initial_execution_stage import (
    InitialExecutionStageResult,
    run_initial_execution_stage,
)


def _run(*, fail_at=None):
    calls = []
    obj = {name: object() for name in (
        "input_plan", "plan", "task_plans", "comparison", "canary",
        "typed_1", "typed_2", "results", "trace", "cp8", "cp9", "sender",
        "timings",
    )}

    def dependency(name, value=None):
        def call(*args, **kwargs):
            calls.append((name, args, kwargs))
            if fail_at == name:
                raise LookupError(name)
            return value
        return call

    def execute(*args, **kwargs):
        calls.append(("execute", args, kwargs))
        if fail_at == "execute":
            raise LookupError("execute")
        kwargs["shadow_observer"](obj["typed_1"])
        kwargs["shadow_observer"](obj["typed_2"])
        return obj["results"], obj["trace"]

    def observe(*args, **kwargs):
        calls.append(("observe", args, kwargs))
        if fail_at == "observe":
            raise LookupError("observe")
        return args[2](*args[3:], **kwargs)

    obj["execute_callable"] = execute

    result = run_initial_execution_stage(
        obj["input_plan"], obj["timings"], sender=obj["sender"],
        attach_requirements=dependency("attach", obj["plan"]),
        build_task_execution_plans_shadow=dependency("build", obj["task_plans"]),
        compare_task_execution_plans_shadow=dependency("compare", obj["comparison"]),
        run_task_execution_canary=dependency("canary", obj["canary"]),
        observability_call=observe,
        execute_plan=execute,
        build_task_execution_shadow=dependency("cp8", obj["cp8"]),
        build_task_planner_canary=dependency("cp9", obj["cp9"]),
    )
    return result, calls, obj


def test_exact_order_identity_observer_and_return_contract():
    result, calls, obj = _run()
    assert isinstance(result, InitialExecutionStageResult)
    assert [field.name for field in fields(result)] == [
        "plan", "task_execution_plans_shadow",
        "task_execution_plan_comparison_shadow", "task_execution_canary_p4_6b",
        "typed_execution_results", "results", "trace",
        "task_execution_shadow", "task_planner_canary",
    ]
    assert [call[0] for call in calls] == [
        "attach", "build", "compare", "canary", "observe", "execute", "cp8", "cp9",
    ]
    assert calls[0][1] == (obj["input_plan"],)
    assert calls[1][1] == (obj["plan"],)
    assert calls[2][1] == (obj["plan"], obj["task_plans"])
    assert calls[3][1] == (obj["plan"], obj["task_plans"])
    assert calls[3][2]["sender"] is obj["sender"]
    assert calls[4][1][0] is obj["timings"]
    assert calls[4][1][1] == "initial_specialist"
    assert calls[4][1][2] is obj["execute_callable"]
    assert calls[4][1][3] is obj["plan"]
    assert calls[5][1] == (obj["plan"],)
    assert calls[5][2]["sender"] is obj["sender"]
    assert calls[5][2]["shadow_observer"] is calls[4][2]["shadow_observer"]
    assert result.plan is obj["plan"]
    assert result.task_execution_plans_shadow is obj["task_plans"]
    assert result.task_execution_plan_comparison_shadow is obj["comparison"]
    assert result.task_execution_canary_p4_6b is obj["canary"]
    assert result.typed_execution_results == [obj["typed_1"], obj["typed_2"]]
    assert type(result.typed_execution_results) is list
    assert result.results is obj["results"] and result.trace is obj["trace"]
    assert result.task_execution_shadow is obj["cp8"]
    assert result.task_planner_canary is obj["cp9"]


@pytest.mark.parametrize(
    ("fail_at", "plans", "comparison", "canary", "cp8", "cp9"),
    [
        ("build", (), None, "ok", "ok", "ok"),
        ("compare", (), None, "ok", "ok", "ok"),
        ("canary", "ok", "ok", None, "ok", "ok"),
        ("cp8", "ok", "ok", "ok", None, "ok"),
        ("cp9", "ok", "ok", "ok", "ok", None),
    ],
)
def test_fail_open_boundaries_are_independent(
    fail_at, plans, comparison, canary, cp8, cp9
):
    result, calls, obj = _run(fail_at=fail_at)
    expected = lambda marker, key: None if marker is None else obj[key]
    assert result.task_execution_plans_shadow is (
        () if plans == () else obj["task_plans"]
    )
    assert result.task_execution_plan_comparison_shadow is expected(comparison, "comparison")
    assert result.task_execution_canary_p4_6b is expected(canary, "canary")
    assert result.task_execution_shadow is expected(cp8, "cp8")
    assert result.task_planner_canary is expected(cp9, "cp9")
    assert [call[0] for call in calls].count("execute") == 1


@pytest.mark.parametrize("fail_at", ["attach", "observe", "execute"])
def test_authoritative_failures_propagate_unchanged(fail_at):
    with pytest.raises(LookupError, match=f"^{fail_at}$") as caught:
        _run(fail_at=fail_at)
    assert str(caught.value) == fail_at


def test_stage_imports_are_minimal_and_core_block_is_not_duplicated():
    stage_path = Path("app/orchestrator/initial_execution_stage.py")
    service_path = Path("app/orchestrator/service.py")
    stage_source = stage_path.read_text(encoding="utf-8")
    service_source = service_path.read_text(encoding="utf-8")
    stage_tree = ast.parse(stage_source)

    imported_roots = {
        node.module.split(".")[0]
        for node in ast.walk(stage_tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert imported_roots == {"dataclasses", "typing"}
    assert "app.orchestrator.service" not in stage_source
    assert service_source.count("run_initial_execution_stage(") == 1
    assert service_source.count('"initial_specialist"') == 0
    assert stage_source.count('"initial_specialist"') == 1
    assert "typed_execution_results.append" not in service_source


def test_service_binds_all_outputs_before_attempts_and_preserves_wrappers():
    source = Path("app/orchestrator/service.py").read_text(encoding="utf-8")
    stage_call = source.index("initial_execution = run_initial_execution_stage(")
    attempts = source.index("attempts = _observability_get(", stage_call)
    for binding in (
        "plan = initial_execution.plan",
        "task_execution_plans_shadow = (",
        "task_execution_plan_comparison_shadow = (",
        "task_execution_canary_p4_6b = (",
        "typed_execution_results = initial_execution.typed_execution_results",
        "results = initial_execution.results",
        "trace = initial_execution.trace",
        "task_execution_shadow = initial_execution.task_execution_shadow",
        "task_planner_canary = initial_execution.task_planner_canary",
    ):
        assert stage_call < source.index(binding, stage_call) < attempts
    assert "_p4_15cp3c_previous_run_orchestrator = run_orchestrator" in source
    assert "_p4_15cp4b_previous_run_orchestrator = run_orchestrator" in source
    assert "_p4_15cp4f_previous_run_orchestrator = run_orchestrator" in source
