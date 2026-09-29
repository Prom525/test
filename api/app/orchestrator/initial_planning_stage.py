"""Mechanical coordination for the orchestrator's initial planning chain."""

from dataclasses import dataclass
from typing import Any, Callable


__all__ = ("InitialPlanningStageResult", "run_initial_planning_stage")


@dataclass(frozen=True)
class InitialPlanningStageResult:
    plan: Any
    blade_height_filter_boundary: Any


def run_initial_planning_stage(
    question: str,
    conversation_context: Any,
    timings: dict[str, int],
    *,
    original_question: str,
    observability_call: Callable[..., Any],
    understand_query: Callable[..., Any],
    apply_routing_sanity: Callable[[Any], Any],
    assess_blade_height_filter_applicability: Callable[[str, Any], Any],
    assess_research_requirement: Callable[[Any], Any],
    build_execution_plan: Callable[[Any], Any],
) -> Any:
    """Run grounding, then the bounded filter gate, then legacy planning."""
    plan = observability_call(
        timings,
        "understanding",
        understand_query,
        question,
        conversation_context=conversation_context,
    )
    plan = apply_routing_sanity(plan)
    blade_height_filter_boundary = assess_blade_height_filter_applicability(
        original_question,
        plan,
    )
    if blade_height_filter_boundary.short_circuit:
        return InitialPlanningStageResult(plan, blade_height_filter_boundary)
    plan = observability_call(
        timings,
        "research_requirement",
        assess_research_requirement,
        plan,
    )
    plan = observability_call(
        timings,
        "planning",
        build_execution_plan,
        plan,
    )
    return InitialPlanningStageResult(plan, blade_height_filter_boundary)
