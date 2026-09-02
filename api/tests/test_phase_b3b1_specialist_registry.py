import unittest

from app.orchestrator.execution_contracts import (
    ExecutionOutcome,
    FallbackPolicy,
)
from app.orchestrator.specialist_registry import (
    EXPECTED_SPECIALIST_ACTIONS,
    SPECIALIST_CONTRACTS,
    get_specialist_contract,
)


class SpecialistRegistryV1Tests(unittest.TestCase):
    def test_exact_six_specialists(self):
        self.assertEqual(
            set(SPECIALIST_CONTRACTS),
            set(EXPECTED_SPECIALIST_ACTIONS),
        )

        self.assertEqual(
            len(SPECIALIST_CONTRACTS),
            6,
        )

    def test_endpoints_are_exact(self):
        expected = {
            "product_assistant": "/product/assistant/ask",
            "analysis_assistant": "/analysis/assistant/ask",
            "technical_assistant": "/technical/assistant/ask",
            "rfq_assistant": "/rfq/assistant/ask",
            "org_assistant": "/org/assistant/ask",
            "diagnostics_assistant": "/diagnostics/assistant/ask",
        }

        actual = {
            action: contract.endpoint
            for action, contract in SPECIALIST_CONTRACTS.items()
        }

        self.assertEqual(
            actual,
            expected,
        )

    def test_analysis_mode_gap_is_preserved_not_fixed(self):
        contract = get_specialist_contract(
            "analysis_assistant"
        )

        self.assertIsNotNone(contract)

        self.assertNotIn(
            "mode",
            contract.accepted_input_fields,
        )

        self.assertIn(
            "mode",
            contract.planner_fields,
        )

        self.assertIn(
            "mode",
            contract.research_fields,
        )

    def test_rfq_planner_intent_remains_unresolved(self):
        contract = get_specialist_contract(
            "rfq_assistant"
        )

        self.assertIsNotNone(contract)

        self.assertEqual(
            contract.direct_planner,
            "NO_UNRESOLVED_INTENT",
        )

        self.assertEqual(
            contract.planner_fields,
            (),
        )

    def test_fallback_policy_is_not_invented(self):
        for contract in SPECIALIST_CONTRACTS.values():
            self.assertEqual(
                contract.fallback_policy,
                FallbackPolicy.UNRESOLVED,
            )

    def test_known_status_maps_match_design(self):
        analysis = SPECIALIST_CONTRACTS[
            "analysis_assistant"
        ]

        self.assertEqual(
            analysis.status_map["clarification_required"],
            ExecutionOutcome.CLARIFICATION_REQUIRED,
        )

        technical = SPECIALIST_CONTRACTS[
            "technical_assistant"
        ]

        self.assertEqual(
            technical.status_map["redirect"],
            ExecutionOutcome.REDIRECT,
        )


if __name__ == "__main__":
    unittest.main()