from dataclasses import FrozenInstanceError

import pytest

from app.orchestrator.technical_cema_answer_stage import (
    TechnicalCemaAnswerStageResult,
    run_technical_cema_answer_stage,
)


FULL_NAME = "Conveyor Equipment Manufacturers Association"
SOURCE_CODE = "CEMA_BELT_CONVEYORS_7"


class Fatal(BaseException):
    pass


class ExplodingDict(dict):
    def __init__(self, error):
        super().__init__()
        self.error = error

    def get(self, _key, _default=None):
        raise self.error


class ExplodingValue:
    def __init__(self, error):
        self.error = error

    def __bool__(self):
        raise self.error


@pytest.mark.parametrize(
    "source_code",
    [None, "", "cema_belt_conveyors_7", " CEMA_BELT_CONVEYORS_7", 0, False, [], {}],
)
def test_exact_source_code_gate_returns_none(source_code):
    assert run_technical_cema_answer_stage({"source_code": source_code}).answer is None


@pytest.mark.parametrize(
    ("technical_context", "title"),
    [
        (None, None),
        ("bad", None),
        ({"results": None}, None),
        ({"results": [None, {}, {"source_title": "Second"}]}, "Second"),
        ({"results": [{"source_title": 0}, {"source_title": 7}]}, "7"),
        ({"results": [{"source_title": ["Synthetic"]}]}, "['Synthetic']"),
        ({"results": [{"source_title": "  "}]}, "  "),
        ({"results": [{"source_title": "First"}, {"source_title": "Second"}]}, "First"),
    ],
)
def test_title_shapes_priority_truthiness_and_conversion(technical_context, title):
    result = run_technical_cema_answer_stage(
        {"source_code": SOURCE_CODE, "technical_context": technical_context}
    )
    if title is None:
        assert result.answer == (
            "CEMA-referentiegegevens zijn beschikbaar, maar in dit "
            "specialistresultaat is geen definitierecord van CEMA aanwezig."
        )
    else:
        assert result.answer == (
            f"CEMA-referentiegegevens zijn beschikbaar uit {title}. "
            "In dit specialistresultaat is geen definitierecord van CEMA aanwezig."
        )


@pytest.mark.parametrize(
    ("rag_context", "grounded"),
    [
        (None, False),
        ("bad", False),
        ({"antwoord": FULL_NAME}, False),
        ({"used_context": FULL_NAME}, False),
        ({"used_context": [None, 7, [], {}, {"text": 8}]}, False),
        ({"used_context": [f"prefix {FULL_NAME} suffix"]}, True),
        ({"used_context": [{"text": FULL_NAME.upper()}]}, True),
        ({"used_context": [{"answer": FULL_NAME}, {"content": FULL_NAME}]}, False),
    ],
)
def test_used_context_shapes_and_casefolded_substring_grounding(rag_context, grounded):
    result = run_technical_cema_answer_stage(
        {"source_code": SOURCE_CODE, "rag_context": rag_context}
    )
    assert result.answer == (
        f"CEMA staat voor {FULL_NAME}."
        if grounded
        else "CEMA-referentiegegevens zijn beschikbaar, maar in dit "
        "specialistresultaat is geen definitierecord van CEMA aanwezig."
    )


@pytest.mark.parametrize("grounded", [False, True])
def test_exact_grounded_and_ungrounded_text_with_title(grounded):
    result = run_technical_cema_answer_stage({
        "source_code": SOURCE_CODE,
        "technical_context": {"results": [{"source_title": "Manual"}]},
        "rag_context": {"used_context": [FULL_NAME if grounded else "unrelated"]},
    })
    assert result.answer == (
        f"CEMA staat voor {FULL_NAME}. Bron: Manual."
        if grounded
        else "CEMA-referentiegegevens zijn beschikbaar uit Manual. "
        "In dit specialistresultaat is geen definitierecord van CEMA aanwezig."
    )


def test_first_grounding_match_stops_iteration():
    class MustNotBeRead(dict):
        def get(self, *_args):
            raise AssertionError("must stop")

    result = run_technical_cema_answer_stage({
        "source_code": SOURCE_CODE,
        "rag_context": {"used_context": [FULL_NAME, MustNotBeRead()]},
    })
    assert result.answer == f"CEMA staat voor {FULL_NAME}."


@pytest.mark.parametrize("error", [RuntimeError("boom"), Fatal("boom")])
@pytest.mark.parametrize("site", ["source", "technical", "title", "rag"])
def test_exception_and_baseexception_propagate(error, site):
    payload = {"source_code": SOURCE_CODE}
    if site == "source":
        payload = ExplodingDict(error)
    elif site == "technical":
        payload["technical_context"] = ExplodingDict(error)
    elif site == "title":
        payload["technical_context"] = {"results": [{"source_title": ExplodingValue(error)}]}
    else:
        payload["rag_context"] = ExplodingDict(error)
    with pytest.raises(type(error), match="boom"):
        run_technical_cema_answer_stage(payload)


def test_result_is_frozen_with_exactly_one_field():
    result = TechnicalCemaAnswerStageResult(answer=None)
    assert tuple(result.__dataclass_fields__) == ("answer",)
    with pytest.raises(FrozenInstanceError):
        result.answer = "changed"
