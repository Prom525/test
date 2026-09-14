"""Initial shadow planning and authoritative legacy execution stage."""

from dataclasses import dataclass
from typing import Any, Callable


__all__ = ["InitialExecutionStageResult", "run_initial_execution_stage"]


@dataclass(frozen=True)
class InitialExecutionStageResult:
    plan: Any
    task_execution_plans_shadow: Any
    task_execution_plan_comparison_shadow: Any
    task_execution_canary_p4_6b: Any
    typed_execution_results: list[Any]
    results: Any
    trace: Any
    task_execution_shadow: Any
    task_planner_canary: Any


def run_initial_execution_stage(
    plan: Any,
    timings: dict[str, int],
    *,
    sender: Any,
    attach_requirements: Callable[..., Any],
    build_task_execution_plans_shadow: Callable[..., Any],
    compare_task_execution_plans_shadow: Callable[..., Any],
    run_task_execution_canary: Callable[..., Any],
    observability_call: Callable[..., Any],
    execute_plan: Callable[..., Any],
    build_task_execution_shadow: Callable[..., Any],
    build_task_planner_canary: Callable[..., Any],
) -> InitialExecutionStageResult:
    """Run the characterized initial execution boundary without policy changes."""
    plan = attach_requirements(plan)

    task_execution_plans_shadow = ()
    task_execution_plan_comparison_shadow = None
    try:
        task_execution_plans_shadow = build_task_execution_plans_shadow(plan)
        task_execution_plan_comparison_shadow = (
            compare_task_execution_plans_shadow(
                plan,
                task_execution_plans_shadow,
            )
        )
    except Exception:
        task_execution_plans_shadow = ()
        task_execution_plan_comparison_shadow = None

    task_execution_canary_p4_6b = None
    try:
        task_execution_canary_p4_6b = run_task_execution_canary(
            plan,
            task_execution_plans_shadow,
            sender=sender,
        )
    except Exception:
        task_execution_canary_p4_6b = None

    typed_execution_results: list[Any] = []

    results, trace = observability_call(
        timings,
        "initial_specialist",
        execute_plan,
        plan,
        sender=sender,
        shadow_observer=typed_execution_results.append,
    )

    task_execution_shadow = None
    try:
        task_execution_shadow = build_task_execution_shadow(plan, trace)
    except Exception:
        task_execution_shadow = None

    task_planner_canary = None
    try:
        task_planner_canary = build_task_planner_canary(plan)
    except Exception:
        task_planner_canary = None

    return InitialExecutionStageResult(
        plan=plan,
        task_execution_plans_shadow=task_execution_plans_shadow,
        task_execution_plan_comparison_shadow=(
            task_execution_plan_comparison_shadow
        ),
        task_execution_canary_p4_6b=task_execution_canary_p4_6b,
        typed_execution_results=typed_execution_results,
        results=results,
        trace=trace,
        task_execution_shadow=task_execution_shadow,
        task_planner_canary=task_planner_canary,
    )
