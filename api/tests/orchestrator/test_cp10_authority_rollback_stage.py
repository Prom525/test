from collections import UserDict
from dataclasses import FrozenInstanceError, fields

import pytest

from app.orchestrator.cp10_authority_rollback_stage import (
    CP10AuthorityRollbackStageResult,
    run_cp10_authority_rollback_stage,
)


class Fatal(BaseException):
    pass


class DictSubclass(dict):
    pass


class Pipeline(dict):
    def __init__(self, *args, fail_get=None, fail_set=None, error=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fail_get = fail_get
        self.fail_set = fail_set
        self.error = error
        self.events = []

    def get(self, key, *args, **kwargs):
        self.events.append(("get", key))
        if key == self.fail_get:
            raise self.error
        return super().get(key, *args, **kwargs)

    def __setitem__(self, key, value):
        self.events.append(("set", key, value))
        if len([event for event in self.events if event[0] == "set"]) == self.fail_set:
            raise self.error
        super().__setitem__(key, value)


class BrokenIterator:
    def __init__(self, error):
        self.error = error

    def __iter__(self):
        raise self.error


def invoke(pipeline, authority_return=None, authority_error=None,
           canary_return=None, canary_error=None):
    answer, legacy, authority, coverage = object(), object(), object(), object()
    calls = []
    authority_return = ((object(), object()) if authority_return is None
                        else authority_return)
    canary_return = object() if canary_return is None else canary_return

    def authority_guard(*args):
        calls.append(("authority", args))
        if authority_error is not None:
            raise authority_error
        return authority_return

    def canary_guard(*args):
        calls.append(("canary", args))
        if isinstance(pipeline, Pipeline):
            pipeline.events.append(("call", "canary", args))
        if canary_error is not None:
            raise canary_error
        return canary_return

    result = run_cp10_authority_rollback_stage(
        answer, legacy, pipeline, authority, coverage,
        guard_task_coverage_authority=authority_guard,
        guard_public_composition_canary=canary_guard,
    )
    return result, calls, (answer, legacy, authority, coverage), authority_return, canary_return


def test_frozen_result_has_exact_three_fields_in_order():
    assert [field.name for field in fields(CP10AuthorityRollbackStageResult)] == [
        "answer", "evidence_pipeline", "task_public_composition_authority_p4_6f"
    ]
    result = CP10AuthorityRollbackStageResult(1, 2, 3)
    with pytest.raises(FrozenInstanceError):
        result.answer = 4


@pytest.mark.parametrize("factory", [dict, DictSubclass])
def test_dict_typegate_runs_and_preserves_pipeline_identity(factory):
    pipeline = factory()
    result, calls, _, returned, _ = invoke(pipeline)
    assert result.evidence_pipeline is pipeline
    assert result.answer is returned[0]
    assert result.task_public_composition_authority_p4_6f is returned[1]
    assert [name for name, _ in calls] == ["authority", "canary"]


@pytest.mark.parametrize("factory", [UserDict, list, lambda: None, object])
def test_non_dict_is_complete_identity_preserving_noop(factory):
    pipeline = factory()
    result, calls, inputs, _, _ = invoke(pipeline)
    assert result.answer is inputs[0]
    assert result.evidence_pipeline is pipeline
    assert result.task_public_composition_authority_p4_6f is inputs[2]
    assert calls == []


def two_values():
    yield "generator-answer"
    yield "generator-authority"


@pytest.mark.parametrize("returned,answer,authority", [
    (("tuple-answer", "tuple-authority"), "tuple-answer", "tuple-authority"),
    (["list-answer", "list-authority"], "list-answer", "list-authority"),
    ({"dict-answer": 1, "dict-authority": 2}, "dict-answer", "dict-authority"),
    (two_values(), "generator-answer", "generator-authority"),
])
def test_exact_python_two_value_unpacking_and_guard_arguments(returned, answer, authority):
    pipeline = {}
    result, calls, inputs, _, _ = invoke(pipeline, authority_return=returned)
    assert calls[0][1] == inputs
    assert all(value is expected for value, expected in zip(calls[0][1], inputs))
    assert result.answer == answer
    assert result.task_public_composition_authority_p4_6f == authority


@pytest.mark.parametrize("returned,error", [
    ((), ValueError), ((1,), ValueError), ((1, 2, 3), ValueError),
    (object(), TypeError),
])
def test_malformed_returns_propagate(returned, error):
    with pytest.raises(error):
        invoke({}, authority_return=returned)


@pytest.mark.parametrize("error", [RuntimeError("iteration"), Fatal("iteration")])
def test_iterator_errors_propagate(error):
    with pytest.raises(type(error)) as raised:
        invoke({}, authority_return=BrokenIterator(error))
    assert raised.value is error


@pytest.mark.parametrize("where,error", [
    ("authority", RuntimeError("authority")), ("authority", Fatal("authority")),
    ("canary", RuntimeError("canary")), ("canary", Fatal("canary")),
])
def test_guard_exception_and_baseexception_propagate(where, error):
    kwargs = {f"{where}_error": error}
    with pytest.raises(type(error)) as raised:
        invoke(Pipeline(), **kwargs)
    assert raised.value is error


def test_exact_write_order_fresh_get_cp10_gate_and_prior_keys():
    old, shadow = object(), object()
    pipeline = Pipeline({"prior": old, "public_composition_canary_shadow": shadow})
    result, calls, inputs, returned, canary = invoke(pipeline)
    assert pipeline.events == [
        ("set", "task_public_composition_authority_p4_6f", returned[1]),
        ("get", "public_composition_canary_shadow"),
        ("call", "canary", (shadow, inputs[3])),
        ("set", "public_composition_canary_shadow", canary),
        ("set", "task_coverage_gate_cp10", inputs[3]),
    ]
    assert calls[1][1] == (shadow, inputs[3])
    assert pipeline["prior"] is old and result.evidence_pipeline is pipeline


@pytest.mark.parametrize("fail_set,keys,canary_count", [
    (1, [], 0),
    (2, ["task_public_composition_authority_p4_6f"], 1),
    (3, ["task_public_composition_authority_p4_6f", "public_composition_canary_shadow"], 1),
])
def test_all_setitem_failures_preserve_partial_mutations(fail_set, keys, canary_count):
    error = RuntimeError("set")
    pipeline = Pipeline(fail_set=fail_set, error=error)
    with pytest.raises(RuntimeError) as raised:
        invoke(pipeline)
    assert raised.value is error
    assert list(pipeline) == keys
    assert len([event for event in pipeline.events if event[:2] == ("call", "canary")]) == canary_count


@pytest.mark.parametrize("error", [RuntimeError("get"), Fatal("get")])
def test_get_failure_occurs_after_first_write(error):
    pipeline = Pipeline(fail_get="public_composition_canary_shadow", error=error)
    with pytest.raises(type(error)) as raised:
        invoke(pipeline)
    assert raised.value is error
    assert list(pipeline) == ["task_public_composition_authority_p4_6f"]


def test_fresh_state_has_no_cross_invocation_leakage():
    first, _, _, _, _ = invoke({})
    first.evidence_pipeline["leak"] = object()
    second, _, _, _, _ = invoke({})
    assert first is not second
    assert first.evidence_pipeline is not second.evidence_pipeline
    assert "leak" not in second.evidence_pipeline
