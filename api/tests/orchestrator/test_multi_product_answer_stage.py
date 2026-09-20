"""Direct tests for the bounded multi-product answer stage."""

from __future__ import annotations

import copy

import pytest

from app.orchestrator.multi_product_answer_stage import (
    MultiProductAnswerStageResult,
    run_multi_product_answer_stage,
)


class Fatal(BaseException):
    pass


@pytest.mark.parametrize("delegated_answer", [object(), "", False, 0, None])
def test_delegates_once_with_exact_inputs_and_preserves_return_identity(
    delegated_answer,
):
    results = [{"action": "product_assistant", "result": {}}]
    requested = {"price", "inventory"}
    before_results = copy.deepcopy(results)
    before_requested = requested.copy()
    calls = []

    def build(received_results, received_requested):
        calls.append((received_results, received_requested))
        return delegated_answer

    result = run_multi_product_answer_stage(results, requested, build)

    assert isinstance(result, MultiProductAnswerStageResult)
    assert result.delegated_answer is delegated_answer
    assert calls == [(results, requested)]
    assert calls[0][0] is results
    assert calls[0][1] is requested
    assert results == before_results
    assert requested == before_requested


@pytest.mark.parametrize("error", [RuntimeError("exception"), Fatal("fatal")])
def test_propagates_all_throwables_unchanged(error):
    def build(*_args):
        raise error

    with pytest.raises(type(error), match=str(error)) as raised:
        run_multi_product_answer_stage([], set(), build)

    assert raised.value is error


def test_result_contract_is_frozen_and_has_exactly_one_field():
    result = MultiProductAnswerStageResult(delegated_answer=None)

    assert tuple(result.__dataclass_fields__) == ("delegated_answer",)
    with pytest.raises(AttributeError):
        result.delegated_answer = "changed"
