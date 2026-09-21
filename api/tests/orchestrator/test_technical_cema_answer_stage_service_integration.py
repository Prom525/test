import pytest

from app.orchestrator import service
from app.orchestrator.technical_cema_answer_stage import TechnicalCemaAnswerStageResult


def _technical(source_code="CEMA_BELT_CONVEYORS_7", *, action="technical_assistant"):
    return {"action": action, "result": {"source_code": source_code}}


def test_exact_selector_conversion_and_one_stage_call(monkeypatch):
    calls = []

    class Alias:
        def __str__(self):
            return "technical_assistant"

    monkeypatch.setattr(
        service,
        "run_technical_cema_answer_stage",
        lambda value: calls.append(value) or TechnicalCemaAnswerStageResult(answer="CEMA"),
    )
    item = _technical(action=Alias())
    assert service._build_user_answer([item]) == "CEMA"
    assert calls == [item["result"]]


def test_inexact_selector_does_not_call_stage(monkeypatch):
    monkeypatch.setattr(
        service,
        "run_technical_cema_answer_stage",
        lambda _value: pytest.fail("stage must not be called"),
    )
    assert service._build_user_answer([_technical(action="TECHNICAL_ASSISTANT")]) is None


def test_wrong_code_none_falls_through_to_next_technical_result():
    assert service._build_user_answer([
        _technical("OTHER"),
        _technical(),
    ]).startswith("CEMA-referentiegegevens")


def test_wrong_code_falls_through_to_general_none():
    assert service._build_user_answer([_technical("OTHER")]) is None


def test_earlier_branch_keeps_priority(monkeypatch):
    monkeypatch.setattr(service, "run_diagnostics_answer_stage", lambda _value: "earlier")
    assert service._build_user_answer([
        {"action": "diagnostics_assistant", "result": {}},
        _technical(),
    ]) == "earlier"
