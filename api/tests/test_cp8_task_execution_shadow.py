from app.orchestrator.models import (
    Domain,
    IntentTask,
    OrchestratorTrace,
    QueryPlan,
    TraceAttempt,
)
from app.orchestrator.planner import build_execution_plan
from app.orchestrator.response_shaping import compact_orchestrator_response
from app.orchestrator.routing_sanity import apply_routing_sanity
from app.orchestrator.task_execution_shadow import build_task_execution_shadow
from app.orchestrator.understanding import understand_query


CASES = {
    "M4": "Welke bestaande RFQ's bevatten Belle Banne U, wat is hun status/readiness, welke productcontext geldt en welke technische punten staan nog open?",
    "S5": "Beoordeel de readiness en datakwaliteitsproblemen van bestaande RFQ-records.",
    "M3": "Welke Belle Banne U-configuratie past op een transportband van 1200 mm, en wat zijn de technische limieten volgens CEMA? Geen inspectie of ORG.",
    "S3": "Leg de CEMA-methode voor transportbandrolbelasting uit; geen inspectie, productselectie, ORG of RFQ.",
    "S6": "Controleer de health en dependencies van view vw_mes_lifecycle_cycles_clean; dit is geen RFQ-vraag.",
    "M2": "Wie is verantwoordelijk voor VCA-documentatie en welke ontbrekende of conflicterende organisatiekoppelingen zijn er volgens diagnostics?",
}


def _shadow(question):
    plan = build_execution_plan(apply_routing_sanity(understand_query(question)))
    trace = OrchestratorTrace(attempts=[
        TraceAttempt(
            attempt_no=index,
            step_id=step.step_id,
            domain=step.domain,
            action=step.action,
            status="ok",
            accepted=True,
        )
        for index, step in enumerate(plan.execution_steps, start=1)
    ])
    return plan, build_task_execution_shadow(plan, trace)


def test_cp8_expected_cases_are_covered_without_exclusion_gaps():
    for name, question in CASES.items():
        plan, shadow = _shadow(question)
        assert shadow["summary"]["required_total"] == len(plan.intent_tasks), name
        expected_missing = 1 if name in {"S6", "M2"} else 0
        assert shadow["summary"]["required_missing"] == expected_missing, name
        diagnostics = [row for row in shadow["tasks"] if row["domain"] == "diagnostics"]
        if diagnostics:
            assert diagnostics[0]["planned"] and diagnostics[0]["executed"], name
        assert not set(shadow["excluded_domains"]).intersection(
            row["domain"] for row in shadow["tasks"]
        ), name


def test_cp8_missing_required_task_is_reported_but_does_not_raise():
    plan = QueryPlan(
        original_question="test",
        normalized_question="test",
        intent_tasks=[
            IntentTask(task_id="task_1", domain=Domain.ORG, intent="org_lookup")
        ],
    )
    shadow = build_task_execution_shadow(plan)
    assert shadow["summary"] == {
        "required_total": 1,
        "required_planned": 0,
        "required_executed": 0,
        "required_missing": 1,
        "missing_required_tasks": ["task_1"],
    }
    assert shadow["tasks"][0]["gap_reason"] == "not_planned"


def test_cp8_compact_response_contains_summary_not_full_shadow():
    _plan, shadow = _shadow(CASES["M4"])
    compact = compact_orchestrator_response({
        "status": "ok",
        "answer": "ok",
        "query_plan": {"domains": ["rfq", "product", "technical"]},
        "results": [],
        "task_execution_shadow": shadow,
    })
    assert compact["task_execution_shadow_summary"]["required_missing"] == 0
    assert "task_execution_shadow" not in compact
    assert "tasks" not in compact["task_execution_shadow_summary"]
