"""Task-research context and call-guard shadow stage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class TaskResearchContextStageResult:
    task_research_contexts_shadow: Any
    task_research_call_guards_shadow: Any


def run_task_research_context_stage(
    plan: Any,
    results: Any,
    task_research_decisions_shadow: Any,
    *,
    derive_intent_task_research_contexts_shadow: Callable[..., Any],
    derive_intent_task_research_call_guards_shadow: Callable[..., Any],
) -> TaskResearchContextStageResult:
    task_research_contexts_shadow = []
    try:
        task_research_contexts_shadow = (
            derive_intent_task_research_contexts_shadow(
                plan,
                list(results),
                task_research_decisions_shadow,
            )
        )
    except Exception:
        task_research_contexts_shadow = []

    task_research_call_guards_shadow = []
    try:
        task_research_call_guards_shadow = (
            derive_intent_task_research_call_guards_shadow(
                task_research_contexts_shadow
            )
        )
    except Exception:
        task_research_call_guards_shadow = []

    return TaskResearchContextStageResult(
        task_research_contexts_shadow=task_research_contexts_shadow,
        task_research_call_guards_shadow=task_research_call_guards_shadow,
    )
