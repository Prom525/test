from app.orchestrator.models_cp1 import OrchestratorAskRequest
from fastapi import BackgroundTasks

from app.routers import orchestrator_api


def test_response_profile_defaults_to_compact():
    assert OrchestratorAskRequest(vraag="testvraag").response_profile == "compact"


def test_debug_response_profile_is_explicitly_available():
    request = OrchestratorAskRequest(vraag="testvraag", response_profile="debug")
    assert request.response_profile == "debug"


def test_router_defaults_to_compact_even_when_include_trace_is_true(monkeypatch):
    internal = {
        "status": "ok", "answer": "antwoord",
        "query_plan": {"domains": ["inspection"], "intent_tasks": []},
        "results": [], "trace": {"large": "x" * 1000},
        "evidence_pipeline": {"large": "x" * 1000},
        "research": {"large": "x" * 1000},
        "observability": {"large": "x" * 1000},
    }
    monkeypatch.setattr(orchestrator_api, "run_orchestrator", lambda payload: internal)
    response = orchestrator_api.orchestrator_ask(
        OrchestratorAskRequest(vraag="test", include_trace=True),
        BackgroundTasks(),
    )
    assert response["response_profile"] == "compact"
    assert "trace" not in response
