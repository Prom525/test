from dataclasses import FrozenInstanceError, fields
from types import SimpleNamespace

import pytest

from app.orchestrator.phase_c_bounded_research_stage import (
    PhaseCBoundedResearchStageResult,
    run_phase_c_bounded_research_stage,
)


class Fatal(BaseException):
    pass


def _run(*, execution=object(), metadata=None, counts=None,
         observe=None, get=None, integer=None, results=None):
    timings, decision, plan, sender = (object() for _ in range(4))
    counts = counts if counts is not None else {
        "phase_c_research_follow_up_specialist_calls": 7,
        "phase_c_ai_calls": 11,
    }
    results = results if results is not None else [object(), object()]
    calls = []

    def execute(*args, **kwargs):
        calls.append(("execute", args, kwargs))
        return execution

    def default_observe(*args, **kwargs):
        calls.append(("observe", args, kwargs))
        return args[2](*args[3:], **kwargs)

    def default_get(*args):
        calls.append(("get", args, {}))
        return metadata

    def default_integer(value):
        calls.append(("int", (value,), {}))
        return int(value) if value is not None else 0

    result = run_phase_c_bounded_research_stage(
        timings, counts, decision, plan, results, sender,
        _observability_call=observe or default_observe,
        _observability_get=get or default_get,
        _observability_nonnegative_int=integer or default_integer,
        execute_bounded_research=execute,
    )
    return SimpleNamespace(**locals())


def test_result_is_frozen_exact_one_field_contract():
    execution = object()
    result = PhaseCBoundedResearchStageResult(execution)
    assert [field.name for field in fields(result)] == ["research_execution"]
    assert result.research_execution is execution
    with pytest.raises(FrozenInstanceError):
        result.research_execution = None


@pytest.mark.parametrize("execution", [object(), {}, [], (), None])
def test_exact_boundary_fresh_list_sender_and_success_identity(execution):
    h = _run(execution=execution, metadata={
        "follow_up_specialist_calls": 2, "total_ai_calls_used": 3})
    assert [row[0] for row in h.calls] == ["observe", "execute", "get", "int", "int"]
    observed = h.calls[0]
    assert observed[1][:5] == (
        h.timings, "evidence_research", h.execute, h.decision, h.plan)
    copied = observed[1][5]
    assert isinstance(copied, list) and copied is not h.results
    assert all(a is b for a, b in zip(copied, h.results))
    assert observed[2] == {"sender": h.sender}
    assert h.calls[2][1] == (execution, "agent_metadata", None)
    assert h.result.research_execution is execution
    assert h.counts == {
        "phase_c_research_follow_up_specialist_calls": 9,
        "phase_c_ai_calls": 3,
    }


@pytest.mark.parametrize("metadata", [None, [], (), object()])
def test_non_dict_metadata_leaves_counts_unchanged(metadata):
    h = _run(metadata=metadata)
    assert h.counts == {
        "phase_c_research_follow_up_specialist_calls": 7,
        "phase_c_ai_calls": 11,
    }
    assert [row[0] for row in h.calls].count("get") == 1
    assert "int" not in [row[0] for row in h.calls]


def test_dict_subclass_is_processed_and_inputs_remain_caller_owned():
    metadata = type("Metadata", (dict,), {})({
        "follow_up_specialist_calls": 4, "total_ai_calls_used": 5})
    counts = {"phase_c_research_follow_up_specialist_calls": 7,
              "phase_c_ai_calls": 11, "unrelated": object()}
    before = dict(counts)
    results = [object(), object()]
    h = _run(metadata=metadata, counts=counts, results=results)
    assert counts["phase_c_research_follow_up_specialist_calls"] == 11
    assert counts["phase_c_ai_calls"] == 5
    assert counts["unrelated"] is before["unrelated"]
    assert h.results is results


def test_second_get_and_second_conversion_preserve_partial_mutation():
    class Metadata(dict):
        def get(self, key, default=None):
            if key == "total_ai_calls_used":
                raise RuntimeError("second get")
            return super().get(key, default)

    counts = {"phase_c_research_follow_up_specialist_calls": 7,
              "phase_c_ai_calls": 11}
    with pytest.raises(RuntimeError, match="second get"):
        _run(metadata=Metadata(follow_up_specialist_calls=4), counts=counts)
    assert counts == {"phase_c_research_follow_up_specialist_calls": 11,
                      "phase_c_ai_calls": 11}

    invocations = []
    counts = {"phase_c_research_follow_up_specialist_calls": 7,
              "phase_c_ai_calls": 11}

    def integer(value):
        invocations.append(value)
        if len(invocations) == 2:
            raise RuntimeError("second conversion")
        return value

    with pytest.raises(RuntimeError, match="second conversion"):
        _run(metadata={"follow_up_specialist_calls": 4,
                       "total_ai_calls_used": 5}, counts=counts, integer=integer)
    assert counts == {"phase_c_research_follow_up_specialist_calls": 11,
                      "phase_c_ai_calls": 11}


@pytest.mark.parametrize("fatal_type", [RuntimeError, Fatal])
@pytest.mark.parametrize("where", ["list", "observe", "execute", "get", "integer"])
def test_exceptions_propagate_object_identically(fatal_type, where):
    error = fatal_type(where)

    class Results:
        def __iter__(self):
            if where == "list":
                raise error
            return iter(())

    def observe(_timings, _label, callable_, *args, **kwargs):
        if where == "observe":
            raise error
        return callable_(*args, **kwargs)

    def get(*_args):
        if where == "get":
            raise error
        return {"follow_up_specialist_calls": 1, "total_ai_calls_used": 2}

    def integer(value):
        if where == "integer":
            raise error
        return value

    def execute(*_args, **_kwargs):
        if where == "execute":
            raise error
        return object()

    with pytest.raises(fatal_type) as raised:
        run_phase_c_bounded_research_stage(
            object(), {"phase_c_research_follow_up_specialist_calls": 0,
                       "phase_c_ai_calls": 0}, object(), object(), Results(), object(),
            _observability_call=observe, _observability_get=get,
            _observability_nonnegative_int=integer,
            execute_bounded_research=execute)
    assert raised.value is error


def test_real_observability_finally_records_research_timing(monkeypatch):
    from app.orchestrator import service

    timings = service._new_observability_timings()
    ticks = iter((10.0, 10.011))
    monkeypatch.setattr(service, "_observability_now", lambda: next(ticks))
    error = RuntimeError("executor")

    with pytest.raises(RuntimeError) as raised:
        run_phase_c_bounded_research_stage(
            timings, {}, object(), object(), [], object(),
            _observability_call=service._observability_call,
            _observability_get=service._observability_get,
            _observability_nonnegative_int=service._observability_nonnegative_int,
            execute_bounded_research=lambda *_a, **_k: (_ for _ in ()).throw(error))
    assert raised.value is error
    assert timings["evidence_research"] == 11
