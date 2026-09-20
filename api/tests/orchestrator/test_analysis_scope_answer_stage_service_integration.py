"""Service integration tests for analysis-scope answer-stage dispatch."""

from app.orchestrator import service
from app.orchestrator.analysis_scope_answer_stage import AnalysisScopeAnswerStageResult


def _item(action="ignored", **payload):
    return {"action": action, "result": payload}


def test_asset_and_diagnostics_keep_priority(monkeypatch):
    calls = []
    monkeypatch.setattr(service, "run_analysis_scope_answer_stage", lambda value: calls.append(value) or AnalysisScopeAnswerStageResult("scope"))
    monkeypatch.setattr(service, "_display_name_code", lambda *_args: "unknown")
    results = [_item(context_type="analysis_scope"), _item("asset", asset_resolution={}, asset_context={}, message="asset")]
    assert service._build_user_answer(results).endswith("\n\nasset")
    assert calls == []
    monkeypatch.setattr(service, "run_diagnostics_answer_stage", lambda _value: "diagnostics")
    assert service._build_user_answer([_item("diagnostics_assistant"), _item(context_type="analysis_scope")]) == "diagnostics"
    assert calls == []


def test_exact_context_selector_calls_once_and_returns_direct_answer(monkeypatch):
    selected = {"context_type": "analysis_scope", "kort_resultaat": "selected"}
    calls = []
    monkeypatch.setattr(service, "run_analysis_scope_answer_stage", lambda value: calls.append(value) or AnalysisScopeAnswerStageResult("direct"))
    results = [_item("analysis_scope", kort_resultaat="action alias"), _item(context_type="ANALYSIS_SCOPE"), {"action": "ignored", "result": selected}]
    assert service._build_user_answer(results) == "direct"
    assert calls == [selected]


def test_none_falls_through_to_following_scope_and_first_answer_wins(monkeypatch):
    calls = []
    def stage(value):
        calls.append(value)
        return AnalysisScopeAnswerStageResult(value.get("answer"))
    monkeypatch.setattr(service, "run_analysis_scope_answer_stage", stage)
    first = {"context_type": "analysis_scope", "answer": None}
    second = {"context_type": "analysis_scope", "answer": "winner"}
    third = {"context_type": "analysis_scope", "answer": "unreachable"}
    assert service._build_user_answer([{"result": first}, {"result": second}, {"result": third}]) == "winner"
    assert calls == [first, second]


def test_none_falls_through_to_product_and_general_none(monkeypatch):
    monkeypatch.setattr(service, "run_analysis_scope_answer_stage", lambda _value: AnalysisScopeAnswerStageResult(None))
    monkeypatch.setattr(service, "run_multi_product_answer_stage", lambda *_args, **_kwargs: type("Result", (), {"delegated_answer": "product"})())
    assert service._build_user_answer([_item(context_type="analysis_scope"), _item("product_assistant", context_type="product_assistant")]) == "product"
    assert service._build_user_answer([_item(context_type="analysis_scope")]) is None
