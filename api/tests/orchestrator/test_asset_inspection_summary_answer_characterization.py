"""Characterize only the legacy ``inspection_summary`` asset presenter."""
from __future__ import annotations

import copy

import pytest

from app.orchestrator import service


class Fatal(BaseException):
    """Non-Exception sentinel used to pin uncaught propagation."""


class RaisingBool:
    def __init__(self, error):
        self.error = error

    def __bool__(self):
        raise self.error


class RaisingStr:
    def __init__(self, error):
        self.error = error

    def __str__(self):
        raise self.error


class RaisingGet(dict):
    def __init__(self, key, error, **values):
        super().__init__(values)
        self.key = key
        self.error = error

    def get(self, key, default=None):
        if key == self.key:
            raise self.error
        return super().get(key, default)


class RaisingList(list):
    def __init__(self, error):
        super().__init__()
        self.error = error

    def __iter__(self):
        raise self.error


def _row(date="2099-01-02", *, height=7, scraper="R-SYNTH", location="P-SYNTH", **extra):
    return {
        "document_date": date,
        "inspection_key": "INS-SYNTH",
        "scraper_type_raw": scraper,
        "locatie_raw": location,
        "meshoogte_mm": height,
        "mes_vervangen": False,
        **extra,
    }


def _results(rows, **overrides):
    context = {
        "customer_code": "CUSTOMER-SYNTH",
        "site_code": "SITE-SYNTH",
        "area_name": "Area Synthetic",
        "area_code": "AREA-SYNTH",
        "installation_name": "Installation Synthetic",
        "installation_code": "INST-SYNTH",
        "band_code_display": "BAND-SYNTH",
    }
    payload = {
        "asset_resolution": {"status": "resolved"},
        "asset_context": context,
        "entities": {"band_code": "ENTITY-BAND"},
        "intent": "inspection_summary",
        "message": "generic fallback marker",
        "resultaat": rows,
        **overrides,
    }
    return [{"action": "analysis_assistant", "result": payload}]


HEADER = (
    "Klant: CUSTOMER-SYNTH\n"
    "Plaats: SITE-SYNTH\n"
    "Gebied: Area Synthetic (AREA-SYNTH)\n"
    "Installatie: Installation Synthetic (INST-SYNTH)\n"
    "Bandnummer: BAND-SYNTH"
)


@pytest.mark.parametrize(
    ("rows", "expected_suffix"),
    [
        (None, "\n\ngeneric fallback marker"),
        ({}, "\n\ngeneric fallback marker"),
        ((), "\n\ngeneric fallback marker"),
        ("rows", "\n\ngeneric fallback marker"),
        ([], "\n\ngeneric fallback marker"),
        ([None, "row", (), []], "\n\ngeneric fallback marker"),
        ([_row(None), _row(""), _row("   ")], "\n\ngeneric fallback marker"),
    ],
)
def test_outer_and_row_shape_gates_and_no_dated_row_fall_through(rows, expected_suffix):
    answer = service._build_user_answer(_results(rows))
    assert answer == HEADER + expected_suffix


def test_document_date_is_the_only_date_field_and_uses_str_strip_lexicographic_max():
    rows = [
        _row(None, scraper="ignored-inspected", inspected_on="9999-12-31"),
        _row(" 9 ", scraper="nine"),
        _row(10, scraper="ten"),
        _row("malformed", scraper="lexical-winner"),
        _row(" malformed ", scraper="same-after-strip", location="later"),
    ]

    answer = service._build_user_answer(_results(rows))

    assert answer == (
        HEADER
        + "\n\nLaatste inspectie: malformed"
        + "\n\nSchrapers:"
        + "\n- lexical-winner â€” P-SYNTH: 7 mm"
        + "\n- same-after-strip â€” later: 7 mm"
        + "\n\nGeen mesvervanging geregistreerd bij deze laatste metingen."
    )


def test_equal_latest_dates_keep_input_order_until_measurements_are_stably_sorted():
    rows = [
        _row("2099-01-03", scraper="B", location="second", height=2),
        _row("2099-01-03", scraper="A", location="same", height=3),
        _row("2099-01-03", scraper="A", location="same", height=4),
        _row("2099-01-02", scraper="Z", location="older", height=99),
    ]
    answer = service._build_user_answer(_results(rows))
    assert answer.split("Schrapers:\n", 1)[1].split("\n\n", 1)[0].splitlines() == [
        "- A â€” same: 3 mm",
        "- A â€” same: 4 mm",
        "- B â€” second: 2 mm",
    ]
    assert "older" not in answer


def test_dedupe_key_is_exact_four_string_tuple_first_wins_and_other_fields_do_not_matter():
    first = _row("2099-01-03", height=7, mes_vervangen=False, check_code="FIRST")
    duplicate = _row("2099-01-03", height="7", mes_vervangen=True, check_code="SECOND")
    variants = [
        _row("2099-01-03", height=8),
        _row("2099-01-03", height=7, scraper="R-OTHER"),
        _row("2099-01-03", height=7, location="P-OTHER"),
        _row("2099-01-03", height=7, inspection_key="INS-OTHER"),
    ]
    answer = service._build_user_answer(_results([first, duplicate, *variants]))
    assert answer.count("- R-SYNTH â€” P-SYNTH: 7 mm") == 2
    assert "Geen mesvervanging" in answer
    assert "check_code" not in answer


def test_missing_dedupe_fields_collapse_to_empty_strings_and_height_none_is_skipped():
    rows = [
        {"document_date": "2099", "meshoogte_mm": 0, "mes_vervangen": None},
        {"document_date": "2099", "meshoogte_mm": "0", "mes_vervangen": False},
        {"document_date": "2099", "meshoogte_mm": None, "scraper_type_raw": "ignored"},
    ]
    answer = service._build_user_answer(_results(rows))
    assert answer == HEADER + "\n\nLaatste inspectie: 2099\n\nSchrapers:\n- Onbekende schraper: 0 mm"


@pytest.mark.parametrize(
    ("replacement_values", "sentence_present"),
    [
        ([False], True),
        ([False, False], True),
        ([None], False),
        ([0], False),
        ([""], False),
        ([True, False], False),
    ],
)
def test_replacement_sentence_requires_every_deduplicated_value_to_be_false(
    replacement_values, sentence_present
):
    rows = [
        _row("2099", scraper=f"R-{index}", mes_vervangen=value)
        for index, value in enumerate(replacement_values)
    ]
    answer = service._build_user_answer(_results(rows))
    assert ("Geen mesvervanging geregistreerd" in answer) is sentence_present


def test_dated_rows_without_measurements_return_header_and_date_before_generic_fallback():
    answer = service._build_user_answer(
        _results([_row("2099", height=None)], message="must not appear")
    )
    assert answer == HEADER + "\n\nLaatste inspectie: 2099"


def test_exact_success_output_header_precedence_defaults_and_string_conversion():
    rows = [
        _row("2099", height=0, scraper="", location=""),
        _row("2099", height=False, scraper=0, location=0, inspection_key=0),
    ]
    results = _results(rows)
    payload = results[0]["result"]
    payload["asset_context"] = {
        "customer_code": 0,
        "site_code": "",
        "area_name": None,
        "area_code": "AREA",
        "installation_name": "Install",
        "installation_code": "INST",
        "band_code_display": "",
        "band_code_norm": "NORM",
    }
    answer = service._build_user_answer(results)
    assert answer == (
        "Klant: onbekend\nPlaats: onbekend\nGebied: AREA\n"
        "Installatie: Install (INST)\nBandnummer: NORM\n\n"
        "Laatste inspectie: 2099\n\nSchrapers:\n- Onbekende schraper: 0 mm\n"
        "- Onbekende schraper: False mm\n\n"
        "Geen mesvervanging geregistreerd bij deze laatste metingen."
    )


def test_display_helper_is_service_owned_called_twice_before_route_and_objects_are_unchanged(monkeypatch):
    sentinels = [object(), object(), object(), object()]
    rows = [_row()]
    results = _results(rows)
    payload = results[0]["result"]
    context = payload["asset_context"]
    context.update(zip(("area_name", "area_code", "installation_name", "installation_code"), sentinels))
    requested = [" Latest_Measurements "]
    before_results = copy.deepcopy(results)
    before_requested = copy.deepcopy(requested)
    calls = []

    def display(name, code):
        calls.append((name, code))
        return f"display-{len(calls)}"

    monkeypatch.setattr(service, "_display_name_code", display)
    answer = service._build_user_answer(results, requested)
    assert calls == [(sentinels[0], sentinels[1]), (sentinels[2], sentinels[3])]
    assert "Gebied: display-1\nInstallatie: display-2" in answer
    for key in ("customer_code", "site_code", "band_code_display"):
        assert context[key] == before_results[0]["result"]["asset_context"][key]
    assert payload["entities"] == before_results[0]["result"]["entities"]
    assert rows == before_results[0]["result"]["resultaat"]
    assert requested == before_requested
    assert payload["asset_context"] is context and payload["resultaat"] is rows


def test_internal_mojibake_is_preserved_and_repair_remains_outside_presenter():
    answer = service._build_user_answer(_results([_row(location="cafÃ©")]))
    assert "R-SYNTH â€” cafÃ©" in answer
    repaired = service.repair_mojibake_text(answer)
    assert "R-SYNTH — café" in repaired


@pytest.mark.parametrize("fatal", [False, True], ids=["exception", "baseexception"])
@pytest.mark.parametrize(
    "boundary",
    ["payload_get", "rows_iter", "row_get", "date_truth", "date_str", "height_get", "height_str", "replacement_get", "sort", "display"],
)
def test_mapping_iteration_conversion_truthiness_sort_and_helper_throwables_propagate(
    monkeypatch, boundary, fatal
):
    error = Fatal(boundary) if fatal else RuntimeError(boundary)
    rows = [_row()]
    results = _results(rows)
    payload = results[0]["result"]
    if boundary == "payload_get":
        results[0]["result"] = RaisingGet("resultaat", error, **payload)
    elif boundary == "rows_iter":
        payload["resultaat"] = RaisingList(error)
    elif boundary == "row_get":
        payload["resultaat"] = [RaisingGet("document_date", error)]
    elif boundary == "date_truth":
        payload["resultaat"] = [_row(RaisingBool(error))]
    elif boundary == "date_str":
        payload["resultaat"] = [_row(RaisingStr(error))]
    elif boundary == "height_get":
        payload["resultaat"] = [RaisingGet("meshoogte_mm", error, document_date="2099")]
    elif boundary == "height_str":
        payload["resultaat"] = [_row(height=RaisingStr(error))]
    elif boundary == "replacement_get":
        payload["resultaat"] = [RaisingGet("mes_vervangen", error, **_row())]
    elif boundary == "sort":
        monkeypatch.setattr(service, "sorted", lambda *_a, **_k: (_ for _ in ()).throw(error), raising=False)
    elif boundary == "display":
        monkeypatch.setattr(service, "_display_name_code", lambda *_a: (_ for _ in ()).throw(error))
    with pytest.raises(type(error), match=boundary) as raised:
        service._build_user_answer(results)
    assert raised.value is error


def test_no_row_limit_and_direct_return_prevents_generic_text_or_later_route_work():
    rows = [_row("2099", scraper=f"R-{index:03}") for index in range(25)]
    answer = service._build_user_answer(_results(rows, message="forbidden", kort_resultaat="forbidden"))
    assert answer.count("\n- R-") == 25
    assert "forbidden" not in answer
