"""Characterize only the inline ``lifecycle`` asset presenter."""
from __future__ import annotations

import ast
import builtins
import copy
import inspect
from collections import UserDict
from decimal import Decimal

import pytest

from app.orchestrator import asset_lifecycle_answer_stage, service


LEGACY_DASH = "\u00e2\u20ac\u201d"
LEGACY_ARROW = "\u00e2\u2020\u2019"

HEADER = (
    "Klant: CUSTOMER-SYNTH\n"
    "Plaats: SITE-SYNTH\n"
    "Gebied: Area Synthetic (AREA-SYNTH)\n"
    "Installatie: Installation Synthetic (INST-SYNTH)\n"
    "Bandnummer: BAND-SYNTH"
)


class Fatal(BaseException):
    """Non-Exception sentinel used to pin uncaught propagation."""


class DictSubclass(dict):
    pass


class ListSubclass(list):
    pass


class StringifiesTo:
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return self.value


class RaisingBool:
    def __init__(self, error):
        self.error = error

    def __bool__(self):
        raise self.error


class RaisingStr:
    def __init__(self, error):
        self.error = error

    def __str__(self):
        raise self.error


class RaisingGet(dict):
    def __init__(self, key, error, values):
        super().__init__(values)
        self.key = key
        self.error = error

    def get(self, key, default=None):
        if key == self.key:
            raise self.error
        return super().get(key, default)


class RaisingList(list):
    def __init__(self, error):
        super().__init__([object()])
        self.error = error

    def __iter__(self):
        raise self.error


class RaisingStringInt(int):
    error = None

    def __str__(self):
        raise self.error


class RaisingFloatInt(int):
    error = None

    def __float__(self):
        raise self.error


class RaisingFormattedFloat(float):
    error = None

    def is_integer(self):
        raise self.error


class SequentialIntent(DictSubclass):
    def __init__(self, values, **payload):
        super().__init__(payload)
        self.values = iter(values)
        self.intent_calls = 0

    def get(self, key, default=None):
        if key == "intent":
            self.intent_calls += 1
            return next(self.values)
        return super().get(key, default)


class CountingRow(DictSubclass):
    def __init__(self, values):
        super().__init__(values)
        self.calls = []

    def get(self, key, default=None):
        self.calls.append((key, default))
        return super().get(key, default)


def _row(
    inspected_on="2099-01-02",
    *,
    scraper="R-SYNTH",
    position="P-SYNTH",
    cycle="C-SYNTH",
    canonical="I-SYNTH",
    height=7,
    replace=False,
    **extra,
):
    return {
        "inspected_on": inspected_on,
        "scraper_type_norm": scraper,
        "position_hint": position,
        "cycle_id": cycle,
        "canonical_inspection_key": canonical,
        "meshoogte_mm": height,
        "replace_event": replace,
        **extra,
    }


def _payload(rows, **overrides):
    return {
        "asset_resolution": {"status": "resolved"},
        "asset_context": {
            "customer_code": "CUSTOMER-SYNTH",
            "site_code": "SITE-SYNTH",
            "area_name": "Area Synthetic",
            "area_code": "AREA-SYNTH",
            "installation_name": "Installation Synthetic",
            "installation_code": "INST-SYNTH",
            "band_code_display": "BAND-SYNTH",
        },
        "entities": {"band_code": "ENTITY-BAND"},
        "intent": "lifecycle",
        "message": "generic fallback marker",
        "resultaat": rows,
        **overrides,
    }


def _results(rows, *, action="analysis_assistant", **overrides):
    return [{"action": action, "result": _payload(rows, **overrides)}]


def _asset_route_nodes():
    function = ast.parse(inspect.getsource(service._build_user_answer)).body[0]
    asset_if = next(
        node
        for node in function.body
        if isinstance(node, ast.If)
        and ast.unparse(node.test) == "asset_result is not None"
    )
    route_values = {
        "inspection_summary",
        "lifecycle",
        "maintenance_positions",
        "band_deep_analysis",
    }
    routes = []
    for node in asset_if.body:
        if not isinstance(node, ast.If):
            continue
        values = [
            constant.value
            for constant in ast.walk(node.test)
            if isinstance(constant, ast.Constant)
            and constant.value in route_values
        ]
        if values:
            routes.append((values[0], node))
    return function, asset_if, routes


def test_ast_pins_inline_route_order_and_mechanical_extraction_boundary():
    function, asset_if, routes = _asset_route_nodes()
    assert [name for name, _ in routes] == [
        "inspection_summary",
        "lifecycle",
        "maintenance_positions",
        "band_deep_analysis",
    ]
    lifecycle = dict(routes)["lifecycle"]
    assert [type(node) for node in lifecycle.body] == [ast.Assign, ast.If]
    assert ast.unparse(lifecycle.body[0]) == (
        "lifecycle_stage = run_asset_lifecycle_answer_stage(asset_result, "
        "tuple(answer_lines), requested)"
    )
    assert ast.unparse(lifecycle.body[1].test) == (
        "lifecycle_stage.answer is not None"
    )
    assert ast.unparse(lifecycle.body[1].body[0]) == (
        "return lifecycle_stage.answer"
    )
    body_tree = ast.Module(body=lifecycle.body, type_ignores=[])
    calls = {
        ast.unparse(node.func)
        for node in ast.walk(body_tree)
        if isinstance(node, ast.Call)
    }
    assert calls == {"run_asset_lifecycle_answer_stage", "tuple"}
    assert "_display_name_code" not in calls

    runner = ast.parse(
        inspect.getsource(
            asset_lifecycle_answer_stage.run_asset_lifecycle_answer_stage
        )
    ).body[0]
    assert ast.unparse(runner.body[0]) == (
        "answer_lines = list(asset_header_lines)"
    )
    assert ast.unparse(runner.body[1]) == (
        "raw_rows = asset_result.get('resultaat')"
    )
    assert ast.unparse(asset_if.test) == "asset_result is not None"
    assert any(
        isinstance(node, ast.For) and ast.unparse(node.iter) == "results"
        for node in function.body
    )


def test_inspection_stage_fallthrough_precedes_lifecycle_and_success_stops_later_routes(monkeypatch):
    payload = SequentialIntent(
        ["inspection_summary", "lifecycle"],
        **_payload([_row()]),
    )
    calls = []

    class Result:
        answer = None

    def inspection_stage(selected, header):
        calls.append((selected, header))
        return Result()

    monkeypatch.setattr(service, "run_asset_inspection_summary_answer_stage", inspection_stage)
    answer = service._build_user_answer(
        [{"action": "analysis_assistant", "result": payload}]
    )
    assert answer.startswith(HEADER + "\n\nTrendgegevens: 1 metingen")
    assert calls == [(payload, tuple(HEADER.splitlines()))]
    assert payload.intent_calls == 2


def test_empty_lifecycle_falls_through_maintenance_and_band_routes_then_generic():
    maintenance = SequentialIntent(
        ["other", "lifecycle", "maintenance_positions"],
        **_payload(
            [
                {
                    "scraper_types_clean": "M-SYNTH",
                    "position_hint": "P-M",
                    "cycle_end": "2099-01-02",
                    "prioriteit": 1,
                    "eind_meshoogte_mm": 7,
                    "meetpunten": 2,
                }
            ]
        ),
    )
    answer = service._build_user_answer(
        [{"action": "analysis_assistant", "result": maintenance}]
    )
    assert "Onderhoudsprioriteit:" in answer
    assert "Trendgegevens:" not in answer
    assert maintenance.intent_calls == 3

    deep = SequentialIntent(
        ["other", "lifecycle", "maintenance_positions", "band_deep_analysis"],
        **_payload(
            [],
            gecombineerde_slijtage=[
                {
                    "scraper_type_norm": "R-DEEP",
                    "scraper_family": "R",
                    "position_display": "P-DEEP",
                    "laatste_inspectiedatum": "2099-01-01",
                    "meshoogte_mm": 7,
                }
            ],
            forecast_3mm=[],
        ),
    )
    answer = service._build_user_answer(
        [{"action": "analysis_assistant", "result": deep}]
    )
    assert "Vervangadvies:" in answer
    assert deep.intent_calls == 4

    generic = SequentialIntent(
        ["other", "lifecycle", "maintenance_positions", "band_deep_analysis"],
        **_payload([], gecombineerde_slijtage=[], forecast_3mm=[]),
    )
    assert service._build_user_answer(
        [{"action": "analysis_assistant", "result": generic}]
    ) == (HEADER + "\n\ngeneric fallback marker")
    assert generic.intent_calls == 4


def test_first_asset_match_wins_and_asset_preempts_all_non_asset_dispatch(monkeypatch):
    for name in (
        "run_diagnostics_answer_stage",
        "run_analysis_scope_answer_stage",
        "run_multi_product_answer_stage",
        "run_org_answer_stage",
        "run_technical_cema_answer_stage",
    ):
        monkeypatch.setattr(
            service,
            name,
            lambda *_a, **_k: pytest.fail("non-asset dispatch reached"),
        )

    class Untouched:
        def get(self, _key):
            raise AssertionError("prescan continued after its first asset match")

    first = _payload([], message="first asset")
    later = _payload([_row()], message="later asset")
    answer = service._build_user_answer(
        [
            {"action": "diagnostics_assistant", "result": {}},
            {"action": "analysis_assistant", "result": first},
            {"action": "analysis_assistant", "result": later},
            Untouched(),
        ]
    )
    assert answer == HEADER + "\n\nfirst asset"


@pytest.mark.parametrize(
    ("action", "intent"),
    [
        (" analysis_assistant", "lifecycle"),
        ("analysis_assistant ", "lifecycle"),
        ("Analysis_Assistant", "lifecycle"),
        (b"analysis_assistant", "lifecycle"),
        (None, "lifecycle"),
        (0, "lifecycle"),
        ("analysis_assistant", " lifecycle"),
        ("analysis_assistant", "lifecycle "),
        ("analysis_assistant", "Lifecycle"),
        ("analysis_assistant", b"lifecycle"),
        ("analysis_assistant", None),
        ("analysis_assistant", 0),
    ],
)
def test_action_and_intent_are_exact_after_or_then_string_conversion(action, intent):
    answer = service._build_user_answer(
        _results([_row()], action=action, intent=intent)
    )
    assert answer == HEADER + "\n\ngeneric fallback marker"


def test_action_and_intent_accept_objects_stringifying_to_exact_selectors():
    answer = service._build_user_answer(
        _results(
            [_row()],
            action=StringifiesTo("analysis_assistant"),
            intent=StringifiesTo("lifecycle"),
        )
    )
    assert "Trendgegevens: 1 metingen verdeeld over 1 cycli." in answer


@pytest.mark.parametrize(
    "rows",
    [None, {}, DictSubclass(), (), "rows", 0, False, object(), UserDict()],
)
def test_resultaat_requires_list_or_subclass_and_other_outer_shapes_fall_through(rows):
    assert service._build_user_answer(_results(rows)) == (
        HEADER + "\n\ngeneric fallback marker"
    )


def test_list_and_dict_subclasses_are_accepted_while_malformed_rows_are_skipped():
    rows = ListSubclass(
        [None, "row", (), [], UserDict(), DictSubclass(_row())]
    )
    answer = service._build_user_answer(_results(rows))
    assert answer.startswith(HEADER + "\n\nTrendgegevens: 1 metingen")
    assert answer.endswith("- R-SYNTH " + LEGACY_DASH + " P-SYNTH " + LEGACY_DASH + " cyclus C-SYNTH: 1 meting, 2099-01-02 7 mm")


@pytest.mark.parametrize(
    "row",
    [
        _row(inspected_on=None),
        _row(inspected_on=False),
        _row(inspected_on=0),
        _row(inspected_on=""),
        _row(inspected_on="   "),
        _row(scraper=None),
        _row(scraper=False),
        _row(scraper=0),
        _row(scraper=""),
        _row(scraper="   "),
        _row(height=None),
        _row(height=True),
        _row(height=False),
        _row(height="7"),
        _row(height=Decimal("7")),
        _row(height=7 + 0j),
        _row(height=[]),
        _row(height={}),
    ],
)
def test_required_nested_fields_and_numeric_gate_reject_unusable_rows(row):
    assert service._build_user_answer(_results([row])) == (
        HEADER + "\n\ngeneric fallback marker"
    )


def test_only_exact_field_names_are_used_and_optional_fields_do_not_gate():
    aliases_only = {
        "document_date": "9999",
        "scraper_type_raw": "RAW",
        "position_display": "DISPLAY",
        "inspection_key": "KEY",
        "meshoogte_mm": 7,
    }
    optional_missing = {
        "inspected_on": "2099",
        "scraper_type_norm": "R",
        "meshoogte_mm": 0,
    }
    answer = service._build_user_answer(_results([aliases_only, optional_missing]))
    assert answer == (
        HEADER
        + "\n\nTrendgegevens: 1 metingen verdeeld over 1 cycli."
        + "\n\nHistorie per schraper/cyclus:"
        + "\n- R: 1 meting, 2099 0 mm"
    )


def test_string_normalization_none_falsy_bytes_and_cycle_special_case_are_exact():
    rows = [
        _row(" 2099 ", scraper=" R ", position=" P ", cycle=None, canonical=0, height=1),
        _row("2099", scraper="R", position="P", cycle="", canonical="", height=1),
        _row("2099", scraper="R", position=False, cycle=0, canonical=False, height=2),
        _row("2099", scraper="R", position=0, cycle=False, canonical=None, height=3),
        _row(b"2098", scraper=b"U", position=b"PX", cycle=b" C ", height=4),
    ]
    answer = service._build_user_answer(_results(rows))
    assert "Trendgegevens: 4 metingen verdeeld over 4 cycli." in answer
    assert "- R " + LEGACY_DASH + " P: 1 meting, 2099 1 mm" in answer
    assert "- R " + LEGACY_DASH + " cyclus False: 1 meting, 2099 3 mm" in answer
    assert "- R " + LEGACY_DASH + " cyclus 0: 1 meting, 2099 2 mm" in answer
    assert "b'U' " + LEGACY_DASH + " b'PX' " + LEGACY_DASH + " cyclus b' C '" in answer


def test_dedupe_uses_exact_six_string_fields_and_grouping_uses_exact_three_fields():
    base = _row()
    rows = [
        base,
        dict(base),
        _row(canonical="I-OTHER"),
        _row(scraper="U-SYNTH"),
        _row(position="P-OTHER"),
        _row(cycle="C-OTHER"),
        _row(inspected_on="2099-01-03"),
        _row(height=8),
    ]
    answer = service._build_user_answer(_results(rows))
    assert "Trendgegevens: 7 metingen verdeeld over 4 cycli." in answer
    assert (
        "- R-SYNTH "
        + LEGACY_DASH
        + " P-SYNTH "
        + LEGACY_DASH
        + " cyclus C-SYNTH: 4 metingen, 2099-01-02 7 mm "
        + LEGACY_ARROW
        + " 2099-01-03 7 mm"
    ) in answer


def test_point_and_group_sorting_rounding_units_and_stable_equal_date_order():
    rows = [
        _row("2099-01-03", scraper="B", position="P", cycle="2", height=1.234),
        _row("2099-01-01", scraper="B", position="P", cycle="2", height=3.0),
        _row("2099-01-03", scraper="B", position="P", cycle="2", canonical="2", height=9.876),
        _row("2099-01-03", scraper="Z", position="", cycle=None, height=5.0),
        _row("2099-01-03", scraper="A", position="", cycle=None, height=float("nan")),
        _row("2098", scraper="I", position="", cycle=None, height=float("inf")),
    ]
    answer = service._build_user_answer(_results(rows))
    assert answer == (
        HEADER
        + "\n\nTrendgegevens: 6 metingen verdeeld over 4 cycli."
        + "\n\nHistorie per schraper/cyclus:"
        + "\n- Z: 1 meting, 2099-01-03 5 mm"
        + "\n- B " + LEGACY_DASH + " P " + LEGACY_DASH + " cyclus 2: 3 metingen, 2099-01-01 3 mm " + LEGACY_ARROW + " 2099-01-03 9.88 mm"
        + "\n- A: 1 meting, 2099-01-03 nan mm"
        + "\n- I: 1 meting, 2098 inf mm"
    )


def test_exact_all_facets_output_request_normalization_and_replacement_sorting():
    rows = [
        _row("2099-01-03", scraper="R", position="P", cycle="C1", height=6.256),
        _row("2099-01-01", scraper="R", position="P", cycle="C1", canonical="I1", height=7),
        _row("2099-01-02", scraper="R", position="P", cycle="C2", canonical="I2", height=4),
        _row("2099-01-02", scraper="U", position="", cycle=None, canonical="IU", height=5.0),
        _row("2099-01-04", scraper="", height=None, replace=True),
        _row("2099-01-02", scraper="", height=None, replace=True),
        _row("2099-01-04", scraper="", height=None, replace=True),
    ]
    requested = [
        " Latest_Measurements ",
        "REPLACEMENT_EVENTS",
        "replacement_advice",
        "uncertainties",
        "uncertainties",
        b"latest_measurements",
    ]
    answer = service._build_user_answer(_results(rows), requested)
    assert answer == (
        HEADER
        + "\n\nTrendgegevens: 4 metingen verdeeld over 3 cycli."
        + "\n\nHistorie per schraper/cyclus:"
        + "\n- R " + LEGACY_DASH + " P " + LEGACY_DASH + " cyclus C1: 2 metingen, 2099-01-01 7 mm " + LEGACY_ARROW + " 2099-01-03 6.26 mm"
        + "\n- U: 1 meting, 2099-01-02 5 mm"
        + "\n- R " + LEGACY_DASH + " P " + LEGACY_DASH + " cyclus C2: 1 meting, 2099-01-02 4 mm"
        + "\n\nLaatste lifecycle-meting per schraper/positie:"
        + "\n- R - P: 6.26 mm op 2099-01-03"
        + "\n- U: 5 mm op 2099-01-02"
        + "\n\nGeregistreerde vervangevents: 2099-01-02, 2099-01-04"
        + "\n\nVervangadvies: niet bepaald uit deze lifecyclehistorie; hiervoor is een actuele onderhouds-/forecastanalyse nodig."
        + "\n\nOnzekerheden:"
        + "\n- De weergegeven laatste meshoogte is de meest recente lifecycle-meting per schraper/positie in deze bron; dit bevestigt niet dat de positie nog actueel actief is."
        + "\n- Deze lifecyclebron bevat geen afzonderlijke actuele vervang-/forecastanalyse; daarom wordt hier geen vervangmoment afgeleid."
    )


def test_replacement_event_identity_and_requested_empty_sentence_are_exact():
    rows = [
        _row("2099", replace=False),
        _row("2098", canonical="1", replace=1),
        _row("2097", canonical="2", replace="true"),
    ]
    answer = service._build_user_answer(_results(rows), [" replacement_events "])
    assert answer.endswith(
        "\n\nGeregistreerde vervangevents: geen in deze lifecyclebron."
    )
    assert "2098, 2099" not in answer

    rows.append(_row(" 2096 ", canonical="3", height=None, replace=True))
    answer = service._build_user_answer(_results(rows))
    assert answer.endswith("\n\nGeregistreerde vervangevents: 2096")


def test_replacement_only_and_empty_or_malformed_lists_fall_through_but_one_point_returns():
    for rows in (
        [],
        [None, "row", (), []],
        [_row(height=None, replace=True)],
        [_row(scraper="", replace=True)],
    ):
        assert service._build_user_answer(_results(rows)) == (
            HEADER + "\n\ngeneric fallback marker"
        )

    answer = service._build_user_answer(
        _results([_row()], message="forbidden", kort_resultaat="forbidden")
    )
    assert "Trendgegevens:" in answer
    assert "forbidden" not in answer


def test_display_helper_identity_no_mutation_fresh_state_and_single_execution(monkeypatch):
    sentinels = [{"sentinel": index} for index in range(4)]
    row = CountingRow(_row())
    results = _results([row])
    payload = results[0]["result"]
    context = payload["asset_context"]
    context.update(
        zip(
            ("area_name", "area_code", "installation_name", "installation_code"),
            sentinels,
        )
    )
    requested = [" Latest_Measurements "]
    before_results = copy.deepcopy(results)
    before_requested = copy.deepcopy(requested)
    calls = []

    def display(name, code):
        calls.append((name, code))
        return f"display-{len(calls)}"

    monkeypatch.setattr(service, "_display_name_code", display)
    first = service._build_user_answer(results, requested)
    first_row_calls = list(row.calls)
    row.calls.clear()
    second = service._build_user_answer(results, requested)

    assert first.replace("display-1", "display-3").replace("display-2", "display-4") == second
    assert calls == [
        (sentinels[0], sentinels[1]),
        (sentinels[2], sentinels[3]),
        (sentinels[0], sentinels[1]),
        (sentinels[2], sentinels[3]),
    ]
    assert calls[0][0] is sentinels[0] and calls[0][1] is sentinels[1]
    assert calls[1][0] is sentinels[2] and calls[1][1] is sentinels[3]
    expected_row_calls = [
        ("inspected_on", None),
        ("scraper_type_norm", None),
        ("position_hint", None),
        ("cycle_id", None),
        ("canonical_inspection_key", None),
        ("replace_event", None),
        ("meshoogte_mm", None),
    ]
    assert first_row_calls == expected_row_calls
    assert row.calls == expected_row_calls
    assert results == before_results
    assert requested == before_requested
    assert payload is results[0]["result"]
    assert payload["asset_context"] is context
    assert payload["resultaat"][0] is row


def test_no_row_limit_and_latest_position_selection_is_strictly_newer_only():
    rows = [
        _row(
            f"2099-01-{index + 1:02}",
            canonical=f"I-{index}",
            cycle=f"C-{index}",
            height=index,
        )
        for index in range(25)
    ]
    answer = service._build_user_answer(_results(rows), ["latest_measurements"])
    assert "Trendgegevens: 25 metingen verdeeld over 25 cycli." in answer
    assert answer.count("\n- R-SYNTH " + LEGACY_DASH) == 25
    assert answer.endswith("- R-SYNTH - P-SYNTH: 24 mm op 2099-01-25")


@pytest.mark.parametrize("fatal", [False, True], ids=["exception", "baseexception"])
@pytest.mark.parametrize(
    "boundary",
    [
        "requested_truth",
        "requested_iter",
        "requested_str",
        "payload_get",
        "rows_iter",
        "row_get",
        "inspected_truth",
        "inspected_str",
        "scraper_truth",
        "scraper_str",
        "position_truth",
        "position_str",
        "cycle_str",
        "canonical_truth",
        "canonical_str",
        "replacement_get",
        "height_get",
        "height_str",
        "height_float",
        "point_sort",
        "latest_sort",
        "replacement_sort",
        "format",
        "message_truth",
        "display",
    ],
)
def test_mapping_iteration_truthiness_conversion_sort_and_helper_throwables_propagate(
    monkeypatch, boundary, fatal
):
    error = Fatal(boundary) if fatal else RuntimeError(boundary)
    row = _row()
    rows = [row]
    results = _results(rows)
    payload = results[0]["result"]
    requested = None

    if boundary == "requested_truth":
        requested = RaisingBool(error)
    elif boundary == "requested_iter":
        requested = RaisingList(error)
    elif boundary == "requested_str":
        requested = [RaisingStr(error)]
    elif boundary == "payload_get":
        results[0]["result"] = RaisingGet("resultaat", error, payload)
    elif boundary == "rows_iter":
        payload["resultaat"] = RaisingList(error)
    elif boundary == "row_get":
        payload["resultaat"] = [RaisingGet("inspected_on", error, row)]
    elif boundary == "inspected_truth":
        row["inspected_on"] = RaisingBool(error)
    elif boundary == "inspected_str":
        row["inspected_on"] = RaisingStr(error)
    elif boundary == "scraper_truth":
        row["scraper_type_norm"] = RaisingBool(error)
    elif boundary == "scraper_str":
        row["scraper_type_norm"] = RaisingStr(error)
    elif boundary == "position_truth":
        row["position_hint"] = RaisingBool(error)
    elif boundary == "position_str":
        row["position_hint"] = RaisingStr(error)
    elif boundary == "cycle_str":
        row["cycle_id"] = RaisingStr(error)
    elif boundary == "canonical_truth":
        row["canonical_inspection_key"] = RaisingBool(error)
    elif boundary == "canonical_str":
        row["canonical_inspection_key"] = RaisingStr(error)
    elif boundary == "replacement_get":
        payload["resultaat"] = [RaisingGet("replace_event", error, row)]
    elif boundary == "height_get":
        payload["resultaat"] = [RaisingGet("meshoogte_mm", error, row)]
    elif boundary == "height_str":
        RaisingStringInt.error = error
        row["meshoogte_mm"] = RaisingStringInt(7)
    elif boundary == "height_float":
        RaisingFloatInt.error = error
        row["meshoogte_mm"] = RaisingFloatInt(7)
    elif boundary in {"point_sort", "latest_sort", "replacement_sort"}:
        real_sorted = builtins.sorted
        calls = 0
        target = 1 if boundary == "point_sort" else 2

        def throwing_sorted(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == target:
                raise error
            return real_sorted(*args, **kwargs)

        monkeypatch.setattr(
            asset_lifecycle_answer_stage,
            "sorted",
            throwing_sorted,
            raising=False,
        )
        if boundary == "latest_sort":
            requested = ["latest_measurements"]
        elif boundary == "replacement_sort":
            row["replace_event"] = True
    elif boundary == "format":
        RaisingFormattedFloat.error = error
        monkeypatch.setattr(
            asset_lifecycle_answer_stage,
            "float",
            RaisingFormattedFloat,
            raising=False,
        )
    elif boundary == "message_truth":
        payload["message"] = RaisingBool(error)
    elif boundary == "display":
        monkeypatch.setattr(
            service,
            "_display_name_code",
            lambda *_a: (_ for _ in ()).throw(error),
        )

    with pytest.raises(type(error), match=boundary) as raised:
        service._build_user_answer(results, requested)
    assert raised.value is error
