from __future__ import annotations

import json

from app.orchestrator.response_shaping import shape_orchestrator_response


def _large_internal_response():
    return {
        "status": "ok",
        "answer": "A" * 20_000,
        "query_plan": {"domains": ["inspection", "product"], "intent_tasks": [{"task_id": "t1", "domain": "inspection", "intent": "inspection_latest", "primary": True, "scope": {"raw": "x" * 10_000}}]},
        "research": {"raw": "x" * 50_000},
        "results": [{"accepted": True, "result": {"canonical_positions": ["x" * 50_000]}}, {"accepted": False, "error": "x" * 50_000}],
        "evidence_pipeline": {"raw": "x" * 100_000},
        "observability": {"raw": "x" * 100_000},
        "trace": {"raw": "x" * 100_000},
    }


def test_compact_profile_omits_large_internal_fields_and_is_bounded():
    response = shape_orchestrator_response(_large_internal_response(), "compact")
    assert set(response) == {"status", "answer", "response_profile", "domains", "tasks", "coverage"}
    assert response["coverage"] == {"total": 2, "accepted": 1, "failed": 1}
    assert len(json.dumps(response, ensure_ascii=False).encode("utf-8")) < 12_000


def test_include_trace_data_cannot_escape_through_compact_profile():
    response = shape_orchestrator_response(_large_internal_response(), "compact")
    for field in ("trace", "results", "research", "query_plan", "evidence_pipeline", "observability"):
        assert field not in response


def test_debug_profile_preserves_full_response():
    internal = _large_internal_response()
    assert shape_orchestrator_response(internal, "debug") is internal
