import unittest

from app.orchestrator.models import Domain
from app.orchestrator.planner import build_execution_plan
from app.orchestrator.understanding import understand_query


class OrchestratorTechnicalOrgRoutingTests(unittest.TestCase):

    def test_cema_routes_to_technical_assistant(self):
        question = "wat is CEMA"

        plan = understand_query(question)
        plan = build_execution_plan(plan)

        self.assertEqual(
            plan.primary_domain,
            Domain.TECHNICAL,
        )
        self.assertEqual(
            plan.intent,
            "technical_lookup",
        )
        self.assertFalse(
            plan.clarification_required,
        )
        self.assertEqual(
            len(plan.execution_steps),
            1,
        )

        step = plan.execution_steps[0]

        self.assertEqual(
            step.domain,
            Domain.TECHNICAL,
        )
        self.assertEqual(
            step.action,
            "technical_assistant",
        )
        self.assertEqual(
            step.params["vraag"],
            question,
        )

    def test_promati_location_routes_to_org_assistant(self):
        question = "waar is Promati gevestigd"

        plan = understand_query(question)
        plan = build_execution_plan(plan)

        self.assertEqual(
            plan.primary_domain,
            Domain.ORG,
        )
        self.assertEqual(
            plan.intent,
            "org_lookup",
        )
        self.assertFalse(
            plan.clarification_required,
        )
        self.assertEqual(
            len(plan.execution_steps),
            1,
        )

        step = plan.execution_steps[0]

        self.assertEqual(
            step.domain,
            Domain.ORG,
        )
        self.assertEqual(
            step.action,
            "org_assistant",
        )
        self.assertEqual(
            step.params["vraag"],
            question,
        )
        self.assertEqual(
            step.params["mode"],
            "auto",
        )

    def test_it_responsibility_routes_to_org_without_guessing(self):
        question = "wie is verantwoordelijk voor IT"

        plan = understand_query(question)
        plan = build_execution_plan(plan)

        self.assertEqual(
            plan.primary_domain,
            Domain.ORG,
        )
        self.assertEqual(
            plan.intent,
            "org_lookup",
        )
        self.assertFalse(
            plan.clarification_required,
        )
        self.assertEqual(
            len(plan.execution_steps),
            1,
        )

        step = plan.execution_steps[0]

        self.assertEqual(
            step.action,
            "org_assistant",
        )
        self.assertEqual(
            step.params["vraag"],
            question,
        )

        # De orchestrator routeert alleen.
        # Hij verzint geen persoon, functie of afdeling.
        self.assertNotIn(
            "person_name",
            step.params,
        )
        self.assertNotIn(
            "functie_code",
            step.params,
        )
        self.assertNotIn(
            "afdeling",
            step.params,
        )

    def test_product_routing_remains_product(self):
        question = "wat zijn de voordelen van BB-U1800"

        plan = understand_query(question)
        plan = build_execution_plan(plan)

        self.assertEqual(
            plan.primary_domain,
            Domain.PRODUCT,
        )
        self.assertEqual(
            len(plan.execution_steps),
            1,
        )
        self.assertEqual(
            plan.execution_steps[0].action,
            "product_assistant",
        )

    def test_inspection_routing_remains_inspection(self):
        question = "hoe staat band B12 ervoor"

        plan = understand_query(question)
        plan = build_execution_plan(plan)

        self.assertEqual(
            plan.primary_domain,
            Domain.INSPECTION,
        )
        self.assertEqual(
            len(plan.execution_steps),
            1,
        )
        self.assertEqual(
            plan.execution_steps[0].action,
            "analysis_assistant",
        )

    def test_unknown_question_still_requires_clarification(self):
        question = "kun je daar iets over vertellen?"

        plan = understand_query(question)
        plan = build_execution_plan(plan)

        self.assertIsNone(
            plan.primary_domain,
        )
        self.assertEqual(
            plan.intent,
            "unknown",
        )
        self.assertTrue(
            plan.clarification_required,
        )
        self.assertEqual(
            len(plan.execution_steps),
            0,
        )


if __name__ == "__main__":
    unittest.main()
