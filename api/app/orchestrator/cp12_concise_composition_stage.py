"""CP12 concise composition between CP11 presentation and CP15 release."""

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class CP12ConciseCompositionStageResult:
    answer: Any
    evidence_pipeline: Any
    task_concise_composer_cp12: Any
    task_public_composition_authority_p4_6f: Any


def run_cp12_concise_composition_stage(
    answer: Any,
    legacy_answer_before_public_composition_canary: Any,
    response_profile: Any,
    task_coverage_gate_cp10: Any,
    task_presenter_cp11: Any,
    evidence_pipeline: Any,
    task_public_composition_authority_p4_6f: Any,
    *,
    compose_concise_public_answer: Callable[..., Any],
) -> CP12ConciseCompositionStageResult:
    answer, task_concise_composer_cp12 = compose_concise_public_answer(
        answer,
        legacy_answer_before_public_composition_canary,
        response_profile=response_profile,
        task_coverage_gate_cp10=task_coverage_gate_cp10,
        task_presenter_cp11=task_presenter_cp11,
    )
    evidence_pipeline["task_concise_composer_cp12"] = (
        task_concise_composer_cp12
    )
    if task_concise_composer_cp12["public_answer_replaced"] is not True:
        task_public_composition_authority_p4_6f.update({
            "authoritative": False,
            "public_answer_authority": False,
            "public_answer_replaced": False,
            "blocked": True,
            "reason": task_concise_composer_cp12["reason"],
        })
        evidence_pipeline[
            "task_public_composition_authority_p4_6f"
        ] = task_public_composition_authority_p4_6f

    return CP12ConciseCompositionStageResult(
        answer=answer,
        evidence_pipeline=evidence_pipeline,
        task_concise_composer_cp12=task_concise_composer_cp12,
        task_public_composition_authority_p4_6f=(
            task_public_composition_authority_p4_6f
        ),
    )


__all__ = [
    "CP12ConciseCompositionStageResult",
    "run_cp12_concise_composition_stage",
]
