"""Characterize the inline technical/CEMA presentation boundary.

These tests freeze current behaviour only.  They intentionally do not define
the interface of a possible extracted stage.
"""

from __future__ import annotations

import ast
import copy
import inspect

import pytest

from app.orchestrator import service
from app.orchestrator.analysis_scope_answer_stage import AnalysisScopeAnswerStageResult
from app.orchestrator.multi_product_answer_stage import MultiProductAnswerStageResult


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


class ExplodingString:
    def __init__(self, error):
        self.error = error

    def __str__(self):
        raise self.error


class ExplodingTruth:
    def __init__(self, error):
        self.error = error

    def __bool__(self):
        raise self.error


class ExplodingList(list):
    def __init__(self, error):
        super().__init__()
        self.error = error

    def __iter__(self):
        raise self.error


def _technical(*, action="technical_assistant", context_type=None, **payload):
    specialist = dict(payload)
    if context_type is not None:
        specialist["context_type"] = context_type
    return {"action": action, "result": specialist}


def _cema(*, title=None, used_context=None, **overrides):
    payload = {"source_code": SOURCE_CODE}
    if title is not None:
        payload["technical_context"] = {"results": [{"source_title": title}]}
    if used_context is not None:
        payload["rag_context"] = {"used_context": used_context}
    payload.update(overrides)
    return _technical(**payload)


@pytest.mark.parametrize("selector", ["action", "context_type"])
def test_exact_selector_aliases_reach_technical(selector):
    item = _cema(
        action="technical_assistant" if selector == "action" else "other",
        context_type="technical_assistant" if selector == "context_type" else None,
    )
    assert service._build_user_answer([item]) == (
        "CEMA-referentiegegevens zijn beschikbaar, maar in dit "
        "specialistresultaat is geen definitierecord van CEMA aanwezig."
    )


@pytest.mark.parametrize(
    "value",
    [None, "", "TECHNICAL_ASSISTANT", "Technical_Assistant", " technical_assistant",
     "technical_assistant ", b"technical_assistant", 0, False,
     ["technical_assistant"], {"value": "technical_assistant"}, object()],
)
def test_selector_is_exact_after_string_conversion(value):
    assert service._build_user_answer([_cema(action=value)]) is None


@pytest.mark.parametrize("selector", ["action", "context_type"])
def test_selector_string_conversion_can_create_exact_alias(selector):
    class Alias:
        def __str__(self):
            return "technical_assistant"

    assert service._build_user_answer([
        _cema(action=Alias() if selector == "action" else "other",
              context_type=Alias() if selector == "context_type" else None)
    ]).startswith("CEMA-referentiegegevens")


@pytest.mark.parametrize(
    "source_code",
    [None, "", "cema_belt_conveyors_7", " CEMA_BELT_CONVEYORS_7",
     "CEMA_BELT_CONVEYORS_7 ", b"CEMA_BELT_CONVEYORS_7", 0, False, [], {}],
)
def test_source_code_is_one_exact_value_without_string_normalization(source_code):
    assert service._build_user_answer([_technical(source_code=source_code)]) is None


@pytest.mark.parametrize(
    ("technical_context", "expected_title"),
    [
        (None, None), ("context", None), ([], None), ({}, None),
        ({"results": None}, None), ({"results": "rows"}, None),
        ({"results": ()}, None), ({"results": []}, None),
        ({"results": [None, "row", 7, [], {}]}, None),
        ({"results": [{"source_title": ""}, {"source_title": "Second"}]}, "Second"),
        ({"results": [{"source_title": 0}, {"source_title": 7}]}, "7"),
        ({"results": [{"source_title": ["Synthetic"]}]}, "['Synthetic']"),
        ({"results": [{"source_title": "  "}]}, "  "),
        ({"results": [{"source_title": "First"}, {"source_title": "Second"}]}, "First"),
        ({"results": [{"title": "Ignored"}, {"source_title": "Winner"}]}, "Winner"),
    ],
)
def test_source_title_mapping_list_gates_first_truthy_candidate_and_conversion(
    technical_context, expected_title
):
    answer = service._build_user_answer([
        _technical(source_code=SOURCE_CODE, technical_context=technical_context)
    ])
    if expected_title is None:
        assert answer == (
            "CEMA-referentiegegevens zijn beschikbaar, maar in dit "
            "specialistresultaat is geen definitierecord van CEMA aanwezig."
        )
    else:
        assert answer == (
            f"CEMA-referentiegegevens zijn beschikbaar uit {expected_title}. "
            "In dit specialistresultaat is geen definitierecord van CEMA aanwezig."
        )


@pytest.mark.parametrize(
    ("rag_context", "grounded"),
    [
        (None, False), ("context", False), ([], False), ({}, False),
        ({"antwoord": FULL_NAME}, False), ({"used_context": None}, False),
        ({"used_context": FULL_NAME}, False), ({"used_context": ()}, False),
        ({"used_context": []}, False),
        ({"used_context": [None, 7, [], {}, {"text": 8}]}, False),
        ({"used_context": ["unrelated", {"text": "also unrelated"}]}, False),
        ({"used_context": [f"prefix {FULL_NAME} suffix"]}, True),
        ({"used_context": [{"text": FULL_NAME.upper()}]}, True),
        ({"used_context": [{"answer": FULL_NAME}, {"content": FULL_NAME}]}, False),
        ({"used_context": [f"{FULL_NAME[:-1]}x"]}, False),
        ({"used_context": ["", {"text": ""}, {"text": f"x{FULL_NAME}y"}]}, True),
    ],
)
def test_grounding_uses_only_list_items_or_mapping_text_casefolded_substring(
    rag_context, grounded
):
    answer = service._build_user_answer([
        _technical(source_code=SOURCE_CODE, rag_context=rag_context)
    ])
    assert answer == (
        f"CEMA staat voor {FULL_NAME}." if grounded else
        "CEMA-referentiegegevens zijn beschikbaar, maar in dit "
        "specialistresultaat is geen definitierecord van CEMA aanwezig."
    )


@pytest.mark.parametrize(
    ("title", "contexts", "expected"),
    [
        ("Synthetic manual", [FULL_NAME],
         f"CEMA staat voor {FULL_NAME}. Bron: Synthetic manual."),
        (None, [FULL_NAME], f"CEMA staat voor {FULL_NAME}."),
        ("Synthetic manual", ["unrelated"],
         "CEMA-referentiegegevens zijn beschikbaar uit Synthetic manual. "
         "In dit specialistresultaat is geen definitierecord van CEMA aanwezig."),
        (None, ["unrelated"],
         "CEMA-referentiegegevens zijn beschikbaar, maar in dit "
         "specialistresultaat is geen definitierecord van CEMA aanwezig."),
    ],
)
def test_exact_grounded_and_ungrounded_outputs(title, contexts, expected):
    assert service._build_user_answer([_cema(title=title, used_context=contexts)]) == expected


def test_first_grounding_match_stops_iteration():
    class MustNotBeRead(dict):
        def get(self, *_args):
            raise AssertionError("items after the first grounding match must not be read")

    assert service._build_user_answer([
        _cema(used_context=[{"text": FULL_NAME}, MustNotBeRead()])
    ]) == f"CEMA staat voor {FULL_NAME}."


def test_wrong_code_and_unselected_entries_fall_through_but_selected_cema_returns():
    results = [
        _technical(source_code="OTHER"),
        _technical(action="other", source_code=SOURCE_CODE),
        _cema(title="Winner"),
        _cema(title="Never reached", used_context=[FULL_NAME]),
    ]
    assert service._build_user_answer(results).startswith(
        "CEMA-referentiegegevens zijn beschikbaar uit Winner."
    )
    assert service._build_user_answer(results[:2]) is None


def test_input_order_first_successful_technical_entry_wins_without_double_execution():
    first_title = ExplodingTruth(AssertionError("later title must not be tested"))
    results = [_cema(title="First"), _cema(title=first_title)]
    assert service._build_user_answer(results).startswith(
        "CEMA-referentiegegevens zijn beschikbaar uit First."
    )


def test_asset_prescan_and_earlier_dispatch_branches_precede_technical(monkeypatch):
    technical = _cema(title="Technical loses")
    asset = {"action": "analysis_assistant", "result": {
        "asset_resolution": {}, "message": "Asset wins"}}
    assert service._build_user_answer([technical, asset]).endswith("\n\nAsset wins")

    monkeypatch.setattr(service, "run_diagnostics_answer_stage", lambda value: "Diagnostics wins")
    monkeypatch.setattr(service, "run_analysis_scope_answer_stage", lambda value:
                        AnalysisScopeAnswerStageResult(answer="Scope wins"))
    monkeypatch.setattr(service, "run_multi_product_answer_stage", lambda *_args:
                        MultiProductAnswerStageResult(delegated_answer="Product wins"))
    earlier = [
        ({"action": "diagnostics_assistant", "result": {}}, "Diagnostics wins"),
        ({"action": "other", "result": {"context_type": "analysis_scope"}}, "Scope wins"),
        ({"action": "product_assistant", "result": {}}, "Product wins"),
        ({"action": "org_assistant", "result": {
            "result": {"status": "not_found", "message": "ORG wins"}}}, "ORG wins"),
    ]
    for entry, expected in earlier:
        assert service._build_user_answer([entry, technical]) == expected


def test_diagnostics_none_is_a_frozen_return_and_does_not_reach_technical(monkeypatch):
    calls = []
    monkeypatch.setattr(service, "run_diagnostics_answer_stage",
                        lambda value: calls.append(("diagnostics", value)) or None)
    diagnostics = {"action": "diagnostics_assistant", "result": {}}
    technical = _cema(title="Reached")
    assert service._build_user_answer([diagnostics, technical]) is None
    assert calls == [("diagnostics", diagnostics["result"])]


def test_declined_analysis_scope_reaches_technical_once(monkeypatch):
    calls = []
    monkeypatch.setattr(
        service,
        "run_analysis_scope_answer_stage",
        lambda value: calls.append(value) or AnalysisScopeAnswerStageResult(answer=None),
    )
    scope = {"action": "other", "result": {"context_type": "analysis_scope"}}
    technical = _cema(title="Reached")
    assert service._build_user_answer([scope, technical]).startswith(
        "CEMA-referentiegegevens zijn beschikbaar uit Reached."
    )
    assert calls == [scope["result"]]


def test_no_mutation_of_results_requested_information_or_nested_payloads():
    results = [_cema(title="Synthetic source", used_context=[
        {"text": f"prefix {FULL_NAME} suffix"}, {"text": "unused"}
    ])]
    requested = [" TECHNICAL ", "", "technical"]
    before_results = copy.deepcopy(results)
    before_requested = copy.deepcopy(requested)
    service._build_user_answer(results, requested)
    assert results == before_results
    assert requested == before_requested


@pytest.mark.parametrize("error", [RuntimeError("synthetic exception"), Fatal("synthetic fatal")])
@pytest.mark.parametrize("site", ["outer_mapping", "specialist_mapping", "selector_string",
                                  "source_mapping", "title_truth", "title_string",
                                  "technical_rows_iteration", "rag_mapping",
                                  "used_context_iteration"])
def test_exception_and_baseexception_propagate_from_inline_operations(error, site):
    if site == "outer_mapping":
        results = [ExplodingDict(error)]
    elif site == "specialist_mapping":
        results = [{"action": "technical_assistant", "result": ExplodingDict(error)}]
    elif site == "selector_string":
        results = [_cema(action=ExplodingString(error))]
    elif site == "source_mapping":
        results = [_technical(source_code=SOURCE_CODE, technical_context=ExplodingDict(error))]
    elif site == "title_truth":
        results = [_cema(title=ExplodingTruth(error))]
    elif site == "title_string":
        results = [_cema(title=ExplodingString(error))]
    elif site == "technical_rows_iteration":
        results = [_technical(source_code=SOURCE_CODE,
                              technical_context={"results": ExplodingList(error)})]
    elif site == "rag_mapping":
        results = [_technical(source_code=SOURCE_CODE, rag_context=ExplodingDict(error))]
    else:
        results = [_technical(source_code=SOURCE_CODE,
                              rag_context={"used_context": ExplodingList(error)})]
    with pytest.raises(type(error), match=str(error)):
        service._build_user_answer(results)


@pytest.mark.parametrize("error", [RuntimeError("synthetic exception"), Fatal("synthetic fatal")])
def test_results_iteration_propagates_exception_and_baseexception(error):
    class ExplodingResults:
        def __iter__(self):
            raise error

    with pytest.raises(type(error), match=str(error)):
        service._build_user_answer(ExplodingResults())


def test_branch_is_inline_has_no_runtime_dependency_and_is_last_known_dispatch():
    source = inspect.getsource(service._build_user_answer)
    tree = ast.parse(source)
    function = tree.body[0]
    loop = next(
        node for node in function.body
        if isinstance(node, ast.For)
        and any(
            isinstance(child, ast.If)
            and "technical_assistant" in ast.unparse(child.test)
            for child in node.body
        )
    )
    conditions = [ast.unparse(node.test) for node in loop.body if isinstance(node, ast.If)]
    assert conditions[-1] == (
        "action == 'technical_assistant' or context_type == 'technical_assistant'"
    )
    technical_if = [node for node in loop.body if isinstance(node, ast.If)][-1]
    runtime_calls = {
        node.func.id for node in ast.walk(technical_if)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert runtime_calls == {"isinstance", "str"}
    assert "run_technical_cema_answer_stage" not in source
    assert isinstance(function.body[-1], ast.Return)
    assert function.body[-1].value.value is None
