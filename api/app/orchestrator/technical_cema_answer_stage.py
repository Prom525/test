from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TechnicalCemaAnswerStageResult:
    answer: str | None


def run_technical_cema_answer_stage(
    specialist_result: dict[str, Any],
) -> TechnicalCemaAnswerStageResult:
    source_code = specialist_result.get("source_code")

    if source_code != "CEMA_BELT_CONVEYORS_7":
        return TechnicalCemaAnswerStageResult(answer=None)

    technical_context = specialist_result.get("technical_context")
    source_title = None

    if isinstance(technical_context, dict):
        technical_rows = technical_context.get("results")

        if isinstance(technical_rows, list):
            for row in technical_rows:
                if not isinstance(row, dict):
                    continue
                candidate = row.get("source_title")
                if candidate:
                    source_title = str(candidate)
                    break

    full_name = "Conveyor Equipment Manufacturers Association"
    grounded_full_name = False
    rag_context = specialist_result.get("rag_context")

    if isinstance(rag_context, dict):
        used_context = rag_context.get("used_context")
        if isinstance(used_context, list):
            for item in used_context:
                context_text = None
                if isinstance(item, str):
                    context_text = item
                elif isinstance(item, dict):
                    candidate_text = item.get("text")
                    if isinstance(candidate_text, str):
                        context_text = candidate_text
                if not context_text:
                    continue
                if full_name.casefold() in context_text.casefold():
                    grounded_full_name = True
                    break

    if grounded_full_name:
        if source_title:
            return TechnicalCemaAnswerStageResult(
                answer=f"CEMA staat voor {full_name}. Bron: {source_title}."
            )
        return TechnicalCemaAnswerStageResult(
            answer=f"CEMA staat voor {full_name}."
        )

    if source_title:
        return TechnicalCemaAnswerStageResult(
            answer=(
                "CEMA-referentiegegevens zijn "
                f"beschikbaar uit {source_title}. "
                "In dit specialistresultaat is "
                "geen definitierecord van CEMA aanwezig."
            )
        )

    return TechnicalCemaAnswerStageResult(
        answer=(
            "CEMA-referentiegegevens zijn beschikbaar, maar in dit "
            "specialistresultaat is geen definitierecord van CEMA aanwezig."
        )
    )
