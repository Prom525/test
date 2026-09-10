from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from app.orchestrator.evidence_assessor import (
    EvidenceAssessmentStatus,
    assess_evidence,
)
from app.orchestrator.evidence_reconciler import (
    EvidenceReconciliationResult,
    EvidenceReconciliationStatus,
)
from app.orchestrator.evidence_research_executor import ResearchExecutionStatus
from app.orchestrator.evidence_requirement_catalog import get_requirement_set
from app.orchestrator.evidence_synthesizer import synthesize_grounded_evidence


# PROMATI_P4_6E3_TASK_SYNTHESIS_COVERAGE_AUTHORITY_CANARY
_ENV = "AI_TASK_GROUNDED_SYNTHESIS_COVERAGE_AUTHORITY_CANARY_ENABLED"
_CONTRACT_VERSION = (
    "promati.multi_intent.task_grounded_synthesis_coverage_authority_canary.v1"
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


def _task_domain(task: Any) -> str | None:
    return _value(getattr(task, "domain", None))


def _family_codes(task: Any) -> tuple[str, ...]:
    scope = getattr(task, "scope", None)
    if not isinstance(scope, dict):
        return ()
    raw = scope.get("product_family_codes")
    if not isinstance(raw, (list, tuple)):
        return ()

    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        code = str(item).strip()
        if not code:
            continue
        key = code.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(code)
    return tuple(out)


def _evidence_family_code(item: Any) -> str | None:
    entity_type = str(getattr(item, "entity_type", "") or "").casefold()
    entity_id = getattr(item, "entity_id", None)
    if entity_type == "product" and entity_id is not None:
        text = str(entity_id).strip()
        if text:
            return text

    provenance = getattr(item, "provenance", None)
    if isinstance(provenance, dict):
        raw = provenance.get("family_code")
        if raw is not None:
            text = str(raw).strip()
            if text:
                return text
    return None


def _select_task_evidence(
    task: Any,
    evidence_items: tuple[Any, ...],
    *,
    family_code: str | None = None,
) -> tuple[Any, ...]:
    domain = _task_domain(task)
    family_key = family_code.casefold() if family_code else None
    selected: list[Any] = []

    for item in tuple(evidence_items or ()):
        item_domain = str(getattr(item, "domain", "") or "").strip()
        if domain is not None and item_domain != domain:
            continue

        if family_key is not None:
            item_family = _evidence_family_code(item)
            if item_family is None or item_family.casefold() != family_key:
                continue

        selected.append(item)

    return tuple(selected)


def _requirement_set(task: Any):
    task_intent = str(getattr(task, "intent", "") or "").strip()
    return get_requirement_set(task_intent) if task_intent else None


def _claim_to_dict(claim: Any) -> dict[str, Any]:
    return {
        "claim_id": getattr(claim, "claim_id", None),
        "text": getattr(claim, "text", None),
        "evidence_ids": list(getattr(claim, "evidence_ids", ()) or ()),
        "requirement_ids": list(
            getattr(claim, "requirement_ids", ()) or ()
        ),
    }


def _synthesize_existing_evidence_unit(
    task: Any,
    evidence_items: tuple[Any, ...],
    *,
    family_code: str | None,
    now: datetime,
) -> dict[str, Any] | None:
    requirement_set = _requirement_set(task)
    if requirement_set is None:
        return None

    selected = _select_task_evidence(
        task,
        evidence_items,
        family_code=family_code,
    )
    if not selected:
        return None

    assessment = assess_evidence(
        requirement_set,
        selected,
        target_entity_ids=(
            {"product": family_code} if family_code else None
        ),
        now=now,
    )
    if _value(getattr(assessment, "status", None)) != (
        EvidenceAssessmentStatus.SUFFICIENT.value
    ):
        return None

    reconciliation = EvidenceReconciliationResult(
        contract_version=(
            "p4_6e3_existing_task_evidence_reconciliation.v1"
        ),
        requirement_set_id=requirement_set.requirement_set_id,
        intent=requirement_set.intent,
        status=EvidenceReconciliationStatus.UNCHANGED,
        research_status=ResearchExecutionStatus.SKIPPED,
        initial_evidence_items=selected,
        reconciled_evidence_items=selected,
        added_evidence_ids=(),
        discarded_result_count=0,
        initial_assessment=assessment,
        reconciled_assessment=assessment,
        reasons=("p4_6e3_existing_authoritative_task_evidence",),
    )

    grounded = synthesize_grounded_evidence(reconciliation)
    claims = tuple(getattr(grounded, "claims", ()) or ())
    if not claims:
        return None

    return {
        "task_id": getattr(task, "task_id", None),
        "domain": _task_domain(task),
        "family_code": family_code,
        "status": "grounded",
        "source": "existing_authoritative_task_evidence",
        "requirement_set_id": requirement_set.requirement_set_id,
        "grounded_synthesis_status": _value(
            getattr(grounded, "status", None)
        ),
        "claim_count": len(claims),
        "claims": [_claim_to_dict(claim) for claim in claims],
        "evidence_ids_used": list(
            getattr(grounded, "evidence_ids_used", ()) or ()
        ),
        "omitted_requirement_ids": list(
            getattr(grounded, "omitted_requirement_ids", ()) or ()
        ),
        "conflicting_requirement_ids": list(
            getattr(grounded, "conflicting_requirement_ids", ()) or ()
        ),
    }


def build_task_grounded_synthesis_coverage_authority_canary_p4_6e3(
    plan: Any,
    task_evidence_authority: dict[str, Any] | None,
    task_grounded_synthesis_authority: dict[str, Any] | None,
    evidence_items: tuple[Any, ...],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    enabled = _enabled()
    tasks = list(getattr(plan, "intent_tasks", None) or [])

    contract: dict[str, Any] = {
        "contract_version": _CONTRACT_VERSION,
        "enabled": enabled,
        "eligible": False,
        "authoritative": False,
        "authority_scope": "intent_task_grounded_synthesis_coverage_only",
        "task_evidence_authority_required": True,
        "task_grounded_synthesis_authority_required": True,
        "legacy_phase_c_authority_unchanged": True,
        "legacy_reconciliation_authority": False,
        "public_answer_authority": False,
        "total_task_count": len(tasks),
        "covered_task_count": 0,
        "complete_task_coverage": False,
        "unit_count": 0,
        "grounded_unit_count": 0,
        "claim_count": 0,
        "units": [],
        "uncovered_task_ids": [],
        "reason": None,
    }

    if not enabled:
        contract["reason"] = "disabled"
        return contract

    if not isinstance(task_evidence_authority, dict):
        contract["reason"] = "missing_task_evidence_authority"
        return contract
    if (
        task_evidence_authority.get("authoritative") is not True
        or task_evidence_authority.get("authority_scope")
        != "intent_task_evidence_assessment_only"
    ):
        contract["reason"] = "task_evidence_authority_not_active"
        return contract

    # PROMATI_P4_14AB_EXISTING_TASK_EVIDENCE_COVERAGE_V1
    #
    # A multi-intent task can already have sufficient task-scoped evidence
    # without needing bounded follow-up research. In that no-research path,
    # P4.6e2 may legitimately be inactive because P4.6e1 requires accepted
    # follow-up results. Do not block coverage before the existing-evidence
    # synthesis path below has a chance to cover every task.
    existing_task_evidence_fallback = False
    grounded_authority_units = []

    if isinstance(task_grounded_synthesis_authority, dict):
        grounded_authority_active = (
            task_grounded_synthesis_authority.get("authoritative") is True
            and task_grounded_synthesis_authority.get("authority_scope")
            == "intent_task_grounded_synthesis_only"
        )
        if grounded_authority_active:
            grounded_authority_units = list(
                task_grounded_synthesis_authority.get("units") or []
            )
        else:
            reason = str(
                task_grounded_synthesis_authority.get("reason") or ""
            )
            if reason in {
                "task_research_evidence_authority_not_active",
                "missing_task_research_evidence_authority",
                "no_sufficient_authoritative_evidence_units",
                "no_grounded_units",
            }:
                existing_task_evidence_fallback = True
            else:
                contract["reason"] = "task_grounded_synthesis_authority_not_active"
                return contract
    else:
        existing_task_evidence_fallback = True

    if existing_task_evidence_fallback:
        contract["existing_task_evidence_fallback"] = True
        contract["task_grounded_synthesis_authority_required"] = False
        contract["fallback_reason"] = "existing_sufficient_task_evidence"
    else:
        contract["existing_task_evidence_fallback"] = False

    if not tasks:
        contract["reason"] = "no_intent_tasks"
        return contract

    assessment_now = now or datetime.now(timezone.utc)
    if assessment_now.tzinfo is None:
        assessment_now = assessment_now.replace(tzinfo=timezone.utc)
    else:
        assessment_now = assessment_now.astimezone(timezone.utc)

    research_grounded = [
        row
        for row in list(grounded_authority_units or [])
        if isinstance(row, dict)
        and row.get("status") == "grounded"
        and int(row.get("claim_count") or 0) > 0
    ]
    research_by_key = {
        (row.get("task_id"), row.get("family_code")): row
        for row in research_grounded
    }

    units: list[dict[str, Any]] = []
    covered_tasks: set[str] = set()
    uncovered: list[str] = []

    for task in tasks:
        task_id = str(getattr(task, "task_id", "") or "").strip()
        families = _family_codes(task)
        task_units: list[dict[str, Any]] = []

        if families:
            for family_code in families:
                existing = research_by_key.get((task_id, family_code))
                if existing is not None:
                    copied = dict(existing)
                    copied["domain"] = _task_domain(task)
                    copied["source"] = "p4_6e2_authoritative_research_grounded"
                    task_units.append(copied)
                    continue

                synthesized = _synthesize_existing_evidence_unit(
                    task,
                    tuple(evidence_items or ()),
                    family_code=family_code,
                    now=assessment_now,
                )
                if synthesized is not None:
                    task_units.append(synthesized)

            if len(task_units) == len(families):
                covered_tasks.add(task_id)
            else:
                uncovered.append(task_id)
        else:
            existing = research_by_key.get((task_id, None))
            if existing is not None:
                copied = dict(existing)
                copied["domain"] = _task_domain(task)
                copied["source"] = "p4_6e2_authoritative_research_grounded"
                task_units.append(copied)
            else:
                synthesized = _synthesize_existing_evidence_unit(
                    task,
                    tuple(evidence_items or ()),
                    family_code=None,
                    now=assessment_now,
                )
                if synthesized is not None:
                    task_units.append(synthesized)

            if task_units:
                covered_tasks.add(task_id)
            else:
                uncovered.append(task_id)

        units.extend(task_units)

    grounded_units = [
        row for row in units if row.get("status") == "grounded"
    ]

    contract["units"] = units
    contract["covered_task_count"] = len(covered_tasks)
    contract["uncovered_task_ids"] = uncovered
    contract["complete_task_coverage"] = (
        len(covered_tasks) == len(tasks) and not uncovered
    )
    contract["unit_count"] = len(units)
    contract["grounded_unit_count"] = len(grounded_units)
    contract["claim_count"] = sum(
        int(row.get("claim_count") or 0) for row in grounded_units
    )

    if not contract["complete_task_coverage"]:
        contract["reason"] = "incomplete_task_grounded_synthesis_coverage"
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
    contract["reason"] = (
        "activated_complete_task_grounded_synthesis_coverage_authority"
    )
    return contract


__all__ = [
    "build_task_grounded_synthesis_coverage_authority_canary_p4_6e3",
]
