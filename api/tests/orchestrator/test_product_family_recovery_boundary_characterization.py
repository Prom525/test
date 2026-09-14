"""Characterization of the service-owned product-family recovery boundary.

The real stored core facade is used.  The 3F2 entry and service lookup points
are replaced with inert objects so this suite stays network-free.  A
``BaseException`` sentinel stops immediately at the next Phase-C boundary and
therefore cannot be swallowed by either production ``except Exception``.
"""
from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

from app.orchestrator import service
from app.orchestrator.models import OrchestratorAskRequest
from app.orchestrator.phase_c_entry_stage import PhaseCEntryResult


class BoundaryObserved(BaseException):
    pass


DEFAULT_RECOVERY = {
    "contract_version": "promati.orchestrator.product_family_evidence.v1",
    "performed": False,
    "requested_family_codes": [],
    "attempted_family_codes": [],
    "attempted_call_count": 0,
    "accepted_result_count": 0,
    "skipped_budget_family_codes": [],
    "skipped_missing_step_family_codes": [],
}

_UNSET = object()


def _install(
    monkeypatch,
    *,
    coverage_values=(),
    coverage_error_at=None,
    recovery_raw=None,
    recovery_metadata=_UNSET,
    recovery_typed=(),
    recovery_error=False,
    normalize_outputs=None,
    normalize_error_at=None,
    initial_evidence=None,
    working_evidence=None,
    initial_follow_up_count=7,
):
    calls = []
    captured = {}
    requirement_set = object()
    retrieved_at = object()
    plan = SimpleNamespace(
        intent="synthetic_intent",
        clarification_required=False,
        clarification_question=None,
        execution_steps=(),
        research_required=False,
        requested_information=(),
        multi_intent=False,
    )
    initial = tuple((object(),) if initial_evidence is None else initial_evidence)
    working = initial if working_evidence is None else working_evidence
    entry = PhaseCEntryResult(requirement_set, retrieved_at, initial, working)
    counts = service._new_observability_counts()
    counts["phase_c_research_follow_up_specialist_calls"] = initial_follow_up_count
    counts["initial_evidence_items"] = len(initial)
    timings = service._new_observability_timings()
    timings["evidence_normalization"] = 123
    raw_results = []
    typed_results = []
    trace = {"attempts": []}
    sender = object()
    values = list(coverage_values) or [
        {"applicable": False, "missing_family_codes": ()}
    ]

    monkeypatch.setattr(service, "_new_observability_counts", lambda: counts)
    monkeypatch.setattr(service, "_new_observability_timings", lambda: timings)
    monkeypatch.setattr(service, "run_initial_planning_stage", lambda *a, **k: plan)
    monkeypatch.setattr(service, "_record_initial_execution_observability", lambda *a: None)

    def initial_execution(*args, **kwargs):
        calls.append(("initial_execution", args, kwargs))
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

    def phase_c(*args, **kwargs):
        calls.append(("phase_c_entry", args, kwargs))
        return entry

    monkeypatch.setattr(service, "prepare_phase_c_entry", phase_c)

    def coverage(*args, **kwargs):
        index = sum(call[0] == "coverage" for call in calls)
        calls.append(("coverage", args, kwargs))
        if coverage_error_at == index:
            raise RuntimeError(f"coverage-{index}")
        return values[index]

    monkeypatch.setattr(service, "assess_product_family_coverage", coverage)

    metadata = recovery_metadata
    if metadata is _UNSET:
        metadata = {**DEFAULT_RECOVERY, "performed": True, "attempted_call_count": 2}
    raw = object() if recovery_raw is None else recovery_raw

    def recover(*args, **kwargs):
        calls.append(("recover", args, kwargs))
        observer = kwargs["shadow_observer"]
        for item in recovery_typed:
            observer(item)
        if recovery_error:
            raise RuntimeError("recovery")
        return raw, metadata

    monkeypatch.setattr(service, "recover_missing_product_families", recover)

    outputs = normalize_outputs or {}

    def normalize(item, *, retrieved_at):
        index = sum(call[0] == "normalize" for call in calls)
        calls.append(("normalize", item, retrieved_at))
        if normalize_error_at == index:
            raise RuntimeError(f"normalize-{index}")
        return outputs.get(item, ())

    monkeypatch.setattr(service, "normalize_execution_result_evidence", normalize)

    def next_boundary(*args, **kwargs):
        captured.update(inspect.currentframe().f_back.f_locals)
        calls.append(("next_boundary", args, kwargs))
        raise BoundaryObserved("next boundary")

    monkeypatch.setattr(service, "_assess_intent_task_evidence_shadow", next_boundary)
    monkeypatch.setattr(service, "has_service_accepted_execution", lambda *a: True)

    def legacy_answer(*args, **kwargs):
        captured.update(inspect.currentframe().f_back.f_locals)
        calls.append(("legacy_answer", args, kwargs))
        raise BoundaryObserved("legacy path")

    monkeypatch.setattr(service, "_build_user_answer", legacy_answer)
    return SimpleNamespace(
        calls=calls,
        captured=captured,
        counts=counts,
        timings=timings,
        entry=entry,
        initial=initial,
        plan=plan,
        raw=raw,
        metadata=metadata,
        requirement_set=requirement_set,
        retrieved_at=retrieved_at,
        sender=sender,
        typed_results=typed_results,
        raw_results=raw_results,
        trace=trace,
    )


def _run(harness, match="next boundary"):
    payload = OrchestratorAskRequest(q="synthetic", vraag="")
    with pytest.raises(BoundaryObserved, match=match):
        service._p4_15cp3c_previous_run_orchestrator(payload, sender=harness.sender)


def _named(harness, name):
    return [call for call in harness.calls if call[0] == name]


def test_no_recovery_preserves_entry_state_and_exact_fresh_default(monkeypatch):
    first_coverage = {"applicable": False, "missing_family_codes": ["FAMILY-A"]}
    harness = _install(monkeypatch, coverage_values=[first_coverage])
    _run(harness)

    assert [call[0] for call in harness.calls] == [
        "initial_execution", "phase_c_entry", "coverage", "next_boundary"
    ]
    coverage = _named(harness, "coverage")[0]
    assert coverage[1] == (
        harness.requirement_set, harness.entry.working_evidence_items, harness.plan
    )
    assert coverage[1][0] is harness.requirement_set
    assert coverage[1][1] is harness.entry.working_evidence_items
    assert coverage[1][2] is harness.plan
    assert coverage[2] == {"now": harness.retrieved_at}
    assert harness.captured["product_family_coverage"] is first_coverage
    assert harness.captured["working_evidence_items"] is harness.entry.working_evidence_items
    assert harness.captured["product_family_recovery"] == DEFAULT_RECOVERY
    for key, value in DEFAULT_RECOVERY.items():
        if isinstance(value, list):
            assert harness.captured["product_family_recovery"][key] is not value
    assert harness.counts["phase_c_research_follow_up_specialist_calls"] == 7


def test_default_recovery_lists_are_fresh_between_core_calls(monkeypatch):
    first = _install(monkeypatch)
    _run(first)
    first_default = first.captured["product_family_recovery"]
    second = _install(monkeypatch)
    _run(second)
    second_default = second.captured["product_family_recovery"]
    assert first_default is not second_default
    for key, value in DEFAULT_RECOVERY.items():
        if isinstance(value, list):
            assert first_default[key] is not second_default[key]


@pytest.mark.parametrize(
    ("missing", "expected"),
    [
        (None, ()),
        ([], ()),
        ((), ()),
        (("A", "B"), ("A", "B")),
        (["A", "B"], ("A", "B")),
        ("AB", ("A", "B")),
        ({"A": 1, "B": 2}, ("A", "B")),
    ],
)
def test_missing_family_codes_are_exact_tuple_coercion(monkeypatch, missing, expected):
    applicable = bool(expected)
    harness = _install(
        monkeypatch,
        coverage_values=[{"applicable": applicable, "missing_family_codes": missing},
                         {"second": True}],
    )
    _run(harness)
    assert harness.captured["missing_product_families"] == expected
    assert len(_named(harness, "recover")) == (1 if expected else 0)


@pytest.mark.parametrize("applicable", [False, None, 0, ""])
def test_recovery_requires_truthy_applicable_and_nonempty_tuple(monkeypatch, applicable):
    first = {"applicable": applicable, "missing_family_codes": ["A"]}
    harness = _install(monkeypatch, coverage_values=[first])
    _run(harness)
    assert not _named(harness, "recover")
    assert len(_named(harness, "coverage")) == 1
    assert harness.captured["product_family_coverage"] is first


def test_recovery_exact_call_metadata_replacement_counter_and_raw_unused(monkeypatch):
    first = {"applicable": object(), "missing_family_codes": ["B", "A"]}
    second = {"replacement": object()}
    metadata = {"attempted_call_count": "3", "only": "returned-metadata"}
    raw = [object()]
    harness = _install(
        monkeypatch,
        coverage_values=[first, second],
        recovery_raw=raw,
        recovery_metadata=metadata,
    )
    _run(harness)

    recovery = _named(harness, "recover")[0]
    assert recovery[1] == (harness.plan, ("B", "A"))
    assert recovery[1][0] is harness.plan
    assert recovery[2]["sender"] is harness.sender
    assert recovery[2]["shadow_observer"].__self__ is harness.captured[
        "recovery_typed_results"
    ]
    assert recovery[2]["shadow_observer"].__name__ == "append"
    assert harness.captured["_recovery_raw_results"] is raw
    assert harness.captured["product_family_recovery"] is metadata
    assert harness.captured["product_family_recovery"] != DEFAULT_RECOVERY
    assert harness.counts["phase_c_research_follow_up_specialist_calls"] == 10
    assert len(_named(harness, "recover")) == 1
    assert len(_named(harness, "initial_execution")) == 1


@pytest.mark.parametrize(
    ("attempted", "increment"),
    [(4, 4), ("5", 5), (-2, 0), (True, 0), (None, 0), ("bad", 0)],
)
def test_follow_up_counter_uses_existing_nonnegative_int_contract(
    monkeypatch, attempted, increment
):
    metadata = {} if attempted is None else {"attempted_call_count": attempted}
    harness = _install(
        monkeypatch,
        coverage_values=[{"applicable": True, "missing_family_codes": ["A"]}, {}],
        recovery_metadata=metadata,
        initial_follow_up_count=11,
    )
    _run(harness)
    assert harness.counts["phase_c_research_follow_up_specialist_calls"] == 11 + increment


def test_recovered_typed_results_only_are_ordered_flattened_at_same_timestamp(monkeypatch):
    initial_a, initial_b = object(), object()
    recovered_a, recovered_b, recovered_c = object(), object(), object()
    raw = [object()]
    harness = _install(
        monkeypatch,
        coverage_values=[{"applicable": True, "missing_family_codes": ["A"]},
                         {"final": True}],
        recovery_raw=raw,
        recovery_typed=("typed-a", "typed-b", "typed-c"),
        normalize_outputs={
            "typed-a": (recovered_a, recovered_b),
            "typed-b": (),
            "typed-c": (recovered_c,),
        },
        initial_evidence=(initial_a, initial_b),
    )
    _run(harness)

    assert _named(harness, "normalize") == [
        ("normalize", "typed-a", harness.retrieved_at),
        ("normalize", "typed-b", harness.retrieved_at),
        ("normalize", "typed-c", harness.retrieved_at),
    ]
    assert harness.captured["recovered_evidence_items"] == (
        recovered_a, recovered_b, recovered_c
    )
    expected = (initial_a, initial_b, recovered_a, recovered_b, recovered_c)
    assert harness.captured["working_evidence_items"] == expected
    assert isinstance(harness.captured["working_evidence_items"], tuple)
    assert harness.entry.initial_evidence_items == (initial_a, initial_b)
    assert harness.counts["initial_evidence_items"] == 2
    assert harness.timings["evidence_normalization"] == 123
    assert all(item is not raw[0] for item in harness.captured["working_evidence_items"])


def test_zero_recovered_evidence_rebuilds_equal_but_distinct_working_tuple(monkeypatch):
    initial = (object(), object())
    harness = _install(
        monkeypatch,
        coverage_values=[{"applicable": True, "missing_family_codes": ["A"]}, {}],
        recovery_typed=("typed",),
        initial_evidence=initial,
    )
    _run(harness)
    working = harness.captured["working_evidence_items"]
    assert working == initial
    # CPython tuple(x) preserves tuple identity and tuple + () does too.
    assert working is harness.entry.initial_evidence_items


def test_second_coverage_reuses_exact_objects_and_replaces_first(monkeypatch):
    first = {"applicable": True, "missing_family_codes": ["A"]}
    second = {"final": object()}
    harness = _install(monkeypatch, coverage_values=[first, second])
    _run(harness)
    coverages = _named(harness, "coverage")
    assert len(coverages) == 2
    assert coverages[1][1][0] is harness.requirement_set
    assert coverages[1][1][1] is harness.captured["working_evidence_items"]
    assert coverages[1][1][2] is harness.plan
    assert coverages[1][2] == {"now": harness.retrieved_at}
    assert harness.captured["product_family_coverage"] is second


class _GetFailure:
    def get(self, key):
        raise RuntimeError(f"get-{key}")


class _MetadataGetFailure:
    def get(self, key):
        raise RuntimeError(f"metadata-{key}")


@pytest.mark.parametrize(
    ("failure", "expected_counter"),
    [
        ("first_coverage", 7),
        ("coverage_shape", 7),
        ("recovery", 7),
        ("metadata_shape", 7),
        ("normalize_first", 9),
        ("normalize_later", 9),
        ("second_coverage", 9),
    ],
)
def test_each_boundary_exception_enters_outer_fail_open_and_preserves_prior_mutations(
    monkeypatch, failure, expected_counter
):
    coverage_values = [
        {"applicable": True, "missing_family_codes": ["A"]}, {"final": True}
    ]
    kwargs = {}
    if failure == "first_coverage":
        kwargs["coverage_error_at"] = 0
    elif failure == "coverage_shape":
        coverage_values = [_GetFailure()]
    elif failure == "recovery":
        kwargs.update(recovery_error=True, recovery_typed=("observer-before-error",))
    elif failure == "metadata_shape":
        kwargs["recovery_metadata"] = _MetadataGetFailure()
    elif failure == "normalize_first":
        kwargs.update(recovery_typed=("one", "two"), normalize_error_at=0)
    elif failure == "normalize_later":
        kwargs.update(recovery_typed=("one", "two"), normalize_error_at=1)
    else:
        kwargs["coverage_error_at"] = 1

    if "recovery_metadata" not in kwargs:
        kwargs["recovery_metadata"] = {"attempted_call_count": 2}
    harness = _install(
        monkeypatch,
        coverage_values=coverage_values,
        **kwargs,
    )
    _run(harness, "legacy path")
    assert harness.captured["evidence_pipeline"] is None
    assert harness.counts["phase_c_research_follow_up_specialist_calls"] == expected_counter
    assert len(_named(harness, "initial_execution")) == 1
    assert len(_named(harness, "recover")) <= 1
    assert harness.typed_results == []
    assert harness.raw_results == []
    assert harness.trace == {"attempts": []}
    if failure == "recovery":
        assert harness.captured["recovery_typed_results"] == ["observer-before-error"]
        assert "recovered_evidence_items" not in harness.captured
        assert harness.captured["working_evidence_items"] is harness.entry.working_evidence_items


@pytest.mark.parametrize("malformed", [None, 3, object()])
def test_malformed_coverage_shapes_fail_open_without_recovery(monkeypatch, malformed):
    harness = _install(monkeypatch, coverage_values=[malformed])
    _run(harness, "legacy path")
    assert not _named(harness, "recover")
    assert harness.captured["evidence_pipeline"] is None


def test_noniterable_missing_codes_fail_open_before_applicable_lookup(monkeypatch):
    harness = _install(
        monkeypatch,
        coverage_values=[{"applicable": True, "missing_family_codes": 3}],
    )
    _run(harness, "legacy path")
    assert not _named(harness, "recover")
    assert harness.counts["phase_c_research_follow_up_specialist_calls"] == 7


def test_recovery_metadata_none_fails_open_before_counter_mutation(monkeypatch):
    harness = _install(
        monkeypatch,
        coverage_values=[{"applicable": True, "missing_family_codes": ["A"]}],
        recovery_metadata=None,
    )
    _run(harness, "legacy path")
    assert harness.captured["product_family_recovery"] is None
    assert harness.counts["phase_c_research_follow_up_specialist_calls"] == 7
