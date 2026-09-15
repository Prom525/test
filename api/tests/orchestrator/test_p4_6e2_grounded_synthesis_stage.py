from dataclasses import FrozenInstanceError, fields

import pytest

from app.orchestrator.p4_6e2_grounded_synthesis_stage import (
    P46e2GroundedSynthesisStageResult,
    run_p4_6e2_grounded_synthesis_stage,
)


class Fatal(BaseException):
    pass


def test_result_is_frozen_exact_one_field_contract():
    marker = object()
    result = P46e2GroundedSynthesisStageResult(marker)
    assert [field.name for field in fields(result)] == [
        "task_grounded_synthesis_authority_p4_6e2",
    ]
    assert result.task_grounded_synthesis_authority_p4_6e2 is marker
    with pytest.raises(FrozenInstanceError):
        result.task_grounded_synthesis_authority_p4_6e2 = None


@pytest.mark.parametrize("returned", [[], (), {"shape": "mapping"}, None, object()])
def test_success_preserves_identity_and_exact_call(returned):
    authority, units = object(), [object(), object()]
    before = list(units)
    calls = []

    def builder(*args, **kwargs):
        calls.append((args, kwargs))
        return returned

    result = run_p4_6e2_grounded_synthesis_stage(
        authority,
        units,
        build_task_grounded_synthesis_authority_canary_p4_6e2=builder,
    )

    assert result.task_grounded_synthesis_authority_p4_6e2 is returned
    assert calls == [((authority, units), {})]
    assert calls[0][0][0] is authority and calls[0][0][1] is units
    assert units == before
    assert all(actual is expected for actual, expected in zip(units, before))


def test_exception_fails_open_to_exact_none():
    def builder(*_args, **_kwargs):
        raise RuntimeError("builder")

    result = run_p4_6e2_grounded_synthesis_stage(
        object(), [],
        build_task_grounded_synthesis_authority_canary_p4_6e2=builder,
    )
    assert result.task_grounded_synthesis_authority_p4_6e2 is None


def test_baseexception_propagates():
    fatal = Fatal("fatal")

    def builder(*_args, **_kwargs):
        raise fatal

    with pytest.raises(Fatal) as raised:
        run_p4_6e2_grounded_synthesis_stage(
            object(), [],
            build_task_grounded_synthesis_authority_canary_p4_6e2=builder,
        )
    assert raised.value is fatal


def test_independent_calls_have_no_state_leakage():
    first_marker, second_marker = object(), object()
    first = run_p4_6e2_grounded_synthesis_stage(
        object(), [],
        build_task_grounded_synthesis_authority_canary_p4_6e2=(
            lambda *_args, **_kwargs: first_marker
        ),
    )
    second = run_p4_6e2_grounded_synthesis_stage(
        object(), [],
        build_task_grounded_synthesis_authority_canary_p4_6e2=(
            lambda *_args, **_kwargs: second_marker
        ),
    )
    assert first.task_grounded_synthesis_authority_p4_6e2 is first_marker
    assert second.task_grounded_synthesis_authority_p4_6e2 is second_marker
