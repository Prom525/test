from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError, fields

import pytest

from app.orchestrator.task_research_decision_stage import (
    TaskResearchDecisionStageResult,
    run_task_research_decision_stage,
)


class OrdinaryError(Exception):
    pass


def _run(*, shadow_return=(), authority_return=None, shadow_error=None,
         authority_error=None, assessments=None, authority_input=None, calls=None):
    calls = [] if calls is None else calls
    assessments = object() if assessments is None else assessments
    authority_input = object() if authority_input is None else authority_input

    def shadow(actual_assessments):
        calls.append(("shadow", actual_assessments))
        if shadow_error is not None:
            raise shadow_error
        return shadow_return

    def authority(actual_authority, actual_shadow):
        calls.append(("authority", actual_authority, actual_shadow))
        if authority_error is not None:
            raise authority_error
        return authority_return

    result = run_task_research_decision_stage(
        assessments,
        authority_input,
        derive_intent_task_research_decisions_shadow=shadow,
        build_task_research_authority_canary_p4_6d1=authority,
    )
    return result, calls, assessments, authority_input


def test_frozen_exact_two_field_return_contract():
    result, *_ = _run()
    assert [field.name for field in fields(result)] == [
        "task_research_decisions_shadow",
        "task_research_authority_p4_6d1",
    ]
    with pytest.raises(FrozenInstanceError):
        result.task_research_authority_p4_6d1 = object()


@pytest.mark.parametrize("shadow_return", [[], (), {"shape": "mapping"}, None, object()])
def test_success_preserves_both_output_identities_and_exact_order_and_arguments(
    shadow_return,
):
    authority_return = object()
    result, calls, assessments, authority_input = _run(
        shadow_return=shadow_return, authority_return=authority_return
    )
    assert result.task_research_decisions_shadow is shadow_return
    assert result.task_research_authority_p4_6d1 is authority_return
    assert [call[0] for call in calls] == ["shadow", "authority"]
    assert calls[0][1] is assessments
    assert calls[1][1] is authority_input
    assert calls[1][2] is shadow_return


def test_shadow_exception_uses_fresh_list_and_authority_receives_same_fallback():
    first, first_calls, *_ = _run(shadow_error=OrdinaryError("shadow"))
    second, second_calls, *_ = _run(shadow_error=OrdinaryError("shadow"))
    first_shadow = first.task_research_decisions_shadow
    second_shadow = second.task_research_decisions_shadow
    assert first_shadow == second_shadow == []
    assert first_shadow is not second_shadow
    assert first_calls[1][2] is first_shadow
    assert second_calls[1][2] is second_shadow
    assert [call[0] for call in first_calls] == ["shadow", "authority"]


def test_authority_exception_returns_none_and_preserves_shadow():
    shadow_return = object()
    result, calls, *_ = _run(
        shadow_return=shadow_return, authority_error=OrdinaryError("authority")
    )
    assert result.task_research_decisions_shadow is shadow_return
    assert result.task_research_authority_p4_6d1 is None
    assert [call[0] for call in calls] == ["shadow", "authority"]


def test_both_ordinary_exceptions_fail_open_independently():
    result, calls, *_ = _run(
        shadow_error=OrdinaryError("shadow"),
        authority_error=OrdinaryError("authority"),
    )
    assert result.task_research_decisions_shadow == []
    assert calls[1][2] is result.task_research_decisions_shadow
    assert result.task_research_authority_p4_6d1 is None


@pytest.mark.parametrize("target", ["shadow", "authority"])
def test_baseexception_propagates(target):
    fatal = KeyboardInterrupt(target)
    with pytest.raises(KeyboardInterrupt, match=target):
        _run(
            shadow_return=object(),
            shadow_error=fatal if target == "shadow" else None,
            authority_error=fatal if target == "authority" else None,
        )


def test_inputs_are_not_mutated():
    assessments = {"assessments": [["value"]]}
    authority_input = {"authority": [["value"]]}
    before = deepcopy((assessments, authority_input))
    result, calls, *_ = _run(
        shadow_return=object(), authority_return=object(),
        assessments=assessments, authority_input=authority_input,
    )
    assert (assessments, authority_input) == before
    assert calls[0][1] is assessments
    assert calls[1][1] is authority_input
    assert isinstance(result, TaskResearchDecisionStageResult)
