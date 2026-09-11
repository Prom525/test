from app.orchestrator.planner import build_execution_plan
from app.orchestrator.routing_sanity import apply_routing_sanity
from app.orchestrator.understanding import understand_query


def _value(value):
    return getattr(value, "value", value)


def _plan(question):
    return build_execution_plan(apply_routing_sanity(understand_query(question)))


def _domains(plan):
    return [_value(domain) for domain in plan.domains]


def _task_domains(plan):
    return [_value(task.domain) for task in plan.intent_tasks]


def _step_domains(plan):
    return [_value(step.domain) for step in plan.execution_steps]


def test_s1_negated_product_advice_does_not_create_product_task():
    plan = _plan(
        "Geef alleen de meest recente inspectiestatus, meshoogtes, opmerkingen "
        "en recente vervangingen voor band A319; geen productadvies."
    )
    assert _domains(plan) == ["inspection"]
    assert "product" not in _task_domains(plan)
    assert _step_domains(plan) == ["inspection"]


def test_s2_and_s4_negated_inspection_is_not_routed():
    questions = (
        "Geef productinformatie over de Belle Banne U. Geen inspectieanalyse.",
        "Wie is verantwoordelijk voor de VCA-documentatie bij Promati? Geen inspectieanalyse.",
    )
    for question in questions:
        plan = _plan(question)
        assert "inspection" not in _domains(plan)
        assert "inspection" not in _task_domains(plan)
        assert "inspection" not in _step_domains(plan)


def test_s3_negated_domain_enumeration_keeps_only_technical():
    plan = _plan(
        "Leg de CEMA-methode voor transportbandrolbelasting uit; geen inspectie, "
        "productselectie, ORG of RFQ."
    )
    assert _domains(plan) == ["technical"]
    assert _task_domains(plan) == ["technical"]
    assert _step_domains(plan) == ["technical"]


def test_s6_negated_rfq_does_not_select_rfq_diagnostics_domain():
    plan = _plan(
        "Controleer de health en dependencies van view "
        "vw_mes_lifecycle_cycles_clean; dit is geen RFQ-vraag."
    )
    assert _value(plan.primary_domain) == "diagnostics"
    assert plan.entities["diagnostics_domain"].value == "inspections"
    assert _step_domains(plan) == ["diagnostics"]


def test_m3_negated_inspection_and_org_keep_product_and_technical():
    plan = _plan(
        "Welke Belle Banne U-configuratie past op een transportband van 1200 mm, "
        "en wat zijn de technische limieten volgens CEMA? Geen inspectie of ORG."
    )
    assert _domains(plan) == ["product", "technical"]
    assert _task_domains(plan) == ["product", "technical"]
    assert _step_domains(plan) == ["product", "technical"]


def test_positive_inspection_and_product_routes_remain_intact():
    inspection = _plan(
        "Voor lijn MV1: wat is de laatste inspectiestatus en welke "
        "onderhoudsprioriteit volgt daaruit?"
    )
    product = _plan("Geef productinformatie over de Belle Banne U.")
    assert _value(inspection.primary_domain) == "inspection"
    assert "inspection" in _domains(inspection)
    assert _value(product.primary_domain) == "product"
    assert _domains(product) == ["product"]
