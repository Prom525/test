import unittest
from unittest.mock import patch

from app.routers import hybrid_api


class SpecialistRoutingFixTests(unittest.TestCase):

    def test_cema_alias_uses_canonical_source_without_broad_fallback(self):
        calls = []

        def fake_get_technical_context(
            q,
            topic_group=None,
            source_code=None,
            item_type=None,
            limit=20,
        ):
            calls.append(source_code)

            if source_code == "CEMA_BELT_CONVEYORS_7":
                return {
                    "status": "ok",
                    "query": q,
                    "source_code": source_code,
                    "count": 1,
                    "results": [
                        {
                            "source_code":
                                "CEMA_BELT_CONVEYORS_7",
                            "title": "CEMA test result",
                        }
                    ],
                }

            return {
                "status": "ok",
                "query": q,
                "source_code": source_code,
                "count": 0,
                "results": [],
            }

        payload = hybrid_api.TechnicalAskRequest(
            vraag="wat is CEMA",
            use_rag=True,
            limit=10,
        )

        with patch.object(
            hybrid_api,
            "get_technical_context",
            side_effect=fake_get_technical_context,
        ):
            result = hybrid_api.technical_assistant_ask(
                payload
            )

        self.assertEqual(
            result["source_code"],
            "CEMA_BELT_CONVEYORS_7",
        )
        self.assertFalse(
            result[
                "fallback_without_source_code_used"
            ]
        )
        self.assertEqual(
            result["technical_context"]["source_code"],
            "CEMA_BELT_CONVEYORS_7",
        )
        self.assertEqual(
            calls,
            ["CEMA_BELT_CONVEYORS_7"],
        )

    def test_org_auto_detects_natural_location_question(self):
        mode = hybrid_api._detect_org_mode(
            "waar is Promati gevestigd",
            "auto",
        )

        self.assertEqual(
            mode,
            "location_info",
        )

    def test_org_it_not_found_is_not_replaced_by_guess(self):
        calls = []

        def fake_get_internal(
            path,
            params=None,
        ):
            calls.append(
                (path, dict(params or {}))
            )

            return {
                "status": "not_found",
                "query":
                    "wie is verantwoordelijk voor IT",
                "person_name": None,
                "functie_code": None,
                "message":
                    "Geen persoon of functie herkend "
                    "in deze vraag.",
                "results": [],
                "write_actions_available": False,
            }

        payload = hybrid_api.OrgAskRequest(
            vraag="wie is verantwoordelijk voor IT",
            firma="Promati",
            mode="auto",
        )

        with patch.object(
            hybrid_api,
            "_get_internal",
            side_effect=fake_get_internal,
        ):
            result = hybrid_api.org_assistant_ask(
                payload
            )

        self.assertEqual(
            result["mode"],
            "function_info",
        )
        self.assertEqual(
            result["status"],
            "not_found",
        )
        self.assertIsNone(
            result["result"]["person_name"]
        )
        self.assertIsNone(
            result["result"]["functie_code"]
        )
        self.assertEqual(
            len(calls),
            1,
        )
        self.assertEqual(
            calls[0][0],
            "/analysis/context/org/function-info",
        )


if __name__ == "__main__":
    unittest.main()
