from __future__ import annotations

import json
import unittest
from urllib.request import Request, urlopen


BASE_URL = "http://host.docker.internal:8000"


def ask_orchestrator(question: str) -> dict:
    body = json.dumps(
        {
            "vraag": question,
            "include_trace": True,
        }
    ).encode("utf-8")

    request = Request(
        f"{BASE_URL}/orchestrator/ask",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
        },
    )

    with urlopen(request, timeout=60) as response:
        return json.loads(
            response.read().decode("utf-8")
        )


def entity_value(response: dict, name: str):
    entity = (
        response
        .get("query_plan", {})
        .get("entities", {})
        .get(name)
    )

    if entity is None:
        return None

    return entity.get("value")


def first_result(response: dict):
    results = response.get("results") or []

    if not results:
        return None

    return results[0]


class OrchestratorLiveGoldenTests(unittest.TestCase):

    def test_bb_u1800_live(self):
        r = ask_orchestrator("BB U1800")
        result = first_result(r)

        self.assertEqual(r["status"], "ok")
        self.assertEqual(
            r["query_plan"]["primary_domain"],
            "product",
        )
        self.assertEqual(
            entity_value(r, "family_code"),
            "BB-U",
        )
        self.assertEqual(
            entity_value(r, "belt_width_mm"),
            1800,
        )
        self.assertIsNone(
            entity_value(r, "band_code")
        )
        self.assertEqual(
            result["action"],
            "product_assistant",
        )
        self.assertTrue(result["accepted"])

    def test_bb_u1800_inventory_live(self):
        r = ask_orchestrator(
            "Heb je een U voor 1800 op voorraad?"
        )
        result = first_result(r)

        self.assertEqual(r["status"], "ok")
        self.assertEqual(
            r["query_plan"]["intent"],
            "inventory_lookup",
        )
        self.assertEqual(
            entity_value(r, "family_code"),
            "BB-U",
        )
        self.assertEqual(
            entity_value(r, "belt_width_mm"),
            1800,
        )
        self.assertTrue(result["accepted"])

    def test_tph_hd_no_false_band_live(self):
        r = ask_orchestrator("TPH HD 750 PUR")
        result = first_result(r)

        self.assertEqual(r["status"], "ok")
        self.assertEqual(
            entity_value(r, "family_code"),
            "PROM-TPH-HD",
        )
        self.assertIsNone(
            entity_value(r, "band_code")
        )
        self.assertIsNone(
            entity_value(r, "belt_width_mm")
        )
        self.assertTrue(result["accepted"])

    def test_inspection_lookup_live(self):
        r = ask_orchestrator("Hoe staat B12 ervoor?")
        result = first_result(r)

        self.assertEqual(r["status"], "ok")
        self.assertEqual(
            r["query_plan"]["intent"],
            "inspection_lookup",
        )
        self.assertEqual(
            entity_value(r, "band_code"),
            "B12",
        )
        self.assertEqual(
            result["action"],
            "analysis_assistant",
        )
        self.assertTrue(result["accepted"])
        self.assertEqual(
            result["result"]["intent"],
            "inspection_summary",
        )

    def test_inspection_latest_live(self):
        r = ask_orchestrator(
            "Wat was er vorige keer mis met B12?"
        )
        result = first_result(r)

        self.assertEqual(r["status"], "ok")
        self.assertEqual(
            r["query_plan"]["intent"],
            "inspection_latest",
        )
        self.assertTrue(result["accepted"])
        self.assertEqual(
            result["result"]["intent"],
            "inspection_summary",
        )

    def test_inspection_trend_live(self):
        r = ask_orchestrator(
            "Hoe ontwikkelt de slijtage op B12?"
        )
        result = first_result(r)

        self.assertEqual(r["status"], "ok")
        self.assertEqual(
            r["query_plan"]["intent"],
            "inspection_trend",
        )
        self.assertTrue(result["accepted"])
        self.assertEqual(
            result["result"]["intent"],
            "lifecycle",
        )

    def test_maintenance_priority_live(self):
        r = ask_orchestrator(
            "Wat heeft prioriteit qua onderhoud op B12?"
        )
        result = first_result(r)

        self.assertEqual(r["status"], "ok")
        self.assertEqual(
            r["query_plan"]["intent"],
            "maintenance_priority",
        )
        self.assertTrue(result["accepted"])
        self.assertEqual(
            result["result"]["intent"],
            "maintenance_positions",
        )

    def test_unknown_question_does_not_call_specialist(self):
        r = ask_orchestrator(
            "Kun je daar iets over vertellen?"
        )

        self.assertEqual(
            r["status"],
            "clarification_required",
        )
        self.assertEqual(
            r["query_plan"]["intent"],
            "unknown",
        )
        self.assertTrue(
            r["clarification"]["required"]
        )
        self.assertEqual(
            len(r["query_plan"]["execution_steps"]),
            0,
        )
        self.assertEqual(
            len(r.get("results") or []),
            0,
        )
        self.assertEqual(
            len(
                (r.get("trace") or {}).get(
                    "attempts",
                    [],
                )
            ),
            0,
        )


if __name__ == "__main__":
    unittest.main()