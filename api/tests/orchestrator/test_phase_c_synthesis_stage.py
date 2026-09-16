from dataclasses import FrozenInstanceError, fields

import pytest

from app.orchestrator.phase_c_synthesis_stage import (
    PhaseCSynthesisStageResult,
    run_phase_c_synthesis_stage,
)


class Fatal(BaseException):
    pass


def test_result_is_frozen_exact_one_field_contract():
    synthesis = object()
    result = PhaseCSynthesisStageResult(synthesis)
    assert [field.name for field in fields(result)] == ["synthesis"]
    assert result.synthesis is synthesis
    with pytest.raises(FrozenInstanceError):
        result.synthesis = None


@pytest.mark.parametrize("synthesis", [object(), {}, [], (), None])
def test_exact_call_order_cardinality_arguments_and_raw_return_identity(synthesis):
    timings = {"synthesis": 17}
    reconciliation = object()
    calls = []

    def synthesize(value):
        calls.append(("synthesize", (value,), {}))
        return synthesis

    def observe(*args, **kwargs):
        calls.append(("observe", args, kwargs))
        return args[2](*args[3:], **kwargs)

    result = run_phase_c_synthesis_stage(
        timings,
        reconciliation,
        observability_call=observe,
        synthesize_grounded_evidence_callable=synthesize,
    )

    assert [row[0] for row in calls] == ["observe", "synthesize"]
    assert calls[0][1] == (timings, "synthesis", synthesize, reconciliation)
    assert all(
        actual is expected
        for actual, expected in zip(
            calls[0][1], (timings, "synthesis", synthesize, reconciliation)
        )
    )
    assert calls[0][2] == {}
    assert calls[1][1][0] is reconciliation
    assert result.synthesis is synthesis


@pytest.mark.parametrize("fatal_type", [RuntimeError, Fatal])
@pytest.mark.parametrize("where", ["observe", "synthesize"])
def test_exception_and_baseexception_propagate_with_partial_timing_mutation(
        fatal_type, where):
    error = fatal_type(where)
    timings = {"synthesis": 23}
    reconciliation = {"sentinel": object()}

    def synthesize(value):
        assert value is reconciliation
        if where == "synthesize":
            raise error
        return object()

    def observe(actual_timings, label, callable_, *args):
        if where == "observe":
            raise error
        actual_timings[label] = 29
        return callable_(*args)

    with pytest.raises(fatal_type) as raised:
        run_phase_c_synthesis_stage(
            timings,
            reconciliation,
            observability_call=observe,
            synthesize_grounded_evidence_callable=synthesize,
        )
    assert raised.value is error
    assert timings["synthesis"] == (23 if where == "observe" else 29)
    assert reconciliation == {"sentinel": reconciliation["sentinel"]}


def test_no_input_mutation_or_coercion_copy_and_keyword_only_dependencies():
    timings = {}
    sentinel = object()
    reconciliation = {"items": [sentinel]}
    before = list(reconciliation["items"])

    def observe(actual_timings, label, callable_, value):
        actual_timings[label] = 31
        return callable_(value)

    result = run_phase_c_synthesis_stage(
        timings,
        reconciliation,
        observability_call=observe,
        synthesize_grounded_evidence_callable=lambda value: value,
    )
    assert result.synthesis is reconciliation
    assert reconciliation["items"] == before
    assert reconciliation["items"][0] is sentinel
    with pytest.raises(TypeError):
        run_phase_c_synthesis_stage(
            timings, reconciliation, observe, lambda value: value
        )
