"""Characterize Phase-C reconciliation, its metric, and synthesis boundary."""

import importlib.util
from collections import UserDict
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.orchestrator import service
from app.orchestrator.models import OrchestratorAskRequest
from app.orchestrator.observability_stage import _observability_get as leaf_get
from app.orchestrator.phase_c_assessment_gate_stage import (
    PhaseCAssessmentGateStageResult,
)
from app.orchestrator.phase_c_bounded_research_stage import (
    PhaseCBoundedResearchStageResult,
)


class StopAtSynthesis(BaseException):
    pass


class Fatal(BaseException):
    pass


class ListSubclass(list):
    pass


class TupleSubclass(tuple):
    pass


def _prior_characterization():
    path = Path(__file__).with_name(
        "test_phase_c_bounded_research_metrics_boundary_characterization.py"
    )
    spec = importlib.util.spec_from_file_location("phase_c_3r1_for_3s1", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _install(monkeypatch, *, reconciliation=object(), count_start=41,
             timing_start=43):
    prior = _prior_characterization()
    base = prior._install(monkeypatch, metadata=None)
    initial_assessment = object()
    research_execution = object()
    boundary_calls = []
    base.h.counts["reconciled_evidence_items"] = count_start
    base.h.timings["reconciliation"] = timing_start

    monkeypatch.setattr(
        service,
        "run_phase_c_assessment_gate_stage",
        lambda *_args, **_kwargs: PhaseCAssessmentGateStageResult(
            initial_assessment, base.decision
        ),
    )

    def bounded_stage(*args, **kwargs):
        boundary_calls.append(("bounded_stage", args, kwargs))
        return PhaseCBoundedResearchStageResult(research_execution)

    def reconcile(*args, **kwargs):
        boundary_calls.append(("reconcile", args, kwargs))
        return reconciliation

    def get(value, key, default=None):
        boundary_calls.append(("get", (value, key, default), {}))
        return leaf_get(value, key, default)

    def synthesize(value):
        boundary_calls.append(("synthesis", (value,), {}))
        raise StopAtSynthesis("controlled following boundary")

    monkeypatch.setattr(service, "run_phase_c_bounded_research_stage", bounded_stage)
    monkeypatch.setattr(service, "reconcile_evidence", reconcile)
    monkeypatch.setattr(service, "_observability_get", get)
    monkeypatch.setattr(service, "synthesize_grounded_evidence", synthesize)
    before = (
        dict(vars(base.h.plan)),
        list(base.h.results),
        list(base.h.typed_results),
        dict(base.h.trace),
        tuple(base.h.working_evidence_items),
    )
    return SimpleNamespace(**locals())


def _run(harness, exception=StopAtSynthesis):
    with pytest.raises(exception) as raised:
        service._p4_15cp3c_previous_run_orchestrator(
            OrchestratorAskRequest(q="synthetic", vraag=""),
            sender=harness.base.h.sender,
        )
    return raised.value


@pytest.mark.parametrize(
    "reconciliation",
    [
        {"reconciled_evidence_items": [object(), object()]},
        [object()],
        (object(),),
        None,
        object(),
    ],
)
def test_order_single_calls_exact_identities_keywords_and_raw_return(
        monkeypatch, reconciliation):
    h = _install(monkeypatch, reconciliation=reconciliation)
    _run(h)

    assert [row[0] for row in h.boundary_calls] == [
        "bounded_stage", "reconcile", "get", "synthesis"
    ]
    assert all(
        [row[0] for row in h.boundary_calls].count(name) == 1
        for name in ("bounded_stage", "reconcile", "get", "synthesis")
    )
    bounded, reconcile, get, synthesis = h.boundary_calls
    assert bounded[1] == (
        h.base.h.timings, h.base.h.counts, h.base.decision, h.base.h.plan,
        h.base.h.results, h.base.h.sender,
    )
    assert reconcile[1] == (
        h.base.h.requirement_set,
        h.base.h.working_evidence_items,
        h.initial_assessment,
        h.research_execution,
    )
    assert all(actual is expected for actual, expected in zip(
        reconcile[1],
        (h.base.h.requirement_set, h.base.h.working_evidence_items,
         h.initial_assessment, h.research_execution),
    ))
    assert reconcile[2] == {
        "retrieved_at": h.base.h.retrieved_at,
        "target_entity_ids": None,
        "now": h.base.h.retrieved_at,
    }
    assert reconcile[2]["retrieved_at"] is h.base.h.retrieved_at
    assert reconcile[2]["now"] is h.base.h.retrieved_at
    assert get[1] == (reconciliation, "reconciled_evidence_items", ())
    assert get[1][0] is reconciliation
    assert synthesis[1] == (reconciliation,)
    assert synthesis[1][0] is reconciliation
    assert (dict(vars(h.base.h.plan)), h.base.h.results, h.base.h.typed_results,
            h.base.h.trace, tuple(h.base.h.working_evidence_items)) == h.before


def test_runtime_resolved_observability_callable_label_timings_and_arguments(monkeypatch):
    reconciliation = {"reconciled_evidence_items": ()}
    h = _install(monkeypatch, reconciliation=reconciliation)
    original = service._observability_call
    observed = []

    def recording(timings, label, callable_, *args, **kwargs):
        if label in {"reconciliation", "synthesis"}:
            observed.append((timings, label, callable_, args, kwargs))
        return original(timings, label, callable_, *args, **kwargs)

    monkeypatch.setattr(service, "_observability_call", recording)
    _run(h)

    assert [row[1] for row in observed] == ["reconciliation", "synthesis"]
    assert observed[0][0] is observed[1][0] is h.base.h.timings
    assert observed[0][2] is service.reconcile_evidence
    assert observed[1][2] is service.synthesize_grounded_evidence
    assert observed[0][3] == (
        h.base.h.requirement_set, h.base.h.working_evidence_items,
        h.initial_assessment, h.research_execution,
    )
    assert observed[0][4] == {
        "retrieved_at": h.base.h.retrieved_at,
        "target_entity_ids": None,
        "now": h.base.h.retrieved_at,
    }
    assert observed[1][3] == (reconciliation,)
    assert observed[1][4] == {}


@pytest.mark.parametrize(
    "items,expected",
    [
        ([], 0),
        ([object(), object()], 2),
        ((object(),), 1),
        (ListSubclass([1, 2, 3]), 3),
        (TupleSubclass((1, 2, 3, 4)), 4),
    ],
)
def test_only_list_tuple_and_subclasses_replace_count_with_length(
        monkeypatch, items, expected):
    reconciliation = {"reconciled_evidence_items": items}
    h = _install(monkeypatch, reconciliation=reconciliation, count_start=97)
    _run(h)
    assert h.base.h.counts["reconciled_evidence_items"] == expected


@pytest.mark.parametrize(
    "items",
    [
        {"x": 1},
        UserDict({"x": 1}),
        "abc",
        (value for value in range(3)),
        None,
        object(),
    ],
)
def test_mapping_string_generator_none_and_object_leave_count_unchanged(
        monkeypatch, items):
    h = _install(
        monkeypatch,
        reconciliation={"reconciled_evidence_items": items},
        count_start=97,
    )
    _run(h)
    assert h.base.h.counts["reconciled_evidence_items"] == 97


def test_exact_get_default_and_missing_field_replace_count_with_zero(monkeypatch):
    reconciliation = object()
    h = _install(monkeypatch, reconciliation=reconciliation, count_start=101)
    _run(h)
    gets = [row for row in h.boundary_calls if row[0] == "get"]
    assert len(gets) == 1
    assert gets[0][1][0] is reconciliation
    assert gets[0][1][1:] == ("reconciled_evidence_items", ())
    assert h.base.h.counts["reconciled_evidence_items"] == 0


def test_timing_and_count_use_replacement_not_accumulation(monkeypatch):
    h = _install(
        monkeypatch,
        reconciliation={"reconciled_evidence_items": [1, 2, 3]},
        timing_start=987654,
        count_start=123,
    )
    _run(h)
    assert h.base.h.timings["reconciliation"] != 987654
    assert h.base.h.timings["reconciliation"] >= 0
    assert h.base.h.counts["reconciled_evidence_items"] == 3


def test_fresh_timings_and_counts_do_not_leak_between_runs(monkeypatch):
    with monkeypatch.context() as first_patch:
        first = _install(
            first_patch,
            reconciliation={"reconciled_evidence_items": [1, 2]},
            timing_start=701,
            count_start=702,
        )
        _run(first)
        first_timings = first.base.h.timings
        first_counts = first.base.h.counts
        assert first_counts["reconciled_evidence_items"] == 2

    with monkeypatch.context() as second_patch:
        second = _install(
            second_patch,
            reconciliation={"reconciled_evidence_items": object()},
            timing_start=801,
            count_start=802,
        )
        _run(second)
        assert second.base.h.timings is not first_timings
        assert second.base.h.counts is not first_counts
        assert second.base.h.counts["reconciled_evidence_items"] == 802
        assert first_counts["reconciled_evidence_items"] == 2


@pytest.mark.parametrize("where", ["reconcile", "get", "length", "synthesis"])
@pytest.mark.parametrize("fatal", [False, True])
def test_exception_boundary_partial_mutations_and_baseexception_propagation(
        monkeypatch, where, fatal):
    error = Fatal(where) if fatal else RuntimeError(where)

    class ExplodingList(list):
        def __len__(self):
            raise error

    items = ExplodingList([1]) if where == "length" else [1, 2, 3]
    reconciliation = {"reconciled_evidence_items": items}
    h = _install(
        monkeypatch, reconciliation=reconciliation,
        timing_start=887, count_start=889,
    )

    if where == "reconcile":
        def fail_reconcile(*args, **kwargs):
            h.boundary_calls.append(("reconcile", args, kwargs))
            raise error
        monkeypatch.setattr(service, "reconcile_evidence", fail_reconcile)
    elif where == "get":
        def fail_get(*args, **kwargs):
            h.boundary_calls.append(("get", args, kwargs))
            raise error
        monkeypatch.setattr(service, "_observability_get", fail_get)
    elif where == "synthesis":
        def fail_synthesis(value):
            h.boundary_calls.append(("synthesis", (value,), {}))
            raise error
        monkeypatch.setattr(service, "synthesize_grounded_evidence", fail_synthesis)

    raised = _run(
        h,
        Fatal if fatal else h.base.characterized.StopOnLegacyPath,
    )
    if fatal:
        assert raised is error
    names = [row[0] for row in h.boundary_calls]
    assert names.count("reconcile") == 1
    assert ("get" in names) is (where != "reconcile")
    assert ("synthesis" in names) is (where == "synthesis")
    assert ("legacy_path" in [row[0] for row in h.base.h.calls]) is (not fatal)
    assert h.base.h.timings["reconciliation"] != 887
    expected_count = 3 if where == "synthesis" else 889
    assert h.base.h.counts["reconciled_evidence_items"] == expected_count


@pytest.mark.parametrize("fatal", [False, True])
def test_runtime_reconciliation_observability_failure_uses_outer_boundary(
        monkeypatch, fatal):
    h = _install(monkeypatch, timing_start=991, count_start=993)
    error = Fatal("observability") if fatal else RuntimeError("observability")
    original = service._observability_call

    def fail(timings, label, callable_, *args, **kwargs):
        if label == "reconciliation":
            raise error
        return original(timings, label, callable_, *args, **kwargs)

    monkeypatch.setattr(service, "_observability_call", fail)
    raised = _run(h, Fatal if fatal else h.base.characterized.StopOnLegacyPath)
    if fatal:
        assert raised is error
    assert not [row for row in h.boundary_calls if row[0] in {
        "reconcile", "get", "synthesis"
    }]
    assert h.base.h.timings["reconciliation"] == 991
    assert h.base.h.counts["reconciled_evidence_items"] == 993
