"""Pure parsing for explicit blade-height predicates.

This module deliberately does not resolve assets or band scopes, ask a
clarification question, build a query plan, or execute a filter.  It only
recognises one locally bound measurement predicate in the original text.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
import re


class BladeHeightPredicateParseState(str, Enum):
    """Outcome of parsing a possible explicit blade-height predicate."""

    NO_MATCH = "no_match"
    VALID = "valid"
    AMBIGUOUS = "ambiguous"
    INVALID = "invalid"


class BladeHeightPredicateParseReason(str, Enum):
    """Stable reasons for non-valid parser outcomes."""

    NO_MEASUREMENT_PREDICATE = "no_measurement_predicate"
    OTHER_QUANTITY = "other_quantity"
    MISSING_QUANTITY = "missing_quantity"
    MISSING_OPERATOR = "missing_operator"
    MISSING_UNIT = "missing_unit"
    MISSING_VALUE = "missing_value"
    UNSUPPORTED_NUMBER_WORD = "unsupported_number_word"
    APPROXIMATE_VALUE = "approximate_value"
    MULTIPLE_MEASUREMENTS = "multiple_measurements"
    UNSUPPORTED_COMPOSITION = "unsupported_composition"
    NEGATIVE_VALUE = "negative_value"
    NON_FINITE_VALUE = "non_finite_value"
    INVALID_NUMBER = "invalid_number"


class BladeHeightQuantity(str, Enum):
    BLADE_HEIGHT = "blade_height"


class BladeHeightComparisonOperator(str, Enum):
    LT = "lt"
    LTE = "lte"
    EQ = "eq"
    GT = "gt"
    GTE = "gte"


@dataclass(frozen=True)
class SourceSpan:
    """A zero-based, end-exclusive span in the unnormalised input text."""

    start: int
    end: int
    text: str


@dataclass(frozen=True)
class BladeHeightPredicate:
    quantity: BladeHeightQuantity
    operator: BladeHeightComparisonOperator
    value_mm: Decimal
    source_span: SourceSpan


@dataclass(frozen=True)
class BladeHeightPredicateParseResult:
    state: BladeHeightPredicateParseState
    reason: BladeHeightPredicateParseReason | None
    predicate: BladeHeightPredicate | None


_QUANTITY = r"(?:meshoogte|blade[_\s-]?height)"
_OTHER_QUANTITY = r"(?:bandbreedte|breedte|lengte|diameter|slijtage|belt[_\s-]?width)"
_UNIT = r"(?:mm\b|millimeters?\b)"
_NUMBER = r"\d+(?:[.,]\d+)?"
_OPERATOR = (
    r"(?:op\s+of\s+onder\b|minstens\b|onder\b|boven\b|exact\b|op\b|<=|>=|<|>|=)"
)
_APPROXIMATION = r"(?:rond\b|bijna\b|circa\b)"

_PREDICATE_RE = re.compile(
    rf"(?P<quantity>\b{_QUANTITY}\b)\s*"
    rf"(?P<operator>{_OPERATOR})\s*(?:de\s+)?"
    rf"(?P<value>{_NUMBER}|drie\b)\s*(?P<unit>{_UNIT})",
    re.IGNORECASE,
)
_THRESHOLD_RE = re.compile(
    rf"(?P<operator>{_OPERATOR})\s*(?:de\s+)?(?P<value>{_NUMBER}|drie\b)\s*(?P<unit>{_UNIT})",
    re.IGNORECASE,
)
_OTHER_QUANTITY_RE = re.compile(
    rf"\b{_OTHER_QUANTITY}\b\s*{_OPERATOR}\s*(?:de\s+)?"
    rf"(?:{_NUMBER}|drie\b)\s*{_UNIT}",
    re.IGNORECASE,
)
_APPROXIMATE_RE = re.compile(
    rf"\b{_QUANTITY}\b\s*(?:{_OPERATOR}\s*)?{_APPROXIMATION}\s*"
    rf"(?:de\s+)?(?:{_NUMBER}|[A-Za-z]+)\s*{_UNIT}",
    re.IGNORECASE,
)
_VALUE_WITH_UNIT_RE = re.compile(
    rf"\b{_QUANTITY}\b\s*(?P<value>[^\s]+)\s*(?P<unit>{_UNIT})",
    re.IGNORECASE,
)
_OPERATOR_WITH_TOKEN_AND_UNIT_RE = re.compile(
    rf"\b{_QUANTITY}\b\s*(?P<operator>{_OPERATOR})\s*(?:de\s+)?"
    rf"(?P<value>[^\s]+)\s*(?P<unit>{_UNIT})",
    re.IGNORECASE,
)
_MISSING_UNIT_RE = re.compile(
    rf"\b{_QUANTITY}\b\s*{_OPERATOR}\s*(?:de\s+)?(?P<value>{_NUMBER}|drie\b)(?![\w.,])",
    re.IGNORECASE,
)
_MISSING_VALUE_RE = re.compile(
    rf"\b{_QUANTITY}\b\s*{_OPERATOR}(?=\s|$)", re.IGNORECASE
)
_COMPOSED_TAIL_RE = re.compile(
    rf"\s*(?:en|of|tot|,)\s*{_OPERATOR}\s*(?:de\s+)?(?:{_NUMBER}|drie\b)\s*{_UNIT}",
    re.IGNORECASE,
)
_MEASUREMENT_QUANTITY = rf"(?:{_QUANTITY}|{_OTHER_QUANTITY})"
_MEASUREMENT_TOKEN = rf"(?:[-+]?{_NUMBER}|[A-Za-z]+)"
_ADDITIONAL_MEASUREMENT_RE = re.compile(
    rf"\b{_MEASUREMENT_QUANTITY}\b\s*(?:"
    rf"{_OPERATOR}\s*(?:de\s+)?(?:{_APPROXIMATION}\s*)?"
    rf"(?:{_MEASUREMENT_TOKEN}\s*{_UNIT}|{_MEASUREMENT_TOKEN}(?![\w.,]))"
    rf"|{_APPROXIMATION}\s*(?:de\s+)?{_MEASUREMENT_TOKEN}\s*{_UNIT}"
    rf"|{_MEASUREMENT_TOKEN}\s*{_UNIT}"
    rf"|[A-Za-z]+\s+{_MEASUREMENT_TOKEN}\s*{_UNIT}"
    rf")",
    re.IGNORECASE,
)
_ADDITIONAL_TAIL_RE = re.compile(
    rf"^\s*(?:en|of|tot|,)\s*(?:"
    rf"(?:{_OPERATOR}\s*)?(?:{_APPROXIMATION}\s*)?(?:de\s+)?"
    rf"{_MEASUREMENT_TOKEN}(?:\s*{_UNIT})?"
    rf")",
    re.IGNORECASE,
)
_ADDITIONAL_PREFIX_RE = re.compile(
    rf"(?:{_OPERATOR}\s*)?(?:{_APPROXIMATION}\s*)?(?:de\s+)?"
    rf"{_MEASUREMENT_TOKEN}\s*{_UNIT}\s*(?:en|of|tot|,)\s*$",
    re.IGNORECASE,
)

_OPERATOR_MAP = {
    "op of onder": BladeHeightComparisonOperator.LTE,
    "<=": BladeHeightComparisonOperator.LTE,
    "onder": BladeHeightComparisonOperator.LT,
    "<": BladeHeightComparisonOperator.LT,
    "op": BladeHeightComparisonOperator.EQ,
    "exact": BladeHeightComparisonOperator.EQ,
    "=": BladeHeightComparisonOperator.EQ,
    "boven": BladeHeightComparisonOperator.GT,
    ">": BladeHeightComparisonOperator.GT,
    "minstens": BladeHeightComparisonOperator.GTE,
    ">=": BladeHeightComparisonOperator.GTE,
}


def _result(
    state: BladeHeightPredicateParseState,
    reason: BladeHeightPredicateParseReason,
) -> BladeHeightPredicateParseResult:
    return BladeHeightPredicateParseResult(state=state, reason=reason, predicate=None)


def _source_span(text: str, match: re.Match[str]) -> SourceSpan:
    return SourceSpan(start=match.start(), end=match.end(), text=text[match.start() : match.end()])


def _number_from_token(token: str) -> Decimal:
    if token.casefold() == "drie":
        return Decimal("3")
    return Decimal(token.replace(",", "."))


def _invalid_token_result(token: str) -> BladeHeightPredicateParseResult:
    normalized = token.casefold()
    if token.startswith("-"):
        return _result(
            BladeHeightPredicateParseState.INVALID,
            BladeHeightPredicateParseReason.NEGATIVE_VALUE,
        )
    if normalized in {"nan", "inf", "+inf", "infinity", "+infinity"}:
        return _result(
            BladeHeightPredicateParseState.INVALID,
            BladeHeightPredicateParseReason.NON_FINITE_VALUE,
        )
    if any(character.isdigit() for character in token) or "." in token or "," in token:
        return _result(
            BladeHeightPredicateParseState.INVALID,
            BladeHeightPredicateParseReason.INVALID_NUMBER,
        )
    return _result(
        BladeHeightPredicateParseState.AMBIGUOUS,
        BladeHeightPredicateParseReason.UNSUPPORTED_NUMBER_WORD,
    )


def _has_additional_measurement_expression(text: str, match: re.Match[str]) -> bool:
    """Reject a valid-looking predicate when a second local measure is present.

    This deliberately recognises only measure-shaped continuations or a second
    named quantity.  Unrelated identifiers such as ``A319`` or ``DE3`` are not
    measurements and therefore do not affect a single valid predicate.
    """

    for candidate in _ADDITIONAL_MEASUREMENT_RE.finditer(text):
        if candidate.start() < match.start() or candidate.end() > match.end():
            return True
    return bool(
        _ADDITIONAL_TAIL_RE.match(text[match.end() :])
        or _ADDITIONAL_PREFIX_RE.search(text[: match.start()])
    )


def _is_directly_negated(text: str, match: re.Match[str]) -> bool:
    return bool(re.search(r"\b(?:niet|geen)\s*$", text[: match.start()], re.IGNORECASE))


def parse_explicit_blade_height_predicate(
    text: str,
) -> BladeHeightPredicateParseResult:
    """Parse one explicit, local blade-height comparison without side effects.

    A valid result has exactly one positive local predicate and an exact source
    span.  Composition and direct negation are ambiguous rather than silently
    reduced.  ``NO_MATCH`` means there is no blade-height predicate to consume.
    """

    matches = list(_PREDICATE_RE.finditer(text))
    threshold_matches = list(_THRESHOLD_RE.finditer(text))

    if len(matches) > 1:
        return _result(
            BladeHeightPredicateParseState.AMBIGUOUS,
            BladeHeightPredicateParseReason.MULTIPLE_MEASUREMENTS,
        )

    if len(matches) == 1:
        match = matches[0]
        if _is_directly_negated(text, match):
            return _result(
                BladeHeightPredicateParseState.AMBIGUOUS,
                BladeHeightPredicateParseReason.UNSUPPORTED_COMPOSITION,
            )
        if _has_additional_measurement_expression(text, match):
            return _result(
                BladeHeightPredicateParseState.AMBIGUOUS,
                BladeHeightPredicateParseReason.UNSUPPORTED_COMPOSITION,
            )
        if _COMPOSED_TAIL_RE.match(text, match.end()):
            return _result(
                BladeHeightPredicateParseState.AMBIGUOUS,
                BladeHeightPredicateParseReason.UNSUPPORTED_COMPOSITION,
            )
        if len(threshold_matches) > 1:
            return _result(
                BladeHeightPredicateParseState.AMBIGUOUS,
                BladeHeightPredicateParseReason.UNSUPPORTED_COMPOSITION,
            )

        operator_text = " ".join(match.group("operator").casefold().split())
        predicate = BladeHeightPredicate(
            quantity=BladeHeightQuantity.BLADE_HEIGHT,
            operator=_OPERATOR_MAP[operator_text],
            value_mm=_number_from_token(match.group("value")),
            source_span=_source_span(text, match),
        )
        return BladeHeightPredicateParseResult(
            state=BladeHeightPredicateParseState.VALID,
            reason=None,
            predicate=predicate,
        )

    if _APPROXIMATE_RE.search(text):
        return _result(
            BladeHeightPredicateParseState.AMBIGUOUS,
            BladeHeightPredicateParseReason.APPROXIMATE_VALUE,
        )

    invalid_token = _OPERATOR_WITH_TOKEN_AND_UNIT_RE.search(text)
    if invalid_token:
        return _invalid_token_result(invalid_token.group("value"))

    if _MISSING_UNIT_RE.search(text):
        return _result(
            BladeHeightPredicateParseState.AMBIGUOUS,
            BladeHeightPredicateParseReason.MISSING_UNIT,
        )
    if _MISSING_VALUE_RE.search(text):
        return _result(
            BladeHeightPredicateParseState.AMBIGUOUS,
            BladeHeightPredicateParseReason.MISSING_VALUE,
        )
    if _VALUE_WITH_UNIT_RE.search(text):
        return _result(
            BladeHeightPredicateParseState.AMBIGUOUS,
            BladeHeightPredicateParseReason.MISSING_OPERATOR,
        )
    if _OTHER_QUANTITY_RE.search(text):
        return _result(
            BladeHeightPredicateParseState.NO_MATCH,
            BladeHeightPredicateParseReason.OTHER_QUANTITY,
        )
    if threshold_matches:
        return _result(
            BladeHeightPredicateParseState.AMBIGUOUS,
            BladeHeightPredicateParseReason.MISSING_QUANTITY,
        )
    return _result(
        BladeHeightPredicateParseState.NO_MATCH,
        BladeHeightPredicateParseReason.NO_MEASUREMENT_PREDICATE,
    )


__all__ = [
    "BladeHeightComparisonOperator",
    "BladeHeightPredicate",
    "BladeHeightPredicateParseReason",
    "BladeHeightPredicateParseResult",
    "BladeHeightPredicateParseState",
    "BladeHeightQuantity",
    "SourceSpan",
    "parse_explicit_blade_height_predicate",
]
