from __future__ import annotations

from typing import Any


TASK_AUTHORITY_GATE_CONTRACT_VERSION = (
    "promati.orchestrator.task_authority_gate.cp9.v1"
)
TASK_COVERAGE_GATE_CONTRACT_VERSION = (
    "promati.orchestrator.task_coverage_gate.cp10.v1"
)


def build_task_coverage_gate_status(
    task_execution_shadow: dict[str, Any] | None,
    task_synthesis_coverage_authority: dict[str, Any] | None,
) -> dict[str, Any]:
    """Report whether execution and evidence coverage permit public authority."""
    summary = (
        task_execution_shadow.get("summary")
        if isinstance(task_execution_shadow, dict)
        else None
    )
    raw_missing = (
        summary.get("missing_required_tasks")
        if isinstance(summary, dict)
        else None
    )
    missing = list(raw_missing or []) if isinstance(raw_missing, list) else []
    missing = [str(task_id) for task_id in missing if str(task_id).strip()]
    required_missing = (
        summary.get("required_missing")
        if isinstance(summary, dict)
        else None
    )
    execution_available = (
        isinstance(summary, dict)
        and isinstance(raw_missing, list)
        and isinstance(required_missing, int)
        and required_missing == len(missing)
    )
    execution_covered = execution_available and required_missing == 0

    coverage = task_synthesis_coverage_authority
    coverage_available = isinstance(coverage, dict)
    coverage_complete = (
        coverage_available and coverage.get("complete_task_coverage") is True
    )
    coverage_authoritative = (
        coverage_available
        and coverage.get("authoritative") is True
        and coverage.get("authority_scope")
        == "intent_task_grounded_synthesis_coverage_only"
        and coverage_complete
        and coverage.get("public_answer_authority") is False
    )

    if missing:
        reason = "missing_required_tasks"
    elif not execution_available:
        reason = "task_execution_shadow_unavailable"
    elif not coverage_available:
        reason = "coverage_unavailable"
    elif not coverage_authoritative:
        reason = "coverage_not_authoritative"
    else:
        reason = "required_execution_and_coverage_authoritative"

    authoritative = execution_covered and coverage_authoritative
    return {
        "contract_version": TASK_COVERAGE_GATE_CONTRACT_VERSION,
        "evaluated": True,
        "blocked": not authoritative,
        "authoritative": authoritative,
        "reason": reason,
        "missing_required_tasks": missing,
        "required_task_execution_covered": execution_covered,
        "task_execution_shadow_available": execution_available,
        "coverage_available": coverage_available,
        "coverage_complete": coverage_complete,
        "coverage_authoritative": coverage_authoritative,
        "coverage_reason": (
            coverage.get("reason") if coverage_available else None
        ),
    }


def guard_task_coverage_authority(
    candidate_answer: str | None,
    fallback_answer: str | None,
    composition_authority: dict[str, Any] | None,
    gate: dict[str, Any],
) -> tuple[str | None, dict[str, Any]]:
    """Fail closed for public authority unless the CP10 gate passes."""
    authority = dict(composition_authority or {})
    authority["task_coverage_gate_cp10"] = gate
    if gate.get("blocked") is not True:
        return candidate_answer, authority

    previous_reason = authority.get("reason")
    authority.update(
        {
            "authoritative": False,
            "public_answer_authority": False,
            "public_answer_replaced": False,
            "blocked": True,
            "reason": gate.get("reason"),
            "missing_required_tasks": list(
                gate.get("missing_required_tasks") or []
            ),
            "authority_reason_before_cp10_gate": previous_reason,
        }
    )
    return fallback_answer, authority


def guard_public_composition_authority(
    candidate_answer: str | None,
    fallback_answer: str | None,
    composition_authority: dict[str, Any] | None,
    task_execution_shadow: dict[str, Any] | None,
) -> tuple[str | None, dict[str, Any], dict[str, Any]]:
    """Fail closed when CP8 cannot prove execution of every required task."""
    authority = dict(composition_authority or {})
    summary = (
        task_execution_shadow.get("summary")
        if isinstance(task_execution_shadow, dict)
        else None
    )
    raw_missing = (
        summary.get("missing_required_tasks")
        if isinstance(summary, dict)
        else None
    )
    missing = list(raw_missing or []) if isinstance(raw_missing, list) else []
    missing = [str(task_id) for task_id in missing if str(task_id).strip()]
    required_missing = (
        summary.get("required_missing")
        if isinstance(summary, dict)
        else None
    )
    shadow_available = (
        isinstance(summary, dict)
        and isinstance(raw_missing, list)
        and isinstance(required_missing, int)
        and required_missing == len(missing)
    )

    gate: dict[str, Any] = {
        "contract_version": TASK_AUTHORITY_GATE_CONTRACT_VERSION,
        "evaluated": True,
        "blocked": False,
        "reason": "required_task_execution_covered",
        "missing_required_tasks": missing,
        "task_execution_shadow_required": True,
        "task_execution_shadow_available": shadow_available,
    }

    if shadow_available and required_missing == 0:
        authority["task_authority_gate_cp9"] = gate
        return candidate_answer, authority, gate

    reason = (
        "missing_required_tasks"
        if missing
        else "task_execution_shadow_unavailable"
    )
    gate.update({"blocked": True, "reason": reason})
    previous_reason = authority.get("reason")
    authority.update(
        {
            "authoritative": False,
            "public_answer_authority": False,
            "public_answer_replaced": False,
            "blocked": True,
            "reason": reason,
            "missing_required_tasks": missing,
            "authority_reason_before_cp9_gate": previous_reason,
            "task_authority_gate_cp9": gate,
        }
    )
    return fallback_answer, authority, gate


def guard_public_composition_canary(
    public_composition: dict[str, Any] | None,
    gate: dict[str, Any],
) -> dict[str, Any] | None:
    """Prevent an earlier public canary replacement from bypassing CP9."""
    if not isinstance(public_composition, dict) or gate.get("blocked") is not True:
        return public_composition

    contract = dict(public_composition)
    contract.update(
        {
            "activated": False,
            "authoritative": False,
            "public_answer_replaced": False,
            "blocked": True,
            "reason": gate.get("reason"),
            "missing_required_tasks": list(
                gate.get("missing_required_tasks") or []
            ),
            "task_authority_gate_cp9": gate,
        }
    )
    return contract


__all__ = [
    "TASK_AUTHORITY_GATE_CONTRACT_VERSION",
    "TASK_COVERAGE_GATE_CONTRACT_VERSION",
    "build_task_coverage_gate_status",
    "guard_public_composition_canary",
    "guard_public_composition_authority",
    "guard_task_coverage_authority",
]
