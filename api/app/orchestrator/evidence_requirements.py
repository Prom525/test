from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.orchestrator.evidence_contracts import (
    EvidenceSourceType,
    EvidenceType,
)


EVIDENCE_REQUIREMENT_CONTRACT_VERSION = (
    "promati.phase_c2."
    "evidence_requirement_contract.v1"
)


class RequirementNecessity(str, Enum):
    REQUIRED = "required"
    REQUIRED_FOR_DIAGNOSIS = (
        "required_for_diagnosis"
    )
    DESIRED = "desired"


@dataclass(frozen=True)
class EvidenceRequirement:
    contract_version: str
    requirement_id: str
    evidence_types: tuple[EvidenceType, ...]
    necessity: RequirementNecessity
    description: str
    allowed_source_types: tuple[
        EvidenceSourceType,
        ...,
    ]
    minimum_items: int
    entity_type: str | None
    entity_id_required: bool
    maximum_age_seconds: float | None
    forbidden_substitutions: tuple[
        EvidenceType,
        ...,
    ]


@dataclass(frozen=True)
class EvidenceRequirementSet:
    contract_version: str
    requirement_set_id: str
    intent: str
    requirements: tuple[
        EvidenceRequirement,
        ...,
    ]
    notes: tuple[str, ...]


__all__ = [
    "EVIDENCE_REQUIREMENT_CONTRACT_VERSION",
    "EvidenceRequirement",
    "EvidenceRequirementSet",
    "RequirementNecessity",
]