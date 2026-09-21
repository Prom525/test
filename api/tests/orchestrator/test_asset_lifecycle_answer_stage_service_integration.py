import ast
import inspect

import pytest

from app.orchestrator import service
from app.orchestrator.asset_lifecycle_answer_stage import (
    AssetLifecycleAnswerStageResult,
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
        "inspected_on": "2099-01-02",
        "scraper_type_norm": "R",
        "position_hint": "P",
        "cycle_id": "C",
        "canonical_inspection_key": "I",
        "meshoogte_mm": 7,
        "replace_event": False,
    }


def _payload(rows=None, intent="lifecycle", message="generic"):
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


def _answer(payload, requested=None):
    return service._build_user_answer(
        [{"action": "analysis_assistant", "result": payload}],
        requested,
    )


def test_exact_selector_passes_identity_header_and_normalized_requested_then_returns_directly(
    monkeypatch,
):
    payload = _payload()
    direct = object()
    calls = []

    def display(name, code):
        calls.append(("display", name, code))
        return f"{name}/{code}"

    def run(selected, header, requested):
        calls.append(("stage", selected, header, requested))
        return AssetLifecycleAnswerStageResult(answer=direct)

    monkeypatch.setattr(service, "_display_name_code", display)
    monkeypatch.setattr(service, "run_asset_lifecycle_answer_stage", run)
    answer = _answer(
        payload,
        [" Latest_Measurements ", "LATEST_MEASUREMENTS", " uncertainties "],
    )

    assert answer is direct
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
    assert requested == {"latest_measurements", "uncertainties"}


@pytest.mark.parametrize(
    ("action", "intent"),
    [
        ("ANALYSIS_ASSISTANT", "lifecycle"),
        ("analysis_assistant", " lifecycle"),
        ("analysis_assistant", "LIFECYCLE"),
        ("other", "lifecycle"),
    ],
)
def test_selector_is_exact_and_does_not_call_stage(
    monkeypatch, action, intent
):
    monkeypatch.setattr(
        service,
        "run_asset_lifecycle_answer_stage",
        lambda *_: pytest.fail("stage reached"),
    )
    payload = _payload(intent=intent)
    assert service._build_user_answer(
        [{"action": action, "result": payload}]
    ).endswith("generic")


def test_exact_none_falls_through_to_maintenance_deep_analysis_and_generic(
    monkeypatch,
):
    calls = []

    def run(*args):
        calls.append(args)
        return AssetLifecycleAnswerStageResult(answer=None)

    monkeypatch.setattr(service, "run_asset_lifecycle_answer_stage", run)

    maintenance = SequentialIntent(
        ["other", "lifecycle", "maintenance_positions"],
        **_payload(
            [
                {
                    "scraper_types_clean": "M",
                    "position_hint": "P",
                    "cycle_end": "2099-01-02",
                    "prioriteit": 1,
                    "eind_meshoogte_mm": 7,
                    "meetpunten": 2,
                }
            ]
        ),
    )
    assert "Onderhoudsprioriteit:" in _answer(maintenance)
    assert maintenance.intent_calls == 3

    deep = SequentialIntent(
        ["other", "lifecycle", "maintenance_positions", "band_deep_analysis"],
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
        ["other", "lifecycle", "maintenance_positions", "band_deep_analysis"],
        **_payload([]),
    )
    generic["gecombineerde_slijtage"] = []
    generic["forecast_3mm"] = []
    assert _answer(generic).endswith("generic")
    assert generic.intent_calls == 4
    assert len(calls) == 3
    assert [call[0] for call in calls] == [maintenance, deep, generic]


def test_fresh_normalized_set_and_header_snapshot_per_call_and_single_callsite(
    monkeypatch,
):
    captured = []

    def run(selected, header, requested):
        captured.append((selected, header, requested))
        return AssetLifecycleAnswerStageResult(answer="done")

    monkeypatch.setattr(service, "run_asset_lifecycle_answer_stage", run)
    payload = _payload()
    requested = [" Latest_Measurements "]
    assert _answer(payload, requested) == "done"
    assert _answer(payload, requested) == "done"

    assert len(captured) == 2
    assert captured[0][0] is payload and captured[1][0] is payload
    assert captured[0][1] == captured[1][1]
    assert captured[0][1] is not captured[1][1]
    assert captured[0][2] == captured[1][2] == {"latest_measurements"}
    assert captured[0][2] is not captured[1][2]
    assert requested == [" Latest_Measurements "]

    tree = ast.parse(inspect.getsource(service))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and ast.unparse(node.func) == "run_asset_lifecycle_answer_stage"
    ]
    assert len(calls) == 1
    assert [ast.unparse(argument) for argument in calls[0].args] == [
        "asset_result",
        "tuple(answer_lines)",
        "requested",
    ]


@pytest.mark.parametrize("error", [RuntimeError("boom"), Fatal("boom")])
def test_stage_exception_and_baseexception_propagate_unchanged(
    monkeypatch, error
):
    def run(*_args):
        raise error

    monkeypatch.setattr(service, "run_asset_lifecycle_answer_stage", run)
    with pytest.raises(type(error)) as raised:
        _answer(_payload())
    assert raised.value is error
