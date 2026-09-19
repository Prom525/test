from dataclasses import FrozenInstanceError, fields

import pytest

from app.orchestrator.cp15_release_observer_stage import (
    CP15ReleaseObserverStageResult, run_cp15_release_observer_stage,
)


class Fatal(BaseException):
    pass


class Probe(dict):
    def __init__(self, initial=(), *, failures=()):
        super().__init__(initial)
        self.failures = iter(failures)
        self.attempts = []

    def __setitem__(self, key, value):
        if key == "release_gate_cp15":
            self.attempts.append(value)
            failure = next(self.failures, None)
            if failure is not None:
                raise failure
        super().__setitem__(key, value)


def run(pipeline, builder, shadow=None):
    return run_cp15_release_observer_stage(
        shadow, pipeline, build_release_gate_cp15=builder)


def test_frozen_exact_one_field_contract():
    result = CP15ReleaseObserverStageResult({})
    assert [field.name for field in fields(result)] == ["evidence_pipeline"]
    with pytest.raises(FrozenInstanceError):
        result.evidence_pipeline = None


@pytest.mark.parametrize("returned", [{"x": 1}, [1], (1,), None, object()])
def test_exact_args_raw_return_write_and_pipeline_identity(returned):
    shadow, preserved, calls = object(), object(), []
    pipeline = Probe({"preserved": preserved})
    def builder(*args, **kwargs):
        calls.append((args, kwargs))
        return returned
    result = run(pipeline, builder, shadow)
    assert calls == [((shadow, pipeline), {})]
    assert pipeline["release_gate_cp15"] is returned
    assert pipeline["preserved"] is preserved
    assert result.evidence_pipeline is pipeline


@pytest.mark.parametrize("error", [RuntimeError("a"), ValueError("b")])
def test_builder_exception_exact_fresh_fallback(error):
    pipeline = Probe()
    result = run(pipeline, lambda *_: (_ for _ in ()).throw(error))
    fallback = pipeline["release_gate_cp15"]
    assert fallback == {
        "contract_version": "promati.orchestrator.release_gate.cp15.v1",
        "evaluated": False, "release_allowed": False,
        "public_authoritative": False,
        "blocking_reasons": ["cp15_internal_error_fail_closed"],
        "blocked_gate_ids": ["cp15"],
        "internal_error_type": type(error).__name__,
    }
    assert set(fallback) == {"contract_version", "evaluated", "release_allowed",
                             "public_authoritative", "blocking_reasons",
                             "blocked_gate_ids", "internal_error_type"}
    assert fallback["blocking_reasons"] is not fallback["blocked_gate_ids"]
    assert result.evidence_pipeline is pipeline


def test_fallback_state_and_lists_are_fresh():
    first, second = Probe(), Probe()
    for pipeline in (first, second):
        run(pipeline, lambda *_: (_ for _ in ()).throw(RuntimeError()))
    one, two = first["release_gate_cp15"], second["release_gate_cp15"]
    assert one is not two
    assert one["blocking_reasons"] is not two["blocking_reasons"]
    assert one["blocked_gate_ids"] is not two["blocked_gate_ids"]


def test_builder_baseexception_propagates_without_write():
    fatal, pipeline = Fatal("builder"), Probe()
    with pytest.raises(Fatal) as raised:
        run(pipeline, lambda *_: (_ for _ in ()).throw(fatal))
    assert raised.value is fatal and pipeline.attempts == []


def test_first_write_exception_falls_back_preserving_state_and_order():
    pipeline = Probe({"kept": object()}, failures=[RuntimeError("first")])
    returned = object()
    result = run(pipeline, lambda *_: returned)
    assert pipeline.attempts[0] is returned
    assert pipeline.attempts[1] is pipeline["release_gate_cp15"]
    assert pipeline.attempts[1]["internal_error_type"] == "RuntimeError"
    assert len(pipeline.attempts) == 2 and "kept" in pipeline
    assert result.evidence_pipeline is pipeline


def test_first_write_baseexception_propagates_without_fallback():
    fatal, returned = Fatal("write"), object()
    pipeline = Probe(failures=[fatal])
    with pytest.raises(Fatal) as raised:
        run(pipeline, lambda *_: returned)
    assert raised.value is fatal and pipeline.attempts == [returned]


@pytest.mark.parametrize("second", [RuntimeError("fallback"), Fatal("fallback")])
def test_failing_fallback_write_propagates_without_retry(second):
    returned = object()
    pipeline = Probe(failures=[RuntimeError("first"), second])
    with pytest.raises(type(second)) as raised:
        run(pipeline, lambda *_: returned)
    assert raised.value is second
    assert pipeline.attempts[0] is returned
    assert pipeline.attempts[1]["internal_error_type"] == "RuntimeError"
    assert len(pipeline.attempts) == 2 and "release_gate_cp15" not in pipeline
