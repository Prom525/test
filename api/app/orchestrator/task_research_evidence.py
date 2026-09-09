from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from app.orchestrator.evidence_adapters import normalize_execution_result_evidence
from app.orchestrator.evidence_assessor import assess_evidence
from app.orchestrator.evidence_requirement_catalog import REQUIREMENT_SETS_BY_INTENT


# PROMATI_P4_6E1_TASK_RESEARCH_EVIDENCE_AUTHORITY_CANARY
_TASK_RESEARCH_EVIDENCE_AUTHORITY_ENV = (
    "AI_TASK_RESEARCH_EVIDENCE_AUTHORITY_CANARY_ENABLED"
)
_CONTRACT_VERSION = (
    "promati.multi_intent.task_research_evidence_authority_canary.v1"
)


def _enabled() -> bool:
    raw = os.getenv(_TASK_RESEARCH_EVIDENCE_AUTHORITY_ENV, "true")
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _value(value: Any) -> str | None:
    raw = getattr(value, "value", value)
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _task_domain(task: Any) -> str | None:
    return _value(getattr(task, "domain", None))


def _family_code(item: Any) -> str | None:
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


def _select_initial_evidence(
    task: Any,
    evidence_items: tuple[Any, ...],
    *,
    family_code: str | None,
) -> tuple[Any, ...]:
    domain = _task_domain(task)
    family_key = str(family_code).casefold() if family_code else None
    selected = []

    for item in tuple(evidence_items or ()):
        item_domain = str(getattr(item, "domain", "") or "").strip()
        if domain is not None and item_domain != domain:
            continue

        if family_key is not None:
            item_family = _family_code(item)
            if item_family is None or item_family.casefold() != family_key:
                continue

        selected.append(item)

    return tuple(selected)


def _requirement_set_for_task(task: Any):
    requirement_set_id = str(
        getattr(task, "evidence_requirement_set_id", "") or ""
    ).strip()

    if requirement_set_id:
        for requirement_set in REQUIREMENT_SETS_BY_INTENT.values():
            if str(
                getattr(requirement_set, "requirement_set_id", "") or ""
            ) == requirement_set_id:
                return requirement_set

    task_intent = str(getattr(task, "intent", "") or "").strip()
    if task_intent:
        return REQUIREMENT_SETS_BY_INTENT.get(task_intent)

    return None


def _assessment_status(assessment: Any) -> str | None:
    return _value(getattr(assessment, "status", None))


def build_task_research_evidence_authority_canary_p4_6e1(
    plan: Any,
    task_research_execution_authority: dict[str, Any] | None,
    execution_observations: list[dict[str, Any]],
    initial_evidence_items: tuple[Any, ...],
    *,
    now: datetime | None = None,
    grounded_synthesis_observer=None,
) -> dict[str, Any]:
    enabled = _enabled()
    contract: dict[str, Any] = {
        "contract_version": _CONTRACT_VERSION,
        "enabled": enabled,
        "eligible": False,
        "authoritative": False,
        "authority_scope": "intent_task_research_evidence_reassessment_only",
        "task_research_execution_authority_required": True,
        "legacy_phase_c_authority_unchanged": True,
        "legacy_results_mutated": False,
        "legacy_reconciliation_authority": False,
        "public_answer_authority": False,
        "execution_observation_count": 0,
        "normalized_follow_up_evidence_count": 0,
        "reassessed_unit_count": 0,
        "sufficient_unit_count": 0,
        "units": [],
        "reason": None,
    }

    if not enabled:
        contract["reason"] = "disabled"
        return contract

    if not isinstance(task_research_execution_authority, dict):
        contract["reason"] = "missing_task_research_execution_authority"
        return contract

    if (
        task_research_execution_authority.get("authoritative") is not True
        or task_research_execution_authority.get("authority_scope")
        != "intent_task_research_execution_only"
    ):
        contract["reason"] = "task_research_execution_authority_not_active"
        return contract

    if int(
        task_research_execution_authority.get("accepted_follow_up_result_count")
        or 0
    ) <= 0:
        contract["reason"] = "no_accepted_follow_up_results"
        return contract

    assessment_now = now or datetime.now(timezone.utc)
    if assessment_now.tzinfo is None:
        assessment_now = assessment_now.replace(tzinfo=timezone.utc)
    else:
        assessment_now = assessment_now.astimezone(timezone.utc)

    tasks_by_id = {
        getattr(task, "task_id", None): task
        for task in list(getattr(plan, "intent_tasks", None) or [])
        if getattr(task, "task_id", None)
    }

    observations = [
        row for row in list(execution_observations or []) if isinstance(row, dict)
    ]
    contract["execution_observation_count"] = len(observations)

    if not observations:
        contract["reason"] = "missing_internal_execution_observations"
        return contract

    units = []

    for observation in observations:
        task_id = observation.get("task_id")
        task = tasks_by_id.get(task_id)
        if task is None:
            continue

        family_code = observation.get("family_code")
        if family_code is not None:
            family_code = str(family_code).strip() or None

        requirement_set = _requirement_set_for_task(task)
        if requirement_set is None:
            units.append(
                {
                    "task_id": task_id,
                    "domain": _task_domain(task),
                    "family_code": family_code,
                    "status": "blocked_missing_requirement_set",
                    "normalized_evidence_count": 0,
                    "assessment_status": None,
                }
            )
            continue

        normalized = []
        for execution_result in tuple(observation.get("execution_results") or ()):
            if getattr(execution_result, "legacy_accepted", False) is not True:
                continue
            normalized.extend(
                normalize_execution_result_evidence(
                    execution_result,
                    retrieved_at=assessment_now,
                )
            )

        normalized_tuple = tuple(normalized)
        initial_selected = _select_initial_evidence(
            task,
            tuple(initial_evidence_items or ()),
            family_code=family_code,
        )
        combined = initial_selected + normalized_tuple

        target_entity_ids = {"product": family_code} if family_code else None

        assessment = assess_evidence(
            requirement_set,
            combined,
            target_entity_ids=target_entity_ids,
            now=assessment_now,
        )

        if grounded_synthesis_observer is not None:
            try:
                grounded_synthesis_observer(
                    {
                        "task_id": task_id,
                        "family_code": family_code,
                        "requirement_set_id": requirement_set.requirement_set_id,
                        "requirement_set_intent": requirement_set.intent,
                        "assessment": assessment,
                        "evidence_items": combined,
                    }
                )
            except Exception:
                pass

        units.append(
            {
                "task_id": task_id,
                "domain": _task_domain(task),
                "family_code": family_code,
                "status": "reassessed",
                "requirement_set_id": requirement_set.requirement_set_id,
                "initial_evidence_count": len(initial_selected),
                "normalized_evidence_count": len(normalized_tuple),
                "combined_evidence_count": len(combined),
                "assessment_status": _assessment_status(assessment),
                "missing_required_requirement_ids": list(
                    getattr(assessment, "missing_required_requirement_ids", ()) or ()
                ),
                "conflicting_requirement_ids": list(
                    getattr(assessment, "conflicting_requirement_ids", ()) or ()
                ),
                "evidence_ids_considered": list(
                    getattr(assessment, "evidence_ids_considered", ()) or ()
                ),
            }
        )

    reassessed = [row for row in units if row.get("status") == "reassessed"]
    contract["units"] = units
    contract["normalized_follow_up_evidence_count"] = sum(
        int(row.get("normalized_evidence_count") or 0) for row in reassessed
    )
    contract["reassessed_unit_count"] = len(reassessed)
    contract["sufficient_unit_count"] = sum(
        1 for row in reassessed if row.get("assessment_status") == "sufficient"
    )

    if not reassessed:
        contract["reason"] = "no_reassessed_execution_units"
        return contract

    if any(
        int(row.get("normalized_evidence_count") or 0) <= 0 for row in reassessed
    ):
        contract["reason"] = "accepted_follow_up_without_normalized_evidence"
        return contract

    contract["eligible"] = True
    contract["authoritative"] = True
    contract["reason"] = (
        "activated_task_research_evidence_reassessment_authority"
    )
    return contract


__all__ = ["build_task_research_evidence_authority_canary_p4_6e1"]
