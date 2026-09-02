from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from app.orchestrator.execution_contracts import (  # noqa: E402
    EXECUTION_CONTRACT_VERSION,
    ExecutionOutcome,
    ExecutionResult,
    ExecutionTransportState,
)
from app.orchestrator.execution_shadow import (  # noqa: E402
    derive_semantic_outcome,
)
from app.orchestrator.execution_status import (  # noqa: E402
    has_service_accepted_execution,
)


def make_result(
    outcome: ExecutionOutcome,
    *,
    transport: ExecutionTransportState = ExecutionTransportState.COMPLETED,
    legacy_accepted: bool = True,
) -> ExecutionResult:
    return ExecutionResult(
        contract_version=EXECUTION_CONTRACT_VERSION,
        step_id="step_1",
        action="analysis_assistant",
        domain="inspection",
        endpoint="/analysis/assistant/ask",
        transport_state=transport,
        semantic_outcome=outcome,
        specialist_status=None,
        legacy_accepted=legacy_accepted,
        result={},
        error=(
            "synthetic_transport_failure"
            if transport is ExecutionTransportState.FAILED
            else None
        ),
        attempt_count=1,
        duration_ms=1,
        evidence_metadata=None,
        provenance_metadata=None,
    )


def service_accepts(
    typed: ExecutionResult,
    *,
    legacy_accepted: bool = True,
) -> bool:
    return has_service_accepted_execution(
        [typed],
        [
            {
                "step_id": "step_1",
                "accepted": legacy_accepted,
                "result": {},
            }
        ],
    )


class ExecutionOutcomeSemanticTests(unittest.TestCase):

    # Analysis-assistant contract.

    def test_analysis_statusless_success_is_success(self):
        outcome = derive_semantic_outcome(
            "analysis_assistant",
            {"intent": "band_deep_analysis"},
        )
        self.assertEqual(
            outcome,
            ExecutionOutcome.SUCCESS,
        )


    def test_analysis_clarification_is_not_success(self):
        outcome = derive_semantic_outcome(
            "analysis_assistant",
            {"status": "clarification_required"},
        )

        self.assertEqual(
            outcome,
            ExecutionOutcome.CLARIFICATION_REQUIRED,
        )
        self.assertNotEqual(
            outcome,
            ExecutionOutcome.SUCCESS,
        )


    def test_analysis_ambiguous_is_semantic_ambiguous(self):
        outcome = derive_semantic_outcome(
            "analysis_assistant",
            {"status": "ambiguous"},
        )

        self.assertEqual(
            outcome,
            ExecutionOutcome.AMBIGUOUS,
        )


    def test_analysis_context_conflict_is_semantic_conflict(self):
        outcome = derive_semantic_outcome(
            "analysis_assistant",
            {"status": "context_conflict"},
        )

        self.assertEqual(
            outcome,
            ExecutionOutcome.CONTEXT_CONFLICT,
        )


    def test_analysis_not_found_is_negative_business_outcome(self):
        outcome = derive_semantic_outcome(
            "analysis_assistant",
            {"status": "not_found"},
        )

        self.assertEqual(
            outcome,
            ExecutionOutcome.NOT_FOUND,
        )


    def test_analysis_unavailable_is_unavailable(self):
        outcome = derive_semantic_outcome(
            "analysis_assistant",
            {"status": "unavailable"},
        )

        self.assertEqual(
            outcome,
            ExecutionOutcome.UNAVAILABLE,
        )


    # Universal execution-failure mapping.

    def test_explicit_error_is_error(self):
        outcome = derive_semantic_outcome(
            "analysis_assistant",
            {"status": "error"},
        )

        self.assertEqual(
            outcome,
            ExecutionOutcome.ERROR,
        )


    def test_failed_and_failure_are_error(self):
        for status in ("failed", "failure"):
            with self.subTest(status=status):
                outcome = derive_semantic_outcome(
                    "analysis_assistant",
                    {"status": status},
                )

                self.assertEqual(
                    outcome,
                    ExecutionOutcome.ERROR,
                )


    # Service compatibility is deliberately broader
    # than semantic SUCCESS.

    def test_completed_success_is_service_accepted(self):
        self.assertTrue(
            service_accepts(
                make_result(
                    ExecutionOutcome.SUCCESS
                )
            )
        )


    def test_completed_clarification_is_compatibility_accepted(self):
        typed = make_result(
            ExecutionOutcome.CLARIFICATION_REQUIRED
        )

        self.assertNotEqual(
            typed.semantic_outcome,
            ExecutionOutcome.SUCCESS,
        )
        self.assertTrue(
            service_accepts(typed)
        )


    def test_completed_not_found_is_not_execution_failure(self):
        typed = make_result(
            ExecutionOutcome.NOT_FOUND
        )

        self.assertNotEqual(
            typed.semantic_outcome,
            ExecutionOutcome.SUCCESS,
        )
        self.assertTrue(
            service_accepts(typed)
        )


    def test_completed_unknown_remains_compatibility_accepted(self):
        typed = make_result(
            ExecutionOutcome.UNKNOWN
        )

        self.assertNotEqual(
            typed.semantic_outcome,
            ExecutionOutcome.SUCCESS,
        )
        self.assertTrue(
            service_accepts(typed)
        )


    def test_completed_error_is_not_service_accepted(self):
        self.assertFalse(
            service_accepts(
                make_result(
                    ExecutionOutcome.ERROR
                )
            )
        )


    # Transport state has precedence.

    def test_failed_transport_rejects_even_success_outcome(self):
        typed = make_result(
            ExecutionOutcome.SUCCESS,
            transport=ExecutionTransportState.FAILED,
        )

        self.assertFalse(
            service_accepts(typed)
        )


    def test_failed_transport_rejects_every_semantic_outcome(self):
        for outcome in ExecutionOutcome:
            with self.subTest(outcome=outcome.value):
                typed = make_result(
                    outcome,
                    transport=ExecutionTransportState.FAILED,
                )

                self.assertFalse(
                    service_accepts(typed)
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
