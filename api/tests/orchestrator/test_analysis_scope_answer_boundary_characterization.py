"""Characterize the service-owned analysis-scope presentation branch.

This freezes current behavior for deciding whether a mechanical extraction is
worthwhile.  It deliberately stops at the next product/ORG/technical branch.
"""

from __future__ import annotations

import ast
import copy
import inspect

import pytest

from app.orchestrator import service


class Fatal(BaseException):
    """Non-Exception sentinel used to prove uncaught propagation."""


class ExplodingStr:
    def __init__(self, error):
        self._error = error

    def __str__(self):
        raise self._error


class ExplodingBool:
    def __init__(self, error):
        self._error = error

    def __bool__(self):
        raise self._error


class ExplodingList(list):
    def __init__(self, values, error):
        super().__init__(values)
        self._error = error

    def __iter__(self):
        raise self._error


class RaisingDict(dict):
    def __init__(self, key, error, **values):
        super().__init__(values)
        self._key = key
        self._error = error

    def get(self, key, default=None):
        if key == self._key:
            raise self._error
        return super().get(key, default)


def _item(action="ignored", **payload):
    return {"action": action, "result": payload}


def _scope(**payload):
    return _item(context_type="analysis_scope", **payload)


def test_selector_is_exact_case_sensitive_context_type_only():
    assert service._build_user_answer([_scope(kort_resultaat="selected")]) == "selected"

    aliases = [
        _item("analysis_scope", kort_resultaat="action alias"),
        _item(context_type="ANALYSIS_SCOPE", kort_resultaat="case alias"),
        _item(context_type=" analysis_scope ", kort_resultaat="spaced alias"),
        _item(context_type=b"analysis_scope", kort_resultaat="bytes alias"),
    ]
    assert service._build_user_answer(aliases) is None


@pytest.mark.parametrize(
    ("short", "expected"),
    [
        ("text", "text"),
        ("  ", "  "),
        (7, "7"),
        (b"bytes", "b'bytes'"),
        (["x"], "['x']"),
        ({"k": "v"}, "{'k': 'v'}"),
        (object(), None),
        (None, None),
        ("", None),
        (0, None),
        (False, None),
        ([], None),
        ({}, None),
    ],
)
def test_kort_resultaat_uses_truthiness_then_exact_str(short, expected):
    answer = service._build_user_answer([_scope(kort_resultaat=short)])
    if isinstance(short, object) and type(short) is object:
        assert answer == str(short)
    else:
        assert answer == expected


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"operation": "list", "subject": "bands", "bands": ["B-1", 2, b"B-3"]}, "Banden: B-1, 2, b'B-3'"),
        ({"operation": "list", "subject": "bands", "bands": [], "kort_resultaat": ""}, None),
        ({"operation": "list", "subject": "bands", "bands": ("B-1",), "kort_resultaat": ""}, None),
        ({"operation": "LIST", "subject": "bands", "bands": ["B-1"]}, None),
        ({"operation": "list", "subject": "BANDS", "bands": ["B-1"]}, None),
        ({"operation": b"list", "subject": "bands", "bands": ["B-1"]}, None),
        ({"operation": "list", "subject": "bands", "bands": ["hidden"], "kort_resultaat": "short"}, "short"),
    ],
)
def test_list_bands_fallback_has_exact_gates_and_conversion(payload, expected):
    assert service._build_user_answer([_scope(**payload)]) == expected


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"count_semantics": "current_registered_scraper_positions", "data_quality": {"semantic_note": "note"}}, "\nnote"),
        ({"kort_resultaat": "short", "count_semantics": "current_registered_scraper_positions", "data_quality": {"semantic_note": 9}}, "short\n\n9"),
        ({"count_semantics": "current_registered_scraper_positions", "data_quality": {"semantic_note": "  "}}, "\n  "),
        ({"count_semantics": "current_registered_scraper_positions", "data_quality": {"semantic_note": ""}}, None),
        ({"count_semantics": "current_registered_scraper_positions", "data_quality": [("semantic_note", "ignored")]}, None),
        ({"count_semantics": "CURRENT_REGISTERED_SCRAPER_POSITIONS", "data_quality": {"semantic_note": "ignored"}}, None),
        ({"count_semantics": "historical_maintenance_ranking_rows"}, "\nLet op: dit betreft historische onderhoudsregels binnen de canonical scope. Dat is niet automatisch dezelfde set als de actuele unified schraperposities."),
        ({"operation": "analyse"}, "\nDe wear-evidence kan historische posities/cycli bevatten en wordt daarom als aanvullende historie naast de actuele unified snapshot gebruikt."),
        ({"operation": "analyze"}, None),
        ({"kort_resultaat": "short", "count_semantics": "historical_maintenance_ranking_rows", "operation": "analyse"}, "short\n\nLet op: dit betreft historische onderhoudsregels binnen de canonical scope. Dat is niet automatisch dezelfde set als de actuele unified schraperposities.\n\nDe wear-evidence kan historische posities/cycli bevatten en wordt daarom als aanvullende historie naast de actuele unified snapshot gebruikt."),
    ],
)
def test_notes_defaults_and_separator_text_are_exact(payload, expected):
    assert service._build_user_answer([_scope(**payload)]) == expected


def test_message_and_unrelated_fields_are_never_output_aliases():
    result = _scope(message="must not leak", result="must not leak", answer="must not leak")
    assert service._build_user_answer([result]) is None


def test_asset_prescan_is_absolute_and_diagnostics_precedes_scope(monkeypatch):
    calls = []
    monkeypatch.setattr(service, "_display_name_code", lambda *_args: "unknown")
    monkeypatch.setattr(service, "run_diagnostics_answer_stage", lambda value: calls.append(value) or "diagnostics")
    results = [
        _scope(kort_resultaat="scope"),
        _item("asset", asset_resolution={}, asset_context={}, message="asset"),
    ]
    assert service._build_user_answer(results).endswith("\n\nasset")
    assert calls == []

    diagnostic = {"status": "first"}
    assert service._build_user_answer([
        {"action": "diagnostics_assistant", "result": diagnostic},
        _scope(kort_resultaat="scope"),
    ]) == "diagnostics"
    assert calls == [diagnostic]


def test_scope_precedes_later_branches_and_first_answer_wins(monkeypatch):
    monkeypatch.setattr(
        service,
        "run_multi_product_answer_stage",
        lambda *_args: pytest.fail("product branch crossed the stop boundary"),
    )
    results = [
        _scope(),
        _scope(kort_resultaat="winner"),
        _scope(kort_resultaat="never reached"),
        _item("product_assistant", context_type="product_assistant"),
        _item("org_assistant", context_type="org_assistant"),
        _item("technical_assistant", context_type="technical_assistant"),
    ]
    assert service._build_user_answer(results) == "winner"


def test_recognized_empty_entries_fall_through_in_input_order_to_none():
    results = [
        {"action": "ignored", "result": None},
        _scope(kort_resultaat=""),
        _scope(operation="list", subject="bands", bands=[]),
        _scope(data_quality={"semantic_note": "ignored"}),
    ]
    assert service._build_user_answer(results) is None


def test_inputs_and_nested_specialist_payloads_are_not_mutated():
    results = [
        _scope(
            kort_resultaat="synthetic",
            bands=["B-1"],
            data_quality={"semantic_note": "note", "nested": [1, 2]},
        )
    ]
    requested = [" Price ", "PRICE", " inventory "]
    before_results = copy.deepcopy(results)
    before_requested = copy.deepcopy(requested)

    assert service._build_user_answer(results, requested) == "synthetic"
    assert results == before_results
    assert requested == before_requested


@pytest.mark.parametrize("error", [RuntimeError("synthetic get"), Fatal("synthetic fatal")])
def test_mapping_get_propagates_exception_and_baseexception(error):
    payload = RaisingDict("kort_resultaat", error, context_type="analysis_scope")
    with pytest.raises(type(error), match=str(error)):
        service._build_user_answer([{"action": "ignored", "result": payload}])


@pytest.mark.parametrize("error", [RuntimeError("synthetic exception"), Fatal("synthetic fatal")])
def test_outer_entry_get_propagates_exception_and_baseexception(error):
    with pytest.raises(type(error), match=str(error)):
        service._build_user_answer([RaisingDict("result", error)])


@pytest.mark.parametrize("error_type", [RuntimeError, Fatal])
@pytest.mark.parametrize(
    "kind",
    [
        "context_str",
        "short_bool",
        "operation_str",
        "subject_str",
        "semantics_str",
        "bands_iteration",
        "note_bool",
    ],
)
def test_string_truthiness_and_iteration_throwables_propagate(kind, error_type):
    error = error_type("synthetic throwable")
    payloads = {
        "context_str": {"context_type": ExplodingStr(error)},
        "short_bool": {"context_type": "analysis_scope", "kort_resultaat": ExplodingBool(error)},
        "operation_str": {"context_type": "analysis_scope", "operation": ExplodingStr(error)},
        "subject_str": {"context_type": "analysis_scope", "operation": "list", "subject": ExplodingStr(error)},
        "semantics_str": {"context_type": "analysis_scope", "count_semantics": ExplodingStr(error)},
        "bands_iteration": {"context_type": "analysis_scope", "operation": "list", "subject": "bands", "bands": ExplodingList(["B-1"], error)},
        "note_bool": {"context_type": "analysis_scope", "count_semantics": "current_registered_scraper_positions", "data_quality": {"semantic_note": ExplodingBool(error)}},
    }
    with pytest.raises(error_type, match="synthetic throwable"):
        payload = payloads[kind]
        service._build_user_answer([{"action": "ignored", "result": payload}])


def test_non_dict_mapping_and_malformed_outer_entry_behavior_is_exact():
    assert service._build_user_answer([
        {"action": "ignored", "result": RaisingDict("never", RuntimeError("unused"), context_type="other")},
        {"action": "ignored", "result": [("context_type", "analysis_scope")]},
        _scope(kort_resultaat="winner"),
    ]) == "winner"

    with pytest.raises(AttributeError, match="get"):
        service._build_user_answer([object()])


def test_ast_proves_branch_order_stage_call_and_downstream_stop_boundary():
    tree = ast.parse(inspect.getsource(service._build_user_answer))
    function = tree.body[0]
    non_asset_loop = function.body[6]
    conditions = [
        ast.unparse(node.test)
        for node in non_asset_loop.body
        if isinstance(node, ast.If)
    ]
    assert conditions[:4] == [
        "not isinstance(specialist_result, dict)",
        "action == 'diagnostics_assistant'",
        "context_type == 'analysis_scope'",
        "action == 'product_assistant' or context_type == 'product_assistant'",
    ]

    scope_if = next(
        node for node in non_asset_loop.body
        if isinstance(node, ast.If) and ast.unparse(node.test) == "context_type == 'analysis_scope'"
    )
    named_calls = [
        node.func.id
        for node in ast.walk(scope_if)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    assert named_calls == ["run_analysis_scope_answer_stage"]
    assert not any(isinstance(node, (ast.Try, ast.Raise)) for node in ast.walk(scope_if))
    returns = [node for node in ast.walk(scope_if) if isinstance(node, ast.Return)]
    assert len(returns) == 1
    assert ast.unparse(returns[0].value) == "analysis_scope_answer_stage_result.answer"
