from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError, fields

import pytest

from app.orchestrator.cp13_research_semantics_stage import (
    Cp13ResearchSemanticsStageResult,
    run_cp13_research_semantics_stage,
)


class OrdinaryError(Exception):
    pass


class FatalError(BaseException):
    pass


FALLBACK = {
    "contract_version": "promati.orchestrator.task_research_semantics.cp13.v1",
    "evaluated": False,
    "authoritative": False,
    "authority_scope": "intent_task_research_eligibility_only",
    "public_answer_authority": False,
    "legacy_generic_research_allowed": False,
    "allowed_task_ids": [],
    "tasks": [],
    "reason": "internal_error_fail_closed",
}


def test_frozen_exact_one_field_return_contract():
    result = Cp13ResearchSemanticsStageResult(object())
    assert [field.name for field in fields(result)] == [
        "task_research_semantics_cp13"
    ]
    with pytest.raises(FrozenInstanceError):
        result.task_research_semantics_cp13 = object()


@pytest.mark.parametrize("value", [[], (), {"shape": "mapping"}, None, object()])
def test_success_preserves_identity_and_exact_call_contract(value):
    calls = []
    plan, execution, authority = object(), object(), object()

    def dependency(*args, **kwargs):
        calls.append((args, kwargs))
        return value

    result = run_cp13_research_semantics_stage(
        plan, execution, authority,
        build_task_research_semantics=dependency,
    )
    assert calls == [((plan, execution, authority), {})]
    assert result.task_research_semantics_cp13 is value


def test_ordinary_exception_returns_exact_fallback():
    def dependency(*args):
        raise OrdinaryError("ordinary")

    result = run_cp13_research_semantics_stage(
        object(), object(), object(),
        build_task_research_semantics=dependency,
    )
    fallback = result.task_research_semantics_cp13
    assert fallback == FALLBACK
    assert set(fallback) == set(FALLBACK)


def test_fallback_dict_and_lists_are_fresh_independent_and_mutation_isolated():
    def dependency(*args):
        raise OrdinaryError("ordinary")

    first = run_cp13_research_semantics_stage(
        object(), object(), object(), build_task_research_semantics=dependency,
    ).task_research_semantics_cp13
    second = run_cp13_research_semantics_stage(
        object(), object(), object(), build_task_research_semantics=dependency,
    ).task_research_semantics_cp13
    assert first == second == FALLBACK and first is not second
    assert first["allowed_task_ids"] is not first["tasks"]
    assert first["allowed_task_ids"] is not second["allowed_task_ids"]
    assert first["tasks"] is not second["tasks"]
    first["allowed_task_ids"].append("mutation")
    first["tasks"].append({"mutation": True})
    assert second == FALLBACK


def test_baseexception_propagates():
    fatal = FatalError("fatal")

    def dependency(*args):
        raise fatal

    with pytest.raises(FatalError, match="fatal"):
        run_cp13_research_semantics_stage(
            object(), object(), object(), build_task_research_semantics=dependency,
        )


def test_inputs_are_not_mutated():
    plan = {"plan": [[1]]}
    execution = {"execution": [[2]]}
    authority = {"authority": [[3]]}
    before = deepcopy((plan, execution, authority))

    run_cp13_research_semantics_stage(
        plan, execution, authority,
        build_task_research_semantics=lambda *args: object(),
    )
    assert (plan, execution, authority) == before
