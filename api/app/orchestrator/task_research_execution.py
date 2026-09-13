from __future__ import annotations

import json
import os
from typing import Any

from app.orchestrator.research_agent import (
    ResearchCallGuard,
    ResearchToolCall,
    normalize_research_call_guard,
)
from app.orchestrator.research_runtime import _execute_follow_up_call


# PROMATI_P4_6D2_TASK_RESEARCH_EXECUTION_AUTHORITY_CANARY
_TASK_RESEARCH_EXECUTION_AUTHORITY_ENV = (
    "AI_TASK_RESEARCH_EXECUTION_AUTHORITY_CANARY_ENABLED"
)
_CONTRACT_VERSION = (
    "promati.multi_intent."
    "task_research_execution_authority_canary.v1"
)
_MAX_TOTAL_FOLLOW_UP_CALLS = 2


class _DeterministicPlannerResponse:
    def __init__(self, text: str):
        self.text = text


def _enabled() -> bool:
    raw = os.getenv(
        _TASK_RESEARCH_EXECUTION_AUTHORITY_ENV,
        "true",
    )
    return str(raw).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _value(value: Any) -> Any:
    return getattr(value, "value", value)


def _task_domain(task: Any) -> str | None:
    raw = _value(getattr(task, "domain", None))
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _step_domain(step: Any) -> str | None:
    raw = _value(getattr(step, "domain", None))
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _step_family_code(step: Any) -> str | None:
    params = getattr(step, "params", None)
    if not isinstance(params, dict):
        return None
    raw = params.get("family_code")
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _result_domain(item: Any) -> str | None:
    if not isinstance(item, dict):
        return None
    raw = _value(item.get("domain"))
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _result_family_code(item: Any) -> str | None:
    if not isinstance(item, dict):
        return None

    result = item.get("result")
    if not isinstance(result, dict):
        return None

    raw = result.get("detected_family_code")
    if raw is not None and str(raw).strip():
        return str(raw).strip()

    family_context = result.get("family_context")
    if isinstance(family_context, dict):
        raw = family_context.get("detected_family_code")
        if raw is not None and str(raw).strip():
            return str(raw).strip()

        rows = family_context.get("results")
        if (
            isinstance(rows, list)
            and rows
            and isinstance(rows[0], dict)
        ):
            raw = rows[0].get("family_code")
            if raw is not None and str(raw).strip():
                return str(raw).strip()

    return None


def _select_steps(
    plan: Any,
    task: Any,
    *,
    family_code: str | None,
) -> tuple[Any, ...]:
    domain = _task_domain(task)
    family_key = (
        str(family_code).casefold()
        if family_code
        else None
    )

    output = []
    for step in tuple(
        getattr(plan, "execution_steps", None) or ()
    ):
        if _step_domain(step) != domain:
            continue
        if family_key is not None:
            step_family = _step_family_code(step)
            if (
                step_family is None
                or step_family.casefold()
                != family_key
            ):
                continue
        output.append(step)
    return tuple(output)


def _select_results(
    task: Any,
    results: list[dict[str, Any]],
    *,
    family_code: str | None,
) -> tuple[dict[str, Any], ...]:
    domain = _task_domain(task)
    family_key = (
        str(family_code).casefold()
        if family_code
        else None
    )

    output = []
    for item in list(results or []):
        if not isinstance(item, dict):
            continue
        if _result_domain(item) != domain:
            continue
        if family_key is not None:
            result_family = _result_family_code(item)
            if (
                result_family is None
                or result_family.casefold()
                != family_key
            ):
                continue
        output.append(item)
    return tuple(output)


def _copy_step(step: Any) -> Any:
    if hasattr(step, "model_copy"):
        return step.model_copy(deep=True)
    return step.copy(deep=True)


def _project_plan(
    plan: Any,
    task: Any,
    *,
    family_code: str | None,
    task_question: str,
) -> Any:
    if hasattr(plan, "model_copy"):
        projected = plan.model_copy(deep=True)
    else:
        projected = plan.copy(deep=True)

    domain = getattr(task, "domain", None)
    selected_steps = _select_steps(
        plan,
        task,
        family_code=family_code,
    )

    cleaned_question = " ".join(
        str(task_question or "").split()
    ).strip()
    if cleaned_question:
        projected.original_question = cleaned_question
        projected.normalized_question = (
            cleaned_question.casefold()
        )

    projected.primary_domain = domain
    projected.domains = (
        [domain] if domain is not None else []
    )
    projected.intent = str(
        getattr(task, "intent", "") or ""
    )
    projected.intent_tasks = []
    projected.requested_information = list(
        getattr(
            task,
            "requested_information",
            None,
        )
        or []
    )
    projected.entities = {}
    projected.product_families = (
        [family_code]
        if family_code
        else []
    )
    projected.residual_terms = []
    projected.multi_intent = False
    projected.research_required = True
    projected.execution_blockers = []
    projected.clarification_required = False
    projected.clarification_question = None
    projected.execution_steps = [
        _copy_step(step)
        for step in selected_steps
    ]
    return projected


def _guard_from_entry(
    guard_entry: dict[str, Any],
) -> ResearchCallGuard:
    return normalize_research_call_guard(
        ResearchCallGuard(
            allowed_action=str(
                guard_entry.get(
                    "allowed_research_action"
                )
                or ""
            ).strip(),
            pinned_params=dict(
                guard_entry.get(
                    "pinned_params"
                )
                or {}
            ),
            target_requirement_ids=tuple(
                str(item).strip()
                for item in list(
                    guard_entry.get(
                        "target_requirement_ids"
                    )
                    or []
                )
                if str(item).strip()
            ),
            max_follow_up_calls=1,
        )
    )


def _planner(
    *,
    action: str,
    params: dict[str, Any],
    target_requirement_ids: list[str],
):
    state = {"calls": 0}

    def _plan(_request):
        state["calls"] += 1

        if state["calls"] > 1:
            payload = {
                "decision": "synthesize",
                "reason": (
                    "P4.6d2 bounded task research "
                    "follow-up complete."
                ),
                "gaps": [],
                "calls": [],
            }
        else:
            payload = {
                "decision": "follow_up",
                "reason": (
                    "P4.6d2 authoritative "
                    "task-scoped evidence gap."
                ),
                "gaps": list(
                    target_requirement_ids
                ),
                "calls": [
                    {
                        "action": action,
                        "reason": (
                            "Vul uitsluitend deze "
                            "task-scoped evidence-gap."
                        ),
                        "params": dict(params),
                    }
                ],
            }

        return _DeterministicPlannerResponse(
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
            )
        )

    return _plan


def _synthesizer(
    _plan: Any,
    combined_results: list[dict[str, Any]],
) -> dict[str, Any]:
    follow_up_count = 0
    for item in list(combined_results or []):
        if (
            isinstance(item, dict)
            and isinstance(
                item.get("research_follow_up"),
                dict,
            )
        ):
            follow_up_count += 1

    return {
        "status": "task_research_execution_observed",
        "answer": None,
        "ai_calls_used": 0,
        "combined_result_count": len(
            list(combined_results or [])
        ),
        "follow_up_result_count": (
            follow_up_count
        ),
    }


def _execution_units(
    contexts: list[dict[str, Any]],
    guards: list[dict[str, Any]],
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    guards_by_task = {
        row.get("task_id"): row
        for row in list(guards or [])
        if isinstance(row, dict)
        and row.get("task_id")
    }

    units = []

    for context in list(contexts or []):
        if not isinstance(context, dict):
            continue

        task_id = context.get("task_id")
        guard = guards_by_task.get(task_id)
        if not isinstance(guard, dict):
            continue

        family_contexts = context.get(
            "product_family_scope_contexts"
        )
        family_guards = guard.get(
            "product_family_scope_guards"
        )

        if (
            isinstance(family_contexts, list)
            and family_contexts
            and isinstance(family_guards, list)
            and family_guards
        ):
            family_guards_by_code = {
                str(
                    row.get("family_code") or ""
                ).casefold(): row
                for row in family_guards
                if isinstance(row, dict)
                and row.get("family_code")
            }

            for family_context in family_contexts:
                if not isinstance(
                    family_context,
                    dict,
                ):
                    continue
                family_code = str(
                    family_context.get(
                        "family_code"
                    )
                    or ""
                ).strip()
                if not family_code:
                    continue
                family_guard = (
                    family_guards_by_code.get(
                        family_code.casefold()
                    )
                )
                if isinstance(
                    family_guard,
                    dict,
                ):
                    units.append(
                        (
                            family_context,
                            family_guard,
                        )
                    )
            continue

        units.append((context, guard))

    return units


def run_task_research_execution_authority_canary_p4_6d2(
    plan: Any,
    results: list[dict[str, Any]],
    task_research_authority: dict[str, Any] | None,
    task_research_contexts: list[dict[str, Any]],
    task_research_call_guards: list[dict[str, Any]],
    *,
    sender,
    evidence_observer=None,
    task_research_semantics_cp13: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute bounded task research only inside the isolated task contract.

    P4.6d2 does not append follow-up results to legacy results, does not alter
    legacy Phase-C evidence/reconciliation/synthesis, and does not replace the
    public answer. Those later authority transfers remain separate gates.
    """

    enabled = _enabled()
    contract: dict[str, Any] = {
        "contract_version": _CONTRACT_VERSION,
        "enabled": enabled,
        "eligible": False,
        "authoritative": False,
        "authority_scope": (
            "intent_task_research_execution_only"
        ),
        "task_research_decision_authority_required": True,
        "decision_shadow_parity_required": True,
        "legacy_phase_c_authority_unchanged": True,
        "evidence_reconciliation_authority": False,
        "public_answer_authority": False,
        "max_total_follow_up_calls": (
            _MAX_TOTAL_FOLLOW_UP_CALLS
        ),
        "execution_unit_count": 0,
        "executed_unit_count": 0,
        "follow_up_specialist_call_count": 0,
        "accepted_follow_up_result_count": 0,
        "executions": [],
        "reason": None,
    }

    if not enabled:
        contract["reason"] = "disabled"
        return contract

    if not isinstance(
        task_research_authority,
        dict,
    ):
        contract["reason"] = (
            "missing_task_research_decision_authority"
        )
        return contract

    if (
        task_research_authority.get(
            "authoritative"
        )
        is not True
        or task_research_authority.get(
            "authority_scope"
        )
        != "intent_task_research_decision_only"
    ):
        contract["reason"] = (
            "task_research_decision_authority_not_active"
        )
        return contract

    if (
        task_research_authority.get(
            "shadow_parity"
        )
        is not True
    ):
        contract["reason"] = (
            "decision_shadow_parity_not_proven"
        )
        return contract

    tasks_by_id = {
        getattr(task, "task_id", None): task
        for task in list(
            getattr(
                plan,
                "intent_tasks",
                None,
            )
            or []
        )
        if getattr(
            task,
            "task_id",
            None,
        )
    }

    allowed_task_ids = {
        str(item)
        for item in list(
            (task_research_semantics_cp13 or {}).get("allowed_task_ids") or []
        )
    }
    if not isinstance(task_research_semantics_cp13, dict):
        contract["reason"] = "missing_task_research_semantics_cp13"
        return contract
    if task_research_semantics_cp13.get("authority_scope") != (
        "intent_task_research_eligibility_only"
    ):
        contract["reason"] = "invalid_task_research_semantics_cp13"
        return contract

    raw_units = _execution_units(
        task_research_contexts,
        task_research_call_guards,
    )

    eligible_units = []
    for context, guard_entry in raw_units:
        if (
            context.get("research_required")
            is not True
        ):
            continue
        context_precondition = str(
            context.get("runtime_precondition") or ""
        )
        guard_precondition = str(
            guard_entry.get("runtime_precondition") or ""
        )
        allowed_gap_preconditions = {
            "ready",
            "blocked_no_accepted_initial_results",
        }
        if context_precondition not in allowed_gap_preconditions:
            continue
        if guard_precondition not in allowed_gap_preconditions:
            continue
        guard_status = str(
            guard_entry.get("status") or ""
        )
        if (
            guard_status != "projected"
            and not (
                guard_status == "blocked"
                and guard_precondition
                == "blocked_no_accepted_initial_results"
            )
        ):
            continue
        if int(
            guard_entry.get(
                "max_follow_up_calls"
            )
            or 0
        ) != 1:
            continue

        task_id = context.get("task_id")
        if task_id not in tasks_by_id:
            continue
        if str(task_id) not in allowed_task_ids:
            continue

        eligible_units.append(
            (context, guard_entry)
        )

    if not eligible_units:
        contract["reason"] = (
            "no_eligible_research_execution_units"
        )
        return contract

    if (
        len(eligible_units)
        > _MAX_TOTAL_FOLLOW_UP_CALLS
    ):
        eligible_units = eligible_units[
            :_MAX_TOTAL_FOLLOW_UP_CALLS
        ]

    contract["eligible"] = True
    contract["execution_unit_count"] = len(
        eligible_units
    )

    executions = []

    for context, guard_entry in eligible_units:
        task_id = context.get("task_id")
        task = tasks_by_id[task_id]
        family_code = context.get(
            "family_code"
        )
        if family_code is not None:
            family_code = str(
                family_code
            ).strip() or None

        selected_results = _select_results(
            task,
            results,
            family_code=family_code,
        )
        accepted_initial_results = [
            item
            for item in selected_results
            if isinstance(item, dict)
            and item.get("accepted") is True
        ]

        execution = {
            "task_id": task_id,
            "domain": _task_domain(task),
            "family_code": family_code,
            "executed": False,
            "accepted_initial_result_count": len(
                accepted_initial_results
            ),
            "accepted_follow_up_result_count": 0,
            "status": None,
        }

        # P4.6d2 authority is specifically allowed to fill a proven evidence gap.
        # An empty accepted-initial-result set must therefore not block the
        # guarded follow-up. The upstream P4.6c/P4.6d1 authority + shadow parity
        # and the V7 ResearchCallGuard remain the execution preconditions.
        guard = _guard_from_entry(
            guard_entry
        )
        selected_steps = _select_steps(
            plan,
            task,
            family_code=family_code,
        )
        if not selected_steps:
            execution["status"] = (
                "blocked_no_task_execution_step"
            )
            executions.append(execution)
            continue

        base_params = dict(
            getattr(
                selected_steps[0],
                "params",
                {},
            )
            or {}
        )
        task_question = (
            "Vul uitsluitend de ontbrekende "
            "evidence voor deze taak aan. "
            + str(
                getattr(
                    plan,
                    "original_question",
                    "",
                )
                or ""
            ).strip()
        )
        if family_code:
            task_question += (
                f" Productfamilie: {family_code}."
            )

        base_params["vraag"] = task_question
        for key, value in dict(
            guard.pinned_params or {}
        ).items():
            base_params[key] = value

        projected_plan = _project_plan(
            plan,
            task,
            family_code=family_code,
            task_question=task_question,
        )

        # P4.6d1 already made the research decision authoritative and the V7
        # ResearchCallGuard already pins the only allowed task/family action.
        # The generic research planner refuses to plan without accepted initial
        # evidence, which is exactly the gap P4.6d2 is authorized to fill.
        # Execute the single guarded follow-up directly through the existing
        # research runtime helper; that helper re-enforces the guard immediately
        # before execute_plan.
        typed_results = []
        try:
            follow_results = _execute_follow_up_call(
                projected_plan,
                ResearchToolCall(
                    action=guard.allowed_action,
                    reason=(
                        "P4.6d2 authoritative task-scoped "
                        "evidence-gap follow-up."
                    ),
                    params=dict(base_params),
                ),
                round_number=1,
                call_number=1,
                sender=sender,
                call_guard=guard,
                shadow_observer=typed_results.append,
            )
        except Exception as exc:
            execution["status"] = (
                "execution_error"
            )
            execution["error_type"] = (
                type(exc).__name__
            )
            executions.append(execution)
            continue

        # _execute_follow_up_call returns the authoritative legacy-compatible
        # result envelope from execute_plan, where acceptance is the explicit
        # boolean "accepted" field. The typed ExecutionResult observer uses
        # "legacy_accepted" rather than an "accepted" attribute, so counting
        # getattr(item, "accepted") would incorrectly report zero.
        accepted_follow_up = sum(
            1
            for item in list(follow_results or [])
            if isinstance(item, dict)
            and item.get("accepted") is True
        )
        follow_up_calls = 1 if follow_results is not None else 0

        # PROMATI_P4_6E1_TASK_RESEARCH_EVIDENCE_AUTHORITY_CANARY
        # Internal typed-result handoff only. Raw evidence is not copied into the
        # public P4.6d2 metadata contract or observability counters.
        if evidence_observer is not None and typed_results:
            try:
                evidence_observer(
                    {
                        "task_id": task_id,
                        "family_code": family_code,
                        "execution_results": tuple(typed_results),
                    }
                )
            except Exception:
                pass

        execution.update(
            {
                "executed": (
                    follow_up_calls > 0
                ),
                "accepted_follow_up_result_count": (
                    accepted_follow_up
                ),
                "follow_up_specialist_call_count": (
                    follow_up_calls
                ),
                "status": (
                    "executed_authoritative_task_research"
                    if follow_up_calls > 0
                    else "completed_without_follow_up"
                ),
            }
        )
        executions.append(execution)

    contract["executions"] = executions
    contract["executed_unit_count"] = sum(
        1
        for row in executions
        if row.get("executed") is True
    )
    contract[
        "follow_up_specialist_call_count"
    ] = sum(
        int(
            row.get(
                "follow_up_specialist_call_count"
            )
            or 0
        )
        for row in executions
    )
    contract[
        "accepted_follow_up_result_count"
    ] = sum(
        int(
            row.get(
                "accepted_follow_up_result_count"
            )
            or 0
        )
        for row in executions
    )

    contract["authoritative"] = True
    contract["reason"] = (
        "activated_task_research_execution_authority"
    )
    return contract


__all__ = [
    "run_task_research_execution_authority_canary_p4_6d2",
]
