from __future__ import annotations

import pathlib
import unittest

from app.orchestrator.evidence_contracts import (
    EvidenceSourceType,
    EvidenceType,
)
from app.orchestrator.evidence_requirements import (
    EVIDENCE_REQUIREMENT_CONTRACT_VERSION,
    EvidenceRequirementSet,
    RequirementNecessity,
)
import app.orchestrator.evidence_requirement_catalog as catalog


EXPECTED_INTENTS = {
    "band_status",
    "scraper_status",
    "lifecycle_analysis",
    "replacement_advice",
    "product_lookup",
    "price_stock",
    "technical_lookup",
    "technical_calculation",
    "person_role_lookup",
    "rfq_status",
    "diagnostics_health",
}


class EvidenceRequirementCatalogV1Tests(
    unittest.TestCase
):
    def _set(self, intent):
        return catalog.REQUIREMENT_SETS_BY_INTENT[
            intent
        ]

    def _requirement(self, intent, requirement_id):
        requirement_set = self._set(intent)

        matches = tuple(
            requirement
            for requirement
            in requirement_set.requirements
            if requirement.requirement_id
            == requirement_id
        )

        self.assertEqual(
            len(matches),
            1,
            msg=(
                f"{intent} must contain exactly one "
                f"{requirement_id}"
            ),
        )

        return matches[0]

    def test_exact_initial_intent_catalog(self):
        self.assertEqual(
            set(
                catalog.
                REQUIREMENT_SETS_BY_INTENT
            ),
            EXPECTED_INTENTS,
        )
        self.assertEqual(
            len(
                catalog.
                REQUIREMENT_SETS_BY_INTENT
            ),
            11,
        )

    def test_all_sets_are_typed_and_deterministic(self):
        for intent in sorted(EXPECTED_INTENTS):
            requirement_set = self._set(intent)

            self.assertIsInstance(
                requirement_set,
                EvidenceRequirementSet,
            )
            self.assertEqual(
                requirement_set.contract_version,
                EVIDENCE_REQUIREMENT_CONTRACT_VERSION,
            )
            self.assertEqual(
                requirement_set.intent,
                intent,
            )
            self.assertEqual(
                requirement_set.requirement_set_id,
                f"{intent}.v1",
            )
            self.assertIsInstance(
                requirement_set.requirements,
                tuple,
            )
            self.assertGreater(
                len(requirement_set.requirements),
                0,
            )

    def test_every_intent_has_required_evidence(self):
        for intent in sorted(EXPECTED_INTENTS):
            required = tuple(
                requirement
                for requirement
                in self._set(intent).requirements
                if requirement.necessity
                == RequirementNecessity.REQUIRED
            )

            self.assertGreater(
                len(required),
                0,
                msg=intent,
            )

    def test_requirement_ids_are_unique_per_intent(self):
        for intent in sorted(EXPECTED_INTENTS):
            requirement_ids = tuple(
                requirement.requirement_id
                for requirement
                in self._set(intent).requirements
            )

            self.assertEqual(
                len(requirement_ids),
                len(set(requirement_ids)),
                msg=intent,
            )

            for requirement in (
                self._set(intent).requirements
            ):
                self.assertGreaterEqual(
                    requirement.minimum_items,
                    1,
                )

    def test_price_and_stock_require_live_evidence(self):
        for requirement_id in (
            "CURRENT_PRICE",
            "CURRENT_STOCK",
        ):
            requirement = self._requirement(
                "price_stock",
                requirement_id,
            )

            self.assertEqual(
                requirement.necessity,
                RequirementNecessity.REQUIRED,
            )
            self.assertIn(
                EvidenceSourceType.LIVE_CANONICAL,
                requirement.allowed_source_types,
            )
            self.assertIn(
                EvidenceType.DOCUMENT_FRAGMENT,
                requirement.forbidden_substitutions,
            )

    def test_technical_lookup_uses_controlled_sources(self):
        requirement = self._requirement(
            "technical_lookup",
            "TECHNICAL_SOURCE",
        )

        self.assertIn(
            EvidenceType.DOCUMENT_FRAGMENT,
            requirement.evidence_types,
        )
        self.assertEqual(
            set(requirement.allowed_source_types),
            {
                EvidenceSourceType.
                STRUCTURED_KNOWLEDGE,
                EvidenceSourceType.
                APPROVED_DOCUMENT,
                EvidenceSourceType.RAG_CONTEXT,
            },
        )

    def test_calculation_requires_calculation_result(self):
        requirement = self._requirement(
            "technical_calculation",
            "CALCULATION_RESULT",
        )

        self.assertEqual(
            requirement.evidence_types,
            (
                EvidenceType.
                CALCULATION_RESULT,
            ),
        )
        self.assertEqual(
            requirement.allowed_source_types,
            (
                EvidenceSourceType.
                CALCULATION,
            ),
        )

    def test_person_rfq_and_diagnostics_are_not_interchangeable(
        self,
    ):
        person_role = self._requirement(
            "person_role_lookup",
            "CURRENT_PERSON_ROLE",
        )
        rfq_status = self._requirement(
            "rfq_status",
            "RFQ_STATUS",
        )
        diagnostic = self._requirement(
            "diagnostics_health",
            "DIAGNOSTIC_FINDING",
        )

        self.assertIn(
            EvidenceType.RECORD,
            person_role.evidence_types,
        )
        self.assertIn(
            EvidenceSourceType.LIVE_CANONICAL,
            person_role.allowed_source_types,
        )

        self.assertIn(
            EvidenceType.STATUS,
            rfq_status.evidence_types,
        )
        self.assertIn(
            EvidenceSourceType.LIVE_CANONICAL,
            rfq_status.allowed_source_types,
        )

        self.assertEqual(
            diagnostic.evidence_types,
            (
                EvidenceType.
                DIAGNOSTIC_FINDING,
            ),
        )
        self.assertEqual(
            diagnostic.allowed_source_types,
            (
                EvidenceSourceType.DIAGNOSTIC,
            ),
        )

    def test_catalog_lookup_is_exact(self):
        self.assertIs(
            catalog.get_requirement_set(
                "band_status"
            ),
            self._set("band_status"),
        )
        self.assertIsNone(
            catalog.get_requirement_set(
                "unknown_intent"
            )
        )
        self.assertIsNone(
            catalog.get_requirement_set("")
        )

    def test_catalog_contains_no_assessment_or_execution(self):
        source = pathlib.Path(
            catalog.__file__
        ).read_text(
            encoding="utf-8",
        ).lower()

        for forbidden in (
            "assess_evidence",
            "run_research",
            "reconcile_evidence",
            "synthesize_answer",
            "execute_plan",
        ):
            self.assertNotIn(
                forbidden,
                source,
            )


if __name__ == "__main__":
    unittest.main()