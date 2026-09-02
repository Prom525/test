from __future__ import annotations

from typing import Any


PUBLIC_PROFILE = (
    "compact_specialist_results_v1"
)


def _copy_keys(
    source: dict[str, Any],
    keys: tuple[str, ...],
) -> dict[str, Any]:
    return {
        key: source[key]
        for key in keys
        if key in source
    }


def _project_rows(
    value: Any,
    keys: tuple[str, ...],
) -> Any:
    if not isinstance(value, list):
        return value

    projected: list[Any] = []

    for row in value:
        if isinstance(row, dict):
            projected.append(
                _copy_keys(
                    row,
                    keys,
                )
            )
        else:
            projected.append(row)

    return projected


_CURRENT_POSITION_FIELDS = (
    "lijn_code",
    "band_norm",
    "position_display",
    "position_key_unified",
    "scraper_type_norm",
    "scraper_family",
    "scraper_material",
    "scraper_variant",
    "analyse_basis",
    "meshoogte_mm",
    "conditie_code",
    "mes_interpretatie",
    "slijtage_actie_pct",
    "betrouwbaarheid",
    "laatste_vervanging_datum",
    "replace_event",
    "planned_replace_signal",
    "mechanical_or_access_signal",
    "commentaar",
    "laatste_inspectiedatum",
    "row_nr",
    "inspection_key",
    "onderhoudsadvies_unified",
    "laatste_waarde_display",
)


_LIFECYCLE_FIELDS = (
    "inspected_on",
    "lijn_code",
    "band_norm",
    "scraper_type_norm",
    "scraper_role",
    "physical_position_label_final",
    "position_hint",
    "meshoogte_mm",
    "replace_event",
    "cycle_id",
    "commentaar",
    "canonical_inspection_key",
)


_INSPECTION_SUMMARY_FIELDS = (
    "inspection_key",
    "document_date",
    "line_hint",
    "band_code",
    "locatie_raw",
    "scraper_type_raw",
    "band_width_mm",
    "meshoogte_mm",
    "meshoogte_code",
    "mes_vervangen",
    "commentaar",
    "status",
    "source_system",
    "provenance_basis",
)


def _compact_band_deep_analysis(
    result: dict[str, Any],
    requested: set[str],
) -> dict[str, Any]:
    compact = _copy_keys(
        result,
        (
            "intent",
            "entities",
            "kort_resultaat",
            "gecombineerde_slijtage_samenvatting",
            "ongewone_slijtage",
            "mogelijke_oorzaak",
            "uitleg_gecombineerde_slijtage",
            "actie",
            "asset_context",
            "asset_resolution",
        ),
    )

    compact["public_profile"] = (
        PUBLIC_PROFILE
    )

    if "gecombineerde_slijtage" in result:
        compact[
            "gecombineerde_slijtage"
        ] = _project_rows(
            result.get(
                "gecombineerde_slijtage"
            ),
            _CURRENT_POSITION_FIELDS,
        )

    # P1.3 canonical projection is bewust de
    # publieke bron voor current<->history<->forecast
    # koppelingen. Niet verder reduceren.
    if "canonical_positions" in result:
        compact[
            "canonical_positions"
        ] = result.get(
            "canonical_positions"
        )

    lifecycle_requested = (
        "lifecycle_trend" in requested
    )

    replacement_events_requested = (
        "replacement_events" in requested
    )

    raw_lifecycle = result.get(
        "lifecycle"
    )

    if (
        lifecycle_requested
        and isinstance(
            raw_lifecycle,
            list,
        )
    ):
        compact["lifecycle"] = (
            _project_rows(
                raw_lifecycle,
                _LIFECYCLE_FIELDS,
            )
        )

    elif (
        replacement_events_requested
        and isinstance(
            raw_lifecycle,
            list,
        )
    ):
        replacement_rows = [
            row
            for row in raw_lifecycle
            if (
                isinstance(row, dict)
                and row.get(
                    "replace_event"
                )
                is True
            )
        ]

        compact["lifecycle"] = (
            _project_rows(
                replacement_rows,
                _LIFECYCLE_FIELDS,
            )
        )

    return compact


def _compact_inspection_summary(
    result: dict[str, Any],
) -> dict[str, Any]:
    compact = _copy_keys(
        result,
        (
            "intent",
            "entities",
            "kort_resultaat",
            "summary",
            "total_count",
            "count_semantics",
            "evidence_document_semantics",
            "data_quality",
            "resultaat_count",
            "asset_context",
            "asset_resolution",
        ),
    )

    compact["public_profile"] = (
        PUBLIC_PROFILE
    )

    if "resultaat" in result:
        compact["resultaat"] = (
            _project_rows(
                result.get("resultaat"),
                _INSPECTION_SUMMARY_FIELDS,
            )
        )

    return compact


def _compact_lifecycle(
    result: dict[str, Any],
) -> dict[str, Any]:
    compact = _copy_keys(
        result,
        (
            "intent",
            "kort_resultaat",
            "trend_patronen",
            "asset_context",
            "asset_resolution",
        ),
    )

    compact["public_profile"] = (
        PUBLIC_PROFILE
    )

    if "resultaat" in result:
        compact["resultaat"] = (
            _project_rows(
                result.get("resultaat"),
                _LIFECYCLE_FIELDS,
            )
        )

    return compact


def compact_results_for_public_response(
    results: Any,
    *,
    requested_information: (
        list[str] | None
    ) = None,
) -> Any:
    """
    Projecteer alleen publieke specialist-results.

    Intern blijven de oorspronkelijke results volledig
    beschikbaar voor presentation, evidence en trace.

    Onbekende result-intents blijven fail-open ongewijzigd.
    """
    if not isinstance(results, list):
        return results

    requested = {
        str(item).strip().casefold()
        for item
        in (
            requested_information
            or []
        )
        if str(item).strip()
    }

    projected_results: list[Any] = []

    for item in results:
        if not isinstance(item, dict):
            projected_results.append(item)
            continue

        projected_item = dict(item)

        result = item.get("result")

        if not isinstance(result, dict):
            projected_results.append(
                projected_item
            )
            continue

        intent = str(
            result.get("intent")
            or ""
        ).strip()

        if intent == "band_deep_analysis":
            projected_item["result"] = (
                _compact_band_deep_analysis(
                    result,
                    requested,
                )
            )

        elif intent == "inspection_summary":
            projected_item["result"] = (
                _compact_inspection_summary(
                    result
                )
            )

        elif intent == "lifecycle":
            projected_item["result"] = (
                _compact_lifecycle(
                    result
                )
            )

        else:
            # Fail-open: geen contractwijziging voor
            # nog niet geprofileerde specialists.
            projected_item["result"] = (
                result
            )

        projected_results.append(
            projected_item
        )

    return projected_results
