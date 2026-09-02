import unittest

from app.orchestrator.execution_contracts import (
    EXECUTION_CONTRACT_VERSION,
    ExecutionOutcome,
    ExecutionRequest,
    ExecutionResult,
    ExecutionTransportState,
    FallbackPolicy,
    SpecialistContract,
)


class ExecutionContractsV1Tests(unittest.TestCase):
    def test_contract_version_is_frozen_b2e_version(self):
        self.assertEqual(
            EXECUTION_CONTRACT_VERSION,
            "promati.phase_b2e.execution_contract.v1",
        )

    def test_transport_states_are_exact(self):
        self.assertEqual(
            {item.value for item in ExecutionTransportState},
            {
                "NOT_ATTEMPTED",
                "COMPLETED",
                "FAILED",
            },
        )

    def test_semantic_outcomes_are_exact(self):
        self.assertEqual(
            {item.value for item in ExecutionOutcome},
            {
                "SUCCESS",
                "CLARIFICATION_REQUIRED",
                "AMBIGUOUS",
                "CONTEXT_CONFLICT",
                "NOT_FOUND",
                "UNAVAILABLE",
                "REDIRECT",
                "ERROR",
                "UNKNOWN",
            },
        )

    def test_fallback_policies_are_exact(self):
        self.assertEqual(
            {item.value for item in FallbackPolicy},
            {
                "DISABLED",
                "EXPLICIT",
                "UNRESOLVED",
            },
        )

    def test_types_are_constructible_without_runtime_services(self):
        request = ExecutionRequest(
            contract_version=EXECUTION_CONTRACT_VERSION,
            step_id="step_test",
            domain="technical",
            action="technical_assistant",
            endpoint="/technical/assistant/ask",
            params={"vraag": "test"},
            required=True,
            timeout_seconds=30.0,
            retry_count=0,
            fallback_policy=FallbackPolicy.UNRESOLVED,
            legacy_fallback_allowed=True,
        )

        self.assertEqual(
            request.action,
            "technical_assistant",
        )

        self.assertTrue(
            hasattr(ExecutionResult, "__dataclass_fields__")
        )

        self.assertTrue(
            hasattr(SpecialistContract, "__dataclass_fields__")
        )


if __name__ == "__main__":
    unittest.main()