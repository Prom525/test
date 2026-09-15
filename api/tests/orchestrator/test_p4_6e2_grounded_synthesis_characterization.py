"""Characterize the direct P4.6E2 grounded-synthesis contract."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.orchestrator import task_grounded_synthesis as subject
from app.orchestrator.evidence_assessor import EvidenceAssessmentStatus
from app.orchestrator.evidence_reconciler import EvidenceReconciliationStatus
from app.orchestrator.evidence_research_executor import ResearchExecutionStatus
from app.orchestrator.evidence_synthesizer import GroundedClaim, GroundedSynthesisResult, GroundedSynthesisStatus


class Fatal(BaseException):
    pass


class ExplodingIterable:
    def __init__(self, error): self.error = error
    def __iter__(self): raise self.error


def _authority(*units, **overrides):
    value = {
        "authoritative": True,
        "authority_scope": "intent_task_research_evidence_reassessment_only",
        "units": list(units) or [{"task_id": "task-1", "family_code": "f1",
                                  "status": "reassessed", "assessment_status": "sufficient"}],
    }
    value.update(overrides)
    return value


def _assessment(status=EvidenceAssessmentStatus.SUFFICIENT):
    return SimpleNamespace(status=status)


def _row(task_id="task-1", family_code="f1", *, assessment=None, evidence_items=None):
    return {
        "task_id": task_id, "family_code": family_code,
        "requirement_set_id": "requirements.v1", "requirement_set_intent": "lookup",
        "assessment": assessment or _assessment(),
        "evidence_items": evidence_items if evidence_items is not None else
            (SimpleNamespace(evidence_id="ev-1"),),
    }


def _grounded(*claims, status=GroundedSynthesisStatus.COMPLETE,
              used=("ev-1",), omitted=(), conflicting=()):
    return GroundedSynthesisResult(
        contract_version="grounded.v1", requirement_set_id="requirements.v1",
        intent="lookup", status=status, claims=claims,
        omitted_requirement_ids=omitted, conflicting_requirement_ids=conflicting,
        evidence_ids_used=used, reasons=(),
    )


def _claim(text="claim", evidence_ids=("ev-1",), requirement_ids=("req-1",)):
    return GroundedClaim("claim-1", text, evidence_ids, requirement_ids)


@pytest.mark.parametrize("authority,reason", [
    (None, "missing_task_research_evidence_authority"),
    (object(), "missing_task_research_evidence_authority"),
    ({}, "task_research_evidence_authority_not_active"),
    (_authority(authoritative=False), "task_research_evidence_authority_not_active"),
    (_authority(authority_scope="wrong"), "task_research_evidence_authority_not_active"),
])
def test_missing_inactive_or_wrong_scope_reasons_without_synthesis(monkeypatch, authority, reason):
    calls = []
    monkeypatch.setattr(subject, "synthesize_grounded_evidence", calls.append)
    result = subject.build_task_grounded_synthesis_authority_canary_p4_6e2(authority, [_row()])
    assert result["reason"] == reason and result["authoritative"] is False
    assert calls == []


def test_disabled_reason_precedes_input_validation(monkeypatch):
    monkeypatch.setenv("AI_TASK_GROUNDED_SYNTHESIS_AUTHORITY_CANARY_ENABLED", "off")
    result = subject.build_task_grounded_synthesis_authority_canary_p4_6e2(None, [])
    assert result["reason"] == "disabled" and result["enabled"] is False


def test_sufficient_keys_require_dict_reassessed_and_sufficient(monkeypatch):
    calls = []
    monkeypatch.setattr(subject, "synthesize_grounded_evidence", calls.append)
    bad = _authority(
        object(),
        {"task_id": "task-1", "family_code": "f1", "status": "other", "assessment_status": "sufficient"},
        {"task_id": "task-1", "family_code": "f1", "status": "reassessed", "assessment_status": "partial"},
    )
    result = subject.build_task_grounded_synthesis_authority_canary_p4_6e2(bad, [_row()])
    assert result["reason"] == "no_sufficient_authoritative_evidence_units"
    assert calls == []


def test_matching_rows_keep_order_and_duplicates_and_build_exact_reconciliation(monkeypatch):
    reconciliations = []
    evidence = (SimpleNamespace(evidence_id="ev-1"), SimpleNamespace(evidence_id=""),
                SimpleNamespace(evidence_id="ev-2"))
    assessment = _assessment()
    rows = [object(), _row("other", "f1"), _row(assessment=assessment, evidence_items=evidence),
            _row(assessment=assessment, evidence_items=evidence)]
    monkeypatch.setattr(subject, "synthesize_grounded_evidence",
                        lambda reconciliation: reconciliations.append(reconciliation) or _grounded(_claim()))
    result = subject.build_task_grounded_synthesis_authority_canary_p4_6e2(_authority(), rows)
    assert len(reconciliations) == 2 and result["unit_count"] == 2
    for reconciliation in reconciliations:
        assert reconciliation.contract_version == "p4_6e2_task_grounded_synthesis_reconciliation.v1"
        assert reconciliation.requirement_set_id == "requirements.v1" and reconciliation.intent == "lookup"
        assert reconciliation.status is EvidenceReconciliationStatus.IMPROVED
        assert reconciliation.research_status is ResearchExecutionStatus.COMPLETED
        assert reconciliation.initial_evidence_items == ()
        assert reconciliation.reconciled_evidence_items is evidence
        assert reconciliation.added_evidence_ids == ("ev-1", "ev-2")
        assert reconciliation.discarded_result_count == 0
        assert reconciliation.initial_assessment is assessment
        assert reconciliation.reconciled_assessment is assessment
        assert reconciliation.reasons == ("p4_6e2_authoritative_task_grounded_synthesis",)


@pytest.mark.parametrize("assessment,evidence", [(None, (object(),)),
    (_assessment(EvidenceAssessmentStatus.PARTIAL), (object(),)), (_assessment(), ())])
def test_invalid_authoritative_unit_is_blocked_without_synthesis(monkeypatch, assessment, evidence):
    calls = []
    monkeypatch.setattr(subject, "synthesize_grounded_evidence", calls.append)
    row = _row(); row["assessment"] = assessment; row["evidence_items"] = evidence
    result = subject.build_task_grounded_synthesis_authority_canary_p4_6e2(_authority(), [row])
    assert result["reason"] == "no_grounded_units"
    assert result["units"] == [{"task_id": "task-1", "family_code": "f1",
        "status": "blocked_invalid_authoritative_evidence_unit", "grounded_synthesis_status": None,
        "claim_count": 0, "evidence_ids_used": []}]
    assert calls == []


@pytest.mark.parametrize("error_type", [RuntimeError, KeyboardInterrupt])
def test_evidence_iteration_exception_and_baseexception_propagate(monkeypatch, error_type):
    error = error_type("evidence")
    row = _row(); row["evidence_items"] = ExplodingIterable(error)
    with pytest.raises(error_type) as raised:
        subject.build_task_grounded_synthesis_authority_canary_p4_6e2(_authority(), [row])
    assert raised.value is error


@pytest.mark.parametrize("error_type", [RuntimeError, KeyboardInterrupt])
def test_synthesizer_exception_and_baseexception_propagate(monkeypatch, error_type):
    error = error_type("synthesizer")
    monkeypatch.setattr(subject, "synthesize_grounded_evidence",
                        lambda _reconciliation: (_ for _ in ()).throw(error))
    with pytest.raises(error_type) as raised:
        subject.build_task_grounded_synthesis_authority_canary_p4_6e2(_authority(), [_row()])
    assert raised.value is error


def test_grounded_metadata_claim_serialization_aggregates_and_legacy_boundaries(monkeypatch):
    claim = GroundedClaim("c1", "text", ("ev-2", "ev-1"), ("r2", "r1"))
    monkeypatch.setattr(subject, "synthesize_grounded_evidence", lambda _: _grounded(
        claim, status=GroundedSynthesisStatus.PARTIAL, used=("ev-2", "ev-1"),
        omitted=("r3",), conflicting=("r4",)))
    authority, rows = _authority(), [_row()]
    before = deepcopy((authority, rows))
    result = subject.build_task_grounded_synthesis_authority_canary_p4_6e2(authority, rows)
    unit = result["units"][0]
    assert unit == {"task_id": "task-1", "family_code": "f1", "status": "grounded",
        "requirement_set_id": "requirements.v1", "grounded_synthesis_status": "partial",
        "claim_count": 1, "claims": [{"claim_id": "c1", "text": "text",
        "evidence_ids": ["ev-2", "ev-1"], "requirement_ids": ["r2", "r1"]}],
        "evidence_ids_used": ["ev-2", "ev-1"], "omitted_requirement_ids": ["r3"],
        "conflicting_requirement_ids": ["r4"]}
    assert (result["unit_count"], result["grounded_unit_count"], result["claim_count"]) == (1, 1, 1)
    assert result["eligible"] is result["authoritative"] is True
    assert result["reason"] == "activated_task_grounded_synthesis_authority"
    assert result["legacy_phase_c_authority_unchanged"] is True
    assert result["legacy_reconciliation_authority"] is result["public_answer_authority"] is False
    assert deepcopy((authority, rows)) == before
    assert "namespace" not in repr(result).lower()


def test_mixed_blocked_and_grounded_units_still_activate_authority(monkeypatch):
    monkeypatch.setattr(subject, "synthesize_grounded_evidence", lambda _: _grounded(_claim()))
    blocked = _row(); blocked["assessment"] = None
    result = subject.build_task_grounded_synthesis_authority_canary_p4_6e2(
        _authority(), [blocked, _row()])
    assert [unit["status"] for unit in result["units"]] == [
        "blocked_invalid_authoritative_evidence_unit", "grounded"]
    assert result["authoritative"] is True


def test_grounded_unit_without_claims_is_not_authoritative(monkeypatch):
    monkeypatch.setattr(subject, "synthesize_grounded_evidence", lambda _: _grounded())
    result = subject.build_task_grounded_synthesis_authority_canary_p4_6e2(_authority(), [_row()])
    assert result["reason"] == "grounded_unit_without_claims" and result["authoritative"] is False


@pytest.mark.parametrize("claim", [_claim(text="  "), _claim(evidence_ids=()), _claim(requirement_ids=())])
def test_invalid_grounded_claim_contract(claim, monkeypatch):
    monkeypatch.setattr(subject, "synthesize_grounded_evidence", lambda _: _grounded(claim))
    result = subject.build_task_grounded_synthesis_authority_canary_p4_6e2(_authority(), [_row()])
    assert result["reason"] == "invalid_grounded_claim_contract" and result["authoritative"] is False


@pytest.mark.parametrize("attribute", ["claims", "evidence_ids_used",
    "omitted_requirement_ids", "conflicting_requirement_ids"])
def test_grounded_iterable_baseexception_propagates(attribute, monkeypatch):
    fatal = Fatal(attribute)
    grounded = SimpleNamespace(status="grounded", claims=(_claim(),), evidence_ids_used=("ev-1",),
                               omitted_requirement_ids=(), conflicting_requirement_ids=())
    setattr(grounded, attribute, ExplodingIterable(fatal))
    monkeypatch.setattr(subject, "synthesize_grounded_evidence", lambda _: grounded)
    with pytest.raises(Fatal) as raised:
        subject.build_task_grounded_synthesis_authority_canary_p4_6e2(_authority(), [_row()])
    assert raised.value is fatal


@pytest.mark.parametrize("attribute", ["evidence_ids", "requirement_ids"])
def test_claim_iterable_baseexception_propagates(attribute, monkeypatch):
    fatal = Fatal(attribute)
    claim = SimpleNamespace(claim_id="c", text="text", evidence_ids=("ev",), requirement_ids=("r",))
    setattr(claim, attribute, ExplodingIterable(fatal))
    monkeypatch.setattr(subject, "synthesize_grounded_evidence", lambda _: _grounded(claim))
    with pytest.raises(Fatal) as raised:
        subject.build_task_grounded_synthesis_authority_canary_p4_6e2(_authority(), [_row()])
    assert raised.value is fatal
