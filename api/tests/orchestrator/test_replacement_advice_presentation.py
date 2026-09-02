from __future__ import annotations

from copy import deepcopy

from app.orchestrator.service import (
    _build_user_answer,
)


def _result():
    return [
        {
            "step_id": "step_1_inspection",
            "domain": "inspection",
            "action": "analysis_assistant",
            "endpoint": "/analysis/assistant/ask",
            "accepted": True,
            "result": {
                "intent": (
                    "band_deep_analysis"
                ),
                "kort_resultaat": (
                    "Generieke deep-analysis "
                    "samenvatting."
                ),
                "entities": {
                    "band_code": "A660",
                    "lijn_code": None,
                },
                "asset_context": {
                    "customer_code": (
                        "TATA_STEEL"
                    ),
                    "site_code": (
                        "IJMUIDEN"
                    ),
                    "area_code": "GSL",
                    "area_name": "GSL",
                    "installation_code": (
                        "SINTER"
                    ),
                    "installation_name": (
                        "Sinter"
                    ),
                    "band_code": "A660",
                    "band_code_norm": (
                        "A660"
                    ),
                    "band_code_display": (
                        "A660"
                    ),
                },
                "asset_resolution": {
                    "status": "resolved",
                    "match_count": 1,
                    "normalized_band_code": (
                        "A660"
                    ),
                    "normalized_installation_code": (
                        "SINTER"
                    ),
                },
                "gecombineerde_slijtage": [
                    {
                        "band_norm": "A660",
                        "position_display": (
                            "SUB_POSITION"
                        ),
                        "scraper_type_norm": (
                            "RI 1400-1350"
                        ),
                        "scraper_family": "R",
                        "meshoogte_mm": 5.0,
                        "onderhoudsadvies_unified": (
                            "VERVANGEN_VOORBEREIDEN"
                        ),
                        "laatste_inspectiedatum": (
                            "2026-05-05"
                        ),
                    },
                    {
                        "band_norm": "A660",
                        "position_display": (
                            "MIDDEN"
                        ),
                        "scraper_type_norm": (
                            "UI 1400"
                        ),
                        "scraper_family": "U",
                        "meshoogte_mm": 6.0,
                        "onderhoudsadvies_unified": (
                            "CONTROLEREN_BIJ_STOP"
                        ),
                        "laatste_inspectiedatum": (
                            "2026-05-05"
                        ),
                    },
                ],
                "forecast_3mm": [
                    {
                        "band_norm": (
                            "A660"
                        ),
                        "scraper_type_norm": (
                            "R 1400-1350 INOX"
                        ),
                        "position_hint": (
                            "POS A / SECUNDAIR"
                        ),
                        "cycle_end": (
                            "2026-05-05"
                        ),
                        "meetpunten": 7,
                        "eind_meshoogte_mm": (
                            5.0
                        ),
                        "slijtage_mm_per_dag": (
                            0.0117370892
                        ),
                        "geschatte_dagen_tot_3mm": (
                            170.4
                        ),
                        "geschatte_vervangdatum_bij_3mm": (
                            "2026-10-22"
                        ),
                    },
                    {
                        "band_norm": (
                            "A660"
                        ),
                        "scraper_type_norm": (
                            "U 1400 INOX"
                        ),
                        "position_hint": (
                            "POS A / SECUNDAIR / ZUID"
                        ),
                        "cycle_end": (
                            "2025-03-05"
                        ),
                        "meetpunten": 11,
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
                    },
                ],
            },
        }
    ]


def test_replacement_presentation_replaces_generic_summary():
    answer = _build_user_answer(
        _result()
    )

    assert answer is not None

    assert (
        "Vervangadvies:"
        in answer
    )

    assert (
        "Generieke deep-analysis"
        not in answer
    )


def test_five_mm_prepare_is_not_hard_replace():
    answer = _build_user_answer(
        _result()
    )

    assert answer is not None

    assert (
        "RI 1400-1350"
        in answer
    )

    assert (
        "Laatste gemeten meshoogte: "
        "5 mm op 2026-05-05"
        in answer
    )

    assert (
        "Advies: Vervanging voorbereiden"
        in answer
    )

    assert (
        "Advies: NU VERVANGEN"
        not in answer
    )


def test_reliable_r_forecast_is_shown():
    answer = _build_user_answer(
        _result()
    )

    assert answer is not None

    assert (
        "Prognose 3 mm: rond 2026-10-22"
        in answer
    )

    assert (
        "Onderbouwing: 7 meetpunten"
        in answer
    )


def test_incomplete_u_forecast_is_not_shown():
    answer = _build_user_answer(
        _result()
    )

    assert answer is not None

    ui_start = answer.index(
        "UI 1400"
    )

    ui_text = answer[
        ui_start:
    ]

    assert (
        "Advies: Controleren bij stop"
        in ui_text
    )

    assert (
        "Geen betrouwbare forecast beschikbaar"
        in ui_text
    )


def test_measured_three_mm_is_hard_replace():
    result = deepcopy(
        _result()
    )

    result[0]["result"][
        "gecombineerde_slijtage"
    ][0][
        "meshoogte_mm"
    ] = 3.0

    answer = _build_user_answer(
        result
    )

    assert answer is not None

    assert (
        "Advies: NU VERVANGEN"
        in answer
    )


def test_measured_below_three_mm_is_hard_replace():
    result = deepcopy(
        _result()
    )

    result[0]["result"][
        "gecombineerde_slijtage"
    ][0][
        "meshoogte_mm"
    ] = 2.5

    answer = _build_user_answer(
        result
    )

    assert answer is not None

    assert (
        "Advies: NU VERVANGEN"
        in answer
    )


def test_two_forecasts_same_family_fail_closed():
    result = deepcopy(
        _result()
    )

    extra = deepcopy(
        result[0]["result"][
            "forecast_3mm"
        ][0]
    )

    extra[
        "position_hint"
    ] = "ANDERE POSITIE"

    extra[
        "geschatte_vervangdatum_bij_3mm"
    ] = "2026-11-15"

    result[0]["result"][
        "forecast_3mm"
    ].append(
        extra
    )

    answer = _build_user_answer(
        result
    )

    assert answer is not None

    ri_start = answer.index(
        "RI 1400-1350"
    )

    ui_start = answer.index(
        "UI 1400"
    )

    ri_text = answer[
        ri_start:ui_start
    ]

    assert (
        "Geen betrouwbare forecast beschikbaar"
        in ri_text
    )


def test_warning_keeps_three_mm_semantics():
    answer = _build_user_answer(
        _result()
    )

    assert answer is not None

    assert (
        "3 mm is de vervanggrens"
        in answer
    )

    assert (
        "vervanging voorbereiden"
        in answer.lower()
    )