import unittest

from app.orchestrator.planner import build_execution_plan
from app.orchestrator.understanding import (
    detect_line_code,
    understand_query,
)


class OrchestratorContextHintTests(unittest.TestCase):

    def _build_plan(self, question):
        plan = understand_query(question)
        return build_execution_plan(plan)

    def test_mv2_context_is_preserved_in_inspection_params(self):
        question = "laatste meshoogte van band R5 op MV2"

        plan = self._build_plan(question)

        self.assertEqual(len(plan.execution_steps), 1)

        params = plan.execution_steps[0].params

        self.assertEqual(
            params["vraag"],
            "laatste inspecties van band R5",
        )
        self.assertEqual(params["band_code"], "R5")
        self.assertEqual(params["lijn_code"], "MV2")
        self.assertEqual(plan.original_question, question)

    def test_gsl_context_is_preserved_in_inspection_params(self):
        question = "laatste meshoogte van band R5 op GSL"

        plan = self._build_plan(question)

        self.assertEqual(len(plan.execution_steps), 1)

        params = plan.execution_steps[0].params

        self.assertEqual(
            params["vraag"],
            "laatste inspecties van band R5",
        )
        self.assertEqual(params["band_code"], "R5")
        self.assertEqual(params["lijn_code"], "GSL")

    def test_hoo_asset_context_codes_are_detected(self):
        cases = {
            "laatste meshoogte band H601 op HOO6": "HOO6",
            "laatste meshoogte band AB70 op HOO7": "HOO7",
        }

        for question, expected in cases.items():
            with self.subTest(question=question):
                entity = detect_line_code(question.lower())

                self.assertIsNotNone(entity)
                self.assertEqual(entity.value, expected)
                self.assertEqual(
                    entity.source,
                    "explicit_context_code_pattern",
                )

    def test_named_installation_context_is_detected(self):
        cases = {
            "inspectie op BR1": "BR1",
            "inspectie op GROTE_KADE": "GROTE_KADE",
            "inspectie op MENGERIJ": "MENGERIJ",
            "inspectie op PELLET": "PELLET",
            "inspectie op SINTER": "SINTER",
        }

        for question, expected in cases.items():
            with self.subTest(question=question):
                entity = detect_line_code(question.lower())

                self.assertIsNotNone(entity)
                self.assertEqual(entity.value, expected)

    def test_normal_phrase_is_not_misclassified_as_context_code(self):
        entity = detect_line_code(
            "inspectie op morgen"
        )

        self.assertIsNone(entity)


if __name__ == "__main__":
    unittest.main()
