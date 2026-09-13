"""Pure, privacy-safe observability projections for the orchestrator.

This leaf module converts primitive contract data into timing/count maps.  It
must not import pipeline, web, database, settings, or network components.
"""

from __future__ import annotations

from typing import Any


ORCHESTRATOR_OBSERVABILITY_CONTRACT_VERSION = (
    "promati.orchestrator.observability.v1"
)


def _observability_get(
    value: Any,
    key: str,
    default: Any = None,
) -> Any:
    """Read a field from a mapping or object without changing fallback rules."""
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _observability_nonnegative_int(value: Any) -> int:
    """Apply the established integer coercion and nonnegative clamp contract."""
    if isinstance(value, bool):
        return 0
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, number)


def _new_observability_timings() -> dict[str, int]:
    """Return a fresh timing map with the exact v1 keys and defaults."""
    return {
        "understanding": 0,
        "research_requirement": 0,
        "planning": 0,
        "initial_specialist": 0,
        "evidence_requirement_lookup": 0,
        "evidence_normalization": 0,
        "evidence_assessment": 0,
        "evidence_research_gate": 0,
        "evidence_research": 0,
        "reconciliation": 0,
        "synthesis": 0,
        "plan_research": 0,
        "presentation": 0,
        "response_build": 0,
        "total": 0,
    }


def _new_observability_counts() -> dict[str, int]:
    """Return a fresh count map with the exact v1 keys and defaults."""
    return {
        "execution_attempts": 0,
        "initial_specialist_calls": 0,
        "phase_c_research_follow_up_specialist_calls": 0,
        "plan_research_follow_up_specialist_calls": 0,
        "research_follow_up_specialist_calls": 0,
        "total_specialist_calls": 0,
        "initial_raw_result_rows": 0,
        "initial_evidence_items": 0,
        "reconciled_evidence_items": 0,
        "phase_c_ai_calls": 0,
        "plan_research_ai_calls": 0,
        "total_ai_calls": 0,
        "multi_intent_queries": 0,
        "task_execution_plan_shadow_evaluations": 0,
        "task_execution_plan_shadow_tasks": 0,
        "task_execution_plan_shadow_steps": 0,
        "task_execution_plan_shadow_planning_errors": 0,
        "task_execution_plan_shadow_exact_matches": 0,
        "task_research_execution_canary_executions": 0,
        "task_research_execution_canary_follow_up_specialist_calls": 0,
        "public_composition_canary_evaluations": 0,
        "public_composition_canary_enabled_requests": 0,
        "public_composition_canary_eligible_requests": 0,
        "public_composition_canary_activations": 0,
        "public_composition_canary_public_answer_replacements": 0,
        "public_composition_canary_legacy_answer_fallbacks": 0,
        "public_composition_canary_internal_error_fallbacks": 0,
        "task_public_composition_requests": 0,
        "task_public_composition_enabled": 0,
        "task_public_composition_eligible": 0,
        "task_public_composition_authoritative": 0,
        "task_public_composition_answer_replaced": 0,
        "task_public_composition_fail_open": 0,
        "task_public_composition_included_units": 0,
        "task_public_composition_included_claims": 0,
        "task_public_composition_blocked": 0,
        "task_public_composition_reason_activated": 0,
        "task_public_composition_reason_disabled": 0,
        "task_public_composition_reason_blocked_not_multi_intent": 0,
        "task_public_composition_reason_blocked_coverage_not_ready": 0,
        "task_public_composition_reason_internal_error_fail_open": 0,
        "task_public_composition_reason_blocked_other": 0,
    }


def _record_task_execution_plan_shadow_observability(
    counts: dict[str, int],
    plan: Any,
    evidence_pipeline: Any,
) -> None:
    """Record integer-only P4.6a shadow metrics without copying content."""
    if not isinstance(counts, dict):
        return
    if not bool(getattr(plan, "multi_intent", False)):
        return
    counts["task_execution_plan_shadow_evaluations"] = 1
    if not isinstance(evidence_pipeline, dict):
        return
    rows = evidence_pipeline.get("task_execution_plans_shadow")
    if not isinstance(rows, list):
        rows = []
    counts["task_execution_plan_shadow_tasks"] = len(rows)
    counts["task_execution_plan_shadow_steps"] = sum(
        len(row.get("execution_steps") or [])
        for row in rows
        if isinstance(row, dict)
    )
    counts["task_execution_plan_shadow_planning_errors"] = sum(
        1
        for row in rows
        if isinstance(row, dict)
        and str(row.get("status") or "") == "planning_error"
    )
    comparison = evidence_pipeline.get("task_execution_plan_comparison_shadow")
    if isinstance(comparison, dict):
        exact = (
            comparison.get("exact_steps_equivalent") is True
            or comparison.get("exact_match") is True
            or comparison.get("steps_equivalent") is True
        )
        counts["task_execution_plan_shadow_exact_matches"] = int(exact)


def _record_public_composition_canary_release_observability(
    counts: dict[str, int],
    plan: Any,
    evidence_pipeline: Any,
) -> None:
    """Project canary/release contracts to privacy-safe request counters."""
    if not isinstance(counts, dict):
        return
    counts["multi_intent_queries"] = int(bool(getattr(plan, "multi_intent", False)))
    if not isinstance(evidence_pipeline, dict):
        return
    execution_rows = evidence_pipeline.get("task_research_execution_canary_shadow")
    if isinstance(execution_rows, list):
        executed_rows = [
            row for row in execution_rows
            if isinstance(row, dict) and row.get("executed") is True
        ]
        counts["task_research_execution_canary_executions"] = len(executed_rows)
        counts["task_research_execution_canary_follow_up_specialist_calls"] = sum(
            _observability_nonnegative_int(row.get("follow_up_specialist_calls"))
            for row in executed_rows
        )
    contract = evidence_pipeline.get("public_composition_canary_shadow")
    if not isinstance(contract, dict):
        return
    enabled = contract.get("enabled") is True
    eligible = contract.get("eligible") is True
    activated = contract.get("activated") is True
    replaced = contract.get("public_answer_replaced") is True
    reason = str(contract.get("reason") or "").strip()
    counts["public_composition_canary_evaluations"] = 1
    counts["public_composition_canary_enabled_requests"] = int(enabled)
    counts["public_composition_canary_eligible_requests"] = int(eligible)
    counts["public_composition_canary_activations"] = int(activated)
    counts["public_composition_canary_public_answer_replacements"] = int(replaced)
    counts["public_composition_canary_legacy_answer_fallbacks"] = int(enabled and not replaced)
    counts["public_composition_canary_internal_error_fallbacks"] = int(
        reason == "blocked_internal_error_fail_open"
    )
    task_public = evidence_pipeline.get("task_public_composition_authority_p4_6f")
    if not isinstance(task_public, dict):
        return
    counts["task_public_composition_requests"] = 1
    enabled = task_public.get("enabled") is True
    eligible = task_public.get("eligible") is True
    authoritative = task_public.get("authoritative") is True
    replaced = task_public.get("public_answer_replaced") is True
    reason = str(task_public.get("reason") or "").strip()
    counts["task_public_composition_enabled"] = int(enabled)
    counts["task_public_composition_eligible"] = int(eligible)
    counts["task_public_composition_authoritative"] = int(authoritative)
    counts["task_public_composition_answer_replaced"] = int(replaced)
    counts["task_public_composition_included_units"] = _observability_nonnegative_int(
        task_public.get("included_unit_count")
    )
    counts["task_public_composition_included_claims"] = _observability_nonnegative_int(
        task_public.get("included_claim_count")
    )
    blocked = bool(reason.startswith("blocked_")) and not replaced
    counts["task_public_composition_blocked"] = int(blocked)
    counts["task_public_composition_fail_open"] = int(blocked)
    coverage_block_reasons = {
        "blocked_missing_task_synthesis_coverage",
        "blocked_task_synthesis_coverage_not_ready",
        "blocked_no_grounded_units",
        "blocked_incomplete_task_units",
    }
    counts["task_public_composition_reason_activated"] = int(
        reason == "activated_public_multi_intent_composition_authority"
    )
    counts["task_public_composition_reason_disabled"] = int(reason == "disabled")
    counts["task_public_composition_reason_blocked_not_multi_intent"] = int(
        reason == "blocked_not_multi_intent"
    )
    counts["task_public_composition_reason_blocked_coverage_not_ready"] = int(
        reason in coverage_block_reasons
    )
    counts["task_public_composition_reason_internal_error_fail_open"] = int(
        reason == "blocked_internal_error_fail_open"
    )
    counts["task_public_composition_reason_blocked_other"] = int(
        blocked
        and reason not in coverage_block_reasons
        and reason not in {
            "blocked_not_multi_intent",
            "blocked_internal_error_fail_open",
        }
    )


__all__ = (
    "ORCHESTRATOR_OBSERVABILITY_CONTRACT_VERSION",
    "_new_observability_counts",
    "_new_observability_timings",
    "_observability_get",
    "_observability_nonnegative_int",
    "_record_public_composition_canary_release_observability",
    "_record_task_execution_plan_shadow_observability",
)
