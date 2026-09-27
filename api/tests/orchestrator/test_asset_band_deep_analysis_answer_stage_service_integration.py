import ast
import inspect

import pytest

from app.orchestrator import service
from app.orchestrator.asset_band_deep_analysis_answer_stage import (
    AssetBandDeepAnalysisAnswerStageResult,
)


class Fatal(BaseException):
    pass


def _payload(*, intent="band_deep_analysis", message="generic"):
    return {
        "asset_resolution": {},
        "asset_context": {
            "customer_code": "C",
            "site_code": "S",
            "area_name": "A",
            "area_code": "AC",
            "installation_name": "I",
            "installation_code": "IC",
            "band_code_display": "B",
        },
        "intent": intent,
        "message": message,
        "gecombineerde_slijtage": [
            {
                "scraper_type_norm": "R",
                "scraper_family": "R",
                "position_display": "P",
                "laatste_inspectiedatum": "2099-01-01",
                "meshoogte_mm": 7,
            }
        ],
        "forecast_3mm": [],
    }


def _answer(payload, requested=None, action="analysis_assistant"):
    return service._build_user_answer(
        [{"action": action, "result": payload}],
        requested,
    )


def test_exact_selector_passes_identity_header_and_normalized_requested_then_returns_directly(
    monkeypatch,
):
    payload = _payload()
    calls = []

    def display(name, code):
        calls.append(("display", name, code))
        return f"{name}/{code}"

    def run(selected, header, requested):
        calls.append(("stage", selected, header, requested))
        return AssetBandDeepAnalysisAnswerStageResult(answer="stage answer")

    monkeypatch.setattr(service, "_display_name_code", display)
    monkeypatch.setattr(
        service,
        "run_asset_band_deep_analysis_answer_stage",
        run,
    )
    assert _answer(
        payload,
        [" Lifecycle_Trend ", "LIFECYCLE_TREND", " uncertainties "],
    ) == "stage answer"

    assert calls[:2] == [
        ("display", "A", "AC"),
        ("display", "I", "IC"),
    ]
    assert len(calls) == 3
    _, selected, header, requested = calls[2]
    assert selected is payload
    assert header == (
        "Klant: C",
        "Plaats: S",
        "Gebied: A/AC",
        "Installatie: I/IC",
        "Bandnummer: B",
    )
    assert isinstance(header, tuple)
    assert requested == {"lifecycle_trend", "uncertainties"}


@pytest.mark.parametrize(
    ("action", "intent"),
    [
        ("ANALYSIS_ASSISTANT", "band_deep_analysis"),
        ("analysis_assistant", " band_deep_analysis"),
        ("analysis_assistant", "Band_Deep_Analysis"),
        ("other", "band_deep_analysis"),
    ],
)
def test_selector_is_exact_and_does_not_call_stage(monkeypatch, action, intent):
    monkeypatch.setattr(
        service,
        "run_asset_band_deep_analysis_answer_stage",
        lambda *_: pytest.fail("stage reached"),
    )
    assert _answer(_payload(intent=intent), action=action).endswith("generic")


def test_exact_none_falls_through_to_generic_asset_presentation(monkeypatch):
    calls = []

    def run(*args):
        calls.append(args)
        return AssetBandDeepAnalysisAnswerStageResult(answer=None)

    monkeypatch.setattr(
        service,
        "run_asset_band_deep_analysis_answer_stage",
        run,
    )
    payload = _payload()
    assert _answer(payload) == (
        "Klant: C\nPlaats: S\nGebied: A (AC)\nInstallatie: I (IC)"
        "\nBandnummer: B\n\ngeneric"
    )
    assert len(calls) == 1
    assert calls[0][0] is payload


def test_fresh_header_and_requested_per_call_with_one_production_callsite(monkeypatch):
    captured = []

    def run(selected, header, requested):
        captured.append((selected, header, requested))
        return AssetBandDeepAnalysisAnswerStageResult(answer="done")

    monkeypatch.setattr(
        service,
        "run_asset_band_deep_analysis_answer_stage",
        run,
    )
    payload = _payload()
    requested = [" Uncertainties "]
    assert _answer(payload, requested) == "done"
    assert _answer(payload, requested) == "done"

    assert len(captured) == 2
    assert captured[0][0] is payload and captured[1][0] is payload
    assert captured[0][1] == captured[1][1]
    assert captured[0][1] is not captured[1][1]
    assert captured[0][2] == captured[1][2] == {"uncertainties"}
    assert captured[0][2] is not captured[1][2]
    assert requested == [" Uncertainties "]

    tree = ast.parse(inspect.getsource(service))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and ast.unparse(node.func)
        == "run_asset_band_deep_analysis_answer_stage"
    ]
    assert len(calls) == 1
    assert [ast.unparse(argument) for argument in calls[0].args] == [
        "asset_result",
        "tuple(answer_lines)",
        "requested",
    ]


@pytest.mark.parametrize("error", [RuntimeError("boom"), Fatal("boom")])
def test_stage_exception_and_baseexception_propagate_unchanged(monkeypatch, error):
    def run(*_args):
        raise error

    monkeypatch.setattr(
        service,
        "run_asset_band_deep_analysis_answer_stage",
        run,
    )
    with pytest.raises(type(error)) as raised:
        _answer(_payload())
    assert raised.value is error
