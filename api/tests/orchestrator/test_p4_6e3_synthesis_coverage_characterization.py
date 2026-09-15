"""Characterize the direct P4.6E3 task synthesis coverage contract."""
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace

import pytest

from app.orchestrator import task_synthesis_coverage as subject
from app.orchestrator.evidence_assessor import EvidenceAssessmentStatus


class Fatal(BaseException):
    pass


class ExplodingIterable:
    def __init__(self, error): self.error = error
    def __iter__(self): raise self.error


def _task(task_id="t1", *, required=True, polarity="requested", domain="parts", families=None, intent="lookup"):
    scope = {} if families is None else {"product_family_codes": families}
    return SimpleNamespace(task_id=task_id, required=required, polarity=polarity,
                           domain=domain, scope=scope, intent=intent)


def _plan(*tasks):
    return SimpleNamespace(intent_tasks=list(tasks))


def _c(**overrides):
    value = {"authoritative": True, "authority_scope": "intent_task_evidence_assessment_only"}
    value.update(overrides)
    return value


def _e2(*units, **overrides):
    value = {"authoritative": True, "authority_scope": "intent_task_grounded_synthesis_only",
             "units": list(units)}
    value.update(overrides)
    return value


def _unit(task_id="t1", family_code=None, *, claims=None, claim_count=1, status="grounded"):
    if claims is None:
        claims = [{"text": " claim ", "evidence_ids": ["e1"], "requirement_ids": ["r1"]}]
    return {"task_id": task_id, "family_code": family_code, "status": status,
            "claim_count": claim_count, "claims": claims, "payload": object()}


@pytest.mark.parametrize("enabled,authority,reason", [
    (False, None, "disabled"),
    (True, None, "missing_task_evidence_authority"),
    (True, object(), "missing_task_evidence_authority"),
    (True, {}, "task_evidence_authority_not_active"),
    (True, _c(authoritative=False), "task_evidence_authority_not_active"),
    (True, _c(authority_scope="wrong"), "task_evidence_authority_not_active"),
])
def test_gate_defaults_and_exact_early_reasons(monkeypatch, enabled, authority, reason):
    monkeypatch.setenv("AI_TASK_GROUNDED_SYNTHESIS_COVERAGE_AUTHORITY_CANARY_ENABLED",
                       "true" if enabled else "off")
    result = subject.build_task_grounded_synthesis_coverage_authority_canary_p4_6e3(
        _plan(_task()), authority, None, ())
    assert result["reason"] == reason
    assert result["contract_version"] == "promati.multi_intent.task_grounded_synthesis_coverage_authority_canary.v1"
    assert result["authority_scope"] == "intent_task_grounded_synthesis_coverage_only"
    assert result["eligible"] is result["authoritative"] is False
    assert result["legacy_phase_c_authority_unchanged"] is True
    assert result["legacy_reconciliation_authority"] is result["public_answer_authority"] is False
    assert (result["covered_task_count"], result["unit_count"], result["grounded_unit_count"], result["claim_count"]) == (0, 0, 0, 0)
    assert result["units"] == [] and result["uncovered_task_ids"] == []


def test_task_filter_requires_literal_true_and_exact_requested_and_preserves_order():
    tasks = [_task("a"), _task("b", required=1), _task("c", required=False),
             _task("d", polarity="REQUESTED"), _task("e", polarity="requested")]
    result = subject.build_task_grounded_synthesis_coverage_authority_canary_p4_6e3(
        _plan(*tasks), _c(), _e2(_unit("a"), _unit("e")), ())
    assert result["total_task_count"] == 2
    assert [row["task_id"] for row in result["units"]] == ["a", "e"]
    assert result["authoritative"] is True


@pytest.mark.parametrize("authority,expected_fallback,reason", [
    (None, True, "no_intent_tasks"),
    ({}, False, "task_grounded_synthesis_authority_not_active"),
    (_e2(authoritative=False, reason="no_grounded_units"), True, "no_intent_tasks"),
    (_e2(authoritative=False, reason="missing_task_research_evidence_authority"), True, "no_intent_tasks"),
    (_e2(authoritative=False, reason="task_research_evidence_authority_not_active"), True, "no_intent_tasks"),
    (_e2(authoritative=False, reason="no_sufficient_authoritative_evidence_units"), True, "no_intent_tasks"),
    (_e2(authoritative=False, reason="disabled"), False, "task_grounded_synthesis_authority_not_active"),
])
def test_e2_active_or_existing_evidence_fallback_reason_allowlist(authority, expected_fallback, reason):
    result = subject.build_task_grounded_synthesis_coverage_authority_canary_p4_6e3(
        _plan(), _c(), authority, ())
    assert result["reason"] == reason
    if expected_fallback:
        assert result["existing_task_evidence_fallback"] is True
        assert result["task_grounded_synthesis_authority_required"] is False
        assert result["fallback_reason"] == "existing_sufficient_task_evidence"


def test_family_normalization_matching_order_copy_duplicate_overwrite_and_no_input_mutation():
    task = _task(families=[" F1 ", "f1", "F2", "", "f2"])
    first, replacement, second = _unit(family_code="F1"), _unit(family_code="F1"), _unit(family_code="F2")
    first["marker"], replacement["marker"], second["marker"] = "first", "last", "second"
    authority = _e2(first, replacement, second)
    before = [dict(row) for row in authority["units"]]
    result = subject.build_task_grounded_synthesis_coverage_authority_canary_p4_6e3(
        _plan(task), _c(), authority, ())
    assert [row["family_code"] for row in result["units"]] == ["F1", "F2"]
    assert [row["marker"] for row in result["units"]] == ["last", "second"]
    assert result["units"][0] is not replacement
    assert all(row["source"] == "p4_6e2_authoritative_research_grounded" and row["domain"] == "parts"
               for row in result["units"])
    assert authority["units"] == before and "source" not in replacement and "domain" not in replacement


@pytest.mark.parametrize("families", ["F1", {"F1"}, 7, None])
def test_only_list_or_tuple_family_codes_are_recognized(families):
    result = subject.build_task_grounded_synthesis_coverage_authority_canary_p4_6e3(
        _plan(_task(families=families)), _c(), _e2(_unit(family_code=None)), ())
    assert result["authoritative"] is True and result["units"][0]["family_code"] is None


def test_research_units_are_dict_grounded_positive_and_match_case_sensitively():
    rows = [object(), _unit(status="Grounded"), _unit(claim_count=0),
            _unit(family_code="f1"), _unit(family_code="F1")]
    result = subject.build_task_grounded_synthesis_coverage_authority_canary_p4_6e3(
        _plan(_task(families=["F1"])), _c(), _e2(*rows), ())
    assert result["authoritative"] is True
    assert result["units"][0] is not rows[-1]


def test_partial_family_coverage_keeps_units_and_duplicates_uncovered_task_ids():
    tasks = [_task("same", families=["F1", "F2"]), _task("same", families=["F1", "F2"])]
    result = subject.build_task_grounded_synthesis_coverage_authority_canary_p4_6e3(
        _plan(*tasks), _c(), _e2(_unit("same", "F1")), ())
    assert [row["family_code"] for row in result["units"]] == ["F1", "F1"]
    assert result["uncovered_task_ids"] == ["same", "same"]
    assert result["covered_task_count"] == 0 and result["unit_count"] == 2
    assert result["reason"] == "incomplete_task_grounded_synthesis_coverage"


@pytest.mark.parametrize("claims", [
    [object()], [{"text": " ", "evidence_ids": ["e"], "requirement_ids": ["r"]}],
    [{"text": "x", "evidence_ids": [], "requirement_ids": ["r"]}],
    [{"text": "x", "evidence_ids": ["e"], "requirement_ids": []}],
])
def test_invalid_claim_shapes_block_authority(claims):
    result = subject.build_task_grounded_synthesis_coverage_authority_canary_p4_6e3(
        _plan(_task()), _c(), _e2(_unit(claims=claims)), ())
    assert result["reason"] == "invalid_grounded_claim_contract"
    assert result["eligible"] is result["authoritative"] is False


def test_empty_claim_list_vacuously_activates_and_mixed_units_are_ignored():
    valid = _unit(claims=[], claim_count=3)
    result = subject.build_task_grounded_synthesis_coverage_authority_canary_p4_6e3(
        _plan(_task()), _c(), _e2(valid, _unit(status="blocked", claim_count=99)), ())
    assert result["authoritative"] is result["eligible"] is True
    assert result["reason"] == "activated_complete_task_grounded_synthesis_coverage_authority"
    assert (result["unit_count"], result["grounded_unit_count"], result["claim_count"]) == (1, 1, 3)


@pytest.mark.parametrize("supplied,expected", [
    (None, None),
    (datetime(2026, 1, 2, 3, 4, 5), datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)),
    (datetime(2026, 1, 2, 4, 4, 5, tzinfo=timezone(timedelta(hours=1))),
     datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)),
])
def test_existing_evidence_path_normalizes_timestamp_and_preserves_dependency_identity(monkeypatch, supplied, expected):
    task, item = _task(families=["F1"]), SimpleNamespace(domain="parts", entity_type="product", entity_id="f1")
    requirement, assessment, grounded = SimpleNamespace(requirement_set_id="req", intent="lookup"), SimpleNamespace(status=EvidenceAssessmentStatus.SUFFICIENT), SimpleNamespace(
        status="complete", claims=(SimpleNamespace(claim_id="c", text="x", evidence_ids=("e",), requirement_ids=("r",)),),
        evidence_ids_used=("e",), omitted_requirement_ids=(), conflicting_requirement_ids=())
    seen = {}
    monkeypatch.setattr(subject, "get_requirement_set", lambda intent: seen.setdefault("intent", intent) or requirement)
    monkeypatch.setattr(subject, "get_requirement_set", lambda intent: requirement)
    def assess(actual_requirement, selected, **kwargs):
        seen.update(requirement=actual_requirement, selected=selected, target=kwargs["target_entity_ids"], now=kwargs["now"])
        return assessment
    def synthesize(reconciliation):
        seen["reconciliation"] = reconciliation
        return grounded
    monkeypatch.setattr(subject, "assess_evidence", assess)
    monkeypatch.setattr(subject, "synthesize_grounded_evidence", synthesize)
    result = subject.build_task_grounded_synthesis_coverage_authority_canary_p4_6e3(
        _plan(task), _c(), None, (item,), now=supplied)
    assert result["authoritative"] is True
    assert seen["requirement"] is requirement and seen["selected"] == (item,)
    assert seen["target"] == {"product": "F1"}
    if expected is not None: assert seen["now"] == expected
    else: assert seen["now"].tzinfo is timezone.utc
    rec = seen["reconciliation"]
    assert rec.initial_evidence_items is rec.reconciled_evidence_items
    assert rec.initial_evidence_items == (item,) and rec.initial_assessment is rec.reconciled_assessment is assessment
    assert result["units"][0]["source"] == "existing_authoritative_task_evidence"


def test_evidence_selection_uses_exact_domain_then_product_or_provenance_family(monkeypatch):
    task = _task(families=["F1"])
    product = SimpleNamespace(domain="parts", entity_type="PRODUCT", entity_id="f1", provenance={"family_code": "wrong"})
    provenance = SimpleNamespace(domain="parts", entity_type="other", entity_id=None, provenance={"family_code": " F1 "})
    wrong_domain = SimpleNamespace(domain="PARTS", entity_type="product", entity_id="F1", provenance={})
    seen = []
    req = SimpleNamespace(requirement_set_id="req", intent="lookup")
    monkeypatch.setattr(subject, "get_requirement_set", lambda _: req)
    monkeypatch.setattr(subject, "assess_evidence", lambda requirement, selected, **kw:
                        seen.append(selected) or SimpleNamespace(status="sufficient"))
    monkeypatch.setattr(subject, "synthesize_grounded_evidence", lambda rec: SimpleNamespace(
        status="complete", claims=(SimpleNamespace(claim_id="c", text="x", evidence_ids=("e",), requirement_ids=("r",)),),
        evidence_ids_used=("e",), omitted_requirement_ids=(), conflicting_requirement_ids=()))
    subject.build_task_grounded_synthesis_coverage_authority_canary_p4_6e3(
        _plan(task), _c(), None, (product, provenance, wrong_domain))
    assert seen == [(product, provenance)]


@pytest.mark.parametrize("location", ["tasks", "e2_units", "evidence", "requirements", "assessment", "synthesis"])
def test_direct_exceptions_and_baseexceptions_propagate(monkeypatch, location):
    error = Fatal(location)
    plan, authority, evidence = _plan(_task()), _e2(), ()
    if location == "tasks": plan.intent_tasks = ExplodingIterable(error)
    elif location == "e2_units": authority["units"] = ExplodingIterable(error)
    elif location == "evidence": authority = None; evidence = ExplodingIterable(error)
    elif location == "requirements": authority = None; monkeypatch.setattr(subject, "get_requirement_set", lambda _: (_ for _ in ()).throw(error))
    elif location == "assessment":
        authority = None; evidence = (SimpleNamespace(domain="parts", entity_type="other", provenance={}),)
        monkeypatch.setattr(subject, "get_requirement_set", lambda _: SimpleNamespace(requirement_set_id="r", intent="lookup"))
        monkeypatch.setattr(subject, "assess_evidence", lambda *a, **k: (_ for _ in ()).throw(error))
    else:
        authority = None; evidence = (SimpleNamespace(domain="parts", entity_type="other", provenance={}),)
        monkeypatch.setattr(subject, "get_requirement_set", lambda _: SimpleNamespace(requirement_set_id="r", intent="lookup"))
        monkeypatch.setattr(subject, "assess_evidence", lambda *a, **k: SimpleNamespace(status="sufficient"))
        monkeypatch.setattr(subject, "synthesize_grounded_evidence", lambda *a: (_ for _ in ()).throw(error))
    with pytest.raises(Fatal) as raised:
        subject.build_task_grounded_synthesis_coverage_authority_canary_p4_6e3(plan, _c(), authority, evidence)
    assert raised.value is error


def test_inputs_remain_immutable_and_e2_extension_fields_are_copied():
    extension_value = object()
    unit = _unit()
    unit["payload"] = extension_value
    task, authority_c, authority_e2 = _task(), _c(secret="C_AUTHORITY_SENTINEL"), _e2(unit)
    task_before = dict(task.__dict__)
    c_before = dict(authority_c)
    e2_before = dict(authority_e2)
    unit_before = dict(authority_e2["units"][0])
    result = subject.build_task_grounded_synthesis_coverage_authority_canary_p4_6e3(
        _plan(task), authority_c, authority_e2,
        (SimpleNamespace(secret="RAW_EVIDENCE_SENTINEL"),))
    assert task.__dict__ == task_before and authority_c == c_before and authority_e2 == e2_before
    assert authority_e2["units"][0] == unit_before
    assert result["units"][0]["payload"] is extension_value
    rendered = repr(result)
    assert "C_AUTHORITY_SENTINEL" not in rendered
    assert "RAW_EVIDENCE_SENTINEL" not in rendered
