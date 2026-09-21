import pytest

from app.orchestrator import service
from app.orchestrator.asset_inspection_summary_answer_stage import (
    AssetInspectionSummaryAnswerStageResult,
)


def _payload(intent="inspection_summary", message="generic"):
    return {
        "asset_resolution": {},
        "asset_context": {
            "customer_code": "C",
            "site_code": "S",
            "area_name": "A",
            "area_code": "AC",
            "installation_name": "I",
            "installation_code": "IC",
            "band_code_display": "B",
        },
        "intent": intent,
        "message": message,
        "resultaat": [{"document_date": "2099", "meshoogte_mm": None}],
    }


def test_first_asset_priority_header_call_order_exact_selector_and_success(monkeypatch):
    first = _payload()
    second = _payload(message="second")
    calls = []

    def display(name, code):
        calls.append(("display", name, code))
        return f"{name}/{code}"

    def run(payload, header):
        calls.append(("stage", payload, header))
        return AssetInspectionSummaryAnswerStageResult(answer="direct")

    monkeypatch.setattr(service, "_display_name_code", display)
    monkeypatch.setattr(service, "run_asset_inspection_summary_answer_stage", run)
    answer = service._build_user_answer(
        [
            {"action": "ignored", "result": {"message": "nonasset"}},
            {"action": "analysis_assistant", "result": first},
            {"action": "analysis_assistant", "result": second},
        ]
    )
    assert answer == "direct"
    assert calls == [
        ("display", "A", "AC"),
        ("display", "I", "IC"),
        (
            "stage",
            first,
            (
                "Klant: C",
                "Plaats: S",
                "Gebied: A/AC",
                "Installatie: I/IC",
                "Bandnummer: B",
            ),
        ),
    ]


@pytest.mark.parametrize(
    ("action", "intent"),
    [
        ("ANALYSIS_ASSISTANT", "inspection_summary"),
        ("analysis_assistant", " inspection_summary"),
        ("analysis_assistant", "INSPECTION_SUMMARY"),
        ("other", "inspection_summary"),
    ],
)
def test_selector_is_exact_and_does_not_call_stage(monkeypatch, action, intent):
    monkeypatch.setattr(
        service,
        "run_asset_inspection_summary_answer_stage",
        lambda *_: pytest.fail("stage reached"),
    )
    assert service._build_user_answer(
        [{"action": action, "result": _payload(intent=intent)}]
    ).endswith("generic")


def test_none_falls_through_to_generic_and_success_skips_other_routes(monkeypatch):
    monkeypatch.setattr(
        service,
        "run_asset_inspection_summary_answer_stage",
        lambda *_: AssetInspectionSummaryAnswerStageResult(answer=None),
    )
    assert service._build_user_answer(
        [{"action": "analysis_assistant", "result": _payload()}]
    ).endswith("generic")

    monkeypatch.setattr(
        service,
        "run_asset_inspection_summary_answer_stage",
        lambda *_: AssetInspectionSummaryAnswerStageResult(answer="success"),
    )
    payload = _payload()
    payload["resultaat"] = object()
    assert service._build_user_answer(
        [{"action": "analysis_assistant", "result": payload}]
    ) == "success"
