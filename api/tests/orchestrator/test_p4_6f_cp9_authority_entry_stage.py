from dataclasses import FrozenInstanceError, fields

import pytest

from app.orchestrator.p4_6f_cp9_authority_entry_stage import (
    P46FCp9AuthorityEntryStageResult,
    run_p4_6f_cp9_authority_entry_stage,
)


class Fatal(BaseException):
    pass


class DictSubclass(dict):
    pass


def _run(pipeline, *, profile=False, cp13=None, authority=("candidate", "auth")):
    plan, shadow, legacy = object(), object(), object()
    calls = []

    def dependency(name, returned):
        def call(*args):
            calls.append((name, args))
            if isinstance(returned, BaseException):
                raise returned
            return returned
        return call

    result = run_p4_6f_cp9_authority_entry_stage(
        plan, "answer", legacy, pipeline, shadow, profile,
        build_task_coverage_gate_status=dependency("coverage", "coverage"),
        build_task_research_semantics=dependency("cp13", cp13),
        build_public_multi_intent_composition_authority_canary_p4_6f=(
            dependency("authority", authority)
        ),
        guard_public_composition_authority=dependency(
            "cp9", ("guarded", "guarded-auth", "cp9")
        ),
        guard_public_composition_canary=dependency("canary", "canary"),
    )
    return result, calls, plan, shadow, legacy


def test_frozen_exact_six_field_contract_and_order():
    assert [field.name for field in fields(P46FCp9AuthorityEntryStageResult)] == [
        "answer", "evidence_pipeline", "task_research_semantics_cp13",
        "task_coverage_gate_cp10", "task_public_composition_authority_p4_6f",
        "task_authority_gate_cp9",
    ]
    result = P46FCp9AuthorityEntryStageResult(*range(6))
    with pytest.raises(FrozenInstanceError):
        result.answer = 9


@pytest.mark.parametrize("factory", [dict, DictSubclass])
def test_dict_and_subclass_identity_exact_arguments_storage_and_order(factory):
    pipeline = factory(
        task_grounded_synthesis_coverage_authority_p4_6e3="grounded",
        task_research_authority_p4_6d1="research",
        public_composition_canary_shadow="old-canary",
    )
    result, calls, plan, shadow, legacy = _run(pipeline, cp13="semantics")
    assert result.evidence_pipeline is pipeline
    assert [name for name, _ in calls] == [
        "coverage", "cp13", "authority", "cp9", "canary",
    ]
    assert calls[0][1] == (shadow, "grounded")
    assert calls[1][1] == (plan, shadow, "research", "coverage")
    assert calls[2][1] == (plan, "answer", "grounded")
    assert calls[3][1] == ("candidate", legacy, "auth", shadow)
    assert calls[4][1] == ("old-canary", "cp9")
    assert result.answer == "guarded"
    assert pipeline == {
        "task_grounded_synthesis_coverage_authority_p4_6e3": "grounded",
        "task_research_authority_p4_6d1": "research",
        "public_composition_canary_shadow": "canary",
        "task_research_semantics_cp13": "semantics",
        "task_public_composition_authority_p4_6f": "guarded-auth",
        "task_authority_gate_cp9": "cp9",
    }


@pytest.mark.parametrize("profile,coerced", [(False, False), (True, True)])
def test_debug_typegate_and_nondict_defaults(profile, coerced):
    original = []
    result, calls, *_ = _run(original, profile=profile)
    assert isinstance(result.evidence_pipeline, dict) is coerced
    assert (result.evidence_pipeline is original) is not coerced
    assert [name for name, _ in calls] == (
        ["coverage", "cp13", "authority", "cp9", "canary"]
        if coerced else ["coverage"]
    )
    assert result.task_public_composition_authority_p4_6f is (
        "guarded-auth" if coerced else None
    )


def test_cp13_exception_uses_fresh_fail_closed_fallback():
    plan = type("Plan", (), {"complexity_reasons": ["explicit_research_request"]})()
    pipelines = [{}, {}]
    results = []
    for pipeline in pipelines:
        result = run_p4_6f_cp9_authority_entry_stage(
            plan, "answer", "legacy", pipeline, object(), False,
            build_task_coverage_gate_status=lambda *_: "coverage",
            build_task_research_semantics=lambda *_: (_ for _ in ()).throw(RuntimeError()),
            build_public_multi_intent_composition_authority_canary_p4_6f=lambda *_: ("a", "b"),
            guard_public_composition_authority=lambda *_: ("a", "b", "cp9"),
            guard_public_composition_canary=lambda *_: "canary",
        )
        results.append(result.task_research_semantics_cp13)
    assert results[0]["explicit_research_requested"] is True
    assert results[0]["allowed_task_ids"] == results[0]["tasks"] == []
    assert results[0] is not results[1]
    assert results[0]["allowed_task_ids"] is not results[1]["allowed_task_ids"]


@pytest.mark.parametrize("failure", [RuntimeError("ordinary"), Fatal("fatal")])
def test_cp13_baseexception_and_ordinary_exception_semantics(failure):
    if isinstance(failure, Fatal):
        with pytest.raises(Fatal) as raised:
            _run({}, cp13=failure)
        assert raised.value is failure
    else:
        result, *_ = _run({}, cp13=failure)
        assert result.task_research_semantics_cp13["reason"] == "internal_error_fail_closed"


@pytest.mark.parametrize("returned", [None, (), (1,), (1, 2, 3), object()])
def test_authority_raw_unpack_fail_open(returned):
    result, calls, *_ = _run({}, authority=returned)
    assert result.answer == "guarded"
    cp9 = next(args for name, args in calls if name == "cp9")
    assert cp9[0] == "answer" and cp9[2] is None
    assert [name for name, _ in calls].count("authority") == 1


def test_authority_exception_fail_open_and_baseexception_propagates():
    result, calls, *_ = _run({}, authority=RuntimeError("ordinary"))
    cp9 = next(args for name, args in calls if name == "cp9")
    assert cp9[0] == "answer" and cp9[2] is None
    fatal = Fatal("fatal")
    with pytest.raises(Fatal) as raised:
        _run({}, authority=fatal)
    assert raised.value is fatal


def test_coverage_exception_propagates_once_without_later_calls():
    calls = []
    failure = RuntimeError("coverage")
    with pytest.raises(RuntimeError) as raised:
        run_p4_6f_cp9_authority_entry_stage(
            object(), "answer", "legacy", {}, object(), False,
            build_task_coverage_gate_status=lambda *_: calls.append("coverage") or (_ for _ in ()).throw(failure),
            build_task_research_semantics=lambda *_: calls.append("cp13"),
            build_public_multi_intent_composition_authority_canary_p4_6f=lambda *_: calls.append("authority"),
            guard_public_composition_authority=lambda *_: calls.append("cp9"),
            guard_public_composition_canary=lambda *_: calls.append("canary"),
        )
    assert raised.value is failure
    assert calls == ["coverage"]


def test_cp13_setitem_failure_preserves_no_later_mutations():
    class Probe(dict):
        def __setitem__(self, key, value):
            if key == "task_research_semantics_cp13":
                raise RuntimeError("setitem")
            super().__setitem__(key, value)

    pipeline = Probe()
    with pytest.raises(RuntimeError, match="setitem"):
        _run(pipeline)
    assert pipeline == {}
