"""Direct tests for the single-family product answer stage."""

from __future__ import annotations

import copy

import pytest

from app.orchestrator.single_family_product_answer_stage import (
    SingleFamilyProductAnswerStageResult,
    run_single_family_product_answer_stage,
)


class Fatal(BaseException):
    pass


def _family(**overrides):
    family = {
        "family_code": "F-1",
        "family_name": "Family one",
        "strengths": "Strong",
        "limitations": "Limited",
        "selection_advice": "Choose carefully",
    }
    family.update(overrides)
    return family


def _run(specialist_result, requested=None, builder=lambda *_args, **_kwargs: []):
    return run_single_family_product_answer_stage(
        specialist_result,
        set() if requested is None else requested,
        build_product_article_lines=builder,
    )


@pytest.mark.parametrize(
    "specialist_result",
    [
        {},
        {"family_context": None},
        {"family_context": []},
        {"family_context": {}},
        {"family_context": {"results": None}},
        {"family_context": {"results": {}}},
        {"family_context": {"results": "rows"}},
        {"family_context": {"results": ()}},
        {"family_context": {"results": []}},
        {"family_context": {"results": [None]}},
        {"family_context": {"results": ["family"]}},
        {"family_context": {"results": [7]}},
    ],
)
def test_shape_gates_return_exact_none_without_calling_dependency(specialist_result):
    before = copy.deepcopy(specialist_result)

    def forbidden(*_args, **_kwargs):
        pytest.fail("article dependency should not be called")

    result = _run(specialist_result, {"price"}, forbidden)

    assert result.answer is None
    assert specialist_result == before


def test_first_family_only_and_exact_field_order_truthiness_and_conversion():
    specialist_result = {
        "family_context": {
            "results": [
                _family(
                    family_name=42,
                    family_code="ignored",
                    strengths=7,
                    limitations=("x",),
                    selection_advice={"k": "v"},
                ),
                _family(family_name="Never used"),
            ]
        }
    }
    before = copy.deepcopy(specialist_result)

    result = _run(specialist_result)

    assert result.answer == (
        "42\n\nSterktes: 7\n\nBeperkingen: ('x',)\n\n"
        "Selectieadvies: {'k': 'v'}"
    )
    assert specialist_result == before


@pytest.mark.parametrize(
    ("family", "answer"),
    [
        (_family(family_name="", family_code="CODE", strengths=0, limitations=False, selection_advice=[]), "CODE"),
        (_family(family_name=None, family_code=None, strengths="S", limitations=None, selection_advice="A"), "\nSterktes: S\n\nSelectieadvies: A"),
        (_family(family_name=None, family_code=None, strengths=None, limitations=None, selection_advice=None), None),
    ],
)
def test_field_fallback_and_empty_presentation_contract(family, answer):
    assert _run({"family_context": {"results": [family]}}).answer == answer


@pytest.mark.parametrize(
    ("requested", "flags"),
    [
        (set(), None),
        ({"inventory"}, (True, False)),
        ({"price"}, (False, True)),
        ({"inventory", "price"}, (True, True)),
        ({"stock", "cost"}, None),
    ],
)
def test_article_flags_identity_and_call_cardinality(requested, flags):
    specialist_result = {"family_context": {"results": [_family()]}}
    calls = []

    def builder(received, *, include_inventory, include_price):
        calls.append((received, include_inventory, include_price))
        return []

    result = _run(specialist_result, requested, builder)

    assert result.answer.startswith("Family one")
    assert calls == ([] if flags is None else [(specialist_result, *flags)])


@pytest.mark.parametrize(
    ("article_lines", "suffix"),
    [
        (None, "Family one"),
        ([], "Family one"),
        ((), "Family one"),
        (["one", "two"], "Family one\n\none\ntwo"),
        (("one", "two"), "Family one\n\none\ntwo"),
        ("XY", "Family one\n\nX\nY"),
        ({"first": 1, "second": 2}, "Family one\n\nfirst\nsecond"),
    ],
)
def test_article_iterable_is_truthiness_checked_then_splatted(article_lines, suffix):
    family = _family(strengths=None, limitations=None, selection_advice=None)
    result = _run(
        {"family_context": {"results": [family]}},
        {"price"},
        lambda *_args, **_kwargs: article_lines,
    )

    assert result.answer == suffix


@pytest.mark.parametrize("article_lines", [[7], ["valid", 7]])
def test_malformed_article_elements_raise_from_join(article_lines):
    with pytest.raises(TypeError, match="sequence item"):
        _run(
            {"family_context": {"results": [_family()]}},
            {"inventory"},
            lambda *_args, **_kwargs: article_lines,
        )


@pytest.mark.parametrize("error", [RuntimeError("exception"), Fatal("fatal")])
def test_dependency_exception_and_baseexception_propagate_identically(error):
    def builder(*_args, **_kwargs):
        raise error

    with pytest.raises(type(error), match=str(error)) as raised:
        _run({"family_context": {"results": [_family()]}}, {"price"}, builder)

    assert raised.value is error


def test_empty_family_can_produce_existing_leading_newline_article_answer():
    family = _family(
        family_name=None,
        family_code=None,
        strengths=None,
        limitations=None,
        selection_advice=None,
    )
    result = _run(
        {"family_context": {"results": [family]}},
        {"price"},
        lambda *_args, **_kwargs: ["article only"],
    )

    assert result.answer == "\narticle only"


def test_inputs_and_helper_return_are_not_mutated():
    specialist_result = {"family_context": {"results": [_family()]}}
    requested = {"price"}
    article_lines = ["article"]
    before_result = copy.deepcopy(specialist_result)
    before_requested = requested.copy()
    before_articles = article_lines.copy()

    _run(specialist_result, requested, lambda *_args, **_kwargs: article_lines)

    assert specialist_result == before_result
    assert requested == before_requested
    assert article_lines == before_articles


def test_result_contract_is_frozen_and_has_exactly_one_field():
    result = SingleFamilyProductAnswerStageResult(answer=None)

    assert tuple(result.__dataclass_fields__) == ("answer",)
    with pytest.raises(AttributeError):
        result.answer = "changed"
