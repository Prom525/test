"""CP13 task-research semantics stage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class Cp13ResearchSemanticsStageResult:
    task_research_semantics_cp13: Any


def run_cp13_research_semantics_stage(
    plan: Any,
    task_execution_shadow: Any,
    task_research_authority_p4_6d1: Any,
    *,
    build_task_research_semantics: Callable[..., Any],
) -> Cp13ResearchSemanticsStageResult:
    try:
        task_research_semantics_cp13 = build_task_research_semantics(
            plan,
            task_execution_shadow,
            task_research_authority_p4_6d1,
        )
    except Exception:
        task_research_semantics_cp13 = {
            "contract_version": (
                "promati.orchestrator.task_research_semantics.cp13.v1"
            ),
            "evaluated": False,
            "authoritative": False,
            "authority_scope": "intent_task_research_eligibility_only",
            "public_answer_authority": False,
            "legacy_generic_research_allowed": False,
            "allowed_task_ids": [],
            "tasks": [],
            "reason": "internal_error_fail_closed",
        }

    return Cp13ResearchSemanticsStageResult(
        task_research_semantics_cp13=task_research_semantics_cp13,
    )


__all__ = [
    "Cp13ResearchSemanticsStageResult",
    "run_cp13_research_semantics_stage",
]
