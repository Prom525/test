# PROMATI_AI_GATEWAY_V1
from __future__ import annotations

import os

from app.ai.models import AIProviderStatus, AIResearchRequest, AIResearchResult
from app.ai.providers.base import AIResearchProvider
from app.ai.providers.openai_provider import OpenAIResearchProvider


class AIGateway:
    """Single entry point for research-model providers."""

    def _provider_name(self) -> str:
        return (os.getenv("AI_RESEARCH_PROVIDER") or "openai").strip().lower()

    def _provider(self) -> AIResearchProvider:
        provider_name = self._provider_name()

        if provider_name == "openai":
            return OpenAIResearchProvider()

        raise RuntimeError(
            f"Unsupported AI_RESEARCH_PROVIDER: {provider_name!r}."
        )

    def status(self) -> AIProviderStatus:
        return self._provider().status()

    def research(self, request: AIResearchRequest) -> AIResearchResult:
        return self._provider().research(request)


ai_gateway = AIGateway()
