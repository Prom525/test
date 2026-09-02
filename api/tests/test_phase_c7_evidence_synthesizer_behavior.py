from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import unittest

from app.orchestrator.evidence_assessor import (
    EvidenceAssessmentResult,
    EvidenceAssessmentStatus,
    RequirementAssessment,
    RequirementAssessmentStatus,
)
from app.orchestrator.evidence_contracts import (
    EVIDENCE_CONTRACT_VERSION,
    EvidenceDirectness,
    EvidenceFreshnessStatus,
    EvidenceGroundingStatus,
    EvidenceItem,
    EvidenceQualityStatus,
    EvidenceSourceType,
    EvidenceType,
)
from app.orchestrator.evidence_reconciler import (
    EVIDENCE_RECONCILIATION_CONTRACT_VERSION,
    EvidenceReconciliationResult,
    EvidenceReconciliationStatus,
)
from app.orchestrator.evidence_requirements import (
    RequirementNecessity,
)
from app.orchestrator.evidence_research_executor import (
    ResearchExecutionStatus,
)
import app.orchestrator.evidence_synthesizer as synthesizer


class DeterministicGroundedSynthesisV1Tests(
    unittest.TestCase
):
    def setUp(self):
        self.now = datetime(
            2026,
            8,
            28,
            12,
            0,
            tzinfo=timezone.utc,
        )
        self.research_status = next(
            iter(ResearchExecutionStatus)
        )

    def _evidence(
        self,
        evidence_id,
        value,
        *,
        subject="Blade height",
        unit="mm",
        grounding=EvidenceGroundingStatus.GROUNDED,
        quality=EvidenceQualityStatus.VALID,
        freshness=EvidenceFreshnessStatus.CURRENT,
    ):
        return EvidenceItem(
            contract_version=EVIDENCE_CONTRACT_VERSION,
            evidence_id=evidence_id,
            execution_step_id="step-1",
            specialist_id="measurement-specialist",
            domain="measurements",
            subject=subject,
            entity_type="band",
            entity_id="band-1",
            evidence_type=EvidenceType.MEASUREMENT,
            source_type=EvidenceSourceType.LIVE_CANONICAL,
            source_name="measurement-service",
            source_reference="measurement-1",
            source_priority=1,
            observed_at=self.now,
            retrieved_at=self.now,
            effective_at=self.now,
            value=value,
            unit=unit,
            claim_scope=("band-1",),
            freshness_status=freshness,
            grounding_status=grounding,
            quality_status=quality,
            direct_or_derived=EvidenceDirectness.DIRECT,
            derivation_reference=None,
            provenance={"source": "test"},
        )

    def _requirement_result(
        self,
        requirement_id,
        evidence_ids,
        *,
        status=RequirementAssessmentStatus.SATISFIED,
        necessity=RequirementNecessity.REQUIRED,
        grounded=True,
        fresh=True,
        conflicting=False,
    ):
        return RequirementAssessment(
            requirement_id=requirement_id,
            necessity=necessity,
            status=status,
            matched_evidence_ids=tuple(evidence_ids),
            present=bool(evidence_ids),
            relevant=bool(evidence_ids),
            grounded=grounded,
            fresh=fresh,
            conflicting=conflicting,
            reasons=(),
        )

    def _assessment(
        self,
        requirement_results,
        *,
        status=EvidenceAssessmentStatus.SUFFICIENT,
        missing=(),
        conflicting=(),
    ):
        evidence_ids = sorted({
            evidence_id
            for result in requirement_results
            for evidence_id in result.matched_evidence_ids
        })

        return EvidenceAssessmentResult(
            contract_version=(
                "promati.phase_c3."
                "evidence_assessment.v1"
            ),
            requirement_set_id="band-status.v1",
            intent="band_status",
            status=status,
            requirement_results=tuple(
                requirement_results
            ),
            missing_required_requirement_ids=tuple(
                missing
            ),
            conflicting_requirement_ids=tuple(
                conflicting
            ),
            evidence_ids_considered=tuple(
                evidence_ids
            ),
        )

    def _reconciliation(
        self,
        evidence_items,
        assessment,
        *,
        status=EvidenceReconciliationStatus.UNCHANGED,
        reasons=(),
    ):
        return EvidenceReconciliationResult(
            contract_version=(
                EVIDENCE_RECONCILIATION_CONTRACT_VERSION
            ),
            requirement_set_id="band-status.v1",
            intent="band_status",
            status=status,
            research_status=self.research_status,
            initial_evidence_items=tuple(
                evidence_items
            ),
            reconciled_evidence_items=tuple(
                evidence_items
            ),
            added_evidence_ids=(),
            discarded_result_count=0,
            initial_assessment=assessment,
            reconciled_assessment=assessment,
            reasons=tuple(reasons),
        )

    def test_sufficient_grounded_evidence_is_complete(self):
        evidence = self._evidence(
            "evidence-1",
            10,
        )
        requirement = self._requirement_result(
            "LATEST_BLADE_HEIGHT",
            ("evidence-1",),
        )
        reconciliation = self._reconciliation(
            (evidence,),
            self._assessment((requirement,)),
        )

        result = (
            synthesizer
            .synthesize_grounded_evidence(
                reconciliation
            )
        )

        self.assertEqual(
            result.status,
            synthesizer.GroundedSynthesisStatus.COMPLETE,
        )
        self.assertEqual(len(result.claims), 1)
        self.assertEqual(
            result.claims[0].claim_id,
            "claim:evidence-1",
        )
        self.assertEqual(
            result.claims[0].text,
            "Blade height: 10 mm",
        )
        self.assertEqual(
            result.claims[0].evidence_ids,
            ("evidence-1",),
        )
        self.assertEqual(
            result.claims[0].requirement_ids,
            ("LATEST_BLADE_HEIGHT",),
        )
        self.assertEqual(
            result.evidence_ids_used,
            ("evidence-1",),
        )
        self.assertEqual(
            result.omitted_requirement_ids,
            (),
        )

    def test_blocked_reconciliation_produces_no_claims(self):
        evidence = self._evidence(
            "evidence-1",
            10,
        )
        requirement = self._requirement_result(
            "LATEST_BLADE_HEIGHT",
            ("evidence-1",),
        )
        reconciliation = self._reconciliation(
            (evidence,),
            self._assessment((requirement,)),
            status=EvidenceReconciliationStatus.BLOCKED,
            reasons=("research_identity_mismatch",),
        )

        result = (
            synthesizer
            .synthesize_grounded_evidence(
                reconciliation
            )
        )

        self.assertEqual(
            result.status,
            synthesizer.GroundedSynthesisStatus.BLOCKED,
        )
        self.assertEqual(result.claims, ())
        self.assertEqual(result.evidence_ids_used, ())
        self.assertIn(
            "reconciliation_blocked",
            result.reasons,
        )

    def test_ungrounded_evidence_is_omitted(self):
        evidence = self._evidence(
            "evidence-1",
            10,
            grounding=(
                EvidenceGroundingStatus.UNGROUNDED
            ),
        )
        requirement = self._requirement_result(
            "LATEST_BLADE_HEIGHT",
            ("evidence-1",),
            status=RequirementAssessmentStatus.PARTIAL,
            grounded=False,
        )
        assessment = self._assessment(
            (requirement,),
            status=EvidenceAssessmentStatus.PARTIAL,
        )
        reconciliation = self._reconciliation(
            (evidence,),
            assessment,
        )

        result = (
            synthesizer
            .synthesize_grounded_evidence(
                reconciliation
            )
        )

        self.assertEqual(
            result.status,
            synthesizer.GroundedSynthesisStatus.PARTIAL,
        )
        self.assertEqual(result.claims, ())
        self.assertEqual(
            result.omitted_requirement_ids,
            ("LATEST_BLADE_HEIGHT",),
        )
        self.assertEqual(result.evidence_ids_used, ())

    def test_conflicting_requirement_is_not_asserted(self):
        first = self._evidence(
            "evidence-1",
            10,
        )
        second = self._evidence(
            "evidence-2",
            12,
        )
        requirement = self._requirement_result(
            "LATEST_BLADE_HEIGHT",
            ("evidence-1", "evidence-2"),
            status=(
                RequirementAssessmentStatus.CONFLICTING
            ),
            conflicting=True,
        )
        assessment = self._assessment(
            (requirement,),
            status=EvidenceAssessmentStatus.CONFLICTING,
            conflicting=("LATEST_BLADE_HEIGHT",),
        )
        reconciliation = self._reconciliation(
            (first, second),
            assessment,
            status=EvidenceReconciliationStatus.UNRESOLVED,
        )

        result = (
            synthesizer
            .synthesize_grounded_evidence(
                reconciliation
            )
        )

        self.assertEqual(
            result.status,
            synthesizer.GroundedSynthesisStatus.PARTIAL,
        )
        self.assertEqual(result.claims, ())
        self.assertEqual(
            result.conflicting_requirement_ids,
            ("LATEST_BLADE_HEIGHT",),
        )
        self.assertEqual(
            result.omitted_requirement_ids,
            ("LATEST_BLADE_HEIGHT",),
        )

    def test_input_order_does_not_change_result(self):
        first = self._evidence(
            "evidence-b",
            12,
        )
        second = self._evidence(
            "evidence-a",
            10,
        )
        first_requirement = self._requirement_result(
            "HEIGHT_B",
            ("evidence-b",),
        )
        second_requirement = self._requirement_result(
            "HEIGHT_A",
            ("evidence-a",),
        )

        first_reconciliation = self._reconciliation(
            (first, second),
            self._assessment(
                (
                    first_requirement,
                    second_requirement,
                )
            ),
        )
        second_reconciliation = self._reconciliation(
            (second, first),
            self._assessment(
                (
                    second_requirement,
                    first_requirement,
                )
            ),
        )

        first_result = (
            synthesizer
            .synthesize_grounded_evidence(
                first_reconciliation
            )
        )
        second_result = (
            synthesizer
            .synthesize_grounded_evidence(
                second_reconciliation
            )
        )

        self.assertEqual(
            first_result,
            second_result,
        )
        self.assertEqual(
            first_result.evidence_ids_used,
            ("evidence-a", "evidence-b"),
        )

    def test_synthesis_does_not_mutate_input(self):
        evidence = self._evidence(
            "evidence-1",
            10,
        )
        requirement = self._requirement_result(
            "LATEST_BLADE_HEIGHT",
            ("evidence-1",),
        )
        reconciliation = self._reconciliation(
            (evidence,),
            self._assessment((requirement,)),
        )
        before = deepcopy(reconciliation)

        synthesizer.synthesize_grounded_evidence(
            reconciliation
        )

        self.assertEqual(reconciliation, before)


if __name__ == "__main__":
    unittest.main()