from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class PhaseCBoundedResearchStageResult:
    research_execution: Any


def run_phase_c_bounded_research_stage(
    timings: Any,
    counts: Any,
    research_decision: Any,
    plan: Any,
    results: Any,
    sender: Any,
    *,
    _observability_call: Callable[..., Any],
    _observability_get: Callable[..., Any],
    _observability_nonnegative_int: Callable[..., Any],
    execute_bounded_research: Callable[..., Any],
) -> PhaseCBoundedResearchStageResult:
    research_execution = _observability_call(
        timings,
        "evidence_research",
        execute_bounded_research,
        research_decision,
        plan,
        list(results),
        sender=sender,
    )
    metadata = _observability_get(
        research_execution,
        "agent_metadata",
        None,
    )
    if isinstance(metadata, dict):
        counts[
            "phase_c_research_follow_up_specialist_calls"
        ] += _observability_nonnegative_int(
            metadata.get("follow_up_specialist_calls")
        )
        counts[
            "phase_c_ai_calls"
        ] = _observability_nonnegative_int(
            metadata.get("total_ai_calls_used")
        )
    return PhaseCBoundedResearchStageResult(research_execution)
