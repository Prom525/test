from __future__ import annotations

import json
from uuid import UUID

from fastapi import BackgroundTasks

from app.orchestrator.response_shaping import shape_orchestrator_response
from app.routers import orchestrator_api


def _internal_response():
    return {
        "status": "ok",
        "answer": "antwoord",
        "query_plan": {"domains": ["inspection"], "intent_tasks": []},
        "results": [{"accepted": True, "result": {"raw": "x" * 50_000}}],
        "research": {"raw": "x" * 50_000},
        "evidence_pipeline": {"raw": "x" * 50_000},
        "observability": {"raw": "x" * 50_000},
        "trace": {"raw": "x" * 50_000},
    }


def test_compact_response_contains_only_bounded_trace_metadata():
    internal = _internal_response()
    internal["trace_id"] = "725511dd-0db0-48db-b493-3b526b1cc518"

    response = shape_orchestrator_response(internal, "compact")

    assert response["trace_id"] == internal["trace_id"]
    assert isinstance(response["trace_id"], str)
    for field in ("query_plan", "results", "research", "evidence_pipeline", "observability", "trace"):
        assert field not in response
    assert len(json.dumps(response).encode("utf-8")) < 12_000


def test_router_uses_same_trace_id_for_response_and_run_logging(monkeypatch):
    internal = _internal_response()
    background_tasks = BackgroundTasks()
    monkeypatch.setattr(orchestrator_api, "run_orchestrator", lambda payload: internal)

    response = orchestrator_api.orchestrator_ask(
        type("Request", (), {"response_profile": "compact"})(),
        background_tasks,
    )

    UUID(response["trace_id"])
    assert response["trace_id"]
    assert background_tasks.tasks[0].args[0]["trace_id"] == response["trace_id"]

def test_debug_response_keeps_full_internals_and_same_trace_id(monkeypatch):
    internal = _internal_response()
    background_tasks = BackgroundTasks()
    monkeypatch.setattr(orchestrator_api, "run_orchestrator", lambda payload: internal)

    response = orchestrator_api.orchestrator_ask(
        type("Request", (), {"response_profile": "debug"})(),
        background_tasks,
    )

    assert response is internal
    assert response["trace"]
    assert response["observability"]
    assert background_tasks.tasks[0].args[0]["trace_id"] == response["trace_id"]
