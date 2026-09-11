"""CP0: reproduceerbare nulmeting; dit bestand definieert geen productfixes."""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

import pytest

from app.orchestrator.complexity import assess_research_requirement
from app.orchestrator.planner import build_execution_plan
from app.orchestrator.routing_sanity import apply_routing_sanity
from app.orchestrator.understanding import understand_query


FIXTURE = Path(__file__).parent / "fixtures" / "cp0_regression_cases.json"


def _data():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _value(value):
    return getattr(value, "value", value)


def _entity(plan, name):
    item = plan.entities.get(name)
    return _value(item.value) if item is not None else None


def _plan(question):
    plan = apply_routing_sanity(understand_query(question))
    plan = assess_research_requirement(plan)
    return build_execution_plan(plan)


def _snapshot(plan):
    result = {
        "primary": _value(plan.primary_domain),
        "domains": [_value(item) for item in plan.domains],
        "intent": plan.intent,
        "multi": plan.multi_intent,
        "research": plan.research_required,
        "tasks": [f"{_value(item.domain)}:{item.intent}" for item in plan.intent_tasks],
        "steps": [f"{_value(item.domain)}:{item.action}" for item in plan.execution_steps],
    }
    for name in ("diagnostics_domain", "band_code"):
        if name in plan.entities:
            result[name] = _entity(plan, name)
    return result


CASES = _data()["cases"]
GOLDENS = {item["id"]: item for item in _data()["goldens"]}


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_cp0_current_routing_and_planning_snapshot(case):
    """Locks the observed pre-fix state without executing specialists."""
    actual = _snapshot(_plan(case["question"]))
    assert {key: actual.get(key) for key in case["current"]} == case["current"]


@pytest.mark.parametrize(
    "case",
    [pytest.param(case, marks=pytest.mark.xfail(strict=True, reason=f"CP0 known gap {case['id']}")) for case in CASES],
    ids=lambda case: case["id"],
)
def test_cp0_desired_routing_contracts_document_known_gaps(case):
    actual = _snapshot(_plan(case["question"]))
    desired = case["desired"]
    for key, expected in desired.items():
        if key == "step_domains":
            assert [item.split(":", 1)[0] for item in actual["steps"]] == expected
        else:
            assert actual.get(key) == expected


def _multi_raw_answer():
    payload = {
        "measurement_count": 4,
        "min_meshoogte_mm": 3.0,
        "max_meshoogte_mm": 6.0,
        "position_measurements": [{"locatie_raw": "PRIMAIR", "mes_vervangen": None, "meshoogte_mm": 3.0, "scraper_type_raw": "H 1200-1000 SP/M3"}],
    }
    return "Inspection: MV1 Mengveld 1 2026-05-27 latest_blade_height DIRECT_ACTIE_3MM_OVERDUE " + json.dumps(payload) + (" x" * 700)


def test_cp0_mv1_multi_intent_public_answer_golden():
    from app.orchestrator.service import _p4_15cp4f_apply

    response = _p4_15cp4f_apply({"answer": _multi_raw_answer(), "evidence_pipeline": {}})
    assert all(fragment in response["answer"] for fragment in GOLDENS["G1"]["contains"])
    assert len(response["answer"].encode("utf-8")) < 700


def test_cp0_mv1_single_intent_public_answer_golden():
    from app.orchestrator.service import _p4_15cp4f_apply

    response = _p4_15cp4f_apply({"answer": "MV1 Mengveld 1: 43 actuele geregistreerde schraperposities", "evidence_pipeline": {}})
    assert all(fragment in response["answer"] for fragment in GOLDENS["G2"]["contains"])
    assert len(response["answer"].encode("utf-8")) < 500


LIVE_BASE_URL = os.getenv("PROMATI_CP0_LIVE_BASE_URL", "").rstrip("/")


@pytest.mark.skipif(not LIVE_BASE_URL, reason="set PROMATI_CP0_LIVE_BASE_URL for live CP0 metrics")
@pytest.mark.parametrize("item", CASES + list(GOLDENS.values()), ids=lambda item: item["id"])
def test_cp0_optional_live_http_metrics(item, record_property):
    body = json.dumps({"vraag": item["question"], "include_trace": True}).encode("utf-8")
    request = Request(f"{LIVE_BASE_URL}/orchestrator/ask", data=body, method="POST", headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=90) as live_response:
        raw = live_response.read()
    response = json.loads(raw.decode("utf-8"))
    plan = response.get("query_plan") or {}
    results = response.get("results") or []
    composition = (response.get("evidence_pipeline") or {}).get("task_public_composition_authority_p4_6f") or {}
    metrics = {
        "domains": plan.get("domains") or [],
        "intent_tasks": len(plan.get("intent_tasks") or []),
        "execution_actions": [result.get("action") for result in results],
        "accepted_evidence": sum(result.get("accepted") is True for result in results),
        "failed_evidence": sum(result.get("accepted") is False for result in results),
        "answer_length": len(str(response.get("answer") or "")),
        "response_bytes": len(raw),
        "composition_authoritative": composition.get("authoritative"),
        "composition_reason": composition.get("reason"),
    }
    record_property("cp0_metrics", json.dumps(metrics, separators=(",", ":")))
    assert response.get("status") in {"ok", "partial", "clarification_required"}
    if item["id"] in GOLDENS:
        assert all(fragment in str(response.get("answer") or "") for fragment in item["contains"])
