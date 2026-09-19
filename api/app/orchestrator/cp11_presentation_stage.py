"""CP11 presentation between CP10 authority rollback and CP12 composition."""

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class CP11PresentationStageResult:
    answer: Any
    evidence_pipeline: Any
    task_presenter_cp11: Any
    task_public_composition_authority_p4_6f: Any


def run_cp11_presentation_stage(
    plan: Any,
    legacy_answer_before_public_composition_canary: Any,
    task_coverage_gate_cp10: Any,
    evidence_pipeline: Any,
    task_public_composition_authority_p4_6f: Any,
    *,
    present_relevant_task_answer: Callable[..., Any],
) -> CP11PresentationStageResult:
    try:
        answer, task_presenter_cp11, task_public_composition_authority_p4_6f = (
            present_relevant_task_answer(
                plan,
                legacy_answer_before_public_composition_canary,
                task_coverage_gate_cp10,
                evidence_pipeline.get(
                    "task_grounded_synthesis_coverage_authority_p4_6e3"
                ),
                task_public_composition_authority_p4_6f,
            )
        )
    except Exception:
        answer = legacy_answer_before_public_composition_canary
        task_presenter_cp11 = {
            "contract_version": (
                "promati.orchestrator.task_relevance_presenter.cp11.v1"
            ),
            "evaluated": False,
            "authoritative": False,
            "public_answer_replaced": False,
            "reason": "internal_error_fail_closed",
        }
        task_public_composition_authority_p4_6f = dict(
            task_public_composition_authority_p4_6f or {}
        )
        task_public_composition_authority_p4_6f.update({
            "authoritative": False,
            "public_answer_authority": False,
            "public_answer_replaced": False,
            "blocked": True,
            "reason": "presenter_internal_error",
            "task_presenter_cp11": task_presenter_cp11,
        })
    evidence_pipeline["task_presenter_cp11"] = task_presenter_cp11
    evidence_pipeline[
        "task_public_composition_authority_p4_6f"
    ] = task_public_composition_authority_p4_6f

    return CP11PresentationStageResult(
        answer=answer,
        evidence_pipeline=evidence_pipeline,
        task_presenter_cp11=task_presenter_cp11,
        task_public_composition_authority_p4_6f=(
            task_public_composition_authority_p4_6f
        ),
    )


__all__ = [
    "CP11PresentationStageResult",
    "run_cp11_presentation_stage",
]
