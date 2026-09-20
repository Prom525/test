"""Characterize the inline diagnostics presentation in ``_build_user_answer``."""
from __future__ import annotations

import ast
import copy
import inspect

import pytest

from app.orchestrator import service


class Fatal(BaseException):
    """A non-Exception sentinel used to prove transparent propagation."""


class RaisingDict(dict):
    def __init__(self, key, error, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.key = key
        self.error = error

    def get(self, key, default=None):
        if key == self.key:
            raise self.error
        return super().get(key, default)


def _item(action="diagnostics_assistant", **payload):
    return {"action": action, "result": payload}


def _diagnostics_if_node():
    tree = ast.parse(inspect.getsource(service._build_user_answer))
    function = tree.body[0]
    non_asset_loop = next(
        node
        for node in function.body
        if isinstance(node, ast.For)
        and any(
            isinstance(child, ast.If)
            and ast.unparse(child.test) == "action == 'diagnostics_assistant'"
            for child in node.body
        )
    )
    return next(
        child
        for child in non_asset_loop.body
        if isinstance(child, ast.If)
        and ast.unparse(child.test) == "action == 'diagnostics_assistant'"
    )


def test_structure_fixes_selector_position_return_and_absence_of_dependencies():
    branch = _diagnostics_if_node()
    assert ast.unparse(branch.test) == "action == 'diagnostics_assistant'"
    assert len(branch.body) == 1
    assert isinstance(branch.body[0], ast.Return)
    assert ast.unparse(branch.body[0].value) == (
        "run_diagnostics_answer_stage(specialist_result)"
    )

    calls = [
        ast.unparse(node.func)
        for node in ast.walk(branch)
        if isinstance(node, ast.Call)
    ]
    assert calls == ["run_diagnostics_answer_stage"]


def test_asset_prescan_has_absolute_priority_and_does_not_execute_diagnostics(monkeypatch):
    diagnostic = RaisingDict(
        "status", AssertionError("diagnostics branch must not execute"), status="later"
    )
    results = [
        {"action": "diagnostics_assistant", "result": diagnostic},
        _item(
            "asset_assistant",
            asset_resolution={},
            asset_context={},
            message="asset wins",
        ),
    ]
    before = copy.deepcopy(results)
    monkeypatch.setattr(service, "_display_name_code", lambda *_args: "onbekend")

    answer = service._build_user_answer(results)

    assert answer.endswith("\n\nasset wins")
    assert results == before


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({}, "Diagnose (diagnostics / overview): unknown"),
        (
            {"status": None, "mode": "", "domain": 0},
            "Diagnose (diagnostics / overview): unknown",
        ),
        (
            {"status": 7, "mode": ["deep"], "domain": {"name": "db"}},
            "Diagnose ({'name': 'db'} / ['deep']): 7",
        ),
        (
            {"summary": {"message": ["synthetic", 2]}},
            "Diagnose (diagnostics / overview): unknown\n\n['synthetic', 2]",
        ),
        (
            {"summary": []},
            "Diagnose (diagnostics / overview): unknown",
        ),
    ],
)
def test_header_defaults_string_conversion_and_summary_shapes_are_exact(payload, expected):
    assert service._build_user_answer([_item(**payload)]) == expected


@pytest.mark.parametrize(
    ("summary", "expected_tail"),
    [
        (
            {
                "gpt_diagnosis": {
                    "headline": 42,
                    "interpretation": [0, False, None, "first", {"k": "v"}]
                    + [f"line-{index}" for index in range(8)],
                },
                "message": "shadowed",
                "view_name": "shadowed",
            },
            "\n\n42\n- first\n- {'k': 'v'}\n- line-0\n- line-1\n- line-2",
        ),
        (
            {
                "gpt_diagnosis": "not-a-mapping",
                "message": "compatibility message",
                "row_count": 9,
            },
            "\n\ncompatibility message",
        ),
        (
            {
                "gpt_diagnosis": {},
                "message": "suppressed by mapping",
                "row_count": 9,
            },
            "",
        ),
        (
            {
                "view_name": "vw_synthetic",
                "object_name": "obj_synthetic",
                "row_count": 0,
                "dependencies_found": False,
                "objects_checked": [],
                "comparisons_made": {"count": 2},
            },
            "\n\nView: vw_synthetic; Object: obj_synthetic; Rijen: 0; "
            "Dependencies: False; Objecten gecontroleerd: []; Vergelijkingen: {'count': 2}",
        ),
    ],
)
def test_summary_precedence_limits_and_compact_field_order_are_exact(summary, expected_tail):
    header = "Diagnose (diagnostics / overview): unknown"
    assert service._build_user_answer([_item(summary=summary)]) == header + expected_tail


def test_findings_and_recommendations_fix_headings_limits_conversion_and_order():
    findings = [
        "ignored",
        {"severity": None, "issue": "issue-a"},
        {"severity": 3, "message": ["message-b"]},
        {"severity": "warn", "issue": 0, "message": "fallback-b"},
        {"issue": False},
        {"severity": "error", "issue": {"code": 9}},
        {"issue": "sixth-rendered"},
        {"issue": "eighth-slot"},
        {"issue": "beyond-limit"},
    ]
    actions = [0, False, None, "restart", {"step": 2}, "beyond-limit"]

    answer = service._build_user_answer(
        [_item(findings=findings, recommended_actions=actions)]
    )

    assert answer == (
        "Diagnose (diagnostics / overview): unknown\n\nBevindingen:\n"
        "- [INFO] issue-a\n- [3] ['message-b']\n- [WARN] fallback-b\n"
        "- [ERROR] {'code': 9}\n- [INFO] sixth-rendered\n- [INFO] eighth-slot\n\n"
        "Aanbevolen vervolgstappen:\n- restart\n- {'step': 2}"
    )


@pytest.mark.parametrize(
    ("payload", "suffix"),
    [({"findings": [None, "x", {}]}, "\n\nBevindingen:"),
     ({"recommended_actions": [None, 0, False]}, "\n\nAanbevolen vervolgstappen:")],
)
def test_truthy_lists_emit_empty_sections_while_wrong_shapes_emit_nothing(payload, suffix):
    header = "Diagnose (diagnostics / overview): unknown"
    assert service._build_user_answer([_item(**payload)]) == header + suffix
    wrong_shapes = {key: {"not": "a list"} for key in payload}
    assert service._build_user_answer([_item(**wrong_shapes)]) == header


def test_exact_action_only_first_wins_and_recognized_empty_entry_never_falls_through():
    results = [
        _item("ignored", context_type="diagnostics_assistant", status="alias"),
        _item(status="first"),
        _item(status="second"),
        _item("ignored", context_type="analysis_scope", kort_resultaat="later scope"),
        _item("product_assistant", context_type="product_assistant"),
        _item("org_assistant", context_type="org_assistant"),
        _item("technical_assistant", context_type="technical_assistant"),
    ]
    before = copy.deepcopy(results)

    assert service._build_user_answer(results) == (
        "Diagnose (diagnostics / overview): first"
    )
    assert results == before

    assert service._build_user_answer([
        _item(),
        _item("ignored", context_type="analysis_scope", kort_resultaat="unreachable"),
    ]) == "Diagnose (diagnostics / overview): unknown"


def test_context_alias_does_not_select_diagnostics_and_stops_at_next_branch_boundary():
    results = [
        _item("ignored", context_type="diagnostics_assistant", status="not selected"),
        _item("ignored", context_type="analysis_scope", kort_resultaat="scope sentinel"),
    ]
    assert service._build_user_answer(results) == "scope sentinel"


def test_requested_information_and_results_are_not_mutated():
    results = [_item(status="ok", summary={"row_count": 1})]
    requested = [" Price ", 7, "", None]
    before_results = copy.deepcopy(results)
    before_requested = copy.deepcopy(requested)

    assert service._build_user_answer(results, requested).endswith("Rijen: 1")
    assert results == before_results
    assert requested == before_requested


@pytest.mark.parametrize("error_type", [RuntimeError, Fatal])
@pytest.mark.parametrize("location", ["item", "payload", "summary", "finding"])
def test_exception_and_baseexception_from_mapping_operations_propagate(error_type, location):
    error = error_type(f"synthetic-{location}")
    if location == "item":
        results = [RaisingDict("result", error, action="diagnostics_assistant", result={})]
    elif location == "payload":
        results = [{"action": "diagnostics_assistant", "result": RaisingDict("status", error)}]
    elif location == "summary":
        results = [_item(summary=RaisingDict("gpt_diagnosis", error))]
    else:
        results = [_item(findings=[RaisingDict("severity", error)])]

    with pytest.raises(error_type, match=f"synthetic-{location}"):
        service._build_user_answer(results)
