"""Leaf presentation for an asset inspection summary."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AssetInspectionSummaryAnswerStageResult:
    answer: str | None


def run_asset_inspection_summary_answer_stage(
    asset_result: dict[str, Any],
    asset_header_lines: tuple[str, ...],
) -> AssetInspectionSummaryAnswerStageResult:
    answer_lines = list(asset_header_lines)
    raw_rows = asset_result.get("resultaat")

    if isinstance(raw_rows, list):
        dated_rows: list[tuple[str, dict[str, Any]]] = []

        for raw_row in raw_rows:
            if not isinstance(raw_row, dict):
                continue

            document_date = str(raw_row.get("document_date") or "").strip()

            if not document_date:
                continue

            dated_rows.append((document_date, raw_row))

        if dated_rows:
            latest_date = max(document_date for document_date, _ in dated_rows)
            latest_rows = [
                row
                for document_date, row in dated_rows
                if document_date == latest_date
            ]
            seen_measurements: set[tuple[str, str, str, str]] = set()
            measurements: list[dict[str, Any]] = []

            for row in latest_rows:
                meshoogte = row.get("meshoogte_mm")

                if meshoogte is None:
                    continue

                inspection_key = str(row.get("inspection_key") or "").strip()
                scraper_type = str(row.get("scraper_type_raw") or "").strip()
                location = str(row.get("locatie_raw") or "").strip()
                dedupe_key = (
                    inspection_key,
                    scraper_type,
                    location,
                    str(meshoogte),
                )

                if dedupe_key in seen_measurements:
                    continue

                seen_measurements.add(dedupe_key)
                measurements.append(
                    {
                        "inspection_key": inspection_key,
                        "scraper_type": scraper_type,
                        "location": location,
                        "meshoogte_mm": meshoogte,
                        "mes_vervangen": row.get("mes_vervangen"),
                    }
                )

            answer_lines.extend(["", f"Laatste inspectie: {latest_date}"])

            if measurements:
                answer_lines.extend(["", "Schrapers:"])

                for measurement in sorted(
                    measurements,
                    key=lambda item: (
                        item["scraper_type"],
                        item["location"],
                    ),
                ):
                    scraper_type = (
                        measurement["scraper_type"] or "Onbekende schraper"
                    )
                    location = measurement["location"]
                    meshoogte = measurement["meshoogte_mm"]
                    label = scraper_type

                    if location:
                        label += f" â€” {location}"

                    answer_lines.append(f"- {label}: {meshoogte} mm")

                replacement_values = [
                    item.get("mes_vervangen") for item in measurements
                ]

                if replacement_values and all(
                    value is False for value in replacement_values
                ):
                    answer_lines.extend(
                        [
                            "",
                            (
                                "Geen mesvervanging geregistreerd bij "
                                "deze laatste metingen."
                            ),
                        ]
                    )

            return AssetInspectionSummaryAnswerStageResult(
                answer="\n".join(answer_lines)
            )

    return AssetInspectionSummaryAnswerStageResult(answer=None)


__all__ = [
    "AssetInspectionSummaryAnswerStageResult",
    "run_asset_inspection_summary_answer_stage",
]
