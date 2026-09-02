from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT),
    )


from app.orchestrator.execution_contracts import (  # noqa: E402
    EXECUTION_CONTRACT_VERSION,
    ExecutionOutcome,
    ExecutionRequest,
    FallbackPolicy,
)
from app.orchestrator.execution_shadow import (  # noqa: E402
    derive_execution_result,
    derive_semantic_outcome,
)


class AnalysisExecutionContractTests(
    unittest.TestCase
):
    def test_statusless_analysis_success_is_success(
        self,
    ):
        outcome = derive_semantic_outcome(
            "analysis_assistant",
            {
                "intent": "band_deep_analysis",
                "kort_resultaat": "ok",
            },
        )

        self.assertEqual(
            outcome,
            ExecutionOutcome.SUCCESS,
        )


    def test_statusless_inspection_summary_is_success(
        self,
    ):
        outcome = derive_semantic_outcome(
            "analysis_assistant",
            {
                "intent": "inspection_summary",
                "resultaat": [],
            },
        )

        self.assertEqual(
            outcome,
            ExecutionOutcome.SUCCESS,
        )


    def test_statusless_lifecycle_is_success(
        self,
    ):
        outcome = derive_semantic_outcome(
            "analysis_assistant",
            {
                "intent": "lifecycle",
                "resultaat": [],
            },
        )

        self.assertEqual(
            outcome,
            ExecutionOutcome.SUCCESS,
        )


    def test_resolved_is_success(
        self,
    ):
        self.assertEqual(
            derive_semantic_outcome(
                "analysis_assistant",
                {"status": "resolved"},
            ),
            ExecutionOutcome.SUCCESS,
        )


    def test_clarification_is_not_success(
        self,
    ):
        self.assertEqual(
            derive_semantic_outcome(
                "analysis_assistant",
                {
                    "status": (
                        "clarification_required"
                    )
                },
            ),
            (
                ExecutionOutcome
                .CLARIFICATION_REQUIRED
            ),
        )


    def test_ambiguous_is_ambiguous(
        self,
    ):
        self.assertEqual(
            derive_semantic_outcome(
                "analysis_assistant",
                {"status": "ambiguous"},
            ),
            ExecutionOutcome.AMBIGUOUS,
        )


    def test_not_found_is_not_found(
        self,
    ):
        self.assertEqual(
            derive_semantic_outcome(
                "analysis_assistant",
                {"status": "not_found"},
            ),
            ExecutionOutcome.NOT_FOUND,
        )


    def test_unavailable_is_unavailable(
        self,
    ):
        self.assertEqual(
            derive_semantic_outcome(
                "analysis_assistant",
                {"status": "unavailable"},
            ),
            ExecutionOutcome.UNAVAILABLE,
        )


    def test_error_uses_global_error_mapping(
        self,
    ):
        self.assertEqual(
            derive_semantic_outcome(
                "analysis_assistant",
                {"status": "error"},
            ),
            ExecutionOutcome.ERROR,
        )


    def test_unknown_explicit_status_stays_unknown(
        self,
    ):
        self.assertEqual(
            derive_semantic_outcome(
                "analysis_assistant",
                {
                    "status": (
                        "future_unknown_status"
                    )
                },
            ),
            ExecutionOutcome.UNKNOWN,
        )


    def test_missing_status_is_not_global_success_default(
        self,
    ):
        outcome = derive_semantic_outcome(
            "product_assistant",
            {
                "context_type": (
                    "product_assistant"
                )
            },
        )

        self.assertEqual(
            outcome,
            ExecutionOutcome.UNKNOWN,
        )


    def test_execution_result_keeps_legacy_and_typed_semantics(
        self,
    ):
        request = ExecutionRequest(
            contract_version=(
                EXECUTION_CONTRACT_VERSION
            ),
            step_id="step_1_inspection",
            domain="inspection",
            action="analysis_assistant",
            endpoint="/analysis/assistant/ask",
            params={
                "vraag": (
                    "vervangadvies voor band A660"
                )
            },
            required=True,
            timeout_seconds=30.0,
            retry_count=0,
            fallback_policy=(
                FallbackPolicy.UNRESOLVED
            ),
            legacy_fallback_allowed=True,
        )

        execution_result = (
            derive_execution_result(
                request=request,
                raw_result={
                    "intent": (
                        "band_deep_analysis"
                    )
                },
                legacy_accepted=True,
            )
        )

        self.assertTrue(
            execution_result.legacy_accepted
        )

        self.assertEqual(
            execution_result.semantic_outcome,
            ExecutionOutcome.SUCCESS,
        )

        self.assertIsNone(
            execution_result.specialist_status
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
