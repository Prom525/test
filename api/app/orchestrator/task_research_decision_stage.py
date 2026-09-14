"""Task-research decision shadow and P4.6D1 authority stage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class TaskResearchDecisionStageResult:
    task_research_decisions_shadow: Any
    task_research_authority_p4_6d1: Any


def run_task_research_decision_stage(
    task_evidence_assessments_shadow: Any,
    task_evidence_authority_p4_6c: Any,
    *,
    derive_intent_task_research_decisions_shadow: Callable[..., Any],
    build_task_research_authority_canary_p4_6d1: Callable[..., Any],
) -> TaskResearchDecisionStageResult:
    task_research_decisions_shadow = []
    try:
        task_research_decisions_shadow = (
            derive_intent_task_research_decisions_shadow(
                task_evidence_assessments_shadow
            )
        )
    except Exception:
        task_research_decisions_shadow = []

    task_research_authority_p4_6d1 = None
    try:
        task_research_authority_p4_6d1 = (
            build_task_research_authority_canary_p4_6d1(
                task_evidence_authority_p4_6c,
                task_research_decisions_shadow,
            )
        )
    except Exception:
        task_research_authority_p4_6d1 = None

    return TaskResearchDecisionStageResult(
        task_research_decisions_shadow=task_research_decisions_shadow,
        task_research_authority_p4_6d1=task_research_authority_p4_6d1,
    )
