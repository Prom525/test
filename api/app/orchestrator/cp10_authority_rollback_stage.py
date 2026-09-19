"""CP10 authority rollback between P4.6F/CP9 and CP11."""

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class CP10AuthorityRollbackStageResult:
    answer: Any
    evidence_pipeline: Any
    task_public_composition_authority_p4_6f: Any


def run_cp10_authority_rollback_stage(
    answer: Any,
    legacy_answer_before_public_composition_canary: Any,
    evidence_pipeline: Any,
    task_public_composition_authority_p4_6f: Any,
    task_coverage_gate_cp10: Any,
    *,
    guard_task_coverage_authority: Callable[..., Any],
    guard_public_composition_canary: Callable[..., Any],
) -> CP10AuthorityRollbackStageResult:
    if isinstance(evidence_pipeline, dict):
        answer, task_public_composition_authority_p4_6f = (
            guard_task_coverage_authority(
                answer,
                legacy_answer_before_public_composition_canary,
                task_public_composition_authority_p4_6f,
                task_coverage_gate_cp10,
            )
        )
        evidence_pipeline[
            "task_public_composition_authority_p4_6f"
        ] = task_public_composition_authority_p4_6f
        evidence_pipeline["public_composition_canary_shadow"] = (
            guard_public_composition_canary(
                evidence_pipeline.get("public_composition_canary_shadow"),
                task_coverage_gate_cp10,
            )
        )
        evidence_pipeline["task_coverage_gate_cp10"] = task_coverage_gate_cp10

    return CP10AuthorityRollbackStageResult(
        answer=answer,
        evidence_pipeline=evidence_pipeline,
        task_public_composition_authority_p4_6f=(
            task_public_composition_authority_p4_6f
        ),
    )


__all__ = [
    "CP10AuthorityRollbackStageResult",
    "run_cp10_authority_rollback_stage",
]
