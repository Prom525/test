from app.orchestrator.models import Domain
from app.orchestrator.understanding import (
    understand_query,
)


def test_org_routing_function_question():
    plan = understand_query(
        "Wat is de functie van Aaron Thys?"
    )

    assert plan.primary_domain is Domain.ORG
    assert plan.intent == "org_lookup"
    assert plan.clarification_required is False


def test_org_routing_vca_coordinator():
    plan = understand_query(
        "Wie is de VCA-coordinator?"
    )

    assert plan.primary_domain is Domain.ORG
    assert plan.intent == "org_lookup"
    assert plan.clarification_required is False


def test_org_routing_responsibility():
    plan = understand_query(
        "Wie is verantwoordelijk voor VCA?"
    )

    assert plan.primary_domain is Domain.ORG
    assert plan.intent == "org_lookup"
    assert plan.clarification_required is False


def test_org_routing_does_not_steal_product_question():
    plan = understand_query(
        "Wat is de functie van een bandschraper?"
    )

    assert plan.primary_domain is not Domain.ORG