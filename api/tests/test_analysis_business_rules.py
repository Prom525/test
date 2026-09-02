from __future__ import annotations

import unittest
from unittest.mock import patch

from app.routers import analysis_api_v10 as analysis


class AnalysisBusinessRuleGoldenTests(unittest.TestCase):

    def test_latest_meshoogte_uses_latest_view_not_max(self):
        captured = {}

        def fake_fetch_all(sql, params):
            captured["sql"] = sql
            captured["params"] = params
            return []

        with patch.object(
            analysis,
            "fetch_all",
            side_effect=fake_fetch_all,
        ):
            result = analysis.latest_meshoogte(
                lijn_code=None,
                band_code="B12",
                scraper_type=None,
                limit=20,
            )

        sql = captured["sql"]

        self.assertIn(
            "vw_meshoogte_latest_per_scraper_clean",
            sql,
        )

        self.assertNotIn(
            "MAX(",
            sql.upper(),
            (
                "Actuele meshoogte mag niet via MAX() "
                "worden bepaald."
            ),
        )

        self.assertEqual(
            result["intent"],
            "latest_mes",
        )

    def test_forecast_requires_at_least_three_measurements(self):
        captured = {}

        def fake_fetch_all(sql, params):
            captured["sql"] = sql
            captured["params"] = params
            return []

        with patch.object(
            analysis,
            "fetch_all",
            side_effect=fake_fetch_all,
        ):
            result = analysis.forecast_3mm(
                lijn_code=None,
                band_code="B12",
                scraper_type=None,
                limit=20,
            )

        normalized_sql = " ".join(
            captured["sql"].split()
        ).lower()

        self.assertIn(
            "from vw_mes_cycle_analysis_clean",
            normalized_sql,
        )

        self.assertIn(
            "meetpunten >= 3",
            normalized_sql,
            (
                "Forecast moet minimaal drie "
                "meetpunten vereisen."
            ),
        )

        self.assertEqual(
            result["intent"],
            "forecast",
        )

    def test_replacement_boundary_is_three_mm(self):
        row = {
            "eind_meshoogte_mm": 10,
            "slijtage_mm_per_dag": None,
            "cycle_end": None,
        }

        result = analysis.enrich_performance_6mm(row)

        self.assertEqual(
            result["vervanggrens_mm"],
            3,
            "De harde vervanggrens moet 3 mm blijven.",
        )

        self.assertEqual(
            result["prestatiegrens_mm"],
            6,
            (
                "De 6 mm prestatiegrens en "
                "3 mm vervanggrens mogen niet "
                "door elkaar worden gehaald."
            ),
        )

    def test_band_without_scrapers_is_normal_status_not_error(self):
        band_row = {
            "inspection_key": "TEST-001",
            "lijn_code": "L1",
            "band_locatie": "B12",
            "scraper_status": "BAND_ZONDER_SCHRAPERS",
        }

        with (
            patch.object(
                analysis,
                "fetch_one",
                return_value={"total_count": 1},
            ),
            patch.object(
                analysis,
                "fetch_all",
                return_value=[band_row],
            ),
        ):
            result = analysis.band_scraper_status(
                lijn_code=None,
                band_code="B12",
                scraper_status=None,
                only_without_scrapers=False,
                limit=20,
            )

        self.assertEqual(
            result["intent"],
            "band_scraper_status",
        )

        self.assertEqual(
            result["total_count"],
            1,
        )

        self.assertEqual(
            result["resultaat"][0]["scraper_status"],
            "BAND_ZONDER_SCHRAPERS",
        )

        self.assertNotIn(
            "error",
            result,
            (
                "BAND_ZONDER_SCHRAPERS is een geldige "
                "status en mag niet automatisch als "
                "fout worden geretourneerd."
            ),
        )


if __name__ == "__main__":
    unittest.main()