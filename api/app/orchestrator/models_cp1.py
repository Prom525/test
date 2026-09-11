from typing import Literal

from app.orchestrator.models import OrchestratorAskRequest as BaseOrchestratorAskRequest


class OrchestratorAskRequest(BaseOrchestratorAskRequest):
    """Public HTTP request contract with explicit response shaping."""

    response_profile: Literal["compact", "debug"] = "compact"
