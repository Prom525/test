from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT),
    )


from app.orchestrator.public_results import (  # noqa: E402
    PUBLIC_PROFILE,
    compact_results_for_public_response,
)


class PublicResultsProjectionTests(
    unittest.TestCase
):
    def test_replacement_keeps_canonical_but_drops_raw_history(
        self,
    ):
        raw_result = {
            "intent": "band_deep_analysis",
            "kort_resultaat": "ok",
            "gecombineerde_slijtage": [
                {
                    "lijn_code": "GSL",
                    "band_norm": "A660",
                    "row_nr": 41,
                    "meshoogte_mm": 5,
                    "source_file": "internal.xlsx",
                    "sheet": "week 19",
                }
            ],
            "canonical_positions": [
                {
                    "contract_version": "v1",
                    "historical_link": {
                        "status": "MATCHED",
                    },
                }
            ],
            "lifecycle": [
                {
                    "inspected_on": "2026-05-05",
                    "replace_event": False,
                    "source_file": "internal.xlsx",
                }
            ],
            "forecast_3mm": [
                {"meetpunten": 7}
            ],
            "scraper_status": [
                {"inspection_key": "x"}
            ],
            "laatste_meshoogte": [
                {"meshoogte_mm": 5}
            ],
            "relevante_opmerkingen": [
                {"commentaar": "x"}
            ],
            "asset_context": {
                "band_code": "A660",
            },
        }

        results = [
            {
                "step_id": "step_1",
                "action": "analysis_assistant",
                "accepted": True,
                "result": raw_result,
            }
        ]

        compact = (
            compact_results_for_public_response(
                results,
                requested_information=[
                    "replacement_advice"
                ],
            )
        )

        projected = compact[0]["result"]

        self.assertEqual(
            projected["public_profile"],
            PUBLIC_PROFILE,
        )

        self.assertIn(
            "canonical_positions",
            projected,
        )

        self.assertIn(
            "gecombineerde_slijtage",
            projected,
        )

        self.assertNotIn(
            "lifecycle",
            projected,
        )

        self.assertNotIn(
            "forecast_3mm",
            projected,
        )

        self.assertNotIn(
            "scraper_status",
            projected,
        )

        self.assertNotIn(
            "laatste_meshoogte",
            projected,
        )

        self.assertNotIn(
            "relevante_opmerkingen",
            projected,
        )

        self.assertNotIn(
            "source_file",
            projected[
                "gecombineerde_slijtage"
            ][0],
        )

        # Raw intern object wordt niet gewijzigd.
        self.assertIn(
            "lifecycle",
            raw_result,
        )


    def test_composite_keeps_compact_lifecycle(
        self,
    ):
        results = [
            {
                "result": {
                    "intent": (
                        "band_deep_analysis"
                    ),
                    "canonical_positions": [],
                    "gecombineerde_slijtage": [],
                    "lifecycle": [
                        {
                            "inspected_on": (
                                "2026-05-05"
                            ),
                            "band_norm": "A660",
                            "scraper_type_norm": (
                                "R 1400"
                            ),
                            "replace_event": False,
                            "cycle_id": 1,
                            "source_file": (
                                "internal.xlsx"
                            ),
                            "sheet_raw": (
                                "week 19"
                            ),
                        }
                    ],
                }
            }
        ]

        compact = (
            compact_results_for_public_response(
                results,
                requested_information=[
                    "lifecycle_trend",
                ],
            )
        )

        row = compact[0][
            "result"
        ]["lifecycle"][0]

        self.assertEqual(
            row["cycle_id"],
            1,
        )

        self.assertNotIn(
            "source_file",
            row,
        )

        self.assertNotIn(
            "sheet_raw",
            row,
        )


    def test_replacement_events_only_filters_rows(
        self,
    ):
        results = [
            {
                "result": {
                    "intent": (
                        "band_deep_analysis"
                    ),
                    "canonical_positions": [],
                    "gecombineerde_slijtage": [],
                    "lifecycle": [
                        {
                            "inspected_on": (
                                "2025-03-05"
                            ),
                            "replace_event": True,
                            "cycle_id": 1,
                        },
                        {
                            "inspected_on": (
                                "2026-05-05"
                            ),
                            "replace_event": False,
                            "cycle_id": 1,
                        },
                    ],
                }
            }
        ]

        compact = (
            compact_results_for_public_response(
                results,
                requested_information=[
                    "replacement_events",
                ],
            )
        )

        rows = compact[0][
            "result"
        ]["lifecycle"]

        self.assertEqual(
            len(rows),
            1,
        )

        self.assertTrue(
            rows[0]["replace_event"]
        )


    def test_inspection_summary_keeps_all_rows_but_projects_fields(
        self,
    ):
        results = [
            {
                "result": {
                    "intent": (
                        "inspection_summary"
                    ),
                    "resultaat_count": 2,
                    "resultaat": [
                        {
                            "inspection_key": "a",
                            "document_date": (
                                "2026-05-05"
                            ),
                            "band_code": "A660",
                            "meshoogte_mm": 5,
                            "source_file": "x",
                        },
                        {
                            "inspection_key": "b",
                            "document_date": (
                                "2026-03-10"
                            ),
                            "band_code": "A660",
                            "meshoogte_mm": 5,
                            "source_file": "y",
                        },
                    ],
                }
            }
        ]

        compact = (
            compact_results_for_public_response(
                results
            )
        )

        rows = compact[0][
            "result"
        ]["resultaat"]

        self.assertEqual(
            len(rows),
            2,
        )

        self.assertNotIn(
            "source_file",
            rows[0],
        )


    def test_lifecycle_keeps_all_rows_without_internal_sheet_fields(
        self,
    ):
        results = [
            {
                "result": {
                    "intent": "lifecycle",
                    "resultaat": [
                        {
                            "inspected_on": (
                                "2026-05-05"
                            ),
                            "band_norm": "A660",
                            "cycle_id": 1,
                            "meshoogte_mm": 5,
                            "source_file": "x",
                            "sheet_raw": "week 19",
                        },
                        {
                            "inspected_on": (
                                "2026-03-10"
                            ),
                            "band_norm": "A660",
                            "cycle_id": 1,
                            "meshoogte_mm": 5,
                            "source_file": "x",
                            "sheet_raw": "week 11",
                        },
                    ],
                }
            }
        ]

        compact = (
            compact_results_for_public_response(
                results
            )
        )

        rows = compact[0][
            "result"
        ]["resultaat"]

        self.assertEqual(
            len(rows),
            2,
        )

        self.assertNotIn(
            "source_file",
            rows[0],
        )

        self.assertNotIn(
            "sheet_raw",
            rows[0],
        )


    def test_unknown_intent_is_fail_open(
        self,
    ):
        original = {
            "intent": "unknown_future_intent",
            "large_field": [
                {"a": 1}
            ],
        }

        results = [
            {
                "step_id": "x",
                "result": original,
            }
        ]

        compact = (
            compact_results_for_public_response(
                results
            )
        )

        self.assertEqual(
            compact[0]["result"],
            original,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
