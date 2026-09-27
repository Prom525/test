"""Leaf presentation for asset band deep analysis."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AssetBandDeepAnalysisAnswerStageResult:
    answer: str | None


def run_asset_band_deep_analysis_answer_stage(
    asset_result: dict[str, Any],
    asset_header_lines: tuple[str, ...],
    requested: set[str],
) -> AssetBandDeepAnalysisAnswerStageResult:
    answer_lines = list(asset_header_lines)

    # PROMATI_REPLACEMENT_ADVICE_PRESENTATION_V1
    #
    # Smalle legacy-presentatie voor replacement_advice.
    # Geen wijziging aan C7 answer ownership.
    #
    # Semantiek:
    # - gemeten <= 3 mm => NU VERVANGEN
    # - VERVANGEN_VOORBEREIDEN blijft voorbereiden
    # - forecast alleen bij >= 3 bruikbare meetpunten
    # - geen relatieve dagen-tot-3mm presentatie
    raw_positions = asset_result.get(
        "gecombineerde_slijtage"
    )

    raw_forecasts = asset_result.get(
        "forecast_3mm"
    )

    if isinstance(
        raw_positions,
        list,
    ):
        if not isinstance(
            raw_forecasts,
            list,
        ):
            raw_forecasts = []

        def _numeric(
            value: Any,
        ) -> bool:
            return (
                isinstance(
                    value,
                    (int, float),
                )
                and not isinstance(
                    value,
                    bool,
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

        def _family_from_text(
            value: Any,
        ) -> str:
            text = str(
                value or ""
            ).strip().upper()

            if not text:
                return ""

            first = text[0]

            if first in {
                "R",
                "U",
                "T",
            }:
                return first

            return ""

        eligible_forecasts_by_family: dict[
            str,
            list[dict[str, Any]],
        ] = {}

        for raw_forecast in raw_forecasts:
            if not isinstance(
                raw_forecast,
                dict,
            ):
                continue

            meetpunten = raw_forecast.get(
                "meetpunten"
            )

            end_height = raw_forecast.get(
                "eind_meshoogte_mm"
            )

            wear_rate = raw_forecast.get(
                "slijtage_mm_per_dag"
            )

            days_to_3mm = raw_forecast.get(
                "geschatte_dagen_tot_3mm"
            )

            forecast_date = str(
                raw_forecast.get(
                    "geschatte_vervangdatum_bij_3mm"
                )
                or ""
            ).strip()

            family = _family_from_text(
                raw_forecast.get(
                    "scraper_type_norm"
                )
            )

            eligible = (
                isinstance(
                    meetpunten,
                    int,
                )
                and not isinstance(
                    meetpunten,
                    bool,
                )
                and meetpunten >= 3
                and _numeric(
                    end_height
                )
                and _numeric(
                    wear_rate
                )
                and _numeric(
                    days_to_3mm
                )
                and forecast_date != ""
                and family != ""
            )

            if not eligible:
                continue

            eligible_forecasts_by_family.setdefault(
                family,
                [],
            ).append(
                raw_forecast
            )

        positions: list[
            dict[str, Any]
        ] = []

        seen_positions: set[
            tuple[
                str,
                str,
                str,
            ]
        ] = set()

        for raw_position in raw_positions:
            if not isinstance(
                raw_position,
                dict,
            ):
                continue

            scraper_type = str(
                raw_position.get(
                    "scraper_type_norm"
                )
                or ""
            ).strip()

            family = str(
                raw_position.get(
                    "scraper_family"
                )
                or ""
            ).strip().upper()

            if not family:
                family = _family_from_text(
                    scraper_type
                )

            position_display = str(
                raw_position.get(
                    "position_display"
                )
                or ""
            ).strip()

            inspection_date = str(
                raw_position.get(
                    "laatste_inspectiedatum"
                )
                or ""
            ).strip()

            height_raw = (
                raw_position.get(
                    "meshoogte_mm"
                )
            )

            height = (
                float(height_raw)
                if _numeric(
                    height_raw
                )
                else None
            )

            advice = str(
                raw_position.get(
                    "onderhoudsadvies_unified"
                )
                or ""
            ).strip().upper()

            dedupe_key = (
                scraper_type,
                position_display,
                inspection_date,
            )

            if (
                dedupe_key
                in seen_positions
            ):
                continue

            seen_positions.add(
                dedupe_key
            )

            if (
                height is not None
                and height <= 3.0
            ):
                action = (
                    "NU VERVANGEN"
                )

                action_rank = 0

            elif (
                advice
                == "VERVANGEN_VOORBEREIDEN"
            ):
                action = (
                    "Vervanging voorbereiden"
                )

                action_rank = 1

            elif (
                advice
                == "CONTROLEREN_BIJ_STOP"
            ):
                action = (
                    "Controleren bij stop"
                )

                action_rank = 2

            else:
                action = "Monitoren"
                action_rank = 3

            forecast = None

            family_forecasts = (
                eligible_forecasts_by_family.get(
                    family,
                    [],
                )
            )

            # Fail-closed:
            # alleen koppelen wanneer precies
            # Ã©Ã©n betrouwbare forecast bestaat
            # voor deze scraperfamilie.
            if (
                len(
                    family_forecasts
                )
                == 1
            ):
                forecast = (
                    family_forecasts[0]
                )

            positions.append(
                {
                    "scraper_type": (
                        scraper_type
                        or "Onbekende schraper"
                    ),
                    "position": (
                        position_display
                        or "positie onbekend"
                    ),
                    "inspection_date": (
                        inspection_date
                    ),
                    "height": height,
                    "action": action,
                    "action_rank": (
                        action_rank
                    ),
                    "forecast": (
                        forecast
                    ),
                }
            )

        if positions:
            positions.sort(
                key=lambda item: (
                    item["action_rank"],
                    item["scraper_type"],
                    item["position"],
                )
            )

            answer_lines.extend(
                [
                    "",
                    "Vervangadvies:",
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
                            f"{position['scraper_type']}"
                            " â€” "
                            f"{position['position']}"
                        ),
                    ]
                )

                height = position[
                    "height"
                ]

                inspection_date = position[
                    "inspection_date"
                ]

                if height is not None:
                    measurement_line = (
                        "   Laatste gemeten "
                        "meshoogte: "
                        f"{_format_mm(height)} mm"
                    )

                    if inspection_date:
                        measurement_line += (
                            f" op {inspection_date}"
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
                    "   Advies: "
                    f"{position['action']}"
                )

                forecast = position[
                    "forecast"
                ]

                if isinstance(
                    forecast,
                    dict,
                ):
                    forecast_date = str(
                        forecast.get(
                            "geschatte_vervangdatum_bij_3mm"
                        )
                        or ""
                    ).strip()

                    meetpunten = (
                        forecast.get(
                            "meetpunten"
                        )
                    )

                    answer_lines.append(
                        "   Prognose 3 mm: "
                        f"rond {forecast_date}"
                    )

                    answer_lines.append(
                        "   Onderbouwing: "
                        f"{meetpunten} meetpunten"
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
                        "Een advies 'vervanging "
                        "voorbereiden' betekent "
                        "niet dat het mes nu al "
                        "de vervanggrens heeft "
                        "bereikt."
                    ),
                ]
            )

            # PROMATI_REPLACEMENT_ADVICE_FACET_PRESENTATION_V1
            #
            # P1.2b: facetprojecties uit dezelfde
            # band_deep_analysis-response.
            #
            # Actuele meshoogte en vervangadvies blijven
            # uitsluitend gebaseerd op gecombineerde_slijtage
            # en de bestaande forecastlogica hierboven.
            # Lifecycle wordt alleen gebruikt voor historie
            # en geregistreerde vervangevents.
            facet_requested = bool(
                {
                    "lifecycle_trend",
                    "replacement_events",
                    "uncertainties",
                }
                & requested
            )

            if facet_requested:
                raw_lifecycle = (
                    asset_result.get(
                        "lifecycle"
                    )
                )

                lifecycle_available = (
                    isinstance(
                        raw_lifecycle,
                        list,
                    )
                )

                lifecycle_groups: dict[
                    tuple[str, str, str],
                    dict[str, Any],
                ] = {}

                lifecycle_replacement_dates: (
                    set[str]
                ) = set()

                seen_lifecycle_measurements: set[
                    tuple[
                        str,
                        str,
                        str,
                        str,
                        str,
                        str,
                    ]
                ] = set()

                if lifecycle_available:
                    for raw_row in raw_lifecycle:
                        if not isinstance(
                            raw_row,
                            dict,
                        ):
                            continue

                        inspected_on = str(
                            raw_row.get(
                                "inspected_on"
                            )
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
                            if cycle_raw
                            is not None
                            else ""
                        )

                        canonical_key = str(
                            raw_row.get(
                                "canonical_inspection_key"
                            )
                            or ""
                        ).strip()

                        if (
                            raw_row.get(
                                "replace_event"
                            )
                            is True
                            and inspected_on
                        ):
                            lifecycle_replacement_dates.add(
                                inspected_on
                            )

                        meshoogte = (
                            raw_row.get(
                                "meshoogte_mm"
                            )
                        )

                        if not (
                            inspected_on
                            and scraper_type
                            and _numeric(
                                meshoogte
                            )
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

                        if (
                            dedupe_key
                            in seen_lifecycle_measurements
                        ):
                            continue

                        seen_lifecycle_measurements.add(
                            dedupe_key
                        )

                        group_key = (
                            scraper_type,
                            position_hint,
                            cycle_id,
                        )

                        group = (
                            lifecycle_groups.setdefault(
                                group_key,
                                {
                                    "scraper_type": (
                                        scraper_type
                                    ),
                                    "position_hint": (
                                        position_hint
                                    ),
                                    "cycle_id": (
                                        cycle_id
                                    ),
                                    "points": [],
                                },
                            )
                        )

                        group["points"].append(
                            (
                                inspected_on,
                                float(
                                    meshoogte
                                ),
                            )
                        )

                usable_lifecycle_groups: list[
                    dict[str, Any]
                ] = []

                lifecycle_measurement_count = 0

                for group in (
                    lifecycle_groups.values()
                ):
                    points = sorted(
                        group["points"],
                        key=lambda item: (
                            item[0]
                        ),
                    )

                    if not points:
                        continue

                    group["points"] = points

                    lifecycle_measurement_count += (
                        len(points)
                    )

                    usable_lifecycle_groups.append(
                        group
                    )

                usable_lifecycle_groups.sort(
                    key=lambda group: (
                        group["points"][-1][0],
                        group["scraper_type"],
                        group["position_hint"],
                        group["cycle_id"],
                    ),
                    reverse=True,
                )

                if (
                    "lifecycle_trend"
                    in requested
                ):
                    if usable_lifecycle_groups:
                        answer_lines.extend(
                            [
                                "",
                                (
                                    "Lifecycle-trend: "
                                    f"{lifecycle_measurement_count} "
                                    "metingen verdeeld over "
                                    f"{len(usable_lifecycle_groups)} "
                                    "cycli."
                                ),
                            ]
                        )

                        for group in (
                            usable_lifecycle_groups
                        ):
                            points = (
                                group["points"]
                            )

                            (
                                first_date,
                                first_height,
                            ) = points[0]

                            (
                                last_date,
                                last_height,
                            ) = points[-1]

                            label_parts = [
                                group[
                                    "scraper_type"
                                ]
                            ]

                            if group[
                                "position_hint"
                            ]:
                                label_parts.append(
                                    group[
                                        "position_hint"
                                    ]
                                )

                            if group[
                                "cycle_id"
                            ]:
                                label_parts.append(
                                    (
                                        "cyclus "
                                        + group[
                                            "cycle_id"
                                        ]
                                    )
                                )

                            label = (
                                " - ".join(
                                    label_parts
                                )
                            )

                            if len(points) == 1:
                                detail = (
                                    "1 meting, "
                                    + last_date
                                    + " "
                                    + _format_mm(
                                        last_height
                                    )
                                    + " mm"
                                )
                            else:
                                detail = (
                                    str(
                                        len(points)
                                    )
                                    + " metingen, "
                                    + first_date
                                    + " "
                                    + _format_mm(
                                        first_height
                                    )
                                    + " mm -> "
                                    + last_date
                                    + " "
                                    + _format_mm(
                                        last_height
                                    )
                                    + " mm"
                                )

                            answer_lines.append(
                                (
                                    "- "
                                    + label
                                    + ": "
                                    + detail
                                )
                            )

                    else:
                        answer_lines.extend(
                            [
                                "",
                                (
                                    "Lifecycle-trend: "
                                    "niet beschikbaar "
                                    "in deze "
                                    "deep-analysisbron."
                                ),
                            ]
                        )

                if (
                    "replacement_events"
                    in requested
                ):
                    if lifecycle_available:
                        if (
                            lifecycle_replacement_dates
                        ):
                            answer_lines.extend(
                                [
                                    "",
                                    (
                                        "Geregistreerde "
                                        "vervangevents: "
                                        + ", ".join(
                                            sorted(
                                                lifecycle_replacement_dates
                                            )
                                        )
                                    ),
                                ]
                            )
                        else:
                            answer_lines.extend(
                                [
                                    "",
                                    (
                                        "Geregistreerde "
                                        "vervangevents: "
                                        "geen geregistreerd "
                                        "in de lifecycle."
                                    ),
                                ]
                            )
                    else:
                        answer_lines.extend(
                            [
                                "",
                                (
                                    "Geregistreerde "
                                    "vervangevents: "
                                    "niet beschikbaar "
                                    "in deze "
                                    "deep-analysisbron."
                                ),
                            ]
                        )

                if (
                    "uncertainties"
                    in requested
                ):
                    without_reliable_forecast = [
                        position
                        for position in positions
                        if not isinstance(
                            position[
                                "forecast"
                            ],
                            dict,
                        )
                    ]

                    answer_lines.extend(
                        [
                            "",
                            "Onzekerheden:",
                        ]
                    )

                    if (
                        without_reliable_forecast
                    ):
                        answer_lines.append(
                            (
                                "- Voor "
                                f"{len(without_reliable_forecast)} "
                                "van "
                                f"{len(positions)} "
                                "gepresenteerde posities "
                                "is geen betrouwbare "
                                "3 mm-forecast beschikbaar."
                            )
                        )
                    else:
                        answer_lines.append(
                            (
                                "- Voor alle "
                                "gepresenteerde posities "
                                "is volgens de huidige "
                                "forecastcriteria een "
                                "3 mm-prognose beschikbaar."
                            )
                        )

                    if lifecycle_available:
                        answer_lines.append(
                            (
                                "- Historische "
                                "lifecycle-posities worden "
                                "alleen gebruikt voor trend "
                                "en vervangevents; actuele "
                                "meshoogtes en vervangadvies "
                                "hierboven worden daar niet "
                                "uit afgeleid."
                            )
                        )
                    else:
                        answer_lines.append(
                            (
                                "- Lifecyclehistorie "
                                "ontbreekt in deze "
                                "deep-analysisresponse."
                            )
                        )

            return AssetBandDeepAnalysisAnswerStageResult(
                answer="\n".join(
                    answer_lines
                )
            )

    return AssetBandDeepAnalysisAnswerStageResult(answer=None)


__all__ = [
    "AssetBandDeepAnalysisAnswerStageResult",
    "run_asset_band_deep_analysis_answer_stage",
]
