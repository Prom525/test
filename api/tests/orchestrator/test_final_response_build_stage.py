from dataclasses import FrozenInstanceError, fields
from types import SimpleNamespace

import pytest

from app.orchestrator.final_response_build_stage import (
    FinalResponseBuildStageResult,
    run_final_response_build_stage,
)


class Fatal(BaseException):
    pass


class Probe:
    def __init__(self, value, events, label):
        self.value = value
        self.events = events
        self.label = label
        self.calls = 0

    def __bool__(self):
        self.calls += 1
        self.events.append(self.label)
        return self.value


class Payload:
    def __init__(self, value, events):
        self.value = value
        self.events = events
        self.calls = 0

    @property
    def include_trace(self):
        self.calls += 1
        self.events.append("include_trace")
        return self.value


def invoke(*, include=False, debug=False, pipeline=None, timings=None,
           compact_evidence=None, compact_results=None, model=None,
           now=None, elapsed=None, plan=None):
    events = []
    payload = Payload(include, events)
    pipeline = {} if pipeline is None else pipeline
    timings = {"response_build": 0} if timings is None else timings
    plan = SimpleNamespace(requested_information="requested") if plan is None else plan
    compact_evidence = compact_evidence or (lambda value: (events.append("evidence"), "public-evidence")[1])
    compact_results = compact_results or (
        lambda value, *, requested_information: (
            events.append(("results", requested_information)), "public-results"
        )[1]
    )
    model = model or (lambda value: (events.append(("model", value)), {"model": value})[1])
    now = now or (lambda: (events.append("clock"), "started")[1])
    elapsed = elapsed or (lambda started: (events.append(("elapsed", started)), 12.5)[1])
    values = [payload, debug, pipeline, "gate", ["raw-result"], plan, "ok",
              "answer", "question", "research", "clarification", "shadow",
              "canary", {"trace": 1}, timings]
    dependencies = dict(
        observability_now=now,
        compact_evidence_pipeline_for_public_response=compact_evidence,
        compact_results_for_public_response=compact_results,
        model_to_dict=model,
        observability_elapsed_ms=elapsed,
    )
    return values, dependencies, events


def test_frozen_exact_one_field_contract():
    assert [field.name for field in fields(FinalResponseBuildStageResult)] == ["response"]
    result = FinalResponseBuildStageResult(response={})
    with pytest.raises(FrozenInstanceError):
        result.response = None


def test_exact_response_order_values_identity_freshness_and_timing_side_effect():
    values, dependencies, events = invoke()
    first = run_final_response_build_stage(*values, **dependencies)
    second = run_final_response_build_stage(*values, **dependencies)
    assert first.response is not second.response
    assert list(first.response) == [
        "status", "answer", "context_type", "question", "query_plan", "research",
        "clarification", "results", "evidence_pipeline", "task_execution_shadow",
        "task_planner_canary", "trace",
    ]
    assert first.response["status"] is values[6]
    assert first.response["answer"] is values[7]
    assert first.response["results"] == "public-results"
    assert first.response["evidence_pipeline"] == "public-evidence"
    assert first.response["trace"] is None
    assert values[14]["response_build"] == 12.5
    assert events[:4] == ["clock", "include_trace", "evidence", "include_trace"]


def test_trace_short_circuits_compactors_and_serializes_plan_then_trace():
    values, dependencies, events = invoke(include=True)
    result = run_final_response_build_stage(*values, **dependencies)
    assert result.response["results"] is values[4]
    assert result.response["evidence_pipeline"] is values[2]
    assert [event for event in events if isinstance(event, tuple) and event[0] == "model"] == [
        ("model", values[5]), ("model", values[13])]
    assert values[0].calls == 3


@pytest.mark.parametrize("pipeline", [[], object()])
def test_truthy_debug_replaces_only_local_non_dict_pipeline(pipeline):
    values, dependencies, _ = invoke(debug=True, pipeline=pipeline)
    result = run_final_response_build_stage(*values, **dependencies)
    replacement = result.response["evidence_pipeline"]
    assert replacement == {"task_coverage_gate_cp10": values[3]}
    assert values[2] is pipeline


def test_debug_truthiness_is_evaluated_twice_and_dict_identity_is_preserved():
    events = []
    debug = Probe(True, events, "debug")
    pipeline = {"raw": 1}
    values, dependencies, _ = invoke(debug=debug, pipeline=pipeline)
    result = run_final_response_build_stage(*values, **dependencies)
    assert result.response["evidence_pipeline"] is pipeline
    assert debug.calls == 2


def test_requested_information_is_lazy_and_precedes_results_helper():
    events = []
    class Plan:
        @property
        def requested_information(self):
            events.append("requested")
            return "value"
    def compact(value, *, requested_information):
        events.append(("compact", requested_information))
        return value
    values, dependencies, _ = invoke(plan=Plan(), compact_results=compact)
    run_final_response_build_stage(*values, **dependencies)
    assert events == ["requested", ("compact", "value")]


@pytest.mark.parametrize("error", [RuntimeError("clock"), Fatal("clock")])
def test_clock_error_is_before_try_and_does_not_run_elapsed(error):
    called = []
    values, dependencies, _ = invoke(
        now=lambda: (_ for _ in ()).throw(error),
        elapsed=lambda value: called.append(value),
    )
    with pytest.raises(type(error)) as raised:
        run_final_response_build_stage(*values, **dependencies)
    assert raised.value is error and called == []


@pytest.mark.parametrize("error", [RuntimeError("try"), Fatal("try")])
def test_try_error_runs_finally_and_preserves_partial_timing(error):
    values, dependencies, events = invoke(
        compact_evidence=lambda value: (_ for _ in ()).throw(error)
    )
    with pytest.raises(type(error)) as raised:
        run_final_response_build_stage(*values, **dependencies)
    assert raised.value is error
    assert values[14]["response_build"] == 12.5
    assert events[-1] == ("elapsed", "started")


@pytest.mark.parametrize("original", [RuntimeError("try"), Fatal("try")])
def test_elapsed_error_replaces_try_error(original):
    replacement = ValueError("elapsed")
    def fail_compact(value):
        raise original
    def fail_elapsed(value):
        raise replacement
    values, dependencies, _ = invoke(
        compact_evidence=fail_compact,
        elapsed=fail_elapsed,
    )
    with pytest.raises(ValueError) as raised:
        run_final_response_build_stage(*values, **dependencies)
    assert raised.value is replacement
    assert raised.value.__context__ is original
    assert values[14]["response_build"] == 0


def test_trace_serialization_failure_leaves_complete_base_response_in_frame():
    error = RuntimeError("trace")
    values, dependencies, _ = invoke(include=True)
    dependencies["model_to_dict"] = (
        lambda value: (_ for _ in ()).throw(error) if value is values[13] else {"plan": 1}
    )
    with pytest.raises(RuntimeError) as raised:
        run_final_response_build_stage(*values, **dependencies)
    frame = raised.value.__traceback__.tb_next.tb_frame.f_locals
    assert list(frame["response"])[-1] == "task_planner_canary"
    assert "trace" not in frame["response"]
