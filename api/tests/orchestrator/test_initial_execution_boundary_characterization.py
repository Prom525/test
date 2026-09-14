"""Characterize the core's initial execution boundary before extraction.

The harness executes the real core facade and stops at its first operation
after CP9.  Every dependency before that stop is a service-level monkeypatch,
which preserves the runtime lookup contract and prevents network access.
"""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.orchestrator import service
from app.orchestrator.models import OrchestratorAskRequest


class BoundaryStop(RuntimeError):
    pass


@dataclass
class BoundaryHarness:
    calls: list
    outputs: dict
    objects: dict


def _install_boundary(monkeypatch, *, fail_at=None):
    calls = []
    objects = {
        "planning_plan": object(),
        "plan": object(),
        "task_plans": (object(), object()),
        "comparison": object(),
        "execution_canary": object(),
        "typed": (object(), object()),
        "results": [object()],
        "trace": {"opaque": object()},
        "cp8": object(),
        "cp9": object(),
        "sender": object(),
    }
    outputs = {}

    monkeypatch.setattr(service, "_new_observability_timings", lambda: {})
    monkeypatch.setattr(service, "_new_observability_counts", lambda: {})
    monkeypatch.setattr(service, "_observability_now", lambda: 1.0)

    def planning(*args, **kwargs):
        calls.append(("planning", args, kwargs))
        return objects["planning_plan"]

    def attach(plan):
        calls.append(("attach", plan))
        if fail_at == "attach":
            raise LookupError("attach-boundary")
        outputs["plan"] = objects["plan"]
        return objects["plan"]

    def task_plan_build(plan):
        calls.append(("task-plan-build", plan))
        if fail_at == "task-plan-build":
            raise LookupError("task-plan-build-boundary")
        outputs["task_execution_plans_shadow"] = objects["task_plans"]
        return objects["task_plans"]

    def task_plan_compare(plan, task_plans):
        calls.append(("task-plan-compare", plan, task_plans))
        if fail_at == "task-plan-compare":
            raise LookupError("task-plan-compare-boundary")
        outputs["task_execution_plan_comparison_shadow"] = objects["comparison"]
        return objects["comparison"]

    def execution_canary(plan, task_plans, *, sender):
        calls.append(("execution-canary", plan, task_plans, sender))
        outputs["task_plans_at_canary"] = task_plans
        outputs["task_execution_plans_shadow"] = task_plans
        if fail_at == "execution-canary":
            outputs["task_execution_canary_p4_6b"] = None
            raise LookupError("execution-canary-boundary")
        outputs["task_execution_canary_p4_6b"] = objects["execution_canary"]
        return objects["execution_canary"]

    def execute(plan, *, sender, shadow_observer):
        calls.append(("execute", plan, sender, shadow_observer))
        outputs["execution_count"] = outputs.get("execution_count", 0) + 1
        if fail_at == "execute":
            raise LookupError("execute-boundary")
        for item in objects["typed"]:
            shadow_observer(item)
        outputs["typed_execution_results"] = list(objects["typed"])
        outputs["results"] = objects["results"]
        outputs["trace"] = objects["trace"]
        return objects["results"], objects["trace"]

    def observed(timings, label, function, *args, **kwargs):
        calls.append(("observability", timings, label, function, args, kwargs))
        if fail_at == "observability":
            raise LookupError("observability-boundary")
        result = function(*args, **kwargs)
        outputs["observed_result"] = result
        return result

    def cp8(plan, trace):
        calls.append(("cp8", plan, trace))
        if fail_at == "cp8":
            outputs["task_execution_shadow"] = None
            raise LookupError("cp8-boundary")
        outputs["task_execution_shadow"] = objects["cp8"]
        return objects["cp8"]

    def cp9(plan):
        calls.append(("cp9", plan))
        if fail_at == "cp9":
            outputs["task_planner_canary"] = None
            raise LookupError("cp9-boundary")
        outputs["task_planner_canary"] = objects["cp9"]
        return objects["cp9"]

    def stop_after_boundary(trace, key, default):
        calls.append(("post-boundary", trace, key, default))
        outputs.setdefault("task_execution_plans_shadow", ())
        outputs.setdefault("task_execution_plan_comparison_shadow", None)
        raise BoundaryStop("controlled stop after initial execution boundary")

    monkeypatch.setattr(service, "run_initial_planning_stage", planning)
    monkeypatch.setattr(service, "_attach_intent_task_evidence_requirements_shadow", attach)
    monkeypatch.setattr(service, "build_task_execution_plans_shadow", task_plan_build)
    monkeypatch.setattr(service, "compare_task_execution_plans_shadow", task_plan_compare)
    monkeypatch.setattr(service, "_run_task_execution_canary_p4_6b", execution_canary)
    monkeypatch.setattr(service, "execute_plan", execute)
    monkeypatch.setattr(service, "_observability_call", observed)
    monkeypatch.setattr(service, "build_task_execution_shadow", cp8)
    monkeypatch.setattr(service, "build_task_planner_canary", cp9)
    monkeypatch.setattr(service, "_observability_get", stop_after_boundary)
    return BoundaryHarness(calls, outputs, objects)


def _run(harness):
    payload = OrchestratorAskRequest(q="synthetic boundary input", vraag="")
    with pytest.raises(BoundaryStop, match="controlled stop"):
        service._p4_15cp3c_previous_run_orchestrator(
            payload,
            sender=harness.objects["sender"],
        )


def test_success_contract_has_exact_order_identity_label_and_output_shape(monkeypatch):
    harness = _install_boundary(monkeypatch)
    _run(harness)
    calls, output, obj = harness.calls, harness.outputs, harness.objects

    assert [call[0] for call in calls] == [
        "planning", "attach", "task-plan-build", "task-plan-compare",
        "execution-canary", "observability", "execute", "cp8", "cp9",
        "post-boundary",
    ]
    assert calls[1][1] is obj["planning_plan"]
    assert calls[2][1] is obj["plan"]
    assert calls[3][1] is obj["plan"] and calls[3][2] is obj["task_plans"]
    assert calls[4][1] is obj["plan"] and calls[4][2] is obj["task_plans"]
    assert calls[4][3] is obj["sender"]

    observed = calls[5]
    assert observed[2] == "initial_specialist"
    assert observed[3] is service.execute_plan
    assert observed[4] == (obj["plan"],)
    assert observed[5]["sender"] is obj["sender"]
    assert calls[6][1] is obj["plan"] and calls[6][2] is obj["sender"]
    assert calls[6][3] is observed[5]["shadow_observer"]
    assert calls[7][1] is obj["plan"] and calls[7][2] is obj["trace"]
    assert calls[8][1] is obj["plan"]
    assert calls[9][1] is obj["trace"]

    output["shape"] = {
        "plan": output["plan"],
        "task_execution_plans_shadow": output["task_execution_plans_shadow"],
        "task_execution_plan_comparison_shadow": output["task_execution_plan_comparison_shadow"],
        "task_execution_canary_p4_6b": output["task_execution_canary_p4_6b"],
        "typed_execution_results": output["typed_execution_results"],
        "results": output["results"],
        "trace": output["trace"],
        "task_execution_shadow": output["task_execution_shadow"],
        "task_planner_canary": output["task_planner_canary"],
    }
    assert output["shape"] == {
        "plan": obj["plan"],
        "task_execution_plans_shadow": obj["task_plans"],
        "task_execution_plan_comparison_shadow": obj["comparison"],
        "task_execution_canary_p4_6b": obj["execution_canary"],
        "typed_execution_results": [obj["typed"][0], obj["typed"][1]],
        "results": obj["results"],
        "trace": obj["trace"],
        "task_execution_shadow": obj["cp8"],
        "task_planner_canary": obj["cp9"],
    }
    assert output["observed_result"][0] is obj["results"]
    assert output["observed_result"][1] is obj["trace"]
    assert output["execution_count"] == 1


@pytest.mark.parametrize(
    ("fail_at", "expected_task_plans", "compare_runs", "canary", "cp8", "cp9"),
    [
        ("task-plan-build", (), False, "ok", "ok", "ok"),
        ("task-plan-compare", (), True, "ok", "ok", "ok"),
        ("execution-canary", "built", True, None, "ok", "ok"),
        ("cp8", "built", True, "ok", None, "ok"),
        ("cp9", "built", True, "ok", "ok", None),
    ],
)
def test_fail_open_zones_are_independent_and_execute_once(
    monkeypatch, fail_at, expected_task_plans, compare_runs, canary, cp8, cp9
):
    harness = _install_boundary(monkeypatch, fail_at=fail_at)
    _run(harness)
    names = [call[0] for call in harness.calls]
    obj = harness.objects

    expected = obj["task_plans"] if expected_task_plans == "built" else ()
    assert harness.outputs["task_plans_at_canary"] is expected
    assert harness.outputs["task_execution_plans_shadow"] is expected
    assert harness.outputs["task_execution_plan_comparison_shadow"] is (
        obj["comparison"] if fail_at not in {"task-plan-build", "task-plan-compare"} else None
    )
    assert ("task-plan-compare" in names) is compare_runs
    assert harness.outputs["execution_count"] == 1
    assert harness.calls[names.index("execute")][1] is obj["plan"]
    assert ("execution-canary" in names) is True
    assert ("cp8" in names) is True and ("cp9" in names) is True

    actual = {
        "canary": harness.outputs["task_execution_canary_p4_6b"],
        "cp8": harness.outputs["task_execution_shadow"],
        "cp9": harness.outputs["task_planner_canary"],
    }
    assert actual["canary"] is (None if canary is None else obj["execution_canary"])
    assert actual["cp8"] is (None if cp8 is None else obj["cp8"])
    assert actual["cp9"] is (None if cp9 is None else obj["cp9"])


@pytest.mark.parametrize(
    ("fail_at", "message", "expected_names"),
    [
        ("attach", "attach-boundary", ["planning", "attach"]),
        (
            "observability",
            "observability-boundary",
            ["planning", "attach", "task-plan-build", "task-plan-compare",
             "execution-canary", "observability"],
        ),
        (
            "execute",
            "execute-boundary",
            ["planning", "attach", "task-plan-build", "task-plan-compare",
             "execution-canary", "observability", "execute"],
        ),
    ],
)
def test_authoritative_failures_propagate_unchanged_and_short_circuit(
    monkeypatch, fail_at, message, expected_names
):
    harness = _install_boundary(monkeypatch, fail_at=fail_at)
    payload = OrchestratorAskRequest(q="synthetic boundary input", vraag="")
    with pytest.raises(LookupError, match=message) as caught:
        service._p4_15cp3c_previous_run_orchestrator(
            payload, sender=harness.objects["sender"]
        )
    assert str(caught.value) == message
    assert [call[0] for call in harness.calls] == expected_names
    assert harness.outputs.get("execution_count", 0) <= 1
    assert "cp8" not in expected_names and "cp9" not in expected_names
