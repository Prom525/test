import ast
import copy
import inspect
from dataclasses import fields

import pytest

from app.orchestrator import asset_lifecycle_answer_stage as stage


HEADER = ("Klant: SYNTH", "Bandnummer: B-SYNTH")
LEGACY_DASH = "\u00e2\u20ac\u201d"
LEGACY_ARROW = "\u00e2\u2020\u2019"


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
    inspected_on="2099-01-02",
    *,
    scraper="R",
    position="P",
    cycle="C",
    canonical="I",
    height=7,
    replace=False,
):
    return {
        "inspected_on": inspected_on,
        "scraper_type_norm": scraper,
        "position_hint": position,
        "cycle_id": cycle,
        "canonical_inspection_key": canonical,
        "meshoogte_mm": height,
        "replace_event": replace,
    }


def _run(rows, requested=None, header=HEADER):
    return stage.run_asset_lifecycle_answer_stage(
        {"resultaat": rows},
        header,
        requested or set(),
    ).answer


def test_contract_signature_imports_and_fresh_header_copy_are_exact():
    result = stage.AssetLifecycleAnswerStageResult(answer=None)
    assert [field.name for field in fields(result)] == ["answer"]
    with pytest.raises(Exception):
        result.answer = "changed"

    assert list(inspect.signature(stage.run_asset_lifecycle_answer_stage).parameters) == [
        "asset_result",
        "asset_header_lines",
        "requested",
    ]
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
        and node.name == "run_asset_lifecycle_answer_stage"
    )
    assert ast.unparse(runner.body[0]) == "answer_lines = list(asset_header_lines)"


@pytest.mark.parametrize(
    "rows",
    [None, {}, (), "rows", 0, False, object(), [], [None, "row"]],
)
def test_non_list_or_no_usable_group_returns_exact_none(rows):
    assert _run(rows) is None


def test_exact_history_dedupe_sort_format_and_all_facets():
    rows = [
        _row("2099-01-03", height=6.256),
        _row("2099-01-01", canonical="I1", height=7),
        _row("2099-01-02", cycle="C2", canonical="I2", height=4),
        _row(
            "2099-01-02",
            scraper="U",
            position="",
            cycle=None,
            canonical="IU",
            height=5.0,
        ),
        _row("2099-01-04", scraper="", height=None, replace=True),
        _row("2099-01-02", scraper="", height=None, replace=True),
    ]
    answer = _run(
        rows,
        {
            "latest_measurements",
            "replacement_events",
            "replacement_advice",
            "uncertainties",
        },
    )
    assert answer == (
        "Klant: SYNTH\nBandnummer: B-SYNTH"
        "\n\nTrendgegevens: 4 metingen verdeeld over 3 cycli."
        "\n\nHistorie per schraper/cyclus:"
        "\n- R " + LEGACY_DASH + " P " + LEGACY_DASH
        + " cyclus C: 2 metingen, 2099-01-01 7 mm " + LEGACY_ARROW
        + " 2099-01-03 6.26 mm"
        "\n- U: 1 meting, 2099-01-02 5 mm"
        "\n- R " + LEGACY_DASH + " P " + LEGACY_DASH
        + " cyclus C2: 1 meting, 2099-01-02 4 mm"
        "\n\nLaatste lifecycle-meting per schraper/positie:"
        "\n- R - P: 6.26 mm op 2099-01-03"
        "\n- U: 5 mm op 2099-01-02"
        "\n\nGeregistreerde vervangevents: 2099-01-02, 2099-01-04"
        "\n\nVervangadvies: niet bepaald uit deze lifecyclehistorie; "
        "hiervoor is een actuele onderhouds-/forecastanalyse nodig."
        "\n\nOnzekerheden:"
        "\n- De weergegeven laatste meshoogte is de meest recente "
        "lifecycle-meting per schraper/positie in deze bron; dit bevestigt "
        "niet dat de positie nog actueel actief is."
        "\n- Deze lifecyclebron bevat geen afzonderlijke actuele "
        "vervang-/forecastanalyse; daarom wordt hier geen vervangmoment afgeleid."
    )


def test_none_falsy_string_float_and_replacement_identity_semantics_are_exact():
    rows = [
        _row(" 2099 ", position=False, cycle=0, canonical=False, height=1),
        _row("2099", position=0, cycle=False, canonical=None, height=2),
        _row("2098", canonical="I2", height=3.0, replace=1),
        _row("2097", canonical="I3", height=4, replace=True),
    ]
    answer = _run(rows, {"replacement_events"})
    assert "Trendgegevens: 4 metingen verdeeld over 3 cycli." in answer
    assert "cyclus 0: 1 meting, 2099 1 mm" in answer
    assert "cyclus False: 1 meting, 2099 2 mm" in answer
    assert answer.endswith("Geregistreerde vervangevents: 2097")


def test_inputs_are_not_mutated_and_each_call_uses_fresh_state_once():
    row = CountingRow(_row())
    rows = [row]
    payload = {"resultaat": rows}
    requested = {"latest_measurements"}
    header = ("cafÃ©",)
    before_payload = copy.deepcopy(payload)
    before_requested = set(requested)

    first = stage.run_asset_lifecycle_answer_stage(
        payload, header, requested
    ).answer
    first_calls = list(row.calls)
    row.calls.clear()
    second = stage.run_asset_lifecycle_answer_stage(
        payload, header, requested
    ).answer

    expected_calls = [
        ("inspected_on", None),
        ("scraper_type_norm", None),
        ("position_hint", None),
        ("cycle_id", None),
        ("canonical_inspection_key", None),
        ("replace_event", None),
        ("meshoogte_mm", None),
    ]
    assert first == second
    assert first.startswith("cafÃ©\n\nTrendgegevens:")
    assert first_calls == expected_calls
    assert row.calls == expected_calls
    assert payload == before_payload
    assert payload["resultaat"] is rows and rows[0] is row
    assert requested == before_requested
    assert header == ("cafÃ©",)


@pytest.mark.parametrize("error", [RuntimeError("boom"), Fatal("boom")])
def test_exception_and_baseexception_propagate_unchanged(error):
    with pytest.raises(type(error)) as raised:
        stage.run_asset_lifecycle_answer_stage(
            RaisingGet(error), HEADER, set()
        )
    assert raised.value is error
