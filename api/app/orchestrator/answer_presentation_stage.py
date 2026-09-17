"""Legacy answer selection and presentation stage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class AnswerPresentationStageResult:
    answer: Any


def run_answer_presentation_stage(
    results: Any,
    requested_information: Callable[[], Any],
    research: Any,
    timings: Any,
    *,
    observability_now: Callable[[], Any],
    build_user_answer: Callable[..., Any],
    repair_mojibake_text: Callable[[Any], Any],
    observability_elapsed_ms: Callable[[Any], Any],
) -> AnswerPresentationStageResult:
    presentation_started = observability_now()

    try:
        answer = build_user_answer(
            results,
            requested_information=requested_information(),
        )

        if research.get("status") == "ok" and research.get("answer"):
            answer = str(research["answer"])

        if answer:
            answer = repair_mojibake_text(answer)
    finally:
        timings["presentation"] = observability_elapsed_ms(
            presentation_started
        )

    return AnswerPresentationStageResult(answer=answer)


__all__ = [
    "AnswerPresentationStageResult",
    "run_answer_presentation_stage",
]
