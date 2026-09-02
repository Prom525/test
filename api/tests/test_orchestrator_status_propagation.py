import unittest

from app.orchestrator.models import OrchestratorAskRequest
from app.orchestrator.service import run_orchestrator


class OrchestratorStatusPropagationTests(unittest.TestCase):

    def test_specialist_clarification_is_promoted_to_top_level(self):
        def sender(path, payload):
            return {
                "intent": "asset_clarification",
                "status": "clarification_required",
                "message": (
                    "De opgegeven installatie of het gebied "
                    "komt niet overeen met de gevonden band."
                ),
                "asset_resolution": {
                    "status": "context_conflict",
                    "match_count": 1,
                },
            }

        response = run_orchestrator(
            OrchestratorAskRequest(
                vraag="laatste meshoogte van band R5"
            ),
            sender=sender,
        )

        self.assertEqual(
            response["status"],
            "clarification_required",
        )
        self.assertTrue(
            response["clarification"]["required"]
        )
        self.assertEqual(
            response["clarification"]["question"],
            (
                "De opgegeven installatie of het gebied "
                "komt niet overeen met de gevonden band."
            ),
        )

        # Specialistresultaat blijft geldig/accepted.
        self.assertTrue(
            response["results"][0]["accepted"]
        )

    def test_not_found_result_remains_normal_orchestrator_result(self):
        def sender(path, payload):
            return {
                "intent": "inspection_summary",
                "asset_resolution": {
                    "status": "not_found",
                    "match_count": 0,
                },
                "rows": [],
            }

        response = run_orchestrator(
            OrchestratorAskRequest(
                vraag="toon band ZZ999"
            ),
            sender=sender,
        )

        self.assertEqual(
            response["status"],
            "ok",
        )
        self.assertFalse(
            response["clarification"]["required"]
        )
        self.assertTrue(
            response["results"][0]["accepted"]
        )

    def test_normal_specialist_result_remains_ok(self):
        def sender(path, payload):
            return {
                "intent": "inspection_summary",
                "rows": [{"band_code": "R5"}],
            }

        response = run_orchestrator(
            OrchestratorAskRequest(
                vraag="toon band R5"
            ),
            sender=sender,
        )

        self.assertEqual(
            response["status"],
            "ok",
        )
        self.assertFalse(
            response["clarification"]["required"]
        )

    def test_plan_level_clarification_still_wins(self):
        calls = []

        def sender(path, payload):
            calls.append((path, payload))
            return {"status": "ok"}

        response = run_orchestrator(
            OrchestratorAskRequest(
                vraag="vertel me iets"
            ),
            sender=sender,
        )

        self.assertEqual(
            response["status"],
            "clarification_required",
        )
        self.assertTrue(
            response["clarification"]["required"]
        )
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
