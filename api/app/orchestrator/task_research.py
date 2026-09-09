from __future__ import annotations

import os
from typing import Any

from app.orchestrator.evidence_research_gate import (
    decide_research_requirement,
)


# PROMATI_P4_6D1_TASK_RESEARCH_DECISION_AUTHORITY_CANARY
_TASK_RESEARCH_AUTHORITY_ENV = (
    "AI_TASK_RESEARCH_AUTHORITY_CANARY_ENABLED"
)
_CONTRACT_VERSION = (
    "promati.multi_intent."
    "task_research_decision_authority_canary.v1"
)


def _enabled() -> bool:
    raw = os.getenv(
        _TASK_RESEARCH_AUTHORITY_ENV,
        "true",
    )
    return str(raw).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _status_value(value: Any) -> Any:
    raw = getattr(value, "value", value)
    if raw is None:
        return None
    return str(raw)


def _decision_value(
    decision: Any,
    key: str,
    default: Any = None,
) -> Any:
    if isinstance(decision, dict):
        return decision.get(key, default)
    return getattr(decision, key, default)


def _decision_signature(
    entry: dict[str, Any],
) -> dict[str, Any]:
    decision = entry.get("research_decision")
    family_rows = []

    for row in list(
        entry.get(
            "product_family_scope_research_decisions"
        )
        or []
    ):
        if not isinstance(row, dict):
            continue
        family_decision = row.get("research_decision")
        family_rows.append(
            {
                "family_code": row.get("family_code"),
                "status": row.get("status"),
                "assessment_status": row.get(
                    "assessment_status"
                ),
                "research_required": bool(
                    _decision_value(
                        family_decision,
                        "research_required",
                        False,
                    )
                ),
                "target_requirement_ids": sorted(
                    str(item)
                    for item in list(
                        _decision_value(
                            family_decision,
                            "target_requirement_ids",
                            (),
                        )
                        or ()
                    )
                ),
                "decision_intent": _decision_value(
                    family_decision,
                    "intent",
                    None,
                ),
            }
        )

    return {
        "task_id": entry.get("task_id"),
        "domain": entry.get("domain"),
        "intent": entry.get("intent"),
        "primary": bool(
            entry.get("primary", False)
        ),
        "status": entry.get("status"),
        "assessment_status": entry.get(
            "assessment_status"
        ),
        "research_required": bool(
            _decision_value(
                decision,
                "research_required",
                False,
            )
        ),
        "target_requirement_ids": sorted(
            str(item)
            for item in list(
                _decision_value(
                    decision,
                    "target_requirement_ids",
                    (),
                )
                or ()
            )
        ),
        "decision_intent": _decision_value(
            decision,
            "intent",
            None,
        ),
        "product_family_scope_research_decisions": (
            sorted(
                family_rows,
                key=lambda row: str(
                    row.get("family_code") or ""
                ).casefold(),
            )
        ),
    }


def _derive_from_authoritative_assessments(
    task_assessments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []

    for item in list(task_assessments or []):
        if not isinstance(item, dict):
            continue

        assessment = item.get("assessment")
        entry: dict[str, Any] = {
            "contract_version": (
                "promati.multi_intent."
                "task_research_decision_authoritative.v1"
            ),
            "task_id": item.get("task_id"),
            "domain": item.get("domain"),
            "intent": item.get("intent"),
            "primary": bool(
                item.get("primary", False)
            ),
            "scope": dict(
                item.get("scope") or {}
            ),
            "evidence_requirement_set_id": (
                item.get(
                    "evidence_requirement_set_id"
                )
            ),
            "resolved_requirement_set_id": (
                item.get(
                    "resolved_requirement_set_id"
                )
            ),
            "assessment_status": _status_value(
                getattr(
                    assessment,
                    "status",
                    None,
                )
            ),
            "research_decision": None,
            "product_family_scope_research_decisions": [],
            "authoritative": True,
        }

        if assessment is None:
            entry["status"] = "not_assessed"
        else:
            entry["research_decision"] = (
                decide_research_requirement(
                    assessment
                )
            )
            entry["status"] = "decided"

        family_rows = item.get(
            "product_family_scope_assessments"
        )
        if isinstance(family_rows, list):
            family_decisions = []

            for family_row in family_rows:
                if not isinstance(
                    family_row,
                    dict,
                ):
                    continue

                family_assessment = (
                    family_row.get(
                        "assessment"
                    )
                )
                family_entry: dict[
                    str,
                    Any,
                ] = {
                    "family_code": (
                        family_row.get(
                            "family_code"
                        )
                    ),
                    "assessment_status": (
                        _status_value(
                            getattr(
                                family_assessment,
                                "status",
                                None,
                            )
                        )
                    ),
                    "research_decision": None,
                }

                if family_assessment is None:
                    family_entry[
                        "status"
                    ] = "not_assessed"
                else:
                    family_entry[
                        "research_decision"
                    ] = (
                        decide_research_requirement(
                            family_assessment
                        )
                    )
                    family_entry[
                        "status"
                    ] = "decided"

                family_decisions.append(
                    family_entry
                )

            entry[
                "product_family_scope_research_decisions"
            ] = family_decisions

        output.append(entry)

    return output


def build_task_research_authority_canary_p4_6d1(
    task_evidence_authority: dict[str, Any] | None,
    shadow_research_decisions: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Promote only task-scoped research decisions behind a parity gate.

    P4.6d1 intentionally does NOT execute research. It establishes a trusted,
    task-scoped decision contract that P4.6d2 can later feed into bounded
    execution. Legacy Phase-C research/reconciliation/synthesis remains
    authoritative until that later gate is separately proven.
    """

    enabled = _enabled()

    contract: dict[str, Any] = {
        "contract_version": _CONTRACT_VERSION,
        "enabled": enabled,
        "eligible": False,
        "authoritative": False,
        "authority_scope": (
            "intent_task_research_decision_only"
        ),
        "task_evidence_authority_required": True,
        "research_execution_authority": False,
        "legacy_phase_c_authority_unchanged": True,
        "public_answer_authority": False,
        "decision_count": 0,
        "research_required_task_count": 0,
        "shadow_parity_checked": False,
        "shadow_parity": None,
        "task_research_decisions": [],
        "reason": None,
    }

    if not enabled:
        contract["reason"] = "disabled"
        return contract

    if not isinstance(
        task_evidence_authority,
        dict,
    ):
        contract["reason"] = (
            "missing_task_evidence_authority"
        )
        return contract

    if (
        task_evidence_authority.get(
            "authoritative"
        )
        is not True
        or task_evidence_authority.get(
            "authority_scope"
        )
        != "intent_task_evidence_assessment_only"
    ):
        contract["reason"] = (
            "task_evidence_authority_not_active"
        )
        return contract

    assessments = task_evidence_authority.get(
        "task_assessments"
    )
    if not isinstance(assessments, list):
        contract["reason"] = (
            "missing_authoritative_task_assessments"
        )
        return contract

    decisions = (
        _derive_from_authoritative_assessments(
            assessments
        )
    )
    contract["decision_count"] = len(
        decisions
    )
    contract[
        "research_required_task_count"
    ] = sum(
        1
        for row in decisions
        if isinstance(row, dict)
        and bool(
            _decision_value(
                row.get(
                    "research_decision"
                ),
                "research_required",
                False,
            )
        )
    )
    contract[
        "task_research_decisions"
    ] = decisions

    shadow_rows = (
        list(shadow_research_decisions)
        if isinstance(
            shadow_research_decisions,
            list,
        )
        else None
    )

    if shadow_rows is not None:
        contract[
            "shadow_parity_checked"
        ] = True

        authoritative_signatures = sorted(
            (
                _decision_signature(row)
                for row in decisions
                if isinstance(row, dict)
            ),
            key=lambda row: str(
                row.get("task_id") or ""
            ),
        )
        shadow_signatures = sorted(
            (
                _decision_signature(row)
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
        "activated_task_research_decision_authority"
    )
    return contract


__all__ = [
    "build_task_research_authority_canary_p4_6d1",
]
