from dataclasses import FrozenInstanceError, fields

import pytest

from app.orchestrator.p4_6d2_research_execution_stage import (
    P46d2ResearchExecutionStageResult,
    run_p4_6d2_research_execution_stage,
)


class Fatal(BaseException):
    pass


class ExplodingResults:
    def __init__(self, error):
        self.error = error

    def __iter__(self):
        raise self.error


def _run(results, runner, *, inputs=None):
    values = inputs or tuple(object() for _ in range(6))
    plan, authority, contexts, guards, sender, semantics = values
    return run_p4_6d2_research_execution_stage(
        plan, results, authority, contexts, guards, sender, semantics,
        run_task_research_execution_authority_canary_p4_6d2=runner,
    )


def test_result_is_frozen_exact_two_field_contract():
    result = P46d2ResearchExecutionStageResult(object(), [])
    assert [field.name for field in fields(result)] == [
        "task_research_execution_authority_p4_6d2",
        "task_research_execution_observations_p4_6d2",
    ]
    with pytest.raises(FrozenInstanceError):
        result.task_research_execution_authority_p4_6d2 = None


@pytest.mark.parametrize("returned", [[], (), {"shape": "mapping"}, None, object()])
@pytest.mark.parametrize("count", [0, 1, 3])
def test_success_preserves_identity_observations_and_exact_call(returned, count):
    calls = []
    inputs = tuple(object() for _ in range(6))
    source = [object(), object()]
    observations = [object() for _ in range(count)]

    def runner(*args, **kwargs):
        calls.append((args, kwargs))
        for observation in observations:
            kwargs["evidence_observer"](observation)
        return returned

    result = _run(source, runner, inputs=inputs)
    assert result.task_research_execution_authority_p4_6d2 is returned
    observed = result.task_research_execution_observations_p4_6d2
    assert len(calls) == 1 and observed == observations
    assert all(a is b for a, b in zip(observed, observations))
    args, kwargs = calls[0]
    assert args[0] is inputs[0]
    assert args[1] is not source and all(a is b for a, b in zip(args[1], source))
    assert args[2:5] == inputs[1:4]
    assert kwargs["sender"] is inputs[4]
    assert kwargs["evidence_observer"].__self__ is observed
    assert kwargs["task_research_semantics_cp13"] is inputs[5]


def test_observations_are_fresh_and_inputs_are_not_mutated():
    inputs = tuple(object() for _ in range(6))
    source = [object()]
    first = _run(source, lambda *a, **k: object(), inputs=inputs)
    second = _run(source, lambda *a, **k: object(), inputs=inputs)
    assert first.task_research_execution_observations_p4_6d2 == []
    assert first.task_research_execution_observations_p4_6d2 is not second.task_research_execution_observations_p4_6d2
    assert source == [source[0]] and inputs == inputs


def test_list_exception_skips_runner_and_returns_fresh_empty_fallbacks():
    calls = []
    runner = lambda *a, **k: calls.append((a, k))
    first = _run(ExplodingResults(RuntimeError("list")), runner)
    second = _run(ExplodingResults(RuntimeError("list")), runner)
    assert calls == []
    assert first.task_research_execution_authority_p4_6d2 is None
    assert first.task_research_execution_observations_p4_6d2 == []
    assert first.task_research_execution_observations_p4_6d2 is not second.task_research_execution_observations_p4_6d2


@pytest.mark.parametrize("count", [0, 1, 3])
def test_runner_exception_discards_partial_observation_list(count):
    partial = []

    def runner(*args, **kwargs):
        partial.append(kwargs["evidence_observer"].__self__)
        for _ in range(count):
            kwargs["evidence_observer"](object())
        raise RuntimeError("runner")

    result = _run([], runner)
    assert result.task_research_execution_authority_p4_6d2 is None
    assert result.task_research_execution_observations_p4_6d2 == []
    assert result.task_research_execution_observations_p4_6d2 is not partial[0]
    assert len(partial[0]) == count


@pytest.mark.parametrize("source", ["list", "runner"])
def test_baseexception_propagates(source):
    fatal = Fatal("fatal")
    results = ExplodingResults(fatal) if source == "list" else []

    def runner(*args, **kwargs):
        raise fatal

    with pytest.raises(Fatal) as raised:
        _run(results, runner)
    assert raised.value is fatal
