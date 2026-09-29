"""Offline comparison of the pure blade-height parser and legacy planning.

There is deliberately no production wiring between these paths.  The parser is
called as an independent observer; the legacy path remains the real
``understand_query -> apply_routing_sanity -> build_execution_plan`` chain.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pytest

import app.orchestrator.understanding as understanding_module
from app.orchestrator.blade_height_predicate_parser import (
    BladeHeightComparisonOperator,
    BladeHeightPredicateParseReason,
    BladeHeightPredicateParseState,
    parse_explicit_blade_height_predicate,
)
from app.orchestrator.planner import build_execution_plan
from app.orchestrator.routing_sanity import apply_routing_sanity


LEGACY_CLARIFICATION = (
    "Kun je aangeven of je informatie zoekt over een product, inspectie, "
    "technische vraag, RFQ of organisatie?"
)

# This is a test-only boundary replacement for resolve_scope_context.  It
# supplies deterministic already-grounded scope data without touching a
# resolver, database, network, LLM, or service execution.
SYNTHETIC_GROUNDED_SCOPE = {
    "status": "resolved",
    "scope": {
        "scope_type": "installation",
        "canonical_code": "MV1",
        "canonical_name": "Mengveld 1",
        "area_code": "GSL",
        "installation_code": "MV1",
        "source": "synthetic_grounded_resolver",
        "confidence": 1.0,
    },
    "candidates": [],
    "roles": {
        "active": [],
        "excluded": [],
        "comparison": [],
        "mentioned": [],
    },
    "mode": "single",
}


@dataclass(frozen=True)
class LegacyExpectation:
    domains: tuple[str, ...]
    intent: str
    blockers: tuple[tuple[str, str, str, str], ...]
    clarification_required: bool
    clarification_question: str | None
    actions: tuple[str, ...]


@dataclass(frozen=True)
class ComparisonCase:
    name: str
    question: str
    parser_state: BladeHeightPredicateParseState
    parser_reason: BladeHeightPredicateParseReason | None
    parser_operator: BladeHeightComparisonOperator | None
    parser_value_mm: Decimal | None
    legacy: LegacyExpectation
    parser_span: tuple[int, int, str] | None = None
    use_synthetic_grounded_scope: bool = False


GAP = LegacyExpectation(
    domains=(),
    intent="unknown",
    blockers=(),
    clarification_required=True,
    clarification_question=LEGACY_CLARIFICATION,
    actions=(),
)
INSPECTION_LOOKUP = LegacyExpectation(
    domains=("inspection",),
    intent="inspection_lookup",
    blockers=(),
    clarification_required=False,
    clarification_question=None,
    actions=("analysis_assistant",),
)
INSPECTION_LATEST = LegacyExpectation(
    domains=("inspection",),
    intent="inspection_latest",
    blockers=(),
    clarification_required=False,
    clarification_question=None,
    actions=("analysis_assistant",),
)


CASES = (
    ComparisonCase(
        name="original_gsl_gap_has_no_explicit_blade_height",
        question="Geef voor GSL de schrapers die nu op of rond de 3 mm grens zitten.",
        parser_state=BladeHeightPredicateParseState.NO_MATCH,
        parser_reason=BladeHeightPredicateParseReason.NO_MEASUREMENT_PREDICATE,
        parser_operator=None,
        parser_value_mm=None,
        legacy=GAP,
    ),
    ComparisonCase(
        name="explicit_gsl_lte_blade_height",
        question="Geef voor GSL de schrapers met meshoogte op of onder 3 mm.",
        parser_state=BladeHeightPredicateParseState.VALID,
        parser_reason=None,
        parser_operator=BladeHeightComparisonOperator.LTE,
        parser_value_mm=Decimal("3"),
        legacy=INSPECTION_LOOKUP,
    ),
    ComparisonCase(
        name="leading_whitespace_keeps_raw_parser_span",
        question="  Geef voor GSL de schrapers met meshoogte op of onder 3 mm.",
        parser_state=BladeHeightPredicateParseState.VALID,
        parser_reason=None,
        parser_operator=BladeHeightComparisonOperator.LTE,
        parser_value_mm=Decimal("3"),
        parser_span=(33, 59, "meshoogte op of onder 3 mm"),
        legacy=INSPECTION_LOOKUP,
    ),
    ComparisonCase(
        name="explicit_approximate_blade_height_is_ambiguous",
        question="Geef voor GSL de schrapers met meshoogte rond 3 mm.",
        parser_state=BladeHeightPredicateParseState.AMBIGUOUS,
        parser_reason=BladeHeightPredicateParseReason.APPROXIMATE_VALUE,
        parser_operator=None,
        parser_value_mm=None,
        legacy=INSPECTION_LOOKUP,
    ),
    ComparisonCase(
        name="negative_blade_height_is_invalid",
        question="Geef voor GSL de schrapers met meshoogte onder -3 mm.",
        parser_state=BladeHeightPredicateParseState.INVALID,
        parser_reason=BladeHeightPredicateParseReason.NEGATIVE_VALUE,
        parser_operator=None,
        parser_value_mm=None,
        legacy=INSPECTION_LOOKUP,
    ),
    ComparisonCase(
        name="de3_identifier_is_not_a_blade_height_predicate",
        question="toon band DE3",
        parser_state=BladeHeightPredicateParseState.NO_MATCH,
        parser_reason=BladeHeightPredicateParseReason.NO_MEASUREMENT_PREDICATE,
        parser_operator=None,
        parser_value_mm=None,
        legacy=INSPECTION_LOOKUP,
    ),
    ComparisonCase(
        name="grounded_inspection_control_keeps_existing_action",
        question="Wat is de laatste inspectiestatus van de schrapers?",
        parser_state=BladeHeightPredicateParseState.NO_MATCH,
        parser_reason=BladeHeightPredicateParseReason.NO_MEASUREMENT_PREDICATE,
        parser_operator=None,
        parser_value_mm=None,
        legacy=INSPECTION_LATEST,
        use_synthetic_grounded_scope=True,
    ),
    ComparisonCase(
        name="composed_two_measurements_are_ambiguous",
        question="Geef voor GSL de schrapers met meshoogte onder 3 mm en boven 5 mm.",
        parser_state=BladeHeightPredicateParseState.AMBIGUOUS,
        parser_reason=BladeHeightPredicateParseReason.UNSUPPORTED_COMPOSITION,
        parser_operator=None,
        parser_value_mm=None,
        legacy=INSPECTION_LOOKUP,
    ),
)


def _value(value):
    return getattr(value, "value", value)


def _legacy_plan(question: str):
    # This mirrors the service's request selection cleanup for the legacy path.
    return build_execution_plan(apply_routing_sanity(understanding_module.understand_query(question.strip())))


def _snapshot(plan) -> dict[str, object]:
    return {
        "query_class": _value(plan.query_class),
        "domains": tuple(_value(domain) for domain in plan.domains),
        "intent": plan.intent,
        "blockers": tuple(
            (
                _value(blocker.blocker_type),
                blocker.entity_name,
                str(blocker.candidate_value),
                blocker.reason,
            )
            for blocker in plan.execution_blockers
        ),
        "clarification_required": plan.clarification_required,
        "clarification_question": plan.clarification_question,
        "actions": tuple(step.action for step in plan.execution_steps),
        "step_params": tuple(tuple(sorted(step.params.items())) for step in plan.execution_steps),
    }


def _assert_legacy_contract(plan, expected: LegacyExpectation):
    snapshot = _snapshot(plan)
    assert snapshot["query_class"] == "business"
    assert snapshot["domains"] == expected.domains
    assert snapshot["intent"] == expected.intent
    assert snapshot["blockers"] == expected.blockers
    assert snapshot["clarification_required"] is expected.clarification_required
    assert snapshot["clarification_question"] == expected.clarification_question
    assert snapshot["actions"] == expected.actions


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_pure_parser_and_legacy_planning_are_characterized_separately(case, monkeypatch):
    if case.use_synthetic_grounded_scope:
        monkeypatch.setattr(
            understanding_module,
            "resolve_scope_context",
            lambda _normalized_question: SYNTHETIC_GROUNDED_SCOPE,
        )

    # The existing plan must stay unchanged when the standalone parser runs.
    plan_before_parser = _legacy_plan(case.question)
    plan_snapshot_before_parser = _snapshot(plan_before_parser)

    parsed = parse_explicit_blade_height_predicate(case.question)

    assert _snapshot(plan_before_parser) == plan_snapshot_before_parser
    assert parsed.state is case.parser_state
    assert parsed.reason is case.parser_reason
    if case.parser_operator is None:
        assert parsed.predicate is None
    else:
        assert parsed.predicate is not None
        assert parsed.predicate.operator is case.parser_operator
        assert parsed.predicate.value_mm == case.parser_value_mm

    if case.parser_span is not None:
        assert parsed.predicate is not None
        span = parsed.predicate.source_span
        assert (span.start, span.end, span.text) == case.parser_span
        assert case.question[span.start : span.end] == span.text

    # Compare a legacy baseline with a repeat that has the parser in between.
    legacy_baseline = _snapshot(_legacy_plan(case.question))
    parse_explicit_blade_height_predicate(case.question)
    legacy_with_parser_between = _snapshot(_legacy_plan(case.question))
    assert legacy_with_parser_between == legacy_baseline
    _assert_legacy_contract(plan_before_parser, case.legacy)

    if case.use_synthetic_grounded_scope:
        assert plan_before_parser.entities["scope_code"].value == "MV1"
        assert plan_before_parser.execution_steps[0].params == {
            "vraag": case.question.strip(),
            "mode": "auto",
            "scope_code": "MV1",
            "scope_type": "installation",
            "area_code": "GSL",
            "installation_code": "MV1",
        }
