from __future__ import annotations

import pytest

from app.orchestrator.planner import (
    build_execution_plan,
)
from app.orchestrator.understanding import (
    Domain,
    understand_query,
)


@pytest.mark.parametrize(
    "question",
    [
        (
            "Moet er iets vervangen worden "
            "bij Band A660?"
        ),
        (
            "Welke schraper moet vervangen "
            "worden op Band A660?"
        ),
        (
            "Welke schrapers moeten vervangen "
            "worden op Band A660?"
        ),
        "Wat moet vervangen worden op Band A660?",
        "Geef vervangadvies voor Band A660",
    ],
)
def test_explicit_replacement_advice_routes_correctly(
    question: str,
):
    plan = understand_query(
        question
    )

    assert (
        plan.primary_domain
        == Domain.INSPECTION
    )

    assert (
        plan.intent
        == "replacement_advice"
    )


def test_replacement_advice_gets_canonical_execution_question():
    plan = understand_query(
        "Moet er iets vervangen worden "
        "bij Band A660?"
    )

    execution_plan = (
        build_execution_plan(
            plan
        )
    )

    assert (
        execution_plan.intent
        == "replacement_advice"
    )

    assert (
        len(
            execution_plan.execution_steps
        )
        == 1
    )

    step = (
        execution_plan.execution_steps[0]
    )

    assert (
        step.action
        == "analysis_assistant"
    )

    assert (
        step.params["band_code"]
        == "A660"
    )

    assert (
        step.params["vraag"]
        == "vervangadvies voor band A660"
    )


def test_maintenance_priority_stays_maintenance_priority():
    plan = understand_query(
        "Wat heeft prioriteit qua "
        "onderhoud op Band A660?"
    )

    assert (
        plan.intent
        == "maintenance_priority"
    )

    execution_plan = (
        build_execution_plan(
            plan
        )
    )

    assert (
        execution_plan.execution_steps[0]
        .params["vraag"]
        == "onderhoudsplanning voor band A660"
    )


def test_what_must_be_replaced_is_advice_not_maintenance():
    plan = understand_query(
        "Wat moet vervangen worden "
        "op Band A660?"
    )

    assert (
        plan.intent
        == "replacement_advice"
    )


def test_latest_replacement_history_is_not_advice():
    plan = understand_query(
        "Wat was de laatste vervanging "
        "op Band A660?"
    )

    assert (
        plan.intent
        == "inspection_latest"
    )


def test_when_was_scraper_replaced_is_not_advice():
    plan = understand_query(
        "Wanneer is de schraper vervangen "
        "op Band A660?"
    )

    assert (
        plan.intent
        != "replacement_advice"
    )


def test_generic_inspection_lookup_remains_unchanged():
    plan = understand_query(
        "Hoe staat Band A660 ervoor?"
    )

    assert (
        plan.intent
        == "inspection_lookup"
    )


def test_trend_routing_remains_unchanged():
    plan = understand_query(
        "Toon de slijtagetrend "
        "van Band A660"
    )

    assert (
        plan.intent
        == "inspection_trend"
    )