import unittest
from unittest.mock import patch

from app.services.asset_resolver import (
    normalize_asset_code,
    resolve_asset,
)


SAMPLE_R5 = {
    "customer_code": "TATA_STEEL",
    "site_code": "IJMUIDEN",
    "area_code": "GSL",
    "area_name": "GSL",
    "area_source": "historical_source_path",
    "area_confidence": "high",
    "installation_code": "MV1",
    "installation_name": "Mengveld 1",
    "process_area": "Mengvelden",
    "band_code": "R5",
    "band_code_norm": "R5",
    "band_code_display": "R 5",
    "history_mapping_warning": False,
}


SAMPLE_R5_ALT = {
    **SAMPLE_R5,
    "installation_code": "MV9",
    "installation_name": "Testinstallatie",
}


class AssetResolverTests(unittest.TestCase):

    def test_normalize_asset_code_variants(self):
        cases = {
            "R5": "R5",
            "R 5": "R5",
            "R-5": "R5",
            "r5": "R5",
            "E401": "E401",
            "E 401": "E401",
            "E-401": "E401",
            "MV 2": "MV2",
            "MV-2": "MV2",
            "ab 70": "AB70",
        }

        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(
                    normalize_asset_code(raw),
                    expected,
                )

    def test_normalize_empty_values(self):
        self.assertIsNone(normalize_asset_code(None))
        self.assertIsNone(normalize_asset_code(""))
        self.assertIsNone(normalize_asset_code("   "))
        self.assertIsNone(normalize_asset_code("---"))

    @patch("app.services.asset_resolver._fetch_candidates")
    def test_resolved_returns_single_asset_context(
        self,
        fetch_candidates,
    ):
        fetch_candidates.return_value = [
            dict(SAMPLE_R5)
        ]

        result = resolve_asset(
            band_code="R 5",
            installation_code="MV 1",
        )

        self.assertEqual(
            result["status"],
            "resolved",
        )
        self.assertEqual(
            result["normalized_band_code"],
            "R5",
        )
        self.assertEqual(
            result["normalized_installation_code"],
            "MV1",
        )
        self.assertEqual(
            result["match_count"],
            1,
        )
        self.assertEqual(
            result["asset_context"]["band_code_norm"],
            "R5",
        )

    @patch("app.services.asset_resolver._fetch_candidates")
    def test_resolved_contains_required_asset_context_fields(
        self,
        fetch_candidates,
    ):
        fetch_candidates.return_value = [
            dict(SAMPLE_R5)
        ]

        result = resolve_asset(
            band_code="R5",
        )

        context = result["asset_context"]

        required_fields = (
            "customer_code",
            "site_code",
            "area_code",
            "installation_code",
            "band_code_norm",
        )

        for field in required_fields:
            with self.subTest(field=field):
                self.assertIn(field, context)
                self.assertNotIn(
                    context[field],
                    (None, ""),
                )

    @patch("app.services.asset_resolver._fetch_candidates")
    def test_not_found_when_no_candidates(
        self,
        fetch_candidates,
    ):
        fetch_candidates.return_value = []

        result = resolve_asset(
            band_code="ZZ999",
        )

        self.assertEqual(
            result["status"],
            "not_found",
        )
        self.assertEqual(
            result["normalized_band_code"],
            "ZZ999",
        )
        self.assertEqual(
            result["match_count"],
            0,
        )
        self.assertIsNone(
            result["asset_context"]
        )
        self.assertEqual(
            result["candidates"],
            [],
        )

    def test_not_found_without_band_code_does_not_query_database(self):
        with patch(
            "app.services.asset_resolver._fetch_candidates"
        ) as fetch_candidates:

            result = resolve_asset(
                band_code=None,
            )

        fetch_candidates.assert_not_called()

        self.assertEqual(
            result["status"],
            "not_found",
        )
        self.assertEqual(
            result["match_count"],
            0,
        )
        self.assertIsNone(
            result["asset_context"]
        )

    @patch("app.services.asset_resolver._fetch_candidates")
    def test_ambiguous_returns_candidates_and_no_asset_context(
        self,
        fetch_candidates,
    ):
        fetch_candidates.return_value = [
            dict(SAMPLE_R5),
            dict(SAMPLE_R5_ALT),
        ]

        result = resolve_asset(
            band_code="R-5",
        )

        self.assertEqual(
            result["status"],
            "ambiguous",
        )
        self.assertEqual(
            result["normalized_band_code"],
            "R5",
        )
        self.assertEqual(
            result["match_count"],
            2,
        )
        self.assertIsNone(
            result["asset_context"]
        )
        self.assertEqual(
            len(result["candidates"]),
            2,
        )

    @patch("app.services.asset_resolver._fetch_candidates")
    def test_normalized_values_are_passed_to_lookup(
        self,
        fetch_candidates,
    ):
        fetch_candidates.return_value = [
            dict(SAMPLE_R5)
        ]

        resolve_asset(
            band_code="R - 5",
            installation_code="MV - 1",
        )

        kwargs = fetch_candidates.call_args.kwargs

        self.assertEqual(
            kwargs["band_code_norm"],
            "R5",
        )
        self.assertEqual(
            kwargs["installation_code_norm"],
            "MV1",
        )


if __name__ == "__main__":
    unittest.main()
