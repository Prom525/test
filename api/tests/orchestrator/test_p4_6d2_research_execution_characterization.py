"""Networkless direct characterization of the bounded P4.6D2 executor."""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.orchestrator.models import Domain, ExecutionStep, IntentTask, QueryPlan
from app.orchestrator import task_research_execution as subject


def _task(task_id="task-1", domain=Domain.TECHNICAL):
    return IntentTask(task_id=task_id, domain=domain, intent="lookup", required=True,
                      polarity="requested", evidence_requirement_set_id="technical.v1")


def _plan(*tasks, steps=None):
    return QueryPlan(
        original_question="Onderzoek dit.", normalized_question="onderzoek dit.",
        primary_domain=Domain.TECHNICAL, domains=[Domain.TECHNICAL], intent="lookup",
        intent_tasks=list(tasks), execution_steps=list(steps if steps is not None else [
            ExecutionStep(step_id="s1", domain=Domain.TECHNICAL,
                          action="technical_lookup", params={"seed": "kept"})]))


def _authority(**updates):
    value = {"authoritative": True, "authority_scope": "intent_task_research_decision_only",
             "shadow_parity": True}
    value.update(updates)
    return value


def _context(task_id="task-1", **updates):
    value = {"task_id": task_id, "research_required": True, "runtime_precondition": "ready"}
    value.update(updates)
    return value


def _guard(task_id="task-1", **updates):
    value = {"task_id": task_id, "status": "projected", "runtime_precondition": "ready",
             "max_follow_up_calls": 1, "allowed_research_action": "technical_assistant",
             "pinned_params": {"topic_group": "yes"}, "target_requirement_ids": ["req-1"]}
    value.update(updates)
    return value


def _semantics(*task_ids, rows=None, **updates):
    value = {"contract_version": "promati.orchestrator.task_research_semantics.cp13.v1",
             "evaluated": True, "authority_scope": "intent_task_research_eligibility_only",
             "legacy_generic_research_allowed": False, "allowed_task_ids": list(task_ids),
             "tasks": rows if rows is not None else [
                 {"task_id": task_id, "research_allowed": True} for task_id in task_ids]}
    value.update(updates)
    return value


_DEFAULT = object()


def _run(plan, contexts, guards, *, results=None, authority=_DEFAULT, semantics=None,
         sender=None, observer=None):
    return subject.run_task_research_execution_authority_canary_p4_6d2(
        plan, [] if results is None else results, _authority() if authority is _DEFAULT else authority,
        contexts, guards, sender=sender, evidence_observer=observer,
        task_research_semantics_cp13=semantics)


@pytest.mark.parametrize("authority,semantics,reason", [
    (None, _semantics("task-1"), "missing_task_research_decision_authority"),
    ({}, _semantics("task-1"), "task_research_decision_authority_not_active"),
    (_authority(shadow_parity=False), _semantics("task-1"), "decision_shadow_parity_not_proven"),
    (_authority(), None, "missing_task_research_semantics_cp13"),
    (_authority(), {"invalid": True}, "invalid_task_research_semantics_cp13"),
    (_authority(), _semantics(), "no_eligible_research_execution_units"),
])
def test_fail_closed_gates_make_no_execution_calls(monkeypatch, authority, semantics, reason):
    calls = []
    monkeypatch.setattr(subject, "_execute_follow_up_call", lambda *a, **k: calls.append((a, k)))
    result = _run(_plan(_task()), [_context()], [_guard()], authority=authority, semantics=semantics)
    assert result["reason"] == reason and result["authoritative"] is False
    assert calls == []


def test_disabled_makes_no_calls_or_observations(monkeypatch):
    calls, observations = [], []
    monkeypatch.setenv("AI_TASK_RESEARCH_EXECUTION_AUTHORITY_CANARY_ENABLED", "false")
    monkeypatch.setattr(subject, "_execute_follow_up_call", lambda *a, **k: calls.append((a, k)))
    result = _run(_plan(_task()), [_context()], [_guard()],
                  semantics=_semantics("task-1"), observer=observations.append)
    assert result["reason"] == "disabled" and calls == observations == []


def test_cp13_allowlist_must_exactly_match_allowed_rows(monkeypatch):
    calls = []
    monkeypatch.setattr(subject, "_execute_follow_up_call", lambda *a, **k: calls.append((a, k)))
    semantics = _semantics("task-1", rows=[{"task_id": "task-2", "research_allowed": True}])
    result = _run(_plan(_task()), [_context()], [_guard()], semantics=semantics)
    assert result["reason"] == "invalid_task_research_semantics_cp13" and calls == []


@pytest.mark.parametrize("context,guard", [
    (_context("missing"), _guard("missing")),
    (_context(research_required=False), _guard()),
    (_context(runtime_precondition="blocked"), _guard()),
    (_context(), _guard(runtime_precondition="blocked")),
    (_context(), _guard(status="blocked")),
    (_context(), _guard(max_follow_up_calls=2)),
])
def test_only_fully_valid_units_are_eligible(monkeypatch, context, guard):
    calls = []
    monkeypatch.setattr(subject, "_execute_follow_up_call", lambda *a, **k: calls.append((a, k)))
    result = _run(_plan(_task()), [context], [guard], semantics=_semantics("task-1", "missing"))
    assert result["reason"] == "no_eligible_research_execution_units" and calls == []


def test_at_most_two_units_execute_in_context_order_with_exact_call_contract(monkeypatch):
    tasks = [_task(f"task-{n}") for n in range(1, 4)]
    contexts = [_context(task.task_id) for task in tasks]
    guards = [_guard(task.task_id) for task in tasks]
    calls, sender = [], object()
    def execute(*args, **kwargs):
        calls.append((args, kwargs)); return []
    monkeypatch.setattr(subject, "_execute_follow_up_call", execute)
    result = _run(_plan(*tasks), contexts, guards, semantics=_semantics(*(t.task_id for t in tasks)), sender=sender)
    assert [row["task_id"] for row in result["executions"]] == ["task-1", "task-2"]
    assert result["raw_execution_unit_count"] == result["eligible_execution_unit_count"] == 3
    assert result["execution_unit_count"] == 2 and len(calls) == 2
    for args, kwargs in calls:
        projected, tool_call = args
        assert projected is not result and projected.intent_tasks == []
        assert tool_call.action == "technical_assistant"
        assert kwargs["round_number"] == kwargs["call_number"] == 1
        assert kwargs["sender"] is sender
        assert kwargs["call_guard"].max_follow_up_calls == 1


def test_family_scopes_match_case_insensitively_and_select_only_family_data(monkeypatch):
    task = _task()
    steps = [ExecutionStep(step_id="a", domain=Domain.TECHNICAL, action="technical_lookup", params={"family_code": "Alpha"}),
             ExecutionStep(step_id="b", domain=Domain.TECHNICAL, action="technical_lookup", params={"family_code": "Beta"})]
    context = _context(product_family_scope_contexts=[{**_context(), "family_code": "ALPHA"}])
    guard = _guard(product_family_scope_guards=[{**_guard(), "family_code": "alpha"}])
    alpha, beta = ({"domain": "technical", "accepted": True, "result": {"detected_family_code": "aLpHa"}},
                   {"domain": "technical", "accepted": True, "result": {"detected_family_code": "Beta"}})
    calls = []
    def execute(*args, **kwargs): calls.append((args, kwargs)); return []
    monkeypatch.setattr(subject, "_execute_follow_up_call", execute)
    result = _run(_plan(task, steps=steps), [context], [guard], results=[alpha, beta], semantics=_semantics("task-1"))
    projected = calls[0][0][0]
    assert [step.step_id for step in projected.execution_steps] == ["a"]
    assert result["executions"][0]["accepted_initial_result_count"] == 1


def test_missing_step_blocks_without_sender_call_but_authority_activates(monkeypatch):
    calls = []
    monkeypatch.setattr(subject, "_execute_follow_up_call", lambda *a, **k: calls.append((a, k)))
    result = _run(_plan(_task(), steps=[]), [_context()], [_guard()], semantics=_semantics("task-1"))
    assert calls == [] and result["executions"][0]["status"] == "blocked_no_task_execution_step"
    assert result["authoritative"] is True and result["reason"] == "activated_task_research_execution_authority"


def test_exception_is_local_error_type_only_and_next_unit_continues(monkeypatch):
    calls = []
    def execute(*args, **kwargs):
        calls.append((args, kwargs))
        if len(calls) == 1: raise ValueError("secret detail")
        return [{"accepted": True}]
    monkeypatch.setattr(subject, "_execute_follow_up_call", execute)
    tasks = [_task("task-1"), _task("task-2")]
    result = _run(_plan(*tasks), [_context("task-1"), _context("task-2")],
                  [_guard("task-1"), _guard("task-2")], semantics=_semantics("task-1", "task-2"))
    assert len(calls) == 2
    assert result["executions"][0] == {"task_id": "task-1", "domain": "technical", "family_code": None,
        "executed": False, "accepted_initial_result_count": 0,
        "accepted_follow_up_result_count": 0, "status": "execution_error", "error_type": "ValueError"}
    assert result["executions"][1]["status"] == "executed_authoritative_task_research"


@pytest.mark.parametrize("follow_results,expected", [(None, (0, False, "completed_without_follow_up")),
                                                        ([], (1, True, "executed_authoritative_task_research"))])
def test_none_and_empty_list_have_distinct_call_semantics(monkeypatch, follow_results, expected):
    monkeypatch.setattr(subject, "_execute_follow_up_call", lambda *a, **k: follow_results)
    result = _run(_plan(_task()), [_context()], [_guard()], semantics=_semantics("task-1"))
    row = result["executions"][0]
    assert (row["follow_up_specialist_call_count"], row["executed"], row["status"]) == expected


def test_raw_results_stay_private_acceptance_is_exact_and_typed_observer_isolated(monkeypatch):
    typed = [object(), object()]
    raw = [{"accepted": True}, {"accepted": 1}, {"accepted": False}, object()]
    payloads = []
    def execute(*args, shadow_observer=None, **kwargs):
        for item in typed: shadow_observer(item)
        return raw
    monkeypatch.setattr(subject, "_execute_follow_up_call", execute)
    legacy_value = object()
    plan, results, authority = _plan(_task()), [{"legacy": legacy_value}], _authority()
    contexts, guards, semantics = [_context()], [_guard()], _semantics("task-1")
    before = deepcopy((plan, authority, contexts, guards, semantics))
    result = _run(plan, contexts, guards, results=results, authority=authority,
                  semantics=semantics, observer=payloads.append)
    assert result["accepted_follow_up_result_count"] == 1
    assert raw not in result.values()
    assert len(results) == 1 and results[0]["legacy"] is legacy_value
    assert payloads[0]["task_id"] == "task-1" and payloads[0]["family_code"] is None
    assert all(a is b for a, b in zip(payloads[0]["execution_results"], typed))
    assert (plan, authority, contexts, guards, semantics) == before


def test_observer_only_runs_for_typed_results_and_exception_is_swallowed(monkeypatch):
    observations = []
    monkeypatch.setattr(subject, "_execute_follow_up_call", lambda *a, **k: [])
    result = _run(_plan(_task()), [_context()], [_guard()], semantics=_semantics("task-1"), observer=observations.append)
    assert observations == [] and result["authoritative"] is True
    def execute(*args, shadow_observer=None, **kwargs): shadow_observer(object()); return []
    def exploding(_payload): raise RuntimeError("observer")
    monkeypatch.setattr(subject, "_execute_follow_up_call", execute)
    result = _run(_plan(_task()), [_context()], [_guard()], semantics=_semantics("task-1"), observer=exploding)
    assert result["authoritative"] is True and result["executed_unit_count"] == 1


def test_baseexception_from_execution_propagates(monkeypatch):
    class Fatal(BaseException): pass
    monkeypatch.setattr(subject, "_execute_follow_up_call", lambda *a, **k: (_ for _ in ()).throw(Fatal()))
    with pytest.raises(Fatal):
        _run(_plan(_task()), [_context()], [_guard()], semantics=_semantics("task-1"))
