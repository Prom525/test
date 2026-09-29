from __future__ import annotations

import json

import pytest

from app.orchestrator import blade_height_filter_applicability as applicability
from app.orchestrator import initial_planning_stage
from app.orchestrator import service
import app.orchestrator.understanding as understanding_module
from app.orchestrator.models import (
    DetectedEntity,
    Domain,
    OrchestratorAskRequest,
    QueryPlan,
)
from app.orchestrator.response_shaping import shape_orchestrator_response


def _plan(*, multi_intent: bool = False, scope: bool = True) -> QueryPlan:
    entities = {}
    if scope:
        entities["scope_code"] = DetectedEntity(
            name="scope_code",
            raw_value="mengveld 1",
            value="MV1",
            confidence=1.0,
            source="vw_gpt_band_asset_context.installation",
        )
        entities["scope_type"] = DetectedEntity(
            name="scope_type",
            raw_value="installation",
            value="installation",
            confidence=1.0,
            source="scope_resolver",
        )
        entities["installation_code"] = DetectedEntity(
            name="installation_code",
            raw_value="MV1",
            value="MV1",
            confidence=1.0,
            source="scope_resolver",
        )
    return QueryPlan(
        original_question="synthetic",
        normalized_question="synthetic",
        primary_domain=Domain.INSPECTION,
        domains=[Domain.INSPECTION],
        intent="inspection_lookup",
        entities=entities,
        requested_information=["inspection"],
        multi_intent=multi_intent,
        research_required=True,
    )


def _wire_boundary_plan(monkeypatch, plan: QueryPlan, calls: list[str]) -> None:
    monkeypatch.setattr(service, "understand_query", lambda *_args, **_kwargs: plan)
    monkeypatch.setattr(service, "apply_routing_sanity", lambda value: value)

    def forbidden(name):
        def call(*_args, **_kwargs):
            calls.append(name)
            raise AssertionError(f"{name} must not run for a filter boundary outcome")
        return call

    monkeypatch.setattr(service, "assess_research_requirement", forbidden("assessment"))
    monkeypatch.setattr(service, "build_execution_plan", forbidden("planning"))
    monkeypatch.setattr(service, "execute_plan", forbidden("specialist"))
    monkeypatch.setattr(service, "run_bounded_research", forbidden("research"))
    monkeypatch.setattr(service, "run_bounded_research_agent", forbidden("agent"))


_RESOLVED_SCOPE = {
    "status": "resolved",
    "scope": {
        "scope_type": "installation",
        "canonical_code": "MV1",
        "canonical_name": "Mengveld 1",
        "area_code": "GSL",
        "installation_code": "MV1",
        "matched_alias": "mv1",
        "source": "vw_gpt_band_asset_context.installation",
        "confidence": 1.0,
    },
    "candidates": [],
    "roles": {"active": [], "excluded": [], "comparison": [], "mentioned": []},
    "mode": "context_roles",
}


def _wire_real_understanding_filter_boundary(monkeypatch, calls: list[str]) -> None:
    """Keep understanding/routing real; isolate only resolver/external boundaries."""
    monkeypatch.setattr(
        understanding_module,
        "resolve_scope_context",
        lambda _question: _RESOLVED_SCOPE,
    )

    def forbidden(name):
        def call(*_args, **_kwargs):
            calls.append(name)
            raise AssertionError(f"{name} must not run for a filter boundary outcome")

        return call

    monkeypatch.setattr(service, "assess_research_requirement", forbidden("assessment"))
    monkeypatch.setattr(service, "build_execution_plan", forbidden("planning"))
    monkeypatch.setattr(service, "execute_plan", forbidden("specialist"))
    monkeypatch.setattr(service, "run_bounded_research", forbidden("research"))
    monkeypatch.setattr(service, "run_bounded_research_agent", forbidden("agent"))


def test_grounded_explicit_filter_returns_public_unsupported_without_execution(monkeypatch):
    calls: list[str] = []
    plan = _plan()
    _wire_boundary_plan(monkeypatch, plan, calls)

    response = service.run_orchestrator(
        OrchestratorAskRequest(
            vraag="ignored",
            q="  Toon de resultaten voor MV1 met meshoogte op of onder 3 mm.  ",
        )
    )

    assert calls == []
    assert response["status"] == "unsupported"
    assert response["answer"] == (
        "Filteren op meshoogte wordt voor deze scope nog niet ondersteund."
    )
    assert response["clarification"] == {"required": False, "question": None}
    assert response["results"] == []
    assert response["research"]["status"] == "not_required"
    assert shape_orchestrator_response(response, "compact")["status"] == "unsupported"
    assert "blade_height_filter" not in response
    assert "parser_result" not in response["query_plan"]
    assert "decision" not in response["query_plan"]
    assert "blade_height_filter" not in json.dumps(response, default=str)


def test_invalid_explicit_filter_clarifies_without_generic_execution(monkeypatch):
    calls: list[str] = []
    _wire_boundary_plan(monkeypatch, _plan(), calls)

    response = service.run_orchestrator(
        OrchestratorAskRequest(
            vraag="Toon de resultaten voor MV1 met meshoogte rond 3 mm."
        )
    )

    assert calls == []
    assert response["status"] == "clarification_required"
    assert response["clarification"]["required"] is True
    assert "één exacte" in response["clarification"]["question"]
    assert "approximate_value" not in response["clarification"]["question"]


def test_explicit_filter_without_grounded_scope_clarifies_without_execution(monkeypatch):
    calls: list[str] = []
    _wire_boundary_plan(monkeypatch, _plan(scope=False), calls)

    response = service.run_orchestrator(
        OrchestratorAskRequest(vraag="Toon resultaten met meshoogte onder 3 mm.")
    )

    assert calls == []
    assert response["status"] == "clarification_required"
    assert response["clarification"]["required"] is True
    assert "installatie of welk gebied" in response["clarification"]["question"]


def test_multi_intent_filter_is_deferred_without_executing_other_request(monkeypatch):
    calls: list[str] = []
    _wire_boundary_plan(monkeypatch, _plan(multi_intent=True), calls)

    response = service.run_orchestrator(
        OrchestratorAskRequest(
            vraag="Toon voor MV1 resultaten met meshoogte onder 3 mm en geef onderhoudsadvies."
        )
    )

    assert calls == []
    assert response["status"] == "clarification_required"
    assert "combineert" in response["answer"]


def test_existing_clarification_keeps_priority_over_filter_boundary():
    plan = _plan(scope=False)
    plan.clarification_required = True
    plan.clarification_question = "Bestaande scopeverduidelijking."

    result = applicability.assess_blade_height_filter_applicability(
        "Toon resultaten met meshoogte onder 3 mm.", plan
    )

    assert result.short_circuit is False
    assert result.decision is not None


def test_existing_execution_blocker_keeps_priority_over_filter_boundary():
    plan = _plan()
    plan.execution_blockers = [object()]

    result = applicability.assess_blade_height_filter_applicability(
        "Toon resultaten met meshoogte onder 3 mm.", plan
    )

    assert result.short_circuit is False
    assert result.decision is not None


def test_filter_parser_receives_raw_whitespace_once_and_non_filters_stay_legacy(monkeypatch):
    parser_inputs: list[str] = []
    real_parser = applicability.parse_explicit_blade_height_predicate

    def parser(text: str):
        parser_inputs.append(text)
        return real_parser(text)

    monkeypatch.setattr(applicability, "parse_explicit_blade_height_predicate", parser)
    raw = "  Toon resultaten voor MV1 met meshoogte <= 3 mm.  "
    result = applicability.assess_blade_height_filter_applicability(raw, _plan())
    assert result.short_circuit is True
    assert parser_inputs == [raw]
    assert result.decision.parser_result.predicate.source_span.text == "meshoogte <= 3 mm"

    for question in (
        "Wat betekent meshoogte <= 3 mm?",
        "Wat betekent slijtage bij een schraper?",
        'Toon de tekst "meshoogte onder 3 mm"',
        "Toon de laatste inspectie van band DE3.",
        "Toon banden met bandbreedte <= 3 mm.",
        "Wat is de laatste inspectie voor GSL?",
        "Geef voor GSL de schrapers die nu op of rond de 3 mm grens zitten.",
    ):
        assert applicability.assess_blade_height_filter_applicability(
            question, _plan()
        ).decision is None


def test_measurement_lookup_reaches_the_same_legacy_planning_continuation(monkeypatch):
    """A plain latest-height lookup must not become a predicate clarification."""
    question = "Toon de laatste meshoogte per schraper voor MV1"
    monkeypatch.setattr(
        understanding_module,
        "resolve_scope_context",
        lambda _question: _RESOLVED_SCOPE,
    )
    captured_plans: list[QueryPlan] = []

    def legacy_continuation(plan, *_args, **_kwargs):
        captured_plans.append(plan)
        raise RuntimeError("legacy-continuation")

    monkeypatch.setattr(service, "run_initial_execution_stage", legacy_continuation)

    with pytest.raises(RuntimeError, match="legacy-continuation"):
        service.run_orchestrator(OrchestratorAskRequest(vraag=question))

    actual_plan = captured_plans.pop()
    actual_boundary = applicability.assess_blade_height_filter_applicability(
        question, actual_plan
    )
    assert actual_boundary.decision is None
    assert actual_boundary.short_circuit is False
    assert actual_boundary.status is None

    monkeypatch.setattr(
        service,
        "assess_blade_height_filter_applicability",
        lambda _question, _plan: applicability.BladeHeightFilterBoundaryResult(
            None, False, None, None, None
        ),
    )
    with pytest.raises(RuntimeError, match="legacy-continuation"):
        service.run_orchestrator(OrchestratorAskRequest(vraag=question))

    bypass_plan = captured_plans.pop()
    assert (actual_plan.intent, actual_plan.requested_information) == (
        bypass_plan.intent,
        bypass_plan.requested_information,
    )
    assert actual_plan.clarification_required is bypass_plan.clarification_required


@pytest.mark.parametrize(
    "question",
    (
        "Filter op band DE3 en toon de laatste meshoogte per schraper",
        "Selecteer band A319 en geef de laatste meshoogte",
    ),
)
def test_unrelated_band_selection_and_height_lookup_keep_legacy_planning(
    monkeypatch, question
):
    """Use real understanding/routing; only the external scope resolver is isolated."""
    monkeypatch.setattr(
        understanding_module,
        "resolve_scope_context",
        lambda _question: _RESOLVED_SCOPE,
    )

    legacy_plan = understanding_module.understand_query(question)
    legacy_plan = service.apply_routing_sanity(legacy_plan)
    legacy_plan = service.assess_research_requirement(legacy_plan)
    legacy_plan = service.build_execution_plan(legacy_plan)

    stage_result = initial_planning_stage.run_initial_planning_stage(
        question,
        None,
        {},
        original_question=question,
        observability_call=service._observability_call,
        understand_query=service.understand_query,
        apply_routing_sanity=service.apply_routing_sanity,
        assess_blade_height_filter_applicability=(
            service.assess_blade_height_filter_applicability
        ),
        assess_research_requirement=service.assess_research_requirement,
        build_execution_plan=service.build_execution_plan,
    )

    assert stage_result.blade_height_filter_boundary.decision is None
    assert stage_result.blade_height_filter_boundary.short_circuit is False
    assert stage_result.plan.intent == legacy_plan.intent
    assert stage_result.plan.requested_information == legacy_plan.requested_information
    assert stage_result.plan.clarification_required is legacy_plan.clarification_required


def test_local_selection_binding_keeps_filter_and_predicate_guards():
    for question, expected_short_circuit in (
        ("Filter op meshoogte", True),
        ("Filter op band DE3 en filter op meshoogte", True),
        ("Toon band DE3; meshoogte onder 3 mm", False),
    ):
        result = applicability.assess_blade_height_filter_applicability(question, _plan())

        assert result.short_circuit is expected_short_circuit
        assert (result.decision is not None) is expected_short_circuit


def test_incomplete_and_non_finite_filter_attempts_are_clarified(monkeypatch):
    for question, expected_text in (
        ("Filter op meshoogte", "duidelijke meshoogtevergelijking"),
        (
            "Toon schrapers met meshoogte onder NaN mm",
            "eindig getal",
        ),
    ):
        calls: list[str] = []
        _wire_boundary_plan(monkeypatch, _plan(), calls)

        response = service.run_orchestrator(OrchestratorAskRequest(vraag=question))

        assert calls == []
        assert response["status"] == "clarification_required"
        assert expected_text in response["clarification"]["question"]
        assert response["query_plan"]["clarification_required"] is True
        assert (
            response["query_plan"]["clarification_question"]
            == response["clarification"]["question"]
        )
        assert response["research"]["status"] == "not_required"


def test_text_presentation_with_a_predicate_remains_legacy():
    result = applicability.assess_blade_height_filter_applicability(
        'Toon de tekst "meshoogte onder 3 mm"', _plan()
    )

    assert result.decision is None
    assert result.short_circuit is False


@pytest.mark.parametrize(
    "question",
    (
        "Leg uit wat slijtage betekent bij een schraper.",
        'Citeer de woorden "meshoogte onder 3 mm".',
        'Toon de tekst "meshoogte onder 3 mm" en toon schrapers voor MV1.',
        'Toon schrapers voor MV1 en geef de tekst "meshoogte onder 3 mm".',
    ),
)
def test_explanation_presentation_and_quoted_predicates_do_not_form_filters(question):
    result = applicability.assess_blade_height_filter_applicability(question, _plan())

    assert result.decision is None
    assert result.short_circuit is False


def test_ungrounded_or_contradictory_scope_never_returns_unsupported():
    ungrounded = _plan()
    ungrounded.entities["scope_code"].source = "unverified"
    contradictory = _plan()
    contradictory.entities["installation_code"].value = "MV2"

    for plan in (ungrounded, contradictory):
        result = applicability.assess_blade_height_filter_applicability(
            "Toon schrapers met meshoogte onder 3 mm", plan
        )

        assert result.short_circuit is True
        assert result.status == "clarification_required"
        assert result.decision is not None
        assert result.decision.outcome.value == "clarify"


def test_real_understanding_and_routing_reach_unsupported_without_external_execution(monkeypatch):
    calls: list[str] = []
    _wire_real_understanding_filter_boundary(monkeypatch, calls)

    response = service.run_orchestrator(
        OrchestratorAskRequest(vraag="Toon schrapers voor MV1 met meshoogte onder 3 mm")
    )

    assert calls == []
    assert response["status"] == "unsupported"
    assert response["research"]["status"] == "not_required"
    assert response["query_plan"]["clarification_required"] is False
    assert response["query_plan"]["clarification_question"] is None


def test_real_multi_intent_gap_is_deferred_without_claiming_execution(monkeypatch):
    calls: list[str] = []
    _wire_real_understanding_filter_boundary(monkeypatch, calls)
    question = (
        "Toon schrapers voor MV1 met meshoogte onder 3 mm en leg uit "
        "wat slijtage betekent"
    )

    plan = understanding_module.understand_query(question)
    assert plan.multi_intent is False  # Existing classifier has no explanation task here.
    response = service.run_orchestrator(OrchestratorAskRequest(vraag=question))

    assert calls == []
    assert response["status"] == "clarification_required"
    assert "combineert" in response["answer"]
    assert response["research"]["status"] == "not_required"


@pytest.mark.parametrize(
    "question",
    (
        "Leg uit wat slijtage betekent en toon schrapers voor MV1 met meshoogte onder 3 mm",
        "Geef de tekst van het inspectierapport en toon schrapers voor MV1 met meshoogte onder 3 mm",
    ),
)
def test_real_reversed_mixed_requests_defer_the_filter_without_execution(monkeypatch, question):
    calls: list[str] = []
    _wire_real_understanding_filter_boundary(monkeypatch, calls)

    plan = understanding_module.understand_query(question)
    assert plan.multi_intent is False
    response = service.run_orchestrator(OrchestratorAskRequest(vraag=question))

    assert calls == []
    assert response["status"] == "clarification_required"
    assert "combineert" in response["answer"]
    assert response["research"]["status"] == "not_required"


def test_real_classifier_multi_intent_is_deferred_without_execution(monkeypatch):
    calls: list[str] = []
    _wire_real_understanding_filter_boundary(monkeypatch, calls)
    monkeypatch.setattr(
        understanding_module,
        "resolve_scope_context",
        lambda _question: {"status": "not_found", "scope": None, "candidates": []},
    )
    question = (
        "Geef een korte slijtageanalyse van de schrapers op band A660 met "
        "meshoogte onder 3 mm: laatste meshoogte per schraper, lifecycle-trend, "
        "vervangevents en vervangadvies. Benoem onzekerheden."
    )

    plan = understanding_module.understand_query(question)
    assert plan.multi_intent is True
    assert len(plan.intent_tasks) >= 2
    response = service.run_orchestrator(OrchestratorAskRequest(vraag=question))

    assert calls == []
    assert response["status"] == "clarification_required"
    assert "combineert" in response["answer"]
    assert response["research"]["status"] == "not_required"
