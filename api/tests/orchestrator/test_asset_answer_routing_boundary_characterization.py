"""Characterize only the asset prescan and intent-routing boundary."""
from __future__ import annotations

import ast
import copy
import inspect

import pytest

from app.orchestrator import service


class Fatal(BaseException):
    """A non-Exception sentinel used to pin uncaught propagation."""


def _item(action="analysis_assistant", **payload):
    payload.setdefault("asset_resolution", {})
    payload.setdefault("asset_context", {})
    return {"action": action, "result": payload}


def _route_payload(intent):
    payload = {
        "intent": intent,
        "message": "generic marker",
        "resultaat": [
            {
                "document_date": "2099-01-04",
                "inspected_on": "2099-01-03",
                "inspection_key": "INS-SYNTH",
                "canonical_inspection_key": "CAN-SYNTH",
                "scraper_type_raw": "SYNTH-LATEST",
                "scraper_type_norm": "R-SYNTH",
                "position_hint": "P-SYNTH",
                "cycle_id": "C-SYNTH",
                "meshoogte_mm": 7,
                "scraper_types_clean": "SYNTH-MAINTENANCE",
                "cycle_end": "2099-01-02",
                "prioriteit": 1,
                "eind_meshoogte_mm": 7,
                "meetpunten": 2,
            }
        ],
        "gecombineerde_slijtage": [
            {
                "scraper_type_norm": "R-SYNTH-DEEP",
                "scraper_family": "R",
                "position_display": "P-DEEP",
                "laatste_inspectiedatum": "2099-01-01",
                "meshoogte_mm": 7,
            }
        ],
        "forecast_3mm": [],
    }
    return payload


def _asset_if_nodes():
    function = ast.parse(inspect.getsource(service._build_user_answer)).body[0]
    asset_if = function.body[5]
    return function, asset_if, [
        node for node in asset_if.body if isinstance(node, ast.If)
    ]


def test_ast_pins_first_match_prescan_shape_and_exact_route_order():
    function, asset_if, route_nodes = _asset_if_nodes()
    prescan = function.body[4]

    assert isinstance(prescan, ast.For)
    assert ast.unparse(prescan.iter) == "results"
    assert [type(node) for node in prescan.body] == [ast.Assign, ast.If, ast.If]
    assert ast.unparse(prescan.body[1].test) == "not isinstance(specialist_result, dict)"
    selector = prescan.body[2]
    assert "specialist_result.get('asset_resolution')" in ast.unparse(selector.test)
    assert "dict" in ast.unparse(selector.test)
    assert isinstance(selector.body[-1], ast.Break)
    assert ast.unparse(asset_if.test) == "asset_result is not None"

    route_tests = [
        ast.unparse(node.test)
        for node in route_nodes
        if any(
            isinstance(constant, ast.Constant)
            and constant.value in {
                "inspection_summary",
                "lifecycle",
                "maintenance_positions",
                "band_deep_analysis",
            }
            for constant in ast.walk(node.test)
        )
    ]
    assert [
        value
        for test in route_tests
        for value in [
            next(
                constant.value
                for constant in ast.walk(ast.parse(test))
                if isinstance(constant, ast.Constant)
                and constant.value in {
                    "inspection_summary",
                    "lifecycle",
                    "maintenance_positions",
                    "band_deep_analysis",
                }
            )
        ]
    ] == [
        "inspection_summary",
        "lifecycle",
        "maintenance_positions",
        "band_deep_analysis",
    ]
    assert all("asset_action == 'analysis_assistant'" in test for test in route_tests)


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
        {"asset_resolution": "dict-like"},
        {"asset_resolution": []},
        {"asset_resolution": ()},
        {"asset_resolution": 0},
    ],
)
def test_prescan_requires_dict_result_and_dict_asset_resolution(bad_result):
    first = {"action": "asset_assistant", "result": bad_result}
    second = _item(message="selected")

    assert service._build_user_answer([first, second]).endswith("selected")


def test_prescan_uses_first_match_and_does_not_touch_later_entries():
    class Untouched:
        def get(self, _key):
            raise AssertionError("prescan must stop after its first match")

    first = _item(message="first")
    second = _item(message="second")

    assert service._build_user_answer([first, second, Untouched()]).endswith("first")


@pytest.mark.parametrize("asset_index", [0, 1, 2, 3, 4, 5])
def test_asset_has_absolute_priority_over_every_non_asset_family(
    monkeypatch, asset_index
):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("non-asset dispatch must not run")

    monkeypatch.setattr(service, "run_diagnostics_answer_stage", forbidden)
    monkeypatch.setattr(service, "run_analysis_scope_answer_stage", forbidden)
    monkeypatch.setattr(service, "run_multi_product_answer_stage", forbidden)
    monkeypatch.setattr(service, "run_org_answer_stage", forbidden)
    monkeypatch.setattr(service, "run_technical_cema_answer_stage", forbidden)
    competitors = [
        {"action": "diagnostics_assistant", "result": {}},
        {"action": "other", "result": {"context_type": "analysis_scope"}},
        {"action": "product_assistant", "result": {}},
        {"action": "org_assistant", "result": {}},
        {"action": "technical_assistant", "result": {}},
    ]
    competitors.insert(asset_index, _item(message="asset wins"))

    assert service._build_user_answer(competitors).endswith("asset wins")


def test_selected_objects_are_read_only_and_display_helper_receives_exact_values(monkeypatch):
    area_name, area_code, installation_name, installation_code = (
        object(), object(), object(), object()
    )
    context = {
        "customer_code": "CUSTOMER-SYNTH",
        "site_code": "SITE-SYNTH",
        "area_name": area_name,
        "area_code": area_code,
        "installation_name": installation_name,
        "installation_code": installation_code,
    }
    entities = {"band_code": "B-SYNTH"}
    payload = {
        "asset_resolution": {},
        "asset_context": context,
        "entities": entities,
        "message": "marker",
    }
    results = [{"action": "asset_assistant", "result": payload}]
    requested = [" Latest_Measurements "]
    before_context = dict(context)
    before_entities = dict(entities)
    before_payload = dict(payload)
    before_requested = copy.deepcopy(requested)
    calls = []

    def display(name, code):
        calls.append((name, code))
        return "display"

    monkeypatch.setattr(service, "_display_name_code", display)
    service._build_user_answer(results, requested)

    assert calls == [(area_name, area_code), (installation_name, installation_code)]
    assert context == before_context
    assert entities == before_entities
    assert payload == before_payload
    assert requested == before_requested
    assert results[0]["result"] is payload
    assert payload["asset_context"] is context
    assert payload["entities"] is entities


@pytest.mark.parametrize(
    ("intent", "marker"),
    [
        ("inspection_summary", "Laatste inspectie:"),
        ("lifecycle", "Trendgegevens:"),
        ("maintenance_positions", "Onderhoudsprioriteit:"),
        ("band_deep_analysis", "Vervangadvies:"),
    ],
)
def test_each_exact_intent_reaches_its_first_return_boundary_without_mutation(
    intent, marker
):
    results = [_item(**_route_payload(intent))]
    before = copy.deepcopy(results)

    answer = service._build_user_answer(results)

    assert marker in answer
    assert "generic marker" not in answer
    assert results == before


@pytest.mark.parametrize(
    "intent",
    [
        None,
        "",
        " inspection_summary",
        "inspection_summary ",
        "Inspection_Summary",
        b"inspection_summary",
        123,
    ],
)
def test_intent_is_case_and_whitespace_sensitive_and_non_strings_are_stringified(intent):
    payload = _route_payload(intent)
    if intent is None:
        payload.pop("intent")

    answer = service._build_user_answer([_item(**payload)])

    assert answer.endswith("generic marker")
    assert all(
        marker not in answer
        for marker in (
            "Laatste inspectie:",
            "Trendgegevens:",
            "Onderhoudsprioriteit:",
            "Vervangadvies:",
        )
    )


def test_conflicting_route_payloads_are_selected_only_by_exact_intent():
    for intent, expected, rejected in [
        ("inspection_summary", "Laatste inspectie:", "Trendgegevens:"),
        ("lifecycle", "Trendgegevens:", "Onderhoudsprioriteit:"),
        ("maintenance_positions", "Onderhoudsprioriteit:", "Vervangadvies:"),
        ("band_deep_analysis", "Vervangadvies:", "Laatste inspectie:"),
    ]:
        answer = service._build_user_answer([_item(**_route_payload(intent))])
        assert expected in answer
        assert rejected not in answer


@pytest.mark.parametrize(
    "intent",
    ["inspection_summary", "lifecycle", "maintenance_positions", "band_deep_analysis"],
)
def test_recognized_but_non_renderable_route_falls_through_to_generic_asset_answer(intent):
    payload = _route_payload(intent)
    payload["resultaat"] = []
    payload["gecombineerde_slijtage"] = []

    assert service._build_user_answer([_item(**payload)]).endswith("generic marker")


@pytest.mark.parametrize("bad_action", [" analysis_assistant", "Analysis_Assistant", b"analysis_assistant"])
def test_action_selector_is_exact_after_stringification(bad_action):
    answer = service._build_user_answer(
        [_item(action=bad_action, **_route_payload("inspection_summary"))]
    )
    assert answer.endswith("generic marker")
    assert "Laatste inspectie:" not in answer


@pytest.mark.parametrize("error", [RuntimeError("exception"), Fatal("base-exception")])
@pytest.mark.parametrize(
    "boundary", ["outer_get", "result_get", "action_str", "intent_str", "display"]
)
def test_prescan_selector_and_first_helper_do_not_catch_throwables(
    monkeypatch, boundary, error
):
    class RaisingOuter:
        def get(self, _key):
            raise error

    class RaisingResult(dict):
        def get(self, key, default=None):
            if key == "asset_resolution":
                raise error
            return super().get(key, default)

    class RaisingAction:
        def __str__(self):
            raise error

    if boundary == "outer_get":
        results = [RaisingOuter()]
    elif boundary == "result_get":
        results = [{"result": RaisingResult()}]
    elif boundary == "action_str":
        results = [_item(action=RaisingAction(), message="unused")]
    elif boundary == "intent_str":
        results = [_item(intent=RaisingAction(), message="unused")]
    else:
        results = [_item(message="unused")]
        monkeypatch.setattr(
            service,
            "_display_name_code",
            lambda *_args: (_ for _ in ()).throw(error),
        )

    with pytest.raises(type(error), match=str(error)):
        service._build_user_answer(results)
