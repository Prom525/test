"""Leaf presentation for asset maintenance positions."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AssetMaintenancePositionsAnswerStageResult:
    answer: str | None


def run_asset_maintenance_positions_answer_stage(
    asset_result: dict[str, Any],
    asset_header_lines: tuple[str, ...],
) -> AssetMaintenancePositionsAnswerStageResult:
    answer_lines = list(asset_header_lines)
    raw_rows = asset_result.get(
        "resultaat"
    )

    if isinstance(
        raw_rows,
        list,
    ):
        positions: list[
            dict[str, Any]
        ] = []

        seen_positions: set[
            tuple[
                str,
                str,
                str,
                str,
            ]
        ] = set()

        for raw_row in raw_rows:
            if not isinstance(
                raw_row,
                dict,
            ):
                continue

            scraper_types = str(
                raw_row.get(
                    "scraper_types_clean"
                )
                or raw_row.get(
                    "scraper_types"
                )
                or ""
            ).strip()

            position_hint = str(
                raw_row.get(
                    "position_hint"
                )
                or ""
            ).strip()

            cycle_end = str(
                raw_row.get(
                    "cycle_end"
                )
                or ""
            ).strip()

            priority_raw = (
                raw_row.get(
                    "prioriteit"
                )
            )

            priority = (
                float(priority_raw)
                if (
                    isinstance(
                        priority_raw,
                        (int, float),
                    )
                    and not isinstance(
                        priority_raw,
                        bool,
                    )
                )
                else float("inf")
            )

            dedupe_key = (
                scraper_types,
                position_hint,
                cycle_end,
                str(priority_raw),
            )

            if (
                dedupe_key
                in seen_positions
            ):
                continue

            seen_positions.add(
                dedupe_key
            )

            end_height_raw = (
                raw_row.get(
                    "eind_meshoogte_mm"
                )
            )

            numeric_end_height = (
                isinstance(
                    end_height_raw,
                    (int, float),
                )
                and not isinstance(
                    end_height_raw,
                    bool,
                )
            )

            end_height = (
                float(end_height_raw)
                if numeric_end_height
                else None
            )

            meetpunten_raw = (
                raw_row.get(
                    "meetpunten"
                )
            )

            usable_point_count = (
                isinstance(
                    meetpunten_raw,
                    int,
                )
                and not isinstance(
                    meetpunten_raw,
                    bool,
                )
                and meetpunten_raw
                >= 3
            )

            forecast_date = str(
                raw_row.get(
                    "geschatte_vervangdatum_bij_3mm"
                )
                or ""
            ).strip()

            performance_action = str(
                raw_row.get(
                    "prestatie_vervangmoment"
                )
                or ""
            ).strip()

            status_6mm = str(
                raw_row.get(
                    "status_6mm"
                )
                or ""
            ).strip()

            status_3mm = str(
                raw_row.get(
                    "status_3mm"
                )
                or ""
            ).strip()

            if (
                numeric_end_height
                and end_height
                is not None
                and end_height <= 3.0
            ):
                action = (
                    "NU VERVANGEN"
                )
            elif (
                performance_action
                == (
                    "CONTROLEREN_"
                    "PRESTATIEGRENS"
                )
                or status_6mm
                == "OP_OF_ONDER_6MM"
            ):
                action = (
                    "Prestatiegrens "
                    "controleren"
                )
            elif not (
                numeric_end_height
            ):
                action = (
                    "Trend controleren; "
                    "geen bruikbare "
                    "actuele eindmeting"
                )
            elif (
                status_3mm
                == "CHECK_TREND"
            ):
                action = (
                    "Trend controleren"
                )
            else:
                action = "Monitoren"

            reliable_forecast = (
                usable_point_count
                and numeric_end_height
                and forecast_date != ""
            )

            positions.append(
                {
                    "priority": (
                        priority
                    ),
                    "priority_raw": (
                        priority_raw
                    ),
                    "scraper_types": (
                        scraper_types
                        or "Onbekende schraper"
                    ),
                    "position_hint": (
                        position_hint
                        or "positie onbekend"
                    ),
                    "cycle_end": (
                        cycle_end
                    ),
                    "meetpunten": (
                        meetpunten_raw
                    ),
                    "end_height": (
                        end_height
                    ),
                    "action": action,
                    "forecast_date": (
                        forecast_date
                    ),
                    "reliable_forecast": (
                        reliable_forecast
                    ),
                }
            )

        if positions:
            positions.sort(
                key=lambda item: (
                    item["priority"],
                    item[
                        "scraper_types"
                    ],
                    item[
                        "position_hint"
                    ],
                )
            )

            def _format_mm(
                value: float,
            ) -> str:
                if value.is_integer():
                    return str(
                        int(value)
                    )

                return (
                    f"{value:.2f}"
                    .rstrip("0")
                    .rstrip(".")
                )

            answer_lines.extend(
                [
                    "",
                    "Onderhoudsprioriteit:",
                ]
            )

            for index, position in enumerate(
                positions,
                start=1,
            ):
                answer_lines.extend(
                    [
                        "",
                        (
                            f"{index}. "
                            f"{position['scraper_types']}"
                            " â€” "
                            f"{position['position_hint']}"
                        ),
                    ]
                )

                end_height = (
                    position[
                        "end_height"
                    ]
                )

                cycle_end = (
                    position[
                        "cycle_end"
                    ]
                )

                if (
                    end_height
                    is not None
                ):
                    measurement_line = (
                        "   Laatste gemeten "
                        "meshoogte: "
                        f"{_format_mm(end_height)} mm"
                    )

                    if cycle_end:
                        measurement_line += (
                            f" op {cycle_end}"
                        )

                    answer_lines.append(
                        measurement_line
                    )
                else:
                    answer_lines.append(
                        "   Laatste gemeten "
                        "meshoogte: "
                        "niet beschikbaar"
                    )

                answer_lines.append(
                    "   Actie: "
                    f"{position['action']}"
                )

                if (
                    position[
                        "reliable_forecast"
                    ]
                ):
                    answer_lines.append(
                        "   Prognose 3 mm: "
                        "rond "
                        f"{position['forecast_date']}"
                    )

                    answer_lines.append(
                        "   Onderbouwing: "
                        f"{position['meetpunten']} "
                        "meetpunten"
                    )
                else:
                    answer_lines.append(
                        "   Geen betrouwbare "
                        "forecast beschikbaar"
                    )

            answer_lines.extend(
                [
                    "",
                    (
                        "Let op: 3 mm is de "
                        "vervanggrens. "
                        "De 6 mm-grens is een "
                        "prestatiecontrole en "
                        "betekent niet automatisch "
                        "vervangen."
                    ),
                ]
            )

            return AssetMaintenancePositionsAnswerStageResult(
                answer="\n".join(answer_lines)
            )

    return AssetMaintenancePositionsAnswerStageResult(answer=None)


__all__ = [
    "AssetMaintenancePositionsAnswerStageResult",
    "run_asset_maintenance_positions_answer_stage",
]
