from __future__ import annotations

from copy import deepcopy

from app.orchestrator.service import (
    _build_user_answer,
)


def _result():
    return [
        {
            "action": "analysis_assistant",
            "result": {
                "intent": "lifecycle",
                "kort_resultaat": (
                    "6 lifecycle-regels gevonden."
                ),
                "asset_context": {
                    "customer_code": "TATA_STEEL",
                    "site_code": "IJMUIDEN",
                    "area_code": "GSL",
                    "area_name": "GSL",
                    "installation_code": "SINTER",
                    "installation_name": "Sinter",
                    "band_code": "A660",
                    "band_code_norm": "A660",
                    "band_code_display": "A660",
                },
                "asset_resolution": {
                    "status": "resolved",
                    "match_count": 1,
                },
                "resultaat": [
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
                        "inspected_on": "2026-03-10",
                        "scraper_type_norm": (
                            "R 1400-1350 INOX"
                        ),
                        "position_hint": "SECUNDAIR",
                        "cycle_id": 1,
                        "meshoogte_mm": 6.0,
                        "replace_event": False,
                        "canonical_inspection_key": (
                            "R1-2026-03-10"
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
                ],
            },
        }
    ]


def test_trend_presentation_groups_by_scraper_and_cycle():
    answer = _build_user_answer(
        _result()
    )

    assert answer is not None

    assert (
        "Trendgegevens: 7 metingen "
        "verdeeld over 3 cycli."
        in answer
    )

    assert (
        "- R 1400-1350 INOX — SECUNDAIR — cyclus 1: "
        "3 metingen, "
        "2025-03-05 10 mm → "
        "2026-05-05 5 mm"
        in answer
    )

    assert (
        "- U 1400 INOX — ZUID — cyclus 6: "
        "2 metingen, "
        "2023-12-05 10 mm → "
        "2024-12-03 5 mm"
        in answer
    )

    assert (
        "- U 1400 INOX — ZUID — cyclus 5: "
        "2 metingen, "
        "2023-09-12 8 mm → "
        "2023-10-09 6 mm"
        in answer
    )


def test_trend_presentation_keeps_cycles_separate():
    answer = _build_user_answer(
        _result()
    )

    assert answer is not None

    assert answer.count(
        "U 1400 INOX — ZUID"
    ) == 2

    assert "cyclus 5" in answer
    assert "cyclus 6" in answer


def test_trend_presentation_deduplicates_measurements():
    results = _result()

    duplicate = deepcopy(
        results[0]["result"]["resultaat"][0]
    )

    results[0]["result"]["resultaat"].append(
        duplicate
    )

    answer = _build_user_answer(results)

    assert answer is not None

    assert (
        "Trendgegevens: 7 metingen "
        "verdeeld over 3 cycli."
        in answer
    )


def test_trend_presentation_lists_replacement_dates():
    answer = _build_user_answer(
        _result()
    )

    assert answer is not None

    assert (
        "Geregistreerde vervangevents: "
        "2023-12-05, 2025-03-05"
        in answer
    )


def test_trend_presentation_does_not_claim_forecast():
    answer = _build_user_answer(
        _result()
    )

    assert answer is not None

    lowered = answer.casefold()

    assert "forecast" not in lowered
    assert "verwachte vervanging" not in lowered
    assert "dagen resterend" not in lowered


def test_generic_asset_fallback_stays_unchanged():
    results = [
        {
            "action": "other_asset_assistant",
            "result": {
                "asset_context": {
                    "customer_code": "TEST",
                    "site_code": "SITE",
                    "area_code": "AREA",
                    "area_name": "Area",
                    "installation_code": "INST",
                    "installation_name": (
                        "Installation"
                    ),
                    "band_code": "B100",
                    "band_code_norm": "B100",
                    "band_code_display": "B100",
                },
                "asset_resolution": {
                    "status": "resolved",
                    "match_count": 1,
                },
                "kort_resultaat": (
                    "Bestaand generiek resultaat."
                ),
            },
        }
    ]

    answer = _build_user_answer(
        results
    )

    assert answer == (
        "Klant: TEST\n"
        "Plaats: SITE\n"
        "Gebied: Area\n"
        "Installatie: Installation (INST)\n"
        "Bandnummer: B100\n"
        "\n"
        "Bestaand generiek resultaat."
    )