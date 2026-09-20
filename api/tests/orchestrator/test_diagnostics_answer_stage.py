"""Direct tests for the dependency-free diagnostics answer stage."""

from __future__ import annotations

import copy

import pytest

from app.orchestrator.diagnostics_answer_stage import run_diagnostics_answer_stage


class Fatal(BaseException):
    pass


class RaisingDict(dict):
    def __init__(self, key, error, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.key = key
        self.error = error

    def get(self, key, default=None):
        if key == self.key:
            raise self.error
        return super().get(key, default)


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({}, "Diagnose (diagnostics / overview): unknown"),
        ({"status": None, "mode": "", "domain": 0}, "Diagnose (diagnostics / overview): unknown"),
        ({"status": 7, "mode": ["deep"], "domain": {"name": "db"}}, "Diagnose ({'name': 'db'} / ['deep']): 7"),
        ({"summary": {"message": ["synthetic", 2]}}, "Diagnose (diagnostics / overview): unknown\n\n['synthetic', 2]"),
        ({"summary": []}, "Diagnose (diagnostics / overview): unknown"),
    ],
)
def test_header_defaults_conversions_and_summary_shapes(payload, expected):
    assert run_diagnostics_answer_stage(payload) == expected


@pytest.mark.parametrize(
    ("summary", "tail"),
    [
        ({"gpt_diagnosis": {"headline": 42, "interpretation": [0, False, None, "first", {"k": "v"}] + [f"line-{i}" for i in range(8)]}, "message": "shadowed"}, "\n\n42\n- first\n- {'k': 'v'}\n- line-0\n- line-1\n- line-2"),
        ({"gpt_diagnosis": "wrong", "message": "compatibility", "row_count": 9}, "\n\ncompatibility"),
        ({"gpt_diagnosis": {}, "message": "suppressed", "row_count": 9}, ""),
        ({"view_name": "vw", "object_name": "obj", "row_count": 0, "dependencies_found": False, "objects_checked": [], "comparisons_made": {"count": 2}}, "\n\nView: vw; Object: obj; Rijen: 0; Dependencies: False; Objecten gecontroleerd: []; Vergelijkingen: {'count': 2}"),
    ],
)
def test_gpt_message_compact_precedence_limits_and_field_order(summary, tail):
    assert run_diagnostics_answer_stage({"summary": summary}) == "Diagnose (diagnostics / overview): unknown" + tail


def test_findings_actions_headings_limits_truthiness_and_conversion():
    payload = {
        "findings": ["ignored", {"severity": None, "issue": "a"}, {"severity": 3, "message": ["b"]}, {"severity": "warn", "issue": 0, "message": "fallback"}, {"issue": False}, {"severity": "error", "issue": {"code": 9}}, {"issue": "sixth"}, {"issue": "eighth"}, {"issue": "beyond"}],
        "recommended_actions": [0, False, None, "restart", {"step": 2}, "beyond"],
    }
    assert run_diagnostics_answer_stage(payload) == (
        "Diagnose (diagnostics / overview): unknown\n\nBevindingen:\n"
        "- [INFO] a\n- [3] ['b']\n- [WARN] fallback\n- [ERROR] {'code': 9}\n"
        "- [INFO] sixth\n- [INFO] eighth\n\nAanbevolen vervolgstappen:\n"
        "- restart\n- {'step': 2}"
    )


@pytest.mark.parametrize(
    ("payload", "suffix"),
    [({"findings": [None, "x", {}]}, "\n\nBevindingen:"), ({"recommended_actions": [None, 0, False]}, "\n\nAanbevolen vervolgstappen:")],
)
def test_truthy_lists_emit_empty_sections_and_wrong_shapes_do_not(payload, suffix):
    header = "Diagnose (diagnostics / overview): unknown"
    assert run_diagnostics_answer_stage(payload) == header + suffix
    assert run_diagnostics_answer_stage({key: {"wrong": "shape"} for key in payload}) == header


def test_input_is_not_mutated():
    payload = {"summary": {"row_count": 1}, "findings": [{"issue": "x"}], "recommended_actions": ["y"]}
    before = copy.deepcopy(payload)
    run_diagnostics_answer_stage(payload)
    assert payload == before


@pytest.mark.parametrize("error_type", [RuntimeError, Fatal])
@pytest.mark.parametrize("location", ["payload", "summary", "finding"])
def test_exception_and_baseexception_propagate(error_type, location):
    error = error_type(f"synthetic-{location}")
    if location == "payload":
        payload = RaisingDict("status", error)
    elif location == "summary":
        payload = {"summary": RaisingDict("gpt_diagnosis", error)}
    else:
        payload = {"findings": [RaisingDict("severity", error)]}
    with pytest.raises(error_type, match=f"synthetic-{location}"):
        run_diagnostics_answer_stage(payload)

