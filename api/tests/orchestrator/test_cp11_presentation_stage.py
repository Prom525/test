from dataclasses import FrozenInstanceError, fields

import pytest

from app.orchestrator.cp11_presentation_stage import (
    CP11PresentationStageResult,
    run_cp11_presentation_stage,
)


class Fatal(BaseException):
    pass


_DEFAULT = object()


def run(pipeline=None, authority=_DEFAULT, presenter=None):
    pipeline = {} if pipeline is None else pipeline
    authority = {"prior": True} if authority is _DEFAULT else authority
    presenter = presenter or (lambda *args: ("answer", {"ok": True}, authority))
    return run_cp11_presentation_stage(
        "plan", "legacy", "coverage", pipeline, authority,
        present_relevant_task_answer=presenter,
    )


def test_frozen_exact_four_field_contract():
    assert [field.name for field in fields(CP11PresentationStageResult)] == [
        "answer", "evidence_pipeline", "task_presenter_cp11",
        "task_public_composition_authority_p4_6f",
    ]
    result = run()
    with pytest.raises(FrozenInstanceError):
        result.answer = "changed"


def test_exact_presenter_arguments_fresh_get_and_identity():
    coverage = object()
    pipeline = {"task_grounded_synthesis_coverage_authority_p4_6e3": coverage}
    authority = object()
    answer = object()
    presenter_state = object()
    calls = []

    def presenter(*args):
        calls.append(args)
        pipeline["task_grounded_synthesis_coverage_authority_p4_6e3"] = "later"
        return answer, presenter_state, authority

    result = run(pipeline, authority, presenter)
    assert calls == [("plan", "legacy", "coverage", coverage, authority)]
    assert result.answer is answer
    assert result.evidence_pipeline is pipeline
    assert result.task_presenter_cp11 is presenter_state
    assert result.task_public_composition_authority_p4_6f is authority
    assert pipeline["task_presenter_cp11"] is presenter_state
    assert pipeline["task_public_composition_authority_p4_6f"] is authority


@pytest.mark.parametrize("returned", [
    ("a", "p", "u"), ["a", "p", "u"],
    {"a": 1, "p": 2, "u": 3}, (value for value in ("a", "p", "u")),
])
def test_python_three_value_unpacking_accepts_iterables(returned):
    result = run(presenter=lambda *args: returned)
    assert (result.answer, result.task_presenter_cp11,
            result.task_public_composition_authority_p4_6f) == ("a", "p", "u")


@pytest.mark.parametrize("returned", [None, (), (1,), (1, 2), (1, 2, 3, 4), 1])
def test_malformed_returns_use_exact_fallback(returned):
    result = run(authority=None, presenter=lambda *args: returned)
    assert result.answer == "legacy"
    assert result.task_presenter_cp11 == {
        "contract_version": "promati.orchestrator.task_relevance_presenter.cp11.v1",
        "evaluated": False, "authoritative": False,
        "public_answer_replaced": False, "reason": "internal_error_fail_closed",
    }
    assert result.task_public_composition_authority_p4_6f["reason"] == (
        "presenter_internal_error"
    )


def test_iterator_exception_uses_fallback():
    def broken():
        yield 1
        raise RuntimeError("broken")
    assert run(presenter=lambda *args: broken()).answer == "legacy"


@pytest.mark.parametrize("site", ["get", "presenter", "unpack"])
def test_baseexception_propagates(site):
    fatal = Fatal(site)

    class Pipeline(dict):
        def get(self, key):
            if site == "get":
                raise fatal
            return super().get(key)

    def presenter(*args):
        if site == "presenter":
            raise fatal
        if site == "unpack":
            def values():
                raise fatal
                yield
            return values()
        return "a", "p", "u"

    with pytest.raises(Fatal) as caught:
        run(Pipeline(), {}, presenter)
    assert caught.value is fatal


@pytest.mark.parametrize("authority", [None, False, 0, "", {"old": 1}])
def test_fallback_authority_copy_and_update(authority):
    result = run(authority=authority, presenter=lambda *args: (_ for _ in ()).throw(
        RuntimeError("fail")
    ))
    updated = result.task_public_composition_authority_p4_6f
    assert isinstance(updated, dict)
    assert updated.get("old") == (1 if isinstance(authority, dict) else None)
    assert updated["task_presenter_cp11"] is result.task_presenter_cp11


def test_fallback_is_fresh_per_call():
    def fail(*args):
        raise RuntimeError
    first, second = run(presenter=fail), run(presenter=fail)
    assert first.task_presenter_cp11 is not second.task_presenter_cp11
    assert (first.task_public_composition_authority_p4_6f is not
            second.task_public_composition_authority_p4_6f)


def test_truthiness_and_dict_conversion_errors_propagate():
    class BadTruth:
        def __bool__(self):
            raise RuntimeError("truth")
    class BadDict:
        def __iter__(self):
            raise RuntimeError("dict")
    for authority, message in [(BadTruth(), "truth"), (BadDict(), "dict")]:
        with pytest.raises(RuntimeError, match=message):
            run(authority=authority, presenter=lambda *args: 1)


def test_update_failure_preserves_partial_state():
    captured = []

    class Mapping:
        def keys(self):
            captured.append(self)
            return ["bad"]
        def __getitem__(self, key):
            raise RuntimeError("convert")

    with pytest.raises(RuntimeError, match="convert"):
        run(authority=Mapping(), presenter=lambda *args: 1)
    assert captured


@pytest.mark.parametrize("failure,expected", [(1, []), (2, ["task_presenter_cp11"])])
def test_pipeline_write_failures_preserve_exact_partial_mutation(failure, expected):
    class Pipeline(dict):
        count = 0
        successful = []
        def __setitem__(self, key, value):
            self.count += 1
            if self.count == failure:
                raise RuntimeError("write")
            self.successful.append(key)
            super().__setitem__(key, value)

    pipeline = Pipeline(existing=True)
    with pytest.raises(RuntimeError, match="write"):
        run(pipeline)
    assert pipeline.successful == expected
    assert pipeline["existing"] is True
