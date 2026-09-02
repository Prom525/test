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


from app.canonical_positions import (  # noqa: E402
    AMBIGUOUS,
    MATCHED,
    build_canonical_position_projection,
)


class CanonicalPositionCollisionTests(
    unittest.TestCase
):
    def test_many_current_rows_same_lifecycle_are_ambiguous(
        self,
    ):
        key = "SOURCE|week 21|2026-05-19"

        current = [
            {
                "lijn_code": "EO1",
                "band_norm": "E300",
                "position_display": "WEST",
                "position_key_unified": (
                    "E300|WEST|R|SLOT_1"
                ),
                "scraper_type_norm": (
                    "R 1200-1050 SP/M3"
                ),
                "scraper_family": "R",
                "meshoogte_mm": 5.0,
                "laatste_inspectiedatum": (
                    "2026-05-19"
                ),
                "inspection_key": key,
                "row_nr": 14,
            },
            {
                "lijn_code": "EO1",
                "band_norm": "E300",
                "position_display": "WEST",
                "position_key_unified": (
                    "E300|WEST|R|SLOT_2"
                ),
                "scraper_type_norm": (
                    "R 1200-1050 SP/M3"
                ),
                "scraper_family": "R",
                "meshoogte_mm": 5.0,
                "laatste_inspectiedatum": (
                    "2026-05-19"
                ),
                "inspection_key": key,
                "row_nr": 15,
            },
        ]

        lifecycle = [
            {
                "inspected_on": "2026-05-19",
                "lijn_code": "EO1",
                "band_norm": "E300",
                "scraper_type_norm": (
                    "R 1200-1050 SP/M3"
                ),
                "scraper_role": "TERTIAIR",
                "physical_position_label_final": (
                    "WEST"
                ),
                "position_hint": "WEST",
                "meshoogte_mm": 5.0,
                "cycle_id": 0,
                "canonical_inspection_key": key,
            }
        ]

        forecast = [
            {
                "lijn_code": "EO1",
                "band_norm": "E300",
                "scraper_type_norm": (
                    "R 1200-1050 SP/M3"
                ),
                "cycle_start": "2026-01-01",
                "cycle_end": "2026-05-19",
                "meetpunten": 5,
                "geschatte_vervangdatum_bij_3mm": (
                    "2027-01-01"
                ),
                "last_canonical_inspection_key": (
                    key
                ),
            }
        ]

        result = (
            build_canonical_position_projection(
                current_rows=current,
                lifecycle_rows=lifecycle,
                forecast_rows=forecast,
            )
        )

        self.assertEqual(
            len(result),
            2,
        )

        for position in result:
            historical = position[
                "historical_link"
            ]

            self.assertEqual(
                historical["status"],
                AMBIGUOUS,
            )

            self.assertEqual(
                historical["reason"],
                (
                    "many_current_entities_"
                    "share_lifecycle_identity"
                ),
            )

            self.assertEqual(
                historical[
                    "collision_current_count"
                ],
                2,
            )

            self.assertIsNone(
                historical["cycle_id"]
            )

            self.assertFalse(
                position["forecast"]["linked"]
            )


    def test_distinct_positions_remain_matched(
        self,
    ):
        key = "SOURCE|week 21|2026-05-19"

        current = [
            {
                "lijn_code": "EO1",
                "band_norm": "E300",
                "position_display": "WEST",
                "position_key_unified": (
                    "E300|WEST|R"
                ),
                "scraper_type_norm": (
                    "R 1200-1050 SP/M3"
                ),
                "scraper_family": "R",
                "meshoogte_mm": 5.0,
                "inspection_key": key,
                "row_nr": 14,
            },
            {
                "lijn_code": "EO1",
                "band_norm": "E300",
                "position_display": "OOST",
                "position_key_unified": (
                    "E300|OOST|R"
                ),
                "scraper_type_norm": (
                    "R 1200-1050 SP/M3"
                ),
                "scraper_family": "R",
                "meshoogte_mm": 6.0,
                "inspection_key": key,
                "row_nr": 17,
            },
        ]

        lifecycle = [
            {
                "inspected_on": "2026-05-19",
                "lijn_code": "EO1",
                "band_norm": "E300",
                "scraper_type_norm": (
                    "R 1200-1050 SP/M3"
                ),
                "scraper_role": "TERTIAIR",
                "physical_position_label_final": (
                    "WEST"
                ),
                "position_hint": "WEST",
                "meshoogte_mm": 5.0,
                "cycle_id": 0,
                "canonical_inspection_key": key,
            },
            {
                "inspected_on": "2026-05-19",
                "lijn_code": "EO1",
                "band_norm": "E300",
                "scraper_type_norm": (
                    "R 1200-1050 SP/M3"
                ),
                "scraper_role": "SECUNDAIR",
                "physical_position_label_final": (
                    "OOST"
                ),
                "position_hint": "OOST",
                "meshoogte_mm": 6.0,
                "cycle_id": 1,
                "canonical_inspection_key": key,
            },
        ]

        result = (
            build_canonical_position_projection(
                current_rows=current,
                lifecycle_rows=lifecycle,
                forecast_rows=[],
            )
        )

        self.assertEqual(
            result[0]["historical_link"]["status"],
            MATCHED,
        )

        self.assertEqual(
            result[1]["historical_link"]["status"],
            MATCHED,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
