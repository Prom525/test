"""Characterize composition shadow/canary up to the P4.6F boundary."""
from __future__ import annotations

import ast
import importlib.util
from collections import UserDict
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.orchestrator import service
from app.orchestrator.models import OrchestratorAskRequest


class StopAtP46F(BaseException):
    pass


class Fatal(BaseException):
    pass


class DictSubclass(dict):
    pass


class MappingOnly(UserDict):
    pass


class SetItemProbe(dict):
    def __init__(self, *, failures=0):
        super().__init__()
        self.failures = failures
        self.set_calls = []

    def __setitem__(self, key, value):
        self.set_calls.append((key, value))
        if self.failures:
            self.failures -= 1
            raise RuntimeError("synthetic setitem failure")
        super().__setitem__(key, value)


_DEFAULT_CANARY = object()


def _prior_characterization():
    path = Path(__file__).with_name(
        "test_answer_presentation_boundary_characterization.py"
    )
    spec = importlib.util.spec_from_file_location("answer_3x1_for_3y1", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _install(
    monkeypatch, *, pipeline=None, shadow=object(), canary=_DEFAULT_CANARY
):
    prior = _prior_characterization()
    h = prior._install(monkeypatch, answer="synthetic legacy answer")
    if pipeline is None:
        pipeline = {}
    # Replace the 3X1-controlled serializer result without changing its harness.
    monkeypatch.setattr(service, "_evidence_pipeline_to_dict", lambda *_a, **_k: pipeline)
    events = h.events
    calls = h.calls
    shadow_value = shadow
    canary_value = (("synthetic canary answer", object())
                    if canary is _DEFAULT_CANARY else canary)
    boundary = StopAtP46F("controlled P4.6F boundary")

    def build_shadow(*args, **kwargs):
        events.append("shadow")
        calls.append(("shadow", args, kwargs))
        if isinstance(shadow_value, BaseException):
            raise shadow_value
        return shadow_value

    def apply_canary(*args, **kwargs):
        events.append("canary")
        calls.append(("canary", args, kwargs))
        if isinstance(canary_value, BaseException):
            raise canary_value
        return canary_value

    def p46f_boundary(*args, **kwargs):
        events.append("p46f")
        calls.append(("p46f", args, kwargs))
        raise boundary

    monkeypatch.setattr(service, "_build_multi_intent_composition_shadow", build_shadow)
    monkeypatch.setattr(service, "_maybe_apply_public_composition_canary", apply_canary)
    monkeypatch.setattr(service, "_public_composition_canary_enabled", lambda: False)
    monkeypatch.setattr(service, "build_task_coverage_gate_status", p46f_boundary)
    before = (
        dict(vars(h.plan)), list(h.results), list(h.typed), dict(h.trace),
    )
    return SimpleNamespace(
        **locals(),
        plan=h.plan,
        results=h.results,
        typed=h.typed,
        trace=h.trace,
    )


def _run(h, exception=StopAtP46F):
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


def _calls(h, name):
    return [call for call in h.calls if call[0] == name]


@pytest.mark.parametrize(
    "pipeline_factory,accepted",
    [
        (dict, True),
        (DictSubclass, True),
        (MappingOnly, False),
        (list, False),
        (lambda: "malformed", False),
        (lambda: object(), False),
    ],
)
def test_exact_pipeline_type_gate(monkeypatch, pipeline_factory, accepted):
    pipeline = pipeline_factory()
    h = _install(monkeypatch, pipeline=pipeline)
    error = _run(h)
    assert len(_calls(h, "shadow")) == len(_calls(h, "canary")) == int(accepted)
    assert _calls(h, "p46f")[0][1][1] is None
    assert _locals(error)["evidence_pipeline"] is pipeline


def test_none_pipeline_is_rejected_by_exact_dict_gate(monkeypatch):
    h = _install(monkeypatch, pipeline=[])
    h.pipeline = None
    monkeypatch.setattr(service, "_evidence_pipeline_to_dict", lambda *_a, **_k: None)
    error = _run(h)
    assert not _calls(h, "shadow") and not _calls(h, "canary")
    assert _locals(error)["evidence_pipeline"] is None


@pytest.mark.parametrize(
    "returned",
    [{"synthetic": 1}, [1], (1,), None, pytest.param(object(), id="object")],
)
def test_shadow_exact_arguments_identity_and_raw_storage(monkeypatch, returned):
    pipeline = {}
    h = _install(monkeypatch, pipeline=pipeline, shadow=returned)
    error = _run(h)
    call = _calls(h, "shadow")[0]
    assert call[1] == (h.plan, "synthetic legacy answer", pipeline)
    assert call[1][0] is h.plan and call[1][2] is pipeline and call[2] == {}
    assert pipeline["multi_intent_composition_shadow"] is returned
    assert _locals(error)["legacy_answer_before_public_composition_canary"] == "synthetic legacy answer"
    assert len(_calls(h, "shadow")) == 1


def test_shadow_exception_fails_open_to_none_and_continues(monkeypatch):
    pipeline = {}
    h = _install(monkeypatch, pipeline=pipeline, shadow=RuntimeError("synthetic"))
    _run(h)
    assert pipeline["multi_intent_composition_shadow"] is None
    assert len(_calls(h, "shadow")) == len(_calls(h, "canary")) == 1


def test_shadow_baseexception_propagates_identically(monkeypatch):
    fatal = Fatal("synthetic")
    h = _install(monkeypatch, shadow=fatal)
    raised = _run(h, Fatal)
    assert raised is fatal and not _calls(h, "canary") and not _calls(h, "p46f")


@pytest.mark.parametrize("failures,reaches_boundary", [(1, True), (2, False)])
def test_shadow_assignment_failure_and_partial_setitem_contract(
    monkeypatch, failures, reaches_boundary
):
    pipeline = SetItemProbe(failures=failures)
    h = _install(monkeypatch, pipeline=pipeline, shadow=object())
    if reaches_boundary:
        _run(h)
        assert pipeline["multi_intent_composition_shadow"] is None
        assert len(pipeline.set_calls) >= 3  # failed shadow, fallback, canary
    else:
        error = _run(h, RuntimeError)
        assert str(error) == "synthetic setitem failure"
        assert len(pipeline.set_calls) == 2
        assert not _calls(h, "canary") and not _calls(h, "p46f")


@pytest.mark.parametrize(
    "returned,expected_answer,expected_shadow",
    [
        (("new", {"status": 1}), "new", {"status": 1}),
        (["new", [1]], "new", [1]),
        ({"answer_key": 1, "shadow_key": 2}, "answer_key", "shadow_key"),
    ],
)
def test_canary_two_value_unpacking_raw_bindings_and_identity(
    monkeypatch, returned, expected_answer, expected_shadow
):
    pipeline = {}
    h = _install(monkeypatch, pipeline=pipeline, canary=returned)
    error = _run(h)
    call = _calls(h, "canary")[0]
    assert call[1][0] is h.plan and call[1][1] == "synthetic legacy answer"
    assert call[1][2] is pipeline and call[2] == {}
    assert _locals(error)["answer"] == expected_answer
    assert pipeline["public_composition_canary_shadow"] == expected_shadow
    if not isinstance(expected_shadow, str):
        assert pipeline["public_composition_canary_shadow"] is returned[1]
    assert len(_calls(h, "canary")) == 1


@pytest.mark.parametrize("returned", [None, object(), (), (1,), (1, 2, 3)])
def test_malformed_canary_return_fails_open_with_exact_contract(monkeypatch, returned):
    pipeline = {}
    h = _install(monkeypatch, pipeline=pipeline, canary=returned)
    error = _run(h)
    contract = pipeline["public_composition_canary_shadow"]
    assert _locals(error)["answer"] == "synthetic legacy answer"
    assert contract == {
        "contract_version": "promati.multi_intent.public_composition_canary.v1",
        "enabled": False,
        "default_enabled": False,
        "eligible": False,
        "activated": False,
        "public_answer_replaced": False,
        "target": "product_lookup_plus_technical_lookup_cema_definition",
        "release_stage": "narrow_candidate_canary",
        "fail_open_to_legacy_answer": True,
        "release_observability_contract_version": (
            "promati.multi_intent.public_composition_canary_observability.v1"
        ),
        "reason": "blocked_internal_error_fail_open",
    }


def test_canary_exception_uses_runtime_enabled_dependency(monkeypatch):
    enabled_calls = []
    enabled = object()
    h = _install(monkeypatch, canary=RuntimeError("synthetic"))
    monkeypatch.setattr(
        service, "_public_composition_canary_enabled",
        lambda: enabled_calls.append("enabled") or enabled,
    )
    _run(h)
    assert enabled_calls == ["enabled"]
    assert h.pipeline["public_composition_canary_shadow"]["enabled"] is enabled


@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, False), ("", False), ("0", False), ("false", False),
        (" 1 ", True), ("TRUE", True), ("Yes", True), ("on", True),
        ("enabled", False), (object(), False),
    ],
)
def test_real_canary_env_gate_exact_normalization(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv(service._PUBLIC_COMPOSITION_CANARY_ENV, raising=False)
    else:
        monkeypatch.setattr(service.os, "getenv", lambda *_a, **_k: raw)
    assert service._public_composition_canary_enabled() is expected


@pytest.mark.parametrize("multi_intent", [False, None, 0, ""])
def test_real_canary_enabled_gate_blocks_falsey_multi_intent(
    monkeypatch, multi_intent
):
    monkeypatch.setattr(service, "_public_composition_canary_enabled", lambda: True)
    legacy = object()
    returned, contract = service._maybe_apply_public_composition_canary(
        SimpleNamespace(multi_intent=multi_intent), legacy, {}
    )
    assert returned is legacy
    assert contract["enabled"] is True
    assert contract["reason"] == "blocked_not_multi_intent"
    assert contract["public_answer_replaced"] is False


@pytest.mark.parametrize("where", ["canary", "fallback_config"])
def test_canary_baseexception_and_exception_handler_failure_propagate(
    monkeypatch, where
):
    fatal = Fatal("synthetic")
    h = _install(
        monkeypatch,
        canary=fatal if where == "canary" else RuntimeError("synthetic"),
    )
    if where == "fallback_config":
        monkeypatch.setattr(
            service, "_public_composition_canary_enabled",
            lambda: (_ for _ in ()).throw(fatal),
        )
    raised = _run(h, Fatal)
    assert raised is fatal and not _calls(h, "p46f")
    assert len(_calls(h, "canary")) == 1


def test_boundary_locals_order_state_and_no_duplicate_upstream_work(monkeypatch):
    shadow = object()
    canary_shadow = object()
    h = _install(monkeypatch, shadow=shadow, canary=("new", canary_shadow))
    error = _run(h)
    local = _locals(error)
    assert h.events[-3:] == ["shadow", "canary", "p46f"]
    assert local["answer"] == "new"
    assert local["answer_before_p4_6f_public_composition"] == "new"
    assert local["legacy_answer_before_public_composition_canary"] == "synthetic legacy answer"
    assert local["task_public_composition_authority_p4_6f"] is None
    assert local["evidence_pipeline"] is h.pipeline
    assert h.pipeline["multi_intent_composition_shadow"] is shadow
    assert h.pipeline["public_composition_canary_shadow"] is canary_shadow
    assert len(_calls(h, "answer")) == len(_calls(h, "shadow")) == len(_calls(h, "canary")) == 1
    assert (dict(vars(h.plan)), h.results, h.typed, h.trace) == h.before


def test_next_authority_failure_does_not_repeat_shadow_or_canary(monkeypatch):
    h = _install(monkeypatch)
    raised = _run(h)
    assert isinstance(raised, StopAtP46F)
    assert len(_calls(h, "shadow")) == len(_calls(h, "canary")) == 1


def test_ast_exact_order_cardinality_and_observability_is_beyond_boundary():
    path = Path(__file__).parents[2] / "app/orchestrator/service.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    function = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "run_orchestrator"
    )
    calls = [node for node in ast.walk(function) if isinstance(node, ast.Call)]

    def named(name):
        return [
            node for node in calls
            if isinstance(node.func, ast.Name) and node.func.id == name
        ]

    presentation = named("run_answer_presentation_stage")
    shadow = named("_build_multi_intent_composition_shadow")
    canary = named("_maybe_apply_public_composition_canary")
    boundary = named("build_task_coverage_gate_status")
    release = named("_record_public_composition_canary_release_observability")
    assert all(len(nodes) == 1 for nodes in (presentation, shadow, canary, boundary, release))
    assert presentation[0].lineno < shadow[0].lineno < canary[0].lineno < boundary[0].lineno
    assert boundary[0].lineno < release[0].lineno
