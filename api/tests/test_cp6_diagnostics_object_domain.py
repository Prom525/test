from app.orchestrator.planner import build_execution_plan
from app.orchestrator.routing_sanity import apply_routing_sanity
from app.orchestrator.understanding import understand_query


def _value(value):
    return getattr(value, "value", value)


def _plan(question):
    return build_execution_plan(apply_routing_sanity(understand_query(question)))


def _domains(items):
    return [_value(item.domain if hasattr(item, "domain") else item) for item in items]


def test_s6_inspection_view_wins_over_negated_rfq_context():
    plan = _plan(
        "Controleer de health en dependencies van view "
        "vw_mes_lifecycle_cycles_clean; dit is geen RFQ-vraag."
    )

    assert _value(plan.primary_domain) == "diagnostics"
    assert plan.entities["diagnostics_domain"].value == "inspections"
    assert plan.entities["diagnostics_objects"].value == [
        "vw_mes_lifecycle_cycles_clean"
    ]
    assert "rfq" not in _domains(plan.intent_tasks)
    assert _domains(plan.execution_steps) == ["diagnostics"]


def test_m2_organization_link_diagnostics_use_org_domain():
    plan = _plan(
        "Wie is verantwoordelijk voor VCA-documentatie en welke ontbrekende of "
        "conflicterende organisatiekoppelingen zijn er volgens diagnostics?"
    )

    assert _value(plan.primary_domain) == "diagnostics"
    assert plan.entities["diagnostics_domain"].value == "org"
    assert "org" in _domains(plan.intent_tasks)
    assert "diagnostics" in _domains(plan.intent_tasks)
    assert plan.execution_steps[-1].params["domain"] == "org"


def test_positive_rfq_diagnostics_use_rfq_domain():
    plan = _plan("Controleer diagnostics/readiness van bestaande RFQ-records.")

    assert plan.entities["diagnostics_domain"].value == "rfq"
    diagnostics_steps = [
        step for step in plan.execution_steps if _value(step.domain) == "diagnostics"
    ]
    assert diagnostics_steps[0].params["domain"] == "rfq"


def test_negated_rfq_never_selects_rfq_diagnostics_domain():
    plan = _plan(
        "Controleer diagnostics van vw_generic_status; dit is geen RFQ-vraag."
    )

    assert plan.entities["diagnostics_domain"].value == "database"
    assert "rfq" not in _domains(plan.intent_tasks)


def test_generic_view_diagnostics_keep_database_fallback():
    plan = _plan("Controleer diagnostics en dependencies van view vw_generic_status.")

    assert plan.entities["diagnostics_domain"].value == "database"
    assert plan.entities["diagnostics_objects"].value == ["vw_generic_status"]
