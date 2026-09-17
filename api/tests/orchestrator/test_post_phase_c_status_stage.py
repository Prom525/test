from dataclasses import FrozenInstanceError, fields
from types import SimpleNamespace

import pytest

from app.orchestrator.post_phase_c_status_stage import (
    PostPhaseCStatusStageResult,
    run_post_phase_c_status_stage,
)


FALLBACK = "Kun je de ontbrekende context verduidelijken?"


class Fatal(BaseException):
    pass


class DictSubclass(dict):
    pass


class StrSubclass(str):
    pass


class StrValue:
    def __init__(self, value):
        self.value = value
        self.calls = 0

    def __str__(self):
        self.calls += 1
        return self.value


class RaisingStr:
    def __init__(self, error):
        self.error = error

    def __str__(self):
        raise self.error


class RaisingGet:
    def __init__(self, error):
        self.error = error

    def get(self, *_args, **_kwargs):
        raise self.error


class RaisingIterator:
    def __init__(self, error):
        self.error = error

    def __iter__(self):
        raise self.error


def _plan(*, required=False, question=None, steps=()):
    return SimpleNamespace(
        clarification_required=required,
        clarification_question=question,
        execution_steps=steps,
    )


def _run(plan=None, results=None, typed=None, helper=lambda *_args: True):
    return run_post_phase_c_status_stage(
        _plan() if plan is None else plan,
        [] if results is None else results,
        [] if typed is None else typed,
        has_service_accepted_execution_callable=helper,
    )


def test_frozen_exact_ordered_contract_and_minimal_public_surface():
    result = PostPhaseCStatusStageResult("ok", {})
    assert [field.name for field in fields(result)] == ["status", "clarification"]
    with pytest.raises(FrozenInstanceError):
        result.status = "changed"


@pytest.mark.parametrize(
    ("status", "matches"),
    [
        ("clarification_required", True),
        ("CLARIFICATION_REQUIRED", True),
        ("Clarification_Required", True),
        (" clarification_required", False),
        ("clarification_required ", False),
        (None, False),
        (7, False),
        (object(), False),
    ],
)
def test_status_uses_exact_str_lower_without_strip(status, matches):
    result = _run(results=[{"result": {"status": status, "message": "q"}}])
    assert result.status == ("clarification_required" if matches else "ok")
    assert result.clarification == (
        {"required": True, "question": "q"}
        if matches else {"required": False, "question": None}
    )


def test_status_string_conversion_once_and_scan_stops_at_first_match():
    status = StrValue("CLARIFICATION_REQUIRED")
    poison = RaisingGet(AssertionError("continued"))
    result = _run(results=[
        {"result": {"status": "ok"}},
        {"result": DictSubclass(status=status, message="first")},
        poison,
    ])
    assert result.clarification == {"required": True, "question": "first"}
    assert status.calls == 1


@pytest.mark.parametrize("nested", [None, "x", 1, object(), [1], (1,)])
def test_only_dict_nested_results_participate(nested):
    result = _run(results=[
        {"result": nested},
        {"result": DictSubclass(status="clarification_required", message="q")},
    ])
    assert result.clarification == {"required": True, "question": "q"}


@pytest.mark.parametrize("item", [None, 3, object(), RaisingGet(AttributeError("get"))])
def test_top_level_items_are_not_filtered_before_get(item):
    with pytest.raises(AttributeError) as raised:
        _run(results=[item])
    if isinstance(item, RaisingGet):
        assert raised.value is item.error


@pytest.mark.parametrize("error_type", [RuntimeError, Fatal])
@pytest.mark.parametrize("source", ["iterator", "item_get", "status_str"])
def test_scan_exception_and_baseexception_propagate_unchanged(error_type, source):
    error = error_type(source)
    if source == "iterator":
        results = RaisingIterator(error)
    elif source == "item_get":
        results = [RaisingGet(error)]
    else:
        results = [{"result": {"status": RaisingStr(error)}}]
    with pytest.raises(error_type) as raised:
        _run(results=results)
    assert raised.value is error


def test_plan_clarification_has_priority_preserves_values_and_skips_helper():
    question = object()
    calls = []
    result = _run(
        plan=_plan(required=True, question=question, steps=(object(),)),
        results=[{"result": {"status": "clarification_required", "message": "q"}}],
        helper=lambda *_args: calls.append(True),
    )
    assert result.status == "clarification_required"
    assert result.clarification == {"required": True, "question": question}
    assert calls == []


@pytest.mark.parametrize(
    ("specialist", "expected"),
    [
        ({"message": "message", "clarification": {"question": "nested"}}, "message"),
        ({"message": 9, "clarification": {"question": "nested"}}, "9"),
        ({"message": "", "clarification": {"question": "nested"}}, "nested"),
        ({"message": None, "clarification": "direct"}, "direct"),
        ({"message": None, "clarification": StrSubclass("subclass")}, "subclass"),
        ({"message": 0, "clarification": DictSubclass(question="dict")}, "dict"),
        ({"message": False, "clarification": {"question": 12}}, "12"),
        ({"message": None, "clarification": {"question": ""}}, FALLBACK),
        ({"message": None, "clarification": 42}, FALLBACK),
        ({"message": None, "clarification": object()}, FALLBACK),
    ],
)
def test_question_precedence_truthiness_fallback_and_string_conversion(
    specialist, expected
):
    result = _run(results=[{"result": dict(specialist, status="clarification_required")}])
    assert result.clarification == {"required": True, "question": expected}


@pytest.mark.parametrize("error_type", [RuntimeError, Fatal])
def test_selected_question_string_failure_propagates_unchanged(error_type):
    error = error_type("question")
    with pytest.raises(error_type) as raised:
        _run(results=[{"result": {
            "status": "clarification_required", "message": RaisingStr(error)
        }}])
    assert raised.value is error


@pytest.mark.parametrize(
    ("steps", "accepted", "expected", "calls"),
    [
        ((), False, "ok", 0),
        ([], 0, "ok", 0),
        ((object(),), False, "error", 1),
        ((object(),), None, "error", 1),
        ((object(),), 0, "error", 1),
        ((object(),), "", "error", 1),
        ((object(),), object(), "ok", 1),
        ((object(),), "accepted", "ok", 1),
    ],
)
def test_exact_steps_and_helper_truthiness_with_identity(
    steps, accepted, expected, calls
):
    seen = []
    typed, results = [object()], [{"result": {"status": "ok"}}]

    def helper(*args, **kwargs):
        seen.append((args, kwargs))
        return accepted

    result = _run(_plan(steps=steps), results, typed, helper)
    assert result.status == expected
    assert len(seen) == calls
    if seen:
        assert seen[0] == ((typed, results), {})
        assert seen[0][0][0] is typed and seen[0][0][1] is results


@pytest.mark.parametrize("error_type", [RuntimeError, Fatal])
def test_helper_exception_and_baseexception_propagate_unchanged(error_type):
    error = error_type("helper")

    def helper(*_args):
        raise error

    with pytest.raises(error_type) as raised:
        _run(plan=_plan(steps=(object(),)), helper=helper)
    assert raised.value is error


def test_each_call_returns_fresh_dict_and_does_not_mutate_inputs():
    plan = _plan()
    results = [{"result": {"status": "clarification_required", "message": "q"}}]
    typed = [object()]
    before = (dict(vars(plan)), list(results), list(typed))
    first = _run(plan, results, typed)
    first.clarification["question"] = "mutated"
    second = _run(plan, results, typed)
    assert second.clarification == {"required": True, "question": "q"}
    assert first.clarification is not second.clarification
    assert (dict(vars(plan)), results, typed) == before

