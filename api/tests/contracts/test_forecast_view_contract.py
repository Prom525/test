from __future__ import annotations

import unittest

from app.routers import analysis_api_v10 as analysis


class ForecastDatabaseContractTests(unittest.TestCase):

    def test_vw_mes_cycle_analysis_clean_contract(self):
        row = analysis.fetch_one(
            """
            SELECT pg_get_viewdef(
                'public.vw_mes_cycle_analysis_clean_v14_candidate'::regclass,
                true
            ) AS definition
            """,
            {},
        )

        self.assertIsNotNone(row)

        definition = " ".join(
            row["definition"].split()
        ).lower()

        # Minimaal drie meetpunten voor echte forecast.
        self.assertIn(
            "meetpunten >= 3",
            definition,
        )

        # Harde vervanggrens = 3 mm.
        self.assertRegex(
            definition,
            r"eind_meshoogte_mm\s*<=\s*\(?3\)?::numeric",
        )

        # Forecast naar de 3 mm-grens.
        self.assertRegex(
            definition,
            r"eind_meshoogte_mm\s*-\s*\(?3\)?::numeric",
        )

        # Te weinig data moet expliciet herkenbaar blijven.
        self.assertIn(
            "'te_weinig_meetpunten'::text",
            definition,
        )

        # Kritieke status.
        self.assertIn(
            "'nu vervangen'::text",
            definition,
        )

        # Termijnclassificaties.
        self.assertIn(
            "'binnen 30 dagen'::text",
            definition,
        )

        self.assertIn(
            "'binnen 60 dagen'::text",
            definition,
        )

        # Geldige trendkwaliteit is onderdeel van forecastcontract.
        self.assertIn(
            "'goed_dalende_trend'::text",
            definition,
        )

        self.assertIn(
            "'ok_vlakke_trend'::text",
            definition,
        )

        self.assertIn(
            "'ok_met_meetvariatie'::text",
            definition,
        )


if __name__ == "__main__":
    unittest.main()