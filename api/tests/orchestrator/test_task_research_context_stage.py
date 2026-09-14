from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError, fields

import pytest

from app.orchestrator.task_research_context_stage import (
    TaskResearchContextStageResult,
    run_task_research_context_stage,
)


class OrdinaryError(Exception):
    pass


class FatalError(BaseException):
    pass


class Results:
    def __init__(self, values=(), error=None):
        self.values = values
        self.error = error
        self.iterations = 0

    def __iter__(self):
        self.iterations += 1
        if self.error is not None:
            raise self.error
        return iter(self.values)


def _run(*, results=None, context_return=(), guard_return=(), context_error=None,
         guard_error=None, calls=None, plan=None, decisions=None):
    calls = [] if calls is None else calls
    results = Results([object(), object()]) if results is None else results
    plan = object() if plan is None else plan
    decisions = object() if decisions is None else decisions

    def context(actual_plan, actual_results, actual_decisions):
        calls.append(("context", actual_plan, actual_results, actual_decisions))
        if context_error is not None:
            raise context_error
        return context_return

    def guard(actual_contexts):
        calls.append(("guard", actual_contexts))
        if guard_error is not None:
            raise guard_error
        return guard_return

    result = run_task_research_context_stage(
        plan, results, decisions,
        derive_intent_task_research_contexts_shadow=context,
        derive_intent_task_research_call_guards_shadow=guard,
    )
    return result, calls, plan, results, decisions


def test_frozen_exact_two_field_return_contract():
    result, *_ = _run()
    assert [field.name for field in fields(result)] == [
        "task_research_contexts_shadow", "task_research_call_guards_shadow"
    ]
    with pytest.raises(FrozenInstanceError):
        result.task_research_contexts_shadow = object()


@pytest.mark.parametrize("value", [[], (), {"shape": "mapping"}, None, object()])
def test_context_success_preserves_identity_and_guard_gets_exact_object(value):
    result, calls, *_ = _run(context_return=value)
    assert result.task_research_contexts_shadow is value
    assert calls[1] == ("guard", value)


@pytest.mark.parametrize("value", [[], (), {"shape": "mapping"}, None, object()])
def test_guard_success_preserves_identity(value):
    result, *_ = _run(context_return=object(), guard_return=value)
    assert result.task_research_call_guards_shadow is value


def test_results_are_listed_once_in_order_with_element_identity_and_exact_arguments():
    values = [object(), object()]
    source = Results(values)
    result, calls, plan, _, decisions = _run(results=source, context_return=object())
    assert [call[0] for call in calls] == ["context", "guard"]
    assert source.iterations == 1
    assert calls[0][1] is plan and calls[0][2] is not source
    assert all(a is b for a, b in zip(calls[0][2], values))
    assert calls[0][3] is decisions
    assert calls[1][1] is result.task_research_contexts_shadow


@pytest.mark.parametrize("source", ["list", "context"])
def test_context_zone_exception_uses_fresh_list_and_guard_still_runs(source):
    kwargs = ({"results": Results(error=OrdinaryError("list"))} if source == "list"
              else {"context_error": OrdinaryError("context")})
    first, first_calls, *_ = _run(**kwargs)
    second, second_calls, *_ = _run(**kwargs)
    assert first.task_research_contexts_shadow == []
    assert first.task_research_contexts_shadow is not second.task_research_contexts_shadow
    assert first_calls[-1] == ("guard", first.task_research_contexts_shadow)
    assert second_calls[-1] == ("guard", second.task_research_contexts_shadow)
    assert [c[0] for c in first_calls].count("context") == (source == "context")


def test_guard_exception_uses_fresh_list_and_preserves_context():
    context = object()
    first, *_ = _run(context_return=context, guard_error=OrdinaryError("guard"))
    second, *_ = _run(context_return=context, guard_error=OrdinaryError("guard"))
    assert first.task_research_contexts_shadow is context
    assert first.task_research_call_guards_shadow == []
    assert first.task_research_call_guards_shadow is not second.task_research_call_guards_shadow


def test_combined_ordinary_errors_fail_open_independently():
    result, calls, *_ = _run(context_error=OrdinaryError("context"),
                             guard_error=OrdinaryError("guard"))
    assert result.task_research_contexts_shadow == []
    assert result.task_research_call_guards_shadow == []
    assert result.task_research_contexts_shadow is not result.task_research_call_guards_shadow
    assert calls[1][1] is result.task_research_contexts_shadow


@pytest.mark.parametrize("source", ["list", "context", "guard"])
def test_baseexception_propagates(source):
    kwargs = {
        "results": Results(error=FatalError(source)) if source == "list" else None,
        "context_error": FatalError(source) if source == "context" else None,
        "guard_error": FatalError(source) if source == "guard" else None,
    }
    with pytest.raises(FatalError, match=source):
        _run(**kwargs)


def test_no_input_mutation_and_exact_cardinality():
    plan = {"plan": [[1]]}
    decisions = {"decisions": [[2]]}
    values = [{"result": [3]}]
    before = deepcopy((plan, decisions, values))
    result, calls, *_ = _run(plan=plan, decisions=decisions, results=Results(values),
                             context_return=object(), guard_return=object())
    assert (plan, decisions, values) == before
    assert [call[0] for call in calls] == ["context", "guard"]
    assert isinstance(result, TaskResearchContextStageResult)
