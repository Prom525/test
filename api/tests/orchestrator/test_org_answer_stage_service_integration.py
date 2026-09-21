from app.orchestrator import service
from app.orchestrator.org_answer_stage import OrgAnswerStageResult


def _item(action="org_assistant", context_type=None, nested=None):
    return {"action": action, "result": {"context_type": context_type, "result": nested}}


def test_exact_selector_conversion_and_single_stage_call(monkeypatch):
    calls = []

    class Alias:
        def __str__(self):
            return "org_assistant"

    monkeypatch.setattr(
        service,
        "run_org_answer_stage",
        lambda value: calls.append(value) or OrgAnswerStageResult(answer="answer"),
    )
    item = _item(action=Alias(), nested={})
    assert service._build_user_answer([item]) == "answer"
    assert calls == [item["result"]]


def test_nonmatching_selector_does_not_call_stage(monkeypatch):
    monkeypatch.setattr(service, "run_org_answer_stage", lambda _value: (_ for _ in ()).throw(AssertionError()))
    assert service._build_user_answer([_item(action="ORG_ASSISTANT", nested={})]) is None


def test_direct_answer_identity(monkeypatch):
    answer = "identity " * 20
    monkeypatch.setattr(service, "run_org_answer_stage", lambda _value: OrgAnswerStageResult(answer=answer))
    assert service._build_user_answer([_item(nested={})]) is answer


def test_none_falls_through_to_next_org(monkeypatch):
    answers = iter([None, "second"])
    monkeypatch.setattr(service, "run_org_answer_stage", lambda _value: OrgAnswerStageResult(answer=next(answers)))
    assert service._build_user_answer([_item(nested={}), _item(nested={})]) == "second"


def test_none_falls_through_to_technical_and_general_none(monkeypatch):
    monkeypatch.setattr(service, "run_org_answer_stage", lambda _value: OrgAnswerStageResult(answer=None))
    technical = {"action": "technical_assistant", "result": {"source_code": "CEMA_BELT_CONVEYORS_7"}}
    assert service._build_user_answer([_item(nested={}), technical]).startswith("CEMA-referentiegegevens")
    assert service._build_user_answer([_item(nested={})]) is None


def test_earlier_asset_diagnostics_scope_and_product_keep_priority(monkeypatch):
    calls = []
    monkeypatch.setattr(service, "run_org_answer_stage", lambda value: calls.append(value) or OrgAnswerStageResult(answer="org"))
    asset = {"action": "analysis_assistant", "result": {"asset_resolution": {}, "message": "asset"}}
    assert service._build_user_answer([_item(nested={}), asset]).endswith("asset")
    assert calls == []
