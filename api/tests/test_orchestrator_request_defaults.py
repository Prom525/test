from __future__ import annotations

from app.orchestrator.models import (
    OrchestratorAskRequest,
)


def test_include_trace_defaults_to_false():
    request = OrchestratorAskRequest(
        vraag="testvraag"
    )

    assert request.include_trace is False


def test_include_trace_can_be_explicitly_enabled():
    request = OrchestratorAskRequest(
        vraag="testvraag",
        include_trace=True,
    )

    assert request.include_trace is True


def test_include_trace_can_be_explicitly_disabled():
    request = OrchestratorAskRequest(
        vraag="testvraag",
        include_trace=False,
    )

    assert request.include_trace is False