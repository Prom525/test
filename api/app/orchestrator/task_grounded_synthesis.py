from __future__ import annotations

import os
from typing import Any

from app.orchestrator.evidence_assessor import EvidenceAssessmentStatus
from app.orchestrator.evidence_reconciler import (
    EvidenceReconciliationResult,
    EvidenceReconciliationStatus,
)
from app.orchestrator.evidence_research_executor import ResearchExecutionStatus
from app.orchestrator.evidence_synthesizer import synthesize_grounded_evidence


# PROMATI_P4_6E2_TASK_GROUNDED_SYNTHESIS_AUTHORITY_CANARY
_ENV = "AI_TASK_GROUNDED_SYNTHESIS_AUTHORITY_CANARY_ENABLED"
_CONTRACT_VERSION = (
    "promati.multi_intent.task_grounded_synthesis_authority_canary.v1"
)


def _enabled() -> bool:
    raw = os.getenv(_ENV, "true")
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _value(value: Any) -> str | None:
    raw = getattr(value, "value", value)
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _claim_to_dict(claim: Any) -> dict[str, Any]:
    return {
        "claim_id": getattr(claim, "claim_id", None),
        "text": getattr(claim, "text", None),
        "evidence_ids": list(getattr(claim, "evidence_ids", ()) or ()),
        "requirement_ids": list(
            getattr(claim, "requirement_ids", ()) or ()
        ),
    }


def build_task_grounded_synthesis_authority_canary_p4_6e2(
    task_research_evidence_authority: dict[str, Any] | None,
    evidence_units: list[dict[str, Any]],
) -> dict[str, Any]:
    enabled = _enabled()
    contract: dict[str, Any] = {
        "contract_version": _CONTRACT_VERSION,
        "enabled": enabled,
        "eligible": False,
        "authoritative": False,
        "authority_scope": "intent_task_grounded_synthesis_only",
        "task_research_evidence_authority_required": True,
        "legacy_phase_c_authority_unchanged": True,
        "legacy_reconciliation_authority": False,
        "public_answer_authority": False,
        "unit_count": 0,
        "grounded_unit_count": 0,
        "claim_count": 0,
        "units": [],
        "reason": None,
    }

    if not enabled:
        contract["reason"] = "disabled"
        return contract

    if not isinstance(task_research_evidence_authority, dict):
        contract["reason"] = "missing_task_research_evidence_authority"
        return contract

    if (
        task_research_evidence_authority.get("authoritative") is not True
        or task_research_evidence_authority.get("authority_scope")
        != "intent_task_research_evidence_reassessment_only"
    ):
        contract["reason"] = "task_research_evidence_authority_not_active"
        return contract

    sufficient_keys = {
        (row.get("task_id"), row.get("family_code"))
        for row in list(task_research_evidence_authority.get("units") or [])
        if isinstance(row, dict)
        and row.get("status") == "reassessed"
        and row.get("assessment_status") == "sufficient"
    }
    if not sufficient_keys:
        contract["reason"] = "no_sufficient_authoritative_evidence_units"
        return contract

    units: list[dict[str, Any]] = []

    for row in list(evidence_units or []):
        if not isinstance(row, dict):
            continue

        key = (row.get("task_id"), row.get("family_code"))
        if key not in sufficient_keys:
            continue

        assessment = row.get("assessment")
        evidence_items = tuple(row.get("evidence_items") or ())
        assessment_status = _value(
            getattr(assessment, "status", None)
        )

        if (
            assessment is None
            or assessment_status
            != EvidenceAssessmentStatus.SUFFICIENT.value
            or not evidence_items
        ):
            units.append(
                {
                    "task_id": row.get("task_id"),
                    "family_code": row.get("family_code"),
                    "status": "blocked_invalid_authoritative_evidence_unit",
                    "grounded_synthesis_status": None,
                    "claim_count": 0,
                    "evidence_ids_used": [],
                }
            )
            continue

        reconciliation = EvidenceReconciliationResult(
            contract_version=(
                "p4_6e2_task_grounded_synthesis_reconciliation.v1"
            ),
            requirement_set_id=str(row.get("requirement_set_id") or ""),
            intent=str(row.get("requirement_set_intent") or ""),
            status=EvidenceReconciliationStatus.IMPROVED,
            research_status=ResearchExecutionStatus.COMPLETED,
            initial_evidence_items=(),
            reconciled_evidence_items=evidence_items,
            added_evidence_ids=tuple(
                str(getattr(item, "evidence_id", "") or "")
                for item in evidence_items
                if str(getattr(item, "evidence_id", "") or "")
            ),
            discarded_result_count=0,
            initial_assessment=assessment,
            reconciled_assessment=assessment,
            reasons=("p4_6e2_authoritative_task_grounded_synthesis",),
        )

        grounded = synthesize_grounded_evidence(reconciliation)
        claims = tuple(getattr(grounded, "claims", ()) or ())
        evidence_ids_used = tuple(
            getattr(grounded, "evidence_ids_used", ()) or ()
        )

        units.append(
            {
                "task_id": row.get("task_id"),
                "family_code": row.get("family_code"),
                "status": "grounded",
                "requirement_set_id": row.get("requirement_set_id"),
                "grounded_synthesis_status": _value(
                    getattr(grounded, "status", None)
                ),
                "claim_count": len(claims),
                "claims": [_claim_to_dict(claim) for claim in claims],
                "evidence_ids_used": list(evidence_ids_used),
                "omitted_requirement_ids": list(
                    getattr(grounded, "omitted_requirement_ids", ()) or ()
                ),
                "conflicting_requirement_ids": list(
                    getattr(grounded, "conflicting_requirement_ids", ()) or ()
                ),
            }
        )

    grounded_units = [
        row for row in units if row.get("status") == "grounded"
    ]
    contract["units"] = units
    contract["unit_count"] = len(units)
    contract["grounded_unit_count"] = len(grounded_units)
    contract["claim_count"] = sum(
        int(row.get("claim_count") or 0) for row in grounded_units
    )

    if not grounded_units:
        contract["reason"] = "no_grounded_units"
        return contract

    if any(
        int(row.get("claim_count") or 0) <= 0 for row in grounded_units
    ):
        contract["reason"] = "grounded_unit_without_claims"
        return contract

    if any(
        not all(
            isinstance(claim, dict)
            and bool(str(claim.get("text") or "").strip())
            and bool(claim.get("evidence_ids"))
            and bool(claim.get("requirement_ids"))
            for claim in list(row.get("claims") or [])
        )
        for row in grounded_units
    ):
        contract["reason"] = "invalid_grounded_claim_contract"
        return contract

    contract["eligible"] = True
    contract["authoritative"] = True
    contract["reason"] = "activated_task_grounded_synthesis_authority"
    return contract


__all__ = [
    "build_task_grounded_synthesis_authority_canary_p4_6e2",
]
