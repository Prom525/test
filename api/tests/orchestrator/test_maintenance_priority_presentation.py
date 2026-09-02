from __future__ import annotations

from copy import deepcopy

from app.orchestrator.service import (
    _build_user_answer,
)


def _maintenance_results():
    return [
        {
            "action": (
                "analysis_assistant"
            ),
            "result": {
                "intent": (
                    "maintenance_positions"
                ),
                "kort_resultaat": (
                    "2 onderhoudsposities "
                    "gevonden."
                ),
                "asset_context": {
                    "customer_code": (
                        "TATA_STEEL"
                    ),
                    "site_code": "IJMUIDEN",
                    "area_code": "GSL",
                    "area_name": "GSL",
                    "installation_code": (
                        "SINTER"
                    ),
                    "installation_name": (
                        "Sinter"
                    ),
                    "band_code": "A660",
                    "band_code_norm": "A660",
                    "band_code_display": (
                        "A660"
                    ),
                },
                "asset_resolution": {
                    "status": "resolved",
                    "match_count": 1,
                },
                "resultaat": [
                    {
                        "lijn_code": "GSL",
                        "band_norm": "A660",
                        "position_hint": (
                            "POS A / SECUNDAIR"
                        ),
                        "scraper_types": (
                            "R 1400-1350 INOX"
                        ),
                        "scraper_types_clean": (
                            "R 1400-1350 INOX"
                        ),
                        "cycle_start": (
                            "2025-03-05"
                        ),
                        "cycle_end": (
                            "2026-05-05"
                        ),
                        "meetpunten": 7,
                        "start_meshoogte_mm": (
                            10.0
                        ),
                        "eind_meshoogte_mm": (
                            5.0
                        ),
                        "slijtage_mm_per_dag": (
                            0.0117
                        ),
                        "geschatte_dagen_tot_3mm": (
                            170.4
                        ),
                        "geschatte_vervangdatum_bij_3mm": (
                            "2026-10-22"
                        ),
                        "status_3mm": "OK",
                        "prioriteit": 4,
                        "prestatiegrens_mm": (
                            6
                        ),
                        "vervanggrens_mm": (
                            3
                        ),
                        "status_6mm": (
                            "OP_OF_ONDER_6MM"
                        ),
                        "vervuilingsrisico": (
                            True
                        ),
                        "prestatie_vervangmoment": (
                            "CONTROLEREN_"
                            "PRESTATIEGRENS"
                        ),
                    },
                    {
                        "lijn_code": "GSL",
                        "band_norm": "A660",
                        "position_hint": (
                            "POS A / "
                            "SECUNDAIR / ZUID"
                        ),
                        "scraper_types": (
                            "U 1400 INOX"
                        ),
                        "scraper_types_clean": (
                            "U 1400 INOX"
                        ),
                        "cycle_start": (
                            "2023-12-05"
                        ),
                        "cycle_end": (
                            "2025-03-05"
                        ),
                        "meetpunten": 11,
                        "start_meshoogte_mm": (
                            10.0
                        ),
                        "eind_meshoogte_mm": (
                            None
                        ),
                        "slijtage_mm_per_dag": (
                            None
                        ),
                        "geschatte_dagen_tot_3mm": (
                            None
                        ),
                        "geschatte_vervangdatum_bij_3mm": (
                            None
                        ),
                        "status_3mm": (
                            "CHECK_TREND"
                        ),
                        "prioriteit": 10,
                        "prestatiegrens_mm": (
                            6
                        ),
                        "vervanggrens_mm": (
                            3
                        ),
                        "status_6mm": (
                            "ONBEKEND"
                        ),
                        "vervuilingsrisico": (
                            False
                        ),
                        "prestatie_vervangmoment": (
                            None
                        ),
                    },
                ],
            },
        }
    ]


def test_maintenance_presentation_orders_by_priority():
    answer = _build_user_answer(
        _maintenance_results()
    )

    assert answer is not None

    r_index = answer.index(
        "1. R 1400-1350 INOX"
    )

    u_index = answer.index(
        "2. U 1400 INOX"
    )

    assert r_index < u_index


def test_r_position_shows_measurement_action_and_forecast():
    answer = _build_user_answer(
        _maintenance_results()
    )

    assert answer is not None

    assert (
        "Laatste gemeten meshoogte: "
        "5 mm op 2026-05-05"
        in answer
    )

    assert (
        "Actie: Prestatiegrens controleren"
        in answer
    )

    assert (
        "Prognose 3 mm: rond 2026-10-22"
        in answer
    )

    assert (
        "Onderbouwing: 7 meetpunten"
        in answer
    )


def test_u_position_does_not_invent_measurement_or_forecast():
    answer = _build_user_answer(
        _maintenance_results()
    )

    assert answer is not None

    u_section = answer.split(
        "2. U 1400 INOX",
        1,
    )[1]

    assert (
        "Laatste gemeten meshoogte: "
        "niet beschikbaar"
        in u_section
    )

    assert (
        "Actie: Trend controleren; "
        "geen bruikbare actuele eindmeting"
        in u_section
    )

    assert (
        "Geen betrouwbare forecast beschikbaar"
        in u_section
    )


def test_measured_three_mm_or_less_means_replace_now():
    results = (
        _maintenance_results()
    )

    row = (
        results[0]["result"][
            "resultaat"
        ][0]
    )

    row[
        "eind_meshoogte_mm"
    ] = 3.0

    answer = _build_user_answer(
        results
    )

    assert answer is not None

    assert (
        "Actie: NU VERVANGEN"
        in answer
    )


def test_forecast_requires_at_least_three_points():
    results = (
        _maintenance_results()
    )

    row = (
        results[0]["result"][
            "resultaat"
        ][0]
    )

    row["meetpunten"] = 2

    answer = _build_user_answer(
        results
    )

    assert answer is not None

    r_section = answer.split(
        "1. R 1400-1350 INOX",
        1,
    )[1].split(
        "2. U 1400 INOX",
        1,
    )[0]

    assert (
        "Geen betrouwbare forecast beschikbaar"
        in r_section
    )

    assert (
        "Prognose 3 mm:"
        not in r_section
    )


def test_duplicate_position_is_deduplicated():
    results = (
        _maintenance_results()
    )

    duplicate = deepcopy(
        results[0]["result"][
            "resultaat"
        ][0]
    )

    results[0]["result"][
        "resultaat"
    ].append(
        duplicate
    )

    answer = _build_user_answer(
        results
    )

    assert answer is not None

    assert (
        answer.count(
            "R 1400-1350 INOX"
        )
        == 1
    )


def test_boundary_explanation_is_present():
    answer = _build_user_answer(
        _maintenance_results()
    )

    assert answer is not None

    assert (
        "3 mm is de vervanggrens"
        in answer
    )

    assert (
        "6 mm-grens is een "
        "prestatiecontrole"
        in answer
    )


def test_generic_asset_fallback_remains_unchanged():
    results = [
        {
            "action": (
                "other_asset_assistant"
            ),
            "result": {
                "asset_context": {
                    "customer_code": (
                        "TEST"
                    ),
                    "site_code": "SITE",
                    "area_code": "AREA",
                    "area_name": "Area",
                    "installation_code": (
                        "INST"
                    ),
                    "installation_name": (
                        "Installation"
                    ),
                    "band_code": "B100",
                    "band_code_norm": (
                        "B100"
                    ),
                    "band_code_display": (
                        "B100"
                    ),
                },
                "asset_resolution": {
                    "status": "resolved",
                    "match_count": 1,
                },
                "kort_resultaat": (
                    "Bestaand generiek "
                    "resultaat."
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