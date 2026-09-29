"""Contracts for the pure, caller-assessed blade-height filter decision."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from app.orchestrator.blade_height_filter_decision import (
    BladeHeightFilterApplicability,
    BladeHeightFilterCapabilityAvailability,
    BladeHeightFilterClarification,
    BladeHeightFilterDecisionInput,
    BladeHeightFilterDecisionOutcome,
    BladeHeightFilterDecisionReason,
    BladeHeightFilterScopeAssessment,
    decide_blade_height_filter,
)
from app.orchestrator.blade_height_predicate_parser import (
    BladeHeightPredicateParseReason,
    parse_explicit_blade_height_predicate,
)


def _input(
    question: str,
    applicability: BladeHeightFilterApplicability,
    *,
    scope: BladeHeightFilterScopeAssessment = BladeHeightFilterScopeAssessment.RESOLVED,
    capability: BladeHeightFilterCapabilityAvailability = (
        BladeHeightFilterCapabilityAvailability.UNAVAILABLE
    ),
    has_other_intents: bool = False,
) -> BladeHeightFilterDecisionInput:
    return BladeHeightFilterDecisionInput(
        applicability=applicability,
        parser_result=parse_explicit_blade_height_predicate(question),
        scope=scope,
        capability=capability,
        has_other_intents=has_other_intents,
    )


@pytest.mark.parametrize(
    (
        "name,decision_input,outcome,reason,clarification,parser_reason,"
        "preserves_other_intents"
    ),
    (
        (
            "original_gsl_gap_stays_legacy",
            _input(
                "Geef voor GSL de schrapers die nu op of rond de 3 mm grens zitten.",
                BladeHeightFilterApplicability.NOT_A_FILTER,
            ),
            BladeHeightFilterDecisionOutcome.LEGACY,
            BladeHeightFilterDecisionReason.NOT_A_FILTER_INTENT,
            None,
            BladeHeightPredicateParseReason.NO_MEASUREMENT_PREDICATE,
            False,
        ),
        (
            "ordinary_inspection_stays_legacy",
            _input(
                "Wat is de laatste inspectiestatus van de schrapers?",
                BladeHeightFilterApplicability.NOT_A_FILTER,
            ),
            BladeHeightFilterDecisionOutcome.LEGACY,
            BladeHeightFilterDecisionReason.NOT_A_FILTER_INTENT,
            None,
            BladeHeightPredicateParseReason.NO_MEASUREMENT_PREDICATE,
            False,
        ),
        (
            "de3_identifier_stays_legacy",
            _input("toon band DE3", BladeHeightFilterApplicability.NOT_A_FILTER),
            BladeHeightFilterDecisionOutcome.LEGACY,
            BladeHeightFilterDecisionReason.NOT_A_FILTER_INTENT,
            None,
            BladeHeightPredicateParseReason.NO_MEASUREMENT_PREDICATE,
            False,
        ),
        (
            "other_quantity_stays_legacy",
            _input(
                "toon schrapers met bandbreedte onder 3 mm",
                BladeHeightFilterApplicability.NOT_A_FILTER,
            ),
            BladeHeightFilterDecisionOutcome.LEGACY,
            BladeHeightFilterDecisionReason.NOT_A_FILTER_INTENT,
            None,
            BladeHeightPredicateParseReason.OTHER_QUANTITY,
            False,
        ),
        (
            "valid_parser_alone_does_not_create_filter_intent",
            _input(
                "toon de tekst meshoogte op of onder 3 mm als citaat",
                BladeHeightFilterApplicability.NOT_A_FILTER,
            ),
            BladeHeightFilterDecisionOutcome.LEGACY,
            BladeHeightFilterDecisionReason.NOT_A_FILTER_INTENT,
            None,
            None,
            False,
        ),
        (
            "valid_explicit_filter_is_currently_unsupported",
            _input(
                "Filter de schrapers met meshoogte op of onder 3 mm",
                BladeHeightFilterApplicability.EXPLICIT_FILTER_REQUEST,
            ),
            BladeHeightFilterDecisionOutcome.UNSUPPORTED,
            BladeHeightFilterDecisionReason.BACKEND_CAPABILITY_UNAVAILABLE,
            None,
            None,
            False,
        ),
        (
            "reported_capability_is_not_a_proven_contract",
            _input(
                "Filter de schrapers met meshoogte op of onder 3 mm",
                BladeHeightFilterApplicability.EXPLICIT_FILTER_REQUEST,
                capability=(
                    BladeHeightFilterCapabilityAvailability.REPORTED_AVAILABLE_BUT_UNPROVEN
                ),
            ),
            BladeHeightFilterDecisionOutcome.UNSUPPORTED,
            BladeHeightFilterDecisionReason.CAPABILITY_CONTRACT_UNPROVEN,
            None,
            None,
            False,
        ),
        (
            "negative_invalid_is_predicate_clarification",
            _input(
                "Filter de schrapers met meshoogte onder -3 mm",
                BladeHeightFilterApplicability.EXPLICIT_FILTER_REQUEST,
            ),
            BladeHeightFilterDecisionOutcome.CLARIFY,
            BladeHeightFilterDecisionReason.PREDICATE_INVALID,
            BladeHeightFilterClarification.PREDICATE,
            BladeHeightPredicateParseReason.NEGATIVE_VALUE,
            False,
        ),
        (
            "invalid_number_is_not_relabelled_negative",
            _input(
                "Filter de schrapers met meshoogte onder 3x mm",
                BladeHeightFilterApplicability.EXPLICIT_FILTER_REQUEST,
            ),
            BladeHeightFilterDecisionOutcome.CLARIFY,
            BladeHeightFilterDecisionReason.PREDICATE_INVALID,
            BladeHeightFilterClarification.PREDICATE,
            BladeHeightPredicateParseReason.INVALID_NUMBER,
            False,
        ),
        (
            "approximate_predicate_is_clarified_without_tolerance",
            _input(
                "Filter de schrapers met meshoogte rond 3 mm",
                BladeHeightFilterApplicability.EXPLICIT_FILTER_REQUEST,
            ),
            BladeHeightFilterDecisionOutcome.CLARIFY,
            BladeHeightFilterDecisionReason.PREDICATE_AMBIGUOUS,
            BladeHeightFilterClarification.PREDICATE,
            BladeHeightPredicateParseReason.APPROXIMATE_VALUE,
            False,
        ),
        (
            "two_measurements_are_not_reduced_to_one",
            _input(
                "Filter de schrapers met meshoogte onder 3 mm en boven 5 mm",
                BladeHeightFilterApplicability.EXPLICIT_FILTER_REQUEST,
            ),
            BladeHeightFilterDecisionOutcome.CLARIFY,
            BladeHeightFilterDecisionReason.PREDICATE_AMBIGUOUS,
            BladeHeightFilterClarification.PREDICATE,
            BladeHeightPredicateParseReason.UNSUPPORTED_COMPOSITION,
            False,
        ),
        (
            "explicit_intent_without_parseable_predicate_is_clarified",
            _input(
                "Filter op meshoogte",
                BladeHeightFilterApplicability.EXPLICIT_FILTER_REQUEST,
            ),
            BladeHeightFilterDecisionOutcome.CLARIFY,
            BladeHeightFilterDecisionReason.PREDICATE_NO_MATCH,
            BladeHeightFilterClarification.PREDICATE,
            BladeHeightPredicateParseReason.NO_MEASUREMENT_PREDICATE,
            False,
        ),
        (
            "unresolved_scope_is_its_own_clarification",
            _input(
                "Filter de schrapers met meshoogte op of onder 3 mm",
                BladeHeightFilterApplicability.EXPLICIT_FILTER_REQUEST,
                scope=BladeHeightFilterScopeAssessment.UNRESOLVED,
            ),
            BladeHeightFilterDecisionOutcome.CLARIFY,
            BladeHeightFilterDecisionReason.SCOPE_UNRESOLVED,
            BladeHeightFilterClarification.SCOPE,
            None,
            False,
        ),
        (
            "ambiguous_scope_is_its_own_clarification",
            _input(
                "Filter de schrapers met meshoogte op of onder 3 mm",
                BladeHeightFilterApplicability.EXPLICIT_FILTER_REQUEST,
                scope=BladeHeightFilterScopeAssessment.AMBIGUOUS,
            ),
            BladeHeightFilterDecisionOutcome.CLARIFY,
            BladeHeightFilterDecisionReason.SCOPE_AMBIGUOUS,
            BladeHeightFilterClarification.SCOPE,
            None,
            False,
        ),
        (
            "direct_negation_is_not_positive_selection",
            _input(
                "niet meshoogte onder 3 mm",
                BladeHeightFilterApplicability.EXPLICIT_FILTER_REQUEST,
            ),
            BladeHeightFilterDecisionOutcome.CLARIFY,
            BladeHeightFilterDecisionReason.PREDICATE_AMBIGUOUS,
            BladeHeightFilterClarification.PREDICATE,
            BladeHeightPredicateParseReason.UNSUPPORTED_COMPOSITION,
            False,
        ),
        (
            "unassessed_scope_is_not_resolved",
            _input(
                "Filter de schrapers met meshoogte op of onder 3 mm",
                BladeHeightFilterApplicability.EXPLICIT_FILTER_REQUEST,
                scope=BladeHeightFilterScopeAssessment.NOT_ASSESSED,
            ),
            BladeHeightFilterDecisionOutcome.CLARIFY,
            BladeHeightFilterDecisionReason.SCOPE_NOT_ASSESSED,
            BladeHeightFilterClarification.SCOPE,
            None,
            False,
        ),
        (
            "non_filter_preserves_caller_reported_other_intents",
            _input(
                "toon de tekst meshoogte op of onder 3 mm als citaat",
                BladeHeightFilterApplicability.NOT_A_FILTER,
                has_other_intents=True,
            ),
            BladeHeightFilterDecisionOutcome.LEGACY,
            BladeHeightFilterDecisionReason.NOT_A_FILTER_INTENT,
            None,
            None,
            True,
        ),
        (
            "multi_intent_is_deferred_and_retained",
            _input(
                "Filter de schrapers met meshoogte op of onder 3 mm",
                BladeHeightFilterApplicability.EXPLICIT_FILTER_REQUEST,
                has_other_intents=True,
            ),
            BladeHeightFilterDecisionOutcome.DEFERRED_COMPOSITION,
            BladeHeightFilterDecisionReason.MULTI_INTENT,
            None,
            None,
            True,
        ),
        (
            "multi_intent_keeps_predicate_clarification",
            _input(
                "Filter de schrapers met meshoogte onder -3 mm",
                BladeHeightFilterApplicability.EXPLICIT_FILTER_REQUEST,
                has_other_intents=True,
            ),
            BladeHeightFilterDecisionOutcome.DEFERRED_COMPOSITION,
            BladeHeightFilterDecisionReason.MULTI_INTENT,
            BladeHeightFilterClarification.PREDICATE,
            BladeHeightPredicateParseReason.NEGATIVE_VALUE,
            True,
        ),
        (
            "multi_intent_keeps_scope_clarification",
            _input(
                "Filter de schrapers met meshoogte op of onder 3 mm",
                BladeHeightFilterApplicability.EXPLICIT_FILTER_REQUEST,
                scope=BladeHeightFilterScopeAssessment.AMBIGUOUS,
                has_other_intents=True,
            ),
            BladeHeightFilterDecisionOutcome.DEFERRED_COMPOSITION,
            BladeHeightFilterDecisionReason.MULTI_INTENT,
            BladeHeightFilterClarification.SCOPE,
            None,
            True,
        ),
    ),
    ids=lambda value: value if type(value) is str else None,
)
def test_blade_height_filter_decision_contract(
    name,
    decision_input,
    outcome,
    reason,
    clarification,
    parser_reason,
    preserves_other_intents,
):
    decision = decide_blade_height_filter(decision_input)

    assert decision.outcome is outcome
    assert decision.reason is reason
    assert decision.clarification is clarification
    assert decision.parser_reason is parser_reason
    assert decision.preserves_other_intents is preserves_other_intents
    assert decision.parser_result is decision_input.parser_result


def test_parser_predicate_and_source_span_are_preserved_and_decision_is_deterministic():
    decision_input = _input(
        "  Filter de schrapers met meshoogte op of onder 3 mm",
        BladeHeightFilterApplicability.EXPLICIT_FILTER_REQUEST,
    )
    parsed = decision_input.parser_result
    assert parsed.predicate is not None
    original_span = parsed.predicate.source_span
    original_predicate = parsed.predicate

    first = decide_blade_height_filter(decision_input)
    second = decide_blade_height_filter(decision_input)

    assert first == second
    assert first.parser_result is parsed
    assert parsed.predicate is original_predicate
    assert parsed.predicate.source_span is original_span
    assert (original_span.start, original_span.end, original_span.text) == (
        26,
        52,
        "meshoogte op of onder 3 mm",
    )
    with pytest.raises(FrozenInstanceError):
        decision_input.scope = BladeHeightFilterScopeAssessment.AMBIGUOUS
    with pytest.raises(FrozenInstanceError):
        first.reason = BladeHeightFilterDecisionReason.MULTI_INTENT
