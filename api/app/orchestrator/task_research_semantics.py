from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from app.orchestrator.evidence_research_gate import ResearchGateStatus


TASK_RESEARCH_SEMANTICS_CP13_CONTRACT_VERSION = (
    "promati.orchestrator.task_research_semantics.cp13.v1"
)


def _value(value: Any) -> str:
    return str(getattr(value, "value", value) or "").strip()


def _decision_value(decision: Any, key: str, default: Any = None) -> Any:
    if isinstance(decision, dict):
        return decision.get(key, default)
    return getattr(decision, key, default)


_EXPLICIT_RESEARCH_PATTERNS = (
    re.compile(r"\bresearch\b", re.IGNORECASE),
    re.compile(r"\bonderzoek\b", re.IGNORECASE),
    re.compile(r"\bgrondig\s+analyseren\b", re.IGNORECASE),
    re.compile(r"\bend[\s-]+to[\s-]+end\s+analyse\b", re.IGNORECASE),
)


def _has_explicit_research_request(plan: Any) -> bool:
    complexity_reasons = {
        _value(item)
        for item in (getattr(plan, "complexity_reasons", None) or [])
        if _value(item)
    }
    if "explicit_research_request" in complexity_reasons:
        return True

    question = " ".join(
        str(getattr(plan, field, "") or "").strip()
        for field in ("original_question", "normalized_question")
    )
    return any(pattern.search(question) for pattern in _EXPLICIT_RESEARCH_PATTERNS)


def build_task_research_semantics(
    plan: Any,
    task_execution_shadow: dict[str, Any] | None,
    task_research_authority: dict[str, Any] | None,
    task_coverage_gate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Decide research eligibility per required intent task, fail closed.

    This contract grants research-execution scope only. It deliberately grants
    no evidence, synthesis, presenter, composer, or public-answer authority.
    """
    tasks = list(getattr(plan, "intent_tasks", None) or [])
    excluded_domains = {
        _value(item) for item in (getattr(plan, "excluded_domains", None) or [])
        if _value(item)
    }
    execution_rows = {
        str(row.get("task_id") or ""): row
        for row in list((task_execution_shadow or {}).get("tasks") or [])
        if isinstance(row, dict) and row.get("task_id")
    }
    decision_rows = {
        str(row.get("task_id") or ""): row
        for row in list(
            (task_research_authority or {}).get("task_research_decisions") or []
        )
        if isinstance(row, dict) and row.get("task_id")
    }
    authority_active = bool(
        isinstance(task_research_authority, dict)
        and task_research_authority.get("authoritative") is True
        and task_research_authority.get("authority_scope")
        == "intent_task_research_decision_only"
    )
    clarification_required = bool(getattr(plan, "clarification_required", False))
    explicit_research_requested = _has_explicit_research_request(plan)
    missing_required_tasks = sorted(
        str(item)
        for item in list((task_coverage_gate or {}).get("missing_required_tasks") or [])
        if str(item).strip()
    )
    coverage_gate_reason = (
        str((task_coverage_gate or {}).get("reason") or "").strip() or None
    )

    rows: list[dict[str, Any]] = []
    allowed_task_ids: list[str] = []
    for task in tasks:
        task_id = _value(getattr(task, "task_id", None))
        domain = _value(getattr(task, "domain", None))
        intent = _value(getattr(task, "intent", None))
        required = bool(getattr(task, "required", True))
        polarity = _value(getattr(task, "polarity", "requested")) or "requested"
        execution = execution_rows.get(task_id)
        decision_entry = decision_rows.get(task_id)
        decision = decision_entry.get("research_decision") if decision_entry else None
        has_gap = bool(_decision_value(decision, "research_required", False))
        target_ids = sorted(
            str(item) for item in list(
                _decision_value(decision, "target_requirement_ids", ()) or ()
            ) if str(item).strip()
        )

        if clarification_required:
            reason = "clarification_required"
        elif not required:
            reason = "not_required_task"
        elif polarity != "requested":
            reason = (
                "negated_domain"
                if polarity in {"excluded", "negated"}
                else "polarity_not_requested"
            )
        elif domain in excluded_domains:
            reason = "excluded_domain"
        elif not isinstance(execution, dict) or execution.get("executed") is not True:
            reason = "missing_required_execution"
        elif not authority_active or decision is None:
            reason = "research_decision_unavailable"
        elif not has_gap:
            reason = "coverage_already_authoritative"
        elif not target_ids:
            reason = "coverage_gap_without_targets"
        else:
            reason = "coverage_gap"
            allowed_task_ids.append(task_id)

        allowed = reason == "coverage_gap"
        rows.append({
            "task_id": task_id,
            "domain": domain,
            "intent": intent,
            "required": required,
            "polarity": polarity,
            "research_allowed": allowed,
            "reason": reason,
            "target_requirement_ids": target_ids if allowed else [],
        })

    return {
        "contract_version": TASK_RESEARCH_SEMANTICS_CP13_CONTRACT_VERSION,
        "evaluated": True,
        "authoritative": False,
        "authority_scope": "intent_task_research_eligibility_only",
        "public_answer_authority": False,
        "evidence_authority": False,
        "synthesis_authority": False,
        "research_results_require_coverage_authority_pipeline": True,
        "legacy_generic_research_allowed": False if tasks else None,
        "explicit_research_requested": explicit_research_requested,
        "research_intent_detected": explicit_research_requested,
        "clarification_required": clarification_required,
        "task_coverage_gate_reason": coverage_gate_reason,
        "missing_required_tasks": missing_required_tasks,
        "excluded_domains": sorted(excluded_domains),
        "excluded_domain_decisions": [
            {"domain": domain, "research_allowed": False, "reason": "excluded_domain"}
            for domain in sorted(excluded_domains)
        ],
        "allowed_task_ids": allowed_task_ids,
        "research_allowed_task_count": len(allowed_task_ids),
        "tasks": rows,
        "reason": "task_scoped_research_evaluated" if tasks else "no_intent_tasks",
    }


def gate_legacy_generic_research(
    decision: Any,
    semantics: dict[str, Any] | None,
) -> Any:
    """Suppress whole-question research when CP13 has intent-task semantics."""
    if (
        not isinstance(semantics, dict)
        or semantics.get("legacy_generic_research_allowed") is not False
    ):
        return decision
    return replace(
        decision,
        status=ResearchGateStatus.NOT_REQUIRED,
        research_required=False,
        target_requirement_ids=(),
        reasons=tuple(
            sorted(
                set(
                    tuple(getattr(decision, "reasons", ()) or ())
                    + ("cp13_generic_research_suppressed",)
                )
            )
        ),
    )


__all__ = [
    "TASK_RESEARCH_SEMANTICS_CP13_CONTRACT_VERSION",
    "build_task_research_semantics",
    "gate_legacy_generic_research",
]
