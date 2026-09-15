from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class P46e3SynthesisCoverageStageResult:
    task_grounded_synthesis_coverage_authority_p4_6e3: Any


def run_p4_6e3_synthesis_coverage_stage(
    plan: Any,
    task_evidence_authority_p4_6c: Any,
    task_grounded_synthesis_authority_p4_6e2: Any,
    working_evidence_items: Any,
    retrieved_at: Any,
    *,
    build_task_grounded_synthesis_coverage_authority_canary_p4_6e3: Callable[..., Any],
) -> P46e3SynthesisCoverageStageResult:
    task_grounded_synthesis_coverage_authority_p4_6e3 = None
    try:
        task_grounded_synthesis_coverage_authority_p4_6e3 = (
            build_task_grounded_synthesis_coverage_authority_canary_p4_6e3(
                plan,
                task_evidence_authority_p4_6c,
                task_grounded_synthesis_authority_p4_6e2,
                tuple(working_evidence_items),
                now=retrieved_at,
            )
        )
    except Exception:
        task_grounded_synthesis_coverage_authority_p4_6e3 = None

    return P46e3SynthesisCoverageStageResult(
        task_grounded_synthesis_coverage_authority_p4_6e3,
    )
