"""Characterize the service-owned answer-presentation boundary after 3W2."""
from __future__ import annotations

import ast
import importlib.util
from collections import UserDict
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.orchestrator import service
from app.orchestrator.models import OrchestratorAskRequest


class StopAtComposition(BaseException):
    pass


class Fatal(BaseException):
    pass


class DictSubclass(dict):
    pass


class MappingOnly(UserDict):
    pass


class RaisingGet:
    def __init__(self, error):
        self.error = error

    def get(self, *_args, **_kwargs):
        raise self.error


class RaisingAnswerKey(dict):
    def __init__(self, error):
        super().__init__(status="ok", answer="truthy")
        self.error = error

    def __getitem__(self, key):
        if key == "answer":
            raise self.error
        return super().__getitem__(key)


class RaisingRequestedPlan(SimpleNamespace):
    requested_error = None

    @property
    def requested_information(self):
        raise self.requested_error

    @requested_information.setter
    def requested_information(self, _value):
        pass


class TruthValue:
    def __init__(self, value, error=None):
        self.value = value
        self.error = error
        self.calls = 0

    def __bool__(self):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.value


class StringValue:
    def __init__(self, rendered, error=None):
        self.rendered = rendered
        self.error = error
        self.calls = 0

    def __str__(self):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.rendered


def _prior_characterization():
    path = Path(__file__).with_name(
        "test_phase_c_evidence_pipeline_assembly_boundary_characterization.py"
    )
    spec = importlib.util.spec_from_file_location("phase_c_3u1_for_3x1", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _install(monkeypatch, *, research=None, answer="legacy", answer_error=None,
             repair=None, repair_error=None, requested_information=None,
             requested_error=None, clock_error=None):
    prior = _prior_characterization()
    upstream = prior._install(monkeypatch, serializer_return={}, stop=False)
    plan = upstream.base.base.base.h.plan
    results = upstream.base.base.base.h.results
    typed = upstream.base.base.base.h.typed_results
    trace = upstream.base.base.base.h.trace
    if requested_information is None:
        requested_information = [object(), object()]
    if requested_error is not None:
        original_execution = service.run_initial_execution_stage
        replacement = RaisingRequestedPlan(**vars(plan))
        replacement.requested_error = requested_error

        def execution_with_raising_plan(*args, **kwargs):
            result = original_execution(*args, **kwargs)
            result.plan = replacement
            return result

        monkeypatch.setattr(service, "run_initial_execution_stage",
                            execution_with_raising_plan)
        plan = replacement
    else:
        plan.requested_information = requested_information
    research_value = ({"status": "not_required", "answer": None}
                      if research is None else research)
    agent = object()
    events = []
    calls = []
    started = object()
    elapsed = object()

    def bounded(*args, **kwargs):
        events.append("3w2")
        calls.append(("3w2", args, kwargs))
        return SimpleNamespace(research=research_value, plan_research_agent=agent)

    def clock():
        events.append("presentation_start")
        if clock_error is not None:
            raise clock_error
        return started

    def build(*args, **kwargs):
        events.append("answer")
        calls.append(("answer", args, kwargs))
        if answer_error is not None:
            raise answer_error
        return answer

    def normalize(value):
        events.append("repair")
        calls.append(("repair", (value,), {}))
        if repair_error is not None:
            raise repair_error
        return value if repair is None else repair

    def elapsed_ms(value):
        events.append("presentation_timing")
        calls.append(("elapsed", (value,), {}))
        return elapsed

    boundary = StopAtComposition("controlled composition boundary")

    def composition(*args, **kwargs):
        events.append("composition")
        calls.append(("composition", args, kwargs))
        raise boundary

    monkeypatch.setattr(service, "run_phase_c_bounded_research_v1_stage", bounded)
    monkeypatch.setattr(service, "_observability_now", clock)
    monkeypatch.setattr(service, "_observability_elapsed_ms", elapsed_ms)
    monkeypatch.setattr(service, "_build_user_answer", build)
    monkeypatch.setattr(service, "repair_mojibake_text", normalize)
    monkeypatch.setattr(service, "_build_multi_intent_composition_shadow", composition)
    before = (dict(vars(plan)), list(results), list(typed), dict(trace))
    return SimpleNamespace(**locals())


def _run(h, exception=StopAtComposition):
    with pytest.raises(exception) as raised:
        service._p4_15cp3c_previous_run_orchestrator(
            OrchestratorAskRequest(q="synthetic", vraag=""), sender=object()
        )
    return raised.value


def _locals(error):
    traceback = error.__traceback__
    while traceback is not None:
        if traceback.tb_frame.f_code is service._p4_15cp3c_previous_run_orchestrator.__code__:
            return traceback.tb_frame.f_locals
        traceback = traceback.tb_next
    raise AssertionError("service frame absent")


def _named(h, name):
    return [call for call in h.calls if call[0] == name]


@pytest.mark.parametrize(
    "returned",
    ["text", "", "   ", None, {"x": 1}, [1], (1,), pytest.param(object(), id="object")],
)
def test_answer_build_exact_arguments_identity_and_truthiness(monkeypatch, returned):
    h = _install(monkeypatch, answer=returned)
    error = _run(h)
    call = _named(h, "answer")[0]
    assert call[1] == (h.results,)
    assert call[1][0] is h.results
    assert call[2] == {"requested_information": h.requested_information}
    assert call[2]["requested_information"] is h.requested_information
    assert len(_named(h, "answer")) == 1
    assert len(_named(h, "repair")) == bool(returned)
    expected = returned if not returned else (returned if h.repair is None else h.repair)
    assert _locals(error)["answer"] is expected


@pytest.mark.parametrize(
    ("research", "overrides"),
    [
        ({}, False),
        ({"status": "ok"}, False),
        ({"status": "ok", "answer": None}, False),
        ({"status": "ok", "answer": ""}, False),
        ({"status": "ok", "answer": "   "}, True),
        ({"status": "ok", "answer": b"bytes"}, True),
        ({"status": "OK", "answer": "specialist"}, False),
        ({"status": "error", "answer": "specialist"}, False),
        (DictSubclass(status="ok", answer="specialist"), True),
        (MappingOnly(status="ok", answer="specialist"), True),
    ],
)
def test_research_selection_uses_mapping_get_equality_and_truthiness(
    monkeypatch, research, overrides
):
    h = _install(monkeypatch, research=research, answer="legacy")
    error = _run(h)
    expected = str(research["answer"]) if overrides else "legacy"
    assert _named(h, "repair")[0][1] == (expected,)
    assert _locals(error)["answer"] == expected


def test_research_answer_string_conversion_once_before_repair(monkeypatch):
    value = StringValue("rendered")
    h = _install(monkeypatch, research={"status": "ok", "answer": value})
    _run(h)
    assert value.calls == 1
    assert _named(h, "repair")[0][1] == ("rendered",)
    assert h.events[-3:] == ["repair", "presentation_timing", "composition"]


@pytest.mark.parametrize("status", [None, False, 0, "", "not_ok"])
def test_non_ok_status_does_not_read_or_convert_answer(monkeypatch, status):
    error = AssertionError("answer access")
    research = RaisingGet(error)

    def get(key, default=None):
        if key == "status":
            return status
        raise error

    research.get = get
    h = _install(monkeypatch, research=research)
    _run(h)


@pytest.mark.parametrize("fatal", [False, True], ids=["exception", "baseexception"])
@pytest.mark.parametrize("where", ["answer", "status_get", "answer_key", "answer_truth", "string", "repair", "elapsed"])
def test_failure_zones_propagate_identically_and_timing_matches_finally(
    monkeypatch, where, fatal
):
    error = Fatal(where) if fatal else RuntimeError(where)
    research = {"status": "not_required", "answer": None}
    answer_error = error if where == "answer" else None
    repair_error = error if where == "repair" else None
    answer = "legacy"
    if where == "status_get":
        research = RaisingGet(error)
    elif where == "answer_key":
        research = RaisingAnswerKey(error)
    elif where == "answer_truth":
        research = {"status": "ok", "answer": TruthValue(True, error)}
    elif where == "string":
        research = {"status": "ok", "answer": StringValue("unused", error)}
    h = _install(monkeypatch, research=research, answer=answer,
                 answer_error=answer_error, repair_error=repair_error)
    if where == "elapsed":
        monkeypatch.setattr(service, "_observability_elapsed_ms",
                            lambda _value: (_ for _ in ()).throw(error))
    raised = _run(h, type(error))
    assert raised is error
    assert len(_named(h, "answer")) == 1
    assert _named(h, "composition") == []
    if where == "elapsed":
        assert _locals(raised)["timings"]["presentation"] == 0
    else:
        assert _locals(raised)["timings"]["presentation"] is h.elapsed


@pytest.mark.parametrize("fatal", [False, True], ids=["exception", "baseexception"])
@pytest.mark.parametrize("where", ["requested_information", "clock"])
def test_property_and_clock_failures_propagate_before_later_calls(
    monkeypatch, fatal, where
):
    error = Fatal(where) if fatal else RuntimeError(where)
    h = _install(
        monkeypatch,
        requested_error=error if where == "requested_information" else None,
        clock_error=error if where == "clock" else None,
    )
    raised = _run(h, type(error))
    assert raised is error
    assert _named(h, "composition") == []
    if where == "requested_information":
        assert _named(h, "answer") == []
        assert _named(h, "elapsed")[0][1] == (h.started,)
        assert _locals(raised)["timings"]["presentation"] is h.elapsed
    else:
        assert _named(h, "answer") == []
        assert _named(h, "elapsed") == []
        assert _locals(raised)["timings"]["presentation"] == 0


def test_timing_exact_key_clock_argument_order_and_state_is_fresh(monkeypatch):
    snapshots = []
    for _ in range(2):
        with monkeypatch.context() as patch:
            h = _install(patch)
            error = _run(h)
            locals_ = _locals(error)
            assert h.events[-5:] == [
                "presentation_start", "answer", "repair",
                "presentation_timing", "composition",
            ]
            assert _named(h, "elapsed")[0][1] == (h.started,)
            assert locals_["timings"]["presentation"] is h.elapsed
            snapshots.append(locals_["timings"])
    assert snapshots[0] is not snapshots[1]


def test_runtime_dependencies_and_inputs_are_not_mutated(monkeypatch):
    research = {"status": "ok", "answer": "specialist", "agent": object()}
    h = _install(monkeypatch, research=research)
    error = _run(h)
    locals_ = _locals(error)
    assert locals_["research"] is research
    assert locals_["plan_research_agent"] is h.agent
    assert (dict(vars(h.plan)), h.results, h.typed, h.trace) == h.before
    assert len(_named(h, "composition")) == 1
    args, kwargs = _named(h, "composition")[0][1:]
    assert args[0] is h.plan and args[1] == "specialist"
    assert args[2] is locals_["evidence_pipeline"] and kwargs == {}


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("caf\u00c3\u00a9", "caf\u00e9"),
        ("already caf\u00e9", "already caf\u00e9"),
        ("A \u00e2\u20ac\u201c B", "A \u2013 B"),
        ("\ufb01le", "file"),
        ("", ""),
        (None, ""),
        (b"bytes", b"bytes"),
    ],
)
def test_real_mojibake_repair_contract(raw, expected):
    assert service.repair_mojibake_text(raw) == expected
    assert service.repair_mojibake_text(service.repair_mojibake_text(raw)) == expected


def test_composition_exception_is_fail_open_without_repeating_presentation(monkeypatch):
    h = _install(monkeypatch)
    composition_error = RuntimeError("composition")
    next_boundary = Fatal("next boundary")

    def composition(*_args, **_kwargs):
        h.events.append("composition")
        h.calls.append(("composition", _args, _kwargs))
        raise composition_error

    monkeypatch.setattr(service, "_build_multi_intent_composition_shadow", composition)
    monkeypatch.setattr(
        service, "_maybe_apply_public_composition_canary",
        lambda *_a, **_k: (_ for _ in ()).throw(next_boundary),
    )
    raised = _run(h, Fatal)
    assert raised is next_boundary
    assert len(_named(h, "answer")) == len(_named(h, "repair")) == 1
    assert _locals(raised)["evidence_pipeline"]["multi_intent_composition_shadow"] is None


def test_ast_exact_boundary_order_cardinality_and_runtime_names():
    path = Path(__file__).parents[2] / "app/orchestrator/service.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name == "run_orchestrator")
    calls = [node for node in ast.walk(function) if isinstance(node, ast.Call)]
    named = lambda name: [
        node for node in calls
        if isinstance(node.func, ast.Name) and node.func.id == name
    ]
    bounded = named("run_phase_c_bounded_research_v1_stage")
    presentation = named("run_answer_presentation_stage")
    composition = named("_build_multi_intent_composition_shadow")
    assert len(bounded) == len(presentation) == len(composition) == 1
    assert bounded[0].lineno < presentation[0].lineno < composition[0].lineno

    answer_bindings = [
        node for node in function.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "answer"
                for target in node.targets)
        and isinstance(node.value, ast.Attribute)
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "answer_presentation_stage_result"
        and node.value.attr == "answer"
    ]
    assert len(answer_bindings) == 1

    stage_call = presentation[0]
    assert [(keyword.arg, keyword.value.id) for keyword in stage_call.keywords] == [
        ("observability_now", "_observability_now"),
        ("build_user_answer", "_build_user_answer"),
        ("repair_mojibake_text", "repair_mojibake_text"),
        ("observability_elapsed_ms", "_observability_elapsed_ms"),
    ]
    requested_information = stage_call.args[1]
    assert isinstance(requested_information, ast.Lambda)
    assert isinstance(requested_information.body, ast.Attribute)
    assert isinstance(requested_information.body.value, ast.Name)
    assert requested_information.body.value.id == "plan"
    assert requested_information.body.attr == "requested_information"

    inline_names = {
        "_observability_now", "_build_user_answer", "repair_mojibake_text",
        "_observability_elapsed_ms",
    }
    assert not [
        node for node in calls
        if isinstance(node.func, ast.Name)
        and node.func.id in inline_names
        and bounded[0].lineno < node.lineno < composition[0].lineno
    ]
