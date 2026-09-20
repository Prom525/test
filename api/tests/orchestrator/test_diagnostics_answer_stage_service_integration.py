"""Service integration tests for diagnostics answer stage dispatch."""

from __future__ import annotations

from app.orchestrator import service


def _item(action="diagnostics_assistant", **payload):
    return {"action": action, "result": payload}


def test_asset_prescan_keeps_absolute_priority(monkeypatch):
    calls = []
    monkeypatch.setattr(service, "run_diagnostics_answer_stage", lambda value: calls.append(value) or "diagnostics")
    monkeypatch.setattr(service, "_display_name_code", lambda *_args: "unknown")
    results = [_item(status="later"), _item("asset_assistant", asset_resolution={}, asset_context={}, message="asset")]
    assert service._build_user_answer(results).endswith("\n\nasset")
    assert calls == []


def test_exact_action_selector_calls_once_and_returns_direct_value(monkeypatch):
    sentinel = "synthetic direct answer"
    selected = {"status": "selected"}
    calls = []
    monkeypatch.setattr(service, "run_diagnostics_answer_stage", lambda value: calls.append(value) or sentinel)
    results = [_item("ignored", context_type="diagnostics_assistant", status="alias"), {"action": "diagnostics_assistant", "result": selected}, _item(status="later")]
    assert service._build_user_answer(results) == sentinel
    assert calls == [selected]


def test_context_alias_continues_to_following_analysis_scope(monkeypatch):
    def forbidden(_value):
        raise AssertionError("must not run")

    monkeypatch.setattr(service, "run_diagnostics_answer_stage", forbidden)
    results = [_item("ignored", context_type="diagnostics_assistant", status="alias"), _item("ignored", context_type="analysis_scope", kort_resultaat="scope")]
    assert service._build_user_answer(results) == "scope"


def test_non_mapping_is_skipped_before_first_diagnostics_entry(monkeypatch):
    selected = {"status": "first"}
    calls = []
    monkeypatch.setattr(service, "run_diagnostics_answer_stage", lambda value: calls.append(value) or "first")
    results = [{"action": "diagnostics_assistant", "result": None}, {"action": "diagnostics_assistant", "result": selected}, _item(status="second")]
    assert service._build_user_answer(results) == "first"
    assert calls == [selected]
