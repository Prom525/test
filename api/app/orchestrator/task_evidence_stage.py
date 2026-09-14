"""Task-evidence shadow and P4.6C authority stage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class TaskEvidenceStageResult:
    task_evidence_assessments_shadow: Any
    task_evidence_authority_p4_6c: Any


def run_task_evidence_stage(
    plan: Any,
    working_evidence_items: Any,
    retrieved_at: Any,
    *,
    assess_intent_task_evidence_shadow: Callable[..., Any],
    build_task_evidence_authority_canary_p4_6c: Callable[..., Any],
) -> TaskEvidenceStageResult:
    task_evidence_assessments_shadow = []
    try:
        task_evidence_assessments_shadow = (
            assess_intent_task_evidence_shadow(
                plan,
                working_evidence_items,
                now=retrieved_at,
            )
        )
    except Exception:
        task_evidence_assessments_shadow = []

    task_evidence_authority_p4_6c = None
    try:
        task_evidence_authority_p4_6c = (
            build_task_evidence_authority_canary_p4_6c(
                plan,
                tuple(working_evidence_items),
                now=retrieved_at,
                shadow_assessments=(
                    task_evidence_assessments_shadow
                ),
            )
        )
    except Exception:
        task_evidence_authority_p4_6c = None

    return TaskEvidenceStageResult(
        task_evidence_assessments_shadow=(
            task_evidence_assessments_shadow
        ),
        task_evidence_authority_p4_6c=(
            task_evidence_authority_p4_6c
        ),
    )
