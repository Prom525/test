from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.orchestrator.evidence_assessor import (
    EvidenceAssessmentResult,
    EvidenceAssessmentStatus,
    RequirementAssessmentStatus,
)


RESEARCH_GATE_CONTRACT_VERSION = (
    "promati.phase_c4."
    "evidence_research_gate_contract.v1"
)


class ResearchGateStatus(str, Enum):
    NOT_REQUIRED = "not_required"
    REQUIRED = "required"


@dataclass(frozen=True)
class ResearchGateDecision:
    contract_version: str
    requirement_set_id: str
    intent: str
    status: ResearchGateStatus
    research_required: bool
    target_requirement_ids: tuple[str, ...]
    reasons: tuple[str, ...]
    assessment_status: EvidenceAssessmentStatus


def decide_research_requirement(
    assessment: EvidenceAssessmentResult,
) -> ResearchGateDecision:
    unresolved = tuple(
        sorted(
            (
                requirement
                for requirement
                in assessment.requirement_results
                if (
                    requirement.status
                    is not RequirementAssessmentStatus.SATISFIED
                )
            ),
            key=lambda requirement: (
                requirement.requirement_id,
                requirement.necessity.value,
                requirement.status.value,
            ),
        )
    )

    target_requirement_ids = tuple(
        sorted(
            {
                requirement.requirement_id
                for requirement in unresolved
            }
        )
    )

    research_required = (
        assessment.status
        is not EvidenceAssessmentStatus.SUFFICIENT
        or bool(target_requirement_ids)
    )

    reasons = []

    if research_required:
        reasons.append(
            "assessment_"
            + assessment.status.value
        )

        for requirement in unresolved:
            reasons.append(
                requirement.requirement_id
                + ":"
                + requirement.status.value
            )

    return ResearchGateDecision(
        contract_version=RESEARCH_GATE_CONTRACT_VERSION,
        requirement_set_id=assessment.requirement_set_id,
        intent=assessment.intent,
        status=(
            ResearchGateStatus.REQUIRED
            if research_required
            else ResearchGateStatus.NOT_REQUIRED
        ),
        research_required=research_required,
        target_requirement_ids=target_requirement_ids,
        reasons=tuple(sorted(set(reasons))),
        assessment_status=assessment.status,
    )