"""Dependency-free analysis-scope answer presentation."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AnalysisScopeAnswerStageResult:
    answer: str | None


def run_analysis_scope_answer_stage(
    specialist_result: dict,
) -> AnalysisScopeAnswerStageResult:
    short = specialist_result.get("kort_resultaat")

    operation = str(specialist_result.get("operation") or "")
    subject = str(specialist_result.get("subject") or "")
    count_semantics = str(specialist_result.get("count_semantics") or "")

    answer_lines: list[str] = []

    if short:
        answer_lines.append(str(short))

    if operation == "list" and subject == "bands":
        bands = specialist_result.get("bands")

        if isinstance(bands, list) and bands and not short:
            answer_lines.append(
                "Banden: " + ", ".join(str(band) for band in bands)
            )

    data_quality = specialist_result.get("data_quality")

    if not isinstance(data_quality, dict):
        data_quality = {}

    if count_semantics == "current_registered_scraper_positions":
        semantic_note = data_quality.get("semantic_note")

        if semantic_note:
            answer_lines.extend(["", str(semantic_note)])

    if count_semantics == "historical_maintenance_ranking_rows":
        answer_lines.extend(
            [
                "",
                (
                    "Let op: dit betreft historische onderhoudsregels binnen de "
                    "canonical scope. Dat is niet automatisch dezelfde set als de "
                    "actuele unified schraperposities."
                ),
            ]
        )

    if operation == "analyse":
        answer_lines.extend(
            [
                "",
                (
                    "De wear-evidence kan historische posities/cycli bevatten en "
                    "wordt daarom als aanvullende historie naast de actuele unified "
                    "snapshot gebruikt."
                ),
            ]
        )

    if answer_lines:
        return AnalysisScopeAnswerStageResult(answer="\n".join(answer_lines))

    return AnalysisScopeAnswerStageResult(answer=None)
