"""Characterize the remaining service-owned bounded-research-v1 boundary."""
from __future__ import annotations

import importlib.util
from collections import UserDict
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.orchestrator import service
from app.orchestrator.models import OrchestratorAskRequest


class StopAtAnswer(BaseException):
    pass


class Fatal(BaseException):
    pass


class DictSubclass(dict):
    pass


class MappingOnly(UserDict):
    pass


_DEFAULT_RESEARCH = object()


class ObservedDict(dict):
    def __init__(self, *args, events=None, error_key=None, error=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.events = events if events is not None else []
        self.error_key = error_key
        self.error = error

    def get(self, key, default=None):
        self.events.append(("get", key, default))
        if key == self.error_key:
            raise self.error
        return super().get(key, default)

    def __contains__(self, key):
        self.events.append(("contains", key))
        if key == self.error_key:
            raise self.error
        return super().__contains__(key)


def _prior_characterization():
    path = Path(__file__).with_name(
        "test_post_phase_c_clarification_status_boundary_characterization.py"
    )
    spec = importlib.util.spec_from_file_location("phase_c_3v1_for_3w1", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _install(
    monkeypatch,
    *,
    required=True,
    status="ok",
    clarification_required=False,
    gate=True,
    gate_error=None,
    research_return=_DEFAULT_RESEARCH,
    research_error=None,
    results=None,
):
    prior = _prior_characterization()
    raw_results = [object(), object()] if results is None else results
    h = prior._install(monkeypatch, results=raw_results)
    requested_information = [object(), object()]
    h.plan.research_required = required
    h.plan.requested_information = requested_information
    input_before = (
        dict(vars(h.plan)), tuple(h.results), tuple(h.typed), dict(h.trace)
    )
    clarification = {"required": clarification_required, "question": object()}
    sender = object()
    events = []
    calls = []

    def status_stage(*args, **kwargs):
        events.append("status")
        calls.append(("status", args, kwargs))
        return SimpleNamespace(status=status, clarification=clarification)

    def enabled():
        events.append("gate")
        if gate_error is not None:
            raise gate_error
        return gate

    returned = (
        {"status": "ok", "answer": None}
        if research_return is _DEFAULT_RESEARCH
        else research_return
    )

    def agent(*args, **kwargs):
        events.append("agent")
        calls.append(("agent", args, kwargs))
        if research_error is not None:
            raise research_error
        return returned

    def legacy(*args, **kwargs):
        events.append("legacy")
        calls.append(("legacy", args, kwargs))
        if research_error is not None:
            raise research_error
        return returned

    def answer(*args, **kwargs):
        events.append("answer")
        calls.append(("answer", args, kwargs))
        raise StopAtAnswer("controlled next boundary")

    tick = iter(range(1000))
    monkeypatch.setattr(service, "_observability_now", lambda: float(next(tick)))
    monkeypatch.setattr(service, "run_post_phase_c_status_stage", status_stage)
    monkeypatch.setattr(service, "_research_agent_enabled", enabled)
    monkeypatch.setattr(service, "run_bounded_research_agent", agent)
    monkeypatch.setattr(service, "run_bounded_research", legacy)
    monkeypatch.setattr(service, "_build_user_answer", answer)
    return SimpleNamespace(**locals())


def _run(h, exception=StopAtAnswer):
    with pytest.raises(exception) as raised:
        service._p4_15cp3c_previous_run_orchestrator(
            OrchestratorAskRequest(q="synthetic", vraag=""), sender=h.sender
        )
    return raised.value


def _locals(error):
    traceback = error.__traceback__
    while traceback is not None:
        if traceback.tb_frame.f_code is service._p4_15cp3c_previous_run_orchestrator.__code__:
            return traceback.tb_frame.f_locals
        traceback = traceback.tb_next
    raise AssertionError("service frame absent")


def _call(h, name):
    return [call for call in h.calls if call[0] == name]


@pytest.mark.parametrize(
    ("required", "status", "clarification_required", "chosen"),
    [
        (True, "ok", False, "agent"),
        (1, "ok", False, "agent"),
        (False, "ok", False, None),
        (0, "ok", False, None),
        (True, "error", False, None),
        (True, "OK", False, None),
        (True, "ok", True, None),
        (True, "ok", 1, None),
    ],
)
def test_exact_route_conditions_and_at_most_one_execution(
    monkeypatch, required, status, clarification_required, chosen
):
    h = _install(
        monkeypatch,
        required=required,
        status=status,
        clarification_required=clarification_required,
    )
    error = _run(h)
    names = [call[0] for call in h.calls]
    assert names.count("agent") + names.count("legacy") == (chosen is not None)
    assert names.count("answer") == 1
    assert ("gate" in h.events) is (chosen is not None)
    if chosen:
        assert names == ["status", chosen, "answer"]
    else:
        assert names == ["status", "answer"]
        locals_ = _locals(error)
        assert locals_["research"] == {
            "status": "not_required",
            "required": bool(required),
            "mode": "bounded_synthesis_v1",
            "ai_calls_used": 0,
            "max_ai_calls": 1,
            "follow_up_rounds_used": 0,
            "max_follow_up_rounds": 0,
            "answer": None,
        }


@pytest.mark.parametrize("gate, chosen", [(True, "agent"), (False, "legacy")])
def test_runtime_dependencies_arguments_identity_order_and_fresh_defaults(
    monkeypatch, gate, chosen
):
    returned = {"status": "opaque", "ai_calls_used": 4}
    h = _install(monkeypatch, gate=gate, research_return=returned)
    error = _run(h)
    call = _call(h, chosen)[0]
    assert call[1] == (h.h.plan, h.h.results)
    assert call[1][0] is h.h.plan and call[1][1] is h.h.results
    assert call[2] == ({"sender": h.sender} if gate else {})
    assert h.events == ["status", "gate", chosen, "answer"]
    assert _locals(error)["research"] is returned
    assert _call(h, "answer")[0][1] == (h.h.results,)
    assert _call(h, "answer")[0][2] == {
        "requested_information": h.requested_information
    }


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, False), ("", False), (" false ", False), ("0", False),
        ("TRUE", True), (" yes ", True), ("On", True), ("1", True),
        ("2", False), (True, True), (1, True),
    ],
)
def test_environment_gate_exact_string_normalization(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv("AI_RESEARCH_AGENT_ENABLED", raising=False)
    else:
        monkeypatch.setenv("AI_RESEARCH_AGENT_ENABLED", raw)
    assert service._research_agent_enabled() is expected


@pytest.mark.parametrize("returned", [{"x": 1}, DictSubclass(x=1), [1], (1,), None, object()])
def test_research_return_is_bound_by_identity_without_copy_or_coercion(monkeypatch, returned):
    h = _install(monkeypatch, research_return=returned)
    error = _run(h)
    locals_ = _locals(error)
    assert locals_["research"] is returned
    assert locals_["plan_research_agent"] is None
    assert locals_["counts"]["plan_research_ai_calls"] == 0


@pytest.mark.parametrize(
    ("agent", "expected_agent", "follow", "ai"),
    [
        (None, None, 0, 8),
        (MappingOnly(follow_up_specialist_calls=7, total_ai_calls_used=6), None, 0, 8),
        (DictSubclass(follow_up_specialist_calls="3", total_ai_calls_used="4"), "same", 3, 4),
        ({}, "same", 0, 8),
        ({"follow_up_specialist_calls": -2, "total_ai_calls_used": True}, "same", 0, 0),
        ({"follow_up_specialist_calls": 2.9}, "same", 2, 8),
    ],
)
def test_agent_parsing_requires_real_dict_and_uses_exact_counter_fallbacks(
    monkeypatch, agent, expected_agent, follow, ai
):
    research = {"agent": agent, "ai_calls_used": "8"}
    h = _install(monkeypatch, research_return=research)
    error = _run(h)
    locals_ = _locals(error)
    assert locals_["plan_research_agent"] is (agent if expected_agent else None)
    assert locals_["counts"]["plan_research_follow_up_specialist_calls"] == follow
    assert locals_["counts"]["plan_research_ai_calls"] == ai


def test_metadata_read_order_assignment_and_aggregate_formulas(monkeypatch):
    events = []
    agent = ObservedDict(
        follow_up_specialist_calls="2", total_ai_calls_used="3", events=events
    )
    research = ObservedDict(agent=agent, ai_calls_used=99, events=events)
    h = _install(monkeypatch, research_return=research)
    error = _run(h)
    counts = _locals(error)["counts"]
    assert events == [
        ("get", "agent", None),
        ("get", "follow_up_specialist_calls", None),
        ("contains", "total_ai_calls_used"),
        ("get", "total_ai_calls_used", None),
    ]
    assert counts["plan_research_follow_up_specialist_calls"] == 2
    assert counts["plan_research_ai_calls"] == 3
    assert counts["research_follow_up_specialist_calls"] == (
        counts["phase_c_research_follow_up_specialist_calls"] + 2
    )
    assert counts["total_specialist_calls"] == (
        counts["initial_specialist_calls"] + counts["research_follow_up_specialist_calls"]
    )
    assert counts["total_ai_calls"] == counts["phase_c_ai_calls"] + 3


@pytest.mark.parametrize("value, expected", [(None, 0), (0, 0), (-3, 0), (4, 4), ("5", 5), (2.9, 2), (True, 0), ("bad", 0)])
def test_top_level_ai_counter_uses_nonnegative_integer_semantics(monkeypatch, value, expected):
    h = _install(monkeypatch, research_return={"ai_calls_used": value})
    error = _run(h)
    assert _locals(error)["counts"]["plan_research_ai_calls"] == expected


@pytest.mark.parametrize("where", ["gate", "agent_get", "follow_get", "contains", "ai_get", "convert"])
@pytest.mark.parametrize("error_type", [RuntimeError, Fatal])
def test_exception_zones_propagate_identically_with_exact_partial_state(
    monkeypatch, where, error_type
):
    error = error_type(where)
    events = []
    conversion_marker = object()
    agent = ObservedDict(
        follow_up_specialist_calls=2,
        total_ai_calls_used=(conversion_marker if where == "convert" else 3),
        events=events,
        error_key=("follow_up_specialist_calls" if where == "follow_get" else
                   "total_ai_calls_used" if where in {"contains", "ai_get"} else None),
        error=error,
    )
    if where == "ai_get":
        agent.error_key = None
        original_get = agent.get
        agent.get = lambda key, default=None: (_ for _ in ()).throw(error) if key == "total_ai_calls_used" else original_get(key, default)
    research = ObservedDict(agent=agent, events=events,
                            error_key="agent" if where == "agent_get" else None,
                            error=error)
    h = _install(monkeypatch, gate_error=error if where == "gate" else None,
                 research_return=research)
    if where == "convert":
        original = service._observability_nonnegative_int
        def convert(value):
            if value is conversion_marker:
                raise error
            return original(value)
        monkeypatch.setattr(service, "_observability_nonnegative_int", convert)
    raised = _run(h, error_type)
    assert raised is error
    locals_ = _locals(raised)
    counts = locals_["counts"]
    assert _call(h, "answer") == []
    assert len(_call(h, "agent")) == (0 if where == "gate" else 1)
    if where in {"contains", "ai_get", "convert"}:
        assert counts["plan_research_follow_up_specialist_calls"] == 2
    else:
        assert counts["plan_research_follow_up_specialist_calls"] == 0
    if where != "gate":
        assert locals_["timings"]["plan_research"] == 1000


@pytest.mark.parametrize("error_type", [RuntimeError, Fatal])
def test_research_callable_failure_records_timing_and_never_retries(monkeypatch, error_type):
    error = error_type("research")
    h = _install(monkeypatch, research_error=error)
    raised = _run(h, error_type)
    assert raised is error
    assert len(_call(h, "agent")) == 1
    assert _call(h, "legacy") == [] and _call(h, "answer") == []
    assert _locals(raised)["timings"]["plan_research"] == 1000


def test_answer_failure_does_not_repeat_research_and_exposes_frozen_locals(monkeypatch):
    result_items = [object(), object()]
    research = {"agent": {"follow_up_specialist_calls": 1}, "ai_calls_used": 2}
    h = _install(monkeypatch, results=result_items, research_return=research)
    raised = _run(h)
    locals_ = _locals(raised)
    assert len(_call(h, "agent")) == len(_call(h, "answer")) == 1
    assert _call(h, "legacy") == []
    assert locals_["plan"] is h.h.plan
    assert locals_["results"] is result_items
    assert locals_["typed_execution_results"] is h.h.typed
    assert locals_["trace"] is h.h.trace
    assert locals_["sender"] is h.sender
    assert locals_["status"] == "ok"
    assert locals_["clarification"] is h.clarification
    assert locals_["research"] is research
    assert locals_["plan_research_agent"] is research["agent"]
    assert (dict(vars(h.h.plan)), tuple(h.h.results), tuple(h.h.typed), dict(h.h.trace)) == h.input_before


def test_each_core_call_gets_fresh_research_and_observability_state(monkeypatch):
    snapshots = []
    for _ in range(2):
        with monkeypatch.context() as patch:
            h = _install(patch, required=False)
            error = _run(h)
            locals_ = _locals(error)
            snapshots.append((locals_["research"], locals_["counts"], locals_["timings"]))
    assert snapshots[0][0] is not snapshots[1][0]
    assert snapshots[0][1] is not snapshots[1][1]
    assert snapshots[0][2] is not snapshots[1][2]
    assert snapshots[0][0] == snapshots[1][0]


def test_ast_fixes_boundary_order_single_calls_and_runtime_names():
    path = Path(__file__).parents[2] / "app/orchestrator/service.py"
    tree = __import__("ast").parse(path.read_text(encoding="utf-8"))
    function = next(
        node for node in tree.body
        if isinstance(node, __import__("ast").FunctionDef) and node.name == "run_orchestrator"
    )
    direct_names = {
        "run_post_phase_c_status_stage", "_research_agent_enabled", "_build_user_answer",
    }
    calls = [
        node for node in __import__("ast").walk(function)
        if isinstance(node, __import__("ast").Call)
        and isinstance(node.func, __import__("ast").Name)
        and node.func.id in direct_names
    ]
    status_line = min(
        node.lineno for node in calls
        if node.func.id == "run_post_phase_c_status_stage"
    )
    answer_line = min(
        node.lineno for node in calls
        if node.func.id == "_build_user_answer" and node.lineno > status_line
    )
    bounded_calls = [node for node in calls if status_line <= node.lineno <= answer_line]
    grouped = {name: [node for node in bounded_calls if node.func.id == name]
               for name in direct_names}
    assert all(len(nodes) == 1 for nodes in grouped.values())
    observed = [
        node for node in __import__("ast").walk(function)
        if isinstance(node, __import__("ast").Call)
        and isinstance(node.func, __import__("ast").Name)
        and node.func.id == "_observability_call"
        and status_line < node.lineno < answer_line
    ]
    assert len(observed) == 2
    assert {node.args[2].id for node in observed} == {
        "run_bounded_research_agent", "run_bounded_research"
    }
    assert grouped["run_post_phase_c_status_stage"][0].lineno < grouped["_research_agent_enabled"][0].lineno
    assert grouped["_research_agent_enabled"][0].lineno < grouped["_build_user_answer"][0].lineno
    assert all(node.lineno < grouped["_build_user_answer"][0].lineno for node in observed)
