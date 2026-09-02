import unittest

from app.orchestrator.models import OrchestratorAskRequest
from app.orchestrator.service import run_orchestrator


class OrchestratorUserAnswerTests(unittest.TestCase):

    def test_resolved_asset_answer_contains_full_context(self):
        def sender(path, payload):
            return {
                "intent": "inspection_summary",
                "kort_resultaat": (
                    "1681 inspectieregels gevonden."
                ),
                "asset_resolution": {
                    "status": "resolved",
                    "match_count": 1,
                },
                "asset_context": {
                    "customer_code": "TATA_STEEL",
                    "site_code": "IJMUIDEN",
                    "area_code": "GSL",
                    "area_name": "GSL",
                    "installation_code": "MV1",
                    "installation_name": "Mengveld 1",
                    "band_code_norm": "R5",
                    "band_code_display": "R 5",
                },
                "resultaat": [
                    {"example": "raw-detail"}
                ],
            }

        response = run_orchestrator(
            OrchestratorAskRequest(
                vraag="laatste meshoogte van band R5"
            ),
            sender=sender,
        )

        answer = response["answer"]

        self.assertIn(
            "Klant: TATA_STEEL",
            answer,
        )
        self.assertIn(
            "Plaats: IJMUIDEN",
            answer,
        )
        self.assertIn(
            "Gebied: GSL",
            answer,
        )
        self.assertIn(
            "Installatie: Mengveld 1 (MV1)",
            answer,
        )
        self.assertIn(
            "Bandnummer: R 5",
            answer,
        )
        self.assertIn(
            "1681 inspectieregels gevonden.",
            answer,
        )

        # Ruwe specialistdata blijft intact.
        self.assertEqual(
            response["results"][0]["result"]["resultaat"],
            [{"example": "raw-detail"}],
        )

    def test_maintenance_answer_uses_kort_resultaat(self):
        def sender(path, payload):
            return {
                "intent": "maintenance_positions",
                "kort_resultaat": (
                    "3 onderhoudsposities gevonden."
                ),
                "asset_resolution": {
                    "status": "resolved",
                    "match_count": 1,
                },
                "asset_context": {
                    "customer_code": "TATA_STEEL",
                    "site_code": "IJMUIDEN",
                    "area_code": "GSL",
                    "area_name": "GSL",
                    "installation_code": "MV2",
                    "installation_name": "Mengveld 2",
                    "band_code_norm": "E401",
                    "band_code_display": "E401",
                },
                "trend_patronen": [
                    "Prioriteit 2: 1",
                ],
            }

        response = run_orchestrator(
            OrchestratorAskRequest(
                vraag="onderhoud van band E401"
            ),
            sender=sender,
        )

        answer = response["answer"]

        self.assertIn(
            "Klant: TATA_STEEL",
            answer,
        )
        self.assertIn(
            "Installatie: Mengveld 2 (MV2)",
            answer,
        )
        self.assertIn(
            "Bandnummer: E401",
            answer,
        )
        self.assertIn(
            "3 onderhoudsposities gevonden.",
            answer,
        )

        self.assertEqual(
            response["results"][0]["result"]["trend_patronen"],
            ["Prioriteit 2: 1"],
        )

    def test_conflict_answer_uses_message_and_canonical_context(self):
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
                "asset_context": {
                    "customer_code": "TATA_STEEL",
                    "site_code": "IJMUIDEN",
                    "area_code": "GSL",
                    "area_name": "GSL",
                    "installation_code": "MV1",
                    "installation_name": "Mengveld 1",
                    "band_code_norm": "R5",
                    "band_code_display": "R 5",
                },
            }

        response = run_orchestrator(
            OrchestratorAskRequest(
                vraag="laatste meshoogte van band R5"
            ),
            sender=sender,
        )

        answer = response["answer"]

        self.assertEqual(
            response["status"],
            "clarification_required",
        )
        self.assertIn(
            "Installatie: Mengveld 1 (MV1)",
            answer,
        )
        self.assertIn(
            "Bandnummer: R 5",
            answer,
        )
        self.assertIn(
            "komt niet overeen met de gevonden band",
            answer,
        )

    def test_not_found_answer_keeps_requested_band_and_unknown_context(self):
        def sender(path, payload):
            return {
                "intent": "inspection_summary",
                "kort_resultaat": (
                    "Geen inspectieregels gevonden."
                ),
                "asset_resolution": {
                    "status": "not_found",
                    "match_count": 0,
                },
                "asset_context": None,
                "entities": {
                    "band_code": "ZZ999",
                },
                "resultaat": [],
            }

        response = run_orchestrator(
            OrchestratorAskRequest(
                vraag="toon band ZZ999"
            ),
            sender=sender,
        )

        answer = response["answer"]

        self.assertIn(
            "Klant: onbekend",
            answer,
        )
        self.assertIn(
            "Plaats: onbekend",
            answer,
        )
        self.assertIn(
            "Gebied: onbekend",
            answer,
        )
        self.assertIn(
            "Installatie: onbekend",
            answer,
        )
        self.assertIn(
            "Bandnummer: ZZ999",
            answer,
        )
        self.assertIn(
            "Geen inspectieregels gevonden.",
            answer,
        )

        self.assertEqual(
            response["status"],
            "ok",
        )

    def test_non_asset_result_is_not_given_fake_asset_context(self):
        def sender(path, payload):
            return {
                "status": "ok",
                "result": "product-result",
            }

        response = run_orchestrator(
            OrchestratorAskRequest(
                vraag="wat zijn de voordelen van BB-U1800"
            ),
            sender=sender,
        )

        answer = response.get("answer")

        if answer is not None:
            self.assertNotIn(
                "Klant: onbekend",
                answer,
            )
            self.assertNotIn(
                "Bandnummer: onbekend",
                answer,
            )


if __name__ == "__main__":
    unittest.main()
