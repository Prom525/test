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


# PROMATI_PHASE_A2D_EXECUTION_GROUNDING_V1
class ExecutionBlockerType(str, Enum):
    UNRESOLVED_REQUIRED_ENTITY = (
        "unresolved_required_entity"
    )
    UNSUPPORTED_MULTI_BAND_EXECUTION = (
        "unsupported_multi_band_execution"
    )


class ExecutionBlocker(BaseModel):
    blocker_type: ExecutionBlockerType
    entity_name: str
    candidate_value: Any = None
    reason: str = "entity_grounding_unresolved"

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

    # PROMATI_PHASE_A2D_EXECUTION_GROUNDING_V1
    execution_blockers: list[ExecutionBlocker] = Field(
        default_factory=list
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


# PROMATI_CONVERSATION_CONTEXT_CONTRACT_V1
#
# Additive request-only contract.
#
# Deze modellen veranderen op zichzelf geen routing of planning.
# De huidige gebruikersvraag blijft altijd ongewijzigd in `vraag`.
# Een latere P2.5-stap mag active_scope uitsluitend als bounded
# fallback gebruiken wanneer conversationele referentie dat vereist.
class ConversationScopeContext(BaseModel):
    scope_code: str | None = None
    scope_type: str | None = None

    area_code: str | None = None
    installation_code: str | None = None
    lijn_code: str | None = None
    band_code: str | None = None


class ConversationContext(BaseModel):
    # "none" betekent: context niet toepassen.
    # "inherit_active_scope" wordt in P2.5b de expliciete,
    # bounded follow-upmodus.
    reference_mode: str = "none"

    active_scope: ConversationScopeContext | None = None


class OrchestratorAskRequest(BaseModel):
    vraag: str
    q: str | None = None

    # PROMATI_CONVERSATION_CONTEXT_CONTRACT_V1
    conversation_context: ConversationContext | None = None

    mode: str = "auto"

    limit: int = Field(
        default=10,
        ge=1,
        le=50,
    )

    include_trace: bool = False
