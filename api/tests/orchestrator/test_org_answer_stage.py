from dataclasses import FrozenInstanceError, fields

import pytest

from app.orchestrator.org_answer_stage import OrgAnswerStageResult, run_org_answer_stage


class Fatal(BaseException):
    pass


class ExplodingDict(dict):
    def __init__(self, error):
        super().__init__()
        self.error = error

    def get(self, _key, _default=None):
        raise self.error


class ExplodingTruth:
    def __init__(self, error):
        self.error = error

    def __bool__(self):
        raise self.error


def _run(nested, **outer):
    return run_org_answer_stage({"result": nested, **outer}).answer


def test_contract_is_frozen_and_has_exactly_one_field():
    result = OrgAnswerStageResult(answer=None)
    assert [(field.name, field.type) for field in fields(result)] == [("answer", str | None)]
    with pytest.raises(FrozenInstanceError):
        result.answer = "changed"


@pytest.mark.parametrize(
    ("nested", "outer", "expected"),
    [
        ("NOT_FOUND", "ok", "message"),
        (None, "NOT_FOUND", "message"),
        ("", "not_found", "message"),
        (" not_found ", "not_found", None),
        ("ok", "not_found", None),
    ],
)
def test_nested_status_has_truthy_priority_over_outer(nested, outer, expected):
    assert _run({"status": nested, "message": "message"}, status=outer) == expected


@pytest.mark.parametrize("message", [None, "", 0, False, [], {}])
def test_not_found_requires_truthy_message(message):
    assert _run({"status": "not_found", "message": message}) is None


def test_string_message_identity_is_preserved_and_other_values_are_converted():
    message = "identity " * 20
    assert _run({"status": "not_found", "message": message}) is message
    assert _run({"status": "not_found", "message": ["x"]}) == "['x']"


@pytest.mark.parametrize(
    ("rows", "expected"),
    [
        (None, None),
        ("bad", None),
        ([], None),
        ([None, {"locatie": "router"}], None),
        ([{"locatie": "HQ", "adres": "A", "plaats": "P", "land": "BE"}], "Promati is gevestigd op:\n- HQ: A"),
        ([{"locatie": None, "adres": "A", "plaats": "P"}], "Promati is gevestigd op:\n- P: A"),
        ([{"locatie": None, "adres": "A", "plaats": None}], "Promati is gevestigd op:\n- A"),
        ([{"locatie": "HQ", "adres": None, "plaats": "P", "land": "BE"}], "Promati is gevestigd op:\n- HQ: P, BE"),
        ([{"locatie": None, "adres": None, "plaats": "P", "land": None}], "Promati is gevestigd op:\n- P: P"),
    ],
)
def test_location_shapes_and_field_priorities(rows, expected):
    assert _run({"results": rows}, mode="location_info") == expected


def test_location_rows_keep_order():
    rows = [{"locatie": "A", "adres": "1"}, "bad", {"locatie": "B", "adres": "2"}]
    assert _run({"results": rows}, mode="location_info") == "Promati is gevestigd op:\n- A: 1\n- B: 2"


@pytest.mark.parametrize(
    ("rows", "expected"),
    [
        (None, None),
        ({}, None),
        ([None, "bad"], None),
        ([{"weergavenaam": "P", "officiele_functienaam": "Lead", "functie_naam": "Alias"}], "P is Lead."),
        ([{"weergavenaam": "P", "officiele_functienaam": "", "functie_naam": "Alias"}], "P is Alias."),
        ([{"weergavenaam": None, "officiele_functienaam": "Lead", "afdeling": "D", "kerntaken": ["T"]}], "Onbekende persoon is Lead.\nAfdeling: D.\n\nKerntaken:\n['T']"),
        ([{"weergavenaam": "P"}], "Functiegegevens gevonden voor P."),
        (["bad", {"weergavenaam": "First"}, {"weergavenaam": "Second", "functie_naam": "Role"}], "Functiegegevens gevonden voor First."),
    ],
)
def test_function_shapes_aliases_and_first_mapping_semantics(rows, expected):
    assert _run({"results": rows}, mode="function_info") == expected


@pytest.mark.parametrize("nested", [None, "bad", [], 7])
def test_malformed_nested_payload_returns_none(nested):
    assert _run(nested) is None


@pytest.mark.parametrize("error", [RuntimeError("boom"), Fatal("fatal")])
def test_mapping_errors_propagate(error):
    with pytest.raises(type(error), match=str(error)):
        run_org_answer_stage(ExplodingDict(error))


@pytest.mark.parametrize("error", [RuntimeError("boom"), Fatal("fatal")])
def test_truthiness_errors_propagate(error):
    with pytest.raises(type(error), match=str(error)):
        _run({"status": "not_found", "message": ExplodingTruth(error)})


@pytest.mark.parametrize("error", [RuntimeError("boom"), Fatal("fatal")])
def test_row_iteration_errors_propagate(error):
    class ExplodingList(list):
        def __iter__(self):
            raise error

    with pytest.raises(type(error), match=str(error)):
        _run({"results": ExplodingList()}, mode="location_info")
