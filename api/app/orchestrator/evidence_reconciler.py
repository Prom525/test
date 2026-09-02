from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import json
from typing import Any, Mapping

from app.orchestrator.evidence_adapters import (
    normalize_execution_result_evidence,
)
from app.orchestrator.evidence_assessor import (
    EvidenceAssessmentResult,
    EvidenceAssessmentStatus,
    assess_evidence,
)
from app.orchestrator.evidence_contracts import (
    EvidenceItem,
)
from app.orchestrator.evidence_research_executor import (
    ResearchExecutionResult,
    ResearchExecutionStatus,
)
from app.orchestrator.evidence_requirements import (
    EvidenceRequirementSet,
)
from app.orchestrator.execution_contracts import (
    EXECUTION_CONTRACT_VERSION,
    ExecutionRequest,
    FallbackPolicy,
)
from app.orchestrator.execution_shadow import (
    derive_execution_result,
)


EVIDENCE_RECONCILIATION_CONTRACT_VERSION = (
    "evidence_reconciliation.v1"
)


class EvidenceReconciliationStatus(str, Enum):
    UNCHANGED = "unchanged"
    IMPROVED = "improved"
    UNRESOLVED = "unresolved"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class EvidenceReconciliationResult:
    contract_version: str
    requirement_set_id: str
    intent: str
    status: EvidenceReconciliationStatus
    research_status: ResearchExecutionStatus
    initial_evidence_items: tuple[EvidenceItem, ...]
    reconciled_evidence_items: tuple[EvidenceItem, ...]
    added_evidence_ids: tuple[str, ...]
    discarded_result_count: int
    initial_assessment: EvidenceAssessmentResult
    reconciled_assessment: EvidenceAssessmentResult
    reasons: tuple[str, ...]


_REQUIRED_WRAPPER_FIELDS = (
    "step_id",
    "domain",
    "action",
    "endpoint",
    "accepted",
    "result",
)


_ASSESSMENT_RANK = {
    EvidenceAssessmentStatus.INSUFFICIENT: 0,
    EvidenceAssessmentStatus.CONFLICTING: 0,
    EvidenceAssessmentStatus.PARTIAL: 1,
    EvidenceAssessmentStatus.SUFFICIENT: 2,
}


def _valid_wrapper(
    value: Any,
) -> bool:
    if not isinstance(value, dict):
        return False

    if any(
        field not in value
        for field in _REQUIRED_WRAPPER_FIELDS
    ):
        return False

    for field in (
        "step_id",
        "domain",
        "action",
        "endpoint",
    ):
        if (
            not isinstance(value[field], str)
            or not value[field]
        ):
            return False

    if not isinstance(value["accepted"], bool):
        return False

    return isinstance(value["result"], dict)


def _wrapper_fingerprint(
    wrapper: dict[str, Any],
) -> str:
    return json.dumps(
        {
            field: wrapper[field]
            for field in _REQUIRED_WRAPPER_FIELDS
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=repr,
    )


def _request_from_wrapper(
    wrapper: dict[str, Any],
) -> ExecutionRequest:
    return ExecutionRequest(
        contract_version=EXECUTION_CONTRACT_VERSION,
        step_id=wrapper["step_id"],
        domain=wrapper["domain"],
        action=wrapper["action"],
        endpoint=wrapper["endpoint"],
        params={},
        required=False,
        timeout_seconds=30.0,
        retry_count=0,
        fallback_policy=FallbackPolicy.UNRESOLVED,
        legacy_fallback_allowed=False,
    )


def _evidence_sort_key(
    item: EvidenceItem,
) -> tuple[str, str]:
    return (
        str(item.evidence_id),
        repr(item.value),
    )


def _detached_sorted_evidence(
    evidence_items: tuple[EvidenceItem, ...],
) -> tuple[EvidenceItem, ...]:
    return tuple(
        sorted(
            (
                deepcopy(item)
                for item in evidence_items
            ),
            key=_evidence_sort_key,
        )
    )


def _base_result(
    requirement_set: EvidenceRequirementSet,
    initial_evidence_items: tuple[EvidenceItem, ...],
    initial_assessment: EvidenceAssessmentResult,
    research_execution: ResearchExecutionResult,
    *,
    status: EvidenceReconciliationStatus,
    reasons: tuple[str, ...],
) -> EvidenceReconciliationResult:
    detached_initial = _detached_sorted_evidence(
        initial_evidence_items
    )

    return EvidenceReconciliationResult(
        contract_version=(
            EVIDENCE_RECONCILIATION_CONTRACT_VERSION
        ),
        requirement_set_id=(
            requirement_set.requirement_set_id
        ),
        intent=requirement_set.intent,
        status=status,
        research_status=research_execution.status,
        initial_evidence_items=detached_initial,
        reconciled_evidence_items=(
            tuple(
                deepcopy(item)
                for item in detached_initial
            )
        ),
        added_evidence_ids=(),
        discarded_result_count=0,
        initial_assessment=initial_assessment,
        reconciled_assessment=initial_assessment,
        reasons=reasons,
    )


def reconcile_evidence(
    requirement_set: EvidenceRequirementSet,
    initial_evidence_items: tuple[EvidenceItem, ...],
    initial_assessment: EvidenceAssessmentResult,
    research_execution: ResearchExecutionResult,
    *,
    retrieved_at: datetime,
    target_entity_ids: Mapping[str, str] | None = None,
    now: datetime | None = None,
) -> EvidenceReconciliationResult:
    if (
        research_execution.requirement_set_id
        != requirement_set.requirement_set_id
        or research_execution.intent
        != requirement_set.intent
    ):
        return _base_result(
            requirement_set,
            initial_evidence_items,
            initial_assessment,
            research_execution,
            status=(
                EvidenceReconciliationStatus.BLOCKED
            ),
            reasons=(
                "research_identity_mismatch",
            ),
        )

    if (
        research_execution.status
        is ResearchExecutionStatus.SKIPPED
    ):
        return _base_result(
            requirement_set,
            initial_evidence_items,
            initial_assessment,
            research_execution,
            status=(
                EvidenceReconciliationStatus.UNCHANGED
            ),
            reasons=("research_not_required",),
        )

    if (
        research_execution.status
        is ResearchExecutionStatus.BLOCKED
    ):
        blocked_reason = (
            research_execution.blocked_reason
            or "research_execution_blocked"
        )

        return _base_result(
            requirement_set,
            initial_evidence_items,
            initial_assessment,
            research_execution,
            status=(
                EvidenceReconciliationStatus.BLOCKED
            ),
            reasons=(blocked_reason,),
        )

    if (
        research_execution.status
        is not ResearchExecutionStatus.COMPLETED
    ):
        return _base_result(
            requirement_set,
            initial_evidence_items,
            initial_assessment,
            research_execution,
            status=(
                EvidenceReconciliationStatus.BLOCKED
            ),
            reasons=(
                "unsupported_research_execution_status",
            ),
        )

    normalized_items: list[EvidenceItem] = []
    discarded_result_count = 0
    seen_wrapper_fingerprints: set[str] = set()

    for raw_wrapper in (
        research_execution.combined_results
    ):
        wrapper = deepcopy(raw_wrapper)

        if not _valid_wrapper(wrapper):
            discarded_result_count += 1
            continue

        if not wrapper["accepted"]:
            discarded_result_count += 1
            continue

        fingerprint = _wrapper_fingerprint(
            wrapper
        )

        if fingerprint in seen_wrapper_fingerprints:
            continue

        seen_wrapper_fingerprints.add(
            fingerprint
        )

        try:
            request = _request_from_wrapper(
                wrapper
            )
            execution_result = (
                derive_execution_result(
                    request=request,
                    raw_result=deepcopy(
                        wrapper["result"]
                    ),
                    legacy_accepted=(
                        wrapper["accepted"]
                    ),
                )
            )
            candidate_items = (
                normalize_execution_result_evidence(
                    execution_result,
                    retrieved_at=retrieved_at,
                )
            )

            for item in candidate_items:
                evidence_id = getattr(
                    item,
                    "evidence_id",
                    None,
                )

                if (
                    not isinstance(evidence_id, str)
                    or not evidence_id
                ):
                    discarded_result_count += 1
                    continue

                normalized_items.append(
                    deepcopy(item)
                )
        except Exception:
            discarded_result_count += 1

    initial_by_id: dict[str, EvidenceItem] = {}

    for item in _detached_sorted_evidence(
        initial_evidence_items
    ):
        initial_by_id.setdefault(
            str(item.evidence_id),
            item,
        )

    reconciled_by_id = dict(initial_by_id)

    for item in sorted(
        (
            deepcopy(item)
            for item in normalized_items
        ),
        key=_evidence_sort_key,
    ):
        reconciled_by_id.setdefault(
            str(item.evidence_id),
            item,
        )

    reconciled_evidence = tuple(
        reconciled_by_id[evidence_id]
        for evidence_id in sorted(
            reconciled_by_id
        )
    )

    added_evidence_ids = tuple(
        evidence_id
        for evidence_id in sorted(
            reconciled_by_id
        )
        if evidence_id not in initial_by_id
    )

    reconciled_assessment = assess_evidence(
        requirement_set,
        reconciled_evidence,
        target_entity_ids=(
            deepcopy(target_entity_ids)
            if target_entity_ids is not None
            else None
        ),
        now=now,
    )

    initial_rank = _ASSESSMENT_RANK.get(
        initial_assessment.status,
        0,
    )
    reconciled_rank = _ASSESSMENT_RANK.get(
        reconciled_assessment.status,
        0,
    )

    if reconciled_rank > initial_rank:
        status = (
            EvidenceReconciliationStatus.IMPROVED
        )
        reasons = ("assessment_improved",)
    else:
        status = (
            EvidenceReconciliationStatus.UNRESOLVED
        )
        reasons = ("assessment_not_improved",)

    return EvidenceReconciliationResult(
        contract_version=(
            EVIDENCE_RECONCILIATION_CONTRACT_VERSION
        ),
        requirement_set_id=(
            requirement_set.requirement_set_id
        ),
        intent=requirement_set.intent,
        status=status,
        research_status=research_execution.status,
        initial_evidence_items=(
            _detached_sorted_evidence(
                initial_evidence_items
            )
        ),
        reconciled_evidence_items=(
            reconciled_evidence
        ),
        added_evidence_ids=added_evidence_ids,
        discarded_result_count=(
            discarded_result_count
        ),
        initial_assessment=initial_assessment,
        reconciled_assessment=(
            reconciled_assessment
        ),
        reasons=reasons,
    )