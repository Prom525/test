# PROMATI_AI_GATEWAY_V1
from __future__ import annotations

from abc import ABC, abstractmethod

from app.ai.models import AIProviderStatus, AIResearchRequest, AIResearchResult


class AIResearchProvider(ABC):
    @abstractmethod
    def status(self) -> AIProviderStatus:
        raise NotImplementedError

    @abstractmethod
    def research(self, request: AIResearchRequest) -> AIResearchResult:
        raise NotImplementedError
