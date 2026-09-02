from __future__ import annotations

import unittest

from app.orchestrator.evidence_adapters import (
    normalize_execution_result_evidence,
)
from app.orchestrator.evidence_assessor import (
    assess_evidence,
)
from app.orchestrator.evidence_requirement_catalog import (
    get_requirement_set,
)
from app.orchestrator.evidence_research_gate import (
    decide_research_requirement,
)
from tests.test_phase_c1_evidence_adapters import (
    RETRIEVED_AT,
    _execution_result,
)


class TechnicalRequirementBehaviorV1Tests(
    unittest.TestCase
):
    def test_existing_adapter_output_requires_no_research(
        self,
    ) -> None:
        requirement_set = get_requirement_set(
            "technical_lookup"
        )

        self.assertIsNotNone(requirement_set)
        assert requirement_set is not None

        evidence_items = (
            normalize_execution_result_evidence(
                _execution_result(),
                retrieved_at=RETRIEVED_AT,
            )
        )

        self.assertGreaterEqual(
            len(evidence_items),
            1,
        )
        self.assertTrue(
            all(
                item.evidence_type.value == "RECORD"
                for item in evidence_items
            )
        )
        self.assertTrue(
            all(
                item.source_type.value
                == "STRUCTURED_KNOWLEDGE"
                for item in evidence_items
            )
        )
        self.assertTrue(
            all(
                item.grounding_status.value
                == "GROUNDED"
                for item in evidence_items
            )
        )
        self.assertTrue(
            all(
                item.quality_status.value
                == "VALID"
                for item in evidence_items
            )
        )

        assessment = assess_evidence(
            requirement_set,
            evidence_items,
            now=RETRIEVED_AT,
        )

        self.assertEqual(
            assessment.status.value,
            "sufficient",
        )
        self.assertEqual(
            assessment.missing_required_requirement_ids,
            (),
        )
        self.assertEqual(
            len(assessment.requirement_results),
            1,
        )

        requirement_result = (
            assessment.requirement_results[0]
        )

        self.assertEqual(
            requirement_result.requirement_id,
            "TECHNICAL_SOURCE",
        )
        self.assertEqual(
            requirement_result.status.value,
            "satisfied",
        )
        self.assertTrue(requirement_result.present)
        self.assertTrue(requirement_result.relevant)
        self.assertTrue(requirement_result.grounded)
        self.assertFalse(
            requirement_result.conflicting
        )
        self.assertGreaterEqual(
            len(
                requirement_result.
                matched_evidence_ids
            ),
            1,
        )

        decision = decide_research_requirement(
            assessment
        )

        self.assertEqual(
            decision.status.value,
            "not_required",
        )
        self.assertFalse(
            decision.research_required
        )
        self.assertEqual(
            decision.target_requirement_ids,
            (),
        )


if __name__ == "__main__":
    unittest.main()