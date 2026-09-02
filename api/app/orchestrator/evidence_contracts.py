from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


EVIDENCE_CONTRACT_VERSION = (
    "promati.phase_c1.evidence_contract.v1"
)


class EvidenceSourceType(str, Enum):
    LIVE_CANONICAL = "LIVE_CANONICAL"
    STRUCTURED_KNOWLEDGE = "STRUCTURED_KNOWLEDGE"
    APPROVED_DOCUMENT = "APPROVED_DOCUMENT"
    RAG_CONTEXT = "RAG_CONTEXT"
    CALCULATION = "CALCULATION"
    DIAGNOSTIC = "DIAGNOSTIC"
    RUNTIME = "RUNTIME"
    SPECIALIST_RESULT = "SPECIALIST_RESULT"
    UNKNOWN = "UNKNOWN"


class EvidenceType(str, Enum):
    RECORD = "RECORD"
    MEASUREMENT = "MEASUREMENT"
    EVENT = "EVENT"
    STATUS = "STATUS"
    DOCUMENT_FRAGMENT = "DOCUMENT_FRAGMENT"
    CALCULATION_RESULT = "CALCULATION_RESULT"
    DIAGNOSTIC_FINDING = "DIAGNOSTIC_FINDING"
    ASSET_RESOLUTION = "ASSET_RESOLUTION"
    RUNTIME_IDENTITY = "RUNTIME_IDENTITY"
    SPECIALIST_RESULT = "SPECIALIST_RESULT"
    UNKNOWN = "UNKNOWN"


class EvidenceFreshnessStatus(str, Enum):
    CURRENT = "CURRENT"
    LATEST_KNOWN = "LATEST_KNOWN"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class EvidenceGroundingStatus(str, Enum):
    GROUNDED = "GROUNDED"
    PARTIAL = "PARTIAL"
    UNGROUNDED = "UNGROUNDED"
    UNKNOWN = "UNKNOWN"


class EvidenceQualityStatus(str, Enum):
    VALID = "VALID"
    PARTIAL = "PARTIAL"
    INVALID = "INVALID"
    UNKNOWN = "UNKNOWN"


class EvidenceDirectness(str, Enum):
    DIRECT = "DIRECT"
    DERIVED = "DERIVED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    contract_version: str
    evidence_id: str
    execution_step_id: str
    specialist_id: str
    domain: str
    subject: str | None
    entity_type: str | None
    entity_id: str | None
    evidence_type: EvidenceType
    source_type: EvidenceSourceType
    source_name: str | None
    source_reference: str | None
    source_priority: int | None
    observed_at: datetime | None
    retrieved_at: datetime | None
    effective_at: datetime | None
    value: Any
    unit: str | None
    claim_scope: tuple[str, ...]
    freshness_status: EvidenceFreshnessStatus
    grounding_status: EvidenceGroundingStatus
    quality_status: EvidenceQualityStatus
    direct_or_derived: EvidenceDirectness
    derivation_reference: str | None
    provenance: dict[str, Any] | None