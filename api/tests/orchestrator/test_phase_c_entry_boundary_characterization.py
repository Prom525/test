"""Behavior contract for the legacy Phase-C/evidence entry boundary.

The real stored core facade is exercised.  Initial planning/execution and all
external work are replaced at their service-level lookup points.  A
BaseException sentinel observes a boundary without being confused with the
production ``except Exception`` fail-open contract.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.orchestrator import service
from app.orchestrator.models import OrchestratorAskRequest


class BoundaryObserved(BaseException):
    pass


class _FixedDateTime:
    value = datetime(2031, 2, 3, 4, 5, 6, tzinfo=timezone.utc)

    @classmethod
    def now(cls, tz):
        assert tz is timezone.utc
        return cls.value


def _install(monkeypatch, *, requirement=object(), clarification=False, results=None,
             typed=(), normalize_outputs=None, normalize_error_at=None,
             requirement_error=False, coverage_error=False):
    calls = []
    captured = {}
    plan = SimpleNamespace(
        intent="synthetic_intent",
        clarification_required=clarification,
        clarification_question="clarify" if clarification else None,
        execution_steps=(),
        research_required=False,
        requested_information=(),
        multi_intent=False,
    )
    raw_results = [] if results is None else results
    typed_results = list(typed)
    trace = {"attempts": []}
    timings = service._new_observability_timings()
    counts = service._new_observability_counts()
    inputs_before = (list(typed_results), list(raw_results), dict(trace), dict(vars(plan)))

    monkeypatch.setattr(service, "_new_observability_timings", lambda: timings)
    monkeypatch.setattr(service, "_new_observability_counts", lambda: counts)
    ticks = iter((1.0, 2.0, 2.011, 3.0, 3.017, 4.0, 4.023))
    monkeypatch.setattr(service, "_observability_now", lambda: next(ticks))
    monkeypatch.setattr(service, "datetime", _FixedDateTime)
    monkeypatch.setattr(service, "run_initial_planning_stage", lambda *a, **k: plan)

    def initial_execution(*args, **kwargs):
        calls.append(("execution", args, kwargs))
        return SimpleNamespace(
            plan=plan,
            task_execution_plans_shadow=(),
            task_execution_plan_comparison_shadow=None,
            task_execution_canary_p4_6b=None,
            typed_execution_results=typed_results,
            results=raw_results,
            trace=trace,
            task_execution_shadow=None,
            task_planner_canary=None,
        )

    monkeypatch.setattr(service, "run_initial_execution_stage", initial_execution)
    monkeypatch.setattr(service, "_record_initial_execution_observability", lambda *a: None)

    def lookup(intent):
        calls.append(("lookup", intent))
        if requirement_error:
            raise RuntimeError("lookup failure")
        return requirement

    monkeypatch.setattr(service, "get_requirement_set", lookup)
    outputs = normalize_outputs or {}

    def normalize(item, *, retrieved_at):
        calls.append(("normalize", item, retrieved_at))
        index = sum(call[0] == "normalize" for call in calls) - 1
        if normalize_error_at == index:
            raise RuntimeError("normalization failure")
        return outputs.get(item, ())

    monkeypatch.setattr(service, "normalize_execution_result_evidence", normalize)

    def coverage(requirement_set, evidence, actual_plan, *, now):
        calls.append(("coverage", requirement_set, evidence, actual_plan, now))
        if coverage_error:
            raise RuntimeError("coverage failure")
        raise BoundaryObserved("first coverage observed")

    monkeypatch.setattr(service, "assess_product_family_coverage", coverage)
    monkeypatch.setattr(service, "has_service_accepted_execution", lambda *a: True)

    def legacy_answer(*args, **kwargs):
        import inspect
        frame = inspect.currentframe().f_back
        captured.update(frame.f_locals)
        calls.append(("legacy_answer", args, kwargs))
        raise BoundaryObserved("legacy path observed")

    monkeypatch.setattr(service, "_build_user_answer", legacy_answer)
    return SimpleNamespace(
        calls=calls, captured=captured, plan=plan, results=raw_results,
        typed=typed_results, trace=trace, timings=timings, counts=counts,
        requirement=requirement, inputs_before=inputs_before,
    )


def _run(harness, match):
    payload = OrchestratorAskRequest(q="synthetic", vraag="")
    with pytest.raises(BoundaryObserved, match=match):
        service._p4_15cp3c_previous_run_orchestrator(payload, sender=object())


def test_lookup_uses_exact_observability_label_callable_and_plan_intent(monkeypatch):
    harness = _install(monkeypatch)
    observed = []
    original = service._observability_call

    def recording(timings, label, function, *args, **kwargs):
        observed.append((timings, label, function, args, kwargs))
        return original(timings, label, function, *args, **kwargs)

    monkeypatch.setattr(service, "_observability_call", recording)
    _run(harness, "first coverage")
    lookup = observed[0]
    assert lookup == (harness.timings, "evidence_requirement_lookup", service.get_requirement_set,
                      (harness.plan.intent,), {})
    assert harness.timings["evidence_requirement_lookup"] == 11


@pytest.mark.parametrize(
    ("requirement", "clarification", "results"),
    [
        (None, False, []),
        (object(), True, []),
        (object(), False, [{"result": {"status": "clarification_required"}}]),
        (object(), False, [{"result": {"status": "CLARIFICATION_REQUIRED"}}]),
        (object(), False, [{"result": {"status": "Clarification_Required"}}]),
    ],
)
def test_gate_skip_cases_reach_legacy_with_exact_defaults(
    monkeypatch, requirement, clarification, results
):
    harness = _install(monkeypatch, requirement=requirement,
                       clarification=clarification, results=results)
    _run(harness, "legacy path")
    assert [call[0] for call in harness.calls].count("lookup") == 1
    assert not any(call[0] in {"normalize", "coverage"} for call in harness.calls)
    assert harness.captured["evidence_pipeline"] is None
    assert harness.captured["task_research_semantics_cp13"] is None
    assert harness.captured["initial_evidence_items"] == ()
    assert harness.captured["research_execution"] is None
    assert harness.captured["reconciliation"] is None
    assert harness.timings["evidence_normalization"] == 0
    assert harness.counts["initial_evidence_items"] == 0


@pytest.mark.parametrize(
    "results",
    [
        ["malformed-top-level"],
        [{"result": "not-a-dict"}],
        [{"result": None}],
        [{"result": {"status": " clarification_required"}}],
        [{"result": {"status": "clarification_required "}}],
    ],
)
def test_malformed_shapes_and_whitespace_do_not_block_entry(monkeypatch, results):
    harness = _install(monkeypatch, results=results)
    _run(harness, "first coverage")
    assert [call[0] for call in harness.calls] == ["execution", "lookup", "coverage"]


@pytest.mark.parametrize(
    ("outputs", "expected"),
    [
        ({"typed-a": (), "typed-b": ()}, ()),
        ({"typed-a": ("a1", "a2"), "typed-b": ("b1",)}, ("a1", "a2", "b1")),
    ],
)
def test_normalization_flattens_only_ordered_typed_results_and_reuses_timestamp(
    monkeypatch, outputs, expected
):
    raw = [{"result": {"status": "ok"}, "private": object()}]
    harness = _install(monkeypatch, results=raw, typed=("typed-a", "typed-b"),
                       normalize_outputs=outputs)
    _run(harness, "first coverage")
    normalizes = [call for call in harness.calls if call[0] == "normalize"]
    assert [call[1] for call in normalizes] == ["typed-a", "typed-b"]
    assert all(call[1] is not raw[0] for call in normalizes)
    coverage = next(call for call in harness.calls if call[0] == "coverage")
    assert coverage[2] == expected and isinstance(coverage[2], tuple)
    assert coverage[1] is harness.requirement and coverage[3] is harness.plan
    assert all(call[2] is _FixedDateTime.value for call in normalizes)
    assert coverage[4] is _FixedDateTime.value
    assert harness.timings["evidence_normalization"] == 17
    assert harness.counts["initial_evidence_items"] == len(expected)


@pytest.mark.parametrize("error_at", [0, 1])
def test_normalization_exception_finally_records_but_tuple_assignment_stays_empty(
    monkeypatch, error_at
):
    outputs = {"typed-a": ("a1", "a2"), "typed-b": ("b1",)}
    harness = _install(monkeypatch, typed=("typed-a", "typed-b"),
                       normalize_outputs=outputs, normalize_error_at=error_at)
    _run(harness, "legacy path")
    assert len([c for c in harness.calls if c[0] == "normalize"]) == error_at + 1
    assert not any(c[0] == "coverage" for c in harness.calls)
    assert harness.captured["initial_evidence_items"] == ()
    assert harness.captured["evidence_pipeline"] is None
    assert harness.timings["evidence_normalization"] == 17
    assert harness.counts["initial_evidence_items"] == 0


@pytest.mark.parametrize("failure", ["lookup", "normalization", "coverage"])
def test_phase_c_failures_are_swallowed_once_and_preserve_inputs(monkeypatch, failure):
    kwargs = {
        "requirement_error": failure == "lookup",
        "normalize_error_at": 0 if failure == "normalization" else None,
        "coverage_error": failure == "coverage",
    }
    harness = _install(monkeypatch, typed=("typed-a",),
                       normalize_outputs={"typed-a": ("evidence",)}, **kwargs)
    _run(harness, "legacy path")
    names = [call[0] for call in harness.calls]
    assert names.count("execution") == 1
    assert names.count("lookup") == 1
    assert names.count("coverage") == (1 if failure == "coverage" else 0)
    assert names[-1] == "legacy_answer"
    assert harness.captured["evidence_pipeline"] is None
    assert harness.captured["task_research_semantics_cp13"] is None
    assert harness.captured["research_execution"] is None
    assert harness.captured["reconciliation"] is None
    assert harness.inputs_before == (
        harness.typed, harness.results, harness.trace, vars(harness.plan)
    )
    if failure == "lookup":
        assert harness.timings["evidence_requirement_lookup"] == 11
        assert harness.timings["evidence_normalization"] == 0
        assert harness.counts["initial_evidence_items"] == 0
        assert harness.captured["initial_evidence_items"] == ()
    elif failure == "normalization":
        assert harness.timings["evidence_requirement_lookup"] == 11
        assert harness.timings["evidence_normalization"] == 17
        assert harness.counts["initial_evidence_items"] == 0
        assert harness.captured["initial_evidence_items"] == ()
    else:
        assert harness.timings["evidence_requirement_lookup"] == 11
        assert harness.timings["evidence_normalization"] == 17
        assert harness.counts["initial_evidence_items"] == 1
        assert harness.captured["initial_evidence_items"] == ("evidence",)
