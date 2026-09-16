from collections import UserDict
from dataclasses import FrozenInstanceError, fields
from types import SimpleNamespace

import pytest

from app.orchestrator.phase_c_reconciliation_stage import (
    PhaseCReconciliationStageResult,
    run_phase_c_reconciliation_stage,
)


class Fatal(BaseException):
    pass


class ListSubclass(list):
    pass


class TupleSubclass(tuple):
    pass


def _run(*, reconciliation=object(), items=(), counts=None, observe=None,
         get=None, reconcile=None):
    timings, requirement_set, working_items, assessment, execution, retrieved_at = (
        object() for _ in range(6)
    )
    counts = counts if counts is not None else {
        "reconciled_evidence_items": 41,
        "unrelated": object(),
    }
    calls = []

    def default_reconcile(*args, **kwargs):
        calls.append(("reconcile", args, kwargs))
        return reconciliation

    def default_observe(*args, **kwargs):
        calls.append(("observe", args, kwargs))
        return args[2](*args[3:], **kwargs)

    def default_get(*args):
        calls.append(("get", args, {}))
        return items

    reconcile_callable = reconcile or default_reconcile
    result = run_phase_c_reconciliation_stage(
        timings,
        counts,
        requirement_set,
        working_items,
        assessment,
        execution,
        retrieved_at,
        observability_call=observe or default_observe,
        observability_get=get or default_get,
        reconcile_evidence_callable=reconcile_callable,
    )
    return SimpleNamespace(**locals())


def test_result_is_frozen_exact_one_field_contract():
    reconciliation = object()
    result = PhaseCReconciliationStageResult(reconciliation)
    assert [field.name for field in fields(result)] == ["reconciliation"]
    assert result.reconciliation is reconciliation
    with pytest.raises(FrozenInstanceError):
        result.reconciliation = None


@pytest.mark.parametrize("reconciliation", [object(), {}, [], (), None])
def test_exact_call_order_cardinality_arguments_callables_and_success_identity(
        reconciliation):
    h = _run(reconciliation=reconciliation, items=())
    assert [row[0] for row in h.calls] == ["observe", "reconcile", "get"]
    observed = h.calls[0]
    assert observed[1] == (
        h.timings,
        "reconciliation",
        h.reconcile_callable,
        h.requirement_set,
        h.working_items,
        h.assessment,
        h.execution,
    )
    assert all(
        actual is expected
        for actual, expected in zip(
            observed[1],
            (
                h.timings,
                "reconciliation",
                h.reconcile_callable,
                h.requirement_set,
                h.working_items,
                h.assessment,
                h.execution,
            ),
        )
    )
    assert observed[2] == {
        "retrieved_at": h.retrieved_at,
        "target_entity_ids": None,
        "now": h.retrieved_at,
    }
    assert observed[2]["retrieved_at"] is observed[2]["now"] is h.retrieved_at
    assert h.calls[2][1] == (
        reconciliation, "reconciled_evidence_items", ())
    assert h.calls[2][1][0] is reconciliation
    assert h.result.reconciliation is reconciliation


@pytest.mark.parametrize(
    "items,expected",
    [
        ([], 0),
        ([1, 2], 2),
        ((), 0),
        ((1,), 1),
        (ListSubclass([1, 2, 3]), 3),
        (TupleSubclass((1, 2, 3, 4)), 4),
    ],
)
def test_only_list_tuple_and_subclasses_replace_count(items, expected):
    counts = {"reconciled_evidence_items": 97}
    _run(items=items, counts=counts)
    assert counts["reconciled_evidence_items"] == expected


@pytest.mark.parametrize(
    "items",
    [{"x": 1}, UserDict({"x": 1}), "abc", iter((1, 2)), None, object()],
)
def test_other_return_shapes_leave_count_unchanged(items):
    counts = {"reconciled_evidence_items": 97}
    _run(items=items, counts=counts)
    assert counts["reconciled_evidence_items"] == 97


def test_missing_field_default_tuple_writes_zero_and_assignment_not_addition():
    calls = []

    def get(value, key, default):
        calls.append((value, key, default))
        return default

    counts = {"reconciled_evidence_items": 123}
    h = _run(counts=counts, get=get)
    assert calls == [(h.reconciliation, "reconciled_evidence_items", ())]
    assert counts["reconciled_evidence_items"] == 0


@pytest.mark.parametrize("fatal_type", [RuntimeError, Fatal])
@pytest.mark.parametrize("where", ["observe", "reconcile", "get", "length"])
def test_exception_and_baseexception_propagate_with_partial_mutations(
        fatal_type, where):
    error = fatal_type(where)
    timings = {"reconciliation": 43}
    counts = {"reconciled_evidence_items": 47}

    class ExplodingList(list):
        def __len__(self):
            raise error

    def reconcile(*_args, **_kwargs):
        if where == "reconcile":
            raise error
        return object()

    def observe(actual_timings, label, callable_, *args, **kwargs):
        if where == "observe":
            raise error
        actual_timings[label] = 59
        return callable_(*args, **kwargs)

    def get(*_args):
        if where == "get":
            raise error
        return ExplodingList([1]) if where == "length" else []

    with pytest.raises(fatal_type) as raised:
        run_phase_c_reconciliation_stage(
            timings, counts, object(), object(), object(), object(), object(),
            observability_call=observe,
            observability_get=get,
            reconcile_evidence_callable=reconcile,
        )
    assert raised.value is error
    assert timings["reconciliation"] == (43 if where == "observe" else 59)
    assert counts["reconciled_evidence_items"] == 47


def test_no_input_mutation_beyond_owned_timing_and_count_outputs():
    requirement_set = {"requirements": [object()]}
    working_items = [object()]
    assessment = {"assessment": object()}
    execution = {"execution": object()}
    before = (
        requirement_set.copy(), list(working_items), assessment.copy(),
        execution.copy(),
    )

    def observe(_timings, _label, callable_, *args, **kwargs):
        return callable_(*args, **kwargs)

    run_phase_c_reconciliation_stage(
        {}, {}, requirement_set, working_items, assessment, execution, object(),
        observability_call=observe,
        observability_get=lambda *_args: object(),
        reconcile_evidence_callable=lambda *_args, **_kwargs: object(),
    )
    assert (requirement_set, working_items, assessment, execution) == before
