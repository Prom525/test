from __future__ import annotations

from typing import Any


TASK_EXECUTION_SHADOW_CONTRACT_VERSION = "promati.orchestrator.task_execution_shadow.v1"


def _value(value: Any) -> str:
    return str(getattr(value, "value", value) or "").strip()


def build_task_execution_shadow(plan: Any, trace: Any = None) -> dict[str, Any]:
    """Compare CP7 tasks with the legacy plan and trace without affecting either."""
    steps = list(getattr(plan, "execution_steps", None) or [])
    attempts = list(getattr(trace, "attempts", None) or [])
    excluded_domains = [
        _value(domain)
        for domain in (getattr(plan, "excluded_domains", None) or [])
        if _value(domain)
    ]
    task_rows: list[dict[str, Any]] = []
    for task in (getattr(plan, "intent_tasks", None) or []):
        domain = _value(getattr(task, "domain", None))
        polarity = _value(getattr(task, "polarity", "requested")) or "requested"
        required = bool(getattr(task, "required", True))
        matching_steps = [step for step in steps if _value(step.domain) == domain]
        step = matching_steps[0] if matching_steps else None
        matching_attempts = []
        for attempt in attempts:
            same_step = step is not None and str(attempt.step_id) == str(step.step_id)
            same_action = step is not None and str(attempt.action) == str(step.action)
            same_domain = _value(attempt.domain) == domain
            if same_step or (same_domain and (step is None or same_action)):
                matching_attempts.append(attempt)
        attempt = matching_attempts[0] if matching_attempts else None
        excluded = polarity == "excluded" or domain in excluded_domains
        planned = step is not None and not excluded
        executed = attempt is not None and not excluded
        if excluded:
            gap_reason = "excluded"
        elif executed:
            gap_reason = None
        elif planned:
            gap_reason = "not_executed"
        elif required:
            gap_reason = "not_planned"
        else:
            gap_reason = "optional_not_planned"
        task_rows.append({
            "task_id": str(getattr(task, "task_id", "") or ""),
            "domain": domain,
            "intent": str(getattr(task, "intent", "") or ""),
            "required": required,
            "polarity": polarity,
            "coverage_requirement": getattr(task, "coverage_requirement", None),
            "evidence_requirement_set_id": getattr(task, "evidence_requirement_set_id", None),
            "planned": planned,
            "executed": executed,
            "matched_step_id": str(step.step_id) if step is not None else None,
            "matched_action": str(attempt.action if attempt is not None else step.action)
            if (attempt is not None or step is not None) else None,
            "gap_reason": gap_reason,
        })
    required_rows = [
        row for row in task_rows
        if row["required"] and row["polarity"] == "requested"
    ]
    missing = [row for row in required_rows if not row["executed"]]
    return {
        "contract_version": TASK_EXECUTION_SHADOW_CONTRACT_VERSION,
        "summary": {
            "required_total": len(required_rows),
            "required_planned": sum(row["planned"] for row in required_rows),
            "required_executed": sum(row["executed"] for row in required_rows),
            "required_missing": len(missing),
            "missing_required_tasks": [row["task_id"] for row in missing],
        },
        "tasks": task_rows,
        "excluded_domains": excluded_domains,
        "shadow_only": True,
    }
