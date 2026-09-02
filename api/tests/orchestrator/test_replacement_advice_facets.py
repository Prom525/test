from __future__ import annotations

from copy import deepcopy

from app.orchestrator.service import (
    _build_user_answer,
)

from tests.orchestrator.test_replacement_advice_presentation import (
    _result,
)


COMPOSITE_FACETS = [
    "latest_measurements",
    "lifecycle_trend",
    "replacement_events",
    "replacement_advice",
    "uncertainties",
]


def _composite_result():
    result = deepcopy(
        _result()
    )

    result[0]["result"]["lifecycle"] = [
        {
            "inspected_on": "2026-05-05",
            "scraper_type_norm": (
                "R 1400-1350 INOX"
            ),
            "position_hint": "SECUNDAIR",
            "cycle_id": 1,
            "meshoogte_mm": 5.0,
            "replace_event": False,
            "canonical_inspection_key": (
                "R1-2026-05-05"
            ),
        },
        {
            "inspected_on": "2025-09-17",
            "scraper_type_norm": (
                "R 1400-1350 INOX"
            ),
            "position_hint": "SECUNDAIR",
            "cycle_id": 1,
            "meshoogte_mm": 8.0,
            "replace_event": False,
            "canonical_inspection_key": (
                "R1-2025-09-17"
            ),
        },
        {
            "inspected_on": "2025-03-05",
            "scraper_type_norm": (
                "R 1400-1350 INOX"
            ),
            "position_hint": "SECUNDAIR",
            "cycle_id": 1,
            "meshoogte_mm": 10.0,
            "replace_event": True,
            "canonical_inspection_key": (
                "R1-2025-03-05"
            ),
        },
        {
            "inspected_on": "2025-03-05",
            "scraper_type_norm": (
                "U 1400 INOX"
            ),
            "position_hint": "ZUID",
            "cycle_id": 6,
            "meshoogte_mm": None,
            "replace_event": False,
            "commentaar": (
                "Schraper verwijderd"
            ),
            "canonical_inspection_key": (
                "U6-2025-03-05"
            ),
        },
        {
            "inspected_on": "2024-12-03",
            "scraper_type_norm": (
                "U 1400 INOX"
            ),
            "position_hint": "ZUID",
            "cycle_id": 6,
            "meshoogte_mm": 5.0,
            "replace_event": False,
            "canonical_inspection_key": (
                "U6-2024-12-03"
            ),
        },
        {
            "inspected_on": "2023-12-05",
            "scraper_type_norm": (
                "U 1400 INOX"
            ),
            "position_hint": "ZUID",
            "cycle_id": 6,
            "meshoogte_mm": 10.0,
            "replace_event": True,
            "canonical_inspection_key": (
                "U6-2023-12-05"
            ),
        },
        {
            "inspected_on": "2023-10-09",
            "scraper_type_norm": (
                "U 1400 INOX"
            ),
            "position_hint": "ZUID",
            "cycle_id": 5,
            "meshoogte_mm": 6.0,
            "replace_event": False,
            "canonical_inspection_key": (
                "U5-2023-10-09"
            ),
        },
        {
            "inspected_on": "2023-09-12",
            "scraper_type_norm": (
                "U 1400 INOX"
            ),
            "position_hint": "ZUID",
            "cycle_id": 5,
            "meshoogte_mm": 8.0,
            "replace_event": False,
            "canonical_inspection_key": (
                "U5-2023-09-12"
            ),
        },
    ]

    return result


def test_pure_replacement_output_gets_no_extra_facets():
    answer = _build_user_answer(
        _result()
    )

    assert answer is not None

    assert "Lifecycle-trend:" not in answer

    assert (
        "Geregistreerde vervangevents:"
        not in answer
    )

    assert "Onzekerheden:" not in answer


def test_composite_keeps_current_measurements_and_advice():
    answer = _build_user_answer(
        _composite_result(),
        requested_information=(
            COMPOSITE_FACETS
        ),
    )

    assert answer is not None

    assert (
        "Laatste gemeten meshoogte: "
        "5 mm op 2026-05-05"
        in answer
    )

    assert (
        "Laatste gemeten meshoogte: "
        "6 mm op 2026-05-05"
        in answer
    )

    assert (
        "Advies: Vervanging voorbereiden"
        in answer
    )

    assert (
        "Prognose 3 mm: rond 2026-10-22"
        in answer
    )


def test_composite_adds_lifecycle_trend():
    answer = _build_user_answer(
        _composite_result(),
        requested_information=(
            COMPOSITE_FACETS
        ),
    )

    assert answer is not None

    assert (
        "Lifecycle-trend: "
        "7 metingen verdeeld over "
        "3 cycli."
        in answer
    )

    assert (
        "- R 1400-1350 INOX - "
        "SECUNDAIR - cyclus 1: "
        "3 metingen, "
        "2025-03-05 10 mm -> "
        "2026-05-05 5 mm"
        in answer
    )

    assert (
        "- U 1400 INOX - "
        "ZUID - cyclus 6: "
        "2 metingen, "
        "2023-12-05 10 mm -> "
        "2024-12-03 5 mm"
        in answer
    )


def test_composite_adds_replacement_events():
    answer = _build_user_answer(
        _composite_result(),
        requested_information=(
            COMPOSITE_FACETS
        ),
    )

    assert answer is not None

    assert (
        "Geregistreerde vervangevents: "
        "2023-12-05, 2025-03-05"
        in answer
    )


def test_uncertainties_are_concrete_and_source_bounded():
    answer = _build_user_answer(
        _composite_result(),
        requested_information=(
            COMPOSITE_FACETS
        ),
    )

    assert answer is not None

    assert "Onzekerheden:" in answer

    assert (
        "Voor 1 van 2 gepresenteerde "
        "posities is geen betrouwbare "
        "3 mm-forecast beschikbaar."
        in answer
    )

    assert (
        "Historische lifecycle-posities "
        "worden alleen gebruikt voor "
        "trend en vervangevents"
        in answer
    )

    lowered = answer.casefold()

    assert (
        "mogelijk band- of trommelconditie"
        not in lowered
    )


def test_historical_u_is_not_used_as_current_measurement():
    answer = _build_user_answer(
        _composite_result(),
        requested_information=(
            COMPOSITE_FACETS
        ),
    )

    assert answer is not None

    assert (
        "UI 1400"
        in answer
    )

    assert (
        "Laatste gemeten meshoogte: "
        "6 mm op 2026-05-05"
        in answer
    )

    assert (
        "U 1400 INOX - ZUID - cyclus 6"
        in answer
    )

    assert (
        "Laatste gemeten meshoogte: "
        "5 mm op 2024-12-03"
        not in answer
    )