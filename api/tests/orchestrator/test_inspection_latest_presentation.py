from __future__ import annotations

from app.orchestrator.service import (
    _build_user_answer,
)


def _inspection_result(
    *,
    replacement_ri=False,
    replacement_ui=False,
):
    return [
        {
            "step_id": "step_1_inspection",
            "domain": "inspection",
            "action": "analysis_assistant",
            "endpoint": "/analysis/assistant/ask",
            "accepted": True,
            "result": {
                "intent": "inspection_summary",
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
                "kort_resultaat": (
                    "1084 inspectie-factregels gevonden."
                ),
                "resultaat": [
                    {
                        "inspection_key": (
                            "TATA|A660|2026-05-05"
                        ),
                        "document_date": "2026-05-05",
                        "band_code": "A660",
                        "locatie_raw": None,
                        "scraper_type_raw": (
                            "RI 1400-1350"
                        ),
                        "meshoogte_mm": 5,
                        "mes_vervangen": replacement_ri,
                        "check_code": (
                            "afdichting_stortpunt"
                        ),
                        "status": "DONE",
                    },
                    {
                        "inspection_key": (
                            "TATA|A660|2026-05-05"
                        ),
                        "document_date": "2026-05-05",
                        "band_code": "A660",
                        "locatie_raw": None,
                        "scraper_type_raw": (
                            "RI 1400-1350"
                        ),
                        "meshoogte_mm": 5,
                        "mes_vervangen": replacement_ri,
                        "check_code": (
                            "werking_schrapers"
                        ),
                        "status": "DONE",
                    },
                    {
                        "inspection_key": (
                            "TATA|A660|2026-05-05"
                        ),
                        "document_date": "2026-05-05",
                        "band_code": "A660",
                        "locatie_raw": "Kap Br.1700",
                        "scraper_type_raw": (
                            "UI 140 midden"
                        ),
                        "meshoogte_mm": 6,
                        "mes_vervangen": replacement_ui,
                        "check_code": (
                            "afdichting_stortpunt"
                        ),
                        "status": "DONE",
                    },
                    {
                        "inspection_key": (
                            "TATA|A660|2026-03-10"
                        ),
                        "document_date": "2026-03-10",
                        "band_code": "A660",
                        "locatie_raw": None,
                        "scraper_type_raw": (
                            "RI 1400-1350"
                        ),
                        "meshoogte_mm": 7,
                        "mes_vervangen": False,
                        "check_code": (
                            "werking_schrapers"
                        ),
                        "status": "DONE",
                    },
                ],
            },
        }
    ]


def test_inspection_latest_presentation_contains_latest_measurements():
    answer = _build_user_answer(
        _inspection_result()
    )

    assert answer is not None

    assert (
        "Laatste inspectie: 2026-05-05"
        in answer
    )

    assert "- RI 1400-1350: 5 mm" in answer

    assert (
        "- UI 140 midden — Kap Br.1700: 6 mm"
        in answer
    )


def test_inspection_latest_presentation_deduplicates_check_rows():
    answer = _build_user_answer(
        _inspection_result()
    )

    assert answer is not None

    assert (
        answer.count(
            "- RI 1400-1350: 5 mm"
        )
        == 1
    )

    assert (
        answer.count(
            "- UI 140 midden — Kap Br.1700: 6 mm"
        )
        == 1
    )


def test_no_replacement_sentence_only_when_all_explicitly_false():
    answer = _build_user_answer(
        _inspection_result(
            replacement_ri=False,
            replacement_ui=False,
        )
    )

    assert answer is not None

    assert (
        "Geen mesvervanging geregistreerd "
        "bij deze laatste metingen."
        in answer
    )


def test_unknown_replacement_omits_no_replacement_sentence():
    answer = _build_user_answer(
        _inspection_result(
            replacement_ri=False,
            replacement_ui=None,
        )
    )

    assert answer is not None

    assert (
        "Geen mesvervanging geregistreerd "
        "bij deze laatste metingen."
        not in answer
    )


def test_generic_asset_presentation_is_unchanged():
    results = [
        {
            "action": "some_asset_assistant",
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

    answer = _build_user_answer(results)

    assert answer == (
        "Klant: TEST\n"
        "Plaats: SITE\n"
        "Gebied: Area\n"
        "Installatie: Installation (INST)\n"
        "Bandnummer: B100\n"
        "\n"
        "Bestaand generiek resultaat."
    )