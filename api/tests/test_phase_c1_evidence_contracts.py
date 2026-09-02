from __future__ import annotations

import dataclasses
import unittest
from datetime import datetime, timezone

import app.orchestrator.evidence_contracts as contracts
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


class EvidenceContractsV1Tests(unittest.TestCase):
    def test_contract_version_is_exact(self):
        self.assertEqual(
            EVIDENCE_CONTRACT_VERSION,
            "promati.phase_c1.evidence_contract.v1",
        )

    def test_taxonomy_values_are_exact(self):
        expected = {
            EvidenceSourceType: (
                "LIVE_CANONICAL",
                "STRUCTURED_KNOWLEDGE",
                "APPROVED_DOCUMENT",
                "RAG_CONTEXT",
                "CALCULATION",
                "DIAGNOSTIC",
                "RUNTIME",
                "SPECIALIST_RESULT",
                "UNKNOWN",
            ),
            EvidenceType: (
                "RECORD",
                "MEASUREMENT",
                "EVENT",
                "STATUS",
                "DOCUMENT_FRAGMENT",
                "CALCULATION_RESULT",
                "DIAGNOSTIC_FINDING",
                "ASSET_RESOLUTION",
                "RUNTIME_IDENTITY",
                "SPECIALIST_RESULT",
                "UNKNOWN",
            ),
            EvidenceFreshnessStatus: (
                "CURRENT",
                "LATEST_KNOWN",
                "STALE",
                "UNKNOWN",
                "NOT_APPLICABLE",
            ),
            EvidenceGroundingStatus: (
                "GROUNDED",
                "PARTIAL",
                "UNGROUNDED",
                "UNKNOWN",
            ),
            EvidenceQualityStatus: (
                "VALID",
                "PARTIAL",
                "INVALID",
                "UNKNOWN",
            ),
            EvidenceDirectness: (
                "DIRECT",
                "DERIVED",
                "UNKNOWN",
            ),
        }

        for enum_type, expected_values in expected.items():
            with self.subTest(enum_type=enum_type.__name__):
                self.assertEqual(
                    tuple(item.value for item in enum_type),
                    expected_values,
                )

    def test_evidence_item_fields_are_exact(self):
        self.assertEqual(
            tuple(
                field.name
                for field in dataclasses.fields(EvidenceItem)
            ),
            (
                "contract_version",
                "evidence_id",
                "execution_step_id",
                "specialist_id",
                "domain",
                "subject",
                "entity_type",
                "entity_id",
                "evidence_type",
                "source_type",
                "source_name",
                "source_reference",
                "source_priority",
                "observed_at",
                "retrieved_at",
                "effective_at",
                "value",
                "unit",
                "claim_scope",
                "freshness_status",
                "grounding_status",
                "quality_status",
                "direct_or_derived",
                "derivation_reference",
                "provenance",
            ),
        )

    def test_evidence_item_is_constructible(self):
        retrieved_at = datetime(
            2026,
            8,
            27,
            11,
            30,
            tzinfo=timezone.utc,
        )

        item = EvidenceItem(
            contract_version=EVIDENCE_CONTRACT_VERSION,
            evidence_id="evidence-001",
            execution_step_id="step-001",
            specialist_id="analysis_assistant",
            domain="inspection",
            subject="A319 West blade height",
            entity_type="scraper_position",
            entity_id="A319:WEST",
            evidence_type=EvidenceType.MEASUREMENT,
            source_type=EvidenceSourceType.LIVE_CANONICAL,
            source_name="inspection_latest",
            source_reference="inspection:A319:WEST",
            source_priority=1,
            observed_at=None,
            retrieved_at=retrieved_at,
            effective_at=None,
            value=5,
            unit="mm",
            claim_scope=("LATEST_BLADE_HEIGHT",),
            freshness_status=EvidenceFreshnessStatus.LATEST_KNOWN,
            grounding_status=EvidenceGroundingStatus.GROUNDED,
            quality_status=EvidenceQualityStatus.VALID,
            direct_or_derived=EvidenceDirectness.DIRECT,
            derivation_reference=None,
            provenance={
                "source_file": "inspection.xlsx",
                "sheet": "A319",
            },
        )

        self.assertEqual(item.value, 5)
        self.assertEqual(item.unit, "mm")
        self.assertEqual(
            item.retrieved_at,
            retrieved_at,
        )

    def test_missing_metadata_is_explicit(self):
        item = EvidenceItem(
            contract_version=EVIDENCE_CONTRACT_VERSION,
            evidence_id="evidence-unknown",
            execution_step_id="step-unknown",
            specialist_id="technical_assistant",
            domain="technical",
            subject=None,
            entity_type=None,
            entity_id=None,
            evidence_type=EvidenceType.UNKNOWN,
            source_type=EvidenceSourceType.UNKNOWN,
            source_name=None,
            source_reference=None,
            source_priority=None,
            observed_at=None,
            retrieved_at=None,
            effective_at=None,
            value=None,
            unit=None,
            claim_scope=(),
            freshness_status=EvidenceFreshnessStatus.UNKNOWN,
            grounding_status=EvidenceGroundingStatus.UNKNOWN,
            quality_status=EvidenceQualityStatus.UNKNOWN,
            direct_or_derived=EvidenceDirectness.UNKNOWN,
            derivation_reference=None,
            provenance=None,
        )

        self.assertIsNone(item.entity_id)
        self.assertIsNone(item.observed_at)
        self.assertIsNone(item.provenance)
        self.assertEqual(
            item.direct_or_derived,
            EvidenceDirectness.UNKNOWN,
        )

    def test_evidence_item_is_frozen(self):
        item = EvidenceItem(
            contract_version=EVIDENCE_CONTRACT_VERSION,
            evidence_id="evidence-frozen",
            execution_step_id="step-frozen",
            specialist_id="diagnostics_assistant",
            domain="diagnostics",
            subject=None,
            entity_type=None,
            entity_id=None,
            evidence_type=EvidenceType.DIAGNOSTIC_FINDING,
            source_type=EvidenceSourceType.DIAGNOSTIC,
            source_name=None,
            source_reference=None,
            source_priority=None,
            observed_at=None,
            retrieved_at=None,
            effective_at=None,
            value={},
            unit=None,
            claim_scope=(),
            freshness_status=EvidenceFreshnessStatus.UNKNOWN,
            grounding_status=EvidenceGroundingStatus.UNKNOWN,
            quality_status=EvidenceQualityStatus.UNKNOWN,
            direct_or_derived=EvidenceDirectness.UNKNOWN,
            derivation_reference=None,
            provenance=None,
        )

        with self.assertRaises(
            dataclasses.FrozenInstanceError
        ):
            item.evidence_id = "changed"

    def test_c1_contains_no_assessor_or_synthesis(self):
        forbidden_names = {
            "EvidenceAssessmentResult",
            "assess_evidence",
            "research_required",
            "synthesize_evidence",
        }

        self.assertEqual(
            forbidden_names.intersection(dir(contracts)),
            set(),
        )


if __name__ == "__main__":
    unittest.main()