from dataclasses import fields

import pytest

from app.orchestrator import asset_inspection_summary_answer_stage as stage


HEADER = ("Klant: SYNTH", "Bandnummer: B-SYNTH")


class Fatal(BaseException):
    pass


class RaisingGet(dict):
    def __init__(self, key, error, **values):
        super().__init__(values)
        self.key = key
        self.error = error

    def get(self, key, default=None):
        if key == self.key:
            raise self.error
        return super().get(key, default)


def _row(date="2099-01-02", height=7, scraper="R", location="P", **extra):
    return {
        "document_date": date,
        "inspection_key": "I",
        "scraper_type_raw": scraper,
        "locatie_raw": location,
        "meshoogte_mm": height,
        "mes_vervangen": False,
        **extra,
    }


def _run(rows):
    return stage.run_asset_inspection_summary_answer_stage(
        {"resultaat": rows}, HEADER
    ).answer


def test_contract_is_frozen_and_has_exactly_one_answer_field():
    result = stage.AssetInspectionSummaryAnswerStageResult(answer=None)
    assert [field.name for field in fields(result)] == ["answer"]
    with pytest.raises(Exception):
        result.answer = "changed"


@pytest.mark.parametrize("rows", [None, {}, (), "rows", [], [None, "row"]])
def test_non_list_or_no_dated_rows_returns_exact_none(rows):
    assert _run(rows) is None


def test_latest_date_dedupe_stable_sort_measurements_and_false_sentence():
    rows = [
        _row(" 9 ", scraper="ignored"),
        _row("malformed", scraper="B", location="second", height=2),
        _row(" malformed ", scraper="A", location="same", height=3),
        _row("malformed", scraper="A", location="same", height=4),
        _row("malformed", scraper="A", location="same", height="3", mes_vervangen=True),
    ]
    assert _run(rows) == (
        "Klant: SYNTH\nBandnummer: B-SYNTH\n\nLaatste inspectie: malformed"
        "\n\nSchrapers:\n- A â€” same: 3 mm\n- A â€” same: 4 mm"
        "\n- B â€” second: 2 mm"
        "\n\nGeen mesvervanging geregistreerd bij deze laatste metingen."
    )


def test_header_only_success_unknown_scraper_and_mm_formatting():
    assert _run([_row("2099", height=None)]) == (
        "Klant: SYNTH\nBandnummer: B-SYNTH\n\nLaatste inspectie: 2099"
    )
    assert _run([_row("2099", height=False, scraper="", location="")]).endswith(
        "\n- Onbekende schraper: False mm"
        "\n\nGeen mesvervanging geregistreerd bij deze laatste metingen."
    )


def test_mojibake_is_preserved_and_header_snapshot_is_not_mutated():
    header = ("cafÃ©",)
    result = stage.run_asset_inspection_summary_answer_stage(
        {"resultaat": [_row(location="cafÃ©")]}, header
    )
    assert "R â€” cafÃ©" in result.answer
    assert header == ("cafÃ©",)


@pytest.mark.parametrize("error", [RuntimeError("boom"), Fatal("boom")])
def test_exception_and_baseexception_propagate_unchanged(error):
    payload = RaisingGet("resultaat", error)
    with pytest.raises(type(error)) as raised:
        stage.run_asset_inspection_summary_answer_stage(payload, HEADER)
    assert raised.value is error


def test_input_payload_and_rows_are_not_mutated():
    row = _row()
    rows = [row]
    payload = {"resultaat": rows}
    stage.run_asset_inspection_summary_answer_stage(payload, HEADER)
    assert payload == {"resultaat": [row]}
    assert payload["resultaat"] is rows and rows[0] is row
