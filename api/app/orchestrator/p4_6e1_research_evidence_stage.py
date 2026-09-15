from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class P46e1ResearchEvidenceStageResult:
    task_research_evidence_authority_p4_6e1: Any
    task_research_evidence_units_p4_6e1: list[Any]


def run_p4_6e1_research_evidence_stage(
    plan: Any,
    task_research_execution_authority_p4_6d2: Any,
    task_research_execution_observations_p4_6d2: Any,
    working_evidence_items: Any,
    retrieved_at: Any,
    *,
    build_task_research_evidence_authority_canary_p4_6e1: Callable[..., Any],
) -> P46e1ResearchEvidenceStageResult:
    task_research_evidence_authority_p4_6e1 = None
    task_research_evidence_units_p4_6e1 = []
    try:
        task_research_evidence_authority_p4_6e1 = (
            build_task_research_evidence_authority_canary_p4_6e1(
                plan,
                task_research_execution_authority_p4_6d2,
                task_research_execution_observations_p4_6d2,
                tuple(working_evidence_items),
                now=retrieved_at,
                grounded_synthesis_observer=(
                    task_research_evidence_units_p4_6e1.append
                ),
            )
        )
    except Exception:
        task_research_evidence_authority_p4_6e1 = None
        task_research_evidence_units_p4_6e1 = []

    return P46e1ResearchEvidenceStageResult(
        task_research_evidence_authority_p4_6e1,
        task_research_evidence_units_p4_6e1,
    )
