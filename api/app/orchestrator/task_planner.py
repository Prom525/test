from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from app.orchestrator.models import Domain, ExecutionStep, IntentTask, QueryPlan
from app.orchestrator.planner import build_execution_plan

TASK_EXECUTION_PLAN_SHADOW_CONTRACT_VERSION = (
    "promati.multi_intent.task_execution_plan_shadow.v1"
)
TASK_EXECUTION_PLAN_COMPARISON_SHADOW_CONTRACT_VERSION = (
    "promati.multi_intent.task_execution_plan_comparison_shadow.v1"
)


@dataclass(frozen=True)
class TaskExecutionPlanShadow:
    contract_version: str
    task_id: str
    domain: str
    intent: str
    primary: bool
    status: str
    execution_steps: tuple[ExecutionStep, ...]
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class TaskExecutionPlanComparison:
    contract_version: str
    applicable: bool
    task_count: int
    task_step_count: int
    legacy_step_count: int
    equivalent_actions: bool
    exact_steps_equivalent: bool
    planning_error_count: int
    task_plans: tuple[TaskExecutionPlanShadow, ...]
    reasons: tuple[str, ...]


def _domain_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "").strip()


def _copy_model(value: Any) -> Any:
    if hasattr(value, "model_copy"):
        return value.model_copy(deep=True)
    if hasattr(value, "copy"):
        return value.copy(deep=True)
    return deepcopy(value)


def _task_family_codes(task: IntentTask) -> tuple[str, ...]:
    scope = getattr(task, "scope", None)
    if not isinstance(scope, dict):
        return ()
    raw = scope.get("product_family_codes")
    if not isinstance(raw, (list, tuple)):
        return ()
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        text = str(item or "").strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return tuple(out)


def _project_task_plan(source_plan: QueryPlan, task: IntentTask) -> QueryPlan:
    projected = _copy_model(source_plan)
    projected.primary_domain = task.domain
    projected.domains = [task.domain]
    projected.intent = str(task.intent or "")
    projected.intent_tasks = []
    projected.requested_information = list(task.requested_information or [])
    projected.multi_intent = False
    projected.research_required = False
    projected.execution_blockers = []
    projected.clarification_required = False
    projected.clarification_question = None
    projected.execution_steps = []
    return projected


def _apply_task_scope(projected: QueryPlan, source_plan: QueryPlan, task: IntentTask) -> None:
    if task.domain != Domain.PRODUCT:
        return
    requested_codes = {code.casefold() for code in _task_family_codes(task)}
    if not requested_codes:
        return
    projected.product_families = [
        _copy_model(item)
        for item in (source_plan.product_families or [])
        if str(getattr(item, "value", "") or "").strip().casefold()
        in requested_codes
    ]


def _scope_step_id(task_id: str, step: ExecutionStep) -> ExecutionStep:
    new_id = f"{task_id}::{step.step_id}"
    if hasattr(step, "model_copy"):
        return step.model_copy(deep=True, update={"step_id": new_id})
    return step.copy(deep=True, update={"step_id": new_id})


def _step_signature(step: ExecutionStep) -> tuple[str, str, tuple[tuple[str, str], ...]]:
    params = tuple(
        sorted(
            (str(key), repr(value))
            for key, value in dict(step.params or {}).items()
        )
    )
    return (_domain_value(step.domain), str(step.action), params)


def _action_signature(step: ExecutionStep) -> tuple[str, str]:
    return (_domain_value(step.domain), str(step.action))


def build_task_execution_plans_shadow(
    plan: QueryPlan,
) -> tuple[TaskExecutionPlanShadow, ...]:
    tasks = list(getattr(plan, "intent_tasks", None) or [])
    if not bool(getattr(plan, "multi_intent", False)) or len(tasks) < 2:
        return ()

    output: list[TaskExecutionPlanShadow] = []
    for task in tasks:
        task_id = str(getattr(task, "task_id", "") or "").strip()
        domain = _domain_value(getattr(task, "domain", None))
        intent = str(getattr(task, "intent", "") or "").strip()
        primary = bool(getattr(task, "primary", False))
        if not task_id or not domain or not intent:
            output.append(
                TaskExecutionPlanShadow(
                    contract_version=TASK_EXECUTION_PLAN_SHADOW_CONTRACT_VERSION,
                    task_id=task_id or "unknown_task",
                    domain=domain,
                    intent=intent,
                    primary=primary,
                    status="planning_error",
                    execution_steps=(),
                    reasons=("invalid_task_contract",),
                )
            )
            continue

        try:
            projected = _project_task_plan(plan, task)
            _apply_task_scope(projected, plan, task)
            projected = build_execution_plan(projected)
            scoped_steps = tuple(
                _scope_step_id(task_id, step)
                for step in (projected.execution_steps or [])
            )
            output.append(
                TaskExecutionPlanShadow(
                    contract_version=TASK_EXECUTION_PLAN_SHADOW_CONTRACT_VERSION,
                    task_id=task_id,
                    domain=domain,
                    intent=intent,
                    primary=primary,
                    status="planned" if scoped_steps else "no_steps",
                    execution_steps=scoped_steps,
                    reasons=(),
                )
            )
        except Exception as exc:
            output.append(
                TaskExecutionPlanShadow(
                    contract_version=TASK_EXECUTION_PLAN_SHADOW_CONTRACT_VERSION,
                    task_id=task_id,
                    domain=domain,
                    intent=intent,
                    primary=primary,
                    status="planning_error",
                    execution_steps=(),
                    reasons=(type(exc).__name__,),
                )
            )

    return tuple(output)


def compare_task_execution_plans_shadow(
    plan: QueryPlan,
    task_plans: tuple[TaskExecutionPlanShadow, ...] | list[TaskExecutionPlanShadow],
) -> TaskExecutionPlanComparison:
    plans = tuple(task_plans or ())
    applicable = bool(getattr(plan, "multi_intent", False)) and len(plans) >= 2
    task_steps = tuple(
        step
        for task_plan in plans
        for step in (task_plan.execution_steps or ())
    )
    legacy_steps = tuple(getattr(plan, "execution_steps", None) or ())
    planning_error_count = sum(1 for item in plans if item.status == "planning_error")

    task_actions = sorted(_action_signature(step) for step in task_steps)
    legacy_actions = sorted(_action_signature(step) for step in legacy_steps)
    task_exact = sorted(_step_signature(step) for step in task_steps)
    legacy_exact = sorted(_step_signature(step) for step in legacy_steps)

    reasons: list[str] = []
    if not applicable:
        reasons.append("not_applicable")
    if planning_error_count:
        reasons.append("planning_errors_present")
    if applicable and task_actions != legacy_actions:
        reasons.append("action_set_differs_from_legacy")
    if applicable and task_exact != legacy_exact:
        reasons.append("step_contract_differs_from_legacy")

    return TaskExecutionPlanComparison(
        contract_version=TASK_EXECUTION_PLAN_COMPARISON_SHADOW_CONTRACT_VERSION,
        applicable=applicable,
        task_count=len(plans),
        task_step_count=len(task_steps),
        legacy_step_count=len(legacy_steps),
        equivalent_actions=(task_actions == legacy_actions) if applicable else False,
        exact_steps_equivalent=(task_exact == legacy_exact) if applicable else False,
        planning_error_count=planning_error_count,
        task_plans=plans,
        reasons=tuple(reasons),
    )
