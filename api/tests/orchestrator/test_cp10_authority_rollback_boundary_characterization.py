"""Characterize the service-owned CP10 rollback block up to CP11."""
from __future__ import annotations

import ast
import importlib.util
from collections import UserDict
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.orchestrator import service


class StopAtCP11(BaseException):
    pass


class StopAfterTypeGate(BaseException):
    pass


class Fatal(BaseException):
    pass


class DictSubclass(dict):
    pass


class PipelineProbe(dict):
    def __init__(self, initial=(), *, fail_get=None, fail_set_at=None, error=None):
        super().__init__(initial)
        self.fail_get = fail_get
        self.fail_set_at = fail_set_at
        self.error = error
        self.get_calls = []
        self.set_calls = []
        self.successful_set_calls = []

    def get(self, key, *args, **kwargs):
        self.get_calls.append((key, args, kwargs))
        if key == self.fail_get:
            raise self.error
        return super().get(key, *args, **kwargs)

    def __setitem__(self, key, value):
        self.set_calls.append((key, value))
        if len(self.set_calls) == self.fail_set_at:
            raise self.error
        super().__setitem__(key, value)
        self.successful_set_calls.append((key, value))


class IterationFailure:
    def __init__(self, error):
        self.error = error

    def __iter__(self):
        raise self.error


_DEFAULT = object()


def _prior_characterization():
    path = Path(__file__).with_name(
        "test_p4_6f_authority_entry_boundary_characterization.py"
    )
    spec = importlib.util.spec_from_file_location("authority_3z1a_for_3z1b", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _install(
    monkeypatch,
    *,
    pipeline_factory=dict,
    authority_return=_DEFAULT,
    authority_error=None,
    canary_return=_DEFAULT,
    canary_error=None,
    cp11_error=None,
):
    prior = _prior_characterization()
    pipeline = pipeline_factory() if callable(pipeline_factory) else pipeline_factory
    h = prior._install(monkeypatch, pipeline_factory=pipeline)
    calls = h.calls
    events = h.events
    answer = object()
    legacy = "synthetic legacy answer"
    authority_before = object()
    coverage = object()
    cp9 = object()
    cp13 = object()
    stage_result = SimpleNamespace(
        answer=answer,
        evidence_pipeline=pipeline,
        task_research_semantics_cp13=cp13,
        task_coverage_gate_cp10=coverage,
        task_public_composition_authority_p4_6f=authority_before,
        task_authority_gate_cp9=cp9,
    )
    authority_value = ((object(), object())
                       if authority_return is _DEFAULT else authority_return)
    canary_value = object() if canary_return is _DEFAULT else canary_return
    boundary = StopAtCP11("controlled CP11 stop boundary")
    type_boundary = StopAfterTypeGate("controlled post-typegate boundary")
    stage_canary_shadow = [None]

    def stage(*args, **kwargs):
        if isinstance(pipeline, dict):
            stage_canary_shadow[0] = dict.get(
                pipeline, "public_composition_canary_shadow"
            )
        if isinstance(pipeline, PipelineProbe):
            pipeline.get_calls.clear()
            pipeline.set_calls.clear()
            pipeline.successful_set_calls.clear()
        events.append("3z2a")
        calls.append(("3z2a", args, kwargs))
        return stage_result

    def authority_guard(*args, **kwargs):
        events.append("cp10_authority")
        calls.append(("cp10_authority", args, kwargs))
        if authority_error is not None:
            raise authority_error
        return authority_value

    def canary_guard(*args, **kwargs):
        events.append("cp10_canary")
        calls.append(("cp10_canary", args, kwargs))
        if canary_error is not None:
            raise canary_error
        return canary_value

    def cp11(*args, **kwargs):
        events.append("cp11")
        calls.append(("cp11", args, kwargs))
        raise boundary if cp11_error is None else cp11_error

    def after_type_gate(*args, **kwargs):
        events.append("after_type_gate")
        calls.append(("after_type_gate", args, kwargs))
        raise type_boundary

    monkeypatch.setattr(service, "run_p4_6f_cp9_authority_entry_stage", stage)
    monkeypatch.setattr(service, "guard_task_coverage_authority", authority_guard)
    monkeypatch.setattr(service, "guard_public_composition_canary", canary_guard)
    monkeypatch.setattr(service, "present_relevant_task_answer", cp11)
    monkeypatch.setattr(
        service, "_record_task_execution_plan_shadow_observability", after_type_gate
    )
    # The stage owns the legacy binding in production; retain the upstream value
    # supplied by 3Y2 while replacing only the six 3Z2A result bindings.
    before = (dict(vars(h.plan)), list(h.results), list(h.typed), dict(h.trace))
    return SimpleNamespace(**locals(), plan=h.plan, results=h.results,
                           typed=h.typed, trace=h.trace, payload=h.payload)


def _run(h, exception=StopAtCP11):
    with pytest.raises(exception) as raised:
        service._p4_15cp3c_previous_run_orchestrator(h.payload, sender=object())
    return raised.value


def _locals(error):
    traceback = error.__traceback__
    while traceback is not None:
        if traceback.tb_frame.f_code.co_filename == service.__file__:
            local = traceback.tb_frame.f_locals
            if "p4_6f_cp9_authority_entry_stage_result" in local:
                return local
        traceback = traceback.tb_next
    raise AssertionError("service frame absent")


def _calls(h, name):
    return [call for call in h.calls if call[0] == name]


@pytest.mark.parametrize("factory", [dict, DictSubclass])
def test_typegate_accepts_dict_and_subclass_without_coercion(monkeypatch, factory):
    pipeline = factory()
    h = _install(monkeypatch, pipeline_factory=pipeline)
    local = _locals(_run(h))
    assert local["evidence_pipeline"] is pipeline
    assert len(_calls(h, "cp10_authority")) == len(_calls(h, "cp11")) == 1


@pytest.mark.parametrize("factory", [UserDict, list, lambda: None, object])
def test_typegate_rejects_non_dict_and_preserves_six_bindings(monkeypatch, factory):
    pipeline = factory()
    h = _install(monkeypatch, pipeline_factory=pipeline)
    local = _locals(_run(h, StopAfterTypeGate))
    assert local["evidence_pipeline"] is pipeline
    assert local["answer"] is h.answer
    assert local["task_research_semantics_cp13"] is h.cp13
    assert local["task_coverage_gate_cp10"] is h.coverage
    assert local["task_public_composition_authority_p4_6f"] is h.authority_before
    assert local["task_authority_gate_cp9"] is h.cp9
    assert not _calls(h, "cp10_authority") and not _calls(h, "cp10_canary")
    assert not _calls(h, "cp11")


def test_authority_exact_arguments_identity_and_single_call(monkeypatch):
    h = _install(monkeypatch)
    error = _run(h)
    call = _calls(h, "cp10_authority")[0]
    local = _locals(error)
    assert call[1] == (h.answer, local["legacy_answer_before_public_composition_canary"],
                       h.authority_before, h.coverage)
    assert call[1][0] is h.answer
    assert call[1][1] == h.legacy
    assert call[1][2] is h.authority_before
    assert call[1][3] is h.coverage
    assert call[2] == {} and len(_calls(h, "cp10_authority")) == 1


def _two_values():
    yield object()
    yield object()


@pytest.mark.parametrize(
    "returned,expected",
    [
        pytest.param(("tuple-answer", object()), "tuple-answer", id="tuple"),
        pytest.param(["list-answer", object()], "list-answer", id="list"),
        pytest.param({"dict-answer": 1, "dict-authority": 2}, "dict-answer", id="dict"),
        pytest.param(_two_values(), None, id="generator"),
    ],
)
def test_authority_exact_python_two_value_unpacking(monkeypatch, returned, expected):
    h = _install(monkeypatch, authority_return=returned)
    local = _locals(_run(h))
    if expected is None:
        assert local["answer"] is not h.answer
    else:
        assert local["answer"] == expected
    if isinstance(returned, (tuple, list)):
        assert local["task_public_composition_authority_p4_6f"] is returned[1]
    elif isinstance(returned, dict):
        assert local["task_public_composition_authority_p4_6f"] == "dict-authority"
    assert len(_calls(h, "cp10_authority")) == 1


@pytest.mark.parametrize(
    "returned,error_type",
    [(None, TypeError), (object(), TypeError), ((), ValueError), ((1,), ValueError),
     ((1, 2, 3), ValueError)],
)
def test_authority_malformed_return_propagates_without_retry(
    monkeypatch, returned, error_type
):
    h = _install(monkeypatch, authority_return=returned)
    _run(h, error_type)
    assert len(_calls(h, "cp10_authority")) == 1
    assert not _calls(h, "cp10_canary") and not _calls(h, "cp11")


@pytest.mark.parametrize("error", [RuntimeError("ordinary"), Fatal("fatal")])
def test_authority_exception_and_baseexception_propagate(monkeypatch, error):
    h = _install(monkeypatch, authority_error=error)
    assert _run(h, type(error)) is error
    assert len(_calls(h, "cp10_authority")) == 1
    assert not _calls(h, "cp10_canary") and not _calls(h, "cp11")


@pytest.mark.parametrize("error", [RuntimeError("unpack"), Fatal("unpack fatal")])
def test_authority_unpack_iteration_error_propagates(monkeypatch, error):
    h = _install(monkeypatch, authority_return=IterationFailure(error))
    assert _run(h, type(error)) is error
    assert len(_calls(h, "cp10_authority")) == 1 and not _calls(h, "cp10_canary")


def test_pipeline_write_order_keys_identity_and_prior_keys(monkeypatch):
    old = object()
    pipeline = PipelineProbe({"prior": old, "public_composition_canary_shadow": object()})
    guarded_answer, guarded_authority, guarded_canary = object(), object(), object()
    h = _install(monkeypatch, pipeline_factory=pipeline,
                 authority_return=(guarded_answer, guarded_authority),
                 canary_return=guarded_canary)
    _run(h)
    assert [key for key, _ in pipeline.set_calls] == [
        "task_public_composition_authority_p4_6f",
        "public_composition_canary_shadow",
        "task_coverage_gate_cp10",
    ]
    assert pipeline["prior"] is old
    assert pipeline.set_calls[0][1] is guarded_authority
    assert pipeline.set_calls[1][1] is guarded_canary
    assert pipeline.set_calls[2][1] is h.coverage
    assert h.events.index("cp10_authority") < h.events.index("cp10_canary") < h.events.index("cp11")


@pytest.mark.parametrize("fail_at,expected_keys,canary_calls", [(1, [], 0), (2, ["task_public_composition_authority_p4_6f"], 1), (3, ["task_public_composition_authority_p4_6f", "public_composition_canary_shadow"], 1)])
def test_setitem_errors_preserve_exact_partial_mutations(
    monkeypatch, fail_at, expected_keys, canary_calls
):
    failure = RuntimeError("setitem")
    pipeline = PipelineProbe({"prior": object()}, fail_set_at=fail_at, error=failure)
    h = _install(monkeypatch, pipeline_factory=pipeline)
    assert _run(h, RuntimeError) is failure
    assert [key for key, _ in pipeline.successful_set_calls] == expected_keys
    assert len(_calls(h, "cp10_canary")) == canary_calls and not _calls(h, "cp11")


def test_canary_exact_get_arguments_raw_return_and_cp10_gate(monkeypatch):
    shadow = object()
    returned = object()
    pipeline = PipelineProbe({"public_composition_canary_shadow": shadow})
    h = _install(monkeypatch, pipeline_factory=pipeline, canary_return=returned)
    _run(h)
    call = _calls(h, "cp10_canary")[0]
    assert call[1] == (h.stage_canary_shadow[0], h.coverage) and call[2] == {}
    assert call[1][0] is h.stage_canary_shadow[0]
    assert call[1][1] is h.coverage
    assert pipeline["public_composition_canary_shadow"] is returned
    assert h.coverage is not h.cp9 and len(_calls(h, "cp10_canary")) == 1


def test_cp11_boundary_receives_post_cp10_authority_and_coverage(monkeypatch):
    grounded = object()
    pipeline = PipelineProbe({
        "task_grounded_synthesis_coverage_authority_p4_6e3": grounded,
    })
    answer, authority = object(), object()
    h = _install(monkeypatch, pipeline_factory=pipeline,
                 authority_return=(answer, authority))
    _run(h)
    call = _calls(h, "cp11")[0]
    assert call[1] == (h.plan, h.legacy, h.coverage, grounded, authority)
    assert call[1][0] is h.plan
    assert call[1][1] == h.legacy
    assert call[1][2] is h.coverage
    assert call[1][3] is grounded
    assert call[1][4] is authority
    assert call[2] == {}


@pytest.mark.parametrize("error", [RuntimeError("get"), Fatal("get fatal")])
def test_canary_get_error_propagates_after_first_write(monkeypatch, error):
    pipeline = PipelineProbe(fail_get="public_composition_canary_shadow", error=error)
    h = _install(monkeypatch, pipeline_factory=pipeline)
    assert _run(h, type(error)) is error
    assert "task_public_composition_authority_p4_6f" in pipeline
    assert not _calls(h, "cp10_canary") and not _calls(h, "cp11")


@pytest.mark.parametrize("error", [RuntimeError("call"), Fatal("call fatal")])
def test_canary_call_error_propagates_without_final_writes(monkeypatch, error):
    pipeline = PipelineProbe()
    h = _install(monkeypatch, pipeline_factory=pipeline, canary_error=error)
    assert _run(h, type(error)) is error
    assert [key for key, _ in pipeline.set_calls] == [
        "task_public_composition_authority_p4_6f"
    ]
    assert len(_calls(h, "cp10_canary")) == 1 and not _calls(h, "cp11")


def test_cp11_stop_captures_exact_locals_and_order_without_upstream_repeats(monkeypatch):
    pipeline = PipelineProbe()
    answer, authority = object(), object()
    h = _install(monkeypatch, pipeline_factory=pipeline,
                 authority_return=(answer, authority))
    local = _locals(_run(h))
    assert h.events[-4:] == ["3z2a", "cp10_authority", "cp10_canary", "cp11"]
    assert local["answer"] is answer
    assert local["legacy_answer_before_public_composition_canary"] == h.legacy
    assert local["task_public_composition_authority_p4_6f"] is authority
    assert local["task_coverage_gate_cp10"] is h.coverage
    assert local["task_authority_gate_cp9"] is h.cp9
    assert local["evidence_pipeline"] is pipeline
    for name in ("3z2a", "cp10_authority", "cp10_canary", "cp11"):
        assert len(_calls(h, name)) == 1
    assert (dict(vars(h.plan)), h.results, h.typed, h.trace) == h.before


def test_cp11_error_does_not_repeat_cp10_or_upstream(monkeypatch):
    failure = Fatal("cp11 fatal")
    h = _install(monkeypatch, cp11_error=failure)
    assert _run(h, Fatal) is failure
    for name in ("3z2a", "cp10_authority", "cp10_canary", "cp11"):
        assert len(_calls(h, name)) == 1
    for name in ("answer", "shadow", "canary"):
        assert len(_calls(h, name)) == 1


def test_fresh_state_per_core_invocation(monkeypatch):
    first = _install(monkeypatch, pipeline_factory=dict)
    _run(first)
    first.pipeline["mutation"] = object()
    second = _install(monkeypatch, pipeline_factory=dict)
    _run(second)
    assert first.pipeline is not second.pipeline
    assert "mutation" not in second.pipeline
    assert first.stage_result is not second.stage_result


def test_ast_cardinality_order_typegate_and_three_writes():
    tree = ast.parse(Path(service.__file__).read_text(encoding="utf-8"))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name == "run_orchestrator")
    calls = [node for node in ast.walk(function) if isinstance(node, ast.Call)]

    def named(name):
        return [node for node in calls if isinstance(node.func, ast.Name)
                and node.func.id == name]

    stage = named("run_p4_6f_cp9_authority_entry_stage")
    authority = named("guard_task_coverage_authority")
    canary = named("guard_public_composition_canary")
    cp11 = named("present_relevant_task_answer")
    assert tuple(map(len, (stage, authority, canary, cp11))) == (1, 1, 1, 1)
    assert stage[0].lineno < authority[0].lineno < canary[0].lineno < cp11[0].lineno
    gate = next(node for node in function.body if isinstance(node, ast.If)
                and any(call is authority[0] for call in ast.walk(node)))
    assert isinstance(gate.test, ast.Call)
    assert isinstance(gate.test.func, ast.Name) and gate.test.func.id == "isinstance"
    assert [getattr(arg, "id", None) for arg in gate.test.args] == [
        "evidence_pipeline", "dict"
    ]
    assert [arg.id for arg in authority[0].args] == [
        "answer", "legacy_answer_before_public_composition_canary",
        "task_public_composition_authority_p4_6f", "task_coverage_gate_cp10",
    ]
    assert [arg.id for arg in canary[0].args[1:]] == ["task_coverage_gate_cp10"]
