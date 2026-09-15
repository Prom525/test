from dataclasses import FrozenInstanceError, fields

import pytest

from app.orchestrator.p4_6e3_synthesis_coverage_stage import (
    P46e3SynthesisCoverageStageResult,
    run_p4_6e3_synthesis_coverage_stage,
)


class Fatal(BaseException):
    pass


class HostileEvidence:
    def __init__(self, error):
        self.error = error

    def __iter__(self):
        raise self.error


def test_result_is_frozen_exact_one_field_contract():
    marker = object()
    result = P46e3SynthesisCoverageStageResult(marker)
    assert [field.name for field in fields(result)] == [
        "task_grounded_synthesis_coverage_authority_p4_6e3",
    ]
    assert result.task_grounded_synthesis_coverage_authority_p4_6e3 is marker
    with pytest.raises(FrozenInstanceError):
        result.task_grounded_synthesis_coverage_authority_p4_6e3 = None


@pytest.mark.parametrize("returned", [{}, [], (), None, object()])
def test_exact_call_tuple_order_identity_and_success_identity(returned):
    plan, authority_c, authority_e2, retrieved_at = (object() for _ in range(4))
    evidence = [object(), object()]
    before = list(evidence)
    calls = []

    def builder(*args, **kwargs):
        calls.append((args, kwargs))
        return returned

    result = run_p4_6e3_synthesis_coverage_stage(
        plan, authority_c, authority_e2, evidence, retrieved_at,
        build_task_grounded_synthesis_coverage_authority_canary_p4_6e3=builder,
    )

    assert result.task_grounded_synthesis_coverage_authority_p4_6e3 is returned
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args[:3] == (plan, authority_c, authority_e2)
    assert args[0] is plan and args[1] is authority_c and args[2] is authority_e2
    assert isinstance(args[3], tuple) and args[3] is not evidence
    assert all(actual is expected for actual, expected in zip(args[3], evidence))
    assert kwargs == {"now": retrieved_at}
    assert evidence == before
    assert all(actual is expected for actual, expected in zip(evidence, before))


@pytest.mark.parametrize("at", ["iteration", "call"])
def test_exception_fails_open_to_exact_none(at):
    error = RuntimeError(at)

    def builder(*_args, **_kwargs):
        raise error

    result = run_p4_6e3_synthesis_coverage_stage(
        object(), object(), object(),
        HostileEvidence(error) if at == "iteration" else [], object(),
        build_task_grounded_synthesis_coverage_authority_canary_p4_6e3=builder,
    )
    assert result.task_grounded_synthesis_coverage_authority_p4_6e3 is None


@pytest.mark.parametrize("at", ["iteration", "call"])
def test_baseexception_propagates(at):
    fatal = Fatal(at)

    def builder(*_args, **_kwargs):
        raise fatal

    with pytest.raises(Fatal) as raised:
        run_p4_6e3_synthesis_coverage_stage(
            object(), object(), object(),
            HostileEvidence(fatal) if at == "iteration" else [], object(),
            build_task_grounded_synthesis_coverage_authority_canary_p4_6e3=builder,
        )
    assert raised.value is fatal
