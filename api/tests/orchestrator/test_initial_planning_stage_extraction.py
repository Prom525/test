from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.orchestrator import initial_planning_stage, service
from app.orchestrator.models import OrchestratorAskRequest


def _chain(*, fail_at=None):
    calls = []
    plans = [object(), object(), object(), object()]
    timings = {}

    def observability(current_timings, label, function, *args, **kwargs):
        calls.append(("timing", label, function, args, kwargs))
        if fail_at == "observability":
            raise LookupError("observability")
        return function(*args, **kwargs)

    def understanding(question, *, conversation_context):
        calls.append(("understanding", question, conversation_context))
        if fail_at == "understanding":
            raise LookupError("understanding")
        return plans[0]

    def routing(plan):
        calls.append(("routing", plan))
        if fail_at == "routing":
            raise LookupError("routing")
        return plans[1]

    def research(plan):
        calls.append(("research", plan))
        if fail_at == "research":
            raise LookupError("research")
        return plans[2]

    def planning(plan):
        calls.append(("planning", plan))
        if fail_at == "planning":
            raise LookupError("planning")
        return plans[3]

    kwargs = dict(
        observability_call=observability,
        understand_query=understanding,
        apply_routing_sanity=routing,
        assess_research_requirement=research,
        build_execution_plan=planning,
    )
    return calls, plans, timings, kwargs


def test_direct_stage_preserves_order_identity_labels_and_serialized_context():
    calls, plans, timings, kwargs = _chain()
    context = {"already": "serialized"}
    result = initial_planning_stage.run_initial_planning_stage(
        " question ", context, timings, **kwargs
    )

    assert result is plans[3]
    assert calls[0][1] == "understanding"
    assert calls[1] == ("understanding", " question ", context)
    assert calls[2] == ("routing", plans[0])
    assert calls[3][1] == "research_requirement"
    assert calls[4] == ("research", plans[1])
    assert calls[5][1] == "planning"
    assert calls[6] == ("planning", plans[2])
    assert [call[1] for call in calls if call[0] == "timing"] == [
        "understanding", "research_requirement", "planning"
    ]


@pytest.mark.parametrize(
    ("fail_at", "expected_steps"),
    [
        ("observability", []),
        ("understanding", ["understanding"]),
        ("routing", ["understanding", "routing"]),
        ("research", ["understanding", "routing", "research"]),
        ("planning", ["understanding", "routing", "research", "planning"]),
    ],
)
def test_stage_propagates_each_exception_and_stops(fail_at, expected_steps):
    calls, _plans, timings, kwargs = _chain(fail_at=fail_at)
    with pytest.raises(LookupError, match=fail_at):
        initial_planning_stage.run_initial_planning_stage("q", None, timings, **kwargs)
    assert [call[0] for call in calls if call[0] != "timing"] == expected_steps


def test_service_runtime_lookup_and_execute_order(monkeypatch):
    calls = []
    plans = [object(), object(), object(), object()]

    def timed(_timings, label, function, *args, **kwargs):
        calls.append(label)
        return function(*args, **kwargs)

    monkeypatch.setattr(service, "_observability_call", timed)
    def understand(question, **kwargs):
        calls.append(("understand", question, kwargs))
        return plans[0]

    def route(plan):
        calls.append(("route", plan))
        return plans[1]

    def assess(plan):
        calls.append(("assess", plan))
        return plans[2]

    def build(plan):
        calls.append(("build", plan))
        return plans[3]

    monkeypatch.setattr(service, "understand_query", understand)
    monkeypatch.setattr(service, "apply_routing_sanity", route)
    monkeypatch.setattr(service, "assess_research_requirement", assess)
    monkeypatch.setattr(service, "build_execution_plan", build)
    monkeypatch.setattr(
        service,
        "_attach_intent_task_evidence_requirements_shadow",
        lambda p: p,
    )
    monkeypatch.setattr(service, "build_task_execution_plans_shadow", lambda p: ())
    monkeypatch.setattr(service, "compare_task_execution_plans_shadow", lambda *a: None)
    monkeypatch.setattr(service, "_run_task_execution_canary_p4_6b", lambda *a, **k: None)

    def execute(plan, **kwargs):
        calls.append(("execute", plan, kwargs))
        raise RuntimeError("stop-after-stage")

    monkeypatch.setattr(service, "execute_plan", execute)
    payload = OrchestratorAskRequest(q="  selected  ", vraag="ignored")
    with pytest.raises(RuntimeError, match="stop-after-stage"):
        service._p4_15cp3c_previous_run_orchestrator(payload)
    assert calls[:7] == [
        "understanding",
        ("understand", "selected", {"conversation_context": None}),
        ("route", plans[0]),
        "research_requirement",
        ("assess", plans[1]),
        "planning",
        ("build", plans[2]),
    ]
    assert calls[7] == "initial_specialist"
    assert calls[8][0] == "execute" and calls[8][1] is plans[3]


def test_source_shape_leaf_imports_and_wrapper_chain():
    stage_tree = ast.parse(Path(initial_planning_stage.__file__).read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(stage_tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module.split(".")[0]
        for node in ast.walk(stage_tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert imported == {"typing"}
    assert initial_planning_stage.__all__ == ("run_initial_planning_stage",)

    service_tree = ast.parse(Path(service.__file__).read_text(encoding="utf-8-sig"))
    core = [n for n in service_tree.body if isinstance(n, ast.FunctionDef) and n.name == "run_orchestrator"][0]
    called = [n.func.id for n in ast.walk(core) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
    assert called.count("run_initial_planning_stage") == 1
    for old_call in ("understand_query", "apply_routing_sanity", "assess_research_requirement", "build_execution_plan"):
        assert old_call not in called
    bindings = [
        n.targets[0].id for n in service_tree.body
        if isinstance(n, ast.Assign) and len(n.targets) == 1
        and isinstance(n.targets[0], ast.Name) and isinstance(n.value, ast.Name)
        and n.value.id == "run_orchestrator" and "previous_run_orchestrator" in n.targets[0].id
    ]
    assert bindings == [
        "_p4_15cp3c_previous_run_orchestrator",
        "_p4_15cp4b_previous_run_orchestrator",
        "_p4_15cp4f_previous_run_orchestrator",
    ]
