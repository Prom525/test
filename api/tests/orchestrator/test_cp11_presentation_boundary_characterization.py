"""Characterize the service-owned CP11 presentation block up to CP12."""
from __future__ import annotations

import ast
import builtins
import importlib.util
from collections import UserDict
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.orchestrator import cp11_presentation_stage, service


class StopAtCP12(BaseException):
    pass


class StopAfterTypeGate(BaseException):
    pass


class Fatal(BaseException):
    pass


class DictSubclass(dict):
    pass


class PipelineProbe(dict):
    def __init__(self, initial=(), *, fail_set_at=None, error=None, fail_get=None):
        super().__init__(initial)
        self.fail_set_at = fail_set_at
        self.error = error
        self.fail_get = fail_get
        self.cp11_set_calls = []
        self.cp11_get_calls = []
        self.cp11_started = False

    def get(self, key, *args, **kwargs):
        if key == "task_grounded_synthesis_coverage_authority_p4_6e3":
            self.cp11_started = True
            self.cp11_get_calls.append((key, args, kwargs))
            if self.fail_get is not None:
                raise self.fail_get
        return super().get(key, *args, **kwargs)

    def __setitem__(self, key, value):
        if self.cp11_started and key in {
            "task_presenter_cp11", "task_public_composition_authority_p4_6f"
        }:
            self.cp11_set_calls.append((key, value))
            if len(self.cp11_set_calls) == self.fail_set_at:
                raise self.error
        super().__setitem__(key, value)


class IterationFailure:
    def __init__(self, error):
        self.error = error

    def __iter__(self):
        raise self.error


class TruthFailure:
    def __init__(self, error):
        self.error = error

    def __bool__(self):
        raise self.error


class MappingFailure:
    def __iter__(self):
        raise RuntimeError("dict conversion")


_DEFAULT = object()


def _prior_characterization():
    path = Path(__file__).with_name(
        "test_cp10_authority_rollback_boundary_characterization.py"
    )
    spec = importlib.util.spec_from_file_location("cp10_3z1b_for_3z1c", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _install(
    monkeypatch,
    *,
    pipeline_factory=PipelineProbe,
    presenter_return=_DEFAULT,
    presenter_error=None,
    authority=_DEFAULT,
    composer_error=None,
):
    prior = _prior_characterization()
    pipeline = pipeline_factory() if callable(pipeline_factory) else pipeline_factory
    authority_value = {} if authority is _DEFAULT else authority
    h = prior._install(
        monkeypatch,
        pipeline_factory=pipeline,
        authority_return=(object(), authority_value),
    )
    legacy = h.legacy
    coverage = h.coverage
    calls = h.calls
    events = h.events
    selected = object()
    presenter = object()
    returned_authority = object()
    returned = (
        (selected, presenter, returned_authority)
        if presenter_return is _DEFAULT else presenter_return
    )
    boundary = StopAtCP12("controlled CP12 stop boundary")
    type_boundary = StopAfterTypeGate("controlled post-typegate stop boundary")

    def cp11(*args, **kwargs):
        events.append("cp11")
        calls.append(("cp11", args, kwargs))
        if presenter_error is not None:
            raise presenter_error
        return returned

    def cp12(*args, **kwargs):
        events.append("cp12")
        calls.append(("cp12", args, kwargs))
        raise boundary if composer_error is None else composer_error

    def after_type_gate(*args, **kwargs):
        events.append("after_type_gate")
        calls.append(("after_type_gate", args, kwargs))
        raise type_boundary

    monkeypatch.setattr(service, "present_relevant_task_answer", cp11)
    monkeypatch.setattr(service, "compose_concise_public_answer", cp12)
    monkeypatch.setattr(
        service, "_record_task_execution_plan_shadow_observability", after_type_gate
    )
    upstream_before = (
        dict(vars(h.plan)), list(h.results), list(h.typed), dict(h.trace)
    )
    return SimpleNamespace(**locals(), plan=h.plan, results=h.results,
                           typed=h.typed, trace=h.trace, payload=h.payload)


def _run(h, exception=StopAtCP12):
    with pytest.raises(exception) as raised:
        service._p4_15cp3c_previous_run_orchestrator(h.payload, sender=object())
    return raised.value


def _locals(error):
    traceback = error.__traceback__
    while traceback is not None:
        if traceback.tb_frame.f_code.co_filename == service.__file__:
            local = traceback.tb_frame.f_locals
            if "cp10_authority_rollback_stage_result" in local:
                return local
        traceback = traceback.tb_next
    raise AssertionError("service frame absent")


def _calls(h, name):
    return [call for call in h.calls if call[0] == name]


@pytest.mark.parametrize("factory", [PipelineProbe, DictSubclass])
def test_typegate_accepts_only_real_dict_family(monkeypatch, factory):
    pipeline = factory()
    h = _install(monkeypatch, pipeline_factory=pipeline)
    local = _locals(_run(h))
    assert local["evidence_pipeline"] is pipeline
    assert len(_calls(h, "cp11")) == len(_calls(h, "cp12")) == 1


@pytest.mark.parametrize("factory", [UserDict, list, tuple, lambda: None, object])
def test_typegate_rejects_non_dict_and_skips_cp11_cp12(monkeypatch, factory):
    pipeline = factory()
    h = _install(monkeypatch, pipeline_factory=pipeline)
    local = _locals(_run(h, StopAfterTypeGate))
    assert local["evidence_pipeline"] is pipeline
    assert "task_presenter_cp11" not in local
    assert not _calls(h, "cp11") and not _calls(h, "cp12")


def test_presenter_exact_runtime_resolved_call_and_get(monkeypatch):
    grounded = object()
    pipeline = PipelineProbe({
        "prior": object(),
        "task_grounded_synthesis_coverage_authority_p4_6e3": grounded,
    })
    authority = object()
    h = _install(monkeypatch, pipeline_factory=pipeline, authority=authority)
    local = _locals(_run(h))
    call = _calls(h, "cp11")[0]
    assert call[1] == (h.plan, h.legacy, h.coverage, grounded, authority)
    assert all(actual is expected for actual, expected in zip(
        call[1], (h.plan, local["legacy_answer_before_public_composition_canary"],
                  h.coverage, grounded, authority)
    ))
    assert call[2] == {}
    assert pipeline.cp11_get_calls == [(
        "task_grounded_synthesis_coverage_authority_p4_6e3", (), {}
    )]


def _three_values():
    yield "generator-answer"
    yield "generator-presenter"
    yield "generator-authority"


@pytest.mark.parametrize(
    "returned,expected",
    [
        (("a", "p", "u"), ("a", "p", "u")),
        (["a", "p", "u"], ("a", "p", "u")),
        ({"a": 1, "p": 2, "u": 3}, ("a", "p", "u")),
        (_three_values(), ("generator-answer", "generator-presenter", "generator-authority")),
    ],
)
def test_exact_python_three_value_unpacking_success(monkeypatch, returned, expected):
    h = _install(monkeypatch, presenter_return=returned)
    local = _locals(_run(h))
    assert tuple(local[name] for name in (
        "answer", "task_presenter_cp11", "task_public_composition_authority_p4_6f"
    )) == expected
    if isinstance(returned, (tuple, list)):
        assert local["answer"] is returned[0]
        assert local["task_presenter_cp11"] is returned[1]
        assert local["task_public_composition_authority_p4_6f"] is returned[2]


@pytest.mark.parametrize("returned", [None, object(), (), (1,), (1, 2), (1, 2, 3, 4)])
def test_malformed_unpack_uses_exact_exception_fallback(monkeypatch, returned):
    h = _install(monkeypatch, presenter_return=returned, authority={"old": object()})
    local = _locals(_run(h))
    fallback = local["task_presenter_cp11"]
    assert local["answer"] == h.legacy
    assert fallback == {
        "contract_version": "promati.orchestrator.task_relevance_presenter.cp11.v1",
        "evaluated": False,
        "authoritative": False,
        "public_answer_replaced": False,
        "reason": "internal_error_fail_closed",
    }
    assert local["task_public_composition_authority_p4_6f"]["task_presenter_cp11"] is fallback
    assert len(_calls(h, "cp11")) == len(_calls(h, "cp12")) == 1


@pytest.mark.parametrize("site", ["get", "presenter", "unpack"])
def test_ordinary_exception_sites_share_fallback(monkeypatch, site):
    error = RuntimeError(site)
    pipeline = PipelineProbe(fail_get=error if site == "get" else None)
    returned = IterationFailure(error) if site == "unpack" else _DEFAULT
    h = _install(
        monkeypatch, pipeline_factory=pipeline, presenter_return=returned,
        presenter_error=error if site == "presenter" else None,
    )
    local = _locals(_run(h))
    assert local["answer"] == h.legacy
    assert local["task_presenter_cp11"]["reason"] == "internal_error_fail_closed"
    assert len(_calls(h, "cp11")) == (0 if site == "get" else 1)


@pytest.mark.parametrize("site", ["get", "presenter", "unpack"])
def test_baseexception_sites_propagate_object_identically(monkeypatch, site):
    error = Fatal(site)
    pipeline = PipelineProbe(fail_get=error if site == "get" else None)
    returned = IterationFailure(error) if site == "unpack" else _DEFAULT
    h = _install(
        monkeypatch, pipeline_factory=pipeline, presenter_return=returned,
        presenter_error=error if site == "presenter" else None,
    )
    assert _run(h, Fatal) is error
    assert not _calls(h, "cp12")


@pytest.mark.parametrize("authority", [None, False, 0, "", UserDict({"old": 1}), DictSubclass(old=1)])
def test_fallback_authority_copy_update_contract(monkeypatch, authority):
    h = _install(monkeypatch, authority=authority, presenter_error=RuntimeError("cp11"))
    local = _locals(_run(h))
    result = local["task_public_composition_authority_p4_6f"]
    assert type(result) is dict
    assert result == ({"old": 1} if isinstance(authority, (UserDict, DictSubclass)) else {}) | {
        "authoritative": False,
        "public_answer_authority": False,
        "public_answer_replaced": False,
        "blocked": True,
        "reason": "presenter_internal_error",
        "task_presenter_cp11": local["task_presenter_cp11"],
    }
    assert result is not authority


@pytest.mark.parametrize("authority,error_type", [
    (MappingFailure(), RuntimeError), (TruthFailure(Fatal("truth")), Fatal)
])
def test_fallback_construction_failures_propagate(monkeypatch, authority, error_type):
    h = _install(monkeypatch, authority=authority, presenter_error=RuntimeError("cp11"))
    error = _run(h, error_type)
    if error_type is Fatal:
        assert error is authority.error
    assert not _calls(h, "cp12")
    assert h.pipeline.cp11_set_calls == []


def test_fallback_update_failure_preserves_constructed_partial_state(monkeypatch):
    class Meta(type):
        def __instancecheck__(cls, instance):
            return isinstance(instance, builtins.dict)

    class FailingDict(dict, metaclass=Meta):
        last = None

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            type(self).last = self

        def update(self, *args, **kwargs):
            raise RuntimeError("update")

    h = _install(monkeypatch, authority={"preserved": object()},
                 presenter_error=RuntimeError("cp11"))
    monkeypatch.setitem(cp11_presentation_stage.__dict__, "dict", FailingDict)
    _run(h, RuntimeError)
    assert list(FailingDict.last) == ["preserved"]
    assert h.pipeline.cp11_set_calls == [] and not _calls(h, "cp12")


def test_pipeline_write_order_identity_existing_keys_and_cp12_arguments(monkeypatch):
    old = object()
    pipeline = PipelineProbe({"prior": old})
    answer, presenter, authority = object(), object(), object()
    h = _install(monkeypatch, pipeline_factory=pipeline,
                 presenter_return=(answer, presenter, authority))
    local = _locals(_run(h))
    assert pipeline.cp11_set_calls == [
        ("task_presenter_cp11", presenter),
        ("task_public_composition_authority_p4_6f", authority),
    ]
    assert pipeline["prior"] is old
    call = _calls(h, "cp12")[0]
    assert call[1] == (answer, h.legacy)
    assert call[1][0] is answer
    assert call[2]["task_coverage_gate_cp10"] is h.coverage
    assert call[2]["task_presenter_cp11"] is presenter
    assert call[2]["response_profile"] == getattr(h.payload, "response_profile", "compact")
    assert local["evidence_pipeline"] is pipeline


@pytest.mark.parametrize("fail_at,successful", [(1, []), (2, ["task_presenter_cp11"])])
@pytest.mark.parametrize("error", [RuntimeError("write"), Fatal("write")])
def test_pipeline_write_failures_propagate_with_exact_partial_mutation(
    monkeypatch, fail_at, successful, error
):
    pipeline = PipelineProbe(fail_set_at=fail_at, error=error)
    h = _install(monkeypatch, pipeline_factory=pipeline)
    assert _run(h, type(error)) is error
    assert [key for key in successful if key in pipeline] == successful
    failed_key = pipeline.cp11_set_calls[-1][0]
    if fail_at == 1:
        assert failed_key not in pipeline
    else:
        assert pipeline[failed_key] is h.authority_value
    assert not _calls(h, "cp12") and len(_calls(h, "cp11")) == 1


def test_cp12_sentinel_does_not_repeat_upstream_and_preserves_inputs(monkeypatch):
    failure = StopAtCP12("cp12 fatal")
    h = _install(monkeypatch, composer_error=failure)
    assert _run(h, StopAtCP12) is failure
    for name in ("3z2a", "cp10_authority", "cp10_canary", "cp11", "cp12"):
        assert len(_calls(h, name)) == 1
    for name in ("answer", "shadow", "canary"):
        assert len(_calls(h, name)) == 1
    assert (dict(vars(h.plan)), h.results, h.typed, h.trace) == h.upstream_before


def test_fallback_reaches_cp12_once_with_fresh_state_per_invocation(monkeypatch):
    first = _install(monkeypatch, presenter_error=RuntimeError("first"))
    first_local = _locals(_run(first))
    second = _install(monkeypatch, presenter_error=RuntimeError("second"))
    second_local = _locals(_run(second))
    assert first.pipeline is not second.pipeline
    assert first_local["task_presenter_cp11"] is not second_local["task_presenter_cp11"]
    assert first_local["task_public_composition_authority_p4_6f"] is not second_local[
        "task_public_composition_authority_p4_6f"
    ]
    assert len(_calls(first, "cp12")) == len(_calls(second, "cp12")) == 1


def test_ast_cardinality_order_gate_calls_writes_and_extractable_shape():
    tree = ast.parse(Path(service.__file__).read_text(encoding="utf-8"))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name == "run_orchestrator")
    calls = [node for node in ast.walk(function) if isinstance(node, ast.Call)]

    def named(name):
        return [node for node in calls if isinstance(node.func, ast.Name)
                and node.func.id == name]

    rollback = named("run_cp10_authority_rollback_stage")
    presenter = named("run_cp11_presentation_stage")
    composer = named("run_cp12_concise_composition_stage")
    assert tuple(map(len, (rollback, presenter, composer))) == (1, 1, 1)
    assert rollback[0].lineno < presenter[0].lineno < composer[0].lineno
    gate = next(node for node in function.body if isinstance(node, ast.If)
                and any(child is presenter[0] for child in ast.walk(node)))
    assert isinstance(gate.test, ast.Call)
    assert isinstance(gate.test.func, ast.Name) and gate.test.func.id == "isinstance"
    assert [arg.id for arg in gate.test.args if isinstance(arg, ast.Name)] == [
        "evidence_pipeline", "dict"
    ]
    assert [arg.id for arg in presenter[0].args] == [
        "plan", "legacy_answer_before_public_composition_canary",
        "task_coverage_gate_cp10", "evidence_pipeline",
        "task_public_composition_authority_p4_6f",
    ]
    assert [(keyword.arg, keyword.value.id) for keyword in presenter[0].keywords] == [
        ("present_relevant_task_answer", "present_relevant_task_answer")
    ]
    bindings = [node for node in gate.body if isinstance(node, ast.Assign)
                and isinstance(node.value, ast.Attribute)
                and isinstance(node.value.value, ast.Name)
                and node.value.value.id == "cp11_presentation_stage_result"]
    assert [(node.targets[0].id, node.value.attr) for node in bindings] == [
        ("answer", "answer"), ("evidence_pipeline", "evidence_pipeline"),
        ("task_presenter_cp11", "task_presenter_cp11"),
        ("task_public_composition_authority_p4_6f",
         "task_public_composition_authority_p4_6f"),
    ]
