"""Characterization of the inline ORG presentation boundary.

This suite intentionally describes the current legacy contract.  It does not
propose the interface of a future extracted stage.
"""

import ast
import copy
import inspect

import pytest

from app.orchestrator import service
from app.orchestrator.analysis_scope_answer_stage import AnalysisScopeAnswerStageResult
from app.orchestrator.multi_product_answer_stage import MultiProductAnswerStageResult
from app.orchestrator.single_family_product_answer_stage import SingleFamilyProductAnswerStageResult


class Fatal(BaseException):
    pass


class ExplodingDict(dict):
    def __init__(self, error):
        super().__init__()
        self.error = error

    def get(self, _key, _default=None):
        raise self.error


class ExplodingTruth:
    def __init__(self, error):
        self.error = error

    def __bool__(self):
        raise self.error


class ExplodingString:
    def __init__(self, error):
        self.error = error

    def __str__(self):
        raise self.error


def _org(*, action="org_assistant", context_type=None, mode=None, nested=None, status=None):
    specialist = {"result": nested}
    if context_type is not None:
        specialist["context_type"] = context_type
    if mode is not None:
        specialist["mode"] = mode
    if status is not None:
        specialist["status"] = status
    return {"action": action, "result": specialist}


def _location(**overrides):
    row = {
        "locatie": "Synthetic site",
        "adres": "Examplelaan 7",
        "plaats": "Voorbeeldstad",
        "land": "BE",
    }
    row.update(overrides)
    return row


def _function(**overrides):
    row = {
        "weergavenaam": "Synthetic Person",
        "officiele_functienaam": "Synthetic Lead",
        "functie_naam": "Compatibility Role",
        "afdeling": "Synthetic Department",
        "kerntaken": "Synthetic responsibilities.",
    }
    row.update(overrides)
    return row


def _decline_product_stages(monkeypatch):
    monkeypatch.setattr(
        service,
        "run_multi_product_answer_stage",
        lambda *_args: MultiProductAnswerStageResult(delegated_answer=None),
    )
    monkeypatch.setattr(
        service,
        "run_single_family_product_answer_stage",
        lambda *_args, **_kwargs: SingleFamilyProductAnswerStageResult(answer=None),
    )


@pytest.mark.parametrize("selector", ["action", "context_type"])
def test_exact_selector_aliases_reach_org(selector):
    item = _org(
        action="org_assistant" if selector == "action" else "other",
        context_type="org_assistant" if selector == "context_type" else None,
        mode="location_info",
        nested={"results": [_location()]},
    )
    assert service._build_user_answer([item]) == (
        "Promati is gevestigd op:\n- Synthetic site: Examplelaan 7"
    )


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "ORG_ASSISTANT",
        "Org_Assistant",
        " org_assistant",
        "org_assistant ",
        b"org_assistant",
        0,
        False,
        ["org_assistant"],
        {"value": "org_assistant"},
        object(),
    ],
)
def test_selector_is_exact_case_and_whitespace_sensitive(value):
    assert service._build_user_answer(
        [_org(action=value, mode="location_info", nested={"results": [_location()]})]
    ) is None


@pytest.mark.parametrize("selector", ["action", "context_type"])
def test_selector_string_conversion_can_create_exact_alias(selector):
    class Alias:
        def __str__(self):
            return "org_assistant"

    item = _org(
        action=Alias() if selector == "action" else "other",
        context_type=Alias() if selector == "context_type" else None,
        mode="function_info",
        nested={"results": [_function()]},
    )
    assert service._build_user_answer([item]).startswith("Synthetic Person is Synthetic Lead.")


@pytest.mark.parametrize(
    ("nested_status", "outer_status", "message", "expected"),
    [
        ("not_found", "ok", "Nested message", "Nested message"),
        ("NOT_FOUND", None, 7, "7"),
        (None, "not_found", "Outer fallback", "Outer fallback"),
        ("", "NOT_FOUND", ["message"], "['message']"),
        (" not_found ", "not_found", "Ignored outer", None),
        ("not_found", None, "", None),
        ("not_found", None, None, None),
        ("not_found", None, 0, None),
        ("clarification", None, "Not presented", None),
        ("error", None, "Not presented", None),
        ("fallback", None, "Not presented", None),
        ("ok", None, "Not presented", None),
        (7, None, "Not presented", None),
        (b"not_found", None, "Not presented", None),
    ],
)
def test_not_found_status_fallback_truthiness_and_message_conversion(
    nested_status, outer_status, message, expected
):
    nested = {"status": nested_status, "message": message}
    assert service._build_user_answer(
        [_org(nested=nested, status=outer_status)]
    ) == expected


def test_not_found_string_message_is_returned_by_identity():
    message = "Synthetic identity message " * 4
    answer = service._build_user_answer(
        [_org(nested={"status": "not_found", "message": message})]
    )
    assert answer is message


@pytest.mark.parametrize("status", [None, "", "ok", "clarification", "error", "fallback", 0, 7, [], {}])
def test_status_does_not_gate_successful_location_rendering(status):
    assert service._build_user_answer(
        [_org(mode="location_info", nested={"status": status, "results": [_location()]})]
    ) == "Promati is gevestigd op:\n- Synthetic site: Examplelaan 7"


@pytest.mark.parametrize("mode", [None, "", "LOCATION_INFO", " location_info", "location_info ", b"location_info", 0, []])
def test_mode_is_exact_after_string_conversion(mode):
    assert service._build_user_answer(
        [_org(mode=mode, nested={"results": [_location()]})]
    ) is None


@pytest.mark.parametrize(
    ("rows", "expected"),
    [
        (None, None),
        ("rows", None),
        ({}, None),
        ((), None),
        ([], None),
        ([None, "row", 7, []], None),
        ([{"locatie": "Router-only", "adres": None, "plaats": None}], None),
        ([_location(locatie="HQ")], "Promati is gevestigd op:\n- HQ: Examplelaan 7"),
        ([_location(locatie=None)], "Promati is gevestigd op:\n- Voorbeeldstad: Examplelaan 7"),
        ([_location(locatie=None, plaats=None)], "Promati is gevestigd op:\n- Examplelaan 7"),
        ([_location(adres=None, locatie="HQ")], "Promati is gevestigd op:\n- HQ: Voorbeeldstad, BE"),
        ([_location(adres=None, locatie=None)], "Promati is gevestigd op:\n- Voorbeeldstad: Voorbeeldstad, BE"),
        ([_location(adres=None, locatie=None, land=None)], "Promati is gevestigd op:\n- Voorbeeldstad: Voorbeeldstad"),
        ([_location(adres=0, plaats=7, locatie=0, land=9)], "Promati is gevestigd op:\n- 7: 7, 9"),
        ([_location(adres=7, locatie=8)], "Promati is gevestigd op:\n- 8: 7"),
        ([_location(adres=b"A", locatie=["L"])], "Promati is gevestigd op:\n- ['L']: b'A'"),
    ],
)
def test_location_shape_field_priority_truthiness_and_exact_output(rows, expected):
    assert service._build_user_answer(
        [_org(mode="location_info", nested={"results": rows})]
    ) == expected


def test_location_keeps_input_order_and_all_renderable_mapping_rows():
    rows = [None, _location(locatie="First"), "bad", _location(locatie="Second")]
    assert service._build_user_answer(
        [_org(mode="location_info", nested={"results": rows})]
    ) == (
        "Promati is gevestigd op:\n"
        "- First: Examplelaan 7\n"
        "- Second: Examplelaan 7"
    )


@pytest.mark.parametrize(
    ("rows", "expected"),
    [
        (None, None),
        ("rows", None),
        ({}, None),
        ((), None),
        ([], None),
        ([None, "row", 7, []], None),
        ([_function()], "Synthetic Person is Synthetic Lead.\nAfdeling: Synthetic Department.\n\nKerntaken:\nSynthetic responsibilities."),
        ([_function(officiele_functienaam=None)], "Synthetic Person is Compatibility Role.\nAfdeling: Synthetic Department.\n\nKerntaken:\nSynthetic responsibilities."),
        ([_function(officiele_functienaam="", functie_naam=None)], "Functiegegevens gevonden voor Synthetic Person.\nAfdeling: Synthetic Department.\n\nKerntaken:\nSynthetic responsibilities."),
        ([_function(weergavenaam=None, afdeling=None, kerntaken=None)], "Onbekende persoon is Synthetic Lead."),
        ([_function(weergavenaam=0, officiele_functienaam=7, afdeling=8, kerntaken=["task"])], "Onbekende persoon is 7.\nAfdeling: 8.\n\nKerntaken:\n['task']"),
        (["bad", _function(weergavenaam="First"), _function(weergavenaam="Second")], "First is Synthetic Lead.\nAfdeling: Synthetic Department.\n\nKerntaken:\nSynthetic responsibilities."),
    ],
)
def test_function_shape_alias_priority_first_mapping_and_exact_output(rows, expected):
    assert service._build_user_answer(
        [_org(mode="function_info", nested={"results": rows})]
    ) == expected


@pytest.mark.parametrize("alias", ["answer", "kort_resultaat", "short_result", "data", "result"])
def test_unrecognized_payload_aliases_do_not_supply_org_answer(alias):
    nested = {alias: "Synthetic alias answer"}
    assert service._build_user_answer([_org(nested=nested)]) is None


def test_result_order_first_successful_org_wins_and_malformed_entries_fall_through():
    results = [
        _org(nested=None),
        _org(mode="location_info", nested={"results": []}),
        _org(mode="function_info", nested={"results": [_function(weergavenaam="Winner")]}),
        _org(nested={"status": "not_found", "message": "Never reached"}),
    ]
    assert service._build_user_answer(results).startswith("Winner is Synthetic Lead.")


def test_org_precedes_technical_and_technical_is_only_the_next_stop_boundary():
    technical = {
        "action": "technical_assistant",
        "result": {"source_code": "CEMA_BELT_CONVEYORS_7"},
    }
    assert service._build_user_answer(
        [_org(nested={"status": "not_found", "message": "ORG wins"}), technical]
    ) == "ORG wins"
    assert service._build_user_answer([_org(nested=None), technical]) == (
        "CEMA-referentiegegevens zijn beschikbaar, maar in dit "
        "specialistresultaat is geen definitierecord van CEMA aanwezig."
    )


def test_asset_prescan_has_global_priority_over_org():
    asset = {
        "action": "analysis_assistant",
        "result": {"asset_resolution": {}, "message": "Asset wins"},
    }
    answer = service._build_user_answer(
        [_org(nested={"status": "not_found", "message": "ORG loses"}), asset]
    )
    assert answer.endswith("\n\nAsset wins")


def test_diagnostics_analysis_scope_and_product_precede_later_org(monkeypatch):
    monkeypatch.setattr(service, "run_diagnostics_answer_stage", lambda value: "Diagnostics wins")
    monkeypatch.setattr(
        service,
        "run_analysis_scope_answer_stage",
        lambda value: AnalysisScopeAnswerStageResult(answer="Scope wins"),
    )
    monkeypatch.setattr(
        service,
        "run_multi_product_answer_stage",
        lambda *_args: MultiProductAnswerStageResult(delegated_answer="Product wins"),
    )
    org = _org(nested={"status": "not_found", "message": "ORG loses"})
    assert service._build_user_answer([{"action": "diagnostics_assistant", "result": {}}, org]) == "Diagnostics wins"
    assert service._build_user_answer([{"action": "other", "result": {"context_type": "analysis_scope"}}, org]) == "Scope wins"
    assert service._build_user_answer([{"action": "product_assistant", "result": {}}, org]) == "Product wins"


def test_declined_earlier_product_then_org_executes_once(monkeypatch):
    calls = []
    monkeypatch.setattr(
        service,
        "run_multi_product_answer_stage",
        lambda *args: calls.append(("multi", args)) or MultiProductAnswerStageResult(delegated_answer=None),
    )
    monkeypatch.setattr(
        service,
        "run_single_family_product_answer_stage",
        lambda *args, **kwargs: calls.append(("single", args, kwargs)) or SingleFamilyProductAnswerStageResult(answer=None),
    )
    org = _org(nested={"status": "not_found", "message": "ORG answer"})
    results = [{"action": "product_assistant", "result": {}}, org]
    assert service._build_user_answer(results) == "ORG answer"
    assert [call[0] for call in calls] == ["multi", "single"]
    assert calls[0][1][0] is results


def test_no_mutation_of_results_requested_information_or_nested_payloads():
    results = [_org(mode="location_info", nested={"results": [_location()]})]
    requested = [" ORG ", "org", ""]
    before_results = copy.deepcopy(results)
    before_requested = copy.deepcopy(requested)
    service._build_user_answer(results, requested)
    assert results == before_results
    assert requested == before_requested


@pytest.mark.parametrize("error", [RuntimeError("synthetic exception"), Fatal("synthetic fatal")])
def test_mapping_get_errors_propagate_exception_and_baseexception(error):
    with pytest.raises(type(error), match=str(error)):
        service._build_user_answer([{"action": "org_assistant", "result": ExplodingDict(error)}])


@pytest.mark.parametrize("error", [RuntimeError("synthetic exception"), Fatal("synthetic fatal")])
def test_string_conversion_errors_propagate_exception_and_baseexception(error):
    with pytest.raises(type(error), match=str(error)):
        service._build_user_answer([_org(action=ExplodingString(error), nested={})])


@pytest.mark.parametrize("error", [RuntimeError("synthetic exception"), Fatal("synthetic fatal")])
def test_truthiness_errors_propagate_exception_and_baseexception(error):
    nested = {"status": "not_found", "message": ExplodingTruth(error)}
    with pytest.raises(type(error), match=str(error)):
        service._build_user_answer([_org(nested=nested)])


@pytest.mark.parametrize("error", [RuntimeError("synthetic exception"), Fatal("synthetic fatal")])
def test_result_iteration_errors_propagate_exception_and_baseexception(error):
    class ExplodingResults:
        def __iter__(self):
            raise error

    with pytest.raises(type(error), match=str(error)):
        service._build_user_answer(ExplodingResults())


@pytest.mark.parametrize("error", [RuntimeError("synthetic exception"), Fatal("synthetic fatal")])
def test_location_row_iteration_errors_propagate_exception_and_baseexception(error):
    class ExplodingList(list):
        def __iter__(self):
            raise error

    with pytest.raises(type(error), match=str(error)):
        service._build_user_answer(
            [_org(mode="location_info", nested={"results": ExplodingList()})]
        )


def test_org_branch_is_inline_without_runtime_helper_and_before_technical_structurally():
    source = inspect.getsource(service._build_user_answer)
    tree = ast.parse(source)
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "run_org_answer_stage" not in calls
    assert source.index("# ORG") < source.index("# TECHNICAL - CEMA")
    assert source.count('action == "org_assistant"') == 1
    assert source.count('context_type == "org_assistant"') == 1
