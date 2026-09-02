# PROMATI_AI_GATEWAY_V1
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AIProviderStatus(BaseModel):
    provider: str
    configured: bool
    model: str | None = None
    model_source: str | None = None
    package_available: bool = False
    detail: str | None = None


class AIResearchRequest(BaseModel):
    question: str = Field(min_length=1)
    context: dict[str, Any] = Field(default_factory=dict)
    max_output_tokens: int = Field(default=1200, ge=64, le=4000)


class AIResearchResult(BaseModel):
    provider: str
    model: str
    text: str
    response_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
