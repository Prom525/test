from app.orchestrator.planner import build_execution_plan
from app.orchestrator.models import Domain, IntentTask, QueryPlan
from app.orchestrator.response_shaping import shape_orchestrator_response
from app.orchestrator.routing_sanity import apply_routing_sanity
from app.orchestrator.task_planner_canary import build_task_planner_canary
from app.orchestrator.understanding import understand_query


CASES = {
    "M4": "Welke bestaande RFQ's bevatten Belle Banne U, wat is hun status/readiness, welke productcontext geldt en welke technische punten staan nog open?",
    "S5": "Beoordeel de readiness en datakwaliteitsproblemen van bestaande RFQ-records.",
    "S6": "Controleer de health en dependencies van view vw_mes_lifecycle_cycles_clean; dit is geen RFQ-vraag.",
    "M2": "Wie is verantwoordelijk voor VCA-documentatie en welke ontbrekende of conflicterende organisatiekoppelingen zijn er volgens diagnostics?",
    "M3": "Welke Belle Banne U-configuratie past op een transportband van 1200 mm, en wat zijn de technische limieten volgens CEMA? Geen inspectie of ORG.",
    "S3": "Leg de CEMA-methode voor transportbandrolbelasting uit; geen inspectie, productselectie, ORG of RFQ.",
}


def _value(value):
    return getattr(value, "value", value)


def _canary(name):
    plan = build_execution_plan(apply_routing_sanity(understand_query(CASES[name])))
    return plan, build_task_planner_canary(plan)


def test_m4_and_s5_match_the_legacy_plan_exactly():
    for name, domains in (("M4", ["rfq", "product", "technical"]), ("S5", ["rfq"])):
        _plan, canary = _canary(name)
        assert [row["domain"] for row in canary["tasks"]] == domains
        assert canary["summary"] == {
            "legacy_steps": len(domains),
            "canary_steps": len(domains),
            "exact_matches": len(domains),
            "missing_in_legacy": 0,
            "extra_in_legacy": 0,
            "action_mismatches": 0,
        }


def test_s6_and_m2_expose_required_org_gap_without_changing_legacy_steps():
    for name in ("S6", "M2"):
        plan, canary = _canary(name)
        before = [(step.step_id, _value(step.domain), step.action) for step in plan.execution_steps]
        org = next(row for row in canary["tasks"] if row["domain"] == "org")
        assert org["proposed_action"] == "org_assistant"
        assert org["matched_legacy_step_id"] is None
        assert org["match_status"] == "missing_in_legacy"
        assert canary["summary"]["missing_in_legacy"] == 1
        assert [(step.step_id, _value(step.domain), step.action) for step in plan.execution_steps] == before
    assert _canary("S6")[0].entities["diagnostics_domain"].value == "inspections"
    assert _canary("M2")[0].entities["diagnostics_domain"].value == "org"


def test_m3_and_s3_never_propose_excluded_domains():
    m3_plan, m3 = _canary("M3")
    assert [row["domain"] for row in m3["tasks"]] == ["product", "technical"]
    assert set(m3["excluded_domains"]) == {"inspection", "org"}
    assert "band_code" not in m3_plan.entities
    assert m3_plan.entities["belt_width_mm"].value == 1200

    _s3_plan, s3 = _canary("S3")
    assert [row["domain"] for row in s3["tasks"]] == ["technical"]
    assert set(s3["excluded_domains"]) == {"inspection", "product", "org", "rfq"}


def test_optional_excluded_and_plan_excluded_tasks_are_not_proposed():
    plan = QueryPlan(
        original_question="test",
        normalized_question="test",
        excluded_domains=[Domain.ORG],
        intent_tasks=[
            IntentTask(task_id="required", domain=Domain.TECHNICAL, intent="technical_lookup"),
            IntentTask(task_id="optional", domain=Domain.PRODUCT, intent="product_lookup", required=False),
            IntentTask(task_id="negative", domain=Domain.RFQ, intent="rfq_lookup", polarity="excluded"),
            IntentTask(task_id="excluded-domain", domain=Domain.ORG, intent="org_lookup"),
        ],
    )
    canary = build_task_planner_canary(plan)
    assert [row["task_id"] for row in canary["tasks"]] == ["required"]
    assert [step["action"] for step in canary["proposed_steps"]] == ["technical_assistant"]


def test_canary_is_debug_only_and_compact_keeps_cp8_summary_only():
    _plan, canary = _canary("M4")
    response = {
        "status": "ok",
        "answer": "ok",
        "query_plan": {"domains": ["rfq", "product", "technical"]},
        "results": [],
        "task_planner_canary": canary,
        "task_execution_shadow": {"summary": {"required_total": 3, "required_missing": 0}},
    }
    assert shape_orchestrator_response(response, "debug")["task_planner_canary"] == canary
    compact = shape_orchestrator_response(response, "compact")
    assert "task_planner_canary" not in compact
    assert "task_planner_canary_summary" not in compact
    assert compact["task_execution_shadow_summary"] == {
        "required_total": 3,
        "required_missing": 0,
    }
