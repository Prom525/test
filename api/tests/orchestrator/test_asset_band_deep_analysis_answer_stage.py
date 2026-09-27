import ast
import copy
import inspect
from dataclasses import fields

import pytest

from app.orchestrator import asset_band_deep_analysis_answer_stage as stage


HEADER = ("Klant: SYNTH", "Bandnummer: B-SYNTH")


class Fatal(BaseException):
    pass


class RaisingGet(dict):
    def __init__(self, error):
        super().__init__()
        self.error = error

    def get(self, key, default=None):
        if key == "gecombineerde_slijtage":
            raise self.error
        return super().get(key, default)


def _position(**overrides):
    return {
        "scraper_type_norm": "R-SYNTH",
        "scraper_family": "R",
        "position_display": "P-SYNTH",
        "laatste_inspectiedatum": "2099-01-02",
        "meshoogte_mm": 5,
        "onderhoudsadvies_unified": "MONITOREN",
        **overrides,
    }


def _forecast(**overrides):
    return {
        "scraper_type_norm": "R-FORECAST",
        "meetpunten": 3,
        "eind_meshoogte_mm": 5,
        "slijtage_mm_per_dag": 0.1,
        "geschatte_dagen_tot_3mm": 20,
        "geschatte_vervangdatum_bij_3mm": "2099-06-01",
        **overrides,
    }


def _run(asset_result, requested=frozenset()):
    return stage.run_asset_band_deep_analysis_answer_stage(
        asset_result,
        HEADER,
        set(requested),
    ).answer


def test_contract_signature_imports_frozen_result_and_fresh_header_copy_are_exact():
    result = stage.AssetBandDeepAnalysisAnswerStageResult(answer=None)
    assert [field.name for field in fields(result)] == ["answer"]
    with pytest.raises(Exception):
        result.answer = "changed"

    assert list(
        inspect.signature(stage.run_asset_band_deep_analysis_answer_stage).parameters
    ) == ["asset_result", "asset_header_lines", "requested"]
    tree = ast.parse(inspect.getsource(stage))
    assert [
        node.module
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
    ] == ["dataclasses", "typing"]
    runner = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "run_asset_band_deep_analysis_answer_stage"
    )
    assert ast.unparse(runner.body[0]) == "answer_lines = list(asset_header_lines)"


def test_direct_stage_preserves_deep_analysis_text_facets_and_input_identity():
    asset_result = {
        "gecombineerde_slijtage": [_position()],
        "forecast_3mm": [_forecast()],
        "lifecycle": [
            {
                "inspected_on": "2099-01-01",
                "scraper_type_norm": "R-SYNTH",
                "position_hint": "P-SYNTH",
                "cycle_id": "C-1",
                "canonical_inspection_key": "I-1",
                "meshoogte_mm": 6,
                "replace_event": True,
            }
        ],
    }
    before = copy.deepcopy(asset_result)

    answer = _run(
        asset_result,
        {"lifecycle_trend", "replacement_events", "uncertainties"},
    )

    assert answer == (
        "Klant: SYNTH\nBandnummer: B-SYNTH"
        "\n\nVervangadvies:"
        "\n\n1. R-SYNTH â€” P-SYNTH"
        "\n   Laatste gemeten meshoogte: 5 mm op 2099-01-02"
        "\n   Advies: Monitoren"
        "\n   Prognose 3 mm: rond 2099-06-01"
        "\n   Onderbouwing: 3 meetpunten"
        "\n\nLet op: 3 mm is de vervanggrens. Een advies 'vervanging "
        "voorbereiden' betekent niet dat het mes nu al de vervanggrens heeft bereikt."
        "\n\nLifecycle-trend: 1 metingen verdeeld over 1 cycli."
        "\n- R-SYNTH - P-SYNTH - cyclus C-1: 1 meting, 2099-01-01 6 mm"
        "\n\nGeregistreerde vervangevents: 2099-01-01"
        "\n\nOnzekerheden:"
        "\n- Voor alle gepresenteerde posities is volgens de huidige "
        "forecastcriteria een 3 mm-prognose beschikbaar."
        "\n- Historische lifecycle-posities worden alleen gebruikt voor trend "
        "en vervangevents; actuele meshoogtes en vervangadvies hierboven "
        "worden daar niet uit afgeleid."
    )
    assert asset_result == before


@pytest.mark.parametrize(
    "positions",
    [None, {}, (), "rows", 0, False, object(), [], [None, "row"]],
)
def test_nonrenderable_position_shapes_return_exact_none(positions):
    assert _run({"gecombineerde_slijtage": positions, "forecast_3mm": []}) is None


@pytest.mark.parametrize("error", [RuntimeError("boom"), Fatal("boom")])
def test_exception_and_baseexception_propagate_unchanged(error):
    with pytest.raises(type(error)) as raised:
        _run(RaisingGet(error))
    assert raised.value is error
