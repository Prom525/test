"""Characterize the service-owned initial assessment and research-gate boundary."""
from types import SimpleNamespace

import pytest

from app.orchestrator import service
from app.orchestrator.cp13_research_semantics_stage import Cp13ResearchSemanticsStageResult
from app.orchestrator.models import OrchestratorAskRequest
from app.orchestrator.p4_6d2_research_execution_stage import P46d2ResearchExecutionStageResult
from app.orchestrator.p4_6e1_research_evidence_stage import P46e1ResearchEvidenceStageResult
from app.orchestrator.p4_6e2_grounded_synthesis_stage import P46e2GroundedSynthesisStageResult
from app.orchestrator.p4_6e3_synthesis_coverage_stage import P46e3SynthesisCoverageStageResult
from app.orchestrator.phase_c_entry_stage import PhaseCEntryResult
from app.orchestrator.product_family_recovery_stage import ProductFamilyRecoveryResult
from app.orchestrator.task_evidence_stage import TaskEvidenceStageResult
from app.orchestrator.task_research_context_stage import TaskResearchContextStageResult
from app.orchestrator.task_research_decision_stage import TaskResearchDecisionStageResult
from app.orchestrator.v8_research_execution_canary_stage import V8ResearchExecutionCanaryStageResult


class StopAtResearchExecution(BaseException):
    pass


class StopOnLegacyPath(BaseException):
    pass


class Fatal(BaseException):
    pass


_DEFAULT = object()


def _install(monkeypatch, *, assessment_return=_DEFAULT, decision_return=_DEFAULT,
             gated_return=_DEFAULT, error_at=None, consumer_error=None):
    calls = []
    timings = service._new_observability_timings()
    counts = service._new_observability_counts()
    plan = SimpleNamespace(
        intent="synthetic", clarification_required=False,
        clarification_question=None, execution_steps=(), research_required=False,
        requested_information=("synthetic",), multi_intent=False,
    )
    requirement_set = object()
    results = [{"result": {"marker": object()}}, {"result": {"marker": object()}}]
    typed_results = [object()]
    trace = {"attempts": []}
    working_evidence_items = [object(), object()]
    retrieved_at, sender = object(), object()
    task_research_semantics_cp13 = object()
    assessment_return = object() if assessment_return is _DEFAULT else assessment_return
    decision_return = object() if decision_return is _DEFAULT else decision_return
    gated_return = object() if gated_return is _DEFAULT else gated_return
    before = (
        dict(vars(plan)),
        [{"result": row["result"]} for row in results],
        list(typed_results),
        dict(trace),
    )
    evidence_before = tuple(working_evidence_items)

    monkeypatch.setattr(service, "_new_observability_timings", lambda: timings)
    monkeypatch.setattr(service, "_new_observability_counts", lambda: counts)
    ticks = iter((0.0, 10.0, 10.011, 20.0, 20.017, 30.0, 30.023))
    last_tick = [40.0]

    def clock():
        try:
            return next(ticks)
        except StopIteration:
            last_tick[0] += 1.0
            return last_tick[0]

    monkeypatch.setattr(service, "_observability_now", clock)

    def stage(name, value):
        def invoke(*args, **kwargs):
            calls.append((name, args, kwargs))
            return value
        return invoke

    monkeypatch.setattr(service, "run_initial_planning_stage", stage("planning", plan))
    monkeypatch.setattr(service, "_model_to_dict", lambda value: {})
    monkeypatch.setattr(service, "_record_initial_execution_observability", lambda *a: None)
    initial = SimpleNamespace(
        plan=plan, task_execution_plans_shadow=(), task_execution_plan_comparison_shadow=None,
        task_execution_canary_p4_6b=None, typed_execution_results=typed_results,
        results=results, trace=trace, task_execution_shadow=object(), task_planner_canary=None,
    )
    monkeypatch.setattr(service, "run_initial_execution_stage", stage("execution", initial))
    monkeypatch.setattr(service, "prepare_phase_c_entry", stage(
        "phase_c_entry", PhaseCEntryResult(requirement_set, retrieved_at, (), working_evidence_items)))
    monkeypatch.setattr(service, "run_product_family_recovery_stage", stage(
        "family_recovery", ProductFamilyRecoveryResult(object(), object(), working_evidence_items)))
    monkeypatch.setattr(service, "run_task_evidence_stage", stage(
        "task_evidence", TaskEvidenceStageResult(object(), object())))
    monkeypatch.setattr(service, "run_task_research_decision_stage", stage(
        "task_decision", TaskResearchDecisionStageResult(object(), object())))
    monkeypatch.setattr(service, "run_task_research_context_stage", stage(
        "task_context", TaskResearchContextStageResult(object(), object())))
    monkeypatch.setattr(service, "run_cp13_research_semantics_stage", stage(
        "cp13_stage", Cp13ResearchSemanticsStageResult(task_research_semantics_cp13)))
    monkeypatch.setattr(service, "run_p4_6d2_research_execution_stage", stage(
        "p4_6d2", P46d2ResearchExecutionStageResult(object(), [])))
    monkeypatch.setattr(service, "run_p4_6e1_research_evidence_stage", stage(
        "p4_6e1", P46e1ResearchEvidenceStageResult(object(), [])))
    monkeypatch.setattr(service, "run_p4_6e2_grounded_synthesis_stage", stage(
        "p4_6e2", P46e2GroundedSynthesisStageResult(object())))
    monkeypatch.setattr(service, "run_p4_6e3_synthesis_coverage_stage", stage(
        "p4_6e3", P46e3SynthesisCoverageStageResult(object())))
    monkeypatch.setattr(service, "run_v8_research_execution_canary_stage", stage(
        "v8", V8ResearchExecutionCanaryStageResult(object(), [], [])))

    def assess(*args, **kwargs):
        calls.append(("assessment", args, kwargs))
        if error_at == "assessment":
            raise consumer_error
        return assessment_return

    def decide(*args, **kwargs):
        calls.append(("decision", args, kwargs))
        if error_at == "decision":
            raise consumer_error
        return decision_return

    def legacy_gate(*args, **kwargs):
        calls.append(("legacy_gate", args, kwargs))
        if error_at == "legacy_gate":
            raise consumer_error
        return gated_return

    def consumer(*args, **kwargs):
        calls.append(("consumer", args, kwargs))
        raise consumer_error or StopAtResearchExecution("controlled consumer boundary")

    monkeypatch.setattr(service, "assess_evidence", assess)
    monkeypatch.setattr(service, "decide_research_requirement", decide)
    monkeypatch.setattr(service, "gate_legacy_generic_research", legacy_gate)
    monkeypatch.setattr(service, "execute_bounded_research", consumer)
    monkeypatch.setattr(service, "has_service_accepted_execution", lambda *a: True)

    def legacy_answer(*args, **kwargs):
        calls.append(("legacy_path", args, kwargs))
        raise StopOnLegacyPath("outer Phase-C fail-open observed")

    monkeypatch.setattr(service, "_build_user_answer", legacy_answer)
    return SimpleNamespace(**locals())


def _run(harness, exception=StopAtResearchExecution):
    with pytest.raises(exception) as raised:
        service._p4_15cp3c_previous_run_orchestrator(
            OrchestratorAskRequest(q="synthetic", vraag=""), sender=harness.sender)
    return raised.value


@pytest.mark.parametrize("gated", [{"x": 1}, [1], (1,), None, object()])
def test_exact_order_inputs_identity_fresh_results_and_unconverted_gated_shapes(monkeypatch, gated):
    assessment, decision = object(), object()
    h = _install(monkeypatch, assessment_return=assessment, decision_return=decision,
                 gated_return=gated)
    _run(h)
    names = [row[0] for row in h.calls]
    assert names == ["planning", "execution", "phase_c_entry", "family_recovery",
                     "task_evidence", "task_decision", "task_context", "cp13_stage",
                     "p4_6d2", "p4_6e1", "p4_6e2", "p4_6e3", "v8",
                     "assessment", "decision", "legacy_gate", "consumer"]
    assessment_call, decision_call, gate_call, consumer_call = h.calls[-4:]
    assert assessment_call[1] == (h.requirement_set, h.working_evidence_items)
    assert assessment_call[1][1] is h.working_evidence_items
    assert assessment_call[2] == {"target_entity_ids": None, "now": h.retrieved_at}
    assert decision_call[1] == (assessment,) and decision_call[1][0] is assessment
    assert decision_call[2] == {}
    assert gate_call[1] == (decision, h.task_research_semantics_cp13)
    assert gate_call[1][0] is decision and gate_call[1][1] is h.task_research_semantics_cp13
    assert gate_call[2] == {}
    assert consumer_call[1][0] is gated and consumer_call[1][1] is h.plan
    copied_results = consumer_call[1][2]
    assert isinstance(copied_results, list) and copied_results is not h.results
    assert all(actual is expected for actual, expected in zip(copied_results, h.results))
    assert consumer_call[2] == {"sender": h.sender}
    assert (vars(h.plan), h.results, h.typed_results, h.trace) == h.before
    assert tuple(h.working_evidence_items) == h.evidence_before
    assert h.timings["evidence_assessment"] == 11
    assert h.timings["evidence_research_gate"] == 17
    assert h.timings["evidence_research"] == 23


def test_observability_uses_same_timings_runtime_callables_and_exact_labels(monkeypatch):
    h = _install(monkeypatch)
    observed = []
    original = service._observability_call

    def recording(timings, label, callable_, *args, **kwargs):
        if label in {"evidence_assessment", "evidence_research_gate", "evidence_research"}:
            observed.append((timings, label, callable_))
        return original(timings, label, callable_, *args, **kwargs)

    monkeypatch.setattr(service, "_observability_call", recording)
    _run(h)
    assert [row[1] for row in observed] == [
        "evidence_assessment", "evidence_research_gate", "evidence_research"]
    assert all(row[0] is h.timings for row in observed)
    assert observed[0][2] is service.assess_evidence
    assert observed[1][2] is service.decide_research_requirement
    assert observed[2][2] is service.execute_bounded_research


@pytest.mark.parametrize("where", ["assessment", "decision", "legacy_gate"])
def test_ordinary_exception_enters_existing_outer_fail_open_and_stops_zone(monkeypatch, where):
    error = RuntimeError(where)
    h = _install(monkeypatch, error_at=where, consumer_error=error)
    _run(h, StopOnLegacyPath)
    names = [row[0] for row in h.calls]
    expected = ["assessment"]
    if where != "assessment":
        expected.append("decision")
    if where == "legacy_gate":
        expected.append("legacy_gate")
    assert names[-len(expected + ["legacy_path"]):] == expected + ["legacy_path"]
    assert "consumer" not in names
    if where in {"assessment", "decision"}:
        key = "evidence_assessment" if where == "assessment" else "evidence_research_gate"
        assert h.timings[key] == (11 if where == "assessment" else 17)


@pytest.mark.parametrize("where", ["assessment", "decision", "legacy_gate"])
def test_baseexception_propagates_unchanged_and_prevents_following_calls(monkeypatch, where):
    fatal = Fatal(where)
    h = _install(monkeypatch, error_at=where, consumer_error=fatal)
    assert _run(h, Fatal) is fatal
    names = [row[0] for row in h.calls]
    assert "consumer" not in names and "legacy_path" not in names
    if where == "assessment":
        assert "decision" not in names and "legacy_gate" not in names
        assert h.timings["evidence_assessment"] == 11
    elif where == "decision":
        assert "legacy_gate" not in names
        assert h.timings["evidence_research_gate"] == 17
    else:
        assert h.timings["evidence_research"] == 0


@pytest.mark.parametrize("error_type,outer_fail_open", [(RuntimeError, True), (Fatal, False)])
def test_bounded_research_is_only_the_following_stop_boundary(monkeypatch, error_type, outer_fail_open):
    error = error_type("consumer")
    h = _install(monkeypatch, consumer_error=error)
    raised = _run(h, StopOnLegacyPath if outer_fail_open else Fatal)
    if not outer_fail_open:
        assert raised is error
    names = [row[0] for row in h.calls]
    assert names.count("assessment") == names.count("decision") == 1
    assert names.count("legacy_gate") == names.count("consumer") == 1
    assert ("legacy_path" in names) is outer_fail_open
    assert h.timings["evidence_research"] == 23
