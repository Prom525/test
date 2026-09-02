import unittest

from app.orchestrator.execution_contracts import (
    EXECUTION_CONTRACT_VERSION,
    ExecutionOutcome,
    ExecutionRequest,
    ExecutionTransportState,
    FallbackPolicy,
)
from app.orchestrator.execution_shadow import (
    derive_execution_result,
    derive_semantic_outcome,
)


class ExecutionShadowV1Tests(unittest.TestCase):
    def test_success_statuses(self):
        self.assertEqual(
            derive_semantic_outcome(
                "product_assistant",
                {"status": "ok"},
            ),
            ExecutionOutcome.SUCCESS,
        )

        self.assertEqual(
            derive_semantic_outcome(
                "analysis_assistant",
                {"status": "resolved"},
            ),
            ExecutionOutcome.SUCCESS,
        )

    def test_non_success_semantic_statuses_are_not_flattened(self):
        expected = {
            "clarification_required":
                ExecutionOutcome.CLARIFICATION_REQUIRED,
            "ambiguous":
                ExecutionOutcome.AMBIGUOUS,
            "context_conflict":
                ExecutionOutcome.CONTEXT_CONFLICT,
            "not_found":
                ExecutionOutcome.NOT_FOUND,
            "unavailable":
                ExecutionOutcome.UNAVAILABLE,
        }

        for status, outcome in expected.items():
            with self.subTest(status=status):
                self.assertEqual(
                    derive_semantic_outcome(
                        "analysis_assistant",
                        {"status": status},
                    ),
                    outcome,
                )

    def test_redirect_is_separate_outcome(self):
        self.assertEqual(
            derive_semantic_outcome(
                "technical_assistant",
                {"status": "redirect"},
            ),
            ExecutionOutcome.REDIRECT,
        )

    def test_error_statuses_map_to_error(self):
        for status in (
            "error",
            "failed",
            "failure",
        ):
            with self.subTest(status=status):
                self.assertEqual(
                    derive_semantic_outcome(
                        "product_assistant",
                        {"status": status},
                    ),
                    ExecutionOutcome.ERROR,
                )

    def test_missing_unrecognized_and_unknown_action_are_unknown(self):
        self.assertEqual(
            derive_semantic_outcome(
                "product_assistant",
                {},
            ),
            ExecutionOutcome.UNKNOWN,
        )

        self.assertEqual(
            derive_semantic_outcome(
                "product_assistant",
                {"status": "something_new"},
            ),
            ExecutionOutcome.UNKNOWN,
        )

        self.assertEqual(
            derive_semantic_outcome(
                "unknown_assistant",
                {"status": "ok"},
            ),
            ExecutionOutcome.UNKNOWN,
        )

    def test_legacy_accepted_is_preserved_independently(self):
        request = ExecutionRequest(
            contract_version=EXECUTION_CONTRACT_VERSION,
            step_id="step_shadow",
            domain="inspection",
            action="analysis_assistant",
            endpoint="/analysis/assistant/ask",
            params={"vraag": "test"},
            required=True,
            timeout_seconds=30.0,
            retry_count=0,
            fallback_policy=FallbackPolicy.UNRESOLVED,
            legacy_fallback_allowed=True,
        )

        result = derive_execution_result(
            request=request,
            raw_result={
                "status": "clarification_required",
                "message": "meer informatie nodig",
            },
            legacy_accepted=True,
        )

        self.assertTrue(
            result.legacy_accepted
        )

        self.assertEqual(
            result.semantic_outcome,
            ExecutionOutcome.CLARIFICATION_REQUIRED,
        )

        self.assertEqual(
            result.transport_state,
            ExecutionTransportState.COMPLETED,
        )

    def test_shadow_derivation_copies_raw_result(self):
        request = ExecutionRequest(
            contract_version=EXECUTION_CONTRACT_VERSION,
            step_id="step_copy",
            domain="product",
            action="product_assistant",
            endpoint="/product/assistant/ask",
            params={"vraag": "test"},
            required=True,
            timeout_seconds=30.0,
            retry_count=0,
            fallback_policy=FallbackPolicy.UNRESOLVED,
            legacy_fallback_allowed=True,
        )

        raw = {
            "status": "ok",
            "value": 1,
        }

        typed = derive_execution_result(
            request=request,
            raw_result=raw,
            legacy_accepted=True,
        )

        self.assertEqual(
            typed.result,
            raw,
        )

        self.assertIsNot(
            typed.result,
            raw,
        )


if __name__ == "__main__":
    unittest.main()