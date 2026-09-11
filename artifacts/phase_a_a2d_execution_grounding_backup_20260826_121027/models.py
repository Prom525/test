from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Domain(str, Enum):
    PRODUCT = "product"
    INSPECTION = "inspection"
    TECHNICAL = "technical"
    RFQ = "rfq"
    ORG = "org"
    DIAGNOSTICS = "diagnostics"


class QueryClass(str, Enum):
    BUSINESS = "business"
    SYSTEM_META = "system_meta"
    CONVERSATIONAL = "conversational"
    UNKNOWN = "unknown"


class DetectedEntity(BaseModel):
    name: str
    raw_value: Any = None
    value: Any = None

    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    source: str = "query_understanding"


class ExecutionStep(BaseModel):
    step_id: str
    domain: Domain
    action: str

    params: dict[str, Any] = Field(
        default_factory=dict
    )

    required: bool = True
    fallback_allowed: bool = True


class QueryPlan(BaseModel):
    original_question: str
    normalized_question: str

    # PROMATI_PHASE_A_QUERY_CLASS_SHADOW_A1A
    query_class: QueryClass = QueryClass.UNKNOWN

    primary_domain: Domain | None = None
    domains: list[Domain] = Field(
        default_factory=list
    )

    intent: str = "unknown"

    entities: dict[str, DetectedEntity] = Field(
        default_factory=dict
    )

    requested_information: list[str] = Field(
        default_factory=list
    )

    residual_terms: list[str] = Field(
        default_factory=list
    )

    # Deterministische research-classificatie.
    # Deze velden sturen in deze fase nog geen AI-provider aan.
    multi_intent: bool = False

    complexity_score: int = Field(
        default=0,
        ge=0,
    )

    complexity_reasons: list[str] = Field(
        default_factory=list
    )

    research_required: bool = False
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    clarification_required: bool = False
    clarification_question: str | None = None

    execution_steps: list[ExecutionStep] = Field(
        default_factory=list
    )


class TraceAttempt(BaseModel):
    attempt_no: int
    step_id: str

    domain: Domain
    action: str

    status: str = "pending"

    request_summary: dict[str, Any] = Field(
        default_factory=dict
    )

    result_count: int | None = None
    accepted: bool = False

    fallback_reason: str | None = None
    error: str | None = None

    duration_ms: int | None = None


class OrchestratorTrace(BaseModel):
    attempts: list[TraceAttempt] = Field(
        default_factory=list
    )

    fallback_used: bool = False
    clarification_used: bool = False


class OrchestratorAskRequest(BaseModel):
    vraag: str
    q: str | None = None

    mode: str = "auto"

    limit: int = Field(
        default=10,
        ge=1,
        le=50,
    )

    include_trace: bool = True
