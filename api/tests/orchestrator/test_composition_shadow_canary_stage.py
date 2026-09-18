from dataclasses import FrozenInstanceError, fields

import pytest

from app.orchestrator.composition_shadow_canary_stage import (
    CompositionShadowCanaryStageResult,
    run_composition_shadow_canary_stage,
)


class Fatal(BaseException):
    pass


class SetItemProbe(dict):
    def __init__(self, failures):
        super().__init__()
        self.failures = failures
        self.calls = []

    def __setitem__(self, key, value):
        self.calls.append((key, value))
        if self.failures:
            self.failures -= 1
            raise RuntimeError("setitem")
        super().__setitem__(key, value)


def _run(
    pipeline,
    *,
    shadow=None,
    canary=("new", None),
    enabled=False,
):
    calls = []

    def build(*args):
        calls.append(("shadow", args))
        if isinstance(shadow, BaseException):
            raise shadow
        return shadow

    def apply(*args):
        calls.append(("canary", args))
        if isinstance(canary, BaseException):
            raise canary
        return canary

    def config():
        calls.append(("config", ()))
        if callable(enabled):
            return enabled()
        if isinstance(enabled, BaseException):
            raise enabled
        return enabled

    result = run_composition_shadow_canary_stage(
        object(), "legacy", pipeline,
        build_multi_intent_composition_shadow=build,
        maybe_apply_public_composition_canary=apply,
        public_composition_canary_enabled=config,
    )
    return result, calls


def test_frozen_exact_three_field_contract_and_order():
    assert [field.name for field in fields(CompositionShadowCanaryStageResult)] == [
        "answer", "legacy_answer_before_public_composition_canary", "evidence_pipeline",
    ]
    result = CompositionShadowCanaryStageResult(1, 2, 3)
    with pytest.raises(FrozenInstanceError):
        result.answer = 4


@pytest.mark.parametrize("pipeline,accepted", [({}, True), (type("D", (dict,), {})(), True), ([], False), (None, False)])
def test_exact_dict_gate(pipeline, accepted):
    result, calls = _run(pipeline)
    assert [name for name, _ in calls] == (["shadow", "canary"] if accepted else [])
    assert result.evidence_pipeline is pipeline


def test_raw_shadow_identity_arguments_and_maximum_one_call():
    pipeline, shadow, plan = {}, object(), object()
    calls = []
    result = run_composition_shadow_canary_stage(
        plan, "legacy", pipeline,
        build_multi_intent_composition_shadow=lambda *args: calls.append(args) or shadow,
        maybe_apply_public_composition_canary=lambda *_: ("new", object()),
        public_composition_canary_enabled=lambda: False,
    )
    assert pipeline["multi_intent_composition_shadow"] is shadow
    assert calls == [(plan, "legacy", pipeline)]
    assert result.legacy_answer_before_public_composition_canary == "legacy"


def test_shadow_exception_falls_back_and_baseexception_propagates():
    pipeline = {}
    _run(pipeline, shadow=RuntimeError("x"))
    assert pipeline["multi_intent_composition_shadow"] is None
    fatal = Fatal("x")
    with pytest.raises(Fatal) as raised:
        _run({}, shadow=fatal)
    assert raised.value is fatal


@pytest.mark.parametrize("failures,succeeds", [(1, True), (2, False)])
def test_both_shadow_setitem_failure_locations_preserve_partial_mutations(failures, succeeds):
    pipeline = SetItemProbe(failures)
    if succeeds:
        _run(pipeline)
        assert pipeline["multi_intent_composition_shadow"] is None
        assert len(pipeline.calls) == 3
    else:
        with pytest.raises(RuntimeError, match="setitem"):
            _run(pipeline)
        assert len(pipeline.calls) == 2


@pytest.mark.parametrize(
    "returned,answer,shadow",
    [(('new', object()), 'new', None), (['new', 2], 'new', 2), ({'a': 1, 'b': 2}, 'a', 'b')],
)
def test_canary_python_unpacking_and_pipeline_replacement(returned, answer, shadow):
    pipeline = {}
    result, calls = _run(pipeline, canary=returned)
    assert result.answer == answer
    expected = returned[1] if not isinstance(returned, dict) else shadow
    assert pipeline["public_composition_canary_shadow"] is expected or pipeline["public_composition_canary_shadow"] == expected
    assert [name for name, _ in calls].count("canary") == 1


@pytest.mark.parametrize("returned", [None, (), (1,), (1, 2, 3), object()])
def test_malformed_canary_return_fails_open(returned):
    result, calls = _run({}, canary=returned)
    assert result.answer == result.legacy_answer_before_public_composition_canary == "legacy"
    assert result.evidence_pipeline["public_composition_canary_shadow"]["reason"] == "blocked_internal_error_fail_open"
    assert [name for name, _ in calls].count("canary") == 1


def test_canary_exception_fails_open_and_baseexception_propagates():
    result, calls = _run({}, canary=RuntimeError("x"), enabled=True)
    assert result.answer == "legacy"
    assert result.evidence_pipeline["public_composition_canary_shadow"]["enabled"] is True
    assert [name for name, _ in calls].count("config") == 1
    fatal = Fatal("x")
    with pytest.raises(Fatal) as raised:
        _run({}, canary=fatal)
    assert raised.value is fatal


def test_config_is_not_called_on_normal_canary_success():
    _, calls = _run({}, canary=("new", None), enabled=AssertionError("unused"))
    assert [name for name, _ in calls].count("config") == 0


@pytest.mark.parametrize("error", [RuntimeError("config"), Fatal("config")])
def test_config_exception_and_baseexception_preserve_propagation(error):
    config_calls = []

    def config():
        config_calls.append("config")
        raise error

    with pytest.raises(type(error)) as raised:
        _run({}, canary=RuntimeError("canary"), enabled=config)
    assert raised.value is error
    assert config_calls == ["config"]


def test_inputs_have_no_leakage_beyond_pipeline_storage():
    plan = {"plan": []}
    before = {"plan": []}
    pipeline = {}
    run_composition_shadow_canary_stage(
        plan, "legacy", pipeline,
        build_multi_intent_composition_shadow=lambda *_: None,
        maybe_apply_public_composition_canary=lambda *_: ("legacy", None),
        public_composition_canary_enabled=lambda: False,
    )
    assert plan == before
    assert set(pipeline) == {"multi_intent_composition_shadow", "public_composition_canary_shadow"}
