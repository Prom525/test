from dataclasses import FrozenInstanceError, fields

import pytest

from app.orchestrator.phase_c_assessment_gate_stage import (
    PhaseCAssessmentGateStageResult,
    run_phase_c_assessment_gate_stage,
)


class Fatal(BaseException):
    pass


def test_result_is_frozen_exact_two_field_contract():
    assessment, decision = object(), object()
    result = PhaseCAssessmentGateStageResult(assessment, decision)
    assert [field.name for field in fields(result)] == [
        "initial_assessment", "research_decision"]
    assert result.initial_assessment is assessment
    assert result.research_decision is decision
    with pytest.raises(FrozenInstanceError):
        result.research_decision = None


@pytest.mark.parametrize("gated", [{}, [], (), None, object()])
def test_exact_calls_identity_shapes_and_no_input_mutation(gated):
    timings, requirements, retrieved_at, semantics = (object() for _ in range(4))
    evidence = [object(), object()]
    before = list(evidence)
    assessment, decision = object(), object()
    calls = []

    def observe(*args, **kwargs):
        calls.append(("observe", args, kwargs))
        return args[2](*args[3:], **kwargs)

    def assess(*args, **kwargs):
        calls.append(("assess", args, kwargs))
        return assessment

    def decide(*args, **kwargs):
        calls.append(("decide", args, kwargs))
        return decision

    def gate(*args, **kwargs):
        calls.append(("gate", args, kwargs))
        return gated

    result = run_phase_c_assessment_gate_stage(
        timings, requirements, evidence, retrieved_at, semantics,
        _observability_call=observe,
        assess_evidence=assess,
        decide_research_requirement=decide,
        gate_legacy_generic_research=gate,
    )
    assert [row[0] for row in calls] == [
        "observe", "assess", "observe", "decide", "gate"]
    assert calls[0][1] == (
        timings, "evidence_assessment", assess, requirements, evidence)
    assert calls[0][1][0] is timings and calls[0][1][4] is evidence
    assert calls[0][2] == {"target_entity_ids": None, "now": retrieved_at}
    assert calls[2][1] == (
        timings, "evidence_research_gate", decide, assessment)
    assert calls[2][1][0] is timings and calls[2][1][3] is assessment
    assert calls[4][1] == (decision, semantics)
    assert calls[4][1][0] is decision and calls[4][1][1] is semantics
    assert result.initial_assessment is assessment
    assert result.research_decision is gated
    assert evidence == before
    assert all(actual is expected for actual, expected in zip(evidence, before))


@pytest.mark.parametrize("fatal_type", [RuntimeError, Fatal])
@pytest.mark.parametrize("where", ["assessment", "decision", "gate"])
def test_exceptions_propagate_identically_and_stop_following_calls(fatal_type, where):
    error = fatal_type(where)
    calls = []

    def observe(_timings, _label, callable_, *args, **kwargs):
        calls.append(_label)
        return callable_(*args, **kwargs)

    def fail_or_return(name, returned):
        def invoke(*_args, **_kwargs):
            calls.append(name)
            if where == name:
                raise error
            return returned
        return invoke

    with pytest.raises(fatal_type) as raised:
        run_phase_c_assessment_gate_stage(
            object(), object(), [], object(), object(),
            _observability_call=observe,
            assess_evidence=fail_or_return("assessment", object()),
            decide_research_requirement=fail_or_return("decision", object()),
            gate_legacy_generic_research=fail_or_return("gate", object()),
        )
    assert raised.value is error
    expected = ["evidence_assessment", "assessment"]
    if where != "assessment":
        expected += ["evidence_research_gate", "decision"]
    if where == "gate":
        expected += ["gate"]
    assert calls == expected


def test_existing_observability_finally_records_timing_on_failure(monkeypatch):
    from app.orchestrator import service

    timings = service._new_observability_timings()
    ticks = iter((10.0, 10.011))
    monkeypatch.setattr(service, "_observability_now", lambda: next(ticks))
    error = RuntimeError("assessment")

    def fail(*_args, **_kwargs):
        raise error

    with pytest.raises(RuntimeError) as raised:
        run_phase_c_assessment_gate_stage(
            timings, object(), [], object(), object(),
            _observability_call=service._observability_call,
            assess_evidence=fail,
            decide_research_requirement=lambda *_a: None,
            gate_legacy_generic_research=lambda *_a: None,
        )
    assert raised.value is error
    assert timings["evidence_assessment"] == 11
