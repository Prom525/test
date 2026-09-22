"""Characterize only the inline ``band_deep_analysis`` asset presenter."""
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


class RaisingGeInt(int):
    error = None

    def __ge__(self, _other):
        raise self.error


class RaisingIsIntegerFloat(float):
    error = None

    def is_integer(self):
        raise self.error


class RaisingIntFloat(float):
    error = None

    def __int__(self):
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


def _position(
    *,
    scraper="R-SYNTH",
    family="R",
    position="P-SYNTH",
    inspected="2099-01-02",
    height=7,
    advice="MONITOREN",
    **extra,
):
    return {
        "scraper_type_norm": scraper,
        "scraper_family": family,
        "position_display": position,
        "laatste_inspectiedatum": inspected,
        "meshoogte_mm": height,
        "onderhoudsadvies_unified": advice,
        **extra,
    }


def _forecast(
    *,
    scraper="R-FORECAST",
    points=3,
    end_height=7,
    wear=0.1,
    days=40,
    date="2099-06-01",
    **extra,
):
    return {
        "scraper_type_norm": scraper,
        "meetpunten": points,
        "eind_meshoogte_mm": end_height,
        "slijtage_mm_per_dag": wear,
        "geschatte_dagen_tot_3mm": days,
        "geschatte_vervangdatum_bij_3mm": date,
        **extra,
    }


def _lifecycle(
    inspected="2099-01-01",
    *,
    scraper="R-HISTORY",
    position="P-HISTORY",
    cycle="C-HISTORY",
    canonical="I-HISTORY",
    height=8,
    replace=False,
    **extra,
):
    return {
        "inspected_on": inspected,
        "scraper_type_norm": scraper,
        "position_hint": position,
        "cycle_id": cycle,
        "canonical_inspection_key": canonical,
        "meshoogte_mm": height,
        "replace_event": replace,
        **extra,
    }


def _payload(positions, forecasts=None, **overrides):
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
        "intent": "band_deep_analysis",
        "message": "generic fallback marker",
        "gecombineerde_slijtage": positions,
        "forecast_3mm": [] if forecasts is None else forecasts,
        **overrides,
    }


def _results(positions, forecasts=None, *, action="analysis_assistant", **overrides):
    return [
        {
            "action": action,
            "result": _payload(positions, forecasts, **overrides),
        }
    ]


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


def test_ast_pins_route_order_whole_branch_and_smallest_mechanical_interface():
    function, asset_if, routes = _asset_route_nodes()
    assert [name for name, _ in routes] == [
        "inspection_summary",
        "lifecycle",
        "maintenance_positions",
        "band_deep_analysis",
    ]

    deep = dict(routes)["band_deep_analysis"]
    assert ast.unparse(deep.test) == (
        "asset_action == 'analysis_assistant' and "
        "str(asset_result.get('intent') or '') == 'band_deep_analysis'"
    )
    assert [type(node) for node in deep.body] == [ast.Assign, ast.Assign, ast.If]
    assert [ast.unparse(node) for node in deep.body[:2]] == [
        "raw_positions = asset_result.get('gecombineerde_slijtage')",
        "raw_forecasts = asset_result.get('forecast_3mm')",
    ]
    positions_gate = deep.body[2]
    assert ast.unparse(positions_gate.test) == "isinstance(raw_positions, list)"
    assert [
        node.name
        for node in positions_gate.body
        if isinstance(node, ast.FunctionDef)
    ] == ["_numeric", "_format_mm", "_family_from_text"]

    rendered_positions_gate = next(
        node
        for node in positions_gate.body
        if isinstance(node, ast.If) and ast.unparse(node.test) == "positions"
    )
    facet_assignment = next(
        node
        for node in rendered_positions_gate.body
        if isinstance(node, ast.Assign)
        and ast.unparse(node.targets[0]) == "facet_requested"
    )
    assert ast.unparse(facet_assignment.value) == (
        "bool({'lifecycle_trend', 'replacement_events', 'uncertainties'} & requested)"
    )
    facet_gate = next(
        node
        for node in rendered_positions_gate.body
        if isinstance(node, ast.If) and ast.unparse(node.test) == "facet_requested"
    )
    assert ast.unparse(rendered_positions_gate.body[-1]) == (
        "return '\\n'.join(answer_lines)"
    )

    # These line-number-independent metrics show why arbitrary internal splitting
    # is not mechanical: the cohesive facet block consumes almost half the route,
    # while the whole selected body has only three external values.
    assert sum(1 for _ in ast.walk(deep)) == 1805
    assert sum(1 for _ in ast.walk(facet_gate)) == 840
    body_module = ast.Module(body=deep.body, type_ignores=[])
    loaded = {
        node.id
        for node in ast.walk(body_module)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }
    bound = {
        node.id
        for node in ast.walk(body_module)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
    }
    bound.update(
        node.arg for node in ast.walk(body_module) if isinstance(node, ast.arg)
    )
    bound.update(
        node.name
        for node in ast.walk(body_module)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    )
    external = loaded - bound - set(dir(builtins)) - {"Any"}
    assert external == {"asset_result", "answer_lines", "requested"}

    calls = {
        ast.unparse(node.func)
        for node in ast.walk(deep)
        if isinstance(node, ast.Call)
    }
    assert not {name for name in calls if name.startswith("run_")}
    assert not {name for name in calls if "shadow" in name or "repair" in name}
    assert ast.unparse(asset_if.body[-2].test) == "result_text"
    assert ast.unparse(asset_if.body[-1]) == "return '\\n'.join(answer_lines)"
    assert any(
        isinstance(node, ast.For) and ast.unparse(node.iter) == "results"
        for node in function.body
    )


def test_prior_stage_order_exact_arguments_fallthrough_and_deep_direct_return(monkeypatch):
    payload = SequentialIntent(
        [
            "inspection_summary",
            "lifecycle",
            "maintenance_positions",
            "band_deep_analysis",
        ],
        **_payload([_position()]),
    )
    calls = []

    class StageResult:
        answer = None

    def inspection(selected, header):
        calls.append(("inspection", selected, header))
        return StageResult()

    def lifecycle(selected, header, requested):
        calls.append(("lifecycle", selected, header, requested))
        return StageResult()

    def maintenance(selected, header):
        calls.append(("maintenance", selected, header))
        return StageResult()

    monkeypatch.setattr(service, "run_asset_inspection_summary_answer_stage", inspection)
    monkeypatch.setattr(service, "run_asset_lifecycle_answer_stage", lifecycle)
    monkeypatch.setattr(service, "run_asset_maintenance_positions_answer_stage", maintenance)
    requested_input = [" Uncertainties "]
    answer = service._build_user_answer(
        [{"action": "analysis_assistant", "result": payload}], requested_input
    )

    header = tuple(HEADER.splitlines())
    assert calls == [
        ("inspection", payload, header),
        ("lifecycle", payload, header, {"uncertainties"}),
        ("maintenance", payload, header),
    ]
    assert calls[0][1] is payload and calls[1][1] is payload and calls[2][1] is payload
    assert payload.intent_calls == 4
    assert answer.startswith(HEADER + "\n\nVervangadvies:")
    assert "generic fallback marker" not in answer


def test_first_asset_match_breaks_prescan_and_preempts_non_asset_dispatch(monkeypatch):
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
    later = _payload([_position()], message="later asset")
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
        (" analysis_assistant", "band_deep_analysis"),
        ("analysis_assistant ", "band_deep_analysis"),
        ("Analysis_Assistant", "band_deep_analysis"),
        (b"analysis_assistant", "band_deep_analysis"),
        (None, "band_deep_analysis"),
        (0, "band_deep_analysis"),
        ("analysis_assistant", " band_deep_analysis"),
        ("analysis_assistant", "band_deep_analysis "),
        ("analysis_assistant", "Band_Deep_Analysis"),
        ("analysis_assistant", b"band_deep_analysis"),
        ("analysis_assistant", None),
        ("analysis_assistant", 0),
    ],
)
def test_action_and_intent_are_exact_after_or_then_string_conversion(action, intent):
    answer = service._build_user_answer(
        _results([_position()], action=action, intent=intent)
    )
    assert answer == HEADER + "\n\ngeneric fallback marker"


def test_action_and_intent_accept_objects_stringifying_to_exact_selectors():
    answer = service._build_user_answer(
        _results(
            [_position()],
            action=StringifiesTo("analysis_assistant"),
            intent=StringifiesTo("band_deep_analysis"),
        )
    )
    assert "Vervangadvies:" in answer


@pytest.mark.parametrize(
    "positions",
    [None, {}, DictSubclass(), (), "rows", 0, False, object(), UserDict(), []],
)
def test_positions_require_nonempty_list_or_subclass_else_generic_fallback(positions):
    assert service._build_user_answer(_results(positions)) == (
        HEADER + "\n\ngeneric fallback marker"
    )


def test_list_and_dict_subclasses_pass_gates_and_malformed_rows_are_skipped():
    positions = ListSubclass(
        [None, "row", (), [], UserDict(), DictSubclass(_position())]
    )
    forecasts = ListSubclass(
        [None, "row", UserDict(), DictSubclass(_forecast())]
    )
    answer = service._build_user_answer(_results(positions, forecasts))
    assert "1. R-SYNTH " + LEGACY_DASH + " P-SYNTH" in answer
    assert "Prognose 3 mm: rond 2099-06-01" in answer


@pytest.mark.parametrize(
    "forecasts",
    [None, {}, DictSubclass(), (), "rows", 0, False, object(), UserDict()],
)
def test_non_list_forecasts_are_replaced_by_empty_list(forecasts):
    answer = service._build_user_answer(_results([_position()], forecasts))
    assert "Geen betrouwbare forecast beschikbaar" in answer


def test_exact_position_fields_aliases_normalization_defaults_and_no_required_field_gate():
    aliases_only = {
        "scraper_types_clean": "ALIAS-SCRAPER",
        "position_hint": "ALIAS-POSITION",
        "inspected_on": "ALIAS-DATE",
        "eind_meshoogte_mm": 2,
        "maintenance_advice": "VERVANGEN_VOORBEREIDEN",
    }
    normalized = _position(
        scraper=b" R-BYTES ",
        family="",
        position=0,
        inspected=False,
        height=None,
        advice=" controleren_bij_stop ",
    )
    answer = service._build_user_answer(_results([aliases_only, normalized]))
    assert answer == (
        HEADER
        + "\n\nVervangadvies:"
        + "\n\n1. b' R-BYTES ' " + LEGACY_DASH + " positie onbekend"
        + "\n   Laatste gemeten meshoogte: niet beschikbaar"
        + "\n   Advies: Controleren bij stop"
        + "\n   Geen betrouwbare forecast beschikbaar"
        + "\n\n2. Onbekende schraper " + LEGACY_DASH + " positie onbekend"
        + "\n   Laatste gemeten meshoogte: niet beschikbaar"
        + "\n   Advies: Monitoren"
        + "\n   Geen betrouwbare forecast beschikbaar"
        + "\n\nLet op: 3 mm is de vervanggrens. Een advies 'vervanging "
        "voorbereiden' betekent niet dat het mes nu al de vervanggrens heeft bereikt."
    )


@pytest.mark.parametrize(
    ("height", "advice", "expected"),
    [
        (3, "MONITOREN", "NU VERVANGEN"),
        (3.0, "VERVANGEN_VOORBEREIDEN", "NU VERVANGEN"),
        (2.999, "CONTROLEREN_BIJ_STOP", "NU VERVANGEN"),
        (0, "", "NU VERVANGEN"),
        (-1, "", "NU VERVANGEN"),
        (3.001, " vervangen_voorbereiden ", "Vervanging voorbereiden"),
        (None, "CONTROLEREN_BIJ_STOP", "Controleren bij stop"),
        ("3", "VERVANGEN_VOORBEREIDEN", "Vervanging voorbereiden"),
        (True, "CONTROLEREN_BIJ_STOP", "Controleren bij stop"),
        (False, "", "Monitoren"),
        (Decimal("2"), "", "Monitoren"),
        (float("nan"), "", "Monitoren"),
        (float("inf"), "", "Monitoren"),
        (4, " controleren_bij_stop ", "Controleren bij stop"),
        (4, "unknown", "Monitoren"),
    ],
)
def test_height_numeric_gate_and_exact_action_precedence(height, advice, expected):
    answer = service._build_user_answer(
        _results([_position(height=height, advice=advice)])
    )
    assert f"Advies: {expected}" in answer


@pytest.mark.parametrize(
    ("overrides", "reliable"),
    [
        ({}, True),
        ({"points": 2}, False),
        ({"points": True}, False),
        ({"points": 3.0}, False),
        ({"points": Decimal("3")}, False),
        ({"end_height": True}, False),
        ({"end_height": "7"}, False),
        ({"end_height": Decimal("7")}, False),
        ({"wear": False}, False),
        ({"wear": "0.1"}, False),
        ({"days": None}, False),
        ({"days": Decimal("40")}, False),
        ({"date": ""}, False),
        ({"date": "   "}, False),
        ({"scraper": "X-UNKNOWN"}, False),
        ({"end_height": float("nan")}, True),
        ({"wear": float("inf")}, True),
        ({"date": b"2099"}, True),
    ],
)
def test_forecast_requires_all_exact_fields_and_numeric_family_gate(overrides, reliable):
    forecast = _forecast(**overrides)
    answer = service._build_user_answer(
        _results([_position(family="R")], [forecast])
    )
    assert ("Prognose 3 mm:" in answer) is reliable
    assert ("Onderbouwing:" in answer) is reliable
    assert ("Geen betrouwbare forecast beschikbaar" in answer) is not reliable


def test_forecast_family_normalization_matching_ambiguity_and_ignored_position_hint():
    positions = [
        _position(scraper=" R-POS ", family="", position="P1"),
        _position(scraper="u-pos", family=" u ", position="P2"),
        _position(scraper="T-POS", family="T-FULL", position="P3"),
    ]
    forecasts = [
        _forecast(scraper=" r-any ", date="R-DATE", position_hint="unrelated"),
        _forecast(scraper="U-one", date="U-FIRST"),
        _forecast(scraper="u-two", date="U-SECOND"),
        _forecast(scraper="t-one", date="T-DATE"),
    ]
    answer = service._build_user_answer(_results(positions, forecasts))
    sections = answer.split("\n\n")
    r_text = next(section for section in sections if "R-POS" in section)
    u_text = next(section for section in sections if "u-pos" in section)
    t_text = next(section for section in sections if "T-POS" in section)
    assert "rond R-DATE" in r_text
    assert "Geen betrouwbare forecast beschikbaar" in u_text
    assert "rond T-DATE" not in t_text
    assert "Geen betrouwbare forecast beschikbaar" in t_text


def test_forecast_aliases_do_not_satisfy_any_exact_field_gate():
    aliases_only = {
        "scraper_family": "R",
        "measurement_count": 3,
        "end_height_mm": 7,
        "wear_rate_mm_per_day": 0.1,
        "days_until_3mm": 40,
        "replacement_date": "2099-06-01",
    }
    answer = service._build_user_answer(
        _results([_position()], [aliases_only])
    )
    assert "Prognose 3 mm:" not in answer
    assert "Geen betrouwbare forecast beschikbaar" in answer


def test_position_dedupe_is_exact_three_normalized_fields_first_wins():
    base = _position(height=9, advice="MONITOREN")
    rows = [
        base,
        dict(base, height=2, advice="VERVANGEN_VOORBEREIDEN", scraper_family="U"),
        _position(scraper="R-OTHER"),
        _position(position="P-OTHER"),
        _position(inspected="2099-01-03"),
    ]
    answer = service._build_user_answer(_results(rows))
    assert answer.count("\n   Advies:") == 4
    retained = next(
        section
        for section in answer.split("\n\n")
        if "R-SYNTH " + LEGACY_DASH + " P-SYNTH\n" in section
    )
    assert "9 mm" in retained
    assert "Advies: Monitoren" in retained
    assert "NU VERVANGEN" not in retained


def test_sort_is_action_rank_scraper_position_and_stable_for_equal_keys():
    rows = [
        _position(scraper="B", position="Z", inspected="FIRST", height=8),
        _position(scraper="A", position="Z", inspected="PREP", height=8, advice="PREP"),
        _position(scraper="B", position="Z", inspected="SECOND", height=9),
        _position(scraper="A", position="B", inspected="STOP", height=8, advice="CONTROLEREN_BIJ_STOP"),
        _position(scraper="A", position="A", inspected="NOW", height=3),
        _position(scraper="A", position="Z", inspected="PREP2", height=8, advice="VERVANGEN_VOORBEREIDEN"),
    ]
    answer = service._build_user_answer(_results(rows))
    headings = [
        line for line in answer.splitlines() if line[:1].isdigit() and ". " in line
    ]
    assert headings == [
        "1. A " + LEGACY_DASH + " A",
        "2. A " + LEGACY_DASH + " Z",
        "3. A " + LEGACY_DASH + " B",
        "4. A " + LEGACY_DASH + " Z",
        "5. B " + LEGACY_DASH + " Z",
        "6. B " + LEGACY_DASH + " Z",
    ]
    assert answer.index("8 mm op FIRST") < answer.index("9 mm op SECOND")


def test_no_position_limit_and_no_grouping_beyond_exact_deduplication():
    rows = [
        _position(position="P", inspected=f"2099-01-{index + 1:02}", height=4 + index)
        for index in range(25)
    ]
    answer = service._build_user_answer(_results(rows))
    assert answer.count("\n   Laatste gemeten meshoogte:") == 25
    assert "1. R-SYNTH " + LEGACY_DASH + " P" in answer
    assert "25. R-SYNTH " + LEGACY_DASH + " P" in answer


def test_exact_core_presentation_rounding_units_blanks_mojibake_and_order():
    answer = service._build_user_answer(
        _results(
            [
                _position(
                    scraper=" U ",
                    family="U",
                    position=" SOUTH ",
                    inspected="",
                    height=None,
                    advice="CONTROLEREN_BIJ_STOP",
                ),
                _position(
                    scraper=" R ",
                    family="R",
                    position=" NORTH ",
                    inspected=" 2099-01-02 ",
                    height=5.678,
                    advice="VERVANGEN_VOORBEREIDEN",
                ),
            ],
            [_forecast(points=7, date=" 2099-06-01 ")],
        )
    )
    assert answer == (
        HEADER
        + "\n\nVervangadvies:"
        + "\n\n1. R " + LEGACY_DASH + " NORTH"
        + "\n   Laatste gemeten meshoogte: 5.68 mm op 2099-01-02"
        + "\n   Advies: Vervanging voorbereiden"
        + "\n   Prognose 3 mm: rond 2099-06-01"
        + "\n   Onderbouwing: 7 meetpunten"
        + "\n\n2. U " + LEGACY_DASH + " SOUTH"
        + "\n   Laatste gemeten meshoogte: niet beschikbaar"
        + "\n   Advies: Controleren bij stop"
        + "\n   Geen betrouwbare forecast beschikbaar"
        + "\n\nLet op: 3 mm is de vervanggrens. Een advies 'vervanging "
        "voorbereiden' betekent niet dat het mes nu al de vervanggrens heeft bereikt."
    )


def test_mm_formatting_zero_negative_nan_infinity_and_two_decimal_trimming():
    rows = [
        _position(scraper="A", height=0),
        _position(scraper="B", height=-1.0),
        _position(scraper="C", height=1.2),
        _position(scraper="D", height=1.234),
        _position(scraper="E", height=float("nan")),
        _position(scraper="F", height=float("inf")),
    ]
    answer = service._build_user_answer(_results(rows))
    assert [
        line.strip()
        for line in answer.splitlines()
        if "Laatste gemeten meshoogte:" in line
    ] == [
        "Laatste gemeten meshoogte: 0 mm op 2099-01-02",
        "Laatste gemeten meshoogte: -1 mm op 2099-01-02",
        "Laatste gemeten meshoogte: 1.2 mm op 2099-01-02",
        "Laatste gemeten meshoogte: 1.23 mm op 2099-01-02",
        "Laatste gemeten meshoogte: nan mm op 2099-01-02",
        "Laatste gemeten meshoogte: inf mm op 2099-01-02",
    ]


def test_all_facets_exact_text_sequence_grouping_dedupe_sort_and_source_boundary():
    lifecycle = [
        _lifecycle("2099-01-03", scraper="R-HISTORY", cycle="C1", height=5.678),
        _lifecycle("2099-01-01", scraper="R-HISTORY", cycle="C1", canonical="I1", height=8),
        _lifecycle("2099-01-03", scraper="R-HISTORY", cycle="C1", height=5.678),
        _lifecycle("2099-01-02", scraper="U-HISTORY", position="", cycle=None, height=7.0),
        _lifecycle("2099-01-04", scraper="", height=None, replace=True),
        _lifecycle("2099-01-02", scraper="", height=None, replace=True),
        _lifecycle("2099-01-04", scraper="", height=None, replace=True),
    ]
    requested = [
        " Lifecycle_Trend ",
        "REPLACEMENT_EVENTS",
        " uncertainties ",
        "UNCERTAINTIES",
        b"lifecycle_trend",
    ]
    answer = service._build_user_answer(
        _results([_position(height=5.0)], [_forecast()], lifecycle=lifecycle),
        requested,
    )
    assert answer == (
        HEADER
        + "\n\nVervangadvies:"
        + "\n\n1. R-SYNTH " + LEGACY_DASH + " P-SYNTH"
        + "\n   Laatste gemeten meshoogte: 5 mm op 2099-01-02"
        + "\n   Advies: Monitoren"
        + "\n   Prognose 3 mm: rond 2099-06-01"
        + "\n   Onderbouwing: 3 meetpunten"
        + "\n\nLet op: 3 mm is de vervanggrens. Een advies 'vervanging "
        "voorbereiden' betekent niet dat het mes nu al de vervanggrens heeft bereikt."
        + "\n\nLifecycle-trend: 3 metingen verdeeld over 2 cycli."
        + "\n- R-HISTORY - P-HISTORY - cyclus C1: 2 metingen, "
        "2099-01-01 8 mm -> 2099-01-03 5.68 mm"
        + "\n- U-HISTORY: 1 meting, 2099-01-02 7 mm"
        + "\n\nGeregistreerde vervangevents: 2099-01-02, 2099-01-04"
        + "\n\nOnzekerheden:"
        + "\n- Voor alle gepresenteerde posities is volgens de huidige "
        "forecastcriteria een 3 mm-prognose beschikbaar."
        + "\n- Historische lifecycle-posities worden alleen gebruikt voor trend "
        "en vervangevents; actuele meshoogtes en vervangadvies hierboven "
        "worden daar niet uit afgeleid."
    )
    assert "generic fallback marker" not in answer


@pytest.mark.parametrize(
    ("lifecycle", "trend", "events", "uncertainty"),
    [
        (
            None,
            "Lifecycle-trend: niet beschikbaar in deze deep-analysisbron.",
            "Geregistreerde vervangevents: niet beschikbaar in deze deep-analysisbron.",
            "Lifecyclehistorie ontbreekt in deze deep-analysisresponse.",
        ),
        (
            {},
            "Lifecycle-trend: niet beschikbaar in deze deep-analysisbron.",
            "Geregistreerde vervangevents: niet beschikbaar in deze deep-analysisbron.",
            "Lifecyclehistorie ontbreekt in deze deep-analysisresponse.",
        ),
        (
            [],
            "Lifecycle-trend: niet beschikbaar in deze deep-analysisbron.",
            "Geregistreerde vervangevents: geen geregistreerd in de lifecycle.",
            "Historische lifecycle-posities worden alleen gebruikt",
        ),
        (
            [None, "row", UserDict()],
            "Lifecycle-trend: niet beschikbaar in deze deep-analysisbron.",
            "Geregistreerde vervangevents: geen geregistreerd in de lifecycle.",
            "Historische lifecycle-posities worden alleen gebruikt",
        ),
    ],
)
def test_lifecycle_outer_shape_distinguishes_unavailable_from_available_empty(
    lifecycle, trend, events, uncertainty
):
    answer = service._build_user_answer(
        _results([_position()], lifecycle=lifecycle),
        ["lifecycle_trend", "replacement_events", "uncertainties"],
    )
    assert trend in answer
    assert events in answer
    assert uncertainty in answer


def test_only_three_exact_facets_trigger_and_each_section_is_independent():
    lifecycle = [_lifecycle(replace=True)]
    base = _results([_position()], lifecycle=lifecycle)
    for request, present, absent in [
        ("lifecycle_trend", "Lifecycle-trend:", ("Geregistreerde", "Onzekerheden:")),
        ("replacement_events", "Geregistreerde vervangevents:", ("Lifecycle-trend:", "Onzekerheden:")),
        ("uncertainties", "Onzekerheden:", ("Lifecycle-trend:", "Geregistreerde")),
    ]:
        answer = service._build_user_answer(base, [request])
        assert present in answer
        assert all(marker not in answer for marker in absent)

    answer = service._build_user_answer(
        base,
        ["latest_measurements", "replacement_advice", b"uncertainties"],
    )
    assert "Lifecycle-trend:" not in answer
    assert "Geregistreerde vervangevents:" not in answer
    assert "Onzekerheden:" not in answer


def test_lifecycle_exact_fields_filters_none_falsy_bytes_cycle_and_event_identity():
    rows = [
        _lifecycle(" 2099 ", scraper=" R ", position=" P ", cycle=None, canonical=0, height=1),
        _lifecycle("2099", scraper="R", position="P", cycle="", canonical="", height=1),
        _lifecycle("2099", scraper="R", position=False, cycle=0, canonical=False, height=2),
        _lifecycle("2099", scraper="R", position=0, cycle=False, canonical=None, height=3),
        _lifecycle(b"2098", scraper=b"U", position=b"PX", cycle=b" C ", height=4),
        _lifecycle("2097", scraper="", height=None, replace=True),
        _lifecycle("2096", scraper="", canonical="E2", height=None, replace=1),
        {
            "document_date": "ALIAS",
            "scraper_types_clean": "ALIAS",
            "position_display": "ALIAS",
            "eind_meshoogte_mm": 9,
            "replace_event": True,
        },
    ]
    answer = service._build_user_answer(
        _results([_position()], lifecycle=rows),
        ["lifecycle_trend", "replacement_events"],
    )
    assert "Lifecycle-trend: 4 metingen verdeeld over 4 cycli." in answer
    assert "- R - P: 1 meting, 2099 1 mm" in answer
    assert "- R - cyclus False: 1 meting, 2099 3 mm" in answer
    assert "- R - cyclus 0: 1 meting, 2099 2 mm" in answer
    assert "b'U' - b'PX' - cyclus b' C '" in answer
    assert "Geregistreerde vervangevents: 2097" in answer
    assert "2096" not in answer
    assert "ALIAS" not in answer


def test_lifecycle_dedupe_six_fields_group_three_fields_and_stable_point_sort():
    base = _lifecycle()
    rows = [
        base,
        dict(base),
        _lifecycle(canonical="I-OTHER"),
        _lifecycle(scraper="U-HISTORY"),
        _lifecycle(position="P-OTHER"),
        _lifecycle(cycle="C-OTHER"),
        _lifecycle("2099-01-03"),
        _lifecycle(height=9),
    ]
    answer = service._build_user_answer(
        _results([_position()], lifecycle=rows), ["lifecycle_trend"]
    )
    assert "Lifecycle-trend: 7 metingen verdeeld over 4 cycli." in answer
    assert (
        "- R-HISTORY - P-HISTORY - cyclus C-HISTORY: 4 metingen, "
        "2099-01-01 8 mm -> 2099-01-03 8 mm"
    ) in answer


def test_equal_date_point_sort_is_stable_and_presentation_uses_first_and_last():
    rows = [
        _lifecycle("2099", canonical="FIRST", height=1),
        _lifecycle("2099", canonical="LAST", height=2),
    ]
    answer = service._build_user_answer(
        _results([_position()], lifecycle=rows), ["lifecycle_trend"]
    )
    assert (
        "2 metingen, 2099 1 mm -> 2099 2 mm"
        in answer
    )


def test_lifecycle_group_sort_is_reverse_latest_scraper_position_cycle_and_unlimited():
    rows = [
        _lifecycle(
            f"2099-01-{index + 1:02}",
            scraper="R",
            position="P",
            cycle=f"C-{index:02}",
            canonical=f"I-{index}",
            height=index,
        )
        for index in range(25)
    ]
    answer = service._build_user_answer(
        _results([_position()], lifecycle=rows), ["lifecycle_trend"]
    )
    assert "Lifecycle-trend: 25 metingen verdeeld over 25 cycli." in answer
    groups = [line for line in answer.splitlines() if line.startswith("- R - P")]
    assert len(groups) == 25
    assert "cyclus C-24" in groups[0]
    assert "cyclus C-00" in groups[-1]


def test_facets_are_not_evaluated_without_a_renderable_current_position():
    lifecycle = RaisingList(AssertionError("facets must remain unreachable"))
    answer = service._build_user_answer(
        _results([], lifecycle=lifecycle),
        ["lifecycle_trend", "replacement_events", "uncertainties"],
    )
    assert answer == HEADER + "\n\ngeneric fallback marker"


def test_generic_fallback_message_priority_and_direct_return_boundary():
    assert service._build_user_answer(
        _results([], message="message marker", kort_resultaat="kort marker")
    ) == (HEADER + "\n\nmessage marker")
    assert service._build_user_answer(
        _results([], message="", kort_resultaat="kort marker")
    ) == (HEADER + "\n\nkort marker")
    assert service._build_user_answer(
        _results([], message=0, kort_resultaat=False)
    ) == HEADER

    rendered = service._build_user_answer(
        _results([_position()], message="forbidden", kort_resultaat="forbidden")
    )
    assert "Vervangadvies:" in rendered
    assert "forbidden" not in rendered


def test_helper_cardinality_field_order_identity_no_mutation_and_fresh_state(monkeypatch):
    sentinels = [{"sentinel": index} for index in range(4)]
    forecast = CountingMapping(_forecast())
    position = CountingMapping(_position())
    lifecycle = CountingMapping(_lifecycle(replace=True))
    payload = CountingMapping(
        _payload([position], [forecast], lifecycle=[lifecycle])
    )
    context = payload["asset_context"]
    context.update(
        zip(
            ("area_name", "area_code", "installation_name", "installation_code"),
            sentinels,
        )
    )
    outer = CountingMapping({"action": "analysis_assistant", "result": payload})
    results = [outer]
    requested = [" Lifecycle_Trend ", "replacement_events", "uncertainties"]
    before_results = copy.deepcopy(results)
    before_requested = copy.deepcopy(requested)
    calls = []

    def display(name, code):
        calls.append((name, code))
        return f"display-{len(calls)}"

    monkeypatch.setattr(service, "_display_name_code", display)
    first = service._build_user_answer(results, requested)
    first_calls = (
        list(outer.calls),
        list(payload.calls),
        list(position.calls),
        list(forecast.calls),
        list(lifecycle.calls),
    )
    for mapping in (outer, payload, position, forecast, lifecycle):
        mapping.calls.clear()
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
    assert first_calls[0] == [("result", None), ("action", None)]
    assert first_calls[1] == [
        ("asset_resolution", None),
        ("asset_context", None),
        ("entities", None),
        ("message", None),
        ("intent", None),
        ("intent", None),
        ("intent", None),
        ("intent", None),
        ("gecombineerde_slijtage", None),
        ("forecast_3mm", None),
        ("lifecycle", None),
    ]
    assert first_calls[2] == [
        ("scraper_type_norm", None),
        ("scraper_family", None),
        ("position_display", None),
        ("laatste_inspectiedatum", None),
        ("meshoogte_mm", None),
        ("onderhoudsadvies_unified", None),
    ]
    assert first_calls[3] == [
        ("meetpunten", None),
        ("eind_meshoogte_mm", None),
        ("slijtage_mm_per_dag", None),
        ("geschatte_dagen_tot_3mm", None),
        ("geschatte_vervangdatum_bij_3mm", None),
        ("scraper_type_norm", None),
        ("geschatte_vervangdatum_bij_3mm", None),
        ("meetpunten", None),
    ]
    assert first_calls[4] == [
        ("inspected_on", None),
        ("scraper_type_norm", None),
        ("position_hint", None),
        ("cycle_id", None),
        ("canonical_inspection_key", None),
        ("replace_event", None),
        ("meshoogte_mm", None),
    ]
    assert [
        outer.calls,
        payload.calls,
        position.calls,
        forecast.calls,
        lifecycle.calls,
    ] == list(first_calls)
    assert results == before_results
    assert requested == before_requested
    assert results[0] is outer and outer["result"] is payload
    assert payload["gecombineerde_slijtage"][0] is position
    assert payload["forecast_3mm"][0] is forecast
    assert payload["lifecycle"][0] is lifecycle


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
        "message_get",
        "message_truth",
        "intent_get",
        "intent_truth",
        "intent_str",
        "positions_get",
        "positions_iter",
        "forecasts_get",
        "forecasts_iter",
        "forecast_get",
        "forecast_truth",
        "forecast_str",
        "forecast_points_compare",
        "position_get",
        "position_truth",
        "position_str",
        "position_height_float",
        "position_sort",
        "enumerate",
        "format_is_integer",
        "format_int",
        "lifecycle_get",
        "lifecycle_iter",
        "lifecycle_row_get",
        "lifecycle_cycle_str",
        "lifecycle_height_float",
        "lifecycle_point_sort",
        "replacement_sort",
        "display",
        "inspection_answer_property",
        "lifecycle_answer_property",
        "maintenance_answer_property",
    ],
)
def test_mapping_property_iteration_truth_conversion_sort_format_and_helper_throwables_propagate(
    monkeypatch, boundary, fatal
):
    error = Fatal(boundary) if fatal else RuntimeError(boundary)
    forecast = _forecast()
    position = _position()
    lifecycle = _lifecycle(replace=True)
    payload = _payload([position], [forecast], lifecycle=[lifecycle])
    results = [{"action": "analysis_assistant", "result": payload}]
    requested = ["lifecycle_trend", "replacement_events"]

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
        payload["asset_context"] = RaisingGet(
            "customer_code", error, payload["asset_context"]
        )
    elif boundary == "context_field_truth":
        payload["asset_context"]["customer_code"] = RaisingBool(error)
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
    elif boundary == "positions_get":
        results[0]["result"] = RaisingGet("gecombineerde_slijtage", error, payload)
    elif boundary == "positions_iter":
        payload["gecombineerde_slijtage"] = RaisingList(error)
    elif boundary == "forecasts_get":
        results[0]["result"] = RaisingGet("forecast_3mm", error, payload)
    elif boundary == "forecasts_iter":
        payload["forecast_3mm"] = RaisingList(error)
    elif boundary == "forecast_get":
        payload["forecast_3mm"] = [RaisingGet("meetpunten", error, forecast)]
    elif boundary == "forecast_truth":
        forecast["geschatte_vervangdatum_bij_3mm"] = RaisingBool(error)
    elif boundary == "forecast_str":
        forecast["geschatte_vervangdatum_bij_3mm"] = RaisingStr(error)
    elif boundary == "forecast_points_compare":
        RaisingGeInt.error = error
        forecast["meetpunten"] = RaisingGeInt(3)
    elif boundary == "position_get":
        payload["gecombineerde_slijtage"] = [
            RaisingGet("scraper_type_norm", error, position)
        ]
    elif boundary == "position_truth":
        position["scraper_type_norm"] = RaisingBool(error)
    elif boundary == "position_str":
        position["position_display"] = RaisingStr(error)
    elif boundary == "position_height_float":
        RaisingFloatInt.error = error
        position["meshoogte_mm"] = RaisingFloatInt(7)
    elif boundary == "position_sort":
        class Comparable:
            def strip(self):
                return self

            def __hash__(self):
                return id(self)

            def __lt__(self, _other):
                raise error

            def __gt__(self, _other):
                raise error

            def __str__(self):
                return "COMPARABLE"

        marker = object()
        position["scraper_type_norm"] = marker
        payload["gecombineerde_slijtage"] = [
            position,
            _position(scraper="Z", position="OTHER"),
        ]
        real_str = builtins.str
        monkeypatch.setattr(
            service,
            "str",
            lambda value="": Comparable() if value is marker else real_str(value),
            raising=False,
        )
    elif boundary == "enumerate":
        monkeypatch.setattr(
            service,
            "enumerate",
            lambda *_a, **_k: (_ for _ in ()).throw(error),
            raising=False,
        )
    elif boundary == "format_is_integer":
        RaisingIsIntegerFloat.error = error
        monkeypatch.setattr(
            service,
            "float",
            RaisingIsIntegerFloat,
            raising=False,
        )
        forecast["slijtage_mm_per_dag"] = 1
    elif boundary == "format_int":
        RaisingIntFloat.error = error
        monkeypatch.setattr(
            service,
            "float",
            RaisingIntFloat,
            raising=False,
        )
        forecast["slijtage_mm_per_dag"] = 1
    elif boundary == "lifecycle_get":
        results[0]["result"] = RaisingGet("lifecycle", error, payload)
    elif boundary == "lifecycle_iter":
        payload["lifecycle"] = RaisingList(error)
    elif boundary == "lifecycle_row_get":
        payload["lifecycle"] = [RaisingGet("inspected_on", error, lifecycle)]
    elif boundary == "lifecycle_cycle_str":
        lifecycle["cycle_id"] = RaisingStr(error)
    elif boundary == "lifecycle_height_float":
        RaisingFloatInt.error = error
        lifecycle["meshoogte_mm"] = RaisingFloatInt(8)
    elif boundary == "lifecycle_point_sort":
        def throwing_sorted(*args, **kwargs):
            raise error

        monkeypatch.setattr(service, "sorted", throwing_sorted, raising=False)
    elif boundary == "replacement_sort":
        real_sorted = builtins.sorted
        calls = 0

        def second_sorted(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise error
            return real_sorted(*args, **kwargs)

        monkeypatch.setattr(service, "sorted", second_sorted, raising=False)
    elif boundary == "display":
        monkeypatch.setattr(
            service,
            "_display_name_code",
            lambda *_a: (_ for _ in ()).throw(error),
        )
    elif boundary in {
        "inspection_answer_property",
        "lifecycle_answer_property",
        "maintenance_answer_property",
    }:
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
        elif boundary == "lifecycle_answer_property":
            payload = SequentialIntent(["other", "lifecycle"], **payload)
            monkeypatch.setattr(
                service,
                "run_asset_lifecycle_answer_stage",
                lambda *_a: Result(),
            )
        else:
            payload = SequentialIntent(
                ["other", "other", "maintenance_positions"], **payload
            )
            monkeypatch.setattr(
                service,
                "run_asset_maintenance_positions_answer_stage",
                lambda *_a: Result(),
            )
        results[0]["result"] = payload

    with pytest.raises(type(error), match=boundary) as raised:
        service._build_user_answer(results, requested)
    assert raised.value is error
