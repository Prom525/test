"""Characterize the Phase-C synthesis boundary immediately after 3S2."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.orchestrator import service
from app.orchestrator.phase_c_entry_stage import PhaseCEntryResult
from app.orchestrator.phase_c_reconciliation_stage import (
    PhaseCReconciliationStageResult,
)


class StopAtPipelineAssembly(BaseException):
    pass


class Fatal(BaseException):
    pass


def _prior_characterization():
    path = Path(__file__).with_name(
        "test_phase_c_reconciliation_metrics_boundary_characterization.py"
    )
    spec = importlib.util.spec_from_file_location("phase_c_3s1_for_3t1", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _install(monkeypatch, *, synthesis=object(), reconciliation=object(),
             timing_start=313):
    prior = _prior_characterization()
    base = prior._install(
        monkeypatch,
        reconciliation=object(),
        timing_start=timing_start,
    )
    calls = []
    base.base.h.timings["synthesis"] = timing_start
    requirement_set = SimpleNamespace(requirement_set_id="semantic-requirement-set")

    monkeypatch.setattr(
        service,
        "prepare_phase_c_entry",
        lambda *_args, **_kwargs: PhaseCEntryResult(
            requirement_set,
            base.base.h.retrieved_at,
            (),
            base.base.h.working_evidence_items,
        ),
    )

    def reconciliation_stage(*args, **kwargs):
        calls.append(("3s2", args, kwargs))
        return PhaseCReconciliationStageResult(reconciliation)

    def synthesize(*args, **kwargs):
        calls.append(("synthesis_callable", args, kwargs))
        return synthesis

    def pipeline(*args, **kwargs):
        calls.append(("pipeline", args, kwargs))
        raise StopAtPipelineAssembly("controlled following boundary")

    monkeypatch.setattr(service, "run_phase_c_reconciliation_stage",
                        reconciliation_stage)
    monkeypatch.setattr(service, "synthesize_grounded_evidence", synthesize)
    monkeypatch.setattr(service, "_evidence_pipeline_to_dict", pipeline)
    before = (
        dict(vars(base.base.h.plan)),
        list(base.base.h.results),
        list(base.base.h.typed_results),
        dict(base.base.h.trace),
        tuple(base.base.h.working_evidence_items),
    )
    before_assessment = base.initial_assessment
    before_research_execution = base.research_execution
    before_reconciliation = reconciliation
    before_retrieved_at = base.base.h.retrieved_at
    return SimpleNamespace(**locals())


def _run(harness, exception=StopAtPipelineAssembly):
    return harness.prior._run(harness.base, exception)


@pytest.mark.parametrize("synthesis", [
    {"value": object()}, [object()], (object(),), None, object(),
])
def test_order_cardinality_runtime_callables_identities_and_raw_return(
        monkeypatch, synthesis):
    reconciliation = object()
    h = _install(
        monkeypatch, synthesis=synthesis, reconciliation=reconciliation)
    observed = []
    original = service._observability_call

    def observability(timings, label, callable_, *args, **kwargs):
        if label == "synthesis":
            observed.append((timings, label, callable_, args, kwargs))
        return original(timings, label, callable_, *args, **kwargs)

    monkeypatch.setattr(service, "_observability_call", observability)
    raised = _run(h)

    assert isinstance(raised, StopAtPipelineAssembly)
    assert [row[0] for row in h.calls] == [
        "3s2", "synthesis_callable", "pipeline"
    ]
    assert all(
        [row[0] for row in h.calls].count(name) == 1
        for name in ("3s2", "synthesis_callable", "pipeline")
    )
    assert len(observed) == 1
    timings, label, callable_, args, kwargs = observed[0]
    assert timings is h.base.base.h.timings
    assert label == "synthesis"
    assert callable_ is service.synthesize_grounded_evidence
    assert args == (reconciliation,)
    assert args[0] is reconciliation
    assert kwargs == {}
    pipeline_mapping = h.calls[-1][1][0]
    assert pipeline_mapping["synthesis"] is synthesis
    assert h.calls[-1][2] == {}


def test_3s2_runtime_binding_and_no_duplicate_upstream_or_synthesis(monkeypatch):
    h = _install(monkeypatch)
    _run(h)

    stage = h.calls[0]
    assert stage[1] == (
        h.base.base.h.timings,
        h.base.base.h.counts,
        h.requirement_set,
        h.base.base.h.working_evidence_items,
        h.base.initial_assessment,
        h.base.research_execution,
        h.base.base.h.retrieved_at,
    )
    assert stage[2] == {
        "observability_call": service._observability_call,
        "observability_get": service._observability_get,
        "reconcile_evidence_callable": service.reconcile_evidence,
    }
    upstream_names = [row[0] for row in h.base.base.h.calls]
    assert upstream_names.count("planning") == 1
    assert upstream_names.count("execution") == 1
    assert len([
        row for row in h.base.boundary_calls if row[0] == "bounded_stage"
    ]) == 1
    assert not [
        row for row in h.base.boundary_calls
        if row[0] in {"reconcile", "get"}
    ]
    assert [row[0] for row in h.calls].count("3s2") == 1
    assert [row[0] for row in h.calls].count("synthesis_callable") == 1


@pytest.mark.parametrize("where", ["wrapper", "synthesizer"])
def test_ordinary_synthesis_failure_uses_outer_fail_open_exact_timing_and_no_pipeline(
        monkeypatch, where):
    h = _install(monkeypatch, timing_start=313)
    error = RuntimeError(where)
    original = service._observability_call

    if where == "wrapper":
        def observability(timings, label, callable_, *args, **kwargs):
            if label == "synthesis":
                raise error
            return original(timings, label, callable_, *args, **kwargs)

        monkeypatch.setattr(service, "_observability_call", observability)
    else:
        def fail(*args, **kwargs):
            h.calls.append(("synthesis_callable", args, kwargs))
            raise error

        monkeypatch.setattr(service, "synthesize_grounded_evidence", fail)
        monkeypatch.setattr(service, "_observability_elapsed_ms",
                            lambda _started: 71)

    _run(h, h.base.base.characterized.StopOnLegacyPath)
    assert not [row for row in h.calls if row[0] == "pipeline"]
    assert h.base.base.h.timings["synthesis"] == (
        313 if where == "wrapper" else 71
    )
    assert [row[0] for row in h.calls].count("synthesis_callable") == (
        0 if where == "wrapper" else 1
    )
    assert [row[0] for row in h.base.base.h.calls].count("legacy_path") == 1


@pytest.mark.parametrize("where", ["wrapper", "synthesizer", "pipeline"])
def test_baseexception_propagates_identically(monkeypatch, where):
    h = _install(monkeypatch, timing_start=401)
    error = Fatal(where)
    original = service._observability_call

    if where == "wrapper":
        def observability(timings, label, callable_, *args, **kwargs):
            if label == "synthesis":
                raise error
            return original(timings, label, callable_, *args, **kwargs)

        monkeypatch.setattr(service, "_observability_call", observability)
    elif where == "synthesizer":
        monkeypatch.setattr(
            service, "synthesize_grounded_evidence",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(error),
        )
    else:
        monkeypatch.setattr(
            service, "_evidence_pipeline_to_dict",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(error),
        )

    raised = _run(h, Fatal)
    assert raised is error
    assert "legacy_path" not in [row[0] for row in h.base.base.h.calls]
    assert not [row for row in h.calls if row[0] == "pipeline"] or where == "pipeline"
    if where == "wrapper":
        assert h.base.base.h.timings["synthesis"] == 401
    elif where == "synthesizer":
        assert h.base.base.h.timings["synthesis"] != 401
        assert h.base.base.h.timings["synthesis"] >= 0


def test_ordinary_pipeline_failure_is_only_next_boundary_and_does_not_repeat_synthesis(
        monkeypatch):
    synthesis = object()
    h = _install(monkeypatch, synthesis=synthesis)
    pipeline_error = RuntimeError("pipeline")
    pipeline_calls = []

    def fail(mapping):
        pipeline_calls.append(mapping)
        raise pipeline_error

    monkeypatch.setattr(service, "_evidence_pipeline_to_dict", fail)
    _run(h, h.base.base.characterized.StopOnLegacyPath)
    assert len(pipeline_calls) == 1
    assert pipeline_calls[0]["synthesis"] is synthesis
    assert [row[0] for row in h.calls].count("synthesis_callable") == 1
    assert [row[0] for row in h.base.base.h.calls].count("legacy_path") == 1


def test_fresh_timings_do_not_leak_between_runs(monkeypatch):
    with monkeypatch.context() as first_patch:
        first = _install(first_patch, timing_start=501)
        _run(first)
        first_timings = first.base.base.h.timings

    with monkeypatch.context() as second_patch:
        second = _install(second_patch, timing_start=601)
        _run(second)
        assert second.base.base.h.timings is not first_timings
        assert second.base.base.h.timings["synthesis"] != 601
        assert first_timings["synthesis"] != 501


def test_no_input_mutation_across_synthesis_and_pipeline_stop(monkeypatch):
    h = _install(monkeypatch)
    _run(h)
    after = (
        dict(vars(h.base.base.h.plan)),
        h.base.base.h.results,
        h.base.base.h.typed_results,
        h.base.base.h.trace,
        tuple(h.base.base.h.working_evidence_items),
    )
    assert after == h.before
    assert vars(h.requirement_set) == {
        "requirement_set_id": "semantic-requirement-set"
    }
    assert h.base.initial_assessment is h.before_assessment
    assert h.base.research_execution is h.before_research_execution
    assert h.reconciliation is h.before_reconciliation
    assert h.base.base.h.retrieved_at is h.before_retrieved_at
