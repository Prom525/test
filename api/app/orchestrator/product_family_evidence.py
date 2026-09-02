
from __future__ import annotations

import re
from copy import deepcopy
from datetime import datetime
from typing import Any, Callable

from app.orchestrator.evidence_assessor import (
    RequirementAssessmentStatus,
    assess_evidence,
)
from app.orchestrator.evidence_contracts import (
    EvidenceItem,
)
from app.orchestrator.evidence_requirements import (
    EvidenceRequirementSet,
)
from app.orchestrator.execution_contracts import (
    ExecutionResult,
)
from app.orchestrator.executor import (
    Sender,
    execute_plan,
)
from app.orchestrator.models import (
    ExecutionStep,
    QueryPlan,
)
from app.orchestrator.research_agent import (
    MAX_FOLLOW_UP_CALLS_PER_ROUND,
    MAX_TOTAL_SPECIALIST_CALLS,
)


# PROMATI_PRODUCT_FAMILY_EVIDENCE_P4_5B4
PRODUCT_FAMILY_EVIDENCE_CONTRACT_VERSION = (
    "promati.orchestrator.product_family_evidence.v2"
)

PRODUCT_LOOKUP_REQUIREMENT_SET_ID = (
    "product_lookup.v1"
)

PRODUCT_RECORD_REQUIREMENT_ID = (
    "PRODUCT_RECORD"
)


def _value(
    value: Any,
) -> str:

    return str(
        getattr(
            value,
            "value",
            value,
        )
        or ""
    ).strip()


def _ordered_family_codes(
    plan: Any,
) -> tuple[str, ...]:

    output: list[str] = []
    seen: set[str] = set()

    for item in (
        getattr(
            plan,
            "product_families",
            None,
        )
        or []
    ):
        code = _value(
            getattr(
                item,
                "value",
                item,
            )
        )

        if not code:
            continue

        key = code.casefold()

        if key in seen:
            continue

        seen.add(key)
        output.append(code)

    return tuple(output)


def _product_requirement_row(
    assessment: Any,
) -> Any | None:

    for item in (
        getattr(
            assessment,
            "requirement_results",
            None,
        )
        or ()
    ):
        if (
            str(
                getattr(
                    item,
                    "requirement_id",
                    "",
                )
            )
            == PRODUCT_RECORD_REQUIREMENT_ID
        ):
            return item

    return None


def assess_product_family_coverage(
    requirement_set: EvidenceRequirementSet,
    evidence_items: tuple[EvidenceItem, ...],
    plan: Any,
    *,
    now: datetime,
) -> dict[str, Any]:
    """Assess every required product requirement for every explicit family."""
    family_codes = _ordered_family_codes(plan)
    requirement_set_id = str(
        getattr(requirement_set, "requirement_set_id", "") or ""
    )
    required_ids_by_set = {
        "product_lookup.v1": ("PRODUCT_RECORD",),
        "price_stock.v1": ("CURRENT_PRICE", "CURRENT_STOCK"),
    }
    required_ids = required_ids_by_set.get(requirement_set_id, ())
    applicable = bool(required_ids) and len(family_codes) >= 2
    if not applicable:
        return {
            "contract_version": PRODUCT_FAMILY_EVIDENCE_CONTRACT_VERSION,
            "applicable": False,
            "requirement_set_id": requirement_set_id,
            "required_requirement_ids": list(required_ids),
            "family_codes": list(family_codes),
            "families": [],
            "missing_family_codes": [],
            "all_satisfied": None,
        }

    rows = []
    missing = []
    for family_code in family_codes:
        assessment = assess_evidence(
            requirement_set,
            tuple(evidence_items),
            target_entity_ids={"product": family_code},
            now=now,
        )
        by_id = {
            str(getattr(item, "requirement_id", "")): item
            for item in (getattr(assessment, "requirement_results", None) or ())
        }
        requirement_rows = []
        family_satisfied = True
        for requirement_id in required_ids:
            item = by_id.get(requirement_id)
            status_value = _value(getattr(item, "status", None)).lower()
            satisfied = status_value == RequirementAssessmentStatus.SATISFIED.value
            family_satisfied = family_satisfied and satisfied
            requirement_rows.append({
                "requirement_id": requirement_id,
                "status": status_value or "missing",
                "satisfied": satisfied,
                "matched_evidence_ids": list(
                    getattr(item, "matched_evidence_ids", ()) or ()
                ),
                "reasons": list(getattr(item, "reasons", ()) or ()),
            })
        if not family_satisfied:
            missing.append(family_code)
        rows.append({
            "family_code": family_code,
            "status": "satisfied" if family_satisfied else "missing",
            "satisfied": family_satisfied,
            "requirements": requirement_rows,
            "matched_evidence_ids": sorted({
                evidence_id
                for row in requirement_rows
                for evidence_id in row["matched_evidence_ids"]
            }),
            "reasons": sorted({
                reason
                for row in requirement_rows
                for reason in row["reasons"]
            }),
        })
    return {
        "contract_version": PRODUCT_FAMILY_EVIDENCE_CONTRACT_VERSION,
        "applicable": True,
        "requirement_set_id": requirement_set_id,
        "required_requirement_ids": list(required_ids),
        "family_codes": list(family_codes),
        "families": rows,
        "missing_family_codes": missing,
        "all_satisfied": not missing,
    }


def _copy_plan(
    plan: QueryPlan,
) -> QueryPlan:

    if hasattr(
        plan,
        "model_copy",
    ):
        return plan.model_copy(
            deep=True
        )

    return plan.copy(
        deep=True
    )


def _copy_step(
    step: ExecutionStep,
    *,
    step_id: str,
) -> ExecutionStep:

    update = {
        "step_id":
            step_id,

        "fallback_allowed":
            False,
    }

    if hasattr(
        step,
        "model_copy",
    ):
        return step.model_copy(
            deep=True,
            update=update,
        )

    return step.copy(
        deep=True,
        update=update,
    )


def _matching_product_step(
    plan: QueryPlan,
    family_code: str,
) -> ExecutionStep | None:

    target = (
        family_code.casefold()
    )

    for step in (
        plan.execution_steps
        or []
    ):
        if (
            step.action
            != "product_assistant"
        ):
            continue

        step_family = str(
            (
                step.params
                or {}
            ).get(
                "family_code",
                "",
            )
            or ""
        ).strip()

        if (
            step_family.casefold()
            == target
        ):
            return step

    return None


def recover_missing_product_families(
    plan: QueryPlan,
    missing_family_codes: tuple[
        str,
        ...,
    ],
    *,
    sender: Sender | None = None,
    shadow_observer: Callable[
        [ExecutionResult],
        None,
    ] | None = None,
) -> tuple[
    list[dict[str, Any]],
    dict[str, Any],
]:
    """
    Deterministic, read-only product retrieval recovery.

    Important:
    - only product_assistant;
    - only families already present in the planned fan-out;
    - original planned params are reused;
    - no AI planner;
    - no SQL;
    - no writes;
    - existing research hard budgets are reused.
    """

    ordered_missing: list[str] = []
    seen: set[str] = set()

    for raw_code in (
        missing_family_codes
        or ()
    ):
        code = str(
            raw_code
            or ""
        ).strip()

        if not code:
            continue

        key = code.casefold()

        if key in seen:
            continue

        seen.add(key)
        ordered_missing.append(
            code
        )

    initial_specialist_calls = len(
        plan.execution_steps
        or []
    )

    remaining_hard_budget = max(
        0,
        MAX_TOTAL_SPECIALIST_CALLS
        - initial_specialist_calls,
    )

    max_recovery_calls = min(
        MAX_FOLLOW_UP_CALLS_PER_ROUND,
        remaining_hard_budget,
    )

    attempted: list[str] = []
    skipped_budget: list[str] = []
    skipped_no_step: list[str] = []

    raw_results: list[
        dict[str, Any]
    ] = []

    accepted_result_count = 0

    for family_code in ordered_missing:

        if (
            len(attempted)
            >= max_recovery_calls
        ):
            skipped_budget.append(
                family_code
            )
            continue

        source_step = (
            _matching_product_step(
                plan,
                family_code,
            )
        )

        if source_step is None:
            skipped_no_step.append(
                family_code
            )
            continue

        safe_code = re.sub(
            r"[^A-Za-z0-9_-]+",
            "-",
            family_code,
        )

        follow_plan = _copy_plan(
            plan
        )

        follow_plan.clarification_required = (
            False
        )

        follow_plan.clarification_question = (
            None
        )

        follow_plan.execution_steps = [
            _copy_step(
                source_step,
                step_id=(
                    "product_family_recovery_"
                    + str(
                        len(attempted)
                        + 1
                    )
                    + "_"
                    + safe_code
                ),
            )
        ]

        result_items, _trace = (
            execute_plan(
                follow_plan,
                sender=sender,
                shadow_observer=(
                    shadow_observer
                ),
            )
        )

        attempted.append(
            family_code
        )

        for item in (
            result_items
            or []
        ):
            if not isinstance(
                item,
                dict,
            ):
                continue

            copied = deepcopy(
                item
            )

            copied[
                "product_family_recovery"
            ] = {
                "family_code":
                    family_code,

                "reason":
                    "missing_product_record",
            }

            if (
                copied.get(
                    "accepted"
                )
                is True
            ):
                accepted_result_count += 1

            raw_results.append(
                copied
            )

    metadata = {
        "contract_version":
            PRODUCT_FAMILY_EVIDENCE_CONTRACT_VERSION,

        "performed":
            bool(
                attempted
            ),

        "requested_family_codes":
            ordered_missing,

        "attempted_family_codes":
            attempted,

        "attempted_call_count":
            len(
                attempted
            ),

        "accepted_result_count":
            accepted_result_count,

        "skipped_budget_family_codes":
            skipped_budget,

        "skipped_missing_step_family_codes":
            skipped_no_step,

        "initial_specialist_calls":
            initial_specialist_calls,

        "max_total_specialist_calls":
            MAX_TOTAL_SPECIALIST_CALLS,

        "max_follow_up_calls":
            MAX_FOLLOW_UP_CALLS_PER_ROUND,

        "remaining_hard_budget_before_recovery":
            remaining_hard_budget,
    }

    return (
        raw_results,
        metadata,
    )
