from decimal import Decimal

import pytest

from app.orchestrator.blade_height_predicate_parser import (
    BladeHeightComparisonOperator,
    BladeHeightPredicateParseReason,
    BladeHeightPredicateParseState,
    parse_explicit_blade_height_predicate,
)


@pytest.mark.parametrize(
    ("question", "operator", "value"),
    [
        ("meshoogte onder 3mm", BladeHeightComparisonOperator.LT, Decimal("3")),
        ("meshoogte op of onder 3 mm", BladeHeightComparisonOperator.LTE, Decimal("3")),
        ("meshoogte boven 3 millimeter", BladeHeightComparisonOperator.GT, Decimal("3")),
        ("meshoogte minstens 3 millimeters", BladeHeightComparisonOperator.GTE, Decimal("3")),
        ("meshoogte exact 3 mm", BladeHeightComparisonOperator.EQ, Decimal("3")),
        ("meshoogte op 3 mm", BladeHeightComparisonOperator.EQ, Decimal("3")),
        ("meshoogte < 3 mm", BladeHeightComparisonOperator.LT, Decimal("3")),
        ("meshoogte > 3 mm", BladeHeightComparisonOperator.GT, Decimal("3")),
        ("meshoogte = 3 mm", BladeHeightComparisonOperator.EQ, Decimal("3")),
        ("blade_height <= 3,5 mm", BladeHeightComparisonOperator.LTE, Decimal("3.5")),
        ("BLADE HEIGHT >= 3.5mm", BladeHeightComparisonOperator.GTE, Decimal("3.5")),
        ("Meshoogte\tonder\t0 MM", BladeHeightComparisonOperator.LT, Decimal("0")),
        ("meshoogte op  of onder 3 mm", BladeHeightComparisonOperator.LTE, Decimal("3")),
        ("meshoogte op\tof\tonder 3 mm", BladeHeightComparisonOperator.LTE, Decimal("3")),
        ("meshoogte onder drie millimeter", BladeHeightComparisonOperator.LT, Decimal("3")),
    ],
)
def test_valid_local_predicates(question, operator, value):
    result = parse_explicit_blade_height_predicate(question)

    assert result.state is BladeHeightPredicateParseState.VALID
    assert result.reason is None
    assert result.predicate is not None
    assert result.predicate.operator is operator
    assert result.predicate.value_mm == value


def test_valid_predicate_has_an_exact_original_source_span():
    question = "Toon voor band A319: Meshoogte  op of onder  3,5 millimeters."
    result = parse_explicit_blade_height_predicate(question)

    assert result.predicate is not None
    span = result.predicate.source_span
    assert span.text == "Meshoogte  op of onder  3,5 millimeters"
    assert question[span.start : span.end] == span.text
    assert span.start == question.index("Meshoogte")


def test_whitespace_normalization_preserves_the_original_source_span():
    question = "Meshoogte op\tof  onder 3 mm"
    result = parse_explicit_blade_height_predicate(question)

    assert result.state is BladeHeightPredicateParseState.VALID
    assert result.predicate is not None
    assert result.predicate.operator is BladeHeightComparisonOperator.LTE
    assert result.predicate.source_span.text == question


@pytest.mark.parametrize(
    ("question", "reason"),
    [
        ("meshoogte onder 3", BladeHeightPredicateParseReason.MISSING_UNIT),
        ("meshoogte 3 mm", BladeHeightPredicateParseReason.MISSING_OPERATOR),
        ("onder 3 mm", BladeHeightPredicateParseReason.MISSING_QUANTITY),
        ("meshoogte onder", BladeHeightPredicateParseReason.MISSING_VALUE),
        ("meshoogte onder vier millimeter", BladeHeightPredicateParseReason.UNSUPPORTED_NUMBER_WORD),
        ("meshoogte rond 3 mm", BladeHeightPredicateParseReason.APPROXIMATE_VALUE),
        ("meshoogte onder circa 3 mm", BladeHeightPredicateParseReason.APPROXIMATE_VALUE),
    ],
)
def test_incomplete_or_ambiguous_predicates_are_typed(question, reason):
    result = parse_explicit_blade_height_predicate(question)

    assert result.state is BladeHeightPredicateParseState.AMBIGUOUS
    assert result.reason is reason
    assert result.predicate is None


@pytest.mark.parametrize(
    ("question", "reason"),
    [
        ("meshoogte onder -3 mm", BladeHeightPredicateParseReason.NEGATIVE_VALUE),
        ("meshoogte onder NaN mm", BladeHeightPredicateParseReason.NON_FINITE_VALUE),
        ("meshoogte onder infinity mm", BladeHeightPredicateParseReason.NON_FINITE_VALUE),
        ("meshoogte onder 3.5.6 mm", BladeHeightPredicateParseReason.INVALID_NUMBER),
    ],
)
def test_invalid_values_are_never_accepted(question, reason):
    result = parse_explicit_blade_height_predicate(question)

    assert result.state is BladeHeightPredicateParseState.INVALID
    assert result.reason is reason
    assert result.predicate is None


@pytest.mark.parametrize(
    ("question", "state", "reason"),
    [
        ("toon band DE3", BladeHeightPredicateParseState.NO_MATCH, BladeHeightPredicateParseReason.NO_MEASUREMENT_PREDICATE),
        ("toon band A319", BladeHeightPredicateParseState.NO_MATCH, BladeHeightPredicateParseReason.NO_MEASUREMENT_PREDICATE),
        ("bandbreedte onder 3 mm", BladeHeightPredicateParseState.NO_MATCH, BladeHeightPredicateParseReason.OTHER_QUANTITY),
        ("slijtage boven 3 mm", BladeHeightPredicateParseState.NO_MATCH, BladeHeightPredicateParseReason.OTHER_QUANTITY),
        ("meshoogte tonen en bandbreedte onder 3mm", BladeHeightPredicateParseState.NO_MATCH, BladeHeightPredicateParseReason.OTHER_QUANTITY),
    ],
)
def test_unrelated_dimensions_and_band_identifiers_do_not_bind_to_meshoogte(
    question, state, reason
):
    result = parse_explicit_blade_height_predicate(question)

    assert result.state is state
    assert result.reason is reason
    assert result.predicate is None


@pytest.mark.parametrize(
    ("question", "reason"),
    [
        (
            "meshoogte onder 3 mm en meshoogte boven 5 mm",
            BladeHeightPredicateParseReason.MULTIPLE_MEASUREMENTS,
        ),
        (
            "meshoogte onder 3 mm en boven 5 mm",
            BladeHeightPredicateParseReason.UNSUPPORTED_COMPOSITION,
        ),
        (
            "meshoogte onder 3 mm en bandbreedte boven 5 mm",
            BladeHeightPredicateParseReason.UNSUPPORTED_COMPOSITION,
        ),
        (
            "meshoogte onder 3 mm en meshoogte boven -5 mm",
            BladeHeightPredicateParseReason.UNSUPPORTED_COMPOSITION,
        ),
        (
            "meshoogte onder 3 mm en meshoogte rond 5 mm",
            BladeHeightPredicateParseReason.UNSUPPORTED_COMPOSITION,
        ),
        (
            "meshoogte onder 3 mm of 5 mm",
            BladeHeightPredicateParseReason.UNSUPPORTED_COMPOSITION,
        ),
        (
            "meshoogte onder 3 mm en meshoogte boven 5",
            BladeHeightPredicateParseReason.UNSUPPORTED_COMPOSITION,
        ),
        (
            "meshoogte onder 3 mm en meshoogte vreemd 5 mm",
            BladeHeightPredicateParseReason.UNSUPPORTED_COMPOSITION,
        ),
        (
            "meshoogte boven -5 mm en meshoogte onder 3 mm",
            BladeHeightPredicateParseReason.UNSUPPORTED_COMPOSITION,
        ),
        (
            "meshoogte rond 5 mm en meshoogte onder 3 mm",
            BladeHeightPredicateParseReason.UNSUPPORTED_COMPOSITION,
        ),
        (
            "5 mm of meshoogte onder 3 mm",
            BladeHeightPredicateParseReason.UNSUPPORTED_COMPOSITION,
        ),
        (
            "niet meshoogte onder 3 mm",
            BladeHeightPredicateParseReason.UNSUPPORTED_COMPOSITION,
        ),
        (
            "geen meshoogte onder 3 mm",
            BladeHeightPredicateParseReason.UNSUPPORTED_COMPOSITION,
        ),
    ],
)
def test_multiple_or_composed_thresholds_are_not_silently_reduced(question, reason):
    result = parse_explicit_blade_height_predicate(question)

    assert result.state is BladeHeightPredicateParseState.AMBIGUOUS
    assert result.reason is reason
    assert result.predicate is None


def test_valid_predicate_does_not_depend_on_resolved_scope_or_band():
    result = parse_explicit_blade_height_predicate("Welke schrapers hebben meshoogte onder 3 mm?")

    assert result.state is BladeHeightPredicateParseState.VALID
    assert result.predicate is not None
    assert result.predicate.value_mm == Decimal("3")


@pytest.mark.parametrize(
    ("question", "state", "reason"),
    [
        ("band A319 met meshoogte onder 3 mm", BladeHeightPredicateParseState.VALID, None),
        ("toon band DE3 met meshoogte onder 3 mm", BladeHeightPredicateParseState.VALID, None),
        (
            "meshoogte is belangrijk; toon band A319 onder 3 mm",
            BladeHeightPredicateParseState.AMBIGUOUS,
            BladeHeightPredicateParseReason.MISSING_QUANTITY,
        ),
    ],
)
def test_unrelated_words_or_identifiers_do_not_create_a_valid_binding(
    question, state, reason
):
    result = parse_explicit_blade_height_predicate(question)

    assert result.state is state
    assert result.reason is reason
    assert (result.predicate is not None) is (state is BladeHeightPredicateParseState.VALID)
