"""Service-owned P4.6D2 research-execution invocation stage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class P46d2ResearchExecutionStageResult:
    task_research_execution_authority_p4_6d2: Any
    task_research_execution_observations_p4_6d2: list[Any]


def run_p4_6d2_research_execution_stage(
    plan: Any,
    results: Any,
    task_research_authority_p4_6d1: Any,
    task_research_contexts_shadow: Any,
    task_research_call_guards_shadow: Any,
    sender: Any,
    task_research_semantics_cp13: Any,
    *,
    run_task_research_execution_authority_canary_p4_6d2: Callable[..., Any],
) -> P46d2ResearchExecutionStageResult:
    task_research_execution_authority_p4_6d2 = None
    task_research_execution_observations_p4_6d2 = []
    try:
        task_research_execution_authority_p4_6d2 = (
            run_task_research_execution_authority_canary_p4_6d2(
                plan,
                list(results),
                task_research_authority_p4_6d1,
                task_research_contexts_shadow,
                task_research_call_guards_shadow,
                sender=sender,
                evidence_observer=(
                    task_research_execution_observations_p4_6d2.append
                ),
                task_research_semantics_cp13=task_research_semantics_cp13,
            )
        )
    except Exception:
        task_research_execution_authority_p4_6d2 = None
        task_research_execution_observations_p4_6d2 = []

    return P46d2ResearchExecutionStageResult(
        task_research_execution_authority_p4_6d2=(
            task_research_execution_authority_p4_6d2
        ),
        task_research_execution_observations_p4_6d2=(
            task_research_execution_observations_p4_6d2
        ),
    )


__all__ = [
    "P46d2ResearchExecutionStageResult",
    "run_p4_6d2_research_execution_stage",
]
