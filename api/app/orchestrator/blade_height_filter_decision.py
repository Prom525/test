"""Pure, non-authoritative decisions for caller-assessed blade-height filters.

The input assessments are deliberately supplied by a caller.  This module does
not classify natural language, resolve a scope, inspect a backend, build a
plan, or grant execution authority.  In particular, a parser ``VALID`` result
is only a local predicate; it is not evidence that a user requested a filter.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .blade_height_predicate_parser import (
    BladeHeightPredicateParseReason,
    BladeHeightPredicateParseResult,
    BladeHeightPredicateParseState,
)


class BladeHeightFilterApplicability(str, Enum):
    """Caller-supplied intent assessment, not production recognition."""

    NOT_A_FILTER = "not_a_filter"
    EXPLICIT_FILTER_REQUEST = "explicit_filter_request"


class BladeHeightFilterScopeAssessment(str, Enum):
    """Caller-supplied scope status for a valid filter request."""

    NOT_ASSESSED = "not_assessed"
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    AMBIGUOUS = "ambiguous"


class BladeHeightFilterCapabilityAvailability(str, Enum):
    """Known capability states; neither state is execution authority here."""

    UNAVAILABLE = "unavailable"
    REPORTED_AVAILABLE_BUT_UNPROVEN = "reported_available_but_unproven"


class BladeHeightFilterDecisionOutcome(str, Enum):
    """The bounded, non-executing outcomes of this milestone."""

    LEGACY = "legacy"
    CLARIFY = "clarify"
    DEFERRED_COMPOSITION = "deferred_composition"
    UNSUPPORTED = "unsupported"


class BladeHeightFilterDecisionReason(str, Enum):
    """Stable decision-level reasons; parser reasons remain separately exact."""

    NOT_A_FILTER_INTENT = "not_a_filter_intent"
    PREDICATE_NO_MATCH = "predicate_no_match"
    PREDICATE_AMBIGUOUS = "predicate_ambiguous"
    PREDICATE_INVALID = "predicate_invalid"
    SCOPE_NOT_ASSESSED = "scope_not_assessed"
    SCOPE_UNRESOLVED = "scope_unresolved"
    SCOPE_AMBIGUOUS = "scope_ambiguous"
    MULTI_INTENT = "multi_intent"
    BACKEND_CAPABILITY_UNAVAILABLE = "backend_capability_unavailable"
    CAPABILITY_CONTRACT_UNPROVEN = "capability_contract_unproven"


class BladeHeightFilterClarification(str, Enum):
    """Typed follow-up need without inventing user-facing wording."""

    PREDICATE = "predicate"
    SCOPE = "scope"


@dataclass(frozen=True)
class BladeHeightFilterDecisionInput:
    """All assessments are inputs; this type makes their provenance explicit.

    ``has_other_intents`` means a caller has already found another request. It
    is never treated as permission to discard that request.
    """

    applicability: BladeHeightFilterApplicability
    parser_result: BladeHeightPredicateParseResult
    scope: BladeHeightFilterScopeAssessment
    capability: BladeHeightFilterCapabilityAvailability
    has_other_intents: bool = False


@dataclass(frozen=True)
class BladeHeightFilterDecision:
    """A pure result that retains the original parser result unchanged.

    ``preserves_other_intents`` is true when caller-reported other intents
    remain to be handled, including on the legacy path. False means none
    were reported, never permission to discard a request.
    """

    outcome: BladeHeightFilterDecisionOutcome
    reason: BladeHeightFilterDecisionReason
    clarification: BladeHeightFilterClarification | None
    parser_reason: BladeHeightPredicateParseReason | None
    parser_result: BladeHeightPredicateParseResult
    preserves_other_intents: bool


def _predicate_reason(
    parser_result: BladeHeightPredicateParseResult,
) -> BladeHeightFilterDecisionReason | None:
    if parser_result.state is BladeHeightPredicateParseState.VALID:
        return None
    if parser_result.state is BladeHeightPredicateParseState.NO_MATCH:
        return BladeHeightFilterDecisionReason.PREDICATE_NO_MATCH
    if parser_result.state is BladeHeightPredicateParseState.AMBIGUOUS:
        return BladeHeightFilterDecisionReason.PREDICATE_AMBIGUOUS
    return BladeHeightFilterDecisionReason.PREDICATE_INVALID


def _scope_reason(
    scope: BladeHeightFilterScopeAssessment,
) -> BladeHeightFilterDecisionReason | None:
    if scope is BladeHeightFilterScopeAssessment.RESOLVED:
        return None
    if scope is BladeHeightFilterScopeAssessment.UNRESOLVED:
        return BladeHeightFilterDecisionReason.SCOPE_UNRESOLVED
    if scope is BladeHeightFilterScopeAssessment.AMBIGUOUS:
        return BladeHeightFilterDecisionReason.SCOPE_AMBIGUOUS
    return BladeHeightFilterDecisionReason.SCOPE_NOT_ASSESSED


def decide_blade_height_filter(
    decision_input: BladeHeightFilterDecisionInput,
) -> BladeHeightFilterDecision:
    """Make a deterministic non-executing decision from supplied assessments.

    The result has no ``ALLOW`` outcome.  A claimed backend capability remains
    unsupported until a later milestone proves its complete contract (operator,
    value, canonical scope, latest-data completeness, and pagination).
    """

    parser_result = decision_input.parser_result
    if decision_input.applicability is BladeHeightFilterApplicability.NOT_A_FILTER:
        return BladeHeightFilterDecision(
            outcome=BladeHeightFilterDecisionOutcome.LEGACY,
            reason=BladeHeightFilterDecisionReason.NOT_A_FILTER_INTENT,
            clarification=None,
            parser_reason=parser_result.reason,
            parser_result=parser_result,
            preserves_other_intents=decision_input.has_other_intents,
        )

    predicate_reason = _predicate_reason(parser_result)
    clarification = (
        BladeHeightFilterClarification.PREDICATE
        if predicate_reason is not None
        else None
    )
    scope_reason = None
    if predicate_reason is None:
        scope_reason = _scope_reason(decision_input.scope)
        if scope_reason is not None:
            clarification = BladeHeightFilterClarification.SCOPE

    if decision_input.has_other_intents:
        return BladeHeightFilterDecision(
            outcome=BladeHeightFilterDecisionOutcome.DEFERRED_COMPOSITION,
            reason=BladeHeightFilterDecisionReason.MULTI_INTENT,
            clarification=clarification,
            parser_reason=parser_result.reason,
            parser_result=parser_result,
            preserves_other_intents=True,
        )

    if predicate_reason is not None:
        return BladeHeightFilterDecision(
            outcome=BladeHeightFilterDecisionOutcome.CLARIFY,
            reason=predicate_reason,
            clarification=BladeHeightFilterClarification.PREDICATE,
            parser_reason=parser_result.reason,
            parser_result=parser_result,
            preserves_other_intents=False,
        )

    if scope_reason is not None:
        return BladeHeightFilterDecision(
            outcome=BladeHeightFilterDecisionOutcome.CLARIFY,
            reason=scope_reason,
            clarification=BladeHeightFilterClarification.SCOPE,
            parser_reason=None,
            parser_result=parser_result,
            preserves_other_intents=False,
        )

    capability_reason = (
        BladeHeightFilterDecisionReason.BACKEND_CAPABILITY_UNAVAILABLE
        if decision_input.capability is BladeHeightFilterCapabilityAvailability.UNAVAILABLE
        else BladeHeightFilterDecisionReason.CAPABILITY_CONTRACT_UNPROVEN
    )
    return BladeHeightFilterDecision(
        outcome=BladeHeightFilterDecisionOutcome.UNSUPPORTED,
        reason=capability_reason,
        clarification=None,
        parser_reason=None,
        parser_result=parser_result,
        preserves_other_intents=False,
    )


__all__ = [
    "BladeHeightFilterApplicability",
    "BladeHeightFilterCapabilityAvailability",
    "BladeHeightFilterClarification",
    "BladeHeightFilterDecision",
    "BladeHeightFilterDecisionInput",
    "BladeHeightFilterDecisionOutcome",
    "BladeHeightFilterDecisionReason",
    "BladeHeightFilterScopeAssessment",
    "decide_blade_height_filter",
]
