"""Mechanical coordination for the orchestrator's initial planning chain."""

from typing import Any, Callable


__all__ = ("run_initial_planning_stage",)


def run_initial_planning_stage(
    question: str,
    conversation_context: Any,
    timings: dict[str, int],
    *,
    observability_call: Callable[..., Any],
    understand_query: Callable[..., Any],
    apply_routing_sanity: Callable[[Any], Any],
    assess_research_requirement: Callable[[Any], Any],
    build_execution_plan: Callable[[Any], Any],
) -> Any:
    """Run the existing understanding, sanity, assessment and planning chain."""
    plan = observability_call(
        timings,
        "understanding",
        understand_query,
        question,
        conversation_context=conversation_context,
    )
    plan = apply_routing_sanity(plan)
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
    return plan
