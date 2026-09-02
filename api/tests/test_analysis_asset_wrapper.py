import unittest
from unittest.mock import patch

from app.routers import analysis_api_v10 as analysis


R5_CONTEXT = {
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


E401_CONTEXT = {
    "customer_code": "TATA_STEEL",
    "site_code": "IJMUIDEN",
    "area_code": "GSL",
    "area_name": "GSL",
    "area_source": "inspection_plan",
    "area_confidence": "high",
    "installation_code": "MV2",
    "installation_name": "Mengveld 2",
    "process_area": "Mengvelden",
    "band_code": "E401",
    "band_code_norm": "E401",
    "band_code_display": "E401",
    "history_mapping_warning": False,
}


def resolved(context):
    return {
        "status": "resolved",
        "match_count": 1,
        "normalized_band_code": context["band_code_norm"],
        "normalized_installation_code": None,
        "asset_context": dict(context),
        "candidates": [],
    }


class AnalysisAssetWrapperTests(unittest.TestCase):

    @patch.object(analysis, "_analysis_assistant_ask_impl")
    @patch.object(analysis, "resolve_asset")
    def test_r_space_5_uses_canonical_mv1_and_adds_context(
        self,
        resolve_asset,
        impl,
    ):
        resolve_asset.return_value = resolved(R5_CONTEXT)
        impl.return_value = {"intent": "latest_mes"}

        payload = analysis.AssistantAskRequest(
            vraag="laatste meshoogte van band R 5",
            band_code="R 5",
        )

        result = analysis.analysis_assistant_ask(payload)

        canonical = impl.call_args.args[0]

        self.assertEqual(canonical.lijn_code, "MV1")
        self.assertEqual(canonical.band_code, "R5")

        self.assertEqual(
            result["asset_resolution"]["status"],
            "resolved",
        )

        context = result["asset_context"]

        for field in (
            "customer_code",
            "site_code",
            "area_code",
            "installation_code",
            "band_code_norm",
        ):
            self.assertIn(field, context)
            self.assertNotIn(context[field], (None, ""))

    @patch.object(analysis, "_analysis_assistant_ask_impl")
    @patch.object(analysis, "resolve_asset")
    def test_r_dash_5_is_detected_from_free_text(
        self,
        resolve_asset,
        impl,
    ):
        resolve_asset.return_value = resolved(R5_CONTEXT)
        impl.return_value = {"intent": "latest_mes"}

        payload = analysis.AssistantAskRequest(
            vraag="laatste meshoogte van band R-5",
        )

        analysis.analysis_assistant_ask(payload)

        resolver_band = (
            resolve_asset.call_args.kwargs["band_code"]
        )

        self.assertEqual(
            analysis.normalize_asset_code(resolver_band),
            "R5",
        )

        canonical = impl.call_args.args[0]

        self.assertEqual(canonical.lijn_code, "MV1")
        self.assertEqual(canonical.band_code, "R5")

    @patch.object(analysis, "_analysis_assistant_ask_impl")
    @patch.object(analysis, "resolve_asset")
    def test_e401_resolves_to_mv2(
        self,
        resolve_asset,
        impl,
    ):
        resolve_asset.return_value = resolved(E401_CONTEXT)
        impl.return_value = {"intent": "maintenance"}

        payload = analysis.AssistantAskRequest(
            vraag="onderhoud van band E401",
            band_code="E401",
        )

        result = analysis.analysis_assistant_ask(payload)

        canonical = impl.call_args.args[0]

        self.assertEqual(canonical.lijn_code, "MV2")
        self.assertEqual(canonical.band_code, "E401")
        self.assertEqual(
            result["asset_context"]["installation_code"],
            "MV2",
        )

    @patch.object(analysis, "_analysis_assistant_ask_impl")
    @patch.object(analysis, "resolve_asset")
    def test_gsl_area_hint_is_accepted_for_r5(
        self,
        resolve_asset,
        impl,
    ):
        resolve_asset.return_value = resolved(R5_CONTEXT)
        impl.return_value = {"intent": "latest_mes"}

        payload = analysis.AssistantAskRequest(
            vraag="laatste meshoogte R5",
            lijn_code="GSL",
            band_code="R5",
        )

        result = analysis.analysis_assistant_ask(payload)

        canonical = impl.call_args.args[0]

        self.assertEqual(canonical.lijn_code, "MV1")
        self.assertEqual(canonical.band_code, "R5")
        self.assertEqual(
            result["asset_resolution"]["status"],
            "resolved",
        )

    @patch.object(analysis, "_analysis_assistant_ask_impl")
    @patch.object(analysis, "resolve_asset")
    def test_conflicting_mv2_r5_requires_clarification(
        self,
        resolve_asset,
        impl,
    ):
        resolve_asset.return_value = resolved(R5_CONTEXT)

        payload = analysis.AssistantAskRequest(
            vraag="laatste meshoogte R5",
            lijn_code="MV2",
            band_code="R5",
        )

        result = analysis.analysis_assistant_ask(payload)

        impl.assert_not_called()

        self.assertEqual(
            result["status"],
            "clarification_required",
        )
        self.assertEqual(
            result["asset_resolution"]["status"],
            "context_conflict",
        )
        self.assertEqual(
            result["asset_context"]["installation_code"],
            "MV1",
        )

    @patch.object(analysis, "_analysis_assistant_ask_impl")
    @patch.object(analysis, "resolve_asset")
    def test_ambiguous_without_hint_requires_clarification(
        self,
        resolve_asset,
        impl,
    ):
        second = {
            **R5_CONTEXT,
            "installation_code": "MV9",
            "installation_name": "Testinstallatie",
            "area_code": "TEST",
        }

        resolve_asset.return_value = {
            "status": "ambiguous",
            "match_count": 2,
            "normalized_band_code": "R5",
            "normalized_installation_code": None,
            "asset_context": None,
            "candidates": [
                dict(R5_CONTEXT),
                second,
            ],
        }

        payload = analysis.AssistantAskRequest(
            vraag="toon band R5",
            band_code="R5",
        )

        result = analysis.analysis_assistant_ask(payload)

        impl.assert_not_called()

        self.assertEqual(
            result["status"],
            "clarification_required",
        )
        self.assertEqual(
            result["asset_resolution"]["status"],
            "ambiguous",
        )
        self.assertEqual(len(result["candidates"]), 2)

    @patch.object(analysis, "_analysis_assistant_ask_impl")
    @patch.object(analysis, "resolve_asset")
    def test_ambiguous_is_narrowed_by_installation_hint(
        self,
        resolve_asset,
        impl,
    ):
        mv2_context = {
            **R5_CONTEXT,
            "installation_code": "MV2",
            "installation_name": "Test MV2",
        }

        resolve_asset.return_value = {
            "status": "ambiguous",
            "match_count": 2,
            "normalized_band_code": "R5",
            "normalized_installation_code": None,
            "asset_context": None,
            "candidates": [
                dict(R5_CONTEXT),
                mv2_context,
            ],
        }

        impl.return_value = {"intent": "latest_mes"}

        payload = analysis.AssistantAskRequest(
            vraag="toon band R5",
            lijn_code="MV2",
            band_code="R5",
        )

        result = analysis.analysis_assistant_ask(payload)

        canonical = impl.call_args.args[0]

        self.assertEqual(canonical.lijn_code, "MV2")
        self.assertEqual(canonical.band_code, "R5")
        self.assertEqual(
            result["asset_context"]["installation_code"],
            "MV2",
        )

    @patch.object(analysis, "_analysis_assistant_ask_impl")
    @patch.object(analysis, "resolve_asset")
    def test_not_found_preserves_legacy_flow(
        self,
        resolve_asset,
        impl,
    ):
        resolve_asset.return_value = {
            "status": "not_found",
            "match_count": 0,
            "normalized_band_code": "ZZ999",
            "normalized_installation_code": None,
            "asset_context": None,
            "candidates": [],
        }

        impl.return_value = {"intent": "legacy_band"}

        payload = analysis.AssistantAskRequest(
            vraag="toon band ZZ999",
            band_code="ZZ999",
        )

        result = analysis.analysis_assistant_ask(payload)

        forwarded = impl.call_args.args[0]

        self.assertEqual(forwarded.band_code, "ZZ999")
        self.assertIsNone(forwarded.lijn_code)

        self.assertEqual(
            result["asset_resolution"]["status"],
            "not_found",
        )
        self.assertIsNone(result["asset_context"])

    @patch.object(analysis, "_analysis_assistant_ask_impl")
    @patch.object(analysis, "resolve_asset")
    def test_no_band_bypasses_resolver(
        self,
        resolve_asset,
        impl,
    ):
        impl.return_value = {"intent": "dataset"}

        payload = analysis.AssistantAskRequest(
            vraag="geef een algemeen overzicht",
        )

        result = analysis.analysis_assistant_ask(payload)

        resolve_asset.assert_not_called()
        impl.assert_called_once()
        self.assertEqual(result, {"intent": "dataset"})

    @patch.object(analysis, "_analysis_assistant_ask_impl")
    @patch.object(analysis, "resolve_asset")
    def test_resolver_exception_preserves_legacy_flow(
        self,
        resolve_asset,
        impl,
    ):
        resolve_asset.side_effect = RuntimeError(
            "resolver unavailable"
        )

        impl.return_value = {"intent": "latest_mes"}

        payload = analysis.AssistantAskRequest(
            vraag="laatste meshoogte R5",
            band_code="R5",
        )

        result = analysis.analysis_assistant_ask(payload)

        impl.assert_called_once()

        self.assertEqual(
            result["asset_resolution"]["status"],
            "unavailable",
        )
        self.assertIsNone(result["asset_context"])


if __name__ == "__main__":
    unittest.main()
