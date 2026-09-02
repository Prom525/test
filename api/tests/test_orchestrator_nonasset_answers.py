import unittest

from app.orchestrator.models import OrchestratorAskRequest
from app.orchestrator.service import run_orchestrator


class OrchestratorNonAssetAnswerTests(unittest.TestCase):

    def test_product_answer_uses_family_context_not_rag_marketing(self):
        def sender(path, payload):
            self.assertEqual(
                path,
                "/product/assistant/ask",
            )

            return {
                "status": "ok",
                "context_type": "product_assistant",
                "vraag": payload["vraag"],
                "family_context": {
                    "status": "ok",
                    "context_type": "product_family_context",
                    "count": 1,
                    "results": [
                        {
                            "family_name": "Belle Banne U",
                            "family_code": "BB-U",
                            "strengths": (
                                "Sterke secundaire reiniging; "
                                "hogere middendruk."
                            ),
                            "limitations": (
                                "Niet bedoeld als primaire "
                                "kopschraper."
                            ),
                            "selection_advice": (
                                "Gebruik als heavy-duty "
                                "secundaire schraper."
                            ),
                        }
                    ],
                },
                "rag_context": {
                    "antwoord": (
                        "MARKETING-RAG MAG NIET DE "
                        "PRIMAIRE ANTWOORDBRON ZIJN"
                    ),
                },
            }

        response = run_orchestrator(
            OrchestratorAskRequest(
                vraag="wat zijn de voordelen van BB-U1800"
            ),
            sender=sender,
        )

        answer = response["answer"]

        self.assertIsNotNone(answer)

        self.assertIn(
            "Belle Banne U",
            answer,
        )

        self.assertIn(
            "Sterke secundaire reiniging",
            answer,
        )

        self.assertIn(
            "Niet bedoeld als primaire kopschraper",
            answer,
        )

        self.assertNotIn(
            "MARKETING-RAG",
            answer,
        )

        self.assertNotIn(
            "Klant:",
            answer,
        )


    def test_org_location_answer_uses_structured_locations(self):
        def sender(path, payload):
            self.assertEqual(
                path,
                "/org/assistant/ask",
            )

            return {
                "status": "ok",
                "context_type": "org_assistant",
                "mode": "location_info",
                "vraag": payload["vraag"],
                "result": {
                    "status": "ok",
                    "firma": "Promati",
                    "locatie": None,
                    "results": [
                        {
                            "firma_naam": "Promati",
                            "locatie": "Algemeen",
                            "adres": None,
                            "plaats": None,
                            "land": "België",
                        },
                        {
                            "firma_naam": "Promati",
                            "locatie": "Breda",
                            "adres": (
                                "Nikkelstraat 45, "
                                "4823 AE Breda, Nederland"
                            ),
                            "plaats": "Breda",
                            "land": "Nederland",
                        },
                        {
                            "firma_naam": "Promati",
                            "locatie": "Maldegem",
                            "adres": (
                                "Ambachtenlaan 3, "
                                "9990 Maldegem, België"
                            ),
                            "plaats": "Maldegem",
                            "land": "België",
                        },
                    ],
                    "write_actions_available": False,
                },
                "write_actions_available": False,
            }

        response = run_orchestrator(
            OrchestratorAskRequest(
                vraag="waar is Promati gevestigd"
            ),
            sender=sender,
        )

        answer = response["answer"]

        self.assertIsNotNone(answer)

        self.assertIn(
            "Nikkelstraat 45, 4823 AE Breda, Nederland",
            answer,
        )

        self.assertIn(
            "Ambachtenlaan 3, 9990 Maldegem, België",
            answer,
        )

        self.assertNotIn(
            "Klant:",
            answer,
        )


    def test_org_not_found_answer_uses_specialist_message_without_guess(self):
        message = (
            "Geen persoon of functie herkend in deze vraag."
        )

        def sender(path, payload):
            self.assertEqual(
                path,
                "/org/assistant/ask",
            )

            return {
                "status": "not_found",
                "context_type": "org_assistant",
                "mode": "function_info",
                "vraag": payload["vraag"],
                "result": {
                    "status": "not_found",
                    "query": payload["vraag"],
                    "person_name": None,
                    "functie_code": None,
                    "message": message,
                    "results": [],
                    "write_actions_available": False,
                },
                "write_actions_available": False,
            }

        response = run_orchestrator(
            OrchestratorAskRequest(
                vraag="wie is verantwoordelijk voor IT"
            ),
            sender=sender,
        )

        self.assertEqual(
            response["status"],
            "ok",
        )

        self.assertEqual(
            response["answer"],
            message,
        )


    def test_cema_answer_is_source_bounded_when_definition_is_absent(self):
        def sender(path, payload):
            self.assertEqual(
                path,
                "/technical/assistant/ask",
            )

            return {
                "status": "ok",
                "context_type": "technical_assistant",
                "vraag": payload["vraag"],
                "source_code": "CEMA_BELT_CONVEYORS_7",
                "fallback_without_source_code_used": False,
                "technical_context": {
                    "status": "ok",
                    "source_code": "CEMA_BELT_CONVEYORS_7",
                    "count": 1,
                    "results": [
                        {
                            "item_type": "table",
                            "source_code": (
                                "CEMA_BELT_CONVEYORS_7"
                            ),
                            "source_title": (
                                "CEMA Belt Conveyors for "
                                "Bulk Materials - 7th Edition"
                            ),
                            "title": (
                                "Table 4.22 CEMA standard "
                                "skirtboard widths"
                            ),
                            "summary_nl": (
                                "CEMA referentie-/lookup-tabel."
                            ),
                        }
                    ],
                },
            }

        response = run_orchestrator(
            OrchestratorAskRequest(
                vraag="wat is CEMA"
            ),
            sender=sender,
        )

        answer = response["answer"]

        self.assertIsNotNone(answer)

        self.assertIn(
            "CEMA",
            answer,
        )

        self.assertIn(
            "CEMA Belt Conveyors for Bulk Materials - 7th Edition",
            answer,
        )

        self.assertIn(
            "geen definitierecord",
            answer.lower(),
        )

        # Deze volledige betekenis zit niet in dit
        # specialistresultaat en mag de formatter dus
        # niet zelf toevoegen.
        self.assertNotIn(
            "Conveyor Equipment Manufacturers Association",
            answer,
        )


    def test_cema_answer_uses_full_name_when_used_context_is_grounded(self):
        full_name = (
            "Conveyor Equipment Manufacturers Association"
        )

        source_title = (
            "CEMA Belt Conveyors for Bulk Materials - "
            "7th Edition"
        )

        def sender(path, payload):
            self.assertEqual(
                path,
                "/technical/assistant/ask",
            )

            return {
                "status": "ok",
                "context_type": "technical_assistant",
                "vraag": payload["vraag"],
                "source_code": "CEMA_BELT_CONVEYORS_7",
                "fallback_without_source_code_used": False,
                "technical_context": {
                    "status": "ok",
                    "source_code": "CEMA_BELT_CONVEYORS_7",
                    "count": 1,
                    "results": [
                        {
                            "item_type": "table",
                            "source_code": (
                                "CEMA_BELT_CONVEYORS_7"
                            ),
                            "source_title": source_title,
                            "title": (
                                "CEMA technical reference"
                            ),
                        }
                    ],
                },
                "rag_context": {
                    "scope_doc_ids": [
                        (
                            "cema_belt_conveyors_o_0000730_"
                            "with_new_logo_ng_2"
                        )
                    ],
                    "scope_mode": "source_linked_documents",
                    "used_context": [
                        {
                            "doc_id": (
                                "cema_belt_conveyors_o_0000730_"
                                "with_new_logo_ng_2"
                            ),
                            "chunk_index": 25,
                            "text": (
                                "CEMA means "
                                + full_name
                                + "."
                            ),
                        }
                    ],
                    "context_hits": [],
                    "antwoord": (
                        "CEMA staat voor "
                        + full_name
                        + "."
                    ),
                },
            }

        response = run_orchestrator(
            OrchestratorAskRequest(
                vraag="wat is CEMA"
            ),
            sender=sender,
        )

        answer = response["answer"]

        self.assertIsNotNone(answer)

        self.assertIn(
            full_name,
            answer,
        )

        self.assertIn(
            source_title,
            answer,
        )

        self.assertNotIn(
            "geen definitierecord",
            answer.lower(),
        )


    def test_cema_answer_does_not_trust_rag_answer_without_grounded_used_context(
        self,
    ):
        full_name = (
            "Conveyor Equipment Manufacturers Association"
        )

        source_title = (
            "CEMA Belt Conveyors for Bulk Materials - "
            "7th Edition"
        )

        def sender(path, payload):
            self.assertEqual(
                path,
                "/technical/assistant/ask",
            )

            return {
                "status": "ok",
                "context_type": "technical_assistant",
                "vraag": payload["vraag"],
                "source_code": "CEMA_BELT_CONVEYORS_7",
                "fallback_without_source_code_used": False,
                "technical_context": {
                    "status": "ok",
                    "source_code": "CEMA_BELT_CONVEYORS_7",
                    "count": 1,
                    "results": [
                        {
                            "item_type": "table",
                            "source_code": (
                                "CEMA_BELT_CONVEYORS_7"
                            ),
                            "source_title": source_title,
                            "title": (
                                "CEMA technical reference"
                            ),
                        }
                    ],
                },
                "rag_context": {
                    "scope_doc_ids": [
                        (
                            "cema_belt_conveyors_o_0000730_"
                            "with_new_logo_ng_2"
                        )
                    ],
                    "scope_mode": "source_linked_documents",
                    "used_context": [
                        {
                            "doc_id": (
                                "cema_belt_conveyors_o_0000730_"
                                "with_new_logo_ng_2"
                            ),
                            "chunk_index": 1163,
                            "text": (
                                "Technical CEMA conveyor "
                                "reference material."
                            ),
                        }
                    ],
                    "context_hits": [],
                    # Bewust: antwoord bevat de naam,
                    # maar de gebruikte broncontext niet.
                    "antwoord": (
                        "CEMA staat voor "
                        + full_name
                        + "."
                    ),
                },
            }

        response = run_orchestrator(
            OrchestratorAskRequest(
                vraag="wat is CEMA"
            ),
            sender=sender,
        )

        answer = response["answer"]

        self.assertIsNotNone(answer)

        self.assertIn(
            source_title,
            answer,
        )

        self.assertIn(
            "geen definitierecord",
            answer.lower(),
        )

        self.assertNotIn(
            full_name,
            answer,
        )



if __name__ == "__main__":
    unittest.main()
