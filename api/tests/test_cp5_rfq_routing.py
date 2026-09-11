from app.orchestrator.planner import build_execution_plan
from app.orchestrator.routing_sanity import apply_routing_sanity
from app.orchestrator.understanding import understand_query


def _value(value):
    return getattr(value, "value", value)


def _plan(question):
    return build_execution_plan(apply_routing_sanity(understand_query(question)))


def _domains(items):
    return [_value(item.domain if hasattr(item, "domain") else item) for item in items]


def test_s5_rfq_readiness_is_first_class_route():
    plan = _plan(
        "Beoordeel de readiness en datakwaliteitsproblemen van bestaande RFQ-records."
    )

    assert _value(plan.primary_domain) == "rfq"
    assert _domains(plan.domains) == ["rfq"]
    assert plan.intent == "rfq_readiness"
    assert _domains(plan.intent_tasks) == ["rfq"]
    assert [task.intent for task in plan.intent_tasks] == ["rfq_readiness"]
    assert _domains(plan.execution_steps) == ["rfq"]
    assert [step.action for step in plan.execution_steps] == ["rfq_assistant"]
    assert not plan.clarification_required


def test_m4_routes_rfq_product_and_technical():
    plan = _plan(
        "Welke bestaande RFQ's bevatten Belle Banne U, wat is hun status/readiness, "
        "welke productcontext geldt en welke technische punten staan nog open?"
    )

    assert _value(plan.primary_domain) == "rfq"
    assert set(_domains(plan.domains)) == {"rfq", "product", "technical"}
    assert _domains(plan.intent_tasks) == ["rfq", "product", "technical"]
    assert _domains(plan.execution_steps) == ["rfq", "product", "technical"]


def test_s6_negated_rfq_does_not_route_to_rfq():
    plan = _plan(
        "Controleer de health en dependencies van view "
        "vw_mes_lifecycle_cycles_clean; dit is geen RFQ-vraag."
    )

    assert _value(plan.primary_domain) == "diagnostics"
    assert "rfq" not in _domains(plan.domains)
    assert "rfq" not in _domains(plan.intent_tasks)
    assert "rfq" not in _domains(plan.execution_steps)
    assert plan.entities["diagnostics_domain"].value == "inspections"


def test_plain_product_question_stays_product_only():
    plan = _plan("Geef productinformatie over de Belle Banne U.")

    assert _value(plan.primary_domain) == "product"
    assert _domains(plan.domains) == ["product"]
    assert _domains(plan.intent_tasks) == ["product"]
    assert _domains(plan.execution_steps) == ["product"]


def test_offerte_and_readiness_terms_route_to_rfq():
    for question in (
        "Welke offertevragen staan nog open?",
        "Beoordeel de readiness van de bestaande records.",
    ):
        plan = _plan(question)
        assert _value(plan.primary_domain) == "rfq"
        assert "rfq" in _domains(plan.domains)
        assert _domains(plan.execution_steps)[0] == "rfq"


def test_cp3_cp4_m3_regression_guard():
    plan = _plan(
        "Welke Belle Banne U-configuratie past op een transportband van 1200 mm, "
        "en wat zijn de technische limieten volgens CEMA? Geen inspectie of ORG."
    )

    assert _domains(plan.domains) == ["product", "technical"]
    assert _domains(plan.intent_tasks) == ["product", "technical"]
    assert _domains(plan.execution_steps) == ["product", "technical"]
    assert "band_code" not in plan.entities
    assert plan.entities["belt_width_mm"].value == 1200
