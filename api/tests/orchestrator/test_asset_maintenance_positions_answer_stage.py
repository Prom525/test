import ast
import builtins
import copy
import inspect
from dataclasses import fields

import pytest

from app.orchestrator import asset_maintenance_positions_answer_stage as stage


HEADER = ("Klant: SYNTH", "Bandnummer: B-SYNTH")
LEGACY_DASH = "\u00e2\u20ac\u201d"


class Fatal(BaseException):
    pass


class RaisingGet(dict):
    def __init__(self, error):
        super().__init__()
        self.error = error

    def get(self, key, default=None):
        if key == "resultaat":
            raise self.error
        return super().get(key, default)


class CountingRow(dict):
    def __init__(self, values):
        super().__init__(values)
        self.calls = []

    def get(self, key, default=None):
        self.calls.append((key, default))
        return super().get(key, default)


def _row(
    *,
    scraper="R",
    position="P",
    cycle_end="2099-01-02",
    priority=1,
    height=7,
    points=3,
    forecast="2099-06-01",
    performance="",
    status_6mm="",
    status_3mm="",
):
    return {
        "scraper_types_clean": scraper,
        "position_hint": position,
        "cycle_end": cycle_end,
        "prioriteit": priority,
        "eind_meshoogte_mm": height,
        "meetpunten": points,
        "geschatte_vervangdatum_bij_3mm": forecast,
        "prestatie_vervangmoment": performance,
        "status_6mm": status_6mm,
        "status_3mm": status_3mm,
    }


def _run(rows, header=HEADER):
    return stage.run_asset_maintenance_positions_answer_stage(
        {"resultaat": rows},
        header,
    ).answer


def test_contract_signature_imports_and_fresh_header_copy_are_exact():
    result = stage.AssetMaintenancePositionsAnswerStageResult(answer=None)
    assert [field.name for field in fields(result)] == ["answer"]
    with pytest.raises(Exception):
        result.answer = "changed"

    assert list(
        inspect.signature(
            stage.run_asset_maintenance_positions_answer_stage
        ).parameters
    ) == ["asset_result", "asset_header_lines"]
    tree = ast.parse(inspect.getsource(stage))
    imports = [
        node.module
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
    ]
    assert imports == ["dataclasses", "typing"]
    runner = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "run_asset_maintenance_positions_answer_stage"
    )
    assert ast.unparse(runner.body[0]) == (
        "answer_lines = list(asset_header_lines)"
    )


@pytest.mark.parametrize(
    "rows",
    [None, {}, (), "rows", 0, False, object(), [], [None, "row"]],
)
def test_non_list_or_no_usable_position_returns_exact_none(rows):
    assert _run(rows) is None


def test_exact_dedupe_first_wins_sort_actions_forecast_and_presentation():
    first = _row(
        scraper=" R ",
        position=" NORTH ",
        height=5.678,
        status_6mm=" OP_OF_ONDER_6MM ",
    )
    rows = [
        _row(
            scraper="U",
            position="SOUTH",
            priority=2,
            height=None,
            points=9,
            forecast="2099-09-09",
        ),
        first,
        dict(
            first,
            eind_meshoogte_mm=2,
            geschatte_vervangdatum_bij_3mm="IGNORED",
        ),
    ]
    assert _run(rows) == (
        "Klant: SYNTH\nBandnummer: B-SYNTH"
        "\n\nOnderhoudsprioriteit:"
        "\n\n1. R " + LEGACY_DASH + " NORTH"
        "\n   Laatste gemeten meshoogte: 5.68 mm op 2099-01-02"
        "\n   Actie: Prestatiegrens controleren"
        "\n   Prognose 3 mm: rond 2099-06-01"
        "\n   Onderbouwing: 3 meetpunten"
        "\n\n2. U " + LEGACY_DASH + " SOUTH"
        "\n   Laatste gemeten meshoogte: niet beschikbaar"
        "\n   Actie: Trend controleren; geen bruikbare actuele eindmeting"
        "\n   Geen betrouwbare forecast beschikbaar"
        "\n\nLet op: 3 mm is de vervanggrens. De 6 mm-grens is een "
        "prestatiecontrole en betekent niet automatisch vervangen."
    )


def test_inputs_are_not_mutated_and_each_call_uses_fresh_state_once():
    row = CountingRow(_row())
    rows = [row]
    payload = {"resultaat": rows}
    header = ("cafÃ©",)
    before_payload = copy.deepcopy(payload)

    first = stage.run_asset_maintenance_positions_answer_stage(
        payload, header
    ).answer
    first_calls = list(row.calls)
    row.calls.clear()
    second = stage.run_asset_maintenance_positions_answer_stage(
        payload, header
    ).answer

    expected_calls = [
        ("scraper_types_clean", None),
        ("position_hint", None),
        ("cycle_end", None),
        ("prioriteit", None),
        ("eind_meshoogte_mm", None),
        ("meetpunten", None),
        ("geschatte_vervangdatum_bij_3mm", None),
        ("prestatie_vervangmoment", None),
        ("status_6mm", None),
        ("status_3mm", None),
    ]
    assert first == second
    assert first.startswith("cafÃ©\n\nOnderhoudsprioriteit:")
    assert first_calls == expected_calls
    assert row.calls == expected_calls
    assert payload == before_payload
    assert payload["resultaat"] is rows and rows[0] is row
    assert header == ("cafÃ©",)


def test_tuple_header_is_copied_to_a_distinct_fresh_list_per_call(monkeypatch):
    real_list = builtins.list

    class TrackingList(real_list):
        created = []
        initial_values = []

        def __init__(self, values=()):
            super().__init__(values)
            self.created.append(self)
            self.initial_values.append(tuple(self))

    rows = TrackingList([_row()])
    TrackingList.created.clear()
    TrackingList.initial_values.clear()
    monkeypatch.setattr(stage, "list", TrackingList, raising=False)

    assert _run(rows).startswith("Klant: SYNTH")
    assert _run(rows).startswith("Klant: SYNTH")
    assert len(TrackingList.created) == 2
    assert TrackingList.created[0] is not TrackingList.created[1]
    assert TrackingList.initial_values == [HEADER, HEADER]


@pytest.mark.parametrize("error", [RuntimeError("boom"), Fatal("boom")])
def test_exception_and_baseexception_propagate_unchanged(error):
    with pytest.raises(type(error)) as raised:
        stage.run_asset_maintenance_positions_answer_stage(
            RaisingGet(error), HEADER
        )
    assert raised.value is error
