from __future__ import annotations

import unittest

from app.orchestrator.understanding import understand_query
from app.orchestrator.planner import build_execution_plan


def entity_value(plan, name):
    entity = plan.entities.get(name)

    if entity is None:
        return None

    return getattr(entity, "value", None)


class OrchestratorGoldenTests(unittest.TestCase):

    def test_bb_u1800(self):
        plan = understand_query("BB U1800")

        self.assertEqual(plan.primary_domain.value, "product")
        self.assertEqual(plan.intent, "product_lookup")
        self.assertEqual(entity_value(plan, "family_code"), "BB-U")
        self.assertEqual(entity_value(plan, "belt_width_mm"), 1800)
        self.assertIsNone(entity_value(plan, "band_code"))
        self.assertFalse(plan.clarification_required)

    def test_bb_u1800_inventory(self):
        plan = understand_query(
            "Heb je een U voor 1800 op voorraad?"
        )

        self.assertEqual(plan.primary_domain.value, "product")
        self.assertEqual(plan.intent, "inventory_lookup")
        self.assertEqual(entity_value(plan, "family_code"), "BB-U")
        self.assertEqual(entity_value(plan, "belt_width_mm"), 1800)
        self.assertIsNone(entity_value(plan, "band_code"))
        self.assertFalse(plan.clarification_required)

    def test_bb_u1800_advantages(self):
        plan = understand_query(
            "Wat zijn de voordelen van een U 1800?"
        )

        self.assertEqual(plan.primary_domain.value, "product")
        self.assertEqual(
            plan.intent,
            "advantages_disadvantages",
        )
        self.assertEqual(entity_value(plan, "family_code"), "BB-U")
        self.assertEqual(entity_value(plan, "belt_width_mm"), 1800)
        self.assertIsNone(entity_value(plan, "band_code"))
        self.assertFalse(plan.clarification_required)

    def test_tph_hd_does_not_create_false_band_code(self):
        plan = understand_query("TPH HD 750 PUR")

        self.assertEqual(plan.primary_domain.value, "product")
        self.assertEqual(plan.intent, "product_lookup")
        self.assertEqual(
            entity_value(plan, "family_code"),
            "PROM-TPH-HD",
        )
        self.assertIsNone(
            entity_value(plan, "belt_width_mm")
        )
        self.assertIsNone(
            entity_value(plan, "band_code")
        )

    def test_tph_explicit_width(self):
        plan = understand_query(
            "TPH HD bandbreedte 750 PUR"
        )

        self.assertEqual(plan.primary_domain.value, "product")
        self.assertEqual(
            entity_value(plan, "family_code"),
            "PROM-TPH-HD",
        )
        self.assertEqual(
            entity_value(plan, "belt_width_mm"),
            750,
        )
        self.assertIsNone(
            entity_value(plan, "band_code")
        )

    def test_explicit_band_code_still_wins(self):
        plan = understand_query(
            "TPH HD op band HD750"
        )

        self.assertEqual(plan.primary_domain.value, "product")
        self.assertEqual(
            entity_value(plan, "family_code"),
            "PROM-TPH-HD",
        )
        self.assertEqual(
            entity_value(plan, "band_code"),
            "HD750",
        )

    def test_inspection_lookup_handoff(self):
        question = "Hoe staat B12 ervoor?"

        plan = understand_query(question)
        plan = build_execution_plan(plan)

        self.assertEqual(
            plan.primary_domain.value,
            "inspection",
        )
        self.assertEqual(plan.intent, "inspection_lookup")
        self.assertEqual(
            entity_value(plan, "band_code"),
            "B12",
        )
        self.assertEqual(len(plan.execution_steps), 1)
        self.assertEqual(
            plan.execution_steps[0].action,
            "analysis_assistant",
        )
        self.assertEqual(
            plan.execution_steps[0].params["vraag"],
            "inspectieoverzicht van band B12",
        )
        self.assertEqual(
            plan.original_question,
            question,
        )

    def test_inspection_latest_handoff(self):
        question = "Wat was er vorige keer mis met B12?"

        plan = understand_query(question)
        plan = build_execution_plan(plan)

        self.assertEqual(
            plan.primary_domain.value,
            "inspection",
        )
        self.assertEqual(plan.intent, "inspection_latest")
        self.assertEqual(
            entity_value(plan, "band_code"),
            "B12",
        )
        self.assertEqual(
            plan.execution_steps[0].params["vraag"],
            "laatste inspecties van band B12",
        )
        self.assertEqual(
            plan.original_question,
            question,
        )

    def test_inspection_trend_handoff(self):
        question = "Hoe ontwikkelt de slijtage op B12?"

        plan = understand_query(question)
        plan = build_execution_plan(plan)

        self.assertEqual(
            plan.primary_domain.value,
            "inspection",
        )
        self.assertEqual(plan.intent, "inspection_trend")
        self.assertEqual(
            entity_value(plan, "band_code"),
            "B12",
        )
        self.assertEqual(
            plan.execution_steps[0].params["vraag"],
            "toon de trend van band B12",
        )
        self.assertEqual(
            plan.original_question,
            question,
        )

    def test_maintenance_priority_handoff(self):
        question = (
            "Wat heeft prioriteit qua onderhoud op B12?"
        )

        plan = understand_query(question)
        plan = build_execution_plan(plan)

        self.assertEqual(
            plan.primary_domain.value,
            "inspection",
        )
        self.assertEqual(
            plan.intent,
            "maintenance_priority",
        )
        self.assertEqual(
            entity_value(plan, "band_code"),
            "B12",
        )
        self.assertEqual(
            plan.execution_steps[0].params["vraag"],
            "onderhoudsplanning voor band B12",
        )
        self.assertEqual(
            plan.original_question,
            question,
        )

    def test_unknown_question_requires_clarification(self):
        plan = understand_query(
            "Kun je daar iets over vertellen?"
        )
        plan = build_execution_plan(plan)

        self.assertIsNone(plan.primary_domain)
        self.assertEqual(plan.intent, "unknown")
        self.assertTrue(plan.clarification_required)
        self.assertEqual(len(plan.execution_steps), 0)


if __name__ == "__main__":
    unittest.main()