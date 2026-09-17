import ast
from dataclasses import FrozenInstanceError, fields
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.orchestrator.phase_c_bounded_research_v1_stage import (
    PhaseCBoundedResearchV1StageResult,
    run_phase_c_bounded_research_v1_stage,
)


class Fatal(BaseException):
    pass


class DictSubclass(dict):
    pass


class MappingOnly:
    def get(self, key, default=None):
        return {"agent": {"total_ai_calls_used": 9}}.get(key, default)


class ObservedDict(dict):
    def __init__(self, *args, events=None, error_key=None, error=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.events = [] if events is None else events
        self.error_key = error_key
        self.error = error

    def get(self, key, default=None):
        self.events.append(("get", key, default))
        if self.error_key == ("get", key):
            raise self.error
        return super().get(key, default)

    def __contains__(self, key):
        self.events.append(("contains", key))
        if self.error_key == ("contains", key):
            raise self.error
        return super().__contains__(key)


def _counts():
    return {
        "initial_specialist_calls": 5,
        "phase_c_research_follow_up_specialist_calls": 7,
        "plan_research_follow_up_specialist_calls": 0,
        "research_follow_up_specialist_calls": 0,
        "total_specialist_calls": 0,
        "phase_c_ai_calls": 11,
        "plan_research_ai_calls": 0,
        "total_ai_calls": 0,
    }


def _nonnegative(value):
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _run(
    *,
    required=True,
    status="ok",
    clarification=None,
    gate=True,
    returned=None,
    gate_callable=None,
    observe_callable=None,
    convert_callable=None,
    agent_callable=None,
    legacy_callable=None,
    counts=None,
    timings=None,
    events=None,
):
    events = [] if events is None else events
    plan = SimpleNamespace(research_required=required)
    results = [object()]
    sender = object()
    clarification = (
        {"required": False} if clarification is None else clarification
    )
    counts = _counts() if counts is None else counts
    timings = {} if timings is None else timings
    returned = {"status": "ok"} if returned is None else returned

    def enabled():
        events.append("gate")
        return gate

    def agent(*args, **kwargs):
        events.append(("agent", args, kwargs))
        return returned

    def legacy(*args, **kwargs):
        events.append(("legacy", args, kwargs))
        return returned

    def observe(target_timings, label, callable_, *args, **kwargs):
        events.append(("observe", target_timings, label, callable_, args, kwargs))
        try:
            return callable_(*args, **kwargs)
        finally:
            target_timings[label] = 13

    result = run_phase_c_bounded_research_v1_stage(
        plan,
        results,
        status,
        clarification,
        sender,
        timings,
        counts,
        _research_agent_enabled=enabled if gate_callable is None else gate_callable,
        _observability_call=observe if observe_callable is None else observe_callable,
        _observability_nonnegative_int=(
            _nonnegative if convert_callable is None else convert_callable
        ),
        run_bounded_research_agent=(
            agent if agent_callable is None else agent_callable
        ),
        run_bounded_research=(
            legacy if legacy_callable is None else legacy_callable
        ),
    )
    return SimpleNamespace(**locals())


def test_frozen_exact_two_fields_in_order():
    result = PhaseCBoundedResearchV1StageResult(object(), object())
    assert [field.name for field in fields(result)] == [
        "research", "plan_research_agent"
    ]
    with pytest.raises(FrozenInstanceError):
        result.research = None


@pytest.mark.parametrize(
    ("required", "status", "clarification", "executes"),
    [
        (True, "ok", {"required": False}, True),
        (1, "ok", {"required": 0}, True),
        (False, "ok", {"required": False}, False),
        (0, "ok", {"required": False}, False),
        (True, "error", {"required": False}, False),
        (True, "OK", {"required": False}, False),
        (True, "ok", {"required": True}, False),
        (True, "ok", {"required": 1}, False),
    ],
)
def test_exact_gate_defaults_and_at_most_one_execution(
    required, status, clarification, executes
):
    h = _run(required=required, status=status, clarification=clarification)
    chosen = [event for event in h.events if isinstance(event, tuple)
              and event[0] in {"agent", "legacy"}]
    assert len(chosen) == int(executes)
    assert h.events.count("gate") == int(executes)
    if not executes:
        assert h.result.research == {
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
def test_agent_legacy_arguments_identity_and_return_identity(gate, chosen):
    returned = {"opaque": object()}
    h = _run(gate=gate, returned=returned)
    call = next(event for event in h.events if isinstance(event, tuple)
                and event[0] == chosen)
    assert call[1] == (h.plan, h.results)
    assert call[1][0] is h.plan and call[1][1] is h.results
    assert call[2] == ({"sender": h.sender} if gate else {})
    observe = next(event for event in h.events if isinstance(event, tuple)
                   and event[0] == "observe")
    assert observe[1] is h.timings and observe[2] == "plan_research"
    assert h.result.research is returned


@pytest.mark.parametrize(
    ("agent", "expected"),
    [({}, "same"), (DictSubclass(x=1), "same"), (MappingOnly(), None),
     ([], None), (None, None), (object(), None)],
)
def test_plan_research_agent_requires_real_dict(agent, expected):
    research = {"agent": agent}
    h = _run(returned=research)
    assert h.result.plan_research_agent is (agent if expected else None)


def test_metadata_read_order_assignment_and_exact_aggregates():
    events = []
    agent = ObservedDict(
        follow_up_specialist_calls="2", total_ai_calls_used="3", events=events
    )
    research = ObservedDict(agent=agent, ai_calls_used=99, events=events)
    h = _run(returned=research, events=[])
    assert events == [
        ("get", "agent", None),
        ("get", "follow_up_specialist_calls", None),
        ("contains", "total_ai_calls_used"),
        ("get", "total_ai_calls_used", None),
    ]
    assert h.counts == {
        "initial_specialist_calls": 5,
        "phase_c_research_follow_up_specialist_calls": 7,
        "plan_research_follow_up_specialist_calls": 2,
        "research_follow_up_specialist_calls": 9,
        "total_specialist_calls": 14,
        "phase_c_ai_calls": 11,
        "plan_research_ai_calls": 3,
        "total_ai_calls": 14,
    }


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, 0), (0, 0), (-3, 0), (4, 4), ("5", 5),
     (2.9, 2), (True, 0), ("bad", 0)],
)
@pytest.mark.parametrize("nested", [False, True])
def test_all_counter_coercions_and_nested_fallbacks(value, expected, nested):
    research = (
        {"agent": {"total_ai_calls_used": value}}
        if nested else {"ai_calls_used": value}
    )
    h = _run(returned=research)
    assert h.counts["plan_research_ai_calls"] == expected


@pytest.mark.parametrize("error_type", [RuntimeError, Fatal])
@pytest.mark.parametrize(
    "where", ["gate", "research", "agent_get", "follow_get", "contains", "ai_get", "convert"]
)
def test_failures_propagate_unchanged_with_exact_partial_mutation(error_type, where):
    error = error_type(where)
    marker = object()
    metadata_events = []
    agent = ObservedDict(
        follow_up_specialist_calls=2,
        total_ai_calls_used=marker if where == "convert" else 3,
        events=metadata_events,
        error_key=(
            ("get", "follow_up_specialist_calls") if where == "follow_get"
            else ("contains", "total_ai_calls_used") if where == "contains"
            else ("get", "total_ai_calls_used") if where == "ai_get"
            else None
        ),
        error=error,
    )
    research = ObservedDict(
        agent=agent,
        error_key=("get", "agent") if where == "agent_get" else None,
        error=error,
    )
    counts, timings = _counts(), {}

    def raise_gate():
        raise error

    def raise_research(*_args, **_kwargs):
        raise error

    def convert(value):
        if value is marker:
            raise error
        return _nonnegative(value)

    with pytest.raises(error_type) as raised:
        _run(
            returned=research,
            gate_callable=raise_gate if where == "gate" else None,
            agent_callable=raise_research if where == "research" else None,
            convert_callable=convert,
            counts=counts,
            timings=timings,
        )
    assert raised.value is error
    assert timings == ({} if where == "gate" else {"plan_research": 13})
    assert counts["plan_research_follow_up_specialist_calls"] == (
        2 if where in {"contains", "ai_get", "convert"} else 0
    )
    assert counts["research_follow_up_specialist_calls"] == 0


def test_no_input_mutation_fresh_defaults_and_no_cross_call_leakage():
    first = _run(required=False)
    second = _run(required=False)
    assert first.result.research is not second.result.research
    assert first.counts is not second.counts and first.timings is not second.timings
    assert vars(first.plan) == {"research_required": False}
    assert len(first.results) == 1
    assert not [event for event in first.events if isinstance(event, tuple)
                and event[0] in {"agent", "legacy"}]


def test_leaf_imports_are_minimal_and_service_is_not_imported():
    path = Path(__file__).parents[2] / "app/orchestrator/phase_c_bounded_research_v1_stage.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {alias.name for node in tree.body if isinstance(node, ast.Import)
               for alias in node.names}
    imports |= {node.module for node in tree.body if isinstance(node, ast.ImportFrom)}
    assert imports == {"dataclasses", "typing"}
    assert "service" not in path.read_text(encoding="utf-8")
