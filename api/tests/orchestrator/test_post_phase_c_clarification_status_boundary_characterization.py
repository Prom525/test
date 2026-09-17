"""Characterize the service-owned status boundary immediately after Phase-C."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.orchestrator import service
from app.orchestrator.models import OrchestratorAskRequest


FALLBACK = "Kun je de ontbrekende context verduidelijken?"


class Fatal(BaseException):
    pass


class DictSubclass(dict):
    pass


class StrSubclass(str):
    pass


class StrValue:
    def __init__(self, rendered):
        self.rendered = rendered
        self.calls = 0

    def __str__(self):
        self.calls += 1
        return self.rendered


class RaisingStr:
    def __init__(self, error):
        self.error = error

    def __str__(self):
        raise self.error


class RaisingGet:
    def __init__(self, error):
        self.error = error

    def get(self, *_args, **_kwargs):
        raise self.error


class RaisingIterator:
    def __init__(self, error):
        self.error = error

    def __iter__(self):
        raise self.error


def _install(
    monkeypatch,
    *,
    results=None,
    typed_results=None,
    clarification_required=False,
    clarification_question=None,
    execution_steps=(),
    accepted=True,
    accepted_error=None,
):
    calls = []
    raw_results = [] if results is None else results
    typed = [] if typed_results is None else typed_results
    plan = SimpleNamespace(
        intent="synthetic",
        clarification_required=clarification_required,
        clarification_question=clarification_question,
        execution_steps=execution_steps,
        research_required=False,
        requested_information=(),
        multi_intent=False,
    )
    trace = {"attempts": []}
    before = (
        dict(vars(plan)),
        tuple(typed),
        tuple(raw_results) if isinstance(raw_results, (list, tuple)) else None,
        dict(trace),
    )
    tick = [-1.0]

    def clock():
        tick[0] += 1.0
        return tick[0]

    monkeypatch.setattr(service, "_observability_now", clock)
    monkeypatch.setattr(service, "run_initial_planning_stage", lambda *a, **k: plan)

    def execute(*args, **kwargs):
        calls.append(("upstream", args, kwargs))
        return SimpleNamespace(
            plan=plan,
            task_execution_plans_shadow=(),
            task_execution_plan_comparison_shadow=None,
            task_execution_canary_p4_6b=None,
            typed_execution_results=typed,
            results=raw_results,
            trace=trace,
            task_execution_shadow=None,
            task_planner_canary=None,
        )

    monkeypatch.setattr(service, "run_initial_execution_stage", execute)
    monkeypatch.setattr(
        service, "_record_initial_execution_observability", lambda *a: None
    )

    def phase_c(*args, **kwargs):
        calls.append(("phase_c", args, kwargs))
        return None

    monkeypatch.setattr(service, "prepare_phase_c_entry", phase_c)

    def helper(*args, **kwargs):
        calls.append(("helper", args, kwargs))
        if accepted_error is not None:
            raise accepted_error
        return accepted

    monkeypatch.setattr(service, "has_service_accepted_execution", helper)
    monkeypatch.setattr(service, "_build_user_answer", lambda *a, **k: "synthetic answer")
    monkeypatch.setattr(service, "repair_mojibake_text", lambda value: value)
    monkeypatch.setattr(
        service, "compact_results_for_public_response", lambda value, **k: value
    )
    monkeypatch.setattr(
        service,
        "_model_to_dict",
        lambda value: dict(vars(value)) if hasattr(value, "__dict__") else value,
    )
    monkeypatch.setattr(
        service,
        "run_bounded_research_agent",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("research called")),
    )
    monkeypatch.setattr(
        service,
        "run_bounded_research",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("research called")),
    )

    return SimpleNamespace(
        calls=calls,
        plan=plan,
        results=raw_results,
        typed=typed,
        trace=trace,
        before=before,
    )


def _run(harness):
    return service._p4_15cp3c_previous_run_orchestrator(
        OrchestratorAskRequest(q="synthetic", vraag=""), sender=object()
    )


@pytest.mark.parametrize(
    ("status", "matches"),
    [
        ("clarification_required", True),
        ("CLARIFICATION_REQUIRED", True),
        ("Clarification_Required", True),
        (" clarification_required", False),
        ("clarification_required ", False),
        (None, False),
        (7, False),
        (object(), False),
    ],
)
def test_status_uses_single_str_lower_without_whitespace_normalization(
    monkeypatch, status, matches
):
    h = _install(
        monkeypatch,
        results=[{"result": {"status": status, "message": "specialist question"}}],
    )
    response = _run(h)
    assert response["status"] == ("clarification_required" if matches else "ok")
    assert response["clarification"] == (
        {"required": True, "question": "specialist question"}
        if matches
        else {"required": False, "question": None}
    )


def test_status_is_converted_to_string_exactly_once(monkeypatch):
    status = StrValue("CLARIFICATION_REQUIRED")
    h = _install(
        monkeypatch,
        results=[{"result": {"status": status, "message": "q"}}],
    )
    assert _run(h)["status"] == "clarification_required"
    assert status.calls == 1


@pytest.mark.parametrize("nested", [None, "x", 1, object(), [1], (1,)])
def test_only_real_dict_or_dict_subclass_nested_results_participate(
    monkeypatch, nested
):
    h = _install(
        monkeypatch,
        results=[
            {"result": nested},
            {"result": DictSubclass(status="clarification_required", message="q")},
        ],
    )
    response = _run(h)
    assert response["status"] == "clarification_required"
    assert response["clarification"] == {"required": True, "question": "q"}


def test_ordered_scan_stops_at_first_matching_nested_result(monkeypatch):
    poison = RaisingGet(AssertionError("scan continued after first match"))
    first = {"status": "CLARIFICATION_REQUIRED", "message": "first"}
    h = _install(
        monkeypatch,
        results=[
            {"result": {"status": "ok", "message": "ignored"}},
            {"result": first},
            poison,
            {"result": {"status": "clarification_required", "message": "later"}},
        ],
    )
    response = _run(h)
    assert response["clarification"] == {"required": True, "question": "first"}


@pytest.mark.parametrize(
    "item",
    [
        DictSubclass(result={"status": "clarification_required", "message": "q"}),
        RaisingGet(AttributeError("exact top-level get failure")),
        None,
        3,
        object(),
    ],
)
def test_top_level_items_are_not_type_filtered_before_exact_get_call(monkeypatch, item):
    h = _install(monkeypatch, results=[item])
    if isinstance(item, DictSubclass):
        assert _run(h)["status"] == "clarification_required"
    else:
        with pytest.raises((AttributeError,)) as raised:
            _run(h)
        if isinstance(item, RaisingGet):
            assert raised.value is item.error


@pytest.mark.parametrize("error_type", [RuntimeError, Fatal])
@pytest.mark.parametrize("source", ["iterator", "item_get", "status_str"])
def test_scan_exception_and_baseexception_propagate_unchanged(
    monkeypatch, error_type, source
):
    error = error_type(source)
    if source == "iterator":
        results = RaisingIterator(error)
    elif source == "item_get":
        results = [RaisingGet(error)]
    else:
        results = [{"result": {"status": RaisingStr(error)}}]
    h = _install(monkeypatch, results=results)
    with pytest.raises(error_type) as raised:
        _run(h)
    assert raised.value is error
    assert [call[0] for call in h.calls] == ["upstream", "phase_c"]


def test_plan_clarification_has_highest_priority_and_preserves_initial_dict(
    monkeypatch,
):
    question = object()
    poison = RaisingGet(AssertionError("specialist detail must not be consulted"))
    h = _install(
        monkeypatch,
        clarification_required=True,
        clarification_question=question,
        results=[{"result": {"status": "clarification_required", "message": poison}}],
        execution_steps=(object(),),
        accepted_error=AssertionError("helper must not run"),
    )
    response = _run(h)
    assert response["status"] == "clarification_required"
    assert response["clarification"] == {"required": True, "question": question}
    assert not any(call[0] == "helper" for call in h.calls)


@pytest.mark.parametrize(
    ("specialist", "expected"),
    [
        ({"message": "message", "clarification": {"question": "nested"}}, "message"),
        ({"message": 9, "clarification": {"question": "nested"}}, "9"),
        ({"message": "", "clarification": {"question": "nested"}}, "nested"),
        ({"message": None, "clarification": "direct"}, "direct"),
        (
            {"message": None, "clarification": StrSubclass("direct subclass")},
            "direct subclass",
        ),
        ({"message": 0, "clarification": DictSubclass(question="subclass")}, "subclass"),
        ({"message": False, "clarification": {"question": 12}}, "12"),
        ({"message": None, "clarification": {"question": ""}}, FALLBACK),
        ({"message": None, "clarification": 42}, FALLBACK),
        ({"message": None, "clarification": object()}, FALLBACK),
    ],
)
def test_specialist_question_precedence_fallback_and_final_string_conversion(
    monkeypatch, specialist, expected
):
    specialist = dict(specialist, status="clarification_required")
    h = _install(monkeypatch, results=[{"result": specialist}])
    response = _run(h)
    assert response["clarification"] == {"required": True, "question": expected}


def test_selected_question_is_converted_to_string_exactly_once(monkeypatch):
    question = StrValue("rendered once")
    h = _install(
        monkeypatch,
        results=[
            {
                "result": {
                    "status": "clarification_required",
                    "message": question,
                }
            }
        ],
    )
    response = _run(h)
    assert response["clarification"] == {
        "required": True,
        "question": "rendered once",
    }
    assert question.calls == 1


def test_specialist_clarification_skips_accepted_helper_with_truthy_steps(
    monkeypatch,
):
    h = _install(
        monkeypatch,
        results=[
            {
                "result": {
                    "status": "clarification_required",
                    "message": "specialist question",
                }
            }
        ],
        execution_steps=(object(),),
        accepted_error=AssertionError("accepted helper must not run"),
    )
    response = _run(h)
    assert response["status"] == "clarification_required"
    assert response["clarification"] == {
        "required": True,
        "question": "specialist question",
    }
    assert not any(call[0] == "helper" for call in h.calls)


@pytest.mark.parametrize("error_type", [RuntimeError, Fatal])
def test_selected_question_string_failure_propagates_unchanged(monkeypatch, error_type):
    error = error_type("question")
    h = _install(
        monkeypatch,
        results=[
            {
                "result": {
                    "status": "clarification_required",
                    "message": RaisingStr(error),
                }
            }
        ],
    )
    with pytest.raises(error_type) as raised:
        _run(h)
    assert raised.value is error


@pytest.mark.parametrize(
    ("steps", "accepted", "expected", "helper_calls"),
    [
        ((), False, "ok", 0),
        ([], 0, "ok", 0),
        ((object(),), False, "error", 1),
        ((object(),), None, "error", 1),
        ((object(),), 0, "error", 1),
        ((object(),), "", "error", 1),
        ((object(),), object(), "ok", 1),
        ((object(),), "accepted", "ok", 1),
    ],
)
def test_nonclarification_status_uses_exact_steps_and_helper_truthiness(
    monkeypatch, steps, accepted, expected, helper_calls
):
    typed = [object()]
    raw = [{"result": {"status": "ok"}}]
    h = _install(
        monkeypatch,
        results=raw,
        typed_results=typed,
        execution_steps=steps,
        accepted=accepted,
    )
    response = _run(h)
    assert response["status"] == expected
    helper = [call for call in h.calls if call[0] == "helper"]
    assert len(helper) == helper_calls
    if helper:
        assert helper[0][1] == (typed, raw)
        assert helper[0][1][0] is typed and helper[0][1][1] is raw
        assert helper[0][2] == {}


@pytest.mark.parametrize("error_type", [RuntimeError, Fatal])
def test_helper_exception_and_baseexception_propagate_unchanged(monkeypatch, error_type):
    error = error_type("helper")
    h = _install(
        monkeypatch,
        execution_steps=(object(),),
        accepted_error=error,
    )
    with pytest.raises(error_type) as raised:
        _run(h)
    assert raised.value is error
    assert len([call for call in h.calls if call[0] == "helper"]) == 1


def test_each_call_gets_fresh_clarification_and_preserves_all_inputs(monkeypatch):
    raw = [{"result": {"status": "clarification_required", "message": "q"}}]
    typed = [object()]
    h = _install(monkeypatch, results=raw, typed_results=typed)
    first = _run(h)
    first["clarification"]["question"] = "mutated response only"
    second = _run(h)
    assert second["clarification"] == {"required": True, "question": "q"}
    assert first["clarification"] is not second["clarification"]
    assert (dict(vars(h.plan)), tuple(h.typed), tuple(h.results), dict(h.trace)) == h.before
    names = [call[0] for call in h.calls]
    assert names.count("upstream") == names.count("phase_c") == 2
    assert names.count("helper") == 0


def test_research_default_is_only_the_following_semantic_boundary(monkeypatch):
    h = _install(monkeypatch)
    response = _run(h)
    assert response["status"] == "ok"
    assert response["research"] == {
        "status": "not_required",
        "required": False,
        "mode": "bounded_synthesis_v1",
        "ai_calls_used": 0,
        "max_ai_calls": 1,
        "follow_up_rounds_used": 0,
        "max_follow_up_rounds": 0,
        "answer": None,
    }
