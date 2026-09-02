from __future__ import annotations

import dataclasses
import inspect
import unittest

import app.orchestrator.evidence_research_gate as gate
from app.orchestrator.evidence_assessor import (
    EvidenceAssessmentResult,
    EvidenceAssessmentStatus,
    RequirementAssessment,
    RequirementAssessmentStatus,
)
from app.orchestrator.evidence_requirements import (
    RequirementNecessity,
)


def _requirement(
    requirement_id: str,
    *,
    necessity: RequirementNecessity,
    status: RequirementAssessmentStatus,
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
            ("evidence-1",)
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
        reasons=(),
    )


def _assessment(
    status: EvidenceAssessmentStatus,
    requirement_results: tuple[
        RequirementAssessment,
        ...,
    ],
) -> EvidenceAssessmentResult:
    return EvidenceAssessmentResult(
        contract_version=(
            "promati.phase_c3."
            "evidence_assessment_contract.v1"
        ),
        requirement_set_id="band_status.v1",
        intent="band_status",
        status=status,
        requirement_results=requirement_results,
        missing_required_requirement_ids=tuple(
            item.requirement_id
            for item in requirement_results
            if (
                item.necessity
                in {
                    RequirementNecessity.REQUIRED,
                    RequirementNecessity.REQUIRED_FOR_DIAGNOSIS,
                }
                and item.status
                is RequirementAssessmentStatus.MISSING
            )
        ),
        conflicting_requirement_ids=tuple(
            item.requirement_id
            for item in requirement_results
            if (
                item.status
                is RequirementAssessmentStatus.CONFLICTING
            )
        ),
        evidence_ids_considered=("evidence-1",),
    )


class ResearchGateContractsV1Tests(
    unittest.TestCase
):
    def test_contract_version_is_exact(self):
        self.assertEqual(
            gate.RESEARCH_GATE_CONTRACT_VERSION,
            (
                "promati.phase_c4."
                "evidence_research_gate_contract.v1"
            ),
        )

    def test_decision_status_values_are_exact(self):
        self.assertEqual(
            tuple(
                item.value
                for item in gate.ResearchGateStatus
            ),
            (
                "not_required",
                "required",
            ),
        )

    def test_decision_fields_are_exact(self):
        self.assertEqual(
            tuple(
                field.name
                for field in dataclasses.fields(
                    gate.ResearchGateDecision
                )
            ),
            (
                "contract_version",
                "requirement_set_id",
                "intent",
                "status",
                "research_required",
                "target_requirement_ids",
                "reasons",
                "assessment_status",
            ),
        )

    def test_decision_is_frozen(self):
        decision = gate.ResearchGateDecision(
            contract_version=(
                gate.RESEARCH_GATE_CONTRACT_VERSION
            ),
            requirement_set_id="band_status.v1",
            intent="band_status",
            status=gate.ResearchGateStatus.REQUIRED,
            research_required=True,
            target_requirement_ids=(
                "LATEST_BLADE_HEIGHT",
            ),
            reasons=("missing_required_evidence",),
            assessment_status=(
                EvidenceAssessmentStatus.INSUFFICIENT
            ),
        )

        with self.assertRaises(
            dataclasses.FrozenInstanceError
        ):
            decision.research_required = False

    def test_collections_are_tuples(self):
        decision = gate.ResearchGateDecision(
            contract_version=(
                gate.RESEARCH_GATE_CONTRACT_VERSION
            ),
            requirement_set_id="band_status.v1",
            intent="band_status",
            status=gate.ResearchGateStatus.REQUIRED,
            research_required=True,
            target_requirement_ids=("A",),
            reasons=("reason",),
            assessment_status=(
                EvidenceAssessmentStatus.PARTIAL
            ),
        )

        self.assertIsInstance(
            decision.target_requirement_ids,
            tuple,
        )
        self.assertIsInstance(
            decision.reasons,
            tuple,
        )

    def test_c4_contains_no_execution_or_synthesis(self):
        source = inspect.getsource(gate).lower()

        forbidden = (
            "requests.",
            "urllib.",
            "httpx.",
            "execute_plan(",
            "run_bounded_research_agent(",
            "openai",
            "synthesize",
            "reconcile",
        )

        for token in forbidden:
            self.assertNotIn(token, source)


class DeterministicResearchGateV1Tests(
    unittest.TestCase
):
    def test_sufficient_assessment_skips_research(self):
        assessment = _assessment(
            EvidenceAssessmentStatus.SUFFICIENT,
            (
                _requirement(
                    "CURRENT_PRICE",
                    necessity=(
                        RequirementNecessity.REQUIRED
                    ),
                    status=(
                        RequirementAssessmentStatus.SATISFIED
                    ),
                ),
            ),
        )

        decision = gate.decide_research_requirement(
            assessment
        )

        self.assertEqual(
            decision.status,
            gate.ResearchGateStatus.NOT_REQUIRED,
        )
        self.assertFalse(decision.research_required)
        self.assertEqual(
            decision.target_requirement_ids,
            (),
        )

    def test_missing_required_requests_research(self):
        assessment = _assessment(
            EvidenceAssessmentStatus.INSUFFICIENT,
            (
                _requirement(
                    "LATEST_BLADE_HEIGHT",
                    necessity=(
                        RequirementNecessity.REQUIRED
                    ),
                    status=(
                        RequirementAssessmentStatus.MISSING
                    ),
                ),
            ),
        )

        decision = gate.decide_research_requirement(
            assessment
        )

        self.assertEqual(
            decision.status,
            gate.ResearchGateStatus.REQUIRED,
        )
        self.assertTrue(decision.research_required)
        self.assertEqual(
            decision.target_requirement_ids,
            ("LATEST_BLADE_HEIGHT",),
        )

    def test_partial_required_requests_research(self):
        assessment = _assessment(
            EvidenceAssessmentStatus.PARTIAL,
            (
                _requirement(
                    "CURRENT_STOCK",
                    necessity=(
                        RequirementNecessity.REQUIRED
                    ),
                    status=(
                        RequirementAssessmentStatus.PARTIAL
                    ),
                ),
            ),
        )

        decision = gate.decide_research_requirement(
            assessment
        )

        self.assertTrue(decision.research_required)
        self.assertEqual(
            decision.target_requirement_ids,
            ("CURRENT_STOCK",),
        )

    def test_conflicting_evidence_requests_research(self):
        assessment = _assessment(
            EvidenceAssessmentStatus.CONFLICTING,
            (
                _requirement(
                    "CURRENT_PERSON_ROLE",
                    necessity=(
                        RequirementNecessity.REQUIRED
                    ),
                    status=(
                        RequirementAssessmentStatus.CONFLICTING
                    ),
                ),
            ),
        )

        decision = gate.decide_research_requirement(
            assessment
        )

        self.assertTrue(decision.research_required)
        self.assertEqual(
            decision.target_requirement_ids,
            ("CURRENT_PERSON_ROLE",),
        )

    def test_missing_desired_is_a_research_target(self):
        assessment = _assessment(
            EvidenceAssessmentStatus.PARTIAL,
            (
                _requirement(
                    "INSPECTION_COMMENTS",
                    necessity=(
                        RequirementNecessity.DESIRED
                    ),
                    status=(
                        RequirementAssessmentStatus.MISSING
                    ),
                ),
            ),
        )

        decision = gate.decide_research_requirement(
            assessment
        )

        self.assertTrue(decision.research_required)
        self.assertEqual(
            decision.target_requirement_ids,
            ("INSPECTION_COMMENTS",),
        )

    def test_target_order_is_deterministic(self):
        first = _assessment(
            EvidenceAssessmentStatus.INSUFFICIENT,
            (
                _requirement(
                    "B",
                    necessity=RequirementNecessity.REQUIRED,
                    status=RequirementAssessmentStatus.MISSING,
                ),
                _requirement(
                    "A",
                    necessity=RequirementNecessity.REQUIRED,
                    status=RequirementAssessmentStatus.PARTIAL,
                ),
            ),
        )

        second = _assessment(
            EvidenceAssessmentStatus.INSUFFICIENT,
            tuple(reversed(first.requirement_results)),
        )

        self.assertEqual(
            gate.decide_research_requirement(first),
            gate.decide_research_requirement(second),
        )

    def test_gate_does_not_mutate_assessment(self):
        assessment = _assessment(
            EvidenceAssessmentStatus.INSUFFICIENT,
            (
                _requirement(
                    "MEASUREMENT_HISTORY",
                    necessity=(
                        RequirementNecessity.REQUIRED
                    ),
                    status=(
                        RequirementAssessmentStatus.MISSING
                    ),
                ),
            ),
        )

        before = repr(assessment)

        gate.decide_research_requirement(assessment)

        self.assertEqual(repr(assessment), before)


if __name__ == "__main__":
    unittest.main()