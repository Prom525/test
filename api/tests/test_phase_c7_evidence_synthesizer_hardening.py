from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
import unittest

from app.orchestrator.evidence_contracts import (
    EvidenceDirectness,
)
from app.orchestrator.evidence_reconciler import (
    EvidenceReconciliationStatus,
)
import app.orchestrator.evidence_synthesizer as synthesizer
from tests.test_phase_c7_evidence_synthesizer_behavior import (
    DeterministicGroundedSynthesisV1Tests,
)


class GroundedSynthesisTrustBoundaryV1Tests(
    DeterministicGroundedSynthesisV1Tests
):
    def test_requirement_identity_mismatch_is_blocked(self):
        evidence = self._evidence(
            "evidence-1",
            10,
        )
        requirement = self._requirement_result(
            "LATEST_BLADE_HEIGHT",
            ("evidence-1",),
        )
        assessment = self._assessment(
            (requirement,)
        )
        mismatched_assessment = replace(
            assessment,
            requirement_set_id="different-set.v1",
        )
        reconciliation = self._reconciliation(
            (evidence,),
            mismatched_assessment,
            status=EvidenceReconciliationStatus.UNCHANGED,
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
            "assessment_identity_mismatch",
            result.reasons,
        )

    def test_malformed_evidence_item_is_discarded(self):
        valid = self._evidence(
            "evidence-1",
            10,
        )
        malformed = SimpleNamespace(
            value="untrusted",
        )
        requirement = self._requirement_result(
            "LATEST_BLADE_HEIGHT",
            ("evidence-1",),
        )
        reconciliation = self._reconciliation(
            (malformed, valid),
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
        self.assertEqual(
            result.evidence_ids_used,
            ("evidence-1",),
        )
        self.assertEqual(len(result.claims), 1)

    def test_conflicting_duplicate_id_is_omitted_deterministically(
        self,
    ):
        first = self._evidence(
            "evidence-1",
            10,
        )
        second = self._evidence(
            "evidence-1",
            12,
        )
        requirement = self._requirement_result(
            "LATEST_BLADE_HEIGHT",
            ("evidence-1",),
        )
        assessment = self._assessment(
            (requirement,)
        )

        first_result = (
            synthesizer
            .synthesize_grounded_evidence(
                self._reconciliation(
                    (first, second),
                    assessment,
                )
            )
        )
        second_result = (
            synthesizer
            .synthesize_grounded_evidence(
                self._reconciliation(
                    (second, first),
                    assessment,
                )
            )
        )

        self.assertEqual(first_result, second_result)
        self.assertEqual(first_result.claims, ())
        self.assertEqual(
            first_result.evidence_ids_used,
            (),
        )
        self.assertEqual(
            first_result.omitted_requirement_ids,
            ("LATEST_BLADE_HEIGHT",),
        )
        self.assertIn(
            "duplicate_evidence_conflict",
            first_result.reasons,
        )

    def test_unreferenced_derived_evidence_is_omitted(self):
        evidence = replace(
            self._evidence(
                "evidence-1",
                10,
            ),
            direct_or_derived=(
                EvidenceDirectness.DERIVED
            ),
            derivation_reference=None,
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
            synthesizer.GroundedSynthesisStatus.PARTIAL,
        )
        self.assertEqual(result.claims, ())
        self.assertEqual(
            result.evidence_ids_used,
            (),
        )
        self.assertEqual(
            result.omitted_requirement_ids,
            ("LATEST_BLADE_HEIGHT",),
        )


if __name__ == "__main__":
    unittest.main()