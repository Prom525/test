from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from app.orchestrator.evidence_assessor import assess_evidence
from app.orchestrator.evidence_requirement_catalog import get_requirement_set


# PROMATI_P4_6C_TASK_EVIDENCE_AUTHORITY_CANARY
_TASK_EVIDENCE_AUTHORITY_ENV = "AI_TASK_EVIDENCE_AUTHORITY_CANARY_ENABLED"
_CONTRACT_VERSION = "promati.multi_intent.task_evidence_authority_canary.v1"


def _enabled() -> bool:
    raw = os.getenv(_TASK_EVIDENCE_AUTHORITY_ENV, "true")
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _domain_value(task: Any) -> str | None:
    domain = getattr(task, "domain", None)
    value = getattr(domain, "value", domain)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _family_codes(task: Any) -> tuple[str, ...]:
    scope = getattr(task, "scope", None)
    if not isinstance(scope, dict):
        return ()
    raw_codes = scope.get("product_family_codes")
    if not isinstance(raw_codes, (list, tuple)):
        return ()

    output: list[str] = []
    seen: set[str] = set()
    for raw_code in raw_codes:
        code = str(raw_code).strip()
        if not code:
            continue
        key = code.casefold()
        if key in seen:
            continue
        seen.add(key)
        output.append(code)
    return tuple(output)


def _evidence_family_code(item: Any) -> str | None:
    entity_type = str(
        getattr(item, "entity_type", "") or ""
    ).casefold()
    entity_id = getattr(item, "entity_id", None)
    if entity_type == "product" and entity_id is not None:
        text = str(entity_id).strip()
        if text:
            return text

    provenance = getattr(item, "provenance", None)
    if isinstance(provenance, dict):
        raw_code = provenance.get("family_code")
        if raw_code is not None:
            text = str(raw_code).strip()
            if text:
                return text
    return None


def _select_task_evidence(
    task: Any,
    evidence_items: tuple[Any, ...],
) -> tuple[Any, ...]:
    domain = _domain_value(task)
    family_keys = {
        code.casefold()
        for code in _family_codes(task)
    }

    selected: list[Any] = []
    for item in tuple(evidence_items or ()):
        item_domain = str(
            getattr(item, "domain", "") or ""
        ).strip()
        if domain is not None and item_domain != domain:
            continue

        if family_keys:
            family_code = _evidence_family_code(item)
            if (
                family_code is None
                or family_code.casefold() not in family_keys
            ):
                continue

        selected.append(item)
    return tuple(selected)


def _assessment_status(assessment: Any) -> str | None:
    raw = getattr(assessment, "status", None)
    raw = getattr(raw, "value", raw)
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _assessment_signature(entry: dict[str, Any]) -> dict[str, Any]:
    family_rows = []
    for row in list(
        entry.get("product_family_scope_assessments") or []
    ):
        if not isinstance(row, dict):
            continue
        family_rows.append(
            {
                "family_code": row.get("family_code"),
                "selected_evidence_ids": sorted(
                    str(item)
                    for item in list(
                        row.get("selected_evidence_ids") or []
                    )
                    if item is not None
                ),
                "assessment_status": _assessment_status(
                    row.get("assessment")
                ),
            }
        )

    return {
        "task_id": entry.get("task_id"),
        "intent": entry.get("intent"),
        "domain": entry.get("domain"),
        "status": entry.get("status"),
        "resolved_requirement_set_id": entry.get(
            "resolved_requirement_set_id"
        ),
        "selected_evidence_ids": sorted(
            str(item)
            for item in list(
                entry.get("selected_evidence_ids") or []
            )
            if item is not None
        ),
        "assessment_status": _assessment_status(
            entry.get("assessment")
        ),
        "product_family_scope_assessments": sorted(
            family_rows,
            key=lambda row: str(
                row.get("family_code") or ""
            ).casefold(),
        ),
    }


def _assess_tasks(
    plan: Any,
    evidence_items: tuple[Any, ...],
    *,
    now: datetime,
) -> list[dict[str, Any]]:
    tasks = getattr(plan, "intent_tasks", None)
    if not isinstance(tasks, list):
        return []

    output: list[dict[str, Any]] = []

    for task in tasks:
        task_intent = str(
            getattr(task, "intent", "") or ""
        ).strip()
        requirement_set = (
            get_requirement_set(task_intent)
            if task_intent
            else None
        )
        selected_items = _select_task_evidence(
            task,
            tuple(evidence_items or ()),
        )

        entry: dict[str, Any] = {
            "contract_version": (
                "promati.multi_intent."
                "task_evidence_assessment_authoritative.v1"
            ),
            "task_id": getattr(task, "task_id", None),
            "domain": _domain_value(task),
            "intent": task_intent or None,
            "primary": bool(
                getattr(task, "primary", False)
            ),
            "scope": dict(
                getattr(task, "scope", {}) or {}
            ),
            "evidence_requirement_set_id": getattr(
                task,
                "evidence_requirement_set_id",
                None,
            ),
            "selected_evidence_count": len(
                selected_items
            ),
            "selected_evidence_ids": [
                getattr(item, "evidence_id", None)
                for item in selected_items
                if getattr(
                    item,
                    "evidence_id",
                    None,
                ) is not None
            ],
            "assessment": None,
            "product_family_scope_assessments": [],
            "authoritative": True,
        }

        if requirement_set is None:
            entry["status"] = "unmapped_requirement_set"
            output.append(entry)
            continue

        entry["resolved_requirement_set_id"] = (
            requirement_set.requirement_set_id
        )
        entry["assessment"] = assess_evidence(
            requirement_set,
            selected_items,
            target_entity_ids=None,
            now=now,
        )
        entry["status"] = "assessed"

        family_codes = _family_codes(task)
        if family_codes:
            family_assessments = []
            for family_code in family_codes:
                family_items = tuple(
                    item
                    for item in selected_items
                    if (
                        (
                            _evidence_family_code(item)
                            or ""
                        ).casefold()
                        == family_code.casefold()
                    )
                )
                family_assessment = assess_evidence(
                    requirement_set,
                    family_items,
                    target_entity_ids={
                        "product": family_code
                    },
                    now=now,
                )
                family_assessments.append(
                    {
                        "family_code": family_code,
                        "selected_evidence_count": len(
                            family_items
                        ),
                        "selected_evidence_ids": [
                            getattr(
                                item,
                                "evidence_id",
                                None,
                            )
                            for item in family_items
                            if getattr(
                                item,
                                "evidence_id",
                                None,
                            ) is not None
                        ],
                        "assessment": (
                            family_assessment
                        ),
                    }
                )
            entry[
                "product_family_scope_assessments"
            ] = family_assessments

        output.append(entry)

    return output


def build_task_evidence_authority_canary_p4_6c(
    plan: Any,
    evidence_items: tuple[Any, ...],
    *,
    now: datetime,
    shadow_assessments: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the P4.6c task-evidence authority contract.

    Authority is intentionally narrow: when enabled and parity-safe, the
    returned task assessments are authoritative for IntentTask evidence
    sufficiency only. Legacy Phase-C research, reconciliation, synthesis and
    public answer ownership are not changed in P4.6c.
    """

    enabled = _enabled()
    contract: dict[str, Any] = {
        "contract_version": _CONTRACT_VERSION,
        "enabled": enabled,
        "eligible": False,
        "authoritative": False,
        "authority_scope": (
            "intent_task_evidence_assessment_only"
        ),
        "legacy_phase_c_authority_unchanged": True,
        "research_execution_authority": False,
        "public_answer_authority": False,
        "task_count": 0,
        "assessed_task_count": 0,
        "shadow_parity_checked": False,
        "shadow_parity": None,
        "task_assessments": [],
        "reason": None,
    }

    if not enabled:
        contract["reason"] = "disabled"
        return contract

    if not bool(getattr(plan, "multi_intent", False)):
        contract["reason"] = "not_multi_intent"
        return contract

    tasks = getattr(plan, "intent_tasks", None)
    if not isinstance(tasks, list) or not tasks:
        contract["reason"] = "no_intent_tasks"
        return contract

    assessments = _assess_tasks(
        plan,
        tuple(evidence_items or ()),
        now=now,
    )
    contract["task_count"] = len(tasks)
    contract["assessed_task_count"] = sum(
        1
        for row in assessments
        if isinstance(row, dict)
        and row.get("status") == "assessed"
    )
    contract["task_assessments"] = assessments

    shadow_rows = (
        list(shadow_assessments)
        if isinstance(shadow_assessments, list)
        else None
    )
    if shadow_rows is not None:
        contract["shadow_parity_checked"] = True
        authoritative_signatures = sorted(
            (
                _assessment_signature(row)
                for row in assessments
                if isinstance(row, dict)
            ),
            key=lambda row: str(
                row.get("task_id") or ""
            ),
        )
        shadow_signatures = sorted(
            (
                _assessment_signature(row)
                for row in shadow_rows
                if isinstance(row, dict)
            ),
            key=lambda row: str(
                row.get("task_id") or ""
            ),
        )
        parity = (
            authoritative_signatures
            == shadow_signatures
        )
        contract["shadow_parity"] = parity
        if not parity:
            contract["reason"] = (
                "shadow_parity_mismatch_fail_open"
            )
            return contract

    contract["eligible"] = True
    contract["authoritative"] = True
    contract["reason"] = (
        "activated_task_evidence_authority"
    )
    return contract


__all__ = [
    "build_task_evidence_authority_canary_p4_6c",
]

# PROMATI_P4_15BX_REPLACEMENT_RESOLVED_CONTEXT_COMPOSITION_V1
#
# Narrow cross-task composition for replacement evidence.
# This patch only allows existing resolved_asset_context evidence to be
# composed into replacement_analysis/replacement_advice task evidence.
# It does not synthesize replacement_history or lifecycle_history and it
# does not import product_record/product_article_record/selection_advice
# as replacement requirement evidence.

_p4_15bx_original_select_task_evidence = _select_task_evidence


def _p4_15bx_value(value):
    raw = getattr(value, "value", value)
    if raw is None:
        return None
    return str(raw)


def _p4_15bx_subject(item):
    return getattr(item, "subject", None)


def _p4_15bx_evidence_id(item):
    return getattr(item, "evidence_id", None)


def _p4_15bx_is_resolved_asset_context(item):
    return _p4_15bx_subject(item) == "resolved_asset_context"


def _p4_15bx_task_intent(task):
    if isinstance(task, dict):
        for key in ("intent", "task_intent", "requested_info", "name", "id"):
            value = task.get(key)
            if value:
                text = str(value)
                if text in {"replacement_analysis", "replacement_advice"}:
                    return text
                if "replacement_analysis" in text:
                    return "replacement_analysis"
                if "replacement_advice" in text:
                    return "replacement_advice"
    for attr in ("intent", "task_intent", "requested_info", "name", "id"):
        value = getattr(task, attr, None)
        if value:
            text = str(value)
            if text in {"replacement_analysis", "replacement_advice"}:
                return text
            if "replacement_analysis" in text:
                return "replacement_analysis"
            if "replacement_advice" in text:
                return "replacement_advice"
    return None


def _p4_15bx_is_replacement_task(task):
    return _p4_15bx_task_intent(task) in {"replacement_analysis", "replacement_advice"}


def _p4_15bx_iter_evidence(value):
    if value is None:
        return tuple()
    if isinstance(value, (str, bytes, dict)):
        return tuple()
    try:
        iterator = iter(value)
    except TypeError:
        return tuple()
    rows = []
    for item in iterator:
        if hasattr(item, "subject") and hasattr(item, "evidence_id"):
            rows.append(item)
    return tuple(rows)


def _p4_15bx_find_task_and_pool(args, kwargs):
    task = None
    evidence_pool = tuple()

    for key in ("task", "task_spec", "task_definition"):
        if key in kwargs:
            task = kwargs.get(key)
            break

    for key in ("evidence_items", "items", "all_evidence", "evidence_pool", "candidate_evidence"):
        if key in kwargs:
            evidence_pool = _p4_15bx_iter_evidence(kwargs.get(key))
            if evidence_pool:
                break

    if task is None:
        for arg in args:
            if _p4_15bx_task_intent(arg):
                task = arg
                break

    if not evidence_pool:
        for arg in args:
            rows = _p4_15bx_iter_evidence(arg)
            if rows:
                evidence_pool = rows
                break

    return task, evidence_pool


def _p4_15bx_compose_resolved_context(selected, evidence_pool, task):
    if not _p4_15bx_is_replacement_task(task):
        return selected

    selected_items = _p4_15bx_iter_evidence(selected)
    if not selected_items:
        return selected

    existing_ids = {
        _p4_15bx_evidence_id(item)
        for item in selected_items
        if _p4_15bx_evidence_id(item)
    }

    additions = []
    for item in evidence_pool:
        if not _p4_15bx_is_resolved_asset_context(item):
            continue
        evidence_id = _p4_15bx_evidence_id(item)
        if evidence_id and evidence_id in existing_ids:
            continue
        additions.append(item)
        if evidence_id:
            existing_ids.add(evidence_id)

    if not additions:
        return selected

    if isinstance(selected, tuple):
        return tuple(list(selected) + additions)
    if isinstance(selected, list):
        return list(selected) + additions

    return tuple(list(selected_items) + additions)


def _select_task_evidence(*args, **kwargs):
    selected = _p4_15bx_original_select_task_evidence(*args, **kwargs)
    task, evidence_pool = _p4_15bx_find_task_and_pool(args, kwargs)
    return _p4_15bx_compose_resolved_context(selected, evidence_pool, task)

