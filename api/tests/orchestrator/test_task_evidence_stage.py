from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
import pytest

from app.orchestrator.task_evidence_stage import (
    TaskEvidenceStageResult,
    run_task_evidence_stage,
)


class OrdinaryError(Exception):
    pass


class TupleError(Exception):
    pass


class _HostileEvidence:
    def __iter__(self):
        raise TupleError("tuple")


def _run(*, shadow_return=(), authority_return=None, shadow_error=None,
         authority_error=None, working=None, calls=None):
    calls = [] if calls is None else calls
    plan = {"plan": [object()]}
    evidence = [object(), object()] if working is None else working
    stamp = object()

    def shadow(actual_plan, actual_evidence, *, now):
        calls.append(("shadow", actual_plan, actual_evidence, now))
        if shadow_error is not None:
            raise shadow_error
        return shadow_return

    def authority(actual_plan, actual_evidence, *, now, shadow_assessments):
        calls.append(("authority", actual_plan, actual_evidence, now,
                      shadow_assessments))
        if authority_error is not None:
            raise authority_error
        return authority_return

    result = run_task_evidence_stage(
        plan,
        evidence,
        stamp,
        assess_intent_task_evidence_shadow=shadow,
        build_task_evidence_authority_canary_p4_6c=authority,
    )
    return result, calls, plan, evidence, stamp


def test_frozen_exact_two_field_return_contract():
    result, *_ = _run()
    assert [field.name for field in fields(result)] == [
        "task_evidence_assessments_shadow",
        "task_evidence_authority_p4_6c",
    ]
    with pytest.raises(FrozenInstanceError):
        result.task_evidence_authority_p4_6c = object()


@pytest.mark.parametrize("shadow_return", [[], (), {"shape": "mapping"}, None, object()])
def test_shadow_success_and_authority_success_preserve_identity_and_exact_calls(
    shadow_return,
):
    authority_return = object()
    result, calls, plan, evidence, stamp = _run(
        shadow_return=shadow_return,
        authority_return=authority_return,
    )
    assert result.task_evidence_assessments_shadow is shadow_return
    assert result.task_evidence_authority_p4_6c is authority_return
    assert [call[0] for call in calls] == ["shadow", "authority"]
    assert calls[0][1] is plan
    assert calls[0][2] is evidence
    assert calls[0][3] is stamp
    assert calls[1][1] is plan
    assert calls[1][2] == tuple(evidence)
    assert all(actual is expected for actual, expected in zip(calls[1][2], evidence))
    assert calls[1][3] is stamp
    assert calls[1][4] is shadow_return


def test_shadow_exception_uses_fresh_list_and_authority_still_runs_once():
    first, first_calls, *_ = _run(shadow_error=OrdinaryError("shadow"))
    second, second_calls, *_ = _run(shadow_error=OrdinaryError("shadow"))
    assert first.task_evidence_assessments_shadow == []
    assert second.task_evidence_assessments_shadow == []
    assert first.task_evidence_assessments_shadow is not second.task_evidence_assessments_shadow
    assert first_calls[1][4] is first.task_evidence_assessments_shadow
    assert [call[0] for call in first_calls] == ["shadow", "authority"]
    assert [call[0] for call in second_calls] == ["shadow", "authority"]


def test_authority_exception_returns_none_and_preserves_shadow():
    shadow_return = object()
    result, calls, *_ = _run(
        shadow_return=shadow_return,
        authority_error=OrdinaryError("authority"),
    )
    assert result.task_evidence_assessments_shadow is shadow_return
    assert result.task_evidence_authority_p4_6c is None
    assert [call[0] for call in calls] == ["shadow", "authority"]


def test_tuple_coercion_exception_is_authority_local_and_skips_authority_call():
    shadow_return = object()
    result, calls, *_ = _run(shadow_return=shadow_return, working=_HostileEvidence())
    assert result.task_evidence_assessments_shadow is shadow_return
    assert result.task_evidence_authority_p4_6c is None
    assert [call[0] for call in calls] == ["shadow"]


@pytest.mark.parametrize("target", ["shadow", "tuple", "authority"])
def test_baseexception_propagates_from_each_zone(target):
    fatal = KeyboardInterrupt(target)
    kwargs = {"shadow_return": object(), "authority_return": object()}
    if target == "shadow":
        kwargs["shadow_error"] = fatal
    elif target == "tuple":
        kwargs["working"] = _BaseExceptionEvidence(fatal)
    else:
        kwargs["authority_error"] = fatal
    with pytest.raises(KeyboardInterrupt, match=target):
        _run(**kwargs)


class _BaseExceptionEvidence:
    def __init__(self, error):
        self.error = error

    def __iter__(self):
        raise self.error


def test_inputs_are_not_mutated():
    plan = {"plan": ["value"]}
    evidence = [{"evidence": ["value"]}]
    stamp = {"timestamp": ["value"]}
    before_plan = {"plan": list(plan["plan"])}
    before_evidence = [{"evidence": list(evidence[0]["evidence"])}]
    before_stamp = {"timestamp": list(stamp["timestamp"])}
    calls = []

    def shadow(*args, **kwargs):
        calls.append((args, kwargs))
        return object()

    def authority(*args, **kwargs):
        calls.append((args, kwargs))
        return object()

    result = run_task_evidence_stage(
        plan,
        evidence,
        stamp,
        assess_intent_task_evidence_shadow=shadow,
        build_task_evidence_authority_canary_p4_6c=authority,
    )
    assert plan == before_plan
    assert evidence == before_evidence
    assert stamp == before_stamp
    assert calls[0][1]["now"] is calls[1][1]["now"] is stamp
    assert isinstance(result, TaskEvidenceStageResult)
