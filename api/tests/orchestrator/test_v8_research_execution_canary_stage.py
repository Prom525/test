from dataclasses import FrozenInstanceError, fields

import pytest

from app.orchestrator.v8_research_execution_canary_stage import (
    V8ResearchExecutionCanaryStageResult,
    run_v8_research_execution_canary_stage,
)


class Fatal(BaseException):
    pass


class HostileIterable:
    def __init__(self, error): self.error = error
    def __iter__(self): raise self.error


def _run(results=(), evidence=(), helper=lambda *a, **k: None):
    values = [object() for _ in range(6)]
    return run_v8_research_execution_canary_stage(
        values[0], results, values[1], values[2], values[3], evidence, values[4],
        _run_intent_task_research_execution_canary_shadow=helper,
    )


def test_result_is_frozen_exact_three_field_contract():
    result = V8ResearchExecutionCanaryStageResult([], [], [])
    assert [field.name for field in fields(result)] == [
        "task_research_execution_canary_shadow",
        "task_research_evidence_reassessment_shadow",
        "task_grounded_synthesis_shadow",
    ]
    with pytest.raises(FrozenInstanceError):
        result.task_research_execution_canary_shadow = []


@pytest.mark.parametrize("returned", [{}, [], (), None, object()])
def test_exact_arguments_observers_and_unconverted_success(returned):
    plan, contexts, guards, sender, now = (object() for _ in range(5))
    results, evidence = [object(), object()], [object(), object()]
    before_results, before_evidence = list(results), list(evidence)
    calls = []

    def helper(*args, **kwargs):
        calls.append((args, kwargs))
        kwargs["evidence_reassessment_observer"](evidence[0])
        kwargs["grounded_synthesis_observer"](evidence[1])
        return returned

    result = run_v8_research_execution_canary_stage(
        plan, results, contexts, guards, sender, evidence, now,
        _run_intent_task_research_execution_canary_shadow=helper,
    )
    args, kwargs = calls[0]
    assert args[0] is plan and args[2] is contexts and args[3] is guards
    assert isinstance(args[1], list) and args[1] is not results
    assert all(a is b for a, b in zip(args[1], results))
    assert kwargs["sender"] is sender and kwargs["reassessment_now"] is now
    copied_evidence = kwargs["initial_evidence_items"]
    assert isinstance(copied_evidence, tuple) and copied_evidence is not evidence
    assert all(a is b for a, b in zip(copied_evidence, evidence))
    assert kwargs["evidence_reassessment_observer"].__self__ is result.task_research_evidence_reassessment_shadow
    assert kwargs["grounded_synthesis_observer"].__self__ is result.task_grounded_synthesis_shadow
    assert result.task_research_execution_canary_shadow is returned
    assert result.task_research_evidence_reassessment_shadow == [evidence[0]]
    assert result.task_grounded_synthesis_shadow == [evidence[1]]
    assert results == before_results and evidence == before_evidence


def test_each_call_has_three_fresh_distinct_defaults():
    seen = []
    def helper(*args, **kwargs):
        frame = __import__("inspect").currentframe().f_back.f_locals
        seen.append((frame["task_research_execution_canary_shadow"],
                     kwargs["evidence_reassessment_observer"].__self__,
                     kwargs["grounded_synthesis_observer"].__self__))
        return object()
    first, second = _run(helper=helper), _run(helper=helper)
    assert first.task_research_execution_canary_shadow is not second.task_research_execution_canary_shadow
    assert all(value == [] for triple in seen for value in triple)
    assert all(len({id(value) for value in triple}) == 3 for triple in seen)
    assert not ({id(value) for value in seen[0]} & {id(value) for value in seen[1]})


@pytest.mark.parametrize("where", ["results", "evidence", "helper", "observer"])
def test_ordinary_exception_resets_all_outputs_and_discards_partials(where):
    error = RuntimeError(where)
    def helper(*args, **kwargs):
        kwargs["evidence_reassessment_observer"]("partial")
        if where == "observer":
            kwargs["grounded_synthesis_observer"].__self__.append = None
        raise error
    result = _run(
        HostileIterable(error) if where == "results" else (),
        HostileIterable(error) if where == "evidence" else (),
        helper,
    )
    outputs = tuple(getattr(result, field.name) for field in fields(result))
    assert outputs == ([], [], []) and len({id(value) for value in outputs}) == 3


@pytest.mark.parametrize("where", ["results", "evidence", "helper"])
def test_baseexception_propagates(where):
    fatal = Fatal(where)
    def helper(*args, **kwargs): raise fatal
    with pytest.raises(Fatal) as raised:
        _run(HostileIterable(fatal) if where == "results" else (),
             HostileIterable(fatal) if where == "evidence" else (), helper)
    assert raised.value is fatal
