from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import app.orchestrator.evidence_reconciler as reconciler
from app.orchestrator.evidence_assessor import (
    EvidenceAssessmentStatus,
)
from app.orchestrator.evidence_research_executor import (
    ResearchExecutionResult,
    ResearchExecutionStatus,
)


class EvidenceReconciliationTrustBoundaryV1Tests(
    unittest.TestCase
):
    def setUp(self):
        self.retrieved_at = datetime(
            2026,
            8,
            28,
            12,
            0,
            tzinfo=timezone.utc,
        )
        self.requirement_set = SimpleNamespace(
            requirement_set_id="technical_lookup.v1",
            intent="technical_lookup",
        )
        self.initial_assessment = SimpleNamespace(
            status=EvidenceAssessmentStatus.PARTIAL,
        )

    def wrapper(
        self,
        step_id,
        *,
        accepted=True,
    ):
        return {
            "step_id": step_id,
            "domain": "technical",
            "action": "technical_assistant",
            "endpoint": "/technical/assistant/ask",
            "accepted": accepted,
            "result": {
                "status": "ok",
                "results": [
                    {"source": step_id},
                ],
            },
        }

    def research(
        self,
        combined_results,
        *,
        requirement_set_id="technical_lookup.v1",
        intent="technical_lookup",
    ):
        return ResearchExecutionResult(
            contract_version="research_execution.v1",
            requirement_set_id=requirement_set_id,
            intent=intent,
            status=ResearchExecutionStatus.COMPLETED,
            research_performed=True,
            target_requirement_ids=(
                "TECHNICAL_SOURCE",
            ),
            initial_results=(),
            combined_results=tuple(
                combined_results
            ),
            agent_metadata=None,
            blocked_reason=None,
        )

    def dependencies(
        self,
        *,
        normalized=(),
    ):
        return (
            patch.object(
                reconciler,
                "derive_execution_result",
                return_value=SimpleNamespace(),
            ),
            patch.object(
                reconciler,
                "normalize_execution_result_evidence",
                return_value=normalized,
            ),
            patch.object(
                reconciler,
                "assess_evidence",
                return_value=self.initial_assessment,
            ),
        )

    def test_unaccepted_wrapper_is_discarded(self):
        research = self.research(
            (
                self.wrapper(
                    "rejected",
                    accepted=False,
                ),
            )
        )
        derive_patch, normalize_patch, assess_patch = (
            self.dependencies()
        )

        with (
            derive_patch as derive,
            normalize_patch as normalize,
            assess_patch,
        ):
            result = reconciler.reconcile_evidence(
                self.requirement_set,
                (),
                self.initial_assessment,
                research,
                retrieved_at=self.retrieved_at,
            )

        derive.assert_not_called()
        normalize.assert_not_called()
        self.assertEqual(
            result.discarded_result_count,
            1,
        )

    def test_requirement_identity_mismatch_is_blocked(
        self,
    ):
        research = self.research(
            (self.wrapper("foreign"),),
            requirement_set_id="price_stock.v1",
            intent="price_stock",
        )
        derive_patch, normalize_patch, assess_patch = (
            self.dependencies()
        )

        with (
            derive_patch as derive,
            normalize_patch as normalize,
            assess_patch as assess,
        ):
            result = reconciler.reconcile_evidence(
                self.requirement_set,
                (),
                self.initial_assessment,
                research,
                retrieved_at=self.retrieved_at,
            )

        self.assertEqual(
            result.status,
            reconciler.EvidenceReconciliationStatus.BLOCKED,
        )
        self.assertEqual(
            result.reasons,
            ("research_identity_mismatch",),
        )
        derive.assert_not_called()
        normalize.assert_not_called()
        assess.assert_not_called()

    def test_duplicate_wrappers_are_processed_once(self):
        wrapper = self.wrapper("duplicate")
        research = self.research(
            (
                wrapper,
                dict(wrapper),
            )
        )
        evidence = SimpleNamespace(
            evidence_id="evidence-1",
            value={"value": 1},
        )
        derive_patch, normalize_patch, assess_patch = (
            self.dependencies(
                normalized=(evidence,),
            )
        )

        with (
            derive_patch as derive,
            normalize_patch as normalize,
            assess_patch,
        ):
            result = reconciler.reconcile_evidence(
                self.requirement_set,
                (),
                self.initial_assessment,
                research,
                retrieved_at=self.retrieved_at,
            )

        self.assertEqual(derive.call_count, 1)
        self.assertEqual(normalize.call_count, 1)
        self.assertEqual(
            tuple(
                item.evidence_id
                for item in (
                    result.reconciled_evidence_items
                )
            ),
            ("evidence-1",),
        )

    def test_invalid_adapter_item_is_discarded(self):
        research = self.research(
            (self.wrapper("invalid-evidence"),)
        )
        invalid_item = SimpleNamespace(
            value={"missing": "evidence_id"},
        )
        derive_patch, normalize_patch, assess_patch = (
            self.dependencies(
                normalized=(invalid_item,),
            )
        )

        with (
            derive_patch,
            normalize_patch,
            assess_patch as assess,
        ):
            result = reconciler.reconcile_evidence(
                self.requirement_set,
                (),
                self.initial_assessment,
                research,
                retrieved_at=self.retrieved_at,
            )

        self.assertEqual(
            result.reconciled_evidence_items,
            (),
        )
        self.assertEqual(
            result.added_evidence_ids,
            (),
        )
        self.assertEqual(
            result.discarded_result_count,
            1,
        )
        assess.assert_called_once()


if __name__ == "__main__":
    unittest.main()