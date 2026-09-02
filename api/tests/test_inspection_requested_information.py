from __future__ import annotations

from app.orchestrator.complexity import (
    assess_research_requirement,
)
from app.orchestrator.planner import (
    build_execution_plan,
)
from app.orchestrator.understanding import (
    understand_query,
)


COMPOSITE = (
    "Geef een korte slijtageanalyse van de schrapers op band A660: "
    "laatste meshoogte per schraper, lifecycle-trend, vervangevents "
    "en vervangadvies. Benoem onzekerheden."
)


def _copy_plan(plan):
    if hasattr(
        plan,
        "model_copy",
    ):
        return plan.model_copy(
            deep=True
        )

    return plan.copy(
        deep=True
    )


def test_composite_inspection_facets_use_richest_fit_intent():
    plan = understand_query(
        COMPOSITE
    )

    assert plan.intent == (
        "replacement_advice"
    )

    assert plan.requested_information == [
        "latest_measurements",
        "lifecycle_trend",
        "replacement_events",
        "replacement_advice",
        "uncertainties",
    ]


def test_composite_uses_one_deep_analysis_execution_step():
    plan = understand_query(
        COMPOSITE
    )

    execution_plan = build_execution_plan(
        plan
    )

    assert len(
        execution_plan.execution_steps
    ) == 1

    step = (
        execution_plan.execution_steps[0]
    )

    assert step.action == (
        "analysis_assistant"
    )

    assert step.params["vraag"] == (
        "vervangadvies voor band A660"
    )

    assert execution_plan.original_question == (
        COMPOSITE
    )


def test_pure_trend_remains_inspection_trend():
    question = (
        "Toon de lifecycle-trend "
        "van band A660."
    )

    plan = understand_query(
        question
    )

    assert plan.intent == (
        "inspection_trend"
    )

    execution_plan = build_execution_plan(
        plan
    )

    assert (
        execution_plan
        .execution_steps[0]
        .params["vraag"]
        == "toon de trend van band A660"
    )


def test_single_inspection_facets_are_detected():
    cases = [
        (
            "Wat is de laatste meshoogte "
            "per schraper op band A660?",
            "latest_measurements",
        ),
        (
            "Toon de lifecycle-trend "
            "van band A660.",
            "lifecycle_trend",
        ),
        (
            "Welke vervangevents zijn "
            "er voor band A660?",
            "replacement_events",
        ),
        (
            "Geef vervangadvies "
            "voor band A660.",
            "replacement_advice",
        ),
        (
            "Benoem onzekerheden in "
            "de inspectiedata van band A660.",
            "uncertainties",
        ),
    ]

    for question, expected in cases:
        plan = understand_query(
            question
        )

        assert expected in (
            plan.requested_information
        )


def test_historical_replacement_is_not_advice():
    plan = understand_query(
        "Wanneer is de schraper vervangen "
        "op band A660?"
    )

    assert (
        "replacement_events"
        in plan.requested_information
    )

    assert (
        "replacement_advice"
        not in plan.requested_information
    )

    assert plan.intent != (
        "replacement_advice"
    )


def test_inspection_facets_do_not_raise_complexity_score():
    detected = understand_query(
        COMPOSITE
    )

    without_facets = _copy_plan(
        detected
    )
    without_facets.requested_information = []

    with_facets = _copy_plan(
        detected
    )

    baseline = assess_research_requirement(
        without_facets
    )

    assessed = assess_research_requirement(
        with_facets
    )

    assert (
        assessed.complexity_score
        == baseline.complexity_score
    )

    assert (
        assessed.research_required
        == baseline.research_required
    )

    assert (
        "multiple_information_requests"
        not in assessed.complexity_reasons
    )

    assert assessed.multi_intent is True