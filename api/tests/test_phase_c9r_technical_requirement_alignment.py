from __future__ import annotations

import unittest

from app.orchestrator.evidence_contracts import (
    EvidenceSourceType,
    EvidenceType,
)
from app.orchestrator.evidence_requirement_catalog import (
    get_requirement_set,
)


class TechnicalRequirementAlignmentV1Tests(
    unittest.TestCase
):
    def test_controlled_structured_record_satisfies_type_contract(
        self,
    ) -> None:
        requirement_set = get_requirement_set(
            "technical_lookup"
        )

        self.assertIsNotNone(requirement_set)
        assert requirement_set is not None

        requirements = {
            requirement.requirement_id: requirement
            for requirement in requirement_set.requirements
        }

        self.assertEqual(
            set(requirements),
            {"TECHNICAL_SOURCE"},
        )

        requirement = requirements[
            "TECHNICAL_SOURCE"
        ]

        self.assertIn(
            EvidenceType.DOCUMENT_FRAGMENT,
            requirement.evidence_types,
        )
        self.assertIn(
            EvidenceType.RECORD,
            requirement.evidence_types,
        )
        self.assertEqual(
            set(requirement.allowed_source_types),
            {
                EvidenceSourceType.
                STRUCTURED_KNOWLEDGE,
                EvidenceSourceType.
                APPROVED_DOCUMENT,
                EvidenceSourceType.
                RAG_CONTEXT,
            },
        )


if __name__ == "__main__":
    unittest.main()