import unittest

from app.orchestrator.models import Domain
from app.orchestrator.planner import build_execution_plan
from app.orchestrator.understanding import understand_query


class ExplicitBandRoutingTests(unittest.TestCase):

    def _plan(self, question):
        plan = understand_query(question)
        return build_execution_plan(plan)

    def test_explicit_unknown_band_routes_to_inspection_lookup(self):
        plan = self._plan("toon band ZZ999")

        self.assertEqual(
            plan.primary_domain,
            Domain.INSPECTION,
        )
        self.assertEqual(
            plan.intent,
            "inspection_lookup",
        )
        self.assertFalse(
            plan.clarification_required
        )

        self.assertEqual(
            len(plan.execution_steps),
            1,
        )

        step = plan.execution_steps[0]

        self.assertEqual(
            step.action,
            "analysis_assistant",
        )
        self.assertEqual(
            step.params["band_code"],
            "ZZ999",
        )
        self.assertEqual(
            step.params["vraag"],
            "inspectieoverzicht van band ZZ999",
        )

    def test_explicit_known_band_routes_to_inspection_lookup(self):
        plan = self._plan("toon band R5")

        self.assertEqual(
            plan.primary_domain,
            Domain.INSPECTION,
        )
        self.assertEqual(
            plan.intent,
            "inspection_lookup",
        )
        self.assertEqual(
            plan.execution_steps[0].params["band_code"],
            "R5",
        )

    def test_standalone_code_remains_conservative(self):
        plan = self._plan("ZZ999")

        self.assertTrue(
            plan.clarification_required
        )
        self.assertIsNone(
            plan.primary_domain
        )
        self.assertEqual(
            plan.execution_steps,
            [],
        )

    def test_product_term_does_not_force_inspection(self):
        plan = self._plan(
            "prijs van band ZZ999"
        )

        self.assertNotEqual(
            plan.primary_domain,
            Domain.INSPECTION,
        )


    def test_unknown_band_with_mv2_context_is_preserved(self):
        plan = self._plan(
            "toon band ZZ999 op MV2"
        )

        self.assertEqual(
            plan.primary_domain,
            Domain.INSPECTION,
        )
        self.assertEqual(
            plan.intent,
            "inspection_lookup",
        )

        step = plan.execution_steps[0]

        self.assertEqual(
            step.params["band_code"],
            "ZZ999",
        )
        self.assertEqual(
            step.params["lijn_code"],
            "MV2",
        )
        self.assertEqual(
            step.params["vraag"],
            "inspectieoverzicht van band ZZ999",
        )

    def test_unknown_band_with_gsl_context_is_preserved(self):
        plan = self._plan(
            "toon band ZZ999 op GSL"
        )

        self.assertEqual(
            plan.primary_domain,
            Domain.INSPECTION,
        )

        step = plan.execution_steps[0]

        self.assertEqual(
            step.params["band_code"],
            "ZZ999",
        )
        self.assertEqual(
            step.params["lijn_code"],
            "GSL",
        )

    def test_known_band_conflicting_context_reaches_analysis(self):
        plan = self._plan(
            "toon band R5 op MV2"
        )

        self.assertEqual(
            plan.primary_domain,
            Domain.INSPECTION,
        )
        self.assertEqual(
            plan.intent,
            "inspection_lookup",
        )

        step = plan.execution_steps[0]

        self.assertEqual(
            step.action,
            "analysis_assistant",
        )
        self.assertEqual(
            step.params["band_code"],
            "R5",
        )
        self.assertEqual(
            step.params["lijn_code"],
            "MV2",
        )


if __name__ == "__main__":
    unittest.main()
