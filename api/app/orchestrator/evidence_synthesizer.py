from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from typing import Any

from app.orchestrator.evidence_assessor import (
    EvidenceAssessmentStatus,
    RequirementAssessmentStatus,
)
from app.orchestrator.evidence_contracts import (
    EvidenceDirectness,
    EvidenceFreshnessStatus,
    EvidenceGroundingStatus,
    EvidenceItem,
    EvidenceQualityStatus,
)
from app.orchestrator.evidence_reconciler import (
    EvidenceReconciliationResult,
    EvidenceReconciliationStatus,
)


GROUNDED_SYNTHESIS_CONTRACT_VERSION = (
    "promati.phase_c7.grounded_synthesis.v1"
)


class GroundedSynthesisStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class GroundedClaim:
    claim_id: str
    text: str
    evidence_ids: tuple[str, ...]
    requirement_ids: tuple[str, ...]


@dataclass(frozen=True)
class GroundedSynthesisResult:
    contract_version: str
    requirement_set_id: str
    intent: str
    status: GroundedSynthesisStatus
    claims: tuple[GroundedClaim, ...]
    omitted_requirement_ids: tuple[str, ...]
    conflicting_requirement_ids: tuple[str, ...]
    evidence_ids_used: tuple[str, ...]
    reasons: tuple[str, ...]


_ALLOWED_FRESHNESS = frozenset(
    (
        EvidenceFreshnessStatus.CURRENT,
        EvidenceFreshnessStatus.LATEST_KNOWN,
        EvidenceFreshnessStatus.NOT_APPLICABLE,
    )
)


def _render_value(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()

    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError):
        return str(value)


def _claim_text(item: EvidenceItem) -> str:
    subject = (
        str(item.subject).strip()
        if item.subject is not None
        else ""
    )

    if not subject:
        subject = item.evidence_type.value.replace(
            "_",
            " ",
        ).title()

    rendered_value = _render_value(item.value)

    unit = (
        str(item.unit).strip()
        if item.unit is not None
        else ""
    )

    if unit:
        return f"{subject}: {rendered_value} {unit}"

    return f"{subject}: {rendered_value}"


def _item_is_claimable(item: EvidenceItem) -> bool:
    return (
        item.grounding_status
        is EvidenceGroundingStatus.GROUNDED
        and item.quality_status
        is EvidenceQualityStatus.VALID
        and item.freshness_status in _ALLOWED_FRESHNESS
        and (
            item.direct_or_derived
            is not EvidenceDirectness.DERIVED
            or (
                item.derivation_reference is not None
                and bool(
                    str(
                        item.derivation_reference
                    ).strip()
                )
            )
        )
    )


def _blocked_result(
    reconciliation: EvidenceReconciliationResult,
    *,
    extra_reasons: tuple[str, ...] = (),
) -> GroundedSynthesisResult:
    assessment = reconciliation.reconciled_assessment

    omitted = tuple(
        sorted(
            {
                result.requirement_id
                for result in assessment.requirement_results
            }
            | set(
                assessment
                .missing_required_requirement_ids
            )
            | set(
                assessment
                .conflicting_requirement_ids
            )
        )
    )

    reasons = tuple(
        sorted(
            {
                "reconciliation_blocked",
                *(
                    str(reason)
                    for reason in reconciliation.reasons
                    if str(reason)
                ),
                *(
                    str(reason)
                    for reason in extra_reasons
                    if str(reason)
                ),
            }
        )
    )

    return GroundedSynthesisResult(
        contract_version=(
            GROUNDED_SYNTHESIS_CONTRACT_VERSION
        ),
        requirement_set_id=(
            reconciliation.requirement_set_id
        ),
        intent=reconciliation.intent,
        status=GroundedSynthesisStatus.BLOCKED,
        claims=(),
        omitted_requirement_ids=omitted,
        conflicting_requirement_ids=tuple(
            sorted(
                set(
                    assessment
                    .conflicting_requirement_ids
                )
            )
        ),
        evidence_ids_used=(),
        reasons=reasons,
    )


def synthesize_grounded_evidence(
    reconciliation: EvidenceReconciliationResult,
) -> GroundedSynthesisResult:
    assessment = reconciliation.reconciled_assessment
    initial_assessment = reconciliation.initial_assessment

    identity_mismatch = (
        assessment.requirement_set_id
        != reconciliation.requirement_set_id
        or assessment.intent != reconciliation.intent
        or initial_assessment.requirement_set_id
        != reconciliation.requirement_set_id
        or initial_assessment.intent
        != reconciliation.intent
    )

    if identity_mismatch:
        return _blocked_result(
            reconciliation,
            extra_reasons=(
                "assessment_identity_mismatch",
            ),
        )

    if (
        reconciliation.status
        is EvidenceReconciliationStatus.BLOCKED
        or assessment.status
        is EvidenceAssessmentStatus.INSUFFICIENT
    ):
        return _blocked_result(reconciliation)

    valid_items = tuple(
        item
        for item in (
            reconciliation.reconciled_evidence_items
        )
        if isinstance(item, EvidenceItem)
    )

    items_by_id: dict[
        str,
        list[EvidenceItem],
    ] = {}

    for item in sorted(
        valid_items,
        key=lambda value: str(value.evidence_id),
    ):
        items_by_id.setdefault(
            str(item.evidence_id),
            [],
        ).append(item)

    evidence_by_id: dict[str, EvidenceItem] = {}
    conflicting_duplicate_ids: set[str] = set()

    for evidence_id in sorted(items_by_id):
        items = items_by_id[evidence_id]
        first = items[0]

        if any(
            candidate != first
            for candidate in items[1:]
        ):
            conflicting_duplicate_ids.add(
                evidence_id
            )
            continue

        evidence_by_id[evidence_id] = first

    considered_ids = set(
        assessment.evidence_ids_considered
    )
    conflicting_ids = set(
        assessment.conflicting_requirement_ids
    )

    requirement_ids_by_evidence: dict[
        str,
        set[str],
    ] = {}

    omitted_requirement_ids: set[str] = set(
        assessment.missing_required_requirement_ids
    )
    omitted_requirement_ids.update(conflicting_ids)

    for requirement in sorted(
        assessment.requirement_results,
        key=lambda value: str(value.requirement_id),
    ):
        requirement_id = str(
            requirement.requirement_id
        )

        requirement_is_claimable = (
            requirement.status
            is RequirementAssessmentStatus.SATISFIED
            and requirement.present
            and requirement.relevant
            and requirement.grounded
            and requirement.fresh
            and not requirement.conflicting
            and requirement_id not in conflicting_ids
        )

        claimable_match_found = False

        if requirement_is_claimable:
            for evidence_id in sorted(
                set(
                    requirement.matched_evidence_ids
                )
            ):
                item = evidence_by_id.get(evidence_id)

                if (
                    item is None
                    or evidence_id not in considered_ids
                    or not _item_is_claimable(item)
                ):
                    continue

                requirement_ids_by_evidence.setdefault(
                    evidence_id,
                    set(),
                ).add(requirement_id)

                claimable_match_found = True

        if not claimable_match_found:
            omitted_requirement_ids.add(
                requirement_id
            )

    claims = []

    for evidence_id in sorted(
        requirement_ids_by_evidence
    ):
        item = evidence_by_id[evidence_id]

        claims.append(
            GroundedClaim(
                claim_id=f"claim:{evidence_id}",
                text=_claim_text(item),
                evidence_ids=(evidence_id,),
                requirement_ids=tuple(
                    sorted(
                        requirement_ids_by_evidence[
                            evidence_id
                        ]
                    )
                ),
            )
        )

    claims_tuple = tuple(claims)
    evidence_ids_used = tuple(
        claim.evidence_ids[0]
        for claim in claims_tuple
    )
    omitted_tuple = tuple(
        sorted(omitted_requirement_ids)
    )
    conflicting_tuple = tuple(
        sorted(conflicting_ids)
    )

    complete = (
        assessment.status
        is EvidenceAssessmentStatus.SUFFICIENT
        and bool(claims_tuple)
        and not omitted_tuple
        and not conflicting_tuple
    )

    status = (
        GroundedSynthesisStatus.COMPLETE
        if complete
        else GroundedSynthesisStatus.PARTIAL
    )

    reasons = set()

    if conflicting_duplicate_ids:
        reasons.add(
            "duplicate_evidence_conflict"
        )

    if omitted_tuple:
        reasons.add("requirements_omitted")

    if conflicting_tuple:
        reasons.add("conflicts_omitted")

    if not claims_tuple:
        reasons.add("no_grounded_claims")

    return GroundedSynthesisResult(
        contract_version=(
            GROUNDED_SYNTHESIS_CONTRACT_VERSION
        ),
        requirement_set_id=(
            reconciliation.requirement_set_id
        ),
        intent=reconciliation.intent,
        status=status,
        claims=claims_tuple,
        omitted_requirement_ids=omitted_tuple,
        conflicting_requirement_ids=(
            conflicting_tuple
        ),
        evidence_ids_used=evidence_ids_used,
        reasons=tuple(sorted(reasons)),
    )