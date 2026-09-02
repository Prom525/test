import unittest

from app.routers.hybrid_api import _detect_org_mode


class OrgGoldenTests(unittest.TestCase):

    def test_location_question_routes_to_location_info(self):
        self.assertEqual(
            _detect_org_mode(
                "Wat is het adres van de vestiging in Breda?"
            ),
            "location_info",
        )

    def test_responsibility_question_routes_to_function_info(self):
        self.assertEqual(
            _detect_org_mode(
                "Wie is verantwoordelijk voor IT?"
            ),
            "function_info",
        )

    def test_wifi_question_routes_to_internal_help(self):
        self.assertEqual(
            _detect_org_mode(
                "Mijn wifi werkt niet"
            ),
            "internal_help",
        )

    def test_procedure_question_routes_to_procedure(self):
        self.assertEqual(
            _detect_org_mode(
                "Wat is de procedure voor een incidentmelding?"
            ),
            "procedure",
        )

    def test_explicit_mode_wins_over_auto_detection(self):
        self.assertEqual(
            _detect_org_mode(
                "Wat is het adres?",
                "function_info",
            ),
            "function_info",
        )


if __name__ == "__main__":
    unittest.main()
