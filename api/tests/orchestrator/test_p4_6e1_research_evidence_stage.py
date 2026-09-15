from dataclasses import FrozenInstanceError, fields

import pytest

from app.orchestrator.p4_6e1_research_evidence_stage import (
    P46e1ResearchEvidenceStageResult,
    run_p4_6e1_research_evidence_stage,
)


class Fatal(BaseException):
    pass


class ExplodingEvidence:
    def __init__(self, error):
        self.error = error

    def __iter__(self):
        raise self.error


def _run(evidence, builder, *, inputs=None):
    values = inputs or tuple(object() for _ in range(4))
    plan, authority, observations, retrieved_at = values
    return run_p4_6e1_research_evidence_stage(
        plan, authority, observations, evidence, retrieved_at,
        build_task_research_evidence_authority_canary_p4_6e1=builder,
    )


def test_result_is_frozen_exact_two_field_contract():
    result = P46e1ResearchEvidenceStageResult(object(), [])
    assert [field.name for field in fields(result)] == [
        "task_research_evidence_authority_p4_6e1",
        "task_research_evidence_units_p4_6e1",
    ]
    with pytest.raises(FrozenInstanceError):
        result.task_research_evidence_authority_p4_6e1 = None


@pytest.mark.parametrize("returned", [[], (), {"shape": "mapping"}, None, object()])
@pytest.mark.parametrize("count", [0, 1, 3])
def test_success_preserves_identity_units_and_exact_call(returned, count):
    calls = []
    inputs = tuple(object() for _ in range(4))
    evidence = [object(), object()]
    units = [object() for _ in range(count)]

    def builder(*args, **kwargs):
        calls.append((args, kwargs))
        for unit in units:
            kwargs["grounded_synthesis_observer"](unit)
        return returned

    result = _run(evidence, builder, inputs=inputs)
    observed = result.task_research_evidence_units_p4_6e1
    assert result.task_research_evidence_authority_p4_6e1 is returned
    assert len(calls) == 1 and observed == units
    assert all(a is b for a, b in zip(observed, units))
    args, kwargs = calls[0]
    assert args[:3] == inputs[:3]
    assert all(args[index] is inputs[index] for index in range(3))
    assert isinstance(args[3], tuple) and args[3] is not evidence
    assert all(a is b for a, b in zip(args[3], evidence))
    assert kwargs["now"] is inputs[3]
    assert kwargs["grounded_synthesis_observer"].__self__ is observed


def test_units_are_fresh_and_inputs_are_not_mutated():
    inputs = tuple(object() for _ in range(4))
    evidence = [object()]
    original = evidence[0]
    first = _run(evidence, lambda *a, **k: object(), inputs=inputs)
    second = _run(evidence, lambda *a, **k: object(), inputs=inputs)
    assert first.task_research_evidence_units_p4_6e1 == []
    assert first.task_research_evidence_units_p4_6e1 is not second.task_research_evidence_units_p4_6e1
    assert evidence == [original] and evidence[0] is original


def test_tuple_exception_skips_builder_and_returns_fresh_empty_fallbacks():
    calls = []
    builder = lambda *a, **k: calls.append((a, k))
    first = _run(ExplodingEvidence(RuntimeError("tuple")), builder)
    second = _run(ExplodingEvidence(RuntimeError("tuple")), builder)
    assert calls == []
    assert first.task_research_evidence_authority_p4_6e1 is None
    assert first.task_research_evidence_units_p4_6e1 == []
    assert first.task_research_evidence_units_p4_6e1 is not second.task_research_evidence_units_p4_6e1


@pytest.mark.parametrize("count", [0, 1, 3])
def test_builder_exception_discards_partial_units(count):
    partial = []

    def builder(*args, **kwargs):
        partial.append(kwargs["grounded_synthesis_observer"].__self__)
        for _ in range(count):
            kwargs["grounded_synthesis_observer"](object())
        raise RuntimeError("builder")

    result = _run([], builder)
    assert result.task_research_evidence_authority_p4_6e1 is None
    assert result.task_research_evidence_units_p4_6e1 == []
    assert result.task_research_evidence_units_p4_6e1 is not partial[0]
    assert len(partial[0]) == count


@pytest.mark.parametrize("source", ["tuple", "builder"])
def test_baseexception_propagates(source):
    fatal = Fatal("fatal")
    evidence = ExplodingEvidence(fatal) if source == "tuple" else []

    def builder(*args, **kwargs):
        raise fatal

    with pytest.raises(Fatal) as raised:
        _run(evidence, builder)
    assert raised.value is fatal
