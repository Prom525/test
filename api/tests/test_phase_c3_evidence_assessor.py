from __future__ import annotations

import dataclasses
import pathlib
import unittest

import app.orchestrator.evidence_assessor as assessor
from app.orchestrator.evidence_requirements import (
    RequirementNecessity,
)


class EvidenceAssessmentContractsV1Tests(
    unittest.TestCase
):
    def _requirement_result(self):
        return assessor.RequirementAssessment(
            requirement_id="LATEST_BLADE_HEIGHT",
            necessity=RequirementNecessity.REQUIRED,
            status=(
                assessor.
                RequirementAssessmentStatus.SATISFIED
            ),
            matched_evidence_ids=("measurement-1",),
            present=True,
            relevant=True,
            grounded=True,
            fresh=True,
            conflicting=False,
            reasons=(),
        )

    def test_assessment_contract_version_is_exact(self):
        self.assertEqual(
            assessor.EVIDENCE_ASSESSMENT_CONTRACT_VERSION,
            (
                "promati.phase_c3."
                "evidence_assessment_contract.v1"
            ),
        )

    def test_requirement_status_values_are_exact(self):
        self.assertEqual(
            {
                item.value
                for item in (
                    assessor.
                    RequirementAssessmentStatus
                )
            },
            {
                "satisfied",
                "partial",
                "missing",
                "conflicting",
            },
        )

    def test_overall_status_values_are_exact(self):
        self.assertEqual(
            {
                item.value
                for item in (
                    assessor.
                    EvidenceAssessmentStatus
                )
            },
            {
                "sufficient",
                "partial",
                "insufficient",
                "conflicting",
            },
        )

    def test_requirement_assessment_fields_are_exact(self):
        self.assertEqual(
            tuple(
                field.name
                for field in dataclasses.fields(
                    assessor.RequirementAssessment
                )
            ),
            (
                "requirement_id",
                "necessity",
                "status",
                "matched_evidence_ids",
                "present",
                "relevant",
                "grounded",
                "fresh",
                "conflicting",
                "reasons",
            ),
        )

    def test_assessment_result_fields_are_exact(self):
        self.assertEqual(
            tuple(
                field.name
                for field in dataclasses.fields(
                    assessor.EvidenceAssessmentResult
                )
            ),
            (
                "contract_version",
                "requirement_set_id",
                "intent",
                "status",
                "requirement_results",
                "missing_required_requirement_ids",
                "conflicting_requirement_ids",
                "evidence_ids_considered",
            ),
        )

    def test_contract_objects_are_constructible(self):
        requirement_result = (
            self._requirement_result()
        )

        result = assessor.EvidenceAssessmentResult(
            contract_version=(
                assessor.
                EVIDENCE_ASSESSMENT_CONTRACT_VERSION
            ),
            requirement_set_id="band_status.v1",
            intent="band_status",
            status=(
                assessor.
                EvidenceAssessmentStatus.SUFFICIENT
            ),
            requirement_results=(
                requirement_result,
            ),
            missing_required_requirement_ids=(),
            conflicting_requirement_ids=(),
            evidence_ids_considered=(
                "measurement-1",
            ),
        )

        self.assertEqual(
            result.requirement_results,
            (requirement_result,),
        )
        self.assertEqual(
            result.status,
            assessor.
            EvidenceAssessmentStatus.SUFFICIENT,
        )

    def test_contract_objects_are_frozen(self):
        requirement_result = (
            self._requirement_result()
        )

        with self.assertRaises(
            dataclasses.FrozenInstanceError
        ):
            requirement_result.present = False

        result = assessor.EvidenceAssessmentResult(
            contract_version=(
                assessor.
                EVIDENCE_ASSESSMENT_CONTRACT_VERSION
            ),
            requirement_set_id="band_status.v1",
            intent="band_status",
            status=(
                assessor.
                EvidenceAssessmentStatus.SUFFICIENT
            ),
            requirement_results=(
                requirement_result,
            ),
            missing_required_requirement_ids=(),
            conflicting_requirement_ids=(),
            evidence_ids_considered=(
                "measurement-1",
            ),
        )

        with self.assertRaises(
            dataclasses.FrozenInstanceError
        ):
            result.intent = "changed"

    def test_collections_are_immutable_tuples(self):
        requirement_result = (
            self._requirement_result()
        )

        self.assertIsInstance(
            requirement_result.
            matched_evidence_ids,
            tuple,
        )
        self.assertIsInstance(
            requirement_result.reasons,
            tuple,
        )

        result = assessor.EvidenceAssessmentResult(
            contract_version=(
                assessor.
                EVIDENCE_ASSESSMENT_CONTRACT_VERSION
            ),
            requirement_set_id="band_status.v1",
            intent="band_status",
            status=(
                assessor.
                EvidenceAssessmentStatus.SUFFICIENT
            ),
            requirement_results=(
                requirement_result,
            ),
            missing_required_requirement_ids=(),
            conflicting_requirement_ids=(),
            evidence_ids_considered=(
                "measurement-1",
            ),
        )

        self.assertIsInstance(
            result.requirement_results,
            tuple,
        )
        self.assertIsInstance(
            result.
            missing_required_requirement_ids,
            tuple,
        )
        self.assertIsInstance(
            result.conflicting_requirement_ids,
            tuple,
        )
        self.assertIsInstance(
            result.evidence_ids_considered,
            tuple,
        )

    def test_c3_contract_contains_no_later_phase_actions(
        self,
    ):
        source = pathlib.Path(
            assessor.__file__
        ).read_text(
            encoding="utf-8",
        ).lower()

        for forbidden in (
            "research_required",
            "run_research",
            "reconcile_evidence",
            "synthesize_answer",
            "execute_plan",
            "llm",
        ):
            self.assertNotIn(
                forbidden,
                source,
            )


from copy import deepcopy
from datetime import datetime, timezone

from app.orchestrator.evidence_contracts import (
    EvidenceDirectness,
    EvidenceFreshnessStatus,
    EvidenceGroundingStatus,
    EvidenceItem,
    EvidenceQualityStatus,
    EvidenceSourceType,
    EvidenceType,
)
from app.orchestrator.evidence_requirements import (
    EVIDENCE_REQUIREMENT_CONTRACT_VERSION,
    EvidenceRequirement,
    EvidenceRequirementSet,
)


class DeterministicEvidenceAssessmentV1Tests(
    unittest.TestCase
):
    def _requirement(
        self,
        *,
        requirement_id="LATEST_BLADE_HEIGHT",
        evidence_types=(EvidenceType.MEASUREMENT,),
        necessity=RequirementNecessity.REQUIRED,
        allowed_source_types=(
            EvidenceSourceType.LIVE_CANONICAL,
        ),
        entity_type="conveyor_belt",
        entity_id_required=True,
        maximum_age_seconds=None,
        minimum_items=1,
    ):
        return EvidenceRequirement(
            contract_version=(
                EVIDENCE_REQUIREMENT_CONTRACT_VERSION
            ),
            requirement_id=requirement_id,
            evidence_types=evidence_types,
            necessity=necessity,
            description=requirement_id,
            allowed_source_types=allowed_source_types,
            minimum_items=minimum_items,
            entity_type=entity_type,
            entity_id_required=entity_id_required,
            maximum_age_seconds=maximum_age_seconds,
            forbidden_substitutions=(),
        )

    def _set(self, *requirements):
        return EvidenceRequirementSet(
            contract_version=(
                EVIDENCE_REQUIREMENT_CONTRACT_VERSION
            ),
            requirement_set_id="band_status.v1",
            intent="band_status",
            requirements=tuple(requirements),
            notes=(),
        )

    def _item(
        self,
        *,
        evidence_id="measurement-1",
        value=12.5,
        evidence_type=EvidenceType.MEASUREMENT,
        source_type=(
            EvidenceSourceType.LIVE_CANONICAL
        ),
        entity_type="conveyor_belt",
        entity_id="A319",
        freshness_status=(
            EvidenceFreshnessStatus.CURRENT
        ),
        grounding_status=(
            EvidenceGroundingStatus.GROUNDED
        ),
        quality_status=(
            EvidenceQualityStatus.VALID
        ),
    ):
        timestamp = datetime(
            2026,
            8,
            28,
            8,
            0,
            tzinfo=timezone.utc,
        )

        return EvidenceItem(
            contract_version=(
                "promati.phase_c1."
                "evidence_contract.v1"
            ),
            evidence_id=evidence_id,
            execution_step_id="step-1",
            specialist_id="analysis_assistant",
            domain="inspection",
            subject="A319",
            entity_type=entity_type,
            entity_id=entity_id,
            evidence_type=evidence_type,
            source_type=source_type,
            source_name="inspection database",
            source_reference="inspection:A319",
            source_priority=10,
            observed_at=timestamp,
            retrieved_at=timestamp,
            effective_at=timestamp,
            value=value,
            unit="mm",
            claim_scope=("blade_height",),
            freshness_status=freshness_status,
            grounding_status=grounding_status,
            quality_status=quality_status,
            direct_or_derived=(
                EvidenceDirectness.DIRECT
            ),
            derivation_reference=None,
            provenance={"table": "inspection"},
        )

    def _assess(self, requirement_set, evidence):
        return assessor.assess_evidence(
            requirement_set,
            tuple(evidence),
            target_entity_ids={
                "conveyor_belt": "A319",
            },
        )

    def test_missing_required_is_insufficient(self):
        result = self._assess(
            self._set(self._requirement()),
            (),
        )

        self.assertEqual(
            result.status,
            assessor.
            EvidenceAssessmentStatus.INSUFFICIENT,
        )
        self.assertEqual(
            result.
            missing_required_requirement_ids,
            ("LATEST_BLADE_HEIGHT",),
        )

        item = result.requirement_results[0]

        self.assertEqual(
            item.status,
            assessor.
            RequirementAssessmentStatus.MISSING,
        )
        self.assertFalse(item.present)
        self.assertFalse(item.relevant)
        self.assertFalse(item.grounded)
        self.assertFalse(item.fresh)

    def test_valid_evidence_is_sufficient(self):
        evidence = self._item()

        result = self._assess(
            self._set(self._requirement()),
            (evidence,),
        )

        self.assertEqual(
            result.status,
            assessor.
            EvidenceAssessmentStatus.SUFFICIENT,
        )

        item = result.requirement_results[0]

        self.assertEqual(
            item.status,
            assessor.
            RequirementAssessmentStatus.SATISFIED,
        )
        self.assertEqual(
            item.matched_evidence_ids,
            ("measurement-1",),
        )
        self.assertTrue(item.present)
        self.assertTrue(item.relevant)
        self.assertTrue(item.grounded)
        self.assertTrue(item.fresh)
        self.assertFalse(item.conflicting)

    def test_wrong_source_is_present_but_not_relevant(self):
        evidence = self._item(
            source_type=(
                EvidenceSourceType.
                APPROVED_DOCUMENT
            ),
        )

        result = self._assess(
            self._set(self._requirement()),
            (evidence,),
        )

        item = result.requirement_results[0]

        self.assertEqual(
            result.status,
            assessor.
            EvidenceAssessmentStatus.INSUFFICIENT,
        )
        self.assertTrue(item.present)
        self.assertFalse(item.relevant)
        self.assertEqual(
            item.status,
            assessor.
            RequirementAssessmentStatus.PARTIAL,
        )

    def test_ungrounded_evidence_is_partial(self):
        evidence = self._item(
            grounding_status=(
                EvidenceGroundingStatus.UNGROUNDED
            ),
        )

        result = self._assess(
            self._set(self._requirement()),
            (evidence,),
        )

        item = result.requirement_results[0]

        self.assertTrue(item.present)
        self.assertTrue(item.relevant)
        self.assertFalse(item.grounded)
        self.assertFalse(item.fresh)
        self.assertEqual(
            result.status,
            assessor.
            EvidenceAssessmentStatus.INSUFFICIENT,
        )

    def test_stale_evidence_is_partial(self):
        evidence = self._item(
            freshness_status=(
                EvidenceFreshnessStatus.STALE
            ),
        )

        result = self._assess(
            self._set(self._requirement()),
            (evidence,),
        )

        item = result.requirement_results[0]

        self.assertTrue(item.grounded)
        self.assertFalse(item.fresh)
        self.assertEqual(
            item.status,
            assessor.
            RequirementAssessmentStatus.PARTIAL,
        )
        self.assertEqual(
            result.status,
            assessor.
            EvidenceAssessmentStatus.INSUFFICIENT,
        )

    def test_conflicting_valid_values_are_explicit(self):
        evidence = (
            self._item(
                evidence_id="measurement-1",
                value=12.5,
            ),
            self._item(
                evidence_id="measurement-2",
                value=9.0,
            ),
        )

        result = self._assess(
            self._set(self._requirement()),
            evidence,
        )

        item = result.requirement_results[0]

        self.assertTrue(item.conflicting)
        self.assertEqual(
            item.status,
            assessor.
            RequirementAssessmentStatus.CONFLICTING,
        )
        self.assertEqual(
            result.status,
            assessor.
            EvidenceAssessmentStatus.CONFLICTING,
        )
        self.assertEqual(
            result.conflicting_requirement_ids,
            ("LATEST_BLADE_HEIGHT",),
        )

    def test_wrong_entity_is_not_relevant(self):
        evidence = self._item(
            entity_id="B999",
        )

        result = self._assess(
            self._set(self._requirement()),
            (evidence,),
        )

        item = result.requirement_results[0]

        self.assertTrue(item.present)
        self.assertFalse(item.relevant)
        self.assertEqual(
            result.status,
            assessor.
            EvidenceAssessmentStatus.INSUFFICIENT,
        )

    def test_missing_desired_yields_partial(self):
        required = self._requirement()

        desired = self._requirement(
            requirement_id="INSPECTION_COMMENTS",
            evidence_types=(EvidenceType.RECORD,),
            necessity=RequirementNecessity.DESIRED,
        )

        result = self._assess(
            self._set(required, desired),
            (self._item(),),
        )

        self.assertEqual(
            result.status,
            assessor.
            EvidenceAssessmentStatus.PARTIAL,
        )
        self.assertEqual(
            result.
            missing_required_requirement_ids,
            (),
        )

    def test_assessment_does_not_mutate_inputs(self):
        requirement_set = self._set(
            self._requirement()
        )
        evidence = (self._item(),)

        requirement_snapshot = deepcopy(
            requirement_set
        )
        evidence_snapshot = deepcopy(
            evidence
        )

        first = self._assess(
            requirement_set,
            evidence,
        )
        second = self._assess(
            requirement_set,
            evidence,
        )

        self.assertEqual(
            requirement_set,
            requirement_snapshot,
        )
        self.assertEqual(
            evidence,
            evidence_snapshot,
        )
        self.assertEqual(first, second)


class DeterministicAssessmentHardeningV1Tests(
    DeterministicEvidenceAssessmentV1Tests
):
    def test_maximum_age_overrides_current_label(self):
        requirement = self._requirement(
            maximum_age_seconds=3600,
        )

        result = assessor.assess_evidence(
            self._set(requirement),
            (self._item(),),
            target_entity_ids={
                "conveyor_belt": "A319",
            },
            now=datetime(
                2026,
                8,
                28,
                10,
                0,
                tzinfo=timezone.utc,
            ),
        )

        item = result.requirement_results[0]

        self.assertTrue(item.grounded)
        self.assertFalse(item.fresh)
        self.assertEqual(
            item.status,
            assessor.
            RequirementAssessmentStatus.PARTIAL,
        )
        self.assertEqual(
            result.status,
            assessor.
            EvidenceAssessmentStatus.INSUFFICIENT,
        )

    def test_minimum_item_count_is_enforced(self):
        requirement = self._requirement(
            minimum_items=2,
        )

        result = self._assess(
            self._set(requirement),
            (self._item(),),
        )

        item = result.requirement_results[0]

        self.assertTrue(item.present)
        self.assertTrue(item.relevant)
        self.assertTrue(item.grounded)
        self.assertTrue(item.fresh)
        self.assertEqual(
            item.status,
            assessor.
            RequirementAssessmentStatus.PARTIAL,
        )
        self.assertEqual(
            result.status,
            assessor.
            EvidenceAssessmentStatus.INSUFFICIENT,
        )

    def test_invalid_quality_cannot_satisfy(self):
        evidence = self._item(
            quality_status=(
                EvidenceQualityStatus.INVALID
            ),
        )

        result = self._assess(
            self._set(self._requirement()),
            (evidence,),
        )

        item = result.requirement_results[0]

        self.assertTrue(item.grounded)
        self.assertFalse(item.fresh)
        self.assertEqual(
            result.status,
            assessor.
            EvidenceAssessmentStatus.INSUFFICIENT,
        )

    def test_identical_values_do_not_conflict(self):
        evidence = (
            self._item(
                evidence_id="measurement-1",
                value={"height": 12.5},
            ),
            self._item(
                evidence_id="measurement-2",
                value={"height": 12.5},
            ),
        )

        result = self._assess(
            self._set(self._requirement()),
            evidence,
        )

        item = result.requirement_results[0]

        self.assertFalse(item.conflicting)
        self.assertEqual(
            item.status,
            assessor.
            RequirementAssessmentStatus.SATISFIED,
        )
        self.assertEqual(
            result.status,
            assessor.
            EvidenceAssessmentStatus.SUFFICIENT,
        )

    def test_input_order_does_not_change_result(self):
        first_item = self._item(
            evidence_id="measurement-b",
            value=12.5,
        )
        second_item = self._item(
            evidence_id="measurement-a",
            value=12.5,
        )

        requirement_set = self._set(
            self._requirement()
        )

        first_result = self._assess(
            requirement_set,
            (
                first_item,
                second_item,
            ),
        )

        second_result = self._assess(
            requirement_set,
            (
                second_item,
                first_item,
            ),
        )

        self.assertEqual(
            first_result,
            second_result,
        )
        self.assertEqual(
            first_result.
            evidence_ids_considered,
            (
                "measurement-a",
                "measurement-b",
            ),
        )


if __name__ == "__main__":
    unittest.main()