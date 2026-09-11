from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


EXECUTION_CONTRACT_VERSION = "promati.phase_b2e.execution_contract.v1"


class ExecutionTransportState(str, Enum):
    NOT_ATTEMPTED = "NOT_ATTEMPTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ExecutionOutcome(str, Enum):
    SUCCESS = "SUCCESS"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
    AMBIGUOUS = "AMBIGUOUS"
    CONTEXT_CONFLICT = "CONTEXT_CONFLICT"
    NOT_FOUND = "NOT_FOUND"
    UNAVAILABLE = "UNAVAILABLE"
    REDIRECT = "REDIRECT"
    ERROR = "ERROR"
    UNKNOWN = "UNKNOWN"


class FallbackPolicy(str, Enum):
    DISABLED = "DISABLED"
    EXPLICIT = "EXPLICIT"
    UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    contract_version: str
    step_id: str
    domain: str
    action: str
    endpoint: str
    params: dict[str, Any]
    required: bool
    timeout_seconds: float
    retry_count: int
    fallback_policy: FallbackPolicy
    legacy_fallback_allowed: bool | None


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    contract_version: str
    step_id: str
    action: str
    domain: str
    endpoint: str
    transport_state: ExecutionTransportState
    semantic_outcome: ExecutionOutcome
    specialist_status: str | None
    legacy_accepted: bool
    result: dict[str, Any]
    error: str | None
    attempt_count: int
    duration_ms: int | None
    evidence_metadata: dict[str, Any] | None
    provenance_metadata: dict[str, Any] | None


@dataclass(frozen=True, slots=True)
class SpecialistContract:
    action: str
    endpoint: str
    owner: str
    required_fields: tuple[str, ...]
    accepted_input_fields: tuple[str, ...]
    planner_fields: tuple[str, ...]
    research_fields: tuple[str, ...]
    direct_planner: str
    legacy_fallback_allowed: bool | None
    fallback_policy: FallbackPolicy
    status_contract_state: str
    status_map: dict[str, ExecutionOutcome]