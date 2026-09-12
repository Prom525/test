from __future__ import annotations

from typing import Any


TASK_PLANNER_CANARY_CONTRACT_VERSION = "promati.orchestrator.task_planner_canary.v1"

_ACTIONS_BY_DOMAIN = {
    "rfq": "rfq_assistant",
    "product": "product_assistant",
    "technical": "technical_assistant",
    "inspection": "analysis_assistant",
    "org": "org_assistant",
    "diagnostics": "diagnostics_assistant",
}


def _value(value: Any) -> str:
    return str(getattr(value, "value", value) or "").strip()


def _conservative_params(plan: Any, domain: str, legacy_steps: list[Any]) -> dict[str, Any]:
    """Reuse the legacy contract when present; otherwise send only the question."""
    for step in legacy_steps:
        if _value(getattr(step, "domain", None)) == domain:
            return dict(getattr(step, "params", None) or {})
    question = str(getattr(plan, "original_question", "") or "").strip()
    return {"vraag": question} if question else {}


def build_task_planner_canary(plan: Any) -> dict[str, Any]:
    """Derive and compare a task-driven plan without mutating the legacy plan."""
    legacy_steps = list(getattr(plan, "execution_steps", None) or [])
    excluded_domains = {
        _value(domain)
        for domain in (getattr(plan, "excluded_domains", None) or [])
        if _value(domain)
    }
    proposed_steps: list[dict[str, Any]] = []
    task_rows: list[dict[str, Any]] = []

    for task in (getattr(plan, "intent_tasks", None) or []):
        domain = _value(getattr(task, "domain", None))
        required = bool(getattr(task, "required", True))
        polarity = _value(getattr(task, "polarity", "requested")) or "requested"
        action = _ACTIONS_BY_DOMAIN.get(domain)
        if not required or polarity != "requested" or domain in excluded_domains or not action:
            continue
        step_id = f"canary_{len(proposed_steps) + 1}"
        proposed_steps.append({
            "step_id": step_id,
            "task_id": str(getattr(task, "task_id", "") or ""),
            "domain": domain,
            "intent": str(getattr(task, "intent", "") or ""),
            "action": action,
            "params": _conservative_params(plan, domain, legacy_steps),
            "required": True,
        })

    unmatched_legacy = set(range(len(legacy_steps)))
    for proposed in proposed_steps:
        same_domain = [
            index for index in unmatched_legacy
            if _value(getattr(legacy_steps[index], "domain", None)) == proposed["domain"]
        ]
        exact = [
            index for index in same_domain
            if str(getattr(legacy_steps[index], "action", "")) == proposed["action"]
        ]
        matched_index = exact[0] if exact else (same_domain[0] if same_domain else None)
        if matched_index is None:
            match_status = "missing_in_legacy"
            gap_reason = "no_legacy_step_for_required_task"
            matched_step_id = None
        else:
            unmatched_legacy.remove(matched_index)
            legacy_step = legacy_steps[matched_index]
            matched_step_id = str(getattr(legacy_step, "step_id", "") or "") or None
            if exact:
                match_status = "exact_match"
                gap_reason = None
            else:
                match_status = "action_mismatch"
                gap_reason = "legacy_action_differs"
        task_rows.append({
            "task_id": proposed["task_id"],
            "domain": proposed["domain"],
            "intent": proposed["intent"],
            "proposed_action": proposed["action"],
            "matched_legacy_step_id": matched_step_id,
            "match_status": match_status,
            "gap_reason": gap_reason,
        })

    return {
        "contract_version": TASK_PLANNER_CANARY_CONTRACT_VERSION,
        "summary": {
            "legacy_steps": len(legacy_steps),
            "canary_steps": len(proposed_steps),
            "exact_matches": sum(row["match_status"] == "exact_match" for row in task_rows),
            "missing_in_legacy": sum(row["match_status"] == "missing_in_legacy" for row in task_rows),
            "extra_in_legacy": len(unmatched_legacy),
            "action_mismatches": sum(row["match_status"] == "action_mismatch" for row in task_rows),
        },
        "proposed_steps": proposed_steps,
        "tasks": task_rows,
        "excluded_domains": sorted(excluded_domains),
        "canary_only": True,
        "legacy_authoritative": True,
    }
