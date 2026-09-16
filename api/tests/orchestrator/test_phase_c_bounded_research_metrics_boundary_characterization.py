"""Characterize bounded Phase-C research and its immediate metrics boundary."""

import importlib.util
from collections import UserDict
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.orchestrator import service
from app.orchestrator.models import OrchestratorAskRequest
from app.orchestrator.phase_c_assessment_gate_stage import (
    PhaseCAssessmentGateStageResult,
)


class StopAtReconciliation(BaseException):
    pass


class Fatal(BaseException):
    pass


class AttributeMetadata:
    agent_metadata = {"follow_up_specialist_calls": 99, "total_ai_calls_used": 88}


class ExplodingMetadata(dict):
    def get(self, key, default=None):
        if key == "total_ai_calls_used":
            raise RuntimeError("second metadata get")
        return super().get(key, default)


def _characterization():
    path = Path(__file__).with_name(
        "test_phase_c_assessment_research_gate_boundary_characterization.py")
    spec = importlib.util.spec_from_file_location("phase_c_3q1_for_3r1", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _install(monkeypatch, *, execution=object(), metadata=None,
             follow_start=7, ai_start=11):
    characterized = _characterization()
    h = characterized._install(monkeypatch)
    h.counts["phase_c_research_follow_up_specialist_calls"] = follow_start
    h.counts["phase_c_ai_calls"] = ai_start
    decision = object()
    monkeypatch.setattr(
        service,
        "run_phase_c_assessment_gate_stage",
        lambda *_args, **_kwargs: PhaseCAssessmentGateStageResult(object(), decision),
    )
    calls = []

    def execute(*args, **kwargs):
        calls.append(("execute", args, kwargs))
        return execution

    def get(value, key, default=None):
        calls.append(("get", (value, key, default), {}))
        if key == "agent_metadata":
            return metadata
        return service._observability_get(value, key, default)

    original_int = service._observability_nonnegative_int

    def integer(value):
        calls.append(("int", (value,), {}))
        return original_int(value)

    def reconcile(*args, **kwargs):
        calls.append(("reconcile", args, kwargs))
        raise StopAtReconciliation("controlled next consumer")

    monkeypatch.setattr(service, "execute_bounded_research", execute)
    monkeypatch.setattr(service, "_observability_get", get)
    monkeypatch.setattr(service, "_observability_nonnegative_int", integer)
    monkeypatch.setattr(service, "reconcile_evidence", reconcile)
    return SimpleNamespace(**locals())


def _run(h, exception=StopAtReconciliation):
    with pytest.raises(exception) as raised:
        service._p4_15cp3c_previous_run_orchestrator(
            OrchestratorAskRequest(q="synthetic", vraag=""), sender=h.h.sender)
    return raised.value


@pytest.mark.parametrize("execution", [object(), {"x": 1}, [1], (1,), None])
def test_exact_execution_order_identity_inputs_and_single_reconciliation(monkeypatch, execution):
    metadata = {"follow_up_specialist_calls": 2, "total_ai_calls_used": 3}
    h = _install(monkeypatch, execution=execution, metadata=metadata)
    _run(h)
    assert [row[0] for row in h.calls] == ["execute", "get", "int", "int", "reconcile"]
    execute = h.calls[0]
    assert execute[1][0] is h.decision and execute[1][1] is h.h.plan
    copied = execute[1][2]
    assert isinstance(copied, list) and copied is not h.h.results
    assert all(actual is expected for actual, expected in zip(copied, h.h.results))
    assert execute[2] == {"sender": h.h.sender}
    assert h.calls[1][1] == (execution, "agent_metadata", None)
    reconcile = h.calls[-1]
    assert reconcile[1] == (
        h.h.requirement_set, h.h.working_evidence_items,
        reconcile[1][2], execution)
    assert reconcile[1][3] is execution
    assert reconcile[2] == {
        "retrieved_at": h.h.retrieved_at,
        "target_entity_ids": None,
        "now": h.h.retrieved_at,
    }
    assert h.h.counts["phase_c_research_follow_up_specialist_calls"] == 9
    assert h.h.counts["phase_c_ai_calls"] == 3
    assert h.h.timings["evidence_research"] == 11
    assert (vars(h.h.plan), h.h.results, h.h.typed_results, h.h.trace) == h.h.before
    assert tuple(h.h.working_evidence_items) == h.h.evidence_before


@pytest.mark.parametrize(
    "value, expected",
    [(None, 0), (4, 4), (-4, 0), (True, 0), ("5", 5), ("bad", 0),
     (2.9, 2), (object(), 0)],
)
def test_each_metadata_counter_uses_current_nonnegative_integer_semantics(
        monkeypatch, value, expected):
    metadata = {"follow_up_specialist_calls": value, "total_ai_calls_used": value}
    h = _install(monkeypatch, metadata=metadata)
    _run(h)
    assert [row[1][0] for row in h.calls if row[0] == "int"] == [value, value]
    assert h.h.counts["phase_c_research_follow_up_specialist_calls"] == 7 + expected
    assert h.h.counts["phase_c_ai_calls"] == expected


def test_missing_metadata_keys_use_none_and_fresh_counts_do_not_leak(monkeypatch):
    first = _install(monkeypatch, metadata={}, follow_start=13, ai_start=17)
    _run(first)
    assert [row[1][0] for row in first.calls if row[0] == "int"] == [None, None]
    assert first.h.counts["phase_c_research_follow_up_specialist_calls"] == 13
    assert first.h.counts["phase_c_ai_calls"] == 0


@pytest.mark.parametrize(
    "metadata",
    [None, [], (), UserDict({"follow_up_specialist_calls": 9}), object()],
)
def test_non_dict_metadata_leaves_counts_exactly_unchanged(monkeypatch, metadata):
    h = _install(monkeypatch, metadata=metadata, follow_start=13, ai_start=17)
    _run(h)
    assert not [row for row in h.calls if row[0] == "int"]
    assert h.h.counts["phase_c_research_follow_up_specialist_calls"] == 13
    assert h.h.counts["phase_c_ai_calls"] == 17


def test_dict_subclass_is_processed_and_attribute_metadata_is_read_once(monkeypatch):
    metadata = type("MetadataDict", (dict,), {})({
        "follow_up_specialist_calls": 4, "total_ai_calls_used": 5})
    h = _install(monkeypatch, execution=AttributeMetadata(), metadata=metadata)
    _run(h)
    assert len([row for row in h.calls if row[0] == "get"]) == 1
    assert h.h.counts["phase_c_research_follow_up_specialist_calls"] == 11
    assert h.h.counts["phase_c_ai_calls"] == 5


def test_second_metadata_get_failure_preserves_partial_first_counter_mutation(monkeypatch):
    h = _install(monkeypatch, metadata=ExplodingMetadata(
        follow_up_specialist_calls=4), follow_start=7, ai_start=11)
    _run(h, h.characterized.StopOnLegacyPath)
    assert h.h.counts["phase_c_research_follow_up_specialist_calls"] == 11
    assert h.h.counts["phase_c_ai_calls"] == 11
    assert h.h.timings["evidence_research"] == 11
    assert not [row for row in h.calls if row[0] == "reconcile"]


@pytest.mark.parametrize("fatal", [False, True])
def test_second_integer_failure_preserves_partial_first_counter_mutation(monkeypatch, fatal):
    h = _install(monkeypatch, metadata={
        "follow_up_specialist_calls": 4, "total_ai_calls_used": 5})
    original = service._observability_nonnegative_int
    invocations = []

    def fail_second(value):
        invocations.append(value)
        if len(invocations) == 2:
            raise Fatal("second conversion") if fatal else RuntimeError("second conversion")
        return original(value)

    monkeypatch.setattr(service, "_observability_nonnegative_int", fail_second)
    raised = _run(h, Fatal if fatal else h.characterized.StopOnLegacyPath)
    if fatal:
        assert isinstance(raised, Fatal)
    assert invocations[:2] == [4, 5]
    assert h.h.counts["phase_c_research_follow_up_specialist_calls"] == 11
    assert h.h.counts["phase_c_ai_calls"] == 11
    assert h.h.timings["evidence_research"] == 11


@pytest.mark.parametrize("fatal", [False, True])
@pytest.mark.parametrize("failing_key", [
    "follow_up_specialist_calls", "total_ai_calls_used"])
def test_metadata_dict_get_exceptions_keep_exact_partial_state(
        monkeypatch, fatal, failing_key):
    error = Fatal(failing_key) if fatal else RuntimeError(failing_key)

    class Metadata(dict):
        def get(self, key, default=None):
            if key == failing_key:
                raise error
            return super().get(key, default)

    h = _install(monkeypatch, metadata=Metadata(
        follow_up_specialist_calls=4, total_ai_calls_used=5))
    raised = _run(h, Fatal if fatal else h.characterized.StopOnLegacyPath)
    if fatal:
        assert raised is error
    expected_follow = 7 if failing_key == "follow_up_specialist_calls" else 11
    assert h.h.counts["phase_c_research_follow_up_specialist_calls"] == expected_follow
    assert h.h.counts["phase_c_ai_calls"] == 11
    assert h.h.timings["evidence_research"] == 11
    assert not [row for row in h.calls if row[0] == "reconcile"]


@pytest.mark.parametrize("fatal", [False, True])
@pytest.mark.parametrize("where", ["execution", "metadata", "first_int"])
def test_exception_boundaries_stop_reconciliation_and_preserve_research_timing(
        monkeypatch, fatal, where):
    error = Fatal(where) if fatal else RuntimeError(where)
    h = _install(monkeypatch, metadata={
        "follow_up_specialist_calls": 2, "total_ai_calls_used": 3})

    if where == "execution":
        def fail(*_args, **_kwargs):
            raise error
        monkeypatch.setattr(service, "execute_bounded_research", fail)
    elif where == "metadata":
        def fail(*_args, **_kwargs):
            raise error
        monkeypatch.setattr(service, "_observability_get", fail)
    else:
        calls = [0]

        def fail(*args, **kwargs):
            calls[0] += 1
            if calls[0] == 1:
                raise error
            return h.original_int(*args, **kwargs)
        monkeypatch.setattr(service, "_observability_nonnegative_int", fail)

    raised = _run(h, Fatal if fatal else h.characterized.StopOnLegacyPath)
    if fatal:
        assert raised is error
    assert not [row for row in h.calls if row[0] == "reconcile"]
    assert h.h.timings["evidence_research"] == 11
    assert ("legacy_path" in [row[0] for row in h.h.calls]) is (not fatal)


@pytest.mark.parametrize("fatal", [False, True])
def test_list_coercion_exception_precedes_execution_and_research_timing(monkeypatch, fatal):
    error = Fatal("list") if fatal else RuntimeError("list")

    class BadResults:
        calls = 0

        def __iter__(self):
            self.calls += 1
            if self.calls == 1:
                raise error
            return iter(())

    h = _install(monkeypatch)
    h.h.initial.results = BadResults()
    raised = _run(h, Fatal if fatal else h.characterized.StopOnLegacyPath)
    if fatal:
        assert raised is error
    assert not [row for row in h.calls if row[0] in {"execute", "get", "reconcile"}]
    assert h.h.timings["evidence_research"] == 0


def test_reconciliation_failure_is_only_the_controlled_next_boundary(monkeypatch):
    h = _install(monkeypatch, metadata={
        "follow_up_specialist_calls": 2, "total_ai_calls_used": 3})
    raised = _run(h)
    assert isinstance(raised, StopAtReconciliation)
    assert [row[0] for row in h.calls].count("execute") == 1
    assert [row[0] for row in h.calls].count("reconcile") == 1
    assert h.h.counts["phase_c_research_follow_up_specialist_calls"] == 9
    assert h.h.counts["phase_c_ai_calls"] == 3


def test_research_observability_call_is_runtime_resolved_with_same_timings(monkeypatch):
    h = _install(monkeypatch, metadata={
        "follow_up_specialist_calls": 2, "total_ai_calls_used": 3})
    original = service._observability_call
    observed = []

    def call(timings, label, callable_, *args, **kwargs):
        if label == "evidence_research":
            observed.append((timings, callable_, args, kwargs))
        return original(timings, label, callable_, *args, **kwargs)

    monkeypatch.setattr(service, "_observability_call", call)
    _run(h)
    assert len(observed) == 1
    timings, callable_, args, kwargs = observed[0]
    assert timings is h.h.timings
    assert callable_ is service.execute_bounded_research
    assert args[0] is h.decision and args[1] is h.h.plan
    assert isinstance(args[2], list) and args[2] is not h.h.results
    assert all(actual is expected for actual, expected in zip(args[2], h.h.results))
    assert kwargs == {"sender": h.h.sender}


@pytest.mark.parametrize("fatal", [False, True])
def test_runtime_observability_call_exception_uses_existing_outer_boundary(
        monkeypatch, fatal):
    h = _install(monkeypatch)
    error = Fatal("observability call") if fatal else RuntimeError("observability call")
    original = service._observability_call

    def call(timings, label, callable_, *args, **kwargs):
        if label == "evidence_research":
            raise error
        return original(timings, label, callable_, *args, **kwargs)

    monkeypatch.setattr(service, "_observability_call", call)
    raised = _run(h, Fatal if fatal else h.characterized.StopOnLegacyPath)
    if fatal:
        assert raised is error
    assert not [row for row in h.calls if row[0] in {"execute", "get", "reconcile"}]
    assert h.h.timings["evidence_research"] == 0
