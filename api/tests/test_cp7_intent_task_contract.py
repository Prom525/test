from app.orchestrator.models import Domain, IntentTask
from app.orchestrator.planner import build_execution_plan
from app.orchestrator.response_shaping import compact_orchestrator_response
from app.orchestrator.routing_sanity import apply_routing_sanity
from app.orchestrator.understanding import understand_query


def _value(value):
    return getattr(value, "value", value)


def _plan(question):
    return build_execution_plan(apply_routing_sanity(understand_query(question)))


def _tasks_by_domain(plan):
    return {_value(task.domain): task for task in plan.intent_tasks}


def test_intent_task_cp7_defaults_are_backwards_compatible():
    task = IntentTask(task_id="task_1", domain=Domain.PRODUCT, intent="product_lookup")

    assert task.required is True
    assert task.polarity == "requested"
    assert task.coverage_requirement is None
    assert task.exclusion_reason is None


def test_s5_rfq_task_has_required_requested_evidence_metadata():
    plan = _plan(
        "Beoordeel de readiness en datakwaliteitsproblemen van bestaande RFQ-records."
    )
    task = plan.intent_tasks[0]

    assert _value(task.domain) == "rfq"
    assert task.required is True
    assert task.polarity == "requested"
    assert task.evidence_requirement_set_id == "rfq_status.v1"
    assert task.coverage_requirement == task.evidence_requirement_set_id


def test_m4_positive_task_parts_are_required_and_requested():
    plan = _plan(
        "Welke bestaande RFQ's bevatten Belle Banne U, wat is hun status/readiness, "
        "welke productcontext geldt en welke technische punten staan nog open?"
    )
    tasks = _tasks_by_domain(plan)

    assert set(tasks) == {"rfq", "product", "technical"}
    assert all(task.required is True for task in tasks.values())
    assert all(task.polarity == "requested" for task in tasks.values())
    assert all(task.coverage_requirement for task in tasks.values())


def test_m3_records_requested_tasks_and_non_executable_exclusions():
    plan = _plan(
        "Welke Belle Banne U-configuratie past op een transportband van 1200 mm, "
        "en wat zijn de technische limieten volgens CEMA? Geen inspectie of ORG."
    )

    assert set(_tasks_by_domain(plan)) == {"product", "technical"}
    assert {_value(domain) for domain in plan.excluded_domains} == {"inspection", "org"}
    assert {_value(step.domain) for step in plan.execution_steps} == {"product", "technical"}


def test_s3_negated_domains_never_become_requested_or_executable_tasks():
    plan = _plan(
        "Leg de CEMA-methode voor transportbandrolbelasting uit; geen inspectie, "
        "productselectie, ORG of RFQ."
    )

    assert list(_tasks_by_domain(plan)) == ["technical"]
    assert {_value(domain) for domain in plan.excluded_domains} == {
        "inspection",
        "product",
        "org",
        "rfq",
    }
    assert [_value(step.domain) for step in plan.execution_steps] == ["technical"]


def test_compact_tasks_include_only_bounded_cp7_metadata():
    task = IntentTask(
        task_id="task_1",
        domain=Domain.PRODUCT,
        intent="product_lookup",
        requested_information=["x" * 10_000],
        scope={"raw": "x" * 10_000},
    )
    response = compact_orchestrator_response(
        {
            "status": "ok",
            "answer": "ok",
            "query_plan": {"domains": ["product"], "intent_tasks": [task.model_dump()]},
            "results": [],
        }
    )

    assert response["tasks"] == [
        {
            "task_id": "task_1",
            "domain": "product",
            "intent": "product_lookup",
            "primary": False,
            "required": True,
            "polarity": "requested",
        }
    ]
