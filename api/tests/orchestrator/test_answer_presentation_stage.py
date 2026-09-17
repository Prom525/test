from __future__ import annotations

import ast
from collections import UserDict
from dataclasses import FrozenInstanceError, fields
from pathlib import Path

import pytest

from app.orchestrator.answer_presentation_stage import (
    AnswerPresentationStageResult,
    run_answer_presentation_stage,
)


class Fatal(BaseException):
    pass


class StringOnce:
    def __init__(self, value="specialist"):
        self.value, self.calls = value, 0

    def __str__(self):
        self.calls += 1
        return self.value


def _run(*, answer="legacy", research=None, timing=None):
    events, calls = [], []
    results, requested, started = object(), object(), object()
    timings = {"presentation": "old"} if timing is None else timing

    def clock():
        events.append("clock")
        return started

    def requested_information():
        events.append("requested")
        return requested

    def build(*args, **kwargs):
        events.append("build")
        calls.append(("build", args, kwargs))
        return answer

    def repair(value):
        events.append("repair")
        calls.append(("repair", value))
        return value

    def elapsed(value):
        events.append("elapsed")
        calls.append(("elapsed", value))
        return "new"

    result = run_answer_presentation_stage(
        results, requested_information,
        {"status": "not_required", "answer": None} if research is None else research,
        timings, observability_now=clock, build_user_answer=build,
        repair_mojibake_text=repair, observability_elapsed_ms=elapsed,
    )
    return result, events, calls, results, requested, started, timings


def test_frozen_exact_one_field_contract():
    result = AnswerPresentationStageResult(object())
    assert [field.name for field in fields(result)] == ["answer"]
    with pytest.raises(FrozenInstanceError):
        result.answer = object()


@pytest.mark.parametrize("answer", ["text", "", "   ", None, {"x": 1}, [1], (1,), b"bytes"])
def test_build_arguments_identity_truthiness_order_and_fresh_state(answer):
    result, events, calls, results, requested, started, timings = _run(answer=answer)
    assert calls[0] == ("build", (results,), {"requested_information": requested})
    assert calls[0][1][0] is results
    assert calls[0][2]["requested_information"] is requested
    expected = ["clock", "requested", "build"] + (["repair"] if answer else []) + ["elapsed"]
    assert events == expected
    assert result.answer is answer
    assert calls[-1] == ("elapsed", started)
    assert timings["presentation"] == "new"


@pytest.mark.parametrize(("research", "expected"), [
    ({}, "legacy"), ({"status": "ok"}, "legacy"),
    ({"status": "ok", "answer": None}, "legacy"),
    ({"status": "ok", "answer": ""}, "legacy"),
    ({"status": "ok", "answer": "   "}, "   "),
    ({"status": "ok", "answer": b"bytes"}, "b'bytes'"),
    ({"status": "OK", "answer": "specialist"}, "legacy"),
    (type("D", (dict,), {})(status="ok", answer="specialist"), "specialist"),
    (UserDict(status="ok", answer="specialist"), "specialist"),
])
def test_exact_research_selection_forms(research, expected):
    result, *_ = _run(research=research)
    assert result.answer == expected


def test_research_string_conversion_once_and_repair_after_selection():
    value = StringOnce()
    result, events, calls, *_ = _run(research={"status": "ok", "answer": value})
    assert value.calls == 1 and result.answer == "specialist"
    assert calls[-2] == ("repair", "specialist")
    assert events[-2:] == ["repair", "elapsed"]


@pytest.mark.parametrize("error", [RuntimeError("ordinary"), Fatal("fatal")])
@pytest.mark.parametrize("where", ["requested", "build", "status", "repair"])
def test_exception_and_baseexception_propagate_with_final_timing(error, where):
    timings = {"presentation": "old"}
    research = {"status": "not_required"}
    if where == "status":
        class Bad:
            def get(self, *_args): raise error
        research = Bad()
    def fail_requested():
        if where == "requested": raise error
        return object()
    def fail_build(*_args, **_kwargs):
        if where == "build": raise error
        return "legacy"
    def fail_repair(value):
        if where == "repair": raise error
        return value
    with pytest.raises(type(error)) as raised:
        run_answer_presentation_stage(
            object(), fail_requested, research, timings,
            observability_now=lambda: "start", build_user_answer=fail_build,
            repair_mojibake_text=fail_repair,
            observability_elapsed_ms=lambda value: "elapsed",
        )
    assert raised.value is error and timings["presentation"] == "elapsed"


def test_clock_failure_is_before_try_and_elapsed_failure_preserves_existing_value():
    error = Fatal("clock")
    timings = {"presentation": "old"}
    with pytest.raises(Fatal) as raised:
        run_answer_presentation_stage(
            object(), lambda: None, {}, timings,
            observability_now=lambda: (_ for _ in ()).throw(error),
            build_user_answer=lambda *_a, **_k: None,
            repair_mojibake_text=lambda value: value,
            observability_elapsed_ms=lambda value: pytest.fail("elapsed called"),
        )
    assert raised.value is error and timings["presentation"] == "old"
    elapsed_error = RuntimeError("elapsed")
    with pytest.raises(RuntimeError) as raised:
        run_answer_presentation_stage(
            object(), lambda: None, {}, timings,
            observability_now=lambda: "start",
            build_user_answer=lambda *_a, **_k: None,
            repair_mojibake_text=lambda value: value,
            observability_elapsed_ms=lambda value: (_ for _ in ()).throw(elapsed_error),
        )
    assert raised.value is elapsed_error and timings["presentation"] == "old"


def test_no_input_mutation_cross_call_leakage_or_duplicate_calls():
    results, research = [object()], {"status": "ok", "answer": "specialist"}
    before = (list(results), dict(research))
    counts = {name: 0 for name in ("clock", "requested", "build", "repair", "elapsed")}
    def once(name, returned):
        def call(*_args, **_kwargs):
            counts[name] += 1
            return returned
        return call
    for _ in range(2):
        timing = {}
        run_answer_presentation_stage(
            results, once("requested", object()), research, timing,
            observability_now=once("clock", object()),
            build_user_answer=once("build", "legacy"),
            repair_mojibake_text=once("repair", "specialist"),
            observability_elapsed_ms=once("elapsed", 1),
        )
    assert (results, research) == before
    assert counts == {name: 2 for name in counts}


def test_minimal_imports_and_no_service_import():
    path = Path(__file__).parents[2] / "app/orchestrator/answer_presentation_stage.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported = {alias.name for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))
                for alias in node.names}
    assert imported <= {"annotations", "dataclass", "Any", "Callable"}
    assert "service" not in path.read_text(encoding="utf-8")
