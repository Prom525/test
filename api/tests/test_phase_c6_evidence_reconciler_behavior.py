from __future__ import annotations

from copy import deepcopy
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


class DeterministicEvidenceReconciliationV1Tests(
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

    def assessment(self, status):
        return SimpleNamespace(status=status)

    def evidence(self, evidence_id, value=None):
        return SimpleNamespace(
            evidence_id=evidence_id,
            value=(
                {"value": evidence_id}
                if value is None
                else value
            ),
        )

    def wrapper(self, step_id):
        return {
            "step_id": step_id,
            "domain": "technical",
            "action": "technical_assistant",
            "endpoint": "/technical/assistant/ask",
            "accepted": True,
            "result": {
                "status": "ok",
                "results": [
                    {"source": step_id},
                ],
            },
        }

    def research(
        self,
        status,
        *,
        initial_results=(),
        combined_results=(),
        research_performed=True,
        blocked_reason=None,
    ):
        return ResearchExecutionResult(
            contract_version="research_execution.v1",
            requirement_set_id=(
                self.requirement_set.requirement_set_id
            ),
            intent=self.requirement_set.intent,
            status=status,
            research_performed=research_performed,
            target_requirement_ids=(
                "TECHNICAL_SOURCE",
            ),
            initial_results=tuple(initial_results),
            combined_results=tuple(combined_results),
            agent_metadata=None,
            blocked_reason=blocked_reason,
        )

    def dependencies(
        self,
        *,
        derived=None,
        normalized=(),
        reassessed=None,
    ):
        return (
            patch.object(
                reconciler,
                "derive_execution_result",
                return_value=derived,
                create=True,
            ),
            patch.object(
                reconciler,
                "normalize_execution_result_evidence",
                return_value=normalized,
                create=True,
            ),
            patch.object(
                reconciler,
                "assess_evidence",
                return_value=reassessed,
                create=True,
            ),
        )

    def test_skipped_research_is_unchanged(self):
        initial_evidence = (
            self.evidence("existing"),
        )
        initial_assessment = self.assessment(
            EvidenceAssessmentStatus.SUFFICIENT
        )
        research = self.research(
            ResearchExecutionStatus.SKIPPED,
            initial_results=(
                self.wrapper("initial"),
            ),
            combined_results=(
                self.wrapper("initial"),
            ),
            research_performed=False,
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
                initial_evidence,
                initial_assessment,
                research,
                retrieved_at=self.retrieved_at,
            )

        self.assertEqual(
            result.status,
            reconciler.EvidenceReconciliationStatus.UNCHANGED,
        )
        self.assertEqual(
            result.reconciled_evidence_items,
            initial_evidence,
        )
        self.assertEqual(result.added_evidence_ids, ())
        self.assertEqual(result.discarded_result_count, 0)
        self.assertIs(
            result.reconciled_assessment,
            initial_assessment,
        )
        derive.assert_not_called()
        normalize.assert_not_called()
        assess.assert_not_called()

    def test_completed_research_bridges_valid_wrapper(self):
        valid = self.wrapper("follow-1")
        malformed = {
            "step_id": "broken",
            "result": {"status": "ok"},
        }
        research = self.research(
            ResearchExecutionStatus.COMPLETED,
            combined_results=(valid, malformed),
        )
        initial_assessment = self.assessment(
            EvidenceAssessmentStatus.INSUFFICIENT
        )
        typed = SimpleNamespace(
            step_id="follow-1",
            action="technical_assistant",
        )
        added = self.evidence("new-1")
        reassessed = self.assessment(
            EvidenceAssessmentStatus.PARTIAL
        )
        derive_patch, normalize_patch, assess_patch = (
            self.dependencies(
                derived=typed,
                normalized=(added,),
                reassessed=reassessed,
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
                initial_assessment,
                research,
                retrieved_at=self.retrieved_at,
            )

        self.assertEqual(derive.call_count, 1)
        request = derive.call_args.kwargs["request"]
        self.assertEqual(request.step_id, "follow-1")
        self.assertEqual(
            request.action,
            "technical_assistant",
        )
        self.assertEqual(request.domain, "technical")
        self.assertEqual(
            request.endpoint,
            "/technical/assistant/ask",
        )
        self.assertEqual(
            derive.call_args.kwargs["raw_result"],
            valid["result"],
        )
        self.assertTrue(
            derive.call_args.kwargs["legacy_accepted"]
        )
        normalize.assert_called_once_with(
            typed,
            retrieved_at=self.retrieved_at,
        )
        self.assertEqual(
            result.added_evidence_ids,
            ("new-1",),
        )
        self.assertEqual(
            result.discarded_result_count,
            1,
        )

    def test_duplicate_ids_are_deduplicated(self):
        initial = (
            self.evidence("evidence-b"),
            self.evidence("evidence-a"),
        )
        initial_assessment = self.assessment(
            EvidenceAssessmentStatus.PARTIAL
        )
        research = self.research(
            ResearchExecutionStatus.COMPLETED,
            combined_results=(
                self.wrapper("follow-1"),
            ),
        )
        derive_patch, normalize_patch, assess_patch = (
            self.dependencies(
                derived=SimpleNamespace(),
                normalized=(
                    self.evidence(
                        "evidence-a",
                        {"changed": True},
                    ),
                    self.evidence("evidence-c"),
                ),
                reassessed=initial_assessment,
            )
        )

        with (
            derive_patch,
            normalize_patch,
            assess_patch,
        ):
            result = reconciler.reconcile_evidence(
                self.requirement_set,
                initial,
                initial_assessment,
                research,
                retrieved_at=self.retrieved_at,
            )

        self.assertEqual(
            tuple(
                item.evidence_id
                for item in (
                    result.reconciled_evidence_items
                )
            ),
            (
                "evidence-a",
                "evidence-b",
                "evidence-c",
            ),
        )
        self.assertEqual(
            result.added_evidence_ids,
            ("evidence-c",),
        )

    def test_improvement_is_explicit(self):
        initial_assessment = self.assessment(
            EvidenceAssessmentStatus.INSUFFICIENT
        )
        reassessed = self.assessment(
            EvidenceAssessmentStatus.SUFFICIENT
        )
        research = self.research(
            ResearchExecutionStatus.COMPLETED,
            combined_results=(
                self.wrapper("follow-1"),
            ),
        )
        derive_patch, normalize_patch, assess_patch = (
            self.dependencies(
                derived=SimpleNamespace(),
                normalized=(self.evidence("new"),),
                reassessed=reassessed,
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
                initial_assessment,
                research,
                retrieved_at=self.retrieved_at,
                target_entity_ids={
                    "asset": "BAND-1",
                },
                now=self.retrieved_at,
            )

        self.assertEqual(
            result.status,
            reconciler.EvidenceReconciliationStatus.IMPROVED,
        )
        self.assertIs(
            result.reconciled_assessment,
            reassessed,
        )
        assess.assert_called_once()
        self.assertEqual(
            assess.call_args.kwargs[
                "target_entity_ids"
            ],
            {"asset": "BAND-1"},
        )
        self.assertEqual(
            assess.call_args.kwargs["now"],
            self.retrieved_at,
        )

    def test_non_improvement_is_unresolved(self):
        initial_assessment = self.assessment(
            EvidenceAssessmentStatus.PARTIAL
        )
        reassessed = self.assessment(
            EvidenceAssessmentStatus.PARTIAL
        )
        research = self.research(
            ResearchExecutionStatus.COMPLETED,
            combined_results=(
                self.wrapper("follow-1"),
            ),
        )
        derive_patch, normalize_patch, assess_patch = (
            self.dependencies(
                derived=SimpleNamespace(),
                normalized=(self.evidence("new"),),
                reassessed=reassessed,
            )
        )

        with (
            derive_patch,
            normalize_patch,
            assess_patch,
        ):
            result = reconciler.reconcile_evidence(
                self.requirement_set,
                (),
                initial_assessment,
                research,
                retrieved_at=self.retrieved_at,
            )

        self.assertEqual(
            result.status,
            reconciler.EvidenceReconciliationStatus.UNRESOLVED,
        )

    def test_blocked_research_is_typed_blocked(self):
        initial_assessment = self.assessment(
            EvidenceAssessmentStatus.INSUFFICIENT
        )
        research = self.research(
            ResearchExecutionStatus.BLOCKED,
            research_performed=False,
            blocked_reason=(
                "research_runtime_error:RuntimeError"
            ),
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
                initial_assessment,
                research,
                retrieved_at=self.retrieved_at,
            )

        self.assertEqual(
            result.status,
            reconciler.EvidenceReconciliationStatus.BLOCKED,
        )
        self.assertEqual(
            result.reasons,
            (
                "research_runtime_error:RuntimeError",
            ),
        )
        derive.assert_not_called()
        normalize.assert_not_called()
        assess.assert_not_called()

    def test_inputs_are_not_mutated(self):
        initial_evidence = (
            self.evidence(
                "existing",
                {"nested": ["original"]},
            ),
        )
        research = self.research(
            ResearchExecutionStatus.COMPLETED,
            combined_results=(
                self.wrapper("follow-1"),
            ),
        )
        initial_assessment = self.assessment(
            EvidenceAssessmentStatus.PARTIAL
        )
        initial_snapshot = deepcopy(initial_evidence)
        research_snapshot = deepcopy(research)
        derive_patch, normalize_patch, assess_patch = (
            self.dependencies(
                derived=SimpleNamespace(),
                normalized=(),
                reassessed=initial_assessment,
            )
        )

        with (
            derive_patch,
            normalize_patch,
            assess_patch,
        ):
            reconciler.reconcile_evidence(
                self.requirement_set,
                initial_evidence,
                initial_assessment,
                research,
                retrieved_at=self.retrieved_at,
            )

        self.assertEqual(
            initial_evidence,
            initial_snapshot,
        )
        self.assertEqual(
            research,
            research_snapshot,
        )


if __name__ == "__main__":
    unittest.main()