from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class PhaseCBoundedResearchV1StageResult:
    research: Any
    plan_research_agent: Any


def run_phase_c_bounded_research_v1_stage(
    plan: Any,
    results: Any,
    status: Any,
    clarification: Any,
    sender: Any,
    timings: Any,
    counts: Any,
    *,
    _research_agent_enabled: Callable[..., Any],
    _observability_call: Callable[..., Any],
    _observability_nonnegative_int: Callable[..., Any],
    run_bounded_research_agent: Callable[..., Any],
    run_bounded_research: Callable[..., Any],
) -> PhaseCBoundedResearchV1StageResult:
    research = {
        "status": "not_required",
        "required": bool(plan.research_required),
        "mode": "bounded_synthesis_v1",
        "ai_calls_used": 0,
        "max_ai_calls": 1,
        "follow_up_rounds_used": 0,
        "max_follow_up_rounds": 0,
        "answer": None,
    }

    if (
        status == "ok"
        and plan.research_required
        and not clarification.get("required")
    ):
        research_agent_enabled = _research_agent_enabled()

        if research_agent_enabled:
            research = _observability_call(
                timings,
                "plan_research",
                run_bounded_research_agent,
                plan,
                results,
                sender=sender,
            )
        else:
            research = _observability_call(
                timings,
                "plan_research",
                run_bounded_research,
                plan,
                results,
            )

    plan_research_agent = None

    if isinstance(research, dict):
        raw_agent = research.get("agent")

        if isinstance(raw_agent, dict):
            plan_research_agent = raw_agent

    if plan_research_agent is not None:
        counts["plan_research_follow_up_specialist_calls"] = (
            _observability_nonnegative_int(
                plan_research_agent.get("follow_up_specialist_calls")
            )
        )

        if "total_ai_calls_used" in plan_research_agent:
            counts["plan_research_ai_calls"] = (
                _observability_nonnegative_int(
                    plan_research_agent.get("total_ai_calls_used")
                )
            )
        else:
            counts["plan_research_ai_calls"] = (
                _observability_nonnegative_int(research.get("ai_calls_used"))
            )

    elif isinstance(research, dict):
        counts["plan_research_ai_calls"] = (
            _observability_nonnegative_int(research.get("ai_calls_used"))
        )

    counts["research_follow_up_specialist_calls"] = (
        counts["phase_c_research_follow_up_specialist_calls"]
        + counts["plan_research_follow_up_specialist_calls"]
    )

    counts["total_specialist_calls"] = (
        counts["initial_specialist_calls"]
        + counts["research_follow_up_specialist_calls"]
    )

    counts["total_ai_calls"] = (
        counts["phase_c_ai_calls"]
        + counts["plan_research_ai_calls"]
    )

    return PhaseCBoundedResearchV1StageResult(
        research,
        plan_research_agent,
    )
