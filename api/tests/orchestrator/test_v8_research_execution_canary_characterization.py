"""Characterize the existing direct V8 candidate canary semantics."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.orchestrator import service


class Fatal(BaseException): pass


def _task(task_id="t", **overrides):
    values = dict(task_id=task_id, domain="technical", intent="technical_lookup",
        primary=False, requested_information=["definition"], product_families=[])
    values.update(overrides)
    return SimpleNamespace(**values)


def _inputs(*tasks):
    plan = SimpleNamespace(multi_intent=True, intent_tasks=list(tasks), original_question="q",
        normalized_question="q", execution_steps=[], requested_information=[], entities={})
    contexts = [dict(task_id=t.task_id, research_required=True, runtime_precondition="ready",
        family_code=None, gate_intent="gate") for t in tasks]
    guards = [dict(task_id=t.task_id, runtime_precondition="ready", status="projected",
        allowed_research_action="technical_assistant", target_requirement_ids=["TECHNICAL_SOURCE"],
        max_follow_up_calls=1, pinned_params={"source_code": "v"}) for t in tasks]
    results = [dict(task_id=t.task_id, domain="technical", accepted=True) for t in tasks]
    return plan, results, contexts, guards


def _enable(monkeypatch): monkeypatch.setenv("AI_TASK_RESEARCH_EXECUTION_CANARY_ENABLED", "true")


def test_disabled_and_exact_gate_contracts(monkeypatch):
    args = _inputs(_task())
    monkeypatch.delenv("AI_TASK_RESEARCH_EXECUTION_CANARY_ENABLED", raising=False)
    assert service._run_intent_task_research_execution_canary_shadow(*args, sender=None) == []
    _enable(monkeypatch)
    args[0].multi_intent = False
    assert service._run_intent_task_research_execution_canary_shadow(*args, sender=None) == [{
        "contract_version": "promati.multi_intent.task_research_execution_canary_shadow.v1",
        "status": "blocked_not_multi_intent", "executed": False}]


@pytest.mark.parametrize("mutation", [
    lambda t,c,g: setattr(t, "domain", "product"),
    lambda t,c,g: setattr(t, "intent", "other"),
    lambda t,c,g: setattr(t, "primary", True),
    lambda t,c,g: c.update(research_required=1),
    lambda t,c,g: c.update(runtime_precondition="blocked"),
    lambda t,c,g: g.update(status="blocked"),
    lambda t,c,g: g.update(allowed_research_action="other"),
    lambda t,c,g: g.update(max_follow_up_calls=2),
    lambda t,c,g: g.update(target_requirement_ids=[]),
    lambda t,c,g: c.update(family_code="F1"),
])
def test_eligibility_gates_have_exact_no_candidate_reason(monkeypatch, mutation):
    _enable(monkeypatch); task = _task(); args = _inputs(task); mutation(task, args[2][0], args[3][0])
    result = service._run_intent_task_research_execution_canary_shadow(*args, sender=None)
    assert result == [{"contract_version": "promati.multi_intent.task_research_execution_canary_shadow.v1",
                       "status": "no_eligible_secondary_technical_task", "executed": False}]


def test_ambiguous_tasks_preserve_plan_order_and_no_accepted_result_reason(monkeypatch):
    _enable(monkeypatch); args = _inputs(_task("b"), _task("a"))
    result = service._run_intent_task_research_execution_canary_shadow(*args, sender=None)
    assert result[0]["status"] == "blocked_ambiguous_eligible_tasks"
    assert result[0]["eligible_task_ids"] == ["b", "a"]
    args = _inputs(_task("only")); args[1][0]["accepted"] = 1
    result = service._run_intent_task_research_execution_canary_shadow(*args, sender=None)
    assert result[0]["status"] == "blocked_no_accepted_initial_results"


def test_runtime_binding_projection_observers_identity_order_and_privacy(monkeypatch):
    _enable(monkeypatch); task = _task(); plan, results, contexts, guards = _inputs(task)
    sender, now, evidence = object(), object(), (object(), object())
    typed1, typed2, reassessment, grounded = object(), object(), object(), object()
    calls = []
    monkeypatch.setattr(service, "_project_secondary_technical_question_shadow", lambda p,t: "isolated")
    monkeypatch.setattr(service, "_task_research_definition_retrieval_question_shadow", lambda q: "retrieval")
    monkeypatch.setattr(service, "_task_research_canary_copy_plan_shadow", lambda p,t,task_question: SimpleNamespace(marker="projected"))
    monkeypatch.setattr(service, "_task_research_canary_planner_shadow", lambda **kw: calls.append(("planner", kw)) or object())
    monkeypatch.setattr(service, "run_bounded_research_agent", lambda projected, accepted, **kw:
        calls.append(("runtime", projected, accepted, kw)) or
        (kw["shadow_observer"](typed1), kw["shadow_observer"](typed2),
         {"agent": {"follow_up_specialist_calls": 1}, "combined_result_count": 2,
          "follow_up_result_count": 1, "result_summaries": []})[-1])
    monkeypatch.setattr(service, "_build_intent_task_research_evidence_reassessment_shadow",
        lambda *a, **k: calls.append(("reassess", a, k)) or reassessment)
    monkeypatch.setattr(service, "_build_intent_task_grounded_synthesis_shadow",
        lambda *a, **k: calls.append(("grounded", a, k)) or grounded)
    observed = []
    before = deepcopy((plan.__dict__, results, contexts, guards))
    result = service._run_intent_task_research_execution_canary_shadow(plan, results, contexts, guards,
        sender=sender, initial_evidence_items=evidence, reassessment_now=now,
        evidence_reassessment_observer=lambda x: observed.append(("r", x)),
        grounded_synthesis_observer=lambda x: observed.append(("g", x)))
    runtime = next(c for c in calls if c[0] == "runtime")
    assert runtime[3]["sender"] is sender and runtime[3]["call_guard"].pinned_params == {"source_code": "v"}
    assert runtime[2] == [results[0]] and runtime[2][0] is results[0]
    assert observed == [("r", reassessment), ("g", grounded)]
    reassess, grounded_call = [c for c in calls if c[0] in {"reassess", "grounded"}]
    assert reassess[1][1] == evidence and reassess[1][2] == [typed1, typed2] and reassess[2]["now"] is now
    assert grounded_call[1][2] == evidence and grounded_call[1][3] == [typed1, typed2]
    assert result[0]["status"] == "executed_shadow_canary" and result[0]["authoritative"] is False
    assert result[0]["pinned_params"] == {"source_code": "v"}
    assert (plan.__dict__, results, contexts, guards) == before
    assert not any(key in repr(result).lower() for key in ("token", "payload", "answer"))


@pytest.mark.parametrize("fatal", [False, True])
def test_execution_exception_contract_and_baseexception(monkeypatch, fatal):
    _enable(monkeypatch); args = _inputs(_task()); error = Fatal("fatal") if fatal else RuntimeError("ordinary")
    monkeypatch.setattr(service, "_project_secondary_technical_question_shadow", lambda *a: "q")
    monkeypatch.setattr(service, "_task_research_definition_retrieval_question_shadow", lambda q: "rq")
    monkeypatch.setattr(service, "_task_research_canary_copy_plan_shadow", lambda *a, **k: object())
    monkeypatch.setattr(service, "run_bounded_research_agent", lambda *a, **k: (_ for _ in ()).throw(error))
    if fatal:
        with pytest.raises(Fatal) as raised: service._run_intent_task_research_execution_canary_shadow(*args, sender=None)
        assert raised.value is error
    else:
        result = service._run_intent_task_research_execution_canary_shadow(*args, sender=None)
        assert result[0]["status"] == "execution_error" and result[0]["error_type"] == "RuntimeError"


@pytest.mark.parametrize("observer", ["reassessment", "grounded"])
@pytest.mark.parametrize("fatal", [False, True])
def test_observer_exception_fail_open_but_baseexception_propagates(monkeypatch, observer, fatal):
    _enable(monkeypatch); args = _inputs(_task()); error = Fatal(observer) if fatal else RuntimeError(observer)
    monkeypatch.setattr(service, "_project_secondary_technical_question_shadow", lambda *a: "q")
    monkeypatch.setattr(service, "_task_research_definition_retrieval_question_shadow", lambda q: "rq")
    monkeypatch.setattr(service, "_task_research_canary_copy_plan_shadow", lambda *a, **k: object())
    monkeypatch.setattr(service, "run_bounded_research_agent", lambda *a, **k: {"agent": {}, "result_summaries": []})
    kwargs = dict(sender=None, evidence_reassessment_observer=lambda x: None, grounded_synthesis_observer=lambda x: None)
    target = "_build_intent_task_research_evidence_reassessment_shadow" if observer == "reassessment" else "_build_intent_task_grounded_synthesis_shadow"
    monkeypatch.setattr(service, target, lambda *a, **k: (_ for _ in ()).throw(error))
    if fatal:
        with pytest.raises(Fatal) as raised: service._run_intent_task_research_execution_canary_shadow(*args, **kwargs)
        assert raised.value is error
    else:
        assert service._run_intent_task_research_execution_canary_shadow(*args, **kwargs)[0]["executed"] is True
