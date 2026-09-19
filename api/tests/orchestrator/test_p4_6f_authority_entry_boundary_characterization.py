"""Characterize the service-owned P4.6F authority entry up to CP9."""
from __future__ import annotations

import ast
import importlib.util
from collections import UserDict
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.orchestrator import service
from app.orchestrator.models import OrchestratorAskRequest


class StopAtCP9(BaseException):
    pass


class Fatal(BaseException):
    pass


class DictSubclass(dict):
    pass


class RaisingGet(dict):
    def __init__(self, error, key):
        super().__init__()
        self.error = error
        self.key = key

    def get(self, key, *args, **kwargs):
        if key == self.key:
            raise self.error
        return super().get(key, *args, **kwargs)


class RaisingNthGet(dict):
    def __init__(self, error, key, occurrence):
        super().__init__()
        self.error = error
        self.key = key
        self.occurrence = occurrence
        self.seen = 0

    def get(self, key, *args, **kwargs):
        if key == self.key:
            self.seen += 1
            if self.seen == self.occurrence:
                raise self.error
        return super().get(key, *args, **kwargs)


class SetItemProbe(dict):
    def __init__(self, error=None):
        super().__init__()
        self.error = error
        self.set_calls = []

    def __setitem__(self, key, value):
        self.set_calls.append((key, value))
        if self.error is not None and key == "task_research_semantics_cp13":
            raise self.error
        super().__setitem__(key, value)


class RaisingComplexity:
    def __init__(self, error):
        self.error = error

    def __iter__(self):
        raise self.error


class UnpackFatal:
    def __iter__(self):
        raise Fatal("synthetic unpack fatal")


FALLBACK = {
    "contract_version": "promati.orchestrator.task_research_semantics.cp13.v1",
    "evaluated": False,
    "authoritative": False,
    "authority_scope": "intent_task_research_eligibility_only",
    "public_answer_authority": False,
    "evidence_authority": False,
    "synthesis_authority": False,
    "legacy_generic_research_allowed": False,
    "explicit_research_requested": False,
    "allowed_task_ids": [],
    "tasks": [],
    "reason": "internal_error_fail_closed",
}

_DEFAULT = object()


def _prior_characterization():
    path = Path(__file__).with_name(
        "test_composition_shadow_canary_boundary_characterization.py"
    )
    spec = importlib.util.spec_from_file_location("composition_3y1_for_3z1a", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _install(
    monkeypatch,
    *,
    pipeline_factory=dict,
    profile_missing=True,
    profile=None,
    coverage_return=_DEFAULT,
    coverage_error=None,
    cp13_return=_DEFAULT,
    cp13_error=None,
    authority_return=_DEFAULT,
    authority_error=None,
    cp9_error=None,
    stop_at_coverage=False,
):
    prior = _prior_characterization()
    pipeline = pipeline_factory() if callable(pipeline_factory) else pipeline_factory
    h = prior._install(monkeypatch, pipeline=[])
    h.pipeline = pipeline
    monkeypatch.setattr(service, "_evidence_pipeline_to_dict", lambda *_a, **_k: pipeline)
    h.plan.complexity_reasons = None
    coverage_value = object() if coverage_return is _DEFAULT else coverage_return
    cp13_value = object() if cp13_return is _DEFAULT else cp13_return
    authority_value = (("synthetic authority answer", object())
                       if authority_return is _DEFAULT else authority_return)
    boundary = StopAtCP9("controlled CP9 stop boundary")
    calls = h.calls
    events = h.events
    shadow_box = [None]

    def coverage(*args, **kwargs):
        events.append("coverage")
        calls.append(("coverage", args, kwargs))
        shadow_box[0] = args[0]
        if coverage_error is not None:
            raise coverage_error
        if stop_at_coverage:
            raise boundary
        return coverage_value

    def cp13(*args, **kwargs):
        events.append("cp13")
        calls.append(("cp13", args, kwargs))
        if cp13_error is not None:
            raise cp13_error
        return cp13_value

    def authority(*args, **kwargs):
        events.append("authority")
        calls.append(("authority", args, kwargs))
        if authority_error is not None:
            raise authority_error
        return authority_value

    def cp9(*args, **kwargs):
        events.append("cp9")
        calls.append(("cp9", args, kwargs))
        raise boundary if cp9_error is None else cp9_error

    monkeypatch.setattr(service, "build_task_coverage_gate_status", coverage)
    monkeypatch.setattr(service, "build_task_research_semantics", cp13)
    monkeypatch.setattr(
        service, "build_public_multi_intent_composition_authority_canary_p4_6f",
        authority,
    )
    monkeypatch.setattr(service, "guard_public_composition_authority", cp9)
    payload = OrchestratorAskRequest(q="synthetic", vraag="")
    if not profile_missing:
        object.__setattr__(payload, "response_profile", profile)
    before = (
        dict(vars(h.plan)), list(h.results), list(h.typed), dict(h.trace),
        "synthetic canary answer", "synthetic legacy answer",
    )
    return SimpleNamespace(
        **locals(), plan=h.plan, results=h.results, typed=h.typed, trace=h.trace,
    )


def _run(h, exception=StopAtCP9):
    with pytest.raises(exception) as raised:
        service._p4_15cp3c_previous_run_orchestrator(h.payload, sender=object())
    return raised.value


def _locals(error):
    traceback = error.__traceback__
    while traceback is not None:
        if traceback.tb_frame.f_code is service.run_p4_6f_cp9_authority_entry_stage.__code__:
            return traceback.tb_frame.f_locals
        traceback = traceback.tb_next
    raise AssertionError("service frame absent")


def _calls(h, name):
    return [call for call in h.calls if call[0] == name]


@pytest.mark.parametrize(
    "missing,profile,coerced",
    [
        (True, None, False), (False, None, False), (False, "compact", False),
        (False, "debug", True), (False, "DEBUG", False),
        (False, "Debug", False), (False, "synthetic", False),
    ],
)
def test_response_profile_exact_debug_gate(monkeypatch, missing, profile, coerced):
    original = []
    h = _install(
        monkeypatch, pipeline_factory=original,
        profile_missing=missing, profile=profile, stop_at_coverage=not coerced,
    )
    error = _run(h)
    local = _locals(error)
    assert local["cp11_debug_response"] is coerced
    assert isinstance(local["evidence_pipeline"], dict) is coerced
    assert (local["evidence_pipeline"] is original) is not coerced
    assert bool(_calls(h, "cp13")) is coerced


@pytest.mark.parametrize(
    "factory",
    [dict, DictSubclass, UserDict, list, lambda: None, object],
)
def test_pipeline_typegate_identity_and_no_nondebug_coercion(monkeypatch, factory):
    pipeline = factory()
    is_dict = isinstance(pipeline, dict)
    h = _install(
        monkeypatch, pipeline_factory=pipeline, stop_at_coverage=not is_dict
    )
    error = _run(h)
    local = _locals(error)
    assert local["evidence_pipeline"] is pipeline
    assert bool(_calls(h, "cp13")) is is_dict
    assert bool(_calls(h, "authority")) is is_dict
    assert bool(_calls(h, "cp9")) is is_dict
    assert _calls(h, "coverage")[0][1][1] is None


def test_debug_preserves_real_dict_and_subclass_identity(monkeypatch):
    for factory in (dict, DictSubclass):
        pipeline = factory()
        h = _install(monkeypatch, pipeline_factory=pipeline, profile_missing=False, profile="debug")
        error = _run(h)
        assert _locals(error)["evidence_pipeline"] is pipeline


def test_precoverage_bindings_have_exact_fresh_defaults(monkeypatch):
    h = _install(monkeypatch, stop_at_coverage=True)
    local = _locals(_run(h))
    assert local["answer_before_p4_6f_public_composition"] is local["answer"]
    assert local["task_public_composition_authority_p4_6f"] is None
    assert local["cp11_debug_response"] is False
    assert local["evidence_pipeline"] is h.pipeline


def test_fresh_defaults_and_boundary_locals_order_and_immutability(monkeypatch):
    coverage = object()
    cp13 = object()
    authority = object()
    h = _install(
        monkeypatch, coverage_return=coverage, cp13_return=cp13,
        authority_return=("new answer", authority),
    )
    error = _run(h)
    local = _locals(error)
    assert h.events[-5:] == ["canary", "coverage", "cp13", "authority", "cp9"]
    assert local["answer"] == "new answer"
    assert local["answer_before_p4_6f_public_composition"] == "synthetic canary answer"
    assert local["legacy_answer_before_public_composition_canary"] == "synthetic legacy answer"
    assert local["task_public_composition_authority_p4_6f"] is authority
    assert local["task_execution_shadow"] is h.shadow_box[0]
    assert local["task_coverage_gate_cp10"] is coverage
    assert local["task_research_semantics_cp13"] is cp13
    assert local["evidence_pipeline"] is h.pipeline
    assert (dict(vars(h.plan)), h.results, h.typed, h.trace, "synthetic canary answer",
            "synthetic legacy answer") == h.before
    for name in ("answer", "shadow", "canary", "coverage", "cp13", "authority", "cp9"):
        assert len(_calls(h, name)) == 1


@pytest.mark.parametrize("returned", [None, False, 0, "", [], (), {}, object()])
def test_coverage_raw_return_identity_exact_arguments_and_single_call(monkeypatch, returned):
    authority = object()
    pipeline = {"task_grounded_synthesis_coverage_authority_p4_6e3": authority}
    h = _install(monkeypatch, pipeline_factory=pipeline, coverage_return=returned)
    error = _run(h)
    call = _calls(h, "coverage")[0]
    assert call[1] == (h.shadow_box[0], authority) and call[2] == {}
    assert call[1][0] is h.shadow_box[0] and call[1][1] is authority
    assert _locals(error)["task_coverage_gate_cp10"] is returned
    assert _calls(h, "cp13")[0][1][3] is returned
    assert len(_calls(h, "coverage")) == 1


@pytest.mark.parametrize("error", [RuntimeError("ordinary"), Fatal("fatal")])
def test_coverage_exception_and_baseexception_propagate(monkeypatch, error):
    h = _install(monkeypatch, coverage_error=error)
    raised = _run(h, type(error))
    assert raised is error
    assert len(_calls(h, "coverage")) == 1
    assert not _calls(h, "cp13") and not _calls(h, "authority") and not _calls(h, "cp9")


@pytest.mark.parametrize("error", [RuntimeError("get"), Fatal("get fatal")])
@pytest.mark.parametrize(
    "key,occurrence,expected_calls",
    [
        ("task_grounded_synthesis_coverage_authority_p4_6e3", 1, (0, 0, 0)),
        ("task_research_authority_p4_6d1", 1, (1, 0, 0)),
        ("task_grounded_synthesis_coverage_authority_p4_6e3", 2, (1, 1, 0)),
    ],
)
def test_pipeline_get_errors_propagate_at_exact_boundary(
    monkeypatch, error, key, occurrence, expected_calls
):
    h = _install(
        monkeypatch,
        pipeline_factory=lambda: RaisingNthGet(error, key, occurrence),
    )
    caught_inside_cp13_or_authority = (
        isinstance(error, Exception)
        and not (
            key == "task_grounded_synthesis_coverage_authority_p4_6e3"
            and occurrence == 1
        )
    )
    if caught_inside_cp13_or_authority:
        _run(h)
        expected_calls = (
            (1, 0, 1)
            if key == "task_research_authority_p4_6d1"
            else (1, 1, 0)
        )
        assert len(_calls(h, "cp9")) == 1
    else:
        raised = _run(h, type(error))
        assert raised is error
        assert not _calls(h, "cp9")
    assert tuple(len(_calls(h, name)) for name in ("coverage", "cp13", "authority")) == expected_calls


def test_cp13_exact_arguments_raw_storage_and_single_call(monkeypatch):
    research = object()
    coverage = object()
    returned = object()
    pipeline = {"task_research_authority_p4_6d1": research}
    h = _install(
        monkeypatch, pipeline_factory=pipeline,
        coverage_return=coverage, cp13_return=returned,
    )
    error = _run(h)
    call = _calls(h, "cp13")[0]
    assert call[1] == (h.plan, h.shadow_box[0], research, coverage) and call[2] == {}
    assert all(actual is expected for actual, expected in zip(
        call[1], (h.plan, h.shadow_box[0], research, coverage)
    ))
    assert pipeline["task_research_semantics_cp13"] is returned
    assert _locals(error)["task_research_semantics_cp13"] is returned
    assert len(_calls(h, "cp13")) == 1


@pytest.mark.parametrize(
    "reasons,expected",
    [
        (None, False), ([], False), (set(), False),
        (["explicit_research_request"], True),
        ({"explicit_research_request"}, True),
        ("explicit_research_request", False),
        ("prefix explicit_research_request suffix", False),
        (123, None),
    ],
)
def test_cp13_exception_fallback_exact_complexity_semantics(monkeypatch, reasons, expected):
    h = _install(monkeypatch, cp13_error=RuntimeError("ordinary"))
    h.plan.complexity_reasons = reasons
    if expected is None:
        _run(h, TypeError)
        assert not _calls(h, "authority") and not _calls(h, "cp9")
        return
    error = _run(h)
    fallback = _locals(error)["task_research_semantics_cp13"]
    wanted = dict(FALLBACK, explicit_research_requested=expected)
    assert fallback == wanted and set(fallback) == set(wanted)
    assert h.pipeline["task_research_semantics_cp13"] is fallback


def test_cp13_fallback_state_is_fresh_without_leakage(monkeypatch):
    h = _install(monkeypatch, cp13_error=RuntimeError("ordinary"))
    first = _locals(_run(h))["task_research_semantics_cp13"]
    first["allowed_task_ids"].append("mutation")
    first["tasks"].append("mutation")
    second = _locals(_run(h))["task_research_semantics_cp13"]
    assert second == FALLBACK and first is not second
    assert first["allowed_task_ids"] is not second["allowed_task_ids"]
    assert first["tasks"] is not second["tasks"]


@pytest.mark.parametrize("error", [Fatal("cp13 fatal")])
def test_cp13_baseexception_propagates(monkeypatch, error):
    h = _install(monkeypatch, cp13_error=error)
    raised = _run(h, Fatal)
    assert raised is error and len(_calls(h, "cp13")) == 1
    assert not _calls(h, "authority") and not _calls(h, "cp9")


@pytest.mark.parametrize("error", [RuntimeError("iteration"), Fatal("iteration fatal")])
def test_cp13_fallback_iteration_error_propagates(monkeypatch, error):
    h = _install(monkeypatch, cp13_error=RuntimeError("ordinary"))
    h.plan.complexity_reasons = RaisingComplexity(error)
    raised = _run(h, type(error))
    assert raised is error
    assert "task_research_semantics_cp13" not in h.pipeline
    assert not _calls(h, "authority") and not _calls(h, "cp9")


@pytest.mark.parametrize("error", [RuntimeError("setitem"), Fatal("setitem fatal")])
def test_cp13_setitem_error_preserves_partial_mutation_contract(monkeypatch, error):
    pipeline = SetItemProbe(error)
    h = _install(monkeypatch, pipeline_factory=pipeline, cp13_return=object())
    raised = _run(h, type(error))
    assert raised is error
    assert pipeline.set_calls[-1][0] == "task_research_semantics_cp13"
    assert sum(key == "task_research_semantics_cp13" for key, _ in pipeline.set_calls) == 1
    assert not _calls(h, "authority") and not _calls(h, "cp9")


@pytest.mark.parametrize(
    "returned,expected_answer,expected_authority",
    [
        (("new", None), "new", None),
        (["new", False], "new", False),
        ({"answer": 1, "authority": 2}, "answer", "authority"),
    ],
)
def test_authority_python_unpacking_exact_arguments_and_identity(
    monkeypatch, returned, expected_answer, expected_authority
):
    coverage_authority = object()
    pipeline = {"task_grounded_synthesis_coverage_authority_p4_6e3": coverage_authority}
    h = _install(monkeypatch, pipeline_factory=pipeline, authority_return=returned)
    error = _run(h)
    call = _calls(h, "authority")[0]
    assert call[1][0] is h.plan
    assert call[1][1] == "synthetic canary answer"
    assert call[1][2] is coverage_authority and call[2] == {}
    local = _locals(error)
    assert local["answer"] == expected_answer
    assert local["task_public_composition_authority_p4_6f"] == expected_authority
    if not isinstance(expected_authority, str):
        assert local["task_public_composition_authority_p4_6f"] is returned[1]
    assert len(_calls(h, "authority")) == 1


@pytest.mark.parametrize("returned", [None, object(), (), (1,), (1, 2, 3)])
def test_authority_malformed_return_fails_open(monkeypatch, returned):
    h = _install(monkeypatch, authority_return=returned)
    error = _run(h)
    local = _locals(error)
    assert local["answer"] == "synthetic canary answer"
    assert local["task_public_composition_authority_p4_6f"] is None
    assert _calls(h, "cp9")[0][1][:3] == (
        "synthetic canary answer", "synthetic legacy answer", None
    )


@pytest.mark.parametrize("error", [RuntimeError("ordinary")])
def test_authority_exception_fails_open_exactly(monkeypatch, error):
    h = _install(monkeypatch, authority_error=error)
    boundary = _run(h)
    local = _locals(boundary)
    assert local["answer"] == local["answer_before_p4_6f_public_composition"]
    assert local["task_public_composition_authority_p4_6f"] is None
    assert len(_calls(h, "authority")) == len(_calls(h, "cp9")) == 1


def test_authority_baseexception_and_unpack_baseexception_propagate(monkeypatch):
    for kwargs in (
        {"authority_error": Fatal("authority fatal")},
        {"authority_return": UnpackFatal()},
    ):
        h = _install(monkeypatch, **kwargs)
        _run(h, Fatal)
        assert len(_calls(h, "authority")) == 1 and not _calls(h, "cp9")


def test_cp9_exact_stop_arguments_and_failure_never_repeats_upstream(monkeypatch):
    authority = object()
    h = _install(monkeypatch, authority_return=("new", authority))
    _run(h)
    cp9 = _calls(h, "cp9")[0]
    assert cp9[1] == ("new", "synthetic legacy answer", authority, h.shadow_box[0])
    assert cp9[1][2] is authority and cp9[1][3] is h.shadow_box[0] and cp9[2] == {}
    for name in ("answer", "shadow", "canary", "coverage", "cp13", "authority", "cp9"):
        assert len(_calls(h, name)) == 1


def test_cp9_ordinary_exception_propagates_without_retry(monkeypatch):
    failure = RuntimeError("synthetic CP9 failure")
    h = _install(monkeypatch, cp9_error=failure)
    raised = _run(h, RuntimeError)
    assert raised is failure
    for name in ("coverage", "cp13", "authority", "cp9"):
        assert len(_calls(h, name)) == 1


def test_ast_exact_stage_order_bindings_dependencies_and_cp10_stop_boundary():
    path = Path(service.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    function = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "run_orchestrator"
    )
    calls = [node for node in ast.walk(function) if isinstance(node, ast.Call)]

    def named(name):
        return [node for node in calls
                if isinstance(node.func, ast.Name) and node.func.id == name]

    stage_3y2 = named("run_composition_shadow_canary_stage")
    stage_3z2a = named("run_p4_6f_cp9_authority_entry_stage")
    stage_3z2b = named("run_cp10_authority_rollback_stage")
    assert len(stage_3y2) == len(stage_3z2a) == len(stage_3z2b) == 1
    assert stage_3y2[0].lineno < stage_3z2a[0].lineno < stage_3z2b[0].lineno
    assert [arg.id for arg in stage_3z2a[0].args] == [
        "plan", "answer", "legacy_answer_before_public_composition_canary",
        "evidence_pipeline", "task_execution_shadow", "cp11_debug_response",
    ]
    assert {keyword.arg for keyword in stage_3z2a[0].keywords} == {
        "build_task_coverage_gate_status",
        "build_task_research_semantics",
        "build_public_multi_intent_composition_authority_canary_p4_6f",
        "guard_public_composition_authority",
        "guard_public_composition_canary",
    }
    assignments = [
        node for node in function.body
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Attribute)
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "p4_6f_cp9_authority_entry_stage_result"
    ]
    assert [(node.targets[0].id, node.value.attr) for node in assignments] == [
        ("answer", "answer"),
        ("evidence_pipeline", "evidence_pipeline"),
        ("task_research_semantics_cp13", "task_research_semantics_cp13"),
        ("task_coverage_gate_cp10", "task_coverage_gate_cp10"),
        (
            "task_public_composition_authority_p4_6f",
            "task_public_composition_authority_p4_6f",
        ),
        ("task_authority_gate_cp9", "task_authority_gate_cp9"),
    ]
