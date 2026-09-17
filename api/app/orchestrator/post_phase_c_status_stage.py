"""Clarification and status selection immediately after Phase C."""

from dataclasses import dataclass
from typing import Any, Callable


__all__ = ["PostPhaseCStatusStageResult", "run_post_phase_c_status_stage"]


@dataclass(frozen=True)
class PostPhaseCStatusStageResult:
    status: Any
    clarification: Any


def run_post_phase_c_status_stage(
    plan: Any,
    results: Any,
    typed_execution_results: Any,
    *,
    has_service_accepted_execution_callable: Callable[..., Any],
) -> PostPhaseCStatusStageResult:
    """Select the characterized post-Phase-C clarification and status."""
    specialist_clarification = None

    for item in results:
        specialist_result = item.get("result")

        if not isinstance(specialist_result, dict):
            continue

        specialist_status = str(
            specialist_result.get("status", "")
        ).lower()

        if specialist_status == "clarification_required":
            specialist_clarification = specialist_result
            break

    clarification = {
        "required": plan.clarification_required,
        "question": plan.clarification_question,
    }

    if plan.clarification_required:
        status = "clarification_required"

    elif specialist_clarification is not None:
        clarification_question = specialist_clarification.get("message")

        if not clarification_question:
            detail = specialist_clarification.get("clarification")

            if isinstance(detail, dict):
                clarification_question = detail.get("question")

            elif isinstance(detail, str):
                clarification_question = detail

        if not clarification_question:
            clarification_question = "Kun je de ontbrekende context verduidelijken?"

        clarification = {
            "required": True,
            "question": str(clarification_question),
        }

        status = "clarification_required"

    elif (
        plan.execution_steps
        and not has_service_accepted_execution_callable(
            typed_execution_results,
            results,
        )
    ):
        status = "error"

    else:
        status = "ok"

    return PostPhaseCStatusStageResult(
        status=status,
        clarification=clarification,
    )
