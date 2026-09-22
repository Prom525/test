import ast
import inspect

import pytest

from app.orchestrator import service
from app.orchestrator.asset_maintenance_positions_answer_stage import (
    AssetMaintenancePositionsAnswerStageResult,
)


class Fatal(BaseException):
    pass


class SequentialIntent(dict):
    def __init__(self, intents, **payload):
        super().__init__(payload)
        self.intents = iter(intents)
        self.intent_calls = 0

    def get(self, key, default=None):
        if key == "intent":
            self.intent_calls += 1
            return next(self.intents)
        return super().get(key, default)


def _row():
    return {
        "scraper_types_clean": "R",
        "position_hint": "P",
        "cycle_end": "2099-01-02",
        "prioriteit": 1,
        "eind_meshoogte_mm": 7,
        "meetpunten": 3,
        "geschatte_vervangdatum_bij_3mm": "2099-06-01",
        "prestatie_vervangmoment": "",
        "status_6mm": "",
        "status_3mm": "",
    }


def _payload(rows=None, intent="maintenance_positions", message="generic"):
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
        "resultaat": [_row()] if rows is None else rows,
    }


def _answer(payload, action="analysis_assistant"):
    return service._build_user_answer(
        [{"action": action, "result": payload}]
    )


def test_exact_selector_passes_payload_identity_and_tuple_header_then_returns_directly(
    monkeypatch,
):
    payload = _payload()
    direct = object()
    calls = []

    def display(name, code):
        calls.append(("display", name, code))
        return f"{name}/{code}"

    def run(selected, header):
        calls.append(("stage", selected, header))
        return AssetMaintenancePositionsAnswerStageResult(answer=direct)

    monkeypatch.setattr(service, "_display_name_code", display)
    monkeypatch.setattr(
        service,
        "run_asset_maintenance_positions_answer_stage",
        run,
    )
    answer = _answer(payload)

    assert answer is direct
    assert calls[:2] == [
        ("display", "A", "AC"),
        ("display", "I", "IC"),
    ]
    assert len(calls) == 3
    _, selected, header = calls[2]
    assert selected is payload
    assert header == (
        "Klant: C",
        "Plaats: S",
        "Gebied: A/AC",
        "Installatie: I/IC",
        "Bandnummer: B",
    )
    assert isinstance(header, tuple)


@pytest.mark.parametrize(
    ("action", "intent"),
    [
        ("ANALYSIS_ASSISTANT", "maintenance_positions"),
        ("analysis_assistant", " maintenance_positions"),
        ("analysis_assistant", "MAINTENANCE_POSITIONS"),
        ("other", "maintenance_positions"),
    ],
)
def test_selector_is_exact_and_does_not_call_stage(
    monkeypatch, action, intent
):
    monkeypatch.setattr(
        service,
        "run_asset_maintenance_positions_answer_stage",
        lambda *_: pytest.fail("stage reached"),
    )
    assert _answer(_payload(intent=intent), action).endswith("generic")


def test_exact_none_falls_through_to_deep_analysis_and_generic(monkeypatch):
    calls = []

    def run(*args):
        calls.append(args)
        return AssetMaintenancePositionsAnswerStageResult(answer=None)

    monkeypatch.setattr(
        service,
        "run_asset_maintenance_positions_answer_stage",
        run,
    )

    deep = SequentialIntent(
        ["other", "other", "maintenance_positions", "band_deep_analysis"],
        **_payload([]),
    )
    deep["gecombineerde_slijtage"] = [
        {
            "scraper_type_norm": "R",
            "scraper_family": "R",
            "position_display": "P",
            "laatste_inspectiedatum": "2099-01-01",
            "meshoogte_mm": 7,
        }
    ]
    deep["forecast_3mm"] = []
    assert "Vervangadvies:" in _answer(deep)
    assert deep.intent_calls == 4

    generic = SequentialIntent(
        ["other", "other", "maintenance_positions", "other"],
        **_payload([]),
    )
    assert _answer(generic).endswith("generic")
    assert generic.intent_calls == 4
    assert len(calls) == 2
    assert calls[0][0] is deep and calls[1][0] is generic


def test_non_none_return_stops_before_deep_analysis(monkeypatch):
    payload = _payload()
    payload["gecombineerde_slijtage"] = object()
    direct = object()
    monkeypatch.setattr(
        service,
        "run_asset_maintenance_positions_answer_stage",
        lambda selected, header: AssetMaintenancePositionsAnswerStageResult(
            answer=direct
        ),
    )
    assert _answer(payload) is direct


def test_fresh_header_snapshot_per_call_and_single_production_callsite(monkeypatch):
    captured = []

    def run(selected, header):
        captured.append((selected, header))
        return AssetMaintenancePositionsAnswerStageResult(answer="done")

    monkeypatch.setattr(
        service,
        "run_asset_maintenance_positions_answer_stage",
        run,
    )
    payload = _payload()
    assert _answer(payload) == "done"
    assert _answer(payload) == "done"

    assert len(captured) == 2
    assert captured[0][0] is payload and captured[1][0] is payload
    assert captured[0][1] == captured[1][1]
    assert captured[0][1] is not captured[1][1]

    tree = ast.parse(inspect.getsource(service))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and ast.unparse(node.func)
        == "run_asset_maintenance_positions_answer_stage"
    ]
    assert len(calls) == 1
    assert [ast.unparse(argument) for argument in calls[0].args] == [
        "asset_result",
        "tuple(answer_lines)",
    ]


@pytest.mark.parametrize("site", ["runner", "answer"])
@pytest.mark.parametrize("error", [RuntimeError("boom"), Fatal("boom")])
def test_stage_exception_and_baseexception_propagate_unchanged(
    monkeypatch, site, error
):
    class Result:
        @property
        def answer(self):
            raise error

    def run(*_args):
        if site == "runner":
            raise error
        return Result()

    monkeypatch.setattr(
        service,
        "run_asset_maintenance_positions_answer_stage",
        run,
    )
    with pytest.raises(type(error)) as raised:
        _answer(_payload())
    assert raised.value is error

