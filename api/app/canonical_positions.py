from __future__ import annotations

import re
from typing import Any


CONTRACT_VERSION = (
    "promati.canonical_position_projection.v1"
)

MATCHED = "MATCHED"
UNLINKED = "UNLINKED"
AMBIGUOUS = "AMBIGUOUS"


_NON_SPECIFIC_CURRENT_POSITIONS = frozenset(
    {
        "",
        "SUB POSITION",
        "GEEN POSITIE",
        "ONBEKEND",
        "UNKNOWN",
        "NONE",
        "NULL",
    }
)


def _text(value: Any) -> str | None:
    if value is None:
        return None

    value = str(value).strip()

    return value or None


def _norm_code(value: Any) -> str | None:
    value = _text(value)

    if value is None:
        return None

    return re.sub(
        r"\s+",
        "",
        value.upper(),
    )


def _norm_position(value: Any) -> str | None:
    value = _text(value)

    if value is None:
        return None

    return re.sub(
        r"[\s_-]+",
        " ",
        value.upper(),
    ).strip()


def _number(value: Any) -> float | None:
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _same_number(
    left: Any,
    right: Any,
) -> bool:
    left_num = _number(left)
    right_num = _number(right)

    if (
        left_num is None
        or right_num is None
    ):
        return False

    return abs(
        left_num - right_num
    ) <= 0.001


def _identity_field_compatible(
    left: Any,
    right: Any,
) -> bool:
    left_norm = _norm_code(left)
    right_norm = _norm_code(right)

    if (
        left_norm is None
        or right_norm is None
    ):
        return True

    return left_norm == right_norm


def _current_position_is_specific(
    value: Any,
) -> bool:
    norm = _norm_position(value)

    if norm is None:
        return False

    return (
        norm
        not in _NON_SPECIFIC_CURRENT_POSITIONS
    )


def _historical_position(
    row: dict[str, Any],
) -> Any:
    return (
        row.get(
            "physical_position_label_final"
        )
        or row.get("position_hint")
        or row.get("scraper_role")
    )


def _positions_compatible(
    current_row: dict[str, Any],
    lifecycle_row: dict[str, Any],
) -> bool:
    current_position = current_row.get(
        "position_display"
    )

    if not _current_position_is_specific(
        current_position
    ):
        return True

    historical_position = (
        _historical_position(
            lifecycle_row
        )
    )

    historical_norm = _norm_position(
        historical_position
    )

    if historical_norm is None:
        return False

    return (
        _norm_position(current_position)
        == historical_norm
    )


def _leading_alpha_token(
    value: Any,
) -> str | None:
    value = _text(value)

    if value is None:
        return None

    match = re.match(
        r"\s*([A-Za-z]+)",
        value,
    )

    if match is None:
        return None

    return match.group(1).upper()


def _families_compatible(
    current_row: dict[str, Any],
    lifecycle_row: dict[str, Any],
) -> bool:
    current_family = _text(
        current_row.get("scraper_family")
    )

    if current_family is None:
        return True

    current_family = (
        current_family
        .upper()
        .replace(" ", "")
    )

    explicit_historical_family = _text(
        lifecycle_row.get("scraper_family")
    )

    if explicit_historical_family:
        return (
            current_family
            == explicit_historical_family
            .upper()
            .replace(" ", "")
        )

    historical_token = (
        _leading_alpha_token(
            lifecycle_row.get(
                "scraper_type_norm"
            )
        )
    )

    if historical_token is None:
        return False

    return historical_token.startswith(
        current_family
    )


def _lifecycle_candidates(
    current_row: dict[str, Any],
    lifecycle_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    inspection_key = _text(
        current_row.get("inspection_key")
    )

    current_mm = _number(
        current_row.get("meshoogte_mm")
    )

    if (
        inspection_key is None
        or current_mm is None
    ):
        return []

    candidates: list[dict[str, Any]] = []

    for row in lifecycle_rows:
        if (
            _text(
                row.get(
                    "canonical_inspection_key"
                )
            )
            != inspection_key
        ):
            continue

        if not _same_number(
            current_mm,
            row.get("meshoogte_mm"),
        ):
            continue

        if not _identity_field_compatible(
            current_row.get("band_norm"),
            row.get("band_norm"),
        ):
            continue

        if not _identity_field_compatible(
            current_row.get("lijn_code"),
            row.get("lijn_code"),
        ):
            continue

        if not _families_compatible(
            current_row,
            row,
        ):
            continue

        if not _positions_compatible(
            current_row,
            row,
        ):
            continue

        candidates.append(row)

    return candidates


def _forecast_candidates(
    lifecycle_row: dict[str, Any],
    forecast_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    lifecycle_key = _text(
        lifecycle_row.get(
            "canonical_inspection_key"
        )
    )

    lifecycle_type = _text(
        lifecycle_row.get(
            "scraper_type_norm"
        )
    )

    lifecycle_date = _text(
        lifecycle_row.get("inspected_on")
    )

    if (
        lifecycle_key is None
        or lifecycle_type is None
    ):
        return []

    candidates: list[dict[str, Any]] = []

    for row in forecast_rows:
        if (
            _text(
                row.get(
                    "last_canonical_inspection_key"
                )
            )
            != lifecycle_key
        ):
            continue

        if (
            _text(
                row.get("scraper_type_norm")
            )
            != lifecycle_type
        ):
            continue

        if not _identity_field_compatible(
            lifecycle_row.get("band_norm"),
            row.get("band_norm"),
        ):
            continue

        if not _identity_field_compatible(
            lifecycle_row.get("lijn_code"),
            row.get("lijn_code"),
        ):
            continue

        cycle_end = _text(
            row.get("cycle_end")
        )

        if (
            lifecycle_date is not None
            and cycle_end is not None
            and lifecycle_date != cycle_end
        ):
            continue

        candidates.append(row)

    return candidates


def _match_basis(
    current_row: dict[str, Any],
    lifecycle_row: dict[str, Any],
) -> list[str]:
    basis = [
        "canonical_inspection_key",
        "meshoogte_mm",
    ]

    if (
        current_row.get("band_norm")
        and lifecycle_row.get("band_norm")
    ):
        basis.append("band_norm")

    if (
        current_row.get("lijn_code")
        and lifecycle_row.get("lijn_code")
    ):
        basis.append("lijn_code")

    if current_row.get("scraper_family"):
        basis.append("scraper_family")

    if _current_position_is_specific(
        current_row.get("position_display")
    ):
        basis.append(
            "physical_position_label"
        )

    return basis


def _match_confidence(
    current_row: dict[str, Any],
) -> str:
    if _current_position_is_specific(
        current_row.get("position_display")
    ):
        return "HIGH"

    return "MEDIUM"


def _empty_forecast(
    reason: str,
) -> dict[str, Any]:
    return {
        "link_status": UNLINKED,
        "linked": False,
        "reason": reason,
        "candidate_count": 0,
        "reliable": False,
        "forecast_date": None,
        "measurement_count": None,
    }



# PROMATI_CANONICAL_POSITION_ONE_TO_ONE_V1
def _historical_identity_key(
    position: dict[str, Any],
) -> tuple[Any, ...] | None:
    historical = position.get(
        "historical_link",
        {},
    )

    if historical.get("status") != MATCHED:
        return None

    return (
        _text(
            historical.get(
                "canonical_inspection_key"
            )
        ),
        _text(
            historical.get(
                "lifecycle_scraper_type"
            )
        ),
        _text(
            historical.get(
                "scraper_role"
            )
        ),
        _text(
            historical.get(
                "physical_position_label"
            )
        ),
        _text(
            historical.get(
                "position_hint"
            )
        ),
        historical.get("cycle_id"),
        _text(
            historical.get(
                "matched_measurement_date"
            )
        ),
        _number(
            historical.get(
                "matched_meshoogte_mm"
            )
        ),
    )


def _downgrade_many_to_one_collisions(
    positions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    groups: dict[
        tuple[Any, ...],
        list[int],
    ] = {}

    for index, position in enumerate(
        positions
    ):
        identity = _historical_identity_key(
            position
        )

        if identity is None:
            continue

        groups.setdefault(
            identity,
            [],
        ).append(index)

    for indexes in groups.values():
        if len(indexes) <= 1:
            continue

        collision_count = len(indexes)

        for index in indexes:
            position = positions[index]

            historical = position[
                "historical_link"
            ]

            historical.update(
                {
                    "status": AMBIGUOUS,
                    "match_confidence": "LOW",
                    "reason": (
                        "many_current_entities_"
                        "share_lifecycle_identity"
                    ),
                    "collision_current_count": (
                        collision_count
                    ),
                    "lifecycle_scraper_type": None,
                    "scraper_role": None,
                    "physical_position_label": None,
                    "position_hint": None,
                    "cycle_id": None,
                    "canonical_inspection_key": None,
                    "matched_measurement_date": None,
                    "matched_meshoogte_mm": None,
                }
            )

            position["forecast"] = (
                _empty_forecast(
                    "historical_link_"
                    "many_to_one_ambiguous"
                )
            )

    return positions


def build_canonical_position_projection(
    *,
    current_rows: list[dict[str, Any]],
    lifecycle_rows: list[dict[str, Any]],
    forecast_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    positions: list[dict[str, Any]] = []

    for current_row in current_rows:
        lifecycle_candidates = (
            _lifecycle_candidates(
                current_row,
                lifecycle_rows,
            )
        )

        historical_link: dict[str, Any]
        forecast_link: dict[str, Any]

        if len(lifecycle_candidates) == 0:
            reason = (
                "insufficient_current_identity"
                if (
                    not current_row.get(
                        "inspection_key"
                    )
                    or _number(
                        current_row.get(
                            "meshoogte_mm"
                        )
                    )
                    is None
                )
                else "no_exact_lifecycle_match"
            )

            historical_link = {
                "status": UNLINKED,
                "match_confidence": "NONE",
                "match_basis": [],
                "reason": reason,
                "candidate_count": 0,
                "lifecycle_scraper_type": None,
                "scraper_role": None,
                "physical_position_label": None,
                "cycle_id": None,
                "canonical_inspection_key": None,
                "matched_measurement_date": None,
                "matched_meshoogte_mm": None,
            }

            forecast_link = _empty_forecast(
                "historical_link_not_matched"
            )

        elif len(lifecycle_candidates) > 1:
            historical_link = {
                "status": AMBIGUOUS,
                "match_confidence": "LOW",
                "match_basis": [
                    "canonical_inspection_key",
                    "meshoogte_mm",
                ],
                "reason": (
                    "multiple_exact_lifecycle_candidates"
                ),
                "candidate_count": len(
                    lifecycle_candidates
                ),
                "lifecycle_scraper_type": None,
                "scraper_role": None,
                "physical_position_label": None,
                "cycle_id": None,
                "canonical_inspection_key": None,
                "matched_measurement_date": None,
                "matched_meshoogte_mm": None,
            }

            forecast_link = _empty_forecast(
                "historical_link_ambiguous"
            )

        else:
            lifecycle_row = (
                lifecycle_candidates[0]
            )

            historical_link = {
                "status": MATCHED,
                "match_confidence": (
                    _match_confidence(
                        current_row
                    )
                ),
                "match_basis": _match_basis(
                    current_row,
                    lifecycle_row,
                ),
                "reason": None,
                "candidate_count": 1,
                "lifecycle_scraper_type": (
                    lifecycle_row.get(
                        "scraper_type_norm"
                    )
                ),
                "scraper_role": (
                    lifecycle_row.get(
                        "scraper_role"
                    )
                ),
                "physical_position_label": (
                    lifecycle_row.get(
                        "physical_position_label_final"
                    )
                ),
                "position_hint": (
                    lifecycle_row.get(
                        "position_hint"
                    )
                ),
                "cycle_id": (
                    lifecycle_row.get(
                        "cycle_id"
                    )
                ),
                "canonical_inspection_key": (
                    lifecycle_row.get(
                        "canonical_inspection_key"
                    )
                ),
                "matched_measurement_date": (
                    lifecycle_row.get(
                        "inspected_on"
                    )
                ),
                "matched_meshoogte_mm": (
                    lifecycle_row.get(
                        "meshoogte_mm"
                    )
                ),
            }

            forecast_candidates = (
                _forecast_candidates(
                    lifecycle_row,
                    forecast_rows,
                )
            )

            if len(forecast_candidates) == 0:
                forecast_link = _empty_forecast(
                    "no_exact_forecast_match"
                )

            elif len(forecast_candidates) > 1:
                forecast_link = {
                    "link_status": AMBIGUOUS,
                    "linked": False,
                    "reason": (
                        "multiple_exact_forecast_candidates"
                    ),
                    "candidate_count": len(
                        forecast_candidates
                    ),
                    "reliable": False,
                    "forecast_date": None,
                    "measurement_count": None,
                }

            else:
                forecast_row = (
                    forecast_candidates[0]
                )

                measurement_count = (
                    forecast_row.get(
                        "meetpunten"
                    )
                )

                try:
                    reliable = (
                        int(measurement_count)
                        >= 3
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    reliable = False

                forecast_link = {
                    "link_status": MATCHED,
                    "linked": True,
                    "reason": None,
                    "candidate_count": 1,
                    "reliable": reliable,
                    "measurement_count": (
                        measurement_count
                    ),
                    "cycle_start": (
                        forecast_row.get(
                            "cycle_start"
                        )
                    ),
                    "cycle_end": (
                        forecast_row.get(
                            "cycle_end"
                        )
                    ),
                    "forecast_date": (
                        forecast_row.get(
                            "geschatte_vervangdatum_bij_3mm"
                        )
                        if reliable
                        else None
                    ),
                    "status_3mm": (
                        forecast_row.get(
                            "status_3mm"
                        )
                    ),
                    "slijtage_mm_per_dag": (
                        forecast_row.get(
                            "slijtage_mm_per_dag"
                        )
                    ),
                    "last_canonical_inspection_key": (
                        forecast_row.get(
                            "last_canonical_inspection_key"
                        )
                    ),
                }

        positions.append(
            {
                "contract_version": (
                    CONTRACT_VERSION
                ),
                "source_row_identity": {
                    "inspection_key": (
                        current_row.get(
                            "inspection_key"
                        )
                    ),
                    "row_nr": (
                        current_row.get(
                            "row_nr"
                        )
                    ),
                },
                "current_state": {
                    "lijn_code": (
                        current_row.get(
                            "lijn_code"
                        )
                    ),
                    "band_norm": (
                        current_row.get(
                            "band_norm"
                        )
                    ),
                    "current_position_key": (
                        current_row.get(
                            "position_key_unified"
                        )
                    ),
                    "current_position_display": (
                        current_row.get(
                            "position_display"
                        )
                    ),
                    "scraper_type_current": (
                        current_row.get(
                            "scraper_type_norm"
                        )
                    ),
                    "scraper_family": (
                        current_row.get(
                            "scraper_family"
                        )
                    ),
                    "scraper_material": (
                        current_row.get(
                            "scraper_material"
                        )
                    ),
                    "current_meshoogte_mm": (
                        current_row.get(
                            "meshoogte_mm"
                        )
                    ),
                    "current_inspection_date": (
                        current_row.get(
                            "laatste_inspectiedatum"
                        )
                    ),
                },
                "historical_link": (
                    historical_link
                ),
                "forecast": forecast_link,
            }
        )

    return _downgrade_many_to_one_collisions(
        positions
    )
