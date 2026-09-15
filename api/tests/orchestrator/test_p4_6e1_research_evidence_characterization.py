"""Direct characterization of P4.6E1 task-research evidence reassessment."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import MappingProxyType, SimpleNamespace

import pytest

from app.orchestrator import task_research_evidence as subject
from app.orchestrator.models import Domain, IntentTask, QueryPlan


def _task(task_id="task-1", *, intent="technical_lookup", requirement_set_id="technical.v1"):
    return IntentTask(task_id=task_id, domain=Domain.TECHNICAL, intent=intent,
                      evidence_requirement_set_id=requirement_set_id)


def _plan(*tasks):
    return QueryPlan(original_question="q", normalized_question="q",
                     primary_domain=Domain.TECHNICAL, domains=[Domain.TECHNICAL],
                     intent="technical_lookup", intent_tasks=list(tasks))


def _authority(count=1):
    return {"authoritative": True, "authority_scope": "intent_task_research_execution_only",
            "accepted_follow_up_result_count": count}


def _assessment(status="sufficient"):
    return SimpleNamespace(status=status,
        missing_required_requirement_ids=("missing",),
        conflicting_requirement_ids=("conflict",),
        evidence_ids_considered=("ev-a", "ev-b"))


@pytest.mark.parametrize(("env", "authority", "reason"), [
    ("false", _authority(), "disabled"),
    ("true", None, "missing_task_research_execution_authority"),
    ("true", {}, "task_research_execution_authority_not_active"),
    ("true", {"authoritative": False, "authority_scope": "intent_task_research_execution_only"},
     "task_research_execution_authority_not_active"),
    ("true", _authority(0), "no_accepted_follow_up_results"),
    ("true", _authority(-1), "no_accepted_follow_up_results"),
])
def test_early_gates_exact_reason_without_workers(monkeypatch, env, authority, reason):
    calls = []
    monkeypatch.setenv("AI_TASK_RESEARCH_EVIDENCE_AUTHORITY_CANARY_ENABLED", env)
    monkeypatch.setattr(subject, "normalize_execution_result_evidence", lambda *a, **k: calls.append("n"))
    monkeypatch.setattr(subject, "assess_evidence", lambda *a, **k: calls.append("a"))
    result = subject.build_task_research_evidence_authority_canary_p4_6e1(
        _plan(_task()), authority, [{"task_id": "task-1"}], (),
        grounded_synthesis_observer=lambda row: calls.append("o"))
    assert result["reason"] == reason and result["authoritative"] is False and calls == []


def test_observation_filtering_unknown_tasks_and_missing_requirement(monkeypatch):
    task = _task(requirement_set_id="missing", intent="missing")
    calls = []
    monkeypatch.setattr(subject, "REQUIREMENT_SETS_BY_INTENT", MappingProxyType({}))
    result = subject.build_task_research_evidence_authority_canary_p4_6e1(
        _plan(task), _authority(), [None, 1, {"task_id": "unknown"}, {"task_id": task.task_id}], (),
        grounded_synthesis_observer=lambda row: calls.append(row))
    assert result["execution_observation_count"] == 2
    assert result["units"] == [{"task_id": task.task_id, "domain": "technical", "family_code": None,
        "status": "blocked_missing_requirement_set", "normalized_evidence_count": 0,
        "assessment_status": None}]
    assert result["reason"] == "no_reassessed_execution_units" and calls == []


@pytest.mark.parametrize("rows", [[], [None, 1, object()]])
def test_no_valid_dict_observations(rows):
    result = subject.build_task_research_evidence_authority_canary_p4_6e1(
        _plan(_task()), _authority(), rows, ())
    assert result["execution_observation_count"] == 0
    assert result["reason"] == "missing_internal_execution_observations"


@pytest.mark.parametrize(("supplied", "expected"), [
    (datetime(2025, 1, 2, 3, 4, 5), datetime(2025, 1, 2, 3, 4, 5, tzinfo=timezone.utc)),
    (datetime(2025, 1, 2, 4, 4, 5, tzinfo=timezone(timedelta(hours=1))),
     datetime(2025, 1, 2, 3, 4, 5, tzinfo=timezone.utc)),
])
def test_now_normalization_and_same_value_for_all_workers(monkeypatch, supplied, expected):
    seen, normalized = [], object()
    monkeypatch.setattr(subject, "normalize_execution_result_evidence",
        lambda result, *, retrieved_at: seen.append(("n", retrieved_at)) or (normalized,))
    monkeypatch.setattr(subject, "assess_evidence",
        lambda req, evidence, *, target_entity_ids, now: seen.append(("a", now)) or _assessment())
    task = _task()
    subject.build_task_research_evidence_authority_canary_p4_6e1(
        _plan(task), _authority(), [{"task_id": task.task_id,
        "execution_results": (SimpleNamespace(legacy_accepted=True),) * 2}], (), now=supplied)
    assert [stamp for _, stamp in seen] == [expected, expected, expected]
    assert all(stamp is seen[0][1] for _, stamp in seen)


def test_missing_now_is_aware_utc(monkeypatch):
    seen = []
    monkeypatch.setattr(subject, "normalize_execution_result_evidence",
        lambda result, *, retrieved_at: seen.append(retrieved_at) or (object(),))
    monkeypatch.setattr(subject, "assess_evidence", lambda *a, **k: _assessment())
    task = _task()
    subject.build_task_research_evidence_authority_canary_p4_6e1(
        _plan(task), _authority(), [{"task_id": task.task_id,
        "execution_results": (SimpleNamespace(legacy_accepted=True),)}], ())
    assert seen[0].tzinfo is timezone.utc


def test_requirement_id_precedes_intent_and_exact_combined_observer_contract(monkeypatch):
    by_id = SimpleNamespace(requirement_set_id="chosen.v1", intent="chosen")
    by_intent = SimpleNamespace(requirement_set_id="intent.v1", intent="technical_lookup")
    monkeypatch.setattr(subject, "REQUIREMENT_SETS_BY_INTENT",
                        MappingProxyType({"technical_lookup": by_intent, "other": by_id}))
    task = _task(requirement_set_id="chosen.v1")
    initial_product = SimpleNamespace(domain="technical", entity_type="PRODUCT", entity_id="Fam-A")
    initial_provenance = SimpleNamespace(domain="technical", entity_type="other", entity_id=None,
                                         provenance={"family_code": "fam-a"})
    wrong_domain = SimpleNamespace(domain="Technical", entity_type="product", entity_id="fam-a")
    wrong_family = SimpleNamespace(domain="technical", entity_type="product", entity_id="fam-b")
    normalized = (object(), object())
    assessed, observed, assess_calls = _assessment("insufficient"), [], []
    monkeypatch.setattr(subject, "normalize_execution_result_evidence",
                        lambda result, **kwargs: normalized if result.index == 1 else (normalized[0],))
    monkeypatch.setattr(subject, "assess_evidence", lambda *a, **k:
                        assess_calls.append((a, k)) or assessed)
    results = (SimpleNamespace(legacy_accepted=1, index=0),
               SimpleNamespace(legacy_accepted=True, index=0),
               SimpleNamespace(legacy_accepted=True, index=1))
    result = subject.build_task_research_evidence_authority_canary_p4_6e1(
        _plan(task), _authority(), [{"task_id": task.task_id, "family_code": "FAM-A",
        "execution_results": results}],
        (initial_product, wrong_domain, initial_provenance, wrong_family),
        now=datetime(2025, 1, 1, tzinfo=timezone.utc), grounded_synthesis_observer=observed.append)
    combined = assess_calls[0][0][1]
    assert assess_calls[0][0][0] is by_id
    assert combined == (initial_product, initial_provenance, normalized[0], normalized[0], normalized[1])
    assert all(a is b for a, b in zip(combined,
        (initial_product, initial_provenance, normalized[0], normalized[0], normalized[1])))
    assert assess_calls[0][1]["target_entity_ids"] == {"product": "FAM-A"}
    assert observed == [{"task_id": task.task_id, "family_code": "FAM-A",
        "requirement_set_id": "chosen.v1", "requirement_set_intent": "chosen",
        "assessment": assessed, "evidence_items": combined}]
    unit = result["units"][0]
    assert unit == {"task_id": task.task_id, "domain": "technical", "family_code": "FAM-A",
        "status": "reassessed", "requirement_set_id": "chosen.v1", "initial_evidence_count": 2,
        "normalized_evidence_count": 3, "combined_evidence_count": 5,
        "assessment_status": "insufficient", "missing_required_requirement_ids": ["missing"],
        "conflicting_requirement_ids": ["conflict"], "evidence_ids_considered": ["ev-a", "ev-b"]}
    assert result["normalized_follow_up_evidence_count"] == 3
    assert result["reassessed_unit_count"] == 1 and result["sufficient_unit_count"] == 0
    assert result["eligible"] is result["authoritative"] is True
    assert result["reason"] == "activated_task_research_evidence_reassessment_authority"


@pytest.mark.parametrize(("normalized", "reason", "authoritative"), [
    ((), "accepted_follow_up_without_normalized_evidence", False),
    ((object(),), "activated_task_research_evidence_reassessment_authority", True),
])
def test_zero_or_positive_normalized_authority_semantics(monkeypatch, normalized, reason, authoritative):
    monkeypatch.setattr(subject, "normalize_execution_result_evidence", lambda *a, **k: normalized)
    monkeypatch.setattr(subject, "assess_evidence", lambda *a, **k: _assessment("insufficient"))
    task = _task()
    result = subject.build_task_research_evidence_authority_canary_p4_6e1(
        _plan(task), _authority(), [{"task_id": task.task_id,
        "execution_results": (SimpleNamespace(legacy_accepted=True),)}], ())
    assert result["reason"] == reason and result["authoritative"] is authoritative


def test_intent_requirement_fallback_none_target_and_multi_unit_aggregates(monkeypatch):
    requirement_set = SimpleNamespace(requirement_set_id="intent.v1", intent="fallback")
    monkeypatch.setattr(subject, "REQUIREMENT_SETS_BY_INTENT",
                        MappingProxyType({"fallback": requirement_set}))
    tasks = (_task("a", intent="fallback", requirement_set_id=None),
             _task("b", intent="fallback", requirement_set_id="unknown.v1"))
    normalized = object()
    assess_calls = []
    monkeypatch.setattr(subject, "normalize_execution_result_evidence",
                        lambda *a, **k: (normalized,))
    assessments = iter((_assessment("sufficient"), _assessment("insufficient")))
    monkeypatch.setattr(subject, "assess_evidence", lambda *a, **k:
                        assess_calls.append((a, k)) or next(assessments))
    observations = [{"task_id": task.task_id,
        "execution_results": (SimpleNamespace(legacy_accepted=True),)} for task in tasks]
    result = subject.build_task_research_evidence_authority_canary_p4_6e1(
        _plan(*tasks), _authority(2), observations, ())
    assert all(call[0][0] is requirement_set for call in assess_calls)
    assert all(call[1]["target_entity_ids"] is None for call in assess_calls)
    assert result["normalized_follow_up_evidence_count"] == 2
    assert result["reassessed_unit_count"] == 2
    assert result["sufficient_unit_count"] == 1
    assert result["authoritative"] is True


def test_observer_exception_swallowed_but_baseexception_propagates(monkeypatch):
    monkeypatch.setattr(subject, "normalize_execution_result_evidence", lambda *a, **k: (object(),))
    monkeypatch.setattr(subject, "assess_evidence", lambda *a, **k: _assessment())
    task, observation = _task(), {"task_id": "task-1",
        "execution_results": (SimpleNamespace(legacy_accepted=True),)}
    def ordinary(_row):
        raise RuntimeError("observer")
    assert subject.build_task_research_evidence_authority_canary_p4_6e1(
        _plan(task), _authority(), [observation], (), grounded_synthesis_observer=ordinary
    )["authoritative"] is True
    class Fatal(BaseException): pass
    def fatal(_row): raise Fatal("observer")
    with pytest.raises(Fatal):
        subject.build_task_research_evidence_authority_canary_p4_6e1(
            _plan(task), _authority(), [observation], (), grounded_synthesis_observer=fatal)


@pytest.mark.parametrize("worker", ["normalizer", "assessor"])
@pytest.mark.parametrize("error_type", [RuntimeError, KeyboardInterrupt])
def test_worker_exception_and_baseexception_both_propagate(monkeypatch, worker, error_type):
    error = error_type("worker")
    monkeypatch.setattr(subject, "normalize_execution_result_evidence",
                        (lambda *a, **k: (_ for _ in ()).throw(error)) if worker == "normalizer"
                        else (lambda *a, **k: (object(),)))
    monkeypatch.setattr(subject, "assess_evidence",
                        (lambda *a, **k: (_ for _ in ()).throw(error)) if worker == "assessor"
                        else (lambda *a, **k: _assessment()))
    task = _task()
    with pytest.raises(error_type) as raised:
        subject.build_task_research_evidence_authority_canary_p4_6e1(
            _plan(task), _authority(), [{"task_id": task.task_id,
            "execution_results": (SimpleNamespace(legacy_accepted=True),)}], ())
    assert raised.value is error


def test_inputs_unmutated_and_contract_excludes_payload_and_answer_authority(monkeypatch):
    monkeypatch.setattr(subject, "normalize_execution_result_evidence", lambda *a, **k: (object(),))
    monkeypatch.setattr(subject, "assess_evidence", lambda *a, **k: _assessment())
    plan, authority = _plan(_task()), _authority()
    observations = [{"task_id": "task-1", "raw_payload": {"secret": "x"},
        "execution_results": (SimpleNamespace(legacy_accepted=True),)}]
    initial, catalog = [SimpleNamespace(domain="technical")], subject.REQUIREMENT_SETS_BY_INTENT
    before = deepcopy((plan, authority, observations, initial))
    result = subject.build_task_research_evidence_authority_canary_p4_6e1(
        plan, authority, observations, tuple(initial))
    assert deepcopy((plan, authority, observations, initial)) == before
    assert subject.REQUIREMENT_SETS_BY_INTENT is catalog
    assert "raw_payload" not in repr(result)
    assert result["public_answer_authority"] is False
