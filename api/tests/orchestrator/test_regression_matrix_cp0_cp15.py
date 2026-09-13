from __future__ import annotations

import pytest

from app.orchestrator.executor import execute_plan
from app.orchestrator.models import Domain, ExecutionStep, QueryPlan
from app.orchestrator.planner import build_execution_plan
from app.orchestrator.query_classification import classify_query
from app.orchestrator.routing_sanity import apply_routing_sanity
from app.orchestrator.task_concise_composer import MAX_PUBLIC_ANSWER_BYTES, MAX_PUBLIC_BULLETS, MAX_PUBLIC_LINES, compose_concise_public_answer
from app.orchestrator.understanding import understand_query


def _value(value):
    return getattr(value, "value", value)


def _plan(question):
    return build_execution_plan(apply_routing_sanity(understand_query(question)))


@pytest.mark.parametrize(("question", "expected"), (
    ("Geef productinformatie over BB-U.", "business"),
    ("Hoe werkt de orchestrator technisch?", "system_meta"),
    ("Bedankt, dit ziet er goed uit.", "conversational"),
    ("Wat kost die?", "unknown"),
    # Current CP0 behavior; desired future behavior is system_meta.
    ("Waarom werd deze vraag naar de RFQ-specialist gerouteerd?", "business"),
))
def test_query_classification_matrix(question, expected):
    assert _value(classify_query(question)) == expected


@pytest.mark.parametrize(("question", "excluded"), (
    ("Geef productinformatie over de Belle Banne U, geen inspectieanalyse.", "inspection"),
    ("Leg CEMA rolbelasting uit, maar geef geen productadvies.", "product"),
    ("Bekijk de productinformatie van BB-U 1200 mm, geen RFQ-vraag.", "rfq"),
))
def test_negated_domain_never_gets_task_or_step(question, excluded):
    plan = _plan(question)
    assert excluded in {_value(item) for item in plan.excluded_domains}
    assert excluded not in {_value(item.domain) for item in plan.intent_tasks if item.polarity == "requested"}
    assert excluded not in {_value(item.domain) for item in plan.execution_steps}


@pytest.mark.parametrize("question", ("Wat is de Belle Banne U 1200 mm?", "Welke uitvoering van 1200 mm is geschikt voor een BB-U schraper?"))
def test_1200_mm_is_dimension_not_band_code(question):
    plan = _plan(question)
    assert "band_code" not in plan.entities or plan.entities["band_code"].value is None
    assert plan.entities["belt_width_mm"].value == 1200


def test_explicit_band_code_is_preserved():
    assert _plan("Wat is de laatste inspectiestatus van band A319?").entities["band_code"].value == "A319"


def test_meta_band_mention_does_not_execute():
    plan = _plan("Waarom wordt AL5 als bandcode gezien?")
    assert _value(plan.query_class) == "system_meta"
    assert {_value(step.domain) for step in plan.execution_steps} <= {"diagnostics"}
    assert all(step.params.get("band_code") != "AL5" for step in plan.execution_steps)


def test_technical_without_inspection_current_known_gap_is_characterized():
    plan = _plan("Welke technische selectiecriteria gelden voor een U-schraper bij 1200 mm, zonder inspectiedata te gebruiken?")
    assert [_value(item) for item in plan.domains] == ["inspection"]
    assert [_value(item) for item in plan.excluded_domains] == []
    assert [_value(step.domain) for step in plan.execution_steps] == ["inspection"]


def test_multi_band_comparison_does_not_silently_execute_one_band():
    plan = _plan("Vergelijk MV1 en MV2 op inspectiestatus.")
    assert plan.clarification_required or len({s.params.get("band_code") for s in plan.execution_steps if s.params.get("band_code")}) != 1


def test_clarification_executes_nothing():
    plan = _plan("Wat kost die?")
    called = []
    results, trace = execute_plan(plan, lambda path, payload: called.append((path, payload)) or {})
    assert results == [] and called == []
    assert plan.clarification_required


def test_unknown_action_is_rejected_without_calling_sender():
    plan = QueryPlan(original_question="x", normalized_question="x", primary_domain=Domain.PRODUCT, domains=[Domain.PRODUCT], execution_steps=[ExecutionStep(step_id="x", domain=Domain.PRODUCT, action="not_registered", params={})])
    called = []
    results, trace = execute_plan(plan, lambda *_: called.append(True) or {})
    assert results == [] and called == []
    assert trace.attempts[0].accepted is False
    assert "Geen endpoint geregistreerd" in trace.attempts[0].error


@pytest.mark.parametrize(("payload", "accepted", "count"), (
    ({"status": "ok", "resultaat": []}, True, 0),
    ({"status": "not_found", "resultaat": []}, True, 0),
    ({"status": "unavailable", "error": "synthetic"}, True, None),
    ({"status": "error", "error": "synthetic"}, False, None),
))
def test_current_legacy_execution_semantics_are_characterized(payload, accepted, count):
    plan = QueryPlan(original_question="x", normalized_question="x", primary_domain=Domain.PRODUCT, domains=[Domain.PRODUCT], execution_steps=[ExecutionStep(step_id="x", domain=Domain.PRODUCT, action="product_assistant", params={"vraag": "x"})])
    results, trace = execute_plan(plan, lambda *_: dict(payload))
    assert trace.attempts[0].accepted is accepted
    assert trace.attempts[0].result_count == count
    assert len(results) == 1


def test_public_composer_bounds_lines_bullets_bytes_and_authority():
    text = "Titel\n" + "\n".join(f"- regel {i} " + "x" * 220 for i in range(30))
    answer, status = compose_concise_public_answer(text, "Veilige fallback.", task_coverage_gate_cp10={"authoritative": True}, task_presenter_cp11={"authoritative": True, "public_answer_replaced": True})
    assert len(answer.encode("utf-8")) <= MAX_PUBLIC_ANSWER_BYTES
    assert len(answer.splitlines()) <= MAX_PUBLIC_LINES
    assert sum(line.startswith("- ") for line in answer.splitlines()) <= MAX_PUBLIC_BULLETS
    assert status["authoritative"] is False
