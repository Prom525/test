from __future__ import annotations

from dataclasses import fields
from pathlib import Path
from types import SimpleNamespace
import ast

import pytest

from app.orchestrator.product_family_recovery_stage import (
    ProductFamilyRecoveryResult,
    run_product_family_recovery_stage,
)


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


def _run(*, coverage_values=None, recovery_raw=None, recovery_metadata=_UNSET,
         recovery_typed=(), recovery_error=False, normalize_outputs=None,
         normalize_error_at=None, initial=(), working=None, count=7,
         coverage_error_at=None, state=None):
    calls = []
    plan, requirement, stamp, sender = object(), object(), object(), object()
    working = initial if working is None else working
    counts = {"phase_c_research_follow_up_specialist_calls": count}
    values = list(coverage_values or [
        {"applicable": False, "missing_family_codes": ()}
    ])
    metadata = ({**DEFAULT_RECOVERY, "performed": True,
                 "attempted_call_count": 2}
                if recovery_metadata is _UNSET else recovery_metadata)
    raw = object() if recovery_raw is None else recovery_raw

    def coverage(*args, **kwargs):
        index = len([call for call in calls if call[0] == "coverage"])
        calls.append(("coverage", args, kwargs))
        if coverage_error_at == index:
            raise RuntimeError(f"coverage-{index}")
        return values[index]

    def recover(*args, **kwargs):
        calls.append(("recover", args, kwargs))
        for item in recovery_typed:
            kwargs["shadow_observer"](item)
        if recovery_error:
            raise RuntimeError("recovery")
        return raw, metadata

    def normalize(item, *, retrieved_at):
        index = len([call for call in calls if call[0] == "normalize"])
        calls.append(("normalize", item, retrieved_at))
        if normalize_error_at == index:
            raise RuntimeError(f"normalize-{index}")
        return (normalize_outputs or {}).get(item, ())

    def nonnegative(value):
        calls.append(("nonnegative", value))
        if isinstance(value, bool):
            return 0
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return 0

    if state is not None:
        state.update(calls=calls, counts=counts)
    result = run_product_family_recovery_stage(
        plan, requirement, initial, working, stamp, counts, sender,
        assess_product_family_coverage=coverage,
        recover_missing_product_families=recover,
        normalize_execution_result_evidence=normalize,
        observability_nonnegative_int=nonnegative,
    )
    return SimpleNamespace(result=result, calls=calls, counts=counts, plan=plan,
                           requirement=requirement, stamp=stamp, sender=sender,
                           initial=initial, working=working, raw=raw, metadata=metadata)


def _named(run, name):
    return [call for call in run.calls if call[0] == name]


def test_no_recovery_exact_call_return_contract_and_fresh_default():
    working = (object(),)
    first = {"applicable": False, "missing_family_codes": ["A"]}
    run = _run(coverage_values=[first], initial=(object(),), working=working)
    assert isinstance(run.result, ProductFamilyRecoveryResult)
    assert [field.name for field in fields(run.result)] == [
        "product_family_coverage", "product_family_recovery",
        "working_evidence_items",
    ]
    assert [call[0] for call in run.calls] == ["coverage"]
    call = run.calls[0]
    assert call[1] == (run.requirement, working, run.plan)
    assert all(actual is expected for actual, expected in zip(
        call[1], (run.requirement, working, run.plan)
    ))
    assert call[2] == {"now": run.stamp}
    assert run.result.product_family_coverage is first
    assert run.result.working_evidence_items is working
    assert run.result.product_family_recovery == DEFAULT_RECOVERY
    assert run.counts["phase_c_research_follow_up_specialist_calls"] == 7


def test_default_dict_and_lists_are_fresh_between_calls():
    first, second = _run().result.product_family_recovery, _run().result.product_family_recovery
    assert first is not second
    for key, value in DEFAULT_RECOVERY.items():
        if isinstance(value, list):
            assert first[key] is not second[key]


@pytest.mark.parametrize(("missing", "expected"), [
    (None, ()), ([], ()), ((), ()), (("A", "B"), ("A", "B")),
    (["A", "B"], ("A", "B")), ("AB", ("A", "B")),
    ({"A": 1, "B": 2}, ("A", "B")),
])
def test_missing_codes_use_literal_tuple_coercion(missing, expected):
    applicable = bool(expected)
    values = [{"applicable": applicable, "missing_family_codes": missing}]
    if expected:
        values.append({})
    run = _run(coverage_values=values)
    recoveries = _named(run, "recover")
    assert len(recoveries) == (1 if expected else 0)
    if expected:
        assert recoveries[0][1][1] == expected


@pytest.mark.parametrize("applicable", [False, None, 0, ""])
def test_recovery_requires_truthy_applicable(applicable):
    first = {"applicable": applicable, "missing_family_codes": ["A"]}
    run = _run(coverage_values=[first])
    assert not _named(run, "recover")
    assert len(_named(run, "coverage")) == 1
    assert run.result.product_family_coverage is first


def test_exact_recovery_call_metadata_replacement_counter_raw_unused_and_max_one():
    metadata = {"attempted_call_count": "3", "only": "metadata"}
    raw = [object()]
    run = _run(
        coverage_values=[{"applicable": object(), "missing_family_codes": ["B", "A"]},
                         {"replacement": object()}],
        recovery_raw=raw, recovery_metadata=metadata,
    )
    recovery = _named(run, "recover")[0]
    assert recovery[1] == (run.plan, ("B", "A"))
    assert recovery[1][0] is run.plan
    assert recovery[2]["sender"] is run.sender
    assert recovery[2]["shadow_observer"].__name__ == "append"
    assert run.result.product_family_recovery is metadata
    assert run.result.product_family_recovery != DEFAULT_RECOVERY
    assert run.counts["phase_c_research_follow_up_specialist_calls"] == 10
    assert len(_named(run, "recover")) == 1
    assert all(raw is not call[1] for call in _named(run, "normalize"))


@pytest.mark.parametrize(("attempted", "increment"), [
    (4, 4), ("5", 5), (-2, 0), (True, 0), (None, 0), ("bad", 0),
])
def test_counter_uses_supplied_nonnegative_conversion_and_start_value(attempted, increment):
    metadata = {} if attempted is None else {"attempted_call_count": attempted}
    run = _run(
        coverage_values=[{"applicable": True, "missing_family_codes": ["A"]}, {}],
        recovery_metadata=metadata, count=11,
    )
    assert _named(run, "nonnegative") == [("nonnegative", attempted)]
    assert run.counts["phase_c_research_follow_up_specialist_calls"] == 11 + increment


def test_ordered_typed_normalization_timestamp_tuple_composition_and_raw_unused():
    initial = (object(), object())
    recovered = (object(), object(), object())
    raw = [object()]
    run = _run(
        coverage_values=[{"applicable": True, "missing_family_codes": ["A"]},
                         {"final": True}],
        recovery_raw=raw, recovery_typed=("a", "b", "c"), initial=initial,
        normalize_outputs={"a": recovered[:2], "b": (), "c": recovered[2:]},
    )
    assert _named(run, "normalize") == [
        ("normalize", "a", run.stamp), ("normalize", "b", run.stamp),
        ("normalize", "c", run.stamp),
    ]
    assert run.result.working_evidence_items == initial + recovered
    assert isinstance(run.result.working_evidence_items, tuple)
    assert all(item is not raw[0] for item in run.result.working_evidence_items)


def test_zero_recovered_evidence_preserves_tuple_identity():
    initial = (object(), object())
    run = _run(
        coverage_values=[{"applicable": True, "missing_family_codes": ["A"]}, {}],
        recovery_typed=("typed",), initial=initial,
    )
    assert run.result.working_evidence_items is initial


def test_second_coverage_exact_objects_and_replaces_first():
    first, second = ({"applicable": True, "missing_family_codes": ["A"]},
                     {"final": object()})
    run = _run(coverage_values=[first, second])
    calls = _named(run, "coverage")
    assert len(calls) == 2
    assert calls[1][1][0] is run.requirement
    assert calls[1][1][1] is run.result.working_evidence_items
    assert calls[1][1][2] is run.plan
    assert calls[1][2] == {"now": run.stamp}
    assert run.result.product_family_coverage is second


class _GetFailure:
    def get(self, key):
        raise RuntimeError(f"get-{key}")


class _MetadataGetFailure:
    def get(self, key):
        raise RuntimeError(f"metadata-{key}")


@pytest.mark.parametrize(("failure", "expected_counter", "message"), [
    ("first_coverage", 7, "coverage-0"),
    ("coverage_shape", 7, "get-missing_family_codes"),
    ("recovery", 7, "recovery"),
    ("metadata_shape", 7, "metadata-attempted_call_count"),
    ("normalize_first", 9, "normalize-0"),
    ("normalize_later", 9, "normalize-1"),
    ("second_coverage", 9, "coverage-1"),
])
def test_failure_matrix_propagates_and_preserves_partial_count(failure, expected_counter, message):
    kwargs = {"coverage_values": [
        {"applicable": True, "missing_family_codes": ["A"]}, {"final": True}
    ], "recovery_metadata": {"attempted_call_count": 2}}
    if failure == "first_coverage":
        kwargs["coverage_error_at"] = 0
    elif failure == "coverage_shape":
        kwargs["coverage_values"] = [_GetFailure()]
    elif failure == "recovery":
        kwargs.update(recovery_error=True, recovery_typed=("before-error",))
    elif failure == "metadata_shape":
        kwargs["recovery_metadata"] = _MetadataGetFailure()
    elif failure == "normalize_first":
        kwargs.update(recovery_typed=("one", "two"), normalize_error_at=0)
    elif failure == "normalize_later":
        kwargs.update(recovery_typed=("one", "two"), normalize_error_at=1)
    else:
        kwargs["coverage_error_at"] = 1
    state = {}
    with pytest.raises(RuntimeError, match=f"^{message}$"):
        _run(state=state, **kwargs)
    assert state["counts"]["phase_c_research_follow_up_specialist_calls"] == expected_counter
    assert len([call for call in state["calls"] if call[0] == "recover"]) <= 1


@pytest.mark.parametrize("malformed", [None, 3, object()])
def test_malformed_coverage_shape_propagates_without_recovery(malformed):
    state = {}
    with pytest.raises(AttributeError):
        _run(coverage_values=[malformed], state=state)
    assert not [call for call in state["calls"] if call[0] == "recover"]


def test_noniterable_missing_codes_propagates_before_applicable_lookup():
    with pytest.raises(TypeError):
        _run(coverage_values=[{"applicable": True, "missing_family_codes": 3}])


def test_none_metadata_propagates_before_counter_mutation():
    state = {}
    with pytest.raises(AttributeError):
        _run(coverage_values=[{"applicable": True, "missing_family_codes": ["A"]}],
             recovery_metadata=None, state=state)
    assert state["counts"]["phase_c_research_follow_up_specialist_calls"] == 7


def test_leaf_import_surface_and_single_service_call():
    stage_source = Path("app/orchestrator/product_family_recovery_stage.py").read_text()
    service_source = Path("app/orchestrator/service.py").read_text()
    tree = ast.parse(stage_source)
    roots = {node.module.split(".")[0] for node in ast.walk(tree)
             if isinstance(node, ast.ImportFrom) and node.module}
    assert roots == {"dataclasses", "typing"}
    for forbidden in ("service", "fastapi", "database", "settings", "network"):
        assert forbidden not in stage_source.lower()
    assert service_source.count("run_product_family_recovery_stage(") == 1
    assert "missing_product_families =" not in service_source
    assert "recovery_typed_results =" not in service_source
    assert "recovered_evidence_items =" not in service_source
