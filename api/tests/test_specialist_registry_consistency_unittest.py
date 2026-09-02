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


from app.orchestrator.research_agent import (  # noqa: E402
    ALLOWED_RESEARCH_ACTIONS,
    _ACTION_DEFAULTS,
)
from app.orchestrator.specialist_registry import (  # noqa: E402
    EXPECTED_SPECIALIST_ACTIONS,
    SPECIALIST_CONTRACTS,
)


class SpecialistRegistryConsistencyTests(
    unittest.TestCase
):

    def test_expected_actions_match_registry(self):
        self.assertEqual(
            set(EXPECTED_SPECIALIST_ACTIONS),
            set(SPECIALIST_CONTRACTS),
        )


    def test_required_fields_are_accepted(self):
        for action, contract in SPECIALIST_CONTRACTS.items():
            with self.subTest(action=action):
                self.assertTrue(
                    set(contract.required_fields)
                    <= set(contract.accepted_input_fields)
                )


    def test_planner_fields_are_accepted(self):
        for action, contract in SPECIALIST_CONTRACTS.items():
            with self.subTest(action=action):
                self.assertTrue(
                    set(contract.planner_fields)
                    <= set(contract.accepted_input_fields)
                )


    def test_research_fields_are_accepted(self):
        for action, contract in SPECIALIST_CONTRACTS.items():
            with self.subTest(action=action):
                self.assertTrue(
                    set(contract.research_fields)
                    <= set(contract.accepted_input_fields)
                )


    def test_research_action_sets_match_registry(self):
        self.assertEqual(
            set(ALLOWED_RESEARCH_ACTIONS),
            set(SPECIALIST_CONTRACTS),
        )


    def test_research_allowlists_match_registry_contract(self):
        for action, allowed in ALLOWED_RESEARCH_ACTIONS.items():
            with self.subTest(action=action):
                contract = SPECIALIST_CONTRACTS[action]

                self.assertEqual(
                    set(allowed),
                    set(contract.research_fields),
                )


    def test_research_defaults_are_declared_research_fields(self):
        for action, defaults in _ACTION_DEFAULTS.items():
            with self.subTest(action=action):
                contract = SPECIALIST_CONTRACTS[action]

                self.assertTrue(
                    set(defaults)
                    <= set(contract.research_fields)
                )


    def test_field_declarations_have_no_duplicates(self):
        field_names = (
            "required_fields",
            "accepted_input_fields",
            "planner_fields",
            "research_fields",
        )

        for action, contract in SPECIALIST_CONTRACTS.items():
            for field_name in field_names:
                with self.subTest(
                    action=action,
                    field=field_name,
                ):
                    values = tuple(
                        getattr(
                            contract,
                            field_name,
                        )
                    )

                    self.assertEqual(
                        len(values),
                        len(set(values)),
                    )


    def test_analysis_mode_is_accepted_input(self):
        contract = SPECIALIST_CONTRACTS[
            "analysis_assistant"
        ]

        self.assertIn(
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

        self.assertIn(
            "mode",
            ALLOWED_RESEARCH_ACTIONS[
                "analysis_assistant"
            ],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
