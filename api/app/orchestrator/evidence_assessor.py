from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from app.orchestrator.evidence_contracts import (
    EvidenceFreshnessStatus,
    EvidenceGroundingStatus,
    EvidenceItem,
    EvidenceQualityStatus,
)
from app.orchestrator.evidence_requirements import (
    EvidenceRequirement,
    EvidenceRequirementSet,
    RequirementNecessity,
)


EVIDENCE_ASSESSMENT_CONTRACT_VERSION = (
    "promati.phase_c3."
    "evidence_assessment_contract.v1"
)


class RequirementAssessmentStatus(str, Enum):
    SATISFIED = "satisfied"
    PARTIAL = "partial"
    MISSING = "missing"
    CONFLICTING = "conflicting"


class EvidenceAssessmentStatus(str, Enum):
    SUFFICIENT = "sufficient"
    PARTIAL = "partial"
    INSUFFICIENT = "insufficient"
    CONFLICTING = "conflicting"


@dataclass(frozen=True)
class RequirementAssessment:
    requirement_id: str
    necessity: RequirementNecessity
    status: RequirementAssessmentStatus
    matched_evidence_ids: tuple[str, ...]
    present: bool
    relevant: bool
    grounded: bool
    fresh: bool
    conflicting: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceAssessmentResult:
    contract_version: str
    requirement_set_id: str
    intent: str
    status: EvidenceAssessmentStatus
    requirement_results: tuple[
        RequirementAssessment,
        ...,
    ]
    missing_required_requirement_ids: tuple[
        str,
        ...,
    ]
    conflicting_requirement_ids: tuple[
        str,
        ...,
    ]
    evidence_ids_considered: tuple[str, ...]


_FRESH_STATUSES = frozenset(
    {
        EvidenceFreshnessStatus.CURRENT,
        EvidenceFreshnessStatus.LATEST_KNOWN,
        EvidenceFreshnessStatus.NOT_APPLICABLE,
    }
)


def _entity_matches(
    requirement: EvidenceRequirement,
    evidence: EvidenceItem,
    target_entity_ids: Mapping[
        str,
        str,
    ],
) -> bool:
    if (
        requirement.entity_type is not None
        and evidence.entity_type
        != requirement.entity_type
    ):
        return False

    if (
        requirement.entity_id_required
        and not evidence.entity_id
    ):
        return False

    if requirement.entity_type is not None:
        expected_entity_id = (
            target_entity_ids.get(
                requirement.entity_type
            )
        )

        if (
            expected_entity_id is not None
            and evidence.entity_id
            != expected_entity_id
        ):
            return False

    return True


def _timestamp_is_fresh(
    requirement: EvidenceRequirement,
    evidence: EvidenceItem,
    now: datetime,
) -> bool:
    if (
        evidence.freshness_status
        not in _FRESH_STATUSES
    ):
        return False

    if requirement.maximum_age_seconds is None:
        return True

    timestamp = (
        evidence.observed_at
        or evidence.effective_at
        or evidence.retrieved_at
    )

    if timestamp is None:
        return False

    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(
            tzinfo=timezone.utc
        )

    age_seconds = (
        now - timestamp.astimezone(
            timezone.utc
        )
    ).total_seconds()

    return (
        age_seconds >= 0
        and age_seconds
        <= requirement.maximum_age_seconds
    )


def _stable_value(value: Any) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            default=str,
        )
    except (TypeError, ValueError):
        return repr(value)


def _assess_requirement(
    requirement: EvidenceRequirement,
    evidence_items: tuple[
        EvidenceItem,
        ...,
    ],
    target_entity_ids: Mapping[
        str,
        str,
    ],
    now: datetime,
) -> RequirementAssessment:
    type_matches = tuple(
        item
        for item in evidence_items
        if (
            item.evidence_type
            in requirement.evidence_types
            and item.evidence_type
            not in requirement.
            forbidden_substitutions
        )
    )

    relevant_matches = tuple(
        item
        for item in type_matches
        if (
            item.source_type
            in requirement.allowed_source_types
            and _entity_matches(
                requirement,
                item,
                target_entity_ids,
            )
        )
    )

    grounded_matches = tuple(
        item
        for item in relevant_matches
        if (
            item.grounding_status
            == EvidenceGroundingStatus.GROUNDED
        )
    )

    usable_matches = tuple(
        item
        for item in grounded_matches
        if (
            item.quality_status
            != EvidenceQualityStatus.INVALID
            and _timestamp_is_fresh(
                requirement,
                item,
                now,
            )
        )
    )

    present = bool(type_matches)
    relevant = bool(relevant_matches)
    grounded = bool(grounded_matches)
    fresh = bool(usable_matches)

    enough_items = (
        len(usable_matches)
        >= requirement.minimum_items
    )

    values_by_claim_identity: dict[
        tuple[
            str | None,
            str | None,
            str | None,
            tuple[str, ...],
        ],
        set[str],
    ] = {}

    for item in usable_matches:
        claim_identity = (
            item.entity_type,
            item.entity_id,
            item.subject,
            item.claim_scope,
        )
        values_by_claim_identity.setdefault(
            claim_identity,
            set(),
        ).add(
            _stable_value(item.value)
        )

    conflicting = (
        enough_items
        and any(
            len(values) > 1
            for values in (
                values_by_claim_identity.values()
            )
        )
    )

    reasons: list[str] = []

    if not present:
        reasons.append("missing_evidence")
    elif not relevant:
        reasons.append(
            "source_or_entity_not_relevant"
        )
    elif not grounded:
        reasons.append("not_grounded")
    elif not fresh:
        reasons.append(
            "not_fresh_or_invalid_quality"
        )
    elif not enough_items:
        reasons.append(
            "minimum_items_not_met"
        )

    if conflicting:
        reasons.append("conflicting_values")

    if conflicting:
        status = (
            RequirementAssessmentStatus.
            CONFLICTING
        )
    elif enough_items:
        status = (
            RequirementAssessmentStatus.
            SATISFIED
        )
    elif not present:
        status = (
            RequirementAssessmentStatus.
            MISSING
        )
    else:
        status = (
            RequirementAssessmentStatus.
            PARTIAL
        )

    return RequirementAssessment(
        requirement_id=(
            requirement.requirement_id
        ),
        necessity=requirement.necessity,
        status=status,
        matched_evidence_ids=tuple(
            item.evidence_id
            for item in usable_matches
        ),
        present=present,
        relevant=relevant,
        grounded=grounded,
        fresh=fresh,
        conflicting=conflicting,
        reasons=tuple(reasons),
    )


def assess_evidence(
    requirement_set: EvidenceRequirementSet,
    evidence_items: tuple[
        EvidenceItem,
        ...,
    ],
    *,
    target_entity_ids: Mapping[
        str,
        str,
    ] | None = None,
    now: datetime | None = None,
) -> EvidenceAssessmentResult:
    evidence_snapshot = tuple(
        sorted(
            tuple(evidence_items),
            key=lambda item: (
                item.evidence_id,
                item.execution_step_id,
                item.specialist_id,
            ),
        )
    )

    entity_targets = dict(
        target_entity_ids or {}
    )

    assessment_time = (
        now
        if now is not None
        else datetime.now(timezone.utc)
    )

    if assessment_time.tzinfo is None:
        assessment_time = (
            assessment_time.replace(
                tzinfo=timezone.utc
            )
        )
    else:
        assessment_time = (
            assessment_time.astimezone(
                timezone.utc
            )
        )

    requirement_results = tuple(
        _assess_requirement(
            requirement,
            evidence_snapshot,
            entity_targets,
            assessment_time,
        )
        for requirement
        in requirement_set.requirements
    )

    blocking_necessities = {
        RequirementNecessity.REQUIRED,
        RequirementNecessity.
        REQUIRED_FOR_DIAGNOSIS,
    }

    missing_required = tuple(
        item.requirement_id
        for item in requirement_results
        if (
            item.necessity
            in blocking_necessities
            and item.status
            != RequirementAssessmentStatus.
            SATISFIED
        )
    )

    conflicting_ids = tuple(
        item.requirement_id
        for item in requirement_results
        if item.conflicting
    )

    if conflicting_ids:
        overall_status = (
            EvidenceAssessmentStatus.
            CONFLICTING
        )
    elif missing_required:
        overall_status = (
            EvidenceAssessmentStatus.
            INSUFFICIENT
        )
    elif any(
        item.status
        != RequirementAssessmentStatus.
        SATISFIED
        for item in requirement_results
    ):
        overall_status = (
            EvidenceAssessmentStatus.PARTIAL
        )
    else:
        overall_status = (
            EvidenceAssessmentStatus.
            SUFFICIENT
        )

    evidence_ids_considered = tuple(
        dict.fromkeys(
            item.evidence_id
            for item in evidence_snapshot
        )
    )

    return EvidenceAssessmentResult(
        contract_version=(
            EVIDENCE_ASSESSMENT_CONTRACT_VERSION
        ),
        requirement_set_id=(
            requirement_set.requirement_set_id
        ),
        intent=requirement_set.intent,
        status=overall_status,
        requirement_results=(
            requirement_results
        ),
        missing_required_requirement_ids=(
            missing_required
        ),
        conflicting_requirement_ids=(
            conflicting_ids
        ),
        evidence_ids_considered=(
            evidence_ids_considered
        ),
    )


__all__ = [
    "EVIDENCE_ASSESSMENT_CONTRACT_VERSION",
    "EvidenceAssessmentResult",
    "EvidenceAssessmentStatus",
    "RequirementAssessment",
    "RequirementAssessmentStatus",
    "assess_evidence",
]