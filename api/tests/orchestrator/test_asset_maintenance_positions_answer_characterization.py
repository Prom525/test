"""Characterize only the inline ``maintenance_positions`` asset presenter."""
from __future__ import annotations

import ast
import builtins
import copy
import inspect
from collections import UserDict
from decimal import Decimal

import pytest

from app.orchestrator import service


LEGACY_DASH = "\u00e2\u20ac\u201d"
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
    def __init__(self, error, values=None):
        super().__init__([object()] if values is None else values)
        self.error = error

    def __iter__(self):
        raise self.error


class RaisingFloatInt(int):
    error = None

    def __float__(self):
        raise self.error


class RaisingComparableFloat(float):
    error = None

    def __lt__(self, _other):
        raise self.error


class RaisingIsIntegerFloat(float):
    error = None

    def is_integer(self):
        raise self.error


class RaisingIntFloat(float):
    error = None

    def __int__(self):
        raise self.error


class RaisingGeInt(int):
    error = None

    def __ge__(self, _other):
        raise self.error


class RaisingFormatInt(int):
    error = None

    def __format__(self, _specification):
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


class CountingMapping(DictSubclass):
    def __init__(self, values):
        super().__init__(values)
        self.calls = []

    def get(self, key, default=None):
        self.calls.append((key, default))
        return super().get(key, default)


def _row(
    *,
    scraper="R-SYNTH",
    position="P-SYNTH",
    cycle_end="2099-01-02",
    priority=1,
    height=7,
    points=3,
    forecast="2099-06-01",
    performance="",
    status_6mm="",
    status_3mm="",
    **extra,
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
        "intent": "maintenance_positions",
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


def test_ast_pins_route_order_inline_boundary_and_smallest_future_interface():
    function, asset_if, routes = _asset_route_nodes()
    assert [name for name, _ in routes] == [
        "inspection_summary",
        "lifecycle",
        "maintenance_positions",
        "band_deep_analysis",
    ]
    maintenance = dict(routes)["maintenance_positions"]
    assert ast.unparse(maintenance.test) == (
        "asset_action == 'analysis_assistant' and "
        "str(asset_result.get('intent') or '') == 'maintenance_positions'"
    )
    assert [type(node) for node in maintenance.body] == [ast.Assign, ast.If]
    assert ast.unparse(maintenance.body[0]) == (
        "raw_rows = asset_result.get('resultaat')"
    )
    assert isinstance(maintenance.body[1].body[-1], ast.If)
    assert any(
        isinstance(node, ast.Return)
        and ast.unparse(node.value) == "'\\n'.join(answer_lines)"
        for node in ast.walk(maintenance)
    )

    calls = {
        ast.unparse(node.func)
        for node in ast.walk(maintenance)
        if isinstance(node, ast.Call)
    }
    assert {
        "str",
        "float",
        "isinstance",
        "set",
        "int",
        "enumerate",
    } <= calls
    assert not {
        "_display_name_code",
        "run_asset_inspection_summary_answer_stage",
        "run_asset_lifecycle_answer_stage",
    } & calls

    loaded_names = {
        node.id
        for node in ast.walk(maintenance)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }
    assert loaded_names & {
        "bool",
        "dict",
        "enumerate",
        "float",
        "int",
        "isinstance",
        "list",
        "set",
        "str",
        "tuple",
    } == {
        "bool",
        "dict",
        "enumerate",
        "float",
        "int",
        "isinstance",
        "list",
        "set",
        "str",
        "tuple",
    }
    # Mechanical extraction therefore needs only the selected payload and the
    # already-built header; the service keeps selection and display ownership.
    assert {"asset_result", "answer_lines"} <= loaded_names
    assert ast.unparse(asset_if.body[-2].test) == "result_text"
    assert ast.unparse(asset_if.body[-1]) == "return '\\n'.join(answer_lines)"
    assert any(
        isinstance(node, ast.For) and ast.unparse(node.iter) == "results"
        for node in function.body
    )


def test_prior_stage_fallthrough_then_maintenance_success_stops_deep_route(monkeypatch):
    payload = SequentialIntent(
        ["inspection_summary", "lifecycle", "maintenance_positions"],
        **_payload([_row()]),
    )
    calls = []

    class StageResult:
        answer = None

    def inspection_stage(selected, header):
        calls.append(("inspection", selected, header))
        return StageResult()

    def lifecycle_stage(selected, header, requested):
        calls.append(("lifecycle", selected, header, requested))
        return StageResult()

    monkeypatch.setattr(service, "run_asset_inspection_summary_answer_stage", inspection_stage)
    monkeypatch.setattr(service, "run_asset_lifecycle_answer_stage", lifecycle_stage)
    payload["gecombineerde_slijtage"] = RaisingList(
        AssertionError("deep-analysis must not be reached")
    )

    answer = service._build_user_answer(
        [{"action": "analysis_assistant", "result": payload}]
    )
    assert "Onderhoudsprioriteit:" in answer
    assert calls == [
        ("inspection", payload, tuple(HEADER.splitlines())),
        ("lifecycle", payload, tuple(HEADER.splitlines()), set()),
    ]
    assert payload.intent_calls == 3


def test_empty_selected_branch_reaches_deep_stop_boundary_then_generic_fallback():
    deep = SequentialIntent(
        ["other", "other", "maintenance_positions", "band_deep_analysis"],
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
    assert "Onderhoudsprioriteit:" not in answer
    assert "Vervangadvies:" in answer
    assert deep.intent_calls == 4

    generic = SequentialIntent(
        ["other", "other", "maintenance_positions", "other"],
        **_payload([], gecombineerde_slijtage=RaisingList(AssertionError("unused"))),
    )
    assert service._build_user_answer(
        [{"action": "analysis_assistant", "result": generic}]
    ) == (HEADER + "\n\ngeneric fallback marker")
    assert generic.intent_calls == 4


def test_generic_fallback_prefers_message_then_kort_resultaat_then_header_only():
    assert service._build_user_answer(
        _results([], message="message marker", kort_resultaat="kort marker")
    ) == (HEADER + "\n\nmessage marker")
    assert service._build_user_answer(
        _results([], message="", kort_resultaat="kort marker")
    ) == (HEADER + "\n\nkort marker")
    assert service._build_user_answer(
        _results([], message=0, kort_resultaat=False)
    ) == HEADER


def test_first_asset_match_breaks_prescan_and_has_absolute_dispatch_priority(monkeypatch):
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
            raise AssertionError("prescan continued after first asset")

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
        (" analysis_assistant", "maintenance_positions"),
        ("analysis_assistant ", "maintenance_positions"),
        ("Analysis_Assistant", "maintenance_positions"),
        (b"analysis_assistant", "maintenance_positions"),
        (None, "maintenance_positions"),
        (0, "maintenance_positions"),
        ("analysis_assistant", " maintenance_positions"),
        ("analysis_assistant", "maintenance_positions "),
        ("analysis_assistant", "Maintenance_Positions"),
        ("analysis_assistant", b"maintenance_positions"),
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
            intent=StringifiesTo("maintenance_positions"),
        )
    )
    assert "Onderhoudsprioriteit:" in answer


@pytest.mark.parametrize(
    "bad_result",
    [
        None,
        "mapping-like",
        [],
        (),
        0,
        object(),
        {"asset_resolution": None},
        {"asset_resolution": "mapping-like"},
        {"asset_resolution": []},
        {"asset_resolution": UserDict()},
    ],
)
def test_outer_prescan_requires_dict_result_and_dict_asset_resolution(bad_result):
    valid = {"action": "analysis_assistant", "result": _payload([], message="selected")}
    assert service._build_user_answer(
        [{"action": "analysis_assistant", "result": bad_result}, valid]
    ).endswith("selected")


def test_dict_and_list_subclasses_pass_shape_gates_but_userdict_and_bad_rows_do_not():
    payload = DictSubclass(_payload(ListSubclass([None, (), [], UserDict(), DictSubclass()])))
    payload["asset_resolution"] = DictSubclass()
    results = ListSubclass([DictSubclass(action="analysis_assistant", result=payload)])
    answer = service._build_user_answer(results)
    assert answer == (
        HEADER
        + "\n\nOnderhoudsprioriteit:"
        + "\n\n1. Onbekende schraper " + LEGACY_DASH + " positie onbekend"
        + "\n   Laatste gemeten meshoogte: niet beschikbaar"
        + "\n   Actie: Trend controleren; geen bruikbare actuele eindmeting"
        + "\n   Geen betrouwbare forecast beschikbaar"
        + "\n\nLet op: 3 mm is de vervanggrens. De 6 mm-grens is een "
        "prestatiecontrole en betekent niet automatisch vervangen."
    )


@pytest.mark.parametrize(
    "rows",
    [None, {}, DictSubclass(), (), "rows", 0, False, object(), UserDict()],
)
def test_resultaat_requires_list_or_subclass_and_other_shapes_fall_through(rows):
    assert service._build_user_answer(_results(rows)) == (
        HEADER + "\n\ngeneric fallback marker"
    )


@pytest.mark.parametrize(
    "rows",
    [[], [None], ["row", (), [], UserDict()], ListSubclass()],
)
def test_empty_or_all_malformed_lists_fall_through_without_claiming_route(rows):
    assert service._build_user_answer(_results(rows)) == (
        HEADER + "\n\ngeneric fallback marker"
    )


def test_header_shape_gates_exact_fields_defaults_and_service_owned_display(monkeypatch):
    sentinels = [object() for _ in range(4)]
    real_display = service._display_name_code
    context = DictSubclass(
        customer_code=0,
        site_code=False,
        area_name=sentinels[0],
        area_code=sentinels[1],
        installation_name=sentinels[2],
        installation_code=sentinels[3],
        band_code="ignored-context-alias",
    )
    payload = _payload([{}], asset_context=context, entities=UserDict(band_code="ignored"))
    calls = []

    def display(name, code):
        calls.append((name, code))
        return f"display-{len(calls)}"

    monkeypatch.setattr(service, "_display_name_code", display)
    answer = service._build_user_answer(
        [{"action": "analysis_assistant", "result": payload}]
    )
    assert answer.startswith(
        "Klant: onbekend\nPlaats: onbekend\nGebied: display-1\n"
        "Installatie: display-2\nBandnummer: onbekend"
    )
    assert calls == [(sentinels[0], sentinels[1]), (sentinels[2], sentinels[3])]
    assert calls[0][0] is sentinels[0] and calls[0][1] is sentinels[1]
    assert calls[1][0] is sentinels[2] and calls[1][1] is sentinels[3]

    monkeypatch.setattr(service, "_display_name_code", real_display)
    rejected_context = _payload([{}], asset_context=UserDict(context), entities=DictSubclass())
    assert service._build_user_answer(
        [{"action": "analysis_assistant", "result": rejected_context}]
    ).startswith(
        "Klant: onbekend\nPlaats: onbekend\nGebied: onbekend\n"
        "Installatie: onbekend\nBandnummer: onbekend"
    )


def test_exact_row_field_names_fallback_source_and_whitespace_semantics():
    aliases_only = {
        "scraper_type_norm": "IGNORED-SCRAPER",
        "position_display": "IGNORED-POSITION",
        "last_date": "IGNORED-DATE",
        "priority": 0,
        "meshoogte_mm": 2,
        "point_count": 99,
        "forecast_3mm": "2099-01-01",
        "performance_action": "CONTROLEREN_PRESTATIEGRENS",
        "status_6_mm": "OP_OF_ONDER_6MM",
        "status_3_mm": "CHECK_TREND",
    }
    fallback = _row(scraper=None, priority=2, height=8, forecast="", scraper_types=" RAW ")
    whitespace = _row(scraper="   ", priority=3, height=8, forecast="", scraper_types="IGNORED")
    answer = service._build_user_answer(_results([aliases_only, fallback, whitespace]))
    assert "1. RAW " + LEGACY_DASH + " P-SYNTH" in answer
    assert "2. Onbekende schraper " + LEGACY_DASH + " P-SYNTH" in answer
    assert "3. Onbekende schraper " + LEGACY_DASH + " positie onbekend" in answer
    assert "IGNORED-SCRAPER" not in answer
    assert "IGNORED-POSITION" not in answer
    assert "2099-01-01" not in answer


def test_none_falsy_bytes_objects_and_string_stripping_are_exact():
    answer = service._build_user_answer(
        _results(
            [
                _row(
                    scraper=b" R ",
                    position=b" P ",
                    cycle_end=b" D ",
                    priority=False,
                    height=False,
                    points=False,
                    forecast=0,
                    performance=0,
                    status_6mm=None,
                    status_3mm=False,
                ),
                _row(
                    scraper=0,
                    position=0,
                    cycle_end=0,
                    priority=None,
                    height=None,
                    points=0,
                    forecast=None,
                ),
            ]
        )
    )
    assert "1. Onbekende schraper " + LEGACY_DASH + " positie onbekend" in answer
    assert "2. b' R ' " + LEGACY_DASH + " b' P '" in answer
    assert "Laatste gemeten meshoogte: niet beschikbaar" in answer
    assert " op b' D '" not in answer
    assert answer.count("Geen betrouwbare forecast beschikbaar") == 2


def test_deduplication_key_is_four_normalized_fields_and_first_duplicate_wins():
    first = _row(height=8, points=2, forecast="FIRST", status_3mm="CHECK_TREND")
    rows = [
        first,
        dict(first, eind_meshoogte_mm=2, meetpunten=9, geschatte_vervangdatum_bij_3mm="SECOND"),
        dict(first, prioriteit=1.0, eind_meshoogte_mm=6),
        dict(first, cycle_end="2099-01-03", eind_meshoogte_mm=5),
        dict(first, position_hint="P-OTHER", eind_meshoogte_mm=4),
        dict(first, scraper_types_clean="U-SYNTH", eind_meshoogte_mm=3),
    ]
    answer = service._build_user_answer(_results(rows))
    assert answer.count("\n   Laatste gemeten meshoogte:") == 5
    assert "Laatste gemeten meshoogte: 8 mm op 2099-01-02" in answer
    assert "Laatste gemeten meshoogte: 2 mm op 2099-01-02" not in answer
    assert "SECOND" not in answer
    assert "FIRST" not in answer  # two points makes the winning forecast unreliable
    assert "1.0" not in answer  # priority participates in identity but is never displayed


def test_sort_is_priority_then_scraper_then_position_and_stable_for_equal_keys():
    rows = [
        _row(scraper="B", position="Z", cycle_end="FIRST", priority=2, forecast=""),
        _row(scraper="A", position="Z", cycle_end="A", priority=1, forecast=""),
        _row(scraper="A", position="B", cycle_end="B", priority=2, forecast=""),
        _row(scraper="A", position="A", cycle_end="C", priority=2, forecast=""),
        _row(scraper="B", position="Z", cycle_end="SECOND", priority=2, forecast=""),
        _row(scraper="LAST", position="P", cycle_end="INF", priority=True, forecast=""),
    ]
    answer = service._build_user_answer(_results(rows))
    headings = [
        line for line in answer.splitlines() if line[:1].isdigit() and ". " in line
    ]
    assert headings == [
        "1. A " + LEGACY_DASH + " Z",
        "2. A " + LEGACY_DASH + " A",
        "3. A " + LEGACY_DASH + " B",
        "4. B " + LEGACY_DASH + " Z",
        "5. B " + LEGACY_DASH + " Z",
        "6. LAST " + LEGACY_DASH + " P",
    ]
    assert answer.index("7 mm op FIRST") < answer.index("7 mm op SECOND")


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"height": 3}, "NU VERVANGEN"),
        (
            {"height": 3, "performance": "CONTROLEREN_PRESTATIEGRENS"},
            "NU VERVANGEN",
        ),
        (
            {"height": 7, "performance": "CONTROLEREN_PRESTATIEGRENS"},
            "Prestatiegrens controleren",
        ),
        ({"height": 7, "status_6mm": "OP_OF_ONDER_6MM"}, "Prestatiegrens controleren"),
        ({"height": None, "status_6mm": "OP_OF_ONDER_6MM"}, "Prestatiegrens controleren"),
        ({"height": None, "status_3mm": "CHECK_TREND"}, "Trend controleren; geen bruikbare actuele eindmeting"),
        ({"height": "3", "status_3mm": "CHECK_TREND"}, "Trend controleren; geen bruikbare actuele eindmeting"),
        ({"height": 7, "status_3mm": "CHECK_TREND"}, "Trend controleren"),
        ({"height": 7, "status_3mm": " CHECK_TREND "}, "Trend controleren"),
        ({"height": 7, "status_6mm": "op_of_onder_6mm"}, "Monitoren"),
        ({"height": 7, "performance": "controleren_prestatiegrens"}, "Monitoren"),
        ({"height": 7}, "Monitoren"),
        ({"height": float("nan")}, "Monitoren"),
    ],
)
def test_action_precedence_and_exact_status_values(overrides, expected):
    answer = service._build_user_answer(_results([_row(**overrides)]))
    assert f"Actie: {expected}" in answer


@pytest.mark.parametrize(
    ("points", "height", "forecast", "reliable"),
    [
        (3, 7, "2099", True),
        (2, 7, "2099", False),
        (True, 7, "2099", False),
        (3.0, 7, "2099", False),
        (Decimal("3"), 7, "2099", False),
        (3, True, "2099", False),
        (3, "7", "2099", False),
        (3, Decimal("7"), "2099", False),
        (3, 7, "", False),
        (3, 7, "   ", False),
        (3, float("inf"), "2099", True),
        (3, float("nan"), "2099", True),
        (3, 7, b"2099", True),
    ],
)
def test_forecast_gate_requires_exact_integer_points_numeric_height_and_nonempty_stripped_date(
    points, height, forecast, reliable
):
    answer = service._build_user_answer(
        _results([_row(points=points, height=height, forecast=forecast)])
    )
    assert ("Prognose 3 mm:" in answer) is reliable
    assert ("Onderbouwing:" in answer) is reliable
    assert ("Geen betrouwbare forecast beschikbaar" in answer) is not reliable


def test_exact_presentation_rounding_units_separators_blank_lines_and_order():
    answer = service._build_user_answer(
        _results(
            [
                _row(
                    scraper=" U ",
                    position=" SOUTH ",
                    cycle_end="",
                    priority=2,
                    height=None,
                    points=9,
                    forecast="2099-09-09",
                ),
                _row(
                    scraper=" R ",
                    position=" NORTH ",
                    cycle_end=" 2099-01-02 ",
                    priority=1,
                    height=5.678,
                    points=3,
                    forecast=" 2099-06-01 ",
                    status_6mm=" OP_OF_ONDER_6MM ",
                ),
            ]
        )
    )
    assert answer == (
        HEADER
        + "\n\nOnderhoudsprioriteit:"
        + "\n\n1. R " + LEGACY_DASH + " NORTH"
        + "\n   Laatste gemeten meshoogte: 5.68 mm op 2099-01-02"
        + "\n   Actie: Prestatiegrens controleren"
        + "\n   Prognose 3 mm: rond 2099-06-01"
        + "\n   Onderbouwing: 3 meetpunten"
        + "\n\n2. U " + LEGACY_DASH + " SOUTH"
        + "\n   Laatste gemeten meshoogte: niet beschikbaar"
        + "\n   Actie: Trend controleren; geen bruikbare actuele eindmeting"
        + "\n   Geen betrouwbare forecast beschikbaar"
        + "\n\nLet op: 3 mm is de vervanggrens. De 6 mm-grens is een "
        "prestatiecontrole en betekent niet automatisch vervangen."
    )


def test_formatting_zero_negative_nan_infinity_and_two_decimal_trimming():
    rows = [
        _row(scraper="A", cycle_end="", priority=1, height=0, forecast=""),
        _row(scraper="B", cycle_end="", priority=2, height=-1.0, forecast=""),
        _row(scraper="C", cycle_end="", priority=3, height=1.2, forecast=""),
        _row(scraper="D", cycle_end="", priority=4, height=1.234, forecast=""),
        _row(scraper="E", cycle_end="", priority=5, height=float("nan"), forecast=""),
        _row(scraper="F", cycle_end="", priority=6, height=float("inf"), forecast=""),
    ]
    answer = service._build_user_answer(_results(rows))
    assert [
        line.strip()
        for line in answer.splitlines()
        if "Laatste gemeten meshoogte:" in line
    ] == [
        "Laatste gemeten meshoogte: 0 mm",
        "Laatste gemeten meshoogte: -1 mm",
        "Laatste gemeten meshoogte: 1.2 mm",
        "Laatste gemeten meshoogte: 1.23 mm",
        "Laatste gemeten meshoogte: nan mm",
        "Laatste gemeten meshoogte: inf mm",
    ]


def test_priority_numeric_gate_invalid_values_sort_at_infinity_stably():
    class IntSubclass(int):
        pass

    rows = [
        _row(cycle_end="DECIMAL", priority=Decimal("1"), forecast=""),
        _row(cycle_end="STRING", priority="1", forecast=""),
        _row(cycle_end="NONE", priority=None, forecast=""),
        _row(cycle_end="BOOL", priority=True, forecast=""),
        _row(cycle_end="FLOAT", priority=0.5, forecast=""),
        _row(cycle_end="INT-SUBCLASS", priority=IntSubclass(-1), forecast=""),
    ]
    answer = service._build_user_answer(_results(rows))
    ordered_dates = [
        line.rsplit(" op ", 1)[1]
        for line in answer.splitlines()
        if "Laatste gemeten meshoogte:" in line
    ]
    assert ordered_dates == [
        "INT-SUBCLASS",
        "FLOAT",
        "DECIMAL",
        "STRING",
        "NONE",
        "BOOL",
    ]


def test_no_position_limit_and_no_grouping_beyond_exact_deduplication():
    rows = [
        _row(
            scraper="R",
            position="P",
            cycle_end=f"C-{index:02}",
            priority=index,
            height=index + 4,
            forecast="",
        )
        for index in range(25)
    ]
    answer = service._build_user_answer(_results(rows))
    assert answer.count("\n   Laatste gemeten meshoogte:") == 25
    assert "1. R " + LEGACY_DASH + " P" in answer
    assert "25. R " + LEGACY_DASH + " P" in answer


def test_display_helper_call_cardinality_argument_identity_no_mutation_and_fresh_state(monkeypatch):
    sentinels = [{"sentinel": index} for index in range(4)]
    row = CountingMapping(_row())
    payload = CountingMapping(_payload([row]))
    context = payload["asset_context"]
    context.update(
        zip(
            ("area_name", "area_code", "installation_name", "installation_code"),
            sentinels,
        )
    )
    outer = CountingMapping({"action": "analysis_assistant", "result": payload})
    results = [outer]
    requested = [" Latest_Measurements "]
    before_results = copy.deepcopy(results)
    before_requested = copy.deepcopy(requested)
    calls = []

    def display(name, code):
        calls.append((name, code))
        return f"display-{len(calls)}"

    monkeypatch.setattr(service, "_display_name_code", display)
    first = service._build_user_answer(results, requested)
    first_outer_calls = list(outer.calls)
    first_payload_calls = list(payload.calls)
    first_row_calls = list(row.calls)
    outer.calls.clear()
    payload.calls.clear()
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
    assert first_outer_calls == [("result", None), ("action", None)]
    assert outer.calls == first_outer_calls
    assert first_payload_calls == [
        ("asset_resolution", None),
        ("asset_context", None),
        ("entities", None),
        ("message", None),
        ("intent", None),
        ("intent", None),
        ("intent", None),
        ("resultaat", None),
    ]
    assert payload.calls == first_payload_calls
    assert first_row_calls == [
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
    assert row.calls == first_row_calls
    assert results == before_results
    assert requested == before_requested
    assert results[0]["result"] is payload
    assert payload["asset_context"] is context
    assert payload["resultaat"][0] is row


@pytest.mark.parametrize("fatal", [False, True], ids=["exception", "baseexception"])
@pytest.mark.parametrize(
    "boundary",
    [
        "requested_truth",
        "requested_iter",
        "requested_str",
        "results_iter",
        "outer_get",
        "asset_resolution_get",
        "action_truth",
        "action_str",
        "context_get",
        "context_field_get",
        "context_field_truth",
        "entities_get",
        "entities_field_get",
        "message_get",
        "message_truth",
        "intent_get",
        "intent_truth",
        "intent_str",
        "rows_get",
        "rows_iter",
        "row_get",
        "row_truth",
        "row_str",
        "priority_str",
        "priority_float",
        "height_float",
        "meetpunten_compare",
        "meetpunten_format",
        "sort",
        "enumerate",
        "format_is_integer",
        "format_int",
        "display",
        "inspection_answer_property",
        "lifecycle_answer_property",
    ],
)
def test_mapping_property_iteration_truth_conversion_sort_format_and_helper_throwables_propagate(
    monkeypatch, boundary, fatal
):
    error = Fatal(boundary) if fatal else RuntimeError(boundary)
    row = _row(points=2, forecast="")
    rows = [row]
    payload = _payload(rows)
    results = [{"action": "analysis_assistant", "result": payload}]
    requested = None

    if boundary == "requested_truth":
        requested = RaisingBool(error)
    elif boundary == "requested_iter":
        requested = RaisingList(error)
    elif boundary == "requested_str":
        requested = [RaisingStr(error)]
    elif boundary == "results_iter":
        results = RaisingList(error, results)
    elif boundary == "outer_get":
        results = [RaisingGet("result", error, results[0])]
    elif boundary == "asset_resolution_get":
        results[0]["result"] = RaisingGet("asset_resolution", error, payload)
    elif boundary == "action_truth":
        results[0]["action"] = RaisingBool(error)
    elif boundary == "action_str":
        results[0]["action"] = RaisingStr(error)
    elif boundary == "context_get":
        results[0]["result"] = RaisingGet("asset_context", error, payload)
    elif boundary == "context_field_get":
        payload["asset_context"] = RaisingGet("customer_code", error, payload["asset_context"])
    elif boundary == "context_field_truth":
        payload["asset_context"]["customer_code"] = RaisingBool(error)
    elif boundary == "entities_get":
        results[0]["result"] = RaisingGet("entities", error, payload)
    elif boundary == "entities_field_get":
        payload["asset_context"].pop("band_code_display")
        payload["entities"] = RaisingGet("band_code", error, payload["entities"])
    elif boundary == "message_get":
        results[0]["result"] = RaisingGet("message", error, payload)
    elif boundary == "message_truth":
        payload["message"] = RaisingBool(error)
    elif boundary == "intent_get":
        results[0]["result"] = RaisingGet("intent", error, payload)
    elif boundary == "intent_truth":
        payload["intent"] = RaisingBool(error)
    elif boundary == "intent_str":
        payload["intent"] = RaisingStr(error)
    elif boundary == "rows_get":
        results[0]["result"] = RaisingGet("resultaat", error, payload)
    elif boundary == "rows_iter":
        payload["resultaat"] = RaisingList(error)
    elif boundary == "row_get":
        payload["resultaat"] = [RaisingGet("position_hint", error, row)]
    elif boundary == "row_truth":
        row["scraper_types_clean"] = RaisingBool(error)
    elif boundary == "row_str":
        row["position_hint"] = RaisingStr(error)
    elif boundary == "priority_str":
        row["prioriteit"] = RaisingStr(error)
    elif boundary == "priority_float":
        RaisingFloatInt.error = error
        row["prioriteit"] = RaisingFloatInt(1)
    elif boundary == "height_float":
        RaisingFloatInt.error = error
        row["eind_meshoogte_mm"] = RaisingFloatInt(7)
    elif boundary == "meetpunten_compare":
        RaisingGeInt.error = error
        row["meetpunten"] = RaisingGeInt(3)
    elif boundary == "meetpunten_format":
        RaisingFormatInt.error = error
        row["meetpunten"] = RaisingFormatInt(3)
        row["geschatte_vervangdatum_bij_3mm"] = "2099"
    elif boundary == "sort":
        RaisingComparableFloat.error = error
        real_float = builtins.float

        def sort_float(value):
            if value in (1, 2):
                return RaisingComparableFloat(value)
            return real_float(value)

        monkeypatch.setattr(service, "float", sort_float, raising=False)
        payload["resultaat"] = [row, dict(row, prioriteit=2, cycle_end="other")]
    elif boundary == "enumerate":
        monkeypatch.setattr(
            service,
            "enumerate",
            lambda *_a, **_k: (_ for _ in ()).throw(error),
            raising=False,
        )
    elif boundary == "format_is_integer":
        RaisingIsIntegerFloat.error = error
        real_float = builtins.float

        def format_float(value):
            if value == 7:
                return RaisingIsIntegerFloat(value)
            return real_float(value)

        monkeypatch.setattr(service, "float", format_float, raising=False)
    elif boundary == "format_int":
        RaisingIntFloat.error = error
        real_float = builtins.float

        def int_float(value):
            if value == 7:
                return RaisingIntFloat(value)
            return real_float(value)

        monkeypatch.setattr(service, "float", int_float, raising=False)
    elif boundary == "display":
        monkeypatch.setattr(
            service,
            "_display_name_code",
            lambda *_a: (_ for _ in ()).throw(error),
        )
    elif boundary in {"inspection_answer_property", "lifecycle_answer_property"}:
        class Result:
            @property
            def answer(self):
                raise error

        if boundary == "inspection_answer_property":
            payload = SequentialIntent(["inspection_summary"], **payload)
            monkeypatch.setattr(
                service,
                "run_asset_inspection_summary_answer_stage",
                lambda *_a: Result(),
            )
        else:
            payload = SequentialIntent(["other", "lifecycle"], **payload)
            monkeypatch.setattr(
                service,
                "run_asset_lifecycle_answer_stage",
                lambda *_a: Result(),
            )
        results[0]["result"] = payload

    with pytest.raises(type(error), match=boundary) as raised:
        service._build_user_answer(results, requested)
    assert raised.value is error
