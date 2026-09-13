from types import SimpleNamespace

from app.orchestrator.models import Domain, ExecutionStep, IntentTask, QueryPlan
from app.orchestrator.response_shaping import compact_orchestrator_response
from app.orchestrator.task_grounded_synthesis import (
    build_task_grounded_synthesis_authority_canary_p4_6e2,
)
from app.orchestrator.task_research_evidence import (
    build_task_research_evidence_authority_canary_p4_6e1,
)
from app.orchestrator.task_research_execution import (
    run_task_research_execution_authority_canary_p4_6d2,
)
from app.orchestrator.task_synthesis_coverage import (
    build_task_grounded_synthesis_coverage_authority_canary_p4_6e3,
)


def _task(task_id="task_technical", *, required=True, polarity="requested"):
    return IntentTask(
        task_id=task_id,
        domain=Domain.TECHNICAL,
        intent="technical_lookup",
        required=required,
        polarity=polarity,
        evidence_requirement_set_id="technical.v1",
    )


def _plan(*tasks):
    return QueryPlan(
        original_question="Onderzoek de technische gegevens.",
        normalized_question="onderzoek de technische gegevens.",
        primary_domain=Domain.TECHNICAL,
        domains=[Domain.TECHNICAL],
        intent="technical_lookup",
        intent_tasks=list(tasks),
        execution_steps=[
            ExecutionStep(
                step_id="technical_lookup",
                domain=Domain.TECHNICAL,
                action="technical_lookup",
                params={},
            )
        ],
    )


def _decision_authority():
    return {
        "authoritative": True,
        "authority_scope": "intent_task_research_decision_only",
        "shadow_parity": True,
    }


def _semantics(task_id="task_technical"):
    return {
        "contract_version": "promati.orchestrator.task_research_semantics.cp13.v1",
        "evaluated": True,
        "authoritative": False,
        "authority_scope": "intent_task_research_eligibility_only",
        "legacy_generic_research_allowed": False,
        "allowed_task_ids": [task_id],
        "tasks": [
            {
                "task_id": task_id,
                "research_allowed": True,
                "reason": "coverage_gap",
            }
        ],
    }


def _context_and_guard(task_id="task_technical"):
    context = {
        "task_id": task_id,
        "research_required": True,
        "runtime_precondition": "ready",
    }
    guard = {
        "task_id": task_id,
        "status": "projected",
        "runtime_precondition": "ready",
        "max_follow_up_calls": 1,
        "allowed_research_action": "technical_assistant",
        "pinned_params": {},
        "target_requirement_ids": ["technical_source"],
    }
    return [context], [guard]


def test_cp14_d2_requires_a_valid_cp13_contract_and_nonempty_allowlist():
    task = _task()
    contexts, guards = _context_and_guard()
    cases = [
        (None, "missing_task_research_semantics_cp13"),
        ({"authority_scope": "intent_task_research_eligibility_only"},
         "invalid_task_research_semantics_cp13"),
        ({**_semantics(), "allowed_task_ids": [], "tasks": []},
         "no_eligible_research_execution_units"),
        ({**_semantics(), "allowed_task_ids": ["task_other"]},
         "invalid_task_research_semantics_cp13"),
    ]

    for semantics, expected_reason in cases:
        result = run_task_research_execution_authority_canary_p4_6d2(
            _plan(task), [], _decision_authority(), contexts, guards,
            sender=lambda *_args, **_kwargs: None,
            task_research_semantics_cp13=semantics,
        )
        assert result["authoritative"] is False
        assert result["reason"] == expected_reason


def test_cp14_d2_executes_only_allowlisted_unit_without_mutating_legacy_results(
    monkeypatch,
):
    task = _task()
    contexts, guards = _context_and_guard()
    legacy_results = [{"domain": "technical", "accepted": True, "result": {}}]
    before = list(legacy_results)
    typed_result = SimpleNamespace(legacy_accepted=True)
    observations = []

    def fake_follow_up(*_args, shadow_observer=None, **_kwargs):
        shadow_observer(typed_result)
        return [{"accepted": True, "domain": "technical", "result": {}}]

    monkeypatch.setattr(
        "app.orchestrator.task_research_execution._execute_follow_up_call",
        fake_follow_up,
    )
    result = run_task_research_execution_authority_canary_p4_6d2(
        _plan(task), legacy_results, _decision_authority(), contexts, guards,
        sender=lambda *_args, **_kwargs: None,
        evidence_observer=observations.append,
        task_research_semantics_cp13=_semantics(),
    )

    assert result["authoritative"] is True
    assert result["accepted_follow_up_result_count"] == 1
    assert result["follow_up_specialist_call_count"] == 1
    assert result["max_total_follow_up_calls"] == 2
    assert result["public_answer_authority"] is False
    assert result["evidence_reconciliation_authority"] is False
    assert result["synthesis_authority"] is False
    assert result["cp13_allowed_task_ids"] == ["task_technical"]
    assert result["eligible_execution_unit_count"] == 1
    assert legacy_results == before
    assert observations[0]["execution_results"] == (typed_result,)


def test_cp14_e1_fails_closed_without_active_execution_or_observations():
    plan = _plan(_task())
    inactive = build_task_research_evidence_authority_canary_p4_6e1(
        plan, None, [], (),
    )
    no_accepted = build_task_research_evidence_authority_canary_p4_6e1(
        plan,
        {"authoritative": True, "authority_scope": "intent_task_research_execution_only"},
        [],
        (),
    )
    no_observations = build_task_research_evidence_authority_canary_p4_6e1(
        plan,
        {
            "authoritative": True,
            "authority_scope": "intent_task_research_execution_only",
            "accepted_follow_up_result_count": 1,
        },
        [],
        (),
    )

    assert inactive["reason"] == "missing_task_research_execution_authority"
    assert no_accepted["reason"] == "no_accepted_follow_up_results"
    assert no_observations["reason"] == "missing_internal_execution_observations"
    assert not any(row["authoritative"] for row in (inactive, no_accepted, no_observations))


def test_cp14_minimal_positive_e1_e2_e3_chain(monkeypatch):
    task = _task()
    plan = _plan(task)
    requirement_set = SimpleNamespace(
        requirement_set_id="technical.v1", intent="technical_lookup"
    )
    evidence = SimpleNamespace(evidence_id="ev-follow-up", domain="technical")
    assessment = SimpleNamespace(
        status="sufficient",
        missing_required_requirement_ids=(),
        conflicting_requirement_ids=(),
        evidence_ids_considered=("ev-follow-up",),
    )
    claim = SimpleNamespace(
        claim_id="claim-1",
        text="Technisch gegeven bevestigd.",
        evidence_ids=("ev-follow-up",),
        requirement_ids=("technical_source",),
    )
    grounded = SimpleNamespace(
        status="grounded",
        claims=(claim,),
        evidence_ids_used=("ev-follow-up",),
        omitted_requirement_ids=(),
        conflicting_requirement_ids=(),
    )
    monkeypatch.setattr(
        "app.orchestrator.task_research_evidence._requirement_set_for_task",
        lambda _task: requirement_set,
    )
    monkeypatch.setattr(
        "app.orchestrator.task_research_evidence.normalize_execution_result_evidence",
        lambda *_args, **_kwargs: (evidence,),
    )
    monkeypatch.setattr(
        "app.orchestrator.task_research_evidence.assess_evidence",
        lambda *_args, **_kwargs: assessment,
    )
    monkeypatch.setattr(
        "app.orchestrator.task_grounded_synthesis.synthesize_grounded_evidence",
        lambda _reconciliation: grounded,
    )

    evidence_units = []
    e1 = build_task_research_evidence_authority_canary_p4_6e1(
        plan,
        {
            "authoritative": True,
            "authority_scope": "intent_task_research_execution_only",
            "accepted_follow_up_result_count": 1,
        },
        [{"task_id": task.task_id, "execution_results": (SimpleNamespace(legacy_accepted=True),)}],
        (),
        grounded_synthesis_observer=evidence_units.append,
    )
    e2 = build_task_grounded_synthesis_authority_canary_p4_6e2(e1, evidence_units)
    e3 = build_task_grounded_synthesis_coverage_authority_canary_p4_6e3(
        plan,
        {"authoritative": True, "authority_scope": "intent_task_evidence_assessment_only"},
        e2,
        (),
    )

    assert e1["authoritative"] is True and e1["public_answer_authority"] is False
    assert e2["authoritative"] is True and e2["public_answer_authority"] is False
    assert e3["authoritative"] is True
    assert e3["complete_task_coverage"] is True
    assert e3["units"][0]["claims"][0]["evidence_ids"] == ["ev-follow-up"]
    assert e3["units"][0]["claims"][0]["requirement_ids"] == ["technical_source"]


def test_cp14_e2_rejects_claim_without_grounding_links(monkeypatch):
    assessment = SimpleNamespace(status="sufficient")
    monkeypatch.setattr(
        "app.orchestrator.task_grounded_synthesis.synthesize_grounded_evidence",
        lambda _reconciliation: SimpleNamespace(
            status="grounded",
            claims=(SimpleNamespace(claim_id="bad", text="Ongegrond", evidence_ids=(), requirement_ids=()),),
            evidence_ids_used=(),
            omitted_requirement_ids=(),
            conflicting_requirement_ids=(),
        ),
    )
    e2 = build_task_grounded_synthesis_authority_canary_p4_6e2(
        {
            "authoritative": True,
            "authority_scope": "intent_task_research_evidence_reassessment_only",
            "units": [{"task_id": "task_technical", "family_code": None, "status": "reassessed", "assessment_status": "sufficient"}],
        },
        [{
            "task_id": "task_technical",
            "family_code": None,
            "requirement_set_id": "technical.v1",
            "requirement_set_intent": "technical_lookup",
            "assessment": assessment,
            "evidence_items": (SimpleNamespace(evidence_id="ev"),),
        }],
    )

    assert e2["authoritative"] is False
    assert e2["reason"] == "invalid_grounded_claim_contract"


def test_cp14_e3_fails_closed_with_uncovered_required_requested_tasks():
    required = _task("task_required")
    optional = _task("task_optional", required=False)
    e3 = build_task_grounded_synthesis_coverage_authority_canary_p4_6e3(
        _plan(required, optional),
        {"authoritative": True, "authority_scope": "intent_task_evidence_assessment_only"},
        None,
        (),
    )

    assert e3["authoritative"] is False
    assert e3["reason"] == "incomplete_task_grounded_synthesis_coverage"
    assert e3["uncovered_task_ids"] == ["task_required"]
    assert e3["total_task_count"] == 1


def test_cp14_debug_chain_is_filtered_from_compact_response():
    chain = {
        name: {"units": [{"raw": "x" * 10_000}]}
        for name in (
            "task_research_execution_authority_p4_6d2",
            "task_research_evidence_authority_p4_6e1",
            "task_grounded_synthesis_authority_p4_6e2",
            "task_grounded_synthesis_coverage_authority_p4_6e3",
        )
    }
    compact = compact_orchestrator_response({
        "status": "ok",
        "answer": "Kort antwoord.",
        "query_plan": {"domains": ["technical"], "intent_tasks": []},
        "results": [],
        "evidence_pipeline": chain,
    })

    assert compact["answer"] == "Kort antwoord."
    assert "evidence_pipeline" not in compact
    assert all(name not in compact for name in chain)


if __name__ == "__main__":
    for name, value in sorted(globals().items()):
        if name.startswith("test_cp14_") and callable(value):
            value()
    print("CP14 direct tests passed")
