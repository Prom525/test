from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT),
    )


from app.orchestrator.complexity import (  # noqa: E402
    RESEARCH_REQUIRED_THRESHOLD,
    assess_research_requirement,
)
from app.orchestrator.evidence_assessor import (  # noqa: E402
    EVIDENCE_ASSESSMENT_CONTRACT_VERSION,
    EvidenceAssessmentResult,
    EvidenceAssessmentStatus,
    RequirementAssessment,
    RequirementAssessmentStatus,
)
from app.orchestrator.evidence_research_gate import (  # noqa: E402
    ResearchGateStatus,
    decide_research_requirement,
)
from app.orchestrator.evidence_requirements import (  # noqa: E402
    RequirementNecessity,
)
from app.orchestrator.models import (  # noqa: E402
    Domain,
    QueryPlan,
)
from app.orchestrator.research import (  # noqa: E402
    run_bounded_research,
)
from app.orchestrator.research_agent import (  # noqa: E402
    ResearchBudget,
    plan_research_next_step,
)


def make_plan(
    question: str,
    *,
    research_required: bool = False,
    clarification_required: bool = False,
    requested_information: list[str] | None = None,
) -> QueryPlan:
    return QueryPlan(
        original_question=question,
        normalized_question=question.lower(),
        primary_domain=Domain.INSPECTION,
        domains=[Domain.INSPECTION],
        intent="inspection_trend",
        requested_information=list(
            requested_information or []
        ),
        research_required=research_required,
        clarification_required=clarification_required,
    )


def make_requirement_assessment(
    *,
    requirement_id: str,
    status: RequirementAssessmentStatus,
    necessity: RequirementNecessity = (
        RequirementNecessity.REQUIRED
    ),
) -> RequirementAssessment:
    satisfied = (
        status
        is RequirementAssessmentStatus.SATISFIED
    )

    return RequirementAssessment(
        requirement_id=requirement_id,
        necessity=necessity,
        status=status,
        matched_evidence_ids=(
            ("ev_1",)
            if satisfied
            else ()
        ),
        present=satisfied,
        relevant=satisfied,
        grounded=satisfied,
        fresh=satisfied,
        conflicting=(
            status
            is RequirementAssessmentStatus.CONFLICTING
        ),
        reasons=(
            ()
            if satisfied
            else ("test_unresolved",)
        ),
    )


def make_assessment(
    *,
    status: EvidenceAssessmentStatus,
    requirements: tuple[
        RequirementAssessment,
        ...,
    ],
) -> EvidenceAssessmentResult:
    missing = tuple(
        item.requirement_id
        for item in requirements
        if (
            item.necessity
            in {
                RequirementNecessity.REQUIRED,
                (
                    RequirementNecessity
                    .REQUIRED_FOR_DIAGNOSIS
                ),
            }
            and item.status
            is not RequirementAssessmentStatus.SATISFIED
        )
    )

    conflicting = tuple(
        item.requirement_id
        for item in requirements
        if item.conflicting
    )

    return EvidenceAssessmentResult(
        contract_version=(
            EVIDENCE_ASSESSMENT_CONTRACT_VERSION
        ),
        requirement_set_id=(
            "replacement_advice.v1"
        ),
        intent="replacement_advice",
        status=status,
        requirement_results=requirements,
        missing_required_requirement_ids=missing,
        conflicting_requirement_ids=conflicting,
        evidence_ids_considered=("ev_1",),
    )


class ResearchGateRegressionTests(
    unittest.TestCase
):

    # -----------------------------------------------------
    # PLAN-LEVEL COMPLEXITY GATE
    # -----------------------------------------------------

    def test_simple_inspection_does_not_require_plan_research(
        self,
    ):
        plan = make_plan(
            "vervangadvies voor band a660"
        )

        result = assess_research_requirement(
            plan
        )

        self.assertFalse(
            result.research_required
        )

        self.assertLess(
            result.complexity_score,
            RESEARCH_REQUIRED_THRESHOLD,
        )


    def test_explicit_complex_analysis_requires_plan_research(
        self,
    ):
        plan = make_plan(
            (
                "onderzoek waarom de "
                "slijtagehistorie van band a660 "
                "afwijkt en adviseer op basis "
                "van ervaring"
            )
        )

        result = assess_research_requirement(
            plan
        )

        self.assertTrue(
            result.research_required
        )

        self.assertGreaterEqual(
            result.complexity_score,
            RESEARCH_REQUIRED_THRESHOLD,
        )

        self.assertIn(
            "explicit_research_request",
            result.complexity_reasons,
        )

        self.assertIn(
            "causal_analysis",
            result.complexity_reasons,
        )


    def test_clarification_blocks_even_high_score_research(
        self,
    ):
        plan = make_plan(
            (
                "onderzoek waarom de "
                "slijtagehistorie afwijkt "
                "en adviseer een oplossing"
            ),
            clarification_required=True,
        )

        result = assess_research_requirement(
            plan
        )

        self.assertGreaterEqual(
            result.complexity_score,
            RESEARCH_REQUIRED_THRESHOLD,
        )

        self.assertFalse(
            result.research_required
        )

        self.assertIn(
            (
                "clarification_required_"
                "blocks_research"
            ),
            result.complexity_reasons,
        )


    def test_inspection_facets_do_not_raise_complexity_score(
        self,
    ):
        plan = make_plan(
            "toon trend van band a660",
            requested_information=[
                "latest_measurements",
                "lifecycle_trend",
                "replacement_events",
                "replacement_advice",
                "uncertainties",
            ],
        )

        result = assess_research_requirement(
            plan
        )

        self.assertTrue(
            result.multi_intent
        )

        self.assertNotIn(
            "multiple_information_requests",
            result.complexity_reasons,
        )

        self.assertFalse(
            result.research_required
        )


    # -----------------------------------------------------
    # PLAN RESEARCH PLANNER GATE
    # -----------------------------------------------------

    def test_research_agent_not_called_when_not_required(
        self,
    ):
        calls = {"count": 0}

        def forbidden_planner(request):
            calls["count"] += 1
            raise AssertionError(
                "planner must not be called"
            )

        plan = make_plan(
            "toon trend van band a660",
            research_required=False,
        )

        decision = plan_research_next_step(
            plan,
            [],
            ResearchBudget(
                round_number=1,
                initial_specialist_calls=1,
            ),
            planner=forbidden_planner,
        )

        self.assertEqual(
            calls["count"],
            0,
        )

        self.assertEqual(
            decision.status,
            "not_required",
        )

        self.assertEqual(
            decision.planner_ai_calls_used,
            0,
        )


    def test_research_agent_clarification_blocks_ai(
        self,
    ):
        calls = {"count": 0}

        def forbidden_planner(request):
            calls["count"] += 1
            raise AssertionError(
                "planner must not be called"
            )

        plan = make_plan(
            "onderzoek slijtage",
            research_required=True,
            clarification_required=True,
        )

        decision = plan_research_next_step(
            plan,
            [],
            ResearchBudget(
                round_number=1,
                initial_specialist_calls=0,
            ),
            planner=forbidden_planner,
        )

        self.assertEqual(
            calls["count"],
            0,
        )

        self.assertEqual(
            decision.status,
            "blocked",
        )

        self.assertEqual(
            decision.blocked_reason,
            "clarification_required",
        )


    def test_research_agent_requires_accepted_evidence(
        self,
    ):
        calls = {"count": 0}

        def forbidden_planner(request):
            calls["count"] += 1
            raise AssertionError(
                "planner must not be called"
            )

        plan = make_plan(
            "onderzoek slijtage",
            research_required=True,
        )

        decision = plan_research_next_step(
            plan,
            [
                {
                    "step_id": "step_1",
                    "domain": "inspection",
                    "action": "analysis_assistant",
                    "accepted": False,
                    "result": {
                        "intent": "lifecycle",
                    },
                }
            ],
            ResearchBudget(
                round_number=1,
                initial_specialist_calls=1,
            ),
            planner=forbidden_planner,
        )

        self.assertEqual(
            calls["count"],
            0,
        )

        self.assertEqual(
            decision.status,
            "blocked",
        )

        self.assertEqual(
            decision.blocked_reason,
            "insufficient_evidence",
        )


    def test_research_agent_positive_gate_calls_planner_once(
        self,
    ):
        calls = {"count": 0}

        def fake_planner(request):
            calls["count"] += 1

            return SimpleNamespace(
                text=json.dumps(
                    {
                        "decision": "synthesize",
                        "reason": (
                            "Evidence is voldoende."
                        ),
                        "gaps": [],
                        "calls": [],
                    }
                )
            )

        plan = make_plan(
            "onderzoek slijtage",
            research_required=True,
        )

        decision = plan_research_next_step(
            plan,
            [
                {
                    "step_id": "step_1",
                    "domain": "inspection",
                    "action": "analysis_assistant",
                    "accepted": True,
                    "result": {
                        "intent": "lifecycle",
                        "kort_resultaat": "ok",
                    },
                }
            ],
            ResearchBudget(
                round_number=1,
                initial_specialist_calls=1,
            ),
            planner=fake_planner,
        )

        self.assertEqual(
            calls["count"],
            1,
        )

        self.assertEqual(
            decision.status,
            "ok",
        )

        self.assertEqual(
            decision.decision,
            "synthesize",
        )

        self.assertEqual(
            decision.planner_ai_calls_used,
            1,
        )


    # -----------------------------------------------------
    # LEGACY BOUNDED SYNTHESIS GATE
    # -----------------------------------------------------

    def test_bounded_research_returns_without_ai_when_not_required(
        self,
    ):
        plan = make_plan(
            "toon trend",
            research_required=False,
        )

        result = run_bounded_research(
            plan,
            [],
        )

        self.assertEqual(
            result["status"],
            "not_required",
        )

        self.assertEqual(
            result["ai_calls_used"],
            0,
        )


    def test_bounded_research_clarification_blocks_ai(
        self,
    ):
        plan = make_plan(
            "onderzoek trend",
            research_required=True,
            clarification_required=True,
        )

        result = run_bounded_research(
            plan,
            [],
        )

        self.assertEqual(
            result["status"],
            "blocked_by_clarification",
        )

        self.assertEqual(
            result["ai_calls_used"],
            0,
        )


    # -----------------------------------------------------
    # EVIDENCE-DRIVEN PHASE-C GATE
    # -----------------------------------------------------

    def test_sufficient_evidence_does_not_trigger_phase_c_research(
        self,
    ):
        assessment = make_assessment(
            status=(
                EvidenceAssessmentStatus.SUFFICIENT
            ),
            requirements=(
                make_requirement_assessment(
                    requirement_id=(
                        "LATEST_BLADE_HEIGHT"
                    ),
                    status=(
                        RequirementAssessmentStatus
                        .SATISFIED
                    ),
                ),
            ),
        )

        decision = decide_research_requirement(
            assessment
        )

        self.assertEqual(
            decision.status,
            ResearchGateStatus.NOT_REQUIRED,
        )

        self.assertFalse(
            decision.research_required
        )

        self.assertEqual(
            decision.target_requirement_ids,
            (),
        )


    def test_missing_required_evidence_triggers_phase_c_research(
        self,
    ):
        assessment = make_assessment(
            status=(
                EvidenceAssessmentStatus.INSUFFICIENT
            ),
            requirements=(
                make_requirement_assessment(
                    requirement_id=(
                        "LATEST_BLADE_HEIGHT"
                    ),
                    status=(
                        RequirementAssessmentStatus
                        .MISSING
                    ),
                ),
            ),
        )

        decision = decide_research_requirement(
            assessment
        )

        self.assertEqual(
            decision.status,
            ResearchGateStatus.REQUIRED,
        )

        self.assertTrue(
            decision.research_required
        )

        self.assertEqual(
            decision.target_requirement_ids,
            ("LATEST_BLADE_HEIGHT",),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
