from __future__ import annotations

import json
import os
from typing import Any


# PROMATI_P4_6F_PUBLIC_MULTI_INTENT_COMPOSITION_AUTHORITY_CANARY
_ENV = "AI_TASK_PUBLIC_COMPOSITION_AUTHORITY_CANARY_ENABLED"
_CONTRACT_VERSION = (
    "promati.multi_intent.task_public_composition_authority_canary.v1"
)


def _enabled() -> bool:
    raw = os.getenv(_ENV, "true")
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _render_public_claim_text(text: str) -> str:
    # Public rendering only: do not mutate grounded claim/evidence contracts.
    raw = str(text or "").strip()
    if not raw:
        return ""

    label = ""
    payload_text = raw
    if ": " in raw:
        candidate_label, candidate_payload = raw.split(": ", 1)
        if candidate_payload.lstrip().startswith("{"):
            label = candidate_label.strip()
            payload_text = candidate_payload.strip()

    if not payload_text.startswith("{"):
        return raw

    try:
        payload = json.loads(payload_text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return raw

    if not isinstance(payload, dict):
        return raw

    summary = str(payload.get("summary") or "").strip()
    title = str(payload.get("title") or payload.get("family_name") or "").strip()
    item_id = str(payload.get("item_id") or payload.get("family_code") or "").strip()

    rendered_label = label or item_id or title
    rendered_body = summary or title or item_id
    if not rendered_body:
        return raw

    if rendered_label:
        if rendered_body.casefold().startswith(rendered_label.casefold() + ":"):
            return rendered_body
        return f"{rendered_label}: {rendered_body}"

    return rendered_body


def _claim_texts(unit: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for claim in list(unit.get("claims") or []):
        if not isinstance(claim, dict):
            continue
        text = str(claim.get("text") or "").strip()
        if text:
            rendered = _render_public_claim_text(text)
            if rendered:
                out.append(rendered)
    return out


def build_public_multi_intent_composition_authority_canary_p4_6f(
    plan: Any,
    legacy_answer: str | None,
    task_synthesis_coverage_authority: dict[str, Any] | None,
) -> tuple[str | None, dict[str, Any]]:
    enabled = _enabled()
    legacy = (
        str(legacy_answer).strip()
        if legacy_answer is not None
        else None
    )

    contract: dict[str, Any] = {
        "contract_version": _CONTRACT_VERSION,
        "enabled": enabled,
        "eligible": False,
        "authoritative": False,
        "authority_scope": "public_multi_intent_composition_only",
        "task_synthesis_coverage_authority_required": True,
        "legacy_phase_c_authority_unchanged": True,
        "legacy_reconciliation_authority": False,
        "public_answer_authority": False,
        "public_answer_replaced": False,
        "fail_open_to_legacy_answer": True,
        "included_task_ids": [],
        "included_unit_count": 0,
        "included_claim_count": 0,
        "reason": None,
    }

    if not enabled:
        contract["reason"] = "disabled"
        return legacy_answer, contract

    if not bool(getattr(plan, "multi_intent", False)):
        contract["reason"] = "blocked_not_multi_intent"
        return legacy_answer, contract

    if not legacy:
        contract["reason"] = "blocked_no_legacy_answer"
        return legacy_answer, contract

    coverage = task_synthesis_coverage_authority
    if not isinstance(coverage, dict):
        contract["reason"] = "blocked_missing_task_synthesis_coverage"
        return legacy_answer, contract

    if (
        coverage.get("authoritative") is not True
        or coverage.get("authority_scope")
        != "intent_task_grounded_synthesis_coverage_only"
        or coverage.get("complete_task_coverage") is not True
        or coverage.get("public_answer_authority") is not False
    ):
        contract["reason"] = "blocked_task_synthesis_coverage_not_ready"
        return legacy_answer, contract

    units = list(coverage.get("units") or [])
    if not units:
        contract["reason"] = "blocked_no_grounded_units"
        return legacy_answer, contract

    task_order = [
        str(getattr(task, "task_id", "") or "").strip()
        for task in list(getattr(plan, "intent_tasks", None) or [])
    ]
    task_order = [item for item in task_order if item]
    if not task_order:
        contract["reason"] = "blocked_no_intent_tasks"
        return legacy_answer, contract

    grouped: dict[str, list[dict[str, Any]]] = {
        task_id: [] for task_id in task_order
    }
    for unit in units:
        if not isinstance(unit, dict):
            contract["reason"] = "blocked_invalid_grounded_unit"
            return legacy_answer, contract

        task_id = str(unit.get("task_id") or "").strip()
        if task_id not in grouped:
            contract["reason"] = "blocked_unknown_task_unit"
            return legacy_answer, contract

        if unit.get("status") != "grounded":
            contract["reason"] = "blocked_non_grounded_unit"
            return legacy_answer, contract

        claims = _claim_texts(unit)
        if not claims:
            contract["reason"] = "blocked_unit_without_claims"
            return legacy_answer, contract

        grouped[task_id].append(unit)

    if any(not grouped[task_id] for task_id in task_order):
        contract["reason"] = "blocked_incomplete_task_units"
        return legacy_answer, contract

    lines: list[str] = []
    included_task_ids: list[str] = []
    included_claim_count = 0

    for task in list(getattr(plan, "intent_tasks", None) or []):
        task_id = str(getattr(task, "task_id", "") or "").strip()
        if task_id not in grouped:
            continue

        domain_raw = getattr(task, "domain", None)
        domain = str(getattr(domain_raw, "value", domain_raw) or "").strip()
        intent = str(getattr(task, "intent", "") or "").strip()

        title = (
            "Productinformatie"
            if domain == "product"
            else "Technische informatie"
            if domain == "technical"
            else domain.capitalize() or "Aanvullende informatie"
        )

        section_claims: list[str] = []
        for unit in grouped[task_id]:
            section_claims.extend(_claim_texts(unit))

        if not section_claims:
            contract["reason"] = "blocked_task_without_claims"
            return legacy_answer, contract

        if lines:
            lines.append("")
        lines.append(f"{title}:")
        for claim in section_claims:
            lines.append(f"- {claim}")

        included_task_ids.append(task_id)
        included_claim_count += len(section_claims)

    composed = "\n".join(lines).strip()
    if not composed:
        contract["reason"] = "blocked_empty_composed_answer"
        return legacy_answer, contract

    contract.update(
        {
            "eligible": True,
            "authoritative": True,
            "public_answer_authority": True,
            "public_answer_replaced": True,
            "included_task_ids": included_task_ids,
            "included_unit_count": len(units),
            "included_claim_count": included_claim_count,
            "reason": "activated_public_multi_intent_composition_authority",
        }
    )
    return composed, contract


__all__ = [
    "build_public_multi_intent_composition_authority_canary_p4_6f",
]
