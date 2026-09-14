"""Characterize the CP13 service boundary immediately after the 3J2 stage."""
from __future__ import annotations

from copy import deepcopy
import inspect
from types import SimpleNamespace

import pytest

from app.orchestrator import service
from app.orchestrator.models import OrchestratorAskRequest
from app.orchestrator.phase_c_entry_stage import PhaseCEntryResult
from app.orchestrator.product_family_recovery_stage import ProductFamilyRecoveryResult
from app.orchestrator.task_evidence_stage import TaskEvidenceStageResult
from app.orchestrator.task_research_context_stage import TaskResearchContextStageResult
from app.orchestrator.task_research_decision_stage import TaskResearchDecisionStageResult


class P46d2Observed(BaseException):
    pass


class OrdinaryCp13Error(Exception):
    pass


class FatalCp13Error(BaseException):
    pass


FALLBACK = {
    "contract_version": "promati.orchestrator.task_research_semantics.cp13.v1",
    "evaluated": False,
    "authoritative": False,
    "authority_scope": "intent_task_research_eligibility_only",
    "public_answer_authority": False,
    "legacy_generic_research_allowed": False,
    "allowed_task_ids": [],
    "tasks": [],
    "reason": "internal_error_fail_closed",
}


def _install(monkeypatch, *, cp13_return=None, cp13_error=None):
    calls = []
    p4_frames = []
    plan = SimpleNamespace(
        intent="synthetic", clarification_required=False,
        clarification_question=None, execution_steps=(), research_required=False,
        requested_information=("synthetic",), multi_intent=False,
    )
    result_values = [SimpleNamespace(value=[1]), SimpleNamespace(value=[2])]
    results = list(result_values)
    typed_results = [SimpleNamespace(status="synthetic", detail=[3])]
    trace = {"attempts": [{"stage": "synthetic"}]}
    stamp = object()
    initial_evidence = (SimpleNamespace(value=[4]),)
    working_evidence = [initial_evidence[0], SimpleNamespace(value=[5])]
    task_execution_shadow = SimpleNamespace(tasks=[6])
    evidence_shadow = SimpleNamespace(value=[7])
    evidence_authority = SimpleNamespace(value=[8])
    decisions = SimpleNamespace(value=[9])
    research_authority = SimpleNamespace(value=[10])
    contexts = SimpleNamespace(value=[11])
    guards = SimpleNamespace(value=[12])
    sender = SimpleNamespace(value=[13])
    before = deepcopy({
        "plan": plan, "results": results, "typed_results": typed_results,
        "trace": trace, "working_evidence": working_evidence,
        "task_execution_shadow": task_execution_shadow,
        "evidence_shadow": evidence_shadow,
        "evidence_authority": evidence_authority, "decisions": decisions,
        "research_authority": research_authority, "contexts": contexts,
        "guards": guards, "sender": sender,
    })

    monkeypatch.setattr(service, "_new_observability_counts", lambda: {})
    monkeypatch.setattr(service, "run_initial_planning_stage", lambda *a, **k: plan)
    monkeypatch.setattr(service, "_record_initial_execution_observability", lambda *a: None)

    def execution(*args, **kwargs):
        calls.append(("execution", args, kwargs))
        return SimpleNamespace(
            plan=plan, task_execution_plans_shadow=(),
            task_execution_plan_comparison_shadow=None,
            task_execution_canary_p4_6b=None, typed_execution_results=typed_results,
            results=results, trace=trace, task_execution_shadow=task_execution_shadow,
            task_planner_canary=None,
        )

    monkeypatch.setattr(service, "run_initial_execution_stage", execution)

    def phase_c(*args, **kwargs):
        calls.append(("phase_c", args, kwargs))
        return PhaseCEntryResult(object(), stamp, initial_evidence, initial_evidence)

    monkeypatch.setattr(service, "prepare_phase_c_entry", phase_c)

    def recovery(*args, **kwargs):
        calls.append(("recovery", args, kwargs))
        return ProductFamilyRecoveryResult(object(), object(), working_evidence)

    monkeypatch.setattr(service, "run_product_family_recovery_stage", recovery)

    def evidence(*args, **kwargs):
        calls.append(("evidence", args, kwargs))
        return TaskEvidenceStageResult(evidence_shadow, evidence_authority)

    monkeypatch.setattr(service, "run_task_evidence_stage", evidence)

    def decision(*args, **kwargs):
        calls.append(("3i2", args, kwargs))
        return TaskResearchDecisionStageResult(decisions, research_authority)

    monkeypatch.setattr(service, "run_task_research_decision_stage", decision)

    def context_stage(*args, **kwargs):
        calls.append(("3j2", args, kwargs))
        return TaskResearchContextStageResult(contexts, guards)

    monkeypatch.setattr(service, "run_task_research_context_stage", context_stage)

    def cp13(*args, **kwargs):
        calls.append(("cp13", args, kwargs))
        if cp13_error is not None:
            raise cp13_error
        return cp13_return

    monkeypatch.setattr(service, "build_task_research_semantics", cp13)

    def p4(*args, **kwargs):
        caller = inspect.currentframe().f_back.f_locals
        observations = caller["task_research_execution_observations_p4_6d2"]
        p4_frames.append({
            "semantics": caller["task_research_semantics_cp13"],
            "authority": caller["task_research_execution_authority_p4_6d2"],
            "observations": observations,
            "observations_before": list(observations),
        })
        calls.append(("p4.6d2", args, kwargs))
        raise P46d2Observed("controlled stop before P4.6D2 execution")

    monkeypatch.setattr(
        service, "run_task_research_execution_authority_canary_p4_6d2", p4
    )
    monkeypatch.setattr(service, "has_service_accepted_execution", lambda *a: True)
    monkeypatch.setattr(
        service, "_build_user_answer",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("downstream reached")),
    )
    return SimpleNamespace(**locals())


def _run(harness):
    with pytest.raises(P46d2Observed, match="controlled stop"):
        service._p4_15cp3c_previous_run_orchestrator(
            OrchestratorAskRequest(q="synthetic", vraag=""), sender=harness.sender
        )


@pytest.mark.parametrize(
    "value", [[], (), {"shape": "mapping"}, None, object()],
)
def test_success_is_bound_unchanged_and_forwarded_at_exact_boundary(monkeypatch, value):
    harness = _install(monkeypatch, cp13_return=value)
    _run(harness)

    names = [call[0] for call in harness.calls]
    assert names == ["execution", "phase_c", "recovery", "evidence", "3i2", "3j2", "cp13", "p4.6d2"]
    assert all(names.count(name) == 1 for name in names)
    cp13 = harness.calls[-2]
    assert cp13[1] == (
        harness.plan, harness.task_execution_shadow, harness.research_authority
    )
    assert cp13[2] == {}
    assert harness.contexts not in cp13[1] and harness.guards not in cp13[1]

    p4 = harness.calls[-1]
    assert p4[1][0] is harness.plan
    assert p4[1][1] is not harness.results
    assert len(p4[1][1]) == len(harness.result_values)
    assert all(a is b for a, b in zip(p4[1][1], harness.result_values))
    assert p4[1][2:] == (
        harness.research_authority, harness.contexts, harness.guards
    )
    frame = harness.p4_frames[0]
    assert p4[2]["sender"] is harness.sender
    assert callable(p4[2]["evidence_observer"])
    assert p4[2]["evidence_observer"].__self__ is frame["observations"]
    assert p4[2]["evidence_observer"].__name__ == "append"
    assert p4[2]["task_research_semantics_cp13"] is value
    assert frame["semantics"] is value
    assert frame["authority"] is None
    assert frame["observations_before"] == []
    assert type(frame["observations"]) is list


@pytest.mark.parametrize("error", [OrdinaryCp13Error("ordinary")])
def test_exception_uses_exact_fallback_and_reaches_p46d2_once(monkeypatch, error):
    harness = _install(monkeypatch, cp13_error=error)
    _run(harness)

    fallback = harness.p4_frames[0]["semantics"]
    assert fallback == FALLBACK
    assert set(fallback) == set(FALLBACK)
    assert harness.calls[-1][2]["task_research_semantics_cp13"] is fallback
    assert [call[0] for call in harness.calls].count("cp13") == 1
    assert [call[0] for call in harness.calls].count("p4.6d2") == 1


def test_exception_fallback_dict_and_lists_are_fresh_across_core_calls(monkeypatch):
    harness = _install(monkeypatch, cp13_error=OrdinaryCp13Error("ordinary"))
    _run(harness)
    _run(harness)

    first, second = [frame["semantics"] for frame in harness.p4_frames]
    assert first == second == FALLBACK and first is not second
    assert first["allowed_task_ids"] is not second["allowed_task_ids"]
    assert first["tasks"] is not second["tasks"]
    first["allowed_task_ids"].append("mutation")
    first["tasks"].append({"mutation": True})
    assert second == FALLBACK
    assert harness.p4_frames[0]["observations"] is not harness.p4_frames[1]["observations"]


def test_cp13_baseexception_propagates_before_p46d2(monkeypatch):
    fatal = FatalCp13Error("fatal")
    harness = _install(monkeypatch, cp13_error=fatal)
    with pytest.raises(FatalCp13Error, match="fatal"):
        service._p4_15cp3c_previous_run_orchestrator(
            OrchestratorAskRequest(q="synthetic", vraag=""), sender=harness.sender
        )
    assert [call[0] for call in harness.calls].count("cp13") == 1
    assert "p4.6d2" not in [call[0] for call in harness.calls]


def test_cp13_and_p46d2_boundary_do_not_mutate_inputs_or_trigger_downstream(monkeypatch):
    value = SimpleNamespace(value=[14])
    harness = _install(monkeypatch, cp13_return=value)
    _run(harness)

    assert {
        "plan": harness.plan, "results": harness.results,
        "typed_results": harness.typed_results, "trace": harness.trace,
        "working_evidence": harness.working_evidence,
        "task_execution_shadow": harness.task_execution_shadow,
        "evidence_shadow": harness.evidence_shadow,
        "evidence_authority": harness.evidence_authority,
        "decisions": harness.decisions,
        "research_authority": harness.research_authority,
        "contexts": harness.contexts, "guards": harness.guards,
        "sender": harness.sender,
    } == harness.before
    assert [call[0] for call in harness.calls][-2:] == ["cp13", "p4.6d2"]
