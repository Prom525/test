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
    UNLINKED,
    build_canonical_position_projection,
)


class CanonicalPositionProjectionTests(
    unittest.TestCase
):
    def test_r_exact_link_and_forecast(self):
        key = "SOURCE|week 19|2026-05-05"

        current = [
            {
                "lijn_code": "GSL",
                "band_norm": "A660",
                "position_display": (
                    "SUB_POSITION"
                ),
                "position_key_unified": (
                    "CURRENT-R"
                ),
                "scraper_type_norm": (
                    "RI 1400-1350"
                ),
                "scraper_family": "R",
                "scraper_material": "INOX",
                "meshoogte_mm": 5.0,
                "laatste_inspectiedatum": (
                    "2026-05-05"
                ),
                "inspection_key": key,
                "row_nr": 41,
            }
        ]

        lifecycle = [
            {
                "inspected_on": "2026-05-05",
                "lijn_code": "GSL",
                "band_norm": "A660",
                "scraper_type_norm": (
                    "R 1400-1350 INOX"
                ),
                "scraper_role": "SECUNDAIR",
                "physical_position_label_final": (
                    "SECUNDAIR"
                ),
                "position_hint": "SECUNDAIR",
                "meshoogte_mm": 5.0,
                "cycle_id": 1,
                "canonical_inspection_key": key,
            }
        ]

        forecast = [
            {
                "lijn_code": "GSL",
                "band_norm": "A660",
                "scraper_type_norm": (
                    "R 1400-1350 INOX"
                ),
                "cycle_start": "2025-03-05",
                "cycle_end": "2026-05-05",
                "meetpunten": 7,
                "geschatte_vervangdatum_bij_3mm": (
                    "2026-10-22"
                ),
                "status_3mm": "MONITOREN",
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
            result[0]["historical_link"]["status"],
            MATCHED,
        )

        self.assertEqual(
            result[0]["historical_link"]["cycle_id"],
            1,
        )

        self.assertTrue(
            result[0]["forecast"]["linked"]
        )

        self.assertEqual(
            result[0]["forecast"][
                "measurement_count"
            ],
            7,
        )

        self.assertEqual(
            result[0]["forecast"][
                "forecast_date"
            ],
            "2026-10-22",
        )

    def test_u_midden_does_not_link_to_zuid(self):
        key = "SOURCE|week 19|2026-05-05"

        current = [
            {
                "lijn_code": "GSL",
                "band_norm": "A660",
                "position_display": "MIDDEN",
                "position_key_unified": (
                    "CURRENT-U"
                ),
                "scraper_type_norm": "UI 1400",
                "scraper_family": "U",
                "meshoogte_mm": 6.0,
                "laatste_inspectiedatum": (
                    "2026-05-05"
                ),
                "inspection_key": key,
                "row_nr": 39,
            }
        ]

        lifecycle = [
            {
                "inspected_on": "2026-05-05",
                "lijn_code": "GSL",
                "band_norm": "A660",
                "scraper_type_norm": (
                    "U 1400 INOX"
                ),
                "scraper_role": "SECUNDAIR",
                "physical_position_label_final": (
                    "ZUID"
                ),
                "position_hint": "ZUID",
                "meshoogte_mm": 6.0,
                "cycle_id": 6,
                "canonical_inspection_key": key,
            }
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
            UNLINKED,
        )

        self.assertFalse(
            result[0]["forecast"]["linked"]
        )

    def test_old_u_history_is_not_current_u(self):
        current = [
            {
                "lijn_code": "GSL",
                "band_norm": "A660",
                "position_display": "MIDDEN",
                "scraper_type_norm": "UI 1400",
                "scraper_family": "U",
                "meshoogte_mm": 6.0,
                "inspection_key": (
                    "CURRENT|2026-05-05"
                ),
                "row_nr": 39,
            }
        ]

        lifecycle = [
            {
                "inspected_on": "2025-03-05",
                "lijn_code": "GSL",
                "band_norm": "A660",
                "scraper_type_norm": (
                    "U 1400 INOX"
                ),
                "physical_position_label_final": (
                    "ZUID"
                ),
                "position_hint": "ZUID",
                "meshoogte_mm": None,
                "cycle_id": 6,
                "canonical_inspection_key": (
                    "OLD|2025-03-05"
                ),
            }
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
            UNLINKED,
        )

    def test_multiple_exact_candidates_are_ambiguous(
        self,
    ):
        key = "SOURCE|2026-05-05"

        current = [
            {
                "lijn_code": "GSL",
                "band_norm": "A660",
                "position_display": (
                    "SUB_POSITION"
                ),
                "scraper_type_norm": "RI 1400",
                "scraper_family": "R",
                "meshoogte_mm": 5.0,
                "inspection_key": key,
                "row_nr": 41,
            }
        ]

        lifecycle = [
            {
                "inspected_on": "2026-05-05",
                "lijn_code": "GSL",
                "band_norm": "A660",
                "scraper_type_norm": "R 1400",
                "meshoogte_mm": 5.0,
                "cycle_id": 1,
                "canonical_inspection_key": key,
            },
            {
                "inspected_on": "2026-05-05",
                "lijn_code": "GSL",
                "band_norm": "A660",
                "scraper_type_norm": "R 1500",
                "meshoogte_mm": 5.0,
                "cycle_id": 2,
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
            AMBIGUOUS,
        )

        self.assertFalse(
            result[0]["forecast"]["linked"]
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
