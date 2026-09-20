"""Direct tests for the dependency-free analysis-scope answer stage."""

from dataclasses import FrozenInstanceError

import pytest

from app.orchestrator.analysis_scope_answer_stage import AnalysisScopeAnswerStageResult, run_analysis_scope_answer_stage


class Fatal(BaseException):
    pass


class ExplodingBool:
    def __init__(self, error): self.error = error
    def __bool__(self): raise self.error


class ExplodingStr:
    def __init__(self, error): self.error = error
    def __str__(self): raise self.error


class ExplodingList(list):
    def __init__(self, error):
        super().__init__(["B-1"])
        self.error = error
    def __iter__(self): raise self.error


class RaisingDict(dict):
    def __init__(self, key, error, **values):
        super().__init__(values)
        self.key, self.error = key, error
    def get(self, key, default=None):
        if key == self.key: raise self.error
        return super().get(key, default)


@pytest.mark.parametrize(("payload", "expected"), [
    ({"kort_resultaat": "short"}, "short"),
    ({"kort_resultaat": 7}, "7"),
    ({"operation": "list", "subject": "bands", "bands": ["B-1", 2]}, "Banden: B-1, 2"),
    ({"operation": "list", "subject": "bands", "bands": ("B-1",)}, None),
    ({"operation": "list", "subject": "bands", "bands": ["hidden"], "kort_resultaat": "short"}, "short"),
    ({"count_semantics": "current_registered_scraper_positions", "data_quality": {"semantic_note": "note"}}, "\nnote"),
    ({"count_semantics": "historical_maintenance_ranking_rows"}, "\nLet op: dit betreft historische onderhoudsregels binnen de canonical scope. Dat is niet automatisch dezelfde set als de actuele unified schraperposities."),
    ({"operation": "analyse"}, "\nDe wear-evidence kan historische posities/cycli bevatten en wordt daarom als aanvullende historie naast de actuele unified snapshot gebruikt."),
    ({"kort_resultaat": "short", "count_semantics": "historical_maintenance_ranking_rows", "operation": "analyse"}, "short\n\nLet op: dit betreft historische onderhoudsregels binnen de canonical scope. Dat is niet automatisch dezelfde set als de actuele unified schraperposities.\n\nDe wear-evidence kan historische posities/cycli bevatten en wordt daarom als aanvullende historie naast de actuele unified snapshot gebruikt."),
    ({"kort_resultaat": "", "bands": [], "data_quality": []}, None),
    ({"kort_resultaat": 0, "operation": None, "subject": False, "count_semantics": []}, None),
])
def test_exact_presentation_paths_and_malformed_falsy_shapes(payload, expected):
    assert run_analysis_scope_answer_stage(payload).answer == expected


@pytest.mark.parametrize("error", [RuntimeError("boom"), Fatal("boom")])
@pytest.mark.parametrize("payload", [
    lambda error: RaisingDict("kort_resultaat", error),
    lambda error: {"kort_resultaat": ExplodingBool(error)},
    lambda error: {"operation": ExplodingStr(error)},
    lambda error: {"operation": "list", "subject": "bands", "bands": ExplodingList(error)},
    lambda error: {"count_semantics": "current_registered_scraper_positions", "data_quality": {"semantic_note": ExplodingBool(error)}},
])
def test_exception_and_baseexception_propagate_unchanged(error, payload):
    with pytest.raises(type(error), match="boom"):
        run_analysis_scope_answer_stage(payload(error))


def test_result_contract_is_frozen_and_has_exactly_one_field():
    result = AnalysisScopeAnswerStageResult(answer=None)
    assert tuple(result.__dataclass_fields__) == ("answer",)
    with pytest.raises(FrozenInstanceError):
        result.answer = "changed"
