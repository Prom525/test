from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class P46e2GroundedSynthesisStageResult:
    task_grounded_synthesis_authority_p4_6e2: Any


def run_p4_6e2_grounded_synthesis_stage(
    task_research_evidence_authority_p4_6e1: Any,
    task_research_evidence_units_p4_6e1: Any,
    *,
    build_task_grounded_synthesis_authority_canary_p4_6e2: Callable[..., Any],
) -> P46e2GroundedSynthesisStageResult:
    task_grounded_synthesis_authority_p4_6e2 = None
    try:
        task_grounded_synthesis_authority_p4_6e2 = (
            build_task_grounded_synthesis_authority_canary_p4_6e2(
                task_research_evidence_authority_p4_6e1,
                task_research_evidence_units_p4_6e1,
            )
        )
    except Exception:
        task_grounded_synthesis_authority_p4_6e2 = None

    return P46e2GroundedSynthesisStageResult(
        task_grounded_synthesis_authority_p4_6e2,
    )
