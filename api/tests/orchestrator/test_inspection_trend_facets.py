from __future__ import annotations

from tests.orchestrator.test_inspection_trend_presentation import (
    _result,
)

from app.orchestrator.service import (
    _build_user_answer,
)


def test_latest_measurements_use_latest_across_cycles():
    answer = _build_user_answer(
        _result(),
        requested_information=[
            "latest_measurements",
        ],
    )

    assert answer is not None

    assert (
        "Laatste lifecycle-meting "
        "per schraper/positie:"
        in answer
    )

    assert (
        "- R 1400-1350 INOX - SECUNDAIR: "
        "5 mm op 2026-05-05"
        in answer
    )

    assert (
        "- U 1400 INOX - ZUID: "
        "5 mm op 2024-12-03"
        in answer
    )

    latest_section = answer.split(
        "Laatste lifecycle-meting "
        "per schraper/positie:",
        1,
    )[1]

    if "Geregistreerde vervangevents:" in latest_section:
        latest_section = latest_section.split(
            "Geregistreerde vervangevents:",
            1,
        )[0]

    assert latest_section.count(
        "- U 1400 INOX - ZUID:"
    ) == 1


def test_replacement_advice_is_not_inferred_from_lifecycle():
    answer = _build_user_answer(
        _result(),
        requested_information=[
            "replacement_advice",
        ],
    )

    assert answer is not None

    assert (
        "Vervangadvies: niet bepaald uit "
        "deze lifecyclehistorie"
        in answer
    )

    lowered = answer.casefold()

    assert "nu vervangen" not in lowered
    assert "verwachte vervanging" not in lowered
    assert "dagen resterend" not in lowered


def test_uncertainties_are_source_bounded():
    answer = _build_user_answer(
        _result(),
        requested_information=[
            "uncertainties",
        ],
    )

    assert answer is not None

    assert "Onzekerheden:" in answer

    assert (
        "meest recente lifecycle-meting "
        "per schraper/positie"
        in answer
    )

    assert (
        "bevestigt niet dat de positie "
        "nog actueel actief is"
        in answer
    )

    assert (
        "geen afzonderlijke actuele "
        "vervang-/forecastanalyse"
        in answer
    )


def test_composite_facets_preserve_existing_trend_and_events():
    answer = _build_user_answer(
        _result(),
        requested_information=[
            "latest_measurements",
            "lifecycle_trend",
            "replacement_events",
            "replacement_advice",
            "uncertainties",
        ],
    )

    assert answer is not None

    assert (
        "Trendgegevens: 7 metingen "
        "verdeeld over 3 cycli."
        in answer
    )

    assert (
        "Geregistreerde vervangevents: "
        "2023-12-05, 2025-03-05"
        in answer
    )

    assert (
        "Laatste lifecycle-meting "
        "per schraper/positie:"
        in answer
    )

    assert "Vervangadvies:" in answer
    assert "Onzekerheden:" in answer


def test_no_requested_information_preserves_legacy_shape():
    answer = _build_user_answer(
        _result()
    )

    assert answer is not None

    assert (
        "Laatste lifecycle-meting "
        "per schraper/positie:"
        not in answer
    )

    assert "Vervangadvies:" not in answer
    assert "Onzekerheden:" not in answer