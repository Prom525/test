"""Leaf presentation for an asset lifecycle answer."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AssetLifecycleAnswerStageResult:
    answer: str | None


def run_asset_lifecycle_answer_stage(
    asset_result: dict[str, Any],
    asset_header_lines: tuple[str, ...],
    requested: set[str],
) -> AssetLifecycleAnswerStageResult:
    answer_lines = list(asset_header_lines)
    raw_rows = asset_result.get("resultaat")

    if isinstance(raw_rows, list):
        groups: dict[
            tuple[str, str, str],
            dict[str, Any],
        ] = {}

        seen_measurements: set[
            tuple[
                str,
                str,
                str,
                str,
                str,
                str,
            ]
        ] = set()

        replacement_dates: set[str] = set()

        for raw_row in raw_rows:
            if not isinstance(raw_row, dict):
                continue

            inspected_on = str(
                raw_row.get("inspected_on")
                or ""
            ).strip()

            scraper_type = str(
                raw_row.get(
                    "scraper_type_norm"
                )
                or ""
            ).strip()

            position_hint = str(
                raw_row.get(
                    "position_hint"
                )
                or ""
            ).strip()

            cycle_raw = raw_row.get(
                "cycle_id"
            )

            cycle_id = (
                str(cycle_raw)
                if cycle_raw is not None
                else ""
            )

            canonical_key = str(
                raw_row.get(
                    "canonical_inspection_key"
                )
                or ""
            ).strip()

            if (
                raw_row.get("replace_event")
                is True
                and inspected_on
            ):
                replacement_dates.add(
                    inspected_on
                )

            meshoogte = raw_row.get(
                "meshoogte_mm"
            )

            numeric_height = (
                isinstance(
                    meshoogte,
                    (int, float),
                )
                and not isinstance(
                    meshoogte,
                    bool,
                )
            )

            if not (
                inspected_on
                and scraper_type
                and numeric_height
            ):
                continue

            dedupe_key = (
                canonical_key,
                scraper_type,
                position_hint,
                cycle_id,
                inspected_on,
                str(meshoogte),
            )

            if dedupe_key in seen_measurements:
                continue

            seen_measurements.add(
                dedupe_key
            )

            group_key = (
                scraper_type,
                position_hint,
                cycle_id,
            )

            group = groups.setdefault(
                group_key,
                {
                    "scraper_type": scraper_type,
                    "position_hint": position_hint,
                    "cycle_id": cycle_id,
                    "points": [],
                },
            )

            group["points"].append(
                (
                    inspected_on,
                    float(meshoogte),
                )
            )

        usable_groups: list[
            dict[str, Any]
        ] = []

        total_measurements = 0

        for group in groups.values():
            points = sorted(
                group["points"],
                key=lambda item: item[0],
            )

            if not points:
                continue

            group["points"] = points
            total_measurements += len(points)
            usable_groups.append(group)

        if usable_groups:
            usable_groups.sort(
                key=lambda group: (
                    group["points"][-1][0],
                    group["scraper_type"],
                    group["position_hint"],
                    group["cycle_id"],
                ),
                reverse=True,
            )

            answer_lines.extend(
                [
                    "",
                    (
                        "Trendgegevens: "
                        f"{total_measurements} metingen "
                        f"verdeeld over "
                        f"{len(usable_groups)} cycli."
                    ),
                    "",
                    "Historie per schraper/cyclus:",
                ]
            )

            def _format_mm(
                value: float,
            ) -> str:
                if value.is_integer():
                    return str(int(value))

                return (
                    f"{value:.2f}"
                    .rstrip("0")
                    .rstrip(".")
                )

            for group in usable_groups:
                points = group["points"]

                first_date, first_height = (
                    points[0]
                )

                last_date, last_height = (
                    points[-1]
                )

                label_parts = [
                    group["scraper_type"]
                ]

                if group["position_hint"]:
                    label_parts.append(
                        group["position_hint"]
                    )

                if group["cycle_id"]:
                    label_parts.append(
                        (
                            "cyclus "
                            f"{group['cycle_id']}"
                        )
                    )

                label = " â€” ".join(
                    label_parts
                )

                if len(points) == 1:
                    detail = (
                        f"1 meting, "
                        f"{last_date} "
                        f"{_format_mm(last_height)} mm"
                    )
                else:
                    detail = (
                        f"{len(points)} metingen, "
                        f"{first_date} "
                        f"{_format_mm(first_height)} mm "
                        f"â†’ "
                        f"{last_date} "
                        f"{_format_mm(last_height)} mm"
                    )

                answer_lines.append(
                    f"- {label}: {detail}"
                )

            # PROMATI_INSPECTION_TREND_FACET_PRESENTATION_V1
            #
            # P1.1b blijft presentation-only.
            # De lifecyclebron wordt niet opgewaardeerd
            # tot actuele onderhouds- of forecastbron.
            if (
                "latest_measurements"
                in requested
            ):
                latest_by_position: dict[
                    tuple[str, str],
                    dict[str, Any],
                ] = {}

                for group in usable_groups:
                    points = group["points"]

                    if not points:
                        continue

                    (
                        latest_date,
                        latest_height,
                    ) = points[-1]

                    latest_key = (
                        group["scraper_type"],
                        group["position_hint"],
                    )

                    existing = (
                        latest_by_position.get(
                            latest_key
                        )
                    )

                    if (
                        existing is None
                        or latest_date
                        > existing["inspected_on"]
                    ):
                        latest_by_position[
                            latest_key
                        ] = {
                            "scraper_type": (
                                group[
                                    "scraper_type"
                                ]
                            ),
                            "position_hint": (
                                group[
                                    "position_hint"
                                ]
                            ),
                            "inspected_on": (
                                latest_date
                            ),
                            "meshoogte_mm": (
                                latest_height
                            ),
                        }

                if latest_by_position:
                    latest_rows = sorted(
                        latest_by_position.values(),
                        key=lambda item: (
                            item["inspected_on"],
                            item["scraper_type"],
                            item["position_hint"],
                        ),
                        reverse=True,
                    )

                    answer_lines.extend(
                        [
                            "",
                            (
                                "Laatste lifecycle-meting "
                                "per schraper/positie:"
                            ),
                        ]
                    )

                    for measurement in latest_rows:
                        label = measurement[
                            "scraper_type"
                        ]

                        if measurement[
                            "position_hint"
                        ]:
                            label = (
                                label
                                + " - "
                                + measurement[
                                    "position_hint"
                                ]
                            )

                        height_text = _format_mm(
                            measurement[
                                "meshoogte_mm"
                            ]
                        )

                        date_text = str(
                            measurement[
                                "inspected_on"
                            ]
                        )

                        answer_lines.append(
                            (
                                "- "
                                + label
                                + ": "
                                + height_text
                                + " mm op "
                                + date_text
                            )
                        )

            if replacement_dates:
                answer_lines.extend(
                    [
                        "",
                        (
                            "Geregistreerde "
                            "vervangevents: "
                            + ", ".join(
                                sorted(
                                    replacement_dates
                                )
                            )
                        ),
                    ]
                )

            elif (
                "replacement_events"
                in requested
            ):
                answer_lines.extend(
                    [
                        "",
                        (
                            "Geregistreerde "
                            "vervangevents: geen "
                            "in deze lifecyclebron."
                        ),
                    ]
                )

            if (
                "replacement_advice"
                in requested
            ):
                answer_lines.extend(
                    [
                        "",
                        (
                            "Vervangadvies: niet bepaald "
                            "uit deze lifecyclehistorie; "
                            "hiervoor is een actuele "
                            "onderhouds-/forecastanalyse "
                            "nodig."
                        ),
                    ]
                )

            if (
                "uncertainties"
                in requested
            ):
                answer_lines.extend(
                    [
                        "",
                        "Onzekerheden:",
                        (
                            "- De weergegeven laatste "
                            "meshoogte is de meest recente "
                            "lifecycle-meting per "
                            "schraper/positie in deze bron; "
                            "dit bevestigt niet dat de "
                            "positie nog actueel actief is."
                        ),
                        (
                            "- Deze lifecyclebron bevat "
                            "geen afzonderlijke actuele "
                            "vervang-/forecastanalyse; "
                            "daarom wordt hier geen "
                            "vervangmoment afgeleid."
                        ),
                    ]
                )

            return AssetLifecycleAnswerStageResult(
                answer="\n".join(answer_lines)
            )

    return AssetLifecycleAnswerStageResult(answer=None)


__all__ = [
    "AssetLifecycleAnswerStageResult",
    "run_asset_lifecycle_answer_stage",
]
