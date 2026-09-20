"""Characterize the legacy single-family product presentation boundary.

These tests deliberately exercise the code reached after the multi-product
stage declines delegation.  They are the frozen contract for a later 4B2
mechanical extraction; they do not prescribe an implementation shape.
"""

from __future__ import annotations

import copy
import inspect

import pytest

from app.orchestrator import service
from app.orchestrator.multi_product_answer_stage import MultiProductAnswerStageResult


class Fatal(BaseException):
    """Non-Exception sentinel used to characterize propagation."""


def _item(action="product_assistant", *, context_type=None, result=None):
    payload = {} if result is None else result
    if context_type is not None and isinstance(payload, dict):
        payload["context_type"] = context_type
    return {"action": action, "result": payload}


def _family(**overrides):
    row = {
        "family_code": "F-SYNTH",
        "family_name": "Synthetic family",
        "strengths": "Strong synthetic property",
        "limitations": "Synthetic limitation",
        "selection_advice": "Choose by synthetic conditions",
    }
    row.update(overrides)
    return row


def _decline_multi(monkeypatch, calls=None):
    def decline(results, requested, builder):
        if calls is not None:
            calls.append(("multi", results, requested, builder))
        return MultiProductAnswerStageResult(delegated_answer=None)

    monkeypatch.setattr(service, "run_multi_product_answer_stage", decline)


@pytest.mark.parametrize("delegated", ["", False, 0, [], {}, object()])
def test_every_non_none_delegated_value_returns_at_boundary(monkeypatch, delegated):
    def stage(*_args):
        return MultiProductAnswerStageResult(delegated_answer=delegated)

    monkeypatch.setattr(service, "run_multi_product_answer_stage", stage)
    monkeypatch.setattr(
        service,
        "_build_product_article_lines",
        lambda *_args, **_kwargs: pytest.fail("single-family boundary was reached"),
    )

    assert service._build_user_answer([_item(result={"family_context": {}})]) is delegated


@pytest.mark.parametrize(
    "result",
    [None, "specialist", [], 7, {"family_context": None}, {"family_context": []}],
)
def test_specialist_and_family_context_shape_gates_fall_through(monkeypatch, result):
    _decline_multi(monkeypatch)
    item = {"action": "product_assistant", "result": result}
    before = copy.deepcopy(item)

    assert service._build_user_answer([item]) is None
    assert item == before


@pytest.mark.parametrize(
    "rows",
    [None, {}, "rows", (), [], [None], ["family"], [7]],
)
def test_family_results_requires_nonempty_list_with_mapping_first(monkeypatch, rows):
    _decline_multi(monkeypatch)
    results = [_item(result={"family_context": {"results": rows}})]
    before = copy.deepcopy(results)

    assert service._build_user_answer(results) is None
    assert results == before


def test_only_first_family_is_selected_and_later_entries_are_untouched(monkeypatch):
    _decline_multi(monkeypatch)
    rows = [
        _family(family_name="First family", strengths=None, limitations=None, selection_advice=None),
        _family(family_name="Second family"),
        _family(family_name="First family"),
    ]
    results = [_item(result={"family_context": {"results": rows}})]
    before = copy.deepcopy(results)

    assert service._build_user_answer(results) == "First family"
    assert results == before


@pytest.mark.parametrize(
    ("family", "expected"),
    [
        (_family(), "Synthetic family\n\nSterktes: Strong synthetic property\n\nBeperkingen: Synthetic limitation\n\nSelectieadvies: Choose by synthetic conditions"),
        (_family(family_name="", family_code="CODE-ONLY", strengths=0, limitations=False, selection_advice=[]), "CODE-ONLY"),
        (_family(family_name=42, family_code="ignored", strengths=7, limitations=("x",), selection_advice={"k": "v"}), "42\n\nSterktes: 7\n\nBeperkingen: ('x',)\n\nSelectieadvies: {'k': 'v'}"),
        (_family(family_name=None, family_code=None, strengths="S", limitations=None, selection_advice="A"), "\nSterktes: S\n\nSelectieadvies: A"),
        (_family(family_name=None, family_code=None, strengths=None, limitations=None, selection_advice=None), None),
    ],
)
def test_exact_family_field_fallback_truthiness_and_line_order(monkeypatch, family, expected):
    _decline_multi(monkeypatch)
    results = [_item(result={"family_context": {"results": [family]}})]

    assert service._build_user_answer(results) == expected


@pytest.mark.parametrize("selector", ["action", "context_type"])
def test_product_aliases_reach_identical_single_family_boundary(monkeypatch, selector):
    calls = []
    _decline_multi(monkeypatch, calls)
    action = "product_assistant" if selector == "action" else "synthetic_other"
    context_type = "product_assistant" if selector == "context_type" else None
    results = [_item(action, context_type=context_type, result={"family_context": {"results": [_family()]}})]

    assert service._build_user_answer(results).startswith("Synthetic family")
    assert len(calls) == 1


def test_result_order_fallthrough_and_first_successful_product_wins(monkeypatch):
    calls = []
    _decline_multi(monkeypatch, calls)
    results = [
        _item(result={"family_context": {"results": []}}),
        _item(result={"family_context": {"results": [_family(family_name="Winner")]}}),
        _item(result={"family_context": {"results": [_family(family_name="Never reached")]}}),
    ]

    assert service._build_user_answer(results) == (
        "Winner\n\nSterktes: Strong synthetic property\n\n"
        "Beperkingen: Synthetic limitation\n\n"
        "Selectieadvies: Choose by synthetic conditions"
    )
    assert [call[1] for call in calls] == [results, results]


def test_article_dependency_call_order_cardinality_identity_and_normalized_flags(monkeypatch):
    calls = []
    helper_return = ["Actuele artikelinformatie:", "- Synthetic article"]
    result = {"family_context": {"results": [_family()]}}
    results = [_item(result=result)]
    requested = [" INVENTORY ", "inventory", " Price", "", "  "]
    before_results = copy.deepcopy(results)
    before_requested = copy.deepcopy(requested)
    before_helper = copy.deepcopy(helper_return)
    _decline_multi(monkeypatch, calls)

    def articles(specialist_result, *, include_inventory, include_price):
        calls.append(("articles", specialist_result, include_inventory, include_price))
        return helper_return

    monkeypatch.setattr(service, "_build_product_article_lines", articles)

    answer = service._build_user_answer(results, requested)

    assert calls == [
        ("multi", results, {"inventory", "price"}, service._build_multi_product_user_answer),
        ("articles", result, True, True),
    ]
    assert answer.endswith("\n\nActuele artikelinformatie:\n- Synthetic article")
    assert results == before_results
    assert requested == before_requested
    assert helper_return == before_helper


@pytest.mark.parametrize(
    ("requested", "flags"),
    [([], (False, False)), (["inventory"], (True, False)), (["PRICE"], (False, True)), ([" stock ", "cost"], (False, False))],
)
def test_article_dependency_is_called_only_for_normalized_supported_requests(monkeypatch, requested, flags):
    _decline_multi(monkeypatch)
    calls = []

    def articles(_result, *, include_inventory, include_price):
        calls.append((include_inventory, include_price))
        return []

    monkeypatch.setattr(service, "_build_product_article_lines", articles)
    result = service._build_user_answer([_item(result={"family_context": {"results": [_family()]}})], requested)

    assert result.startswith("Synthetic family")
    assert calls == ([flags] if any(flags) else [])


@pytest.mark.parametrize(
    ("helper_return", "suffix"),
    [
        ([], "Synthetic family"),
        (None, "Synthetic family"),
        ((), "Synthetic family"),
        (["line one", "line two"], "Synthetic family\n\nline one\nline two"),
        (("tuple one", "tuple two"), "Synthetic family\n\ntuple one\ntuple two"),
        ("XY", "Synthetic family\n\nX\nY"),
        ({"first": 1, "second": 2}, "Synthetic family\n\nfirst\nsecond"),
    ],
)
def test_article_helper_returns_are_truthiness_checked_then_unconverted_splatted(monkeypatch, helper_return, suffix):
    _decline_multi(monkeypatch)
    family = _family(strengths=None, limitations=None, selection_advice=None)
    monkeypatch.setattr(service, "_build_product_article_lines", lambda *_args, **_kwargs: helper_return)

    assert service._build_user_answer([_item(result={"family_context": {"results": [family]}})], ["price"]) == suffix


@pytest.mark.parametrize("helper_return", [[7], ["valid", 7]])
def test_non_string_article_elements_reach_join_unconverted_and_raise(monkeypatch, helper_return):
    _decline_multi(monkeypatch)
    monkeypatch.setattr(service, "_build_product_article_lines", lambda *_args, **_kwargs: helper_return)

    with pytest.raises(TypeError, match="sequence item"):
        service._build_user_answer([_item(result={"family_context": {"results": [_family()]}})], ["inventory"])


@pytest.mark.parametrize("error", [RuntimeError("synthetic exception"), Fatal("synthetic fatal")])
def test_article_dependency_does_not_catch_exception_or_baseexception(monkeypatch, error):
    _decline_multi(monkeypatch)

    def raise_error(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(service, "_build_product_article_lines", raise_error)
    with pytest.raises(type(error), match=str(error)):
        service._build_user_answer([_item(result={"family_context": {"results": [_family()]}})], ["price"])


def test_empty_family_presentation_can_become_answer_only_through_articles(monkeypatch):
    _decline_multi(monkeypatch)
    empty_family = _family(family_name=None, family_code=None, strengths=None, limitations=None, selection_advice=None)
    monkeypatch.setattr(service, "_build_product_article_lines", lambda *_args, **_kwargs: ["article only"])

    assert service._build_user_answer([_item(result={"family_context": {"results": [empty_family]}})], ["price"]) == "\narticle only"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "4B2 future boundary: add run_single_family_product_answer_stage to service; "
        "then remove this xfail and assert its runtime-resolved article dependency, frozen "
        "answer/None contract, and direct service consumption in normal green tests"
    ),
)
def test_future_4b2_service_boundary_is_stage_owned_without_permanent_helper_coupling():
    source = inspect.getsource(service._build_user_answer)

    assert "run_single_family_product_answer_stage(" in source
    assert "_build_product_article_lines(" not in source
