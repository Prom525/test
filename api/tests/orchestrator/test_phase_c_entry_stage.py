from __future__ import annotations

from dataclasses import fields
from pathlib import Path
from types import SimpleNamespace
import ast

import pytest

from app.orchestrator.phase_c_entry_stage import (
    PhaseCEntryResult,
    prepare_phase_c_entry,
)


def _run(*, requirement=object(), clarification=False, results=(), typed=(),
         outputs=None, error_at=None, state=None):
    calls = []
    timings = {}
    counts = {}
    plan = SimpleNamespace(intent="intent-object", clarification_required=clarification)
    stamp = object()
    if state is not None:
        state.update(calls=calls, timings=timings, counts=counts)

    def lookup(intent):
        calls.append(("lookup", intent))
        return requirement

    def observe(actual_timings, label, function, *args, **kwargs):
        calls.append(("observe", actual_timings, label, function, args, kwargs))
        return function(*args, **kwargs)

    def utc_now():
        calls.append(("utc_now",))
        return stamp

    def clock():
        calls.append(("clock",))
        return 12.5

    def elapsed(started):
        calls.append(("elapsed", started))
        return 37

    def normalize(item, *, retrieved_at):
        calls.append(("normalize", item, retrieved_at))
        index = len([call for call in calls if call[0] == "normalize"]) - 1
        if index == error_at:
            raise RuntimeError(f"normalize-{index}")
        return (outputs or {}).get(item, ())

    value = prepare_phase_c_entry(
        plan, results, typed, timings, counts,
        observability_call=observe,
        get_requirement_set=lookup,
        utc_now=utc_now,
        observability_now=clock,
        observability_elapsed_ms=elapsed,
        normalize_execution_result_evidence=normalize,
    )
    return value, calls, timings, counts, plan, requirement, stamp, lookup


def test_lookup_exact_label_callable_and_intent():
    result, calls, timings, _, plan, _, _, lookup = _run()
    observed = calls[0]
    assert observed == (
        "observe", timings, "evidence_requirement_lookup", lookup,
        (plan.intent,), {},
    )
    assert result is not None


@pytest.mark.parametrize(
    ("requirement", "clarification", "results"),
    [
        (None, False, ()),
        (object(), True, ()),
        (object(), False, ({"result": {"status": "clarification_required"}},)),
        (object(), False, ({"result": {"status": "CLARIFICATION_REQUIRED"}},)),
        (object(), False, ({"result": {"status": "Clarification_Required"}},)),
    ],
)
def test_closed_gate_returns_none_without_timestamp_or_normalization(
    requirement, clarification, results
):
    result, calls, timings, counts, *_ = _run(
        requirement=requirement, clarification=clarification, results=results
    )
    assert result is None
    assert [call[0] for call in calls] == ["observe", "lookup"]
    assert timings == {} and counts == {}


@pytest.mark.parametrize(
    "results",
    [
        ("malformed",),
        ({"result": "not-a-dict"},),
        ({"result": None},),
        ({"result": {"status": " clarification_required"}},),
        ({"result": {"status": "clarification_required "}},),
    ],
)
def test_malformed_and_whitespace_statuses_do_not_close_gate(results):
    result, calls, *_ = _run(results=results)
    assert result is not None
    assert [call[0] for call in calls] == [
        "observe", "lookup", "utc_now", "clock", "elapsed",
    ]


def test_one_timestamp_typed_only_ordered_flatten_and_result_identity():
    result, calls, timings, counts, _, requirement, stamp, _ = _run(
        results=({"raw": object()},),
        typed=("typed-a", "typed-b"),
        outputs={"typed-a": ("a1", "a2"), "typed-b": ("b1",)},
    )
    assert isinstance(result, PhaseCEntryResult)
    assert [field.name for field in fields(result)] == [
        "requirement_set", "retrieved_at", "initial_evidence_items",
        "working_evidence_items",
    ]
    assert result.requirement_set is requirement
    assert result.retrieved_at is stamp
    assert result.initial_evidence_items == ("a1", "a2", "b1")
    assert result.working_evidence_items is result.initial_evidence_items
    normalizes = [call for call in calls if call[0] == "normalize"]
    assert [(call[1], call[2]) for call in normalizes] == [
        ("typed-a", stamp), ("typed-b", stamp),
    ]
    assert [call[0] for call in calls].count("utc_now") == 1
    assert timings == {"evidence_normalization": 37}
    assert counts == {"initial_evidence_items": 3}


@pytest.mark.parametrize("error_at", [0, 1])
def test_normalization_exception_propagates_and_finally_records_empty_tuple(error_at):
    state = {}
    with pytest.raises(RuntimeError, match=f"^normalize-{error_at}$"):
        _run(
            typed=("typed-a", "typed-b"),
            outputs={"typed-a": ("a1",), "typed-b": ("b1",)},
            error_at=error_at,
            state=state,
        )
    assert len([call for call in state["calls"] if call[0] == "normalize"]) == error_at + 1
    assert state["timings"] == {"evidence_normalization": 37}
    assert state["counts"] == {"initial_evidence_items": 0}


def test_exception_finally_uses_service_functions_and_zero_count():
    calls = []
    timings = {}
    counts = {}
    with pytest.raises(RuntimeError, match="boom"):
        prepare_phase_c_entry(
            SimpleNamespace(intent="i", clarification_required=False), (), (1,),
            timings, counts,
            observability_call=lambda t, l, f, *a: f(*a),
            get_requirement_set=lambda i: object(),
            utc_now=lambda: object(),
            observability_now=lambda: calls.append("now") or 4.0,
            observability_elapsed_ms=lambda start: calls.append(("elapsed", start)) or 9,
            normalize_execution_result_evidence=lambda *a, **k: (_ for _ in ()).throw(
                RuntimeError("boom")
            ),
        )
    assert calls == ["now", ("elapsed", 4.0)]
    assert timings == {"evidence_normalization": 9}
    assert counts == {"initial_evidence_items": 0}


def test_leaf_imports_and_single_service_entry_call_with_coverage_retained():
    stage = Path("app/orchestrator/phase_c_entry_stage.py").read_text(encoding="utf-8")
    service = Path("app/orchestrator/service.py").read_text(encoding="utf-8")
    tree = ast.parse(stage)
    roots = {
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert roots == {"dataclasses", "typing"}
    for forbidden in ("service", "fastapi", "database", "settings", "network"):
        assert forbidden not in stage.lower()
    assert service.count("prepare_phase_c_entry(") == 1
    assert '"evidence_requirement_lookup"' not in service
    assert "run_product_family_recovery_stage(" in service
    stage_call = service.index("phase_c_entry = prepare_phase_c_entry(")
    bind = service.index("requirement_set = phase_c_entry.requirement_set", stage_call)
    coverage = service.index("run_product_family_recovery_stage(", bind)
    assert stage_call < bind < coverage
    assert "_p4_15cp3c_previous_run_orchestrator = run_orchestrator" in service
    assert "_p4_15cp4b_previous_run_orchestrator = run_orchestrator" in service
    assert "_p4_15cp4f_previous_run_orchestrator = run_orchestrator" in service
