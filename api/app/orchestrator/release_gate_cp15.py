from __future__ import annotations

from typing import Any


RELEASE_GATE_CP15_CONTRACT_VERSION = (
    "promati.orchestrator.release_gate.cp15.v1"
)

_CP14_GATES = (
    ("cp14_d2", "task_research_execution_authority_p4_6d2",
     "intent_task_research_execution_only"),
    ("cp14_e1", "task_research_evidence_authority_p4_6e1",
     "intent_task_research_evidence_reassessment_only"),
    ("cp14_e2", "task_grounded_synthesis_authority_p4_6e2",
     "intent_task_grounded_synthesis_only"),
    ("cp14_e3", "task_grounded_synthesis_coverage_authority_p4_6e3",
     "intent_task_grounded_synthesis_coverage_only"),
)


def build_release_gate_cp15(
    task_execution_shadow: Any,
    evidence_pipeline: Any,
) -> dict[str, Any]:
    """Observe CP8-CP14 and make one fail-closed release decision.

    This contract is diagnostics-only: it never changes the answer or any
    upstream authority contract.
    """
    blocked: list[str] = []
    reasons: list[str] = []

    def reject(gate_id: str, reason: str) -> None:
        if gate_id not in blocked:
            blocked.append(gate_id)
        if reason not in reasons:
            reasons.append(reason)

    contract: dict[str, Any] = {
        "contract_version": RELEASE_GATE_CP15_CONTRACT_VERSION,
        "evaluated": True,
        "release_allowed": False,
        "public_authoritative": False,
        "blocking_reasons": reasons,
        "blocked_gate_ids": blocked,
        "counts": {
            "required": None,
            "planned": None,
            "executed": None,
            "missing": None,
            "covered": None,
        },
        "gate_status": {},
        "research": {
            "explicit_requested": False,
            "allowed_task_count": None,
            "chain_required": False,
            "authoritative_chain_complete": False,
        },
    }

    summary = (
        task_execution_shadow.get("summary")
        if isinstance(task_execution_shadow, dict) else None
    )
    count_keys = (
        "required_total", "required_planned", "required_executed",
        "required_missing",
    )
    missing_tasks = summary.get("missing_required_tasks") if isinstance(summary, dict) else None
    counts_valid = (
        isinstance(summary, dict)
        and all(type(summary.get(key)) is int and summary[key] >= 0 for key in count_keys)
        and isinstance(missing_tasks, list)
        and all(isinstance(task_id, str) and task_id.strip() for task_id in missing_tasks)
        and summary["required_missing"] == len(missing_tasks)
        and summary["required_planned"] <= summary["required_total"]
        and summary["required_executed"] <= summary["required_planned"]
        and summary["required_executed"] + summary["required_missing"] == summary["required_total"]
    )
    if counts_valid:
        contract["counts"].update({
            "required": summary["required_total"],
            "planned": summary["required_planned"],
            "executed": summary["required_executed"],
            "missing": summary["required_missing"],
        })
        if missing_tasks:
            reject("cp8", "cp8_missing_required_execution")
    else:
        reject("cp8", "cp8_missing_or_malformed_execution_shadow")
    contract["gate_status"]["cp8"] = {
        "valid": counts_valid,
        "missing_required_tasks": list(missing_tasks) if isinstance(missing_tasks, list) else [],
    }

    if not isinstance(evidence_pipeline, dict):
        reject("cp9", "missing_or_malformed_evidence_pipeline")
        for gate_id in ("cp10", "cp11", "cp12", "cp13"):
            reject(gate_id, f"{gate_id}_missing_or_malformed_gate")
        return contract

    def require_gate(gate_id: str, key: str, predicate) -> Any:
        value = evidence_pipeline.get(key)
        valid = isinstance(value, dict) and value.get("evaluated") is True
        passed = valid and predicate(value)
        contract["gate_status"][gate_id] = {
            "valid": valid,
            "passed": passed,
            "reason": value.get("reason") if isinstance(value, dict) else None,
        }
        if not valid:
            reject(gate_id, f"{gate_id}_missing_or_malformed_gate")
        elif not passed:
            reject(gate_id, f"{gate_id}_{value.get('reason') or 'not_authoritative'}")
        return value

    cp9 = require_gate(
        "cp9", "task_authority_gate_cp9",
        lambda value: (
            value.get("contract_version")
            == "promati.orchestrator.task_authority_gate.cp9.v1"
            and value.get("blocked") is False
        ),
    )
    cp10 = require_gate(
        "cp10", "task_coverage_gate_cp10",
        lambda value: (
            value.get("contract_version")
            == "promati.orchestrator.task_coverage_gate.cp10.v1"
            and value.get("blocked") is False
            and value.get("authoritative") is True
        ),
    )
    cp11 = require_gate(
        "cp11", "task_presenter_cp11",
        lambda value: (
            value.get("contract_version")
            == "promati.orchestrator.task_relevance_presenter.cp11.v1"
            and value.get("authoritative") is True
            and value.get("public_answer_replaced") is True
        ),
    )
    cp12 = require_gate(
        "cp12", "task_concise_composer_cp12",
        lambda value: (
            value.get("contract_version")
            == "promati.orchestrator.task_concise_composer.cp12.v1"
            and value.get("authoritative") is True
            and value.get("public_answer_replaced") is True
        ),
    )
    semantics = require_gate(
        "cp13", "task_research_semantics_cp13",
        lambda value: (
            value.get("contract_version")
            == "promati.orchestrator.task_research_semantics.cp13.v1"
            and value.get("authority_scope") == "intent_task_research_eligibility_only"
            and value.get("legacy_generic_research_allowed") is False
            and isinstance(value.get("allowed_task_ids"), list)
            and value.get("public_answer_authority") is False
        ),
    )

    composition = evidence_pipeline.get(
        "task_public_composition_authority_p4_6f"
    )
    composition_valid = isinstance(composition, dict)
    composition_passed = (
        composition_valid
        and composition.get("authoritative") is True
        and composition.get("public_answer_authority") is True
        and composition.get("public_answer_replaced") is True
        and composition.get("blocked") is False
    )
    contract["gate_status"]["public_composition"] = {
        "valid": composition_valid,
        "passed": composition_passed,
        "reason": composition.get("reason") if composition_valid else None,
    }
    if not composition_valid:
        reject("public_composition", "public_composition_missing_or_malformed_gate")
    elif not composition_passed:
        reject(
            "public_composition",
            f"public_composition_{composition.get('reason') or 'not_authoritative'}",
        )

    coverage_complete = cp10.get("coverage_complete") if isinstance(cp10, dict) else None
    contract["counts"]["covered"] = (
        contract["counts"]["required"] if coverage_complete is True else 0
        if coverage_complete is False else None
    )

    explicit = semantics.get("explicit_research_requested") is True if isinstance(semantics, dict) else False
    allowed = semantics.get("allowed_task_ids") if isinstance(semantics, dict) else None
    allowed_count = len(allowed) if isinstance(allowed, list) else None
    d2 = evidence_pipeline.get("task_research_execution_authority_p4_6d2")
    research_execution_observed = isinstance(d2, dict) and (
        d2.get("authoritative") is True
        or isinstance(d2.get("follow_up_specialist_call_count"), int)
        and d2.get("follow_up_specialist_call_count", 0) > 0
        or isinstance(d2.get("accepted_follow_up_result_count"), int)
        and d2.get("accepted_follow_up_result_count", 0) > 0
    )
    chain_required = explicit or bool(allowed) or research_execution_observed
    contract["research"].update({
        "explicit_requested": explicit,
        "allowed_task_count": allowed_count,
        "chain_required": chain_required,
    })
    if explicit and allowed == []:
        reject("cp13", "cp13_explicit_research_without_allowed_tasks")

    chain_complete = False
    if chain_required:
        chain_complete = True
        for gate_id, key, scope in _CP14_GATES:
            value = evidence_pipeline.get(key)
            valid = isinstance(value, dict)
            passed = valid and value.get("authoritative") is True and value.get("authority_scope") == scope
            contract["gate_status"][gate_id] = {
                "valid": valid,
                "passed": passed,
                "reason": value.get("reason") if valid else None,
            }
            if not passed:
                chain_complete = False
                reject(gate_id, f"{gate_id}_{value.get('reason') or 'missing_or_not_authoritative'}" if valid else f"{gate_id}_missing_or_malformed_gate")
    else:
        contract["gate_status"]["cp14"] = {
            "valid": True,
            "passed": True,
            "reason": "research_chain_not_required",
        }
    contract["research"]["authoritative_chain_complete"] = chain_complete

    release_allowed = not blocked
    contract["release_allowed"] = release_allowed
    contract["public_authoritative"] = release_allowed
    return contract


__all__ = [
    "RELEASE_GATE_CP15_CONTRACT_VERSION",
    "build_release_gate_cp15",
]
