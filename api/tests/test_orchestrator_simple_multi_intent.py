import unittest

from app.orchestrator.models import OrchestratorAskRequest
from app.orchestrator.service import run_orchestrator
from app.orchestrator.understanding import understand_query


class OrchestratorSimpleMultiIntentTests(unittest.TestCase):

    QUESTION = (
        "Wat zijn de voordelen van de BB-U en wat is de "
        "voorraad voor 1800 mm?"
    )

    def test_requested_information_detects_strengths_and_inventory(self):
        plan = understand_query(self.QUESTION)

        self.assertEqual(plan.primary_domain.value, "product")
        self.assertIn("strengths", plan.requested_information)
        self.assertIn("inventory", plan.requested_information)
        self.assertFalse(plan.clarification_required)

    def test_answer_combines_family_strengths_and_structured_inventory(self):
        def sender(path, payload):
            self.assertEqual(path, "/product/assistant/ask")

            return {
                "status": "ok",
                "context_type": "product_assistant",
                "family_context": {
                    "status": "ok",
                    "count": 1,
                    "results": [
                        {
                            "family_name": "Belle Banne U",
                            "family_code": "BB-U",
                            "strengths": "Sterke secundaire reiniging.",
                            "limitations": "Niet bedoeld als primaire kopschraper.",
                            "selection_advice": "Gebruik als secundaire schraper.",
                        }
                    ],
                },
                "config_options": {
                    "status": "ok",
                    "count": 2,
                    "results": [
                        {
                            "family_code": "BB-U",
                            "belt_width_mm": 1800,
                            "component_group": "blade",
                            "option_value": "standaard",
                            "internal_ref": "ABUBL1800",
                            "product_name": "Belle Banne schraapmes U 1800",
                            "available_qty": 8,
                            "expected_qty": 7,
                            "uom": "Stuks",
                            "sale_price": 2630.0,
                        },
                        {
                            "family_code": "BB-U",
                            "belt_width_mm": 1800,
                            "component_group": "frame",
                            "option_value": "RVS",
                            "internal_ref": "ABUIFR1800",
                            "product_name": "Belle Banne RVS frame U 1800",
                            "available_qty": 2,
                            "expected_qty": 2,
                            "uom": "Stuks",
                            "sale_price": 2762.0,
                        },
                    ],
                },
                "rag_context": {
                    "antwoord": "RAG MAG GEEN VOORRAAD VERZINNEN"
                },
            }

        response = run_orchestrator(
            OrchestratorAskRequest(vraag=self.QUESTION),
            sender=sender,
        )

        answer = response["answer"]

        self.assertEqual(response["status"], "ok")
        self.assertIn("Sterke secundaire reiniging", answer)
        self.assertIn("Actuele artikelinformatie", answer)
        self.assertIn("ABUBL1800", answer)
        self.assertIn("voorraad: 8 Stuks", answer)
        self.assertIn("verwacht: 7 Stuks", answer)
        self.assertIn("ABUIFR1800", answer)
        self.assertIn("voorraad: 2 Stuks", answer)
        self.assertNotIn("RAG MAG GEEN VOORRAAD VERZINNEN", answer)


if __name__ == "__main__":
    unittest.main()