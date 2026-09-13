"""Characterize all current answer mutation points after the core return."""
from __future__ import annotations

import sys

import pytest

from app.orchestrator import response_shaping, service


def _assessment():
    return {
        "intent": "inspection_latest", "status": "sufficient",
        "missing_required_requirement_ids": [],
        "requirement_results": [
            {"requirement_id": item, "status": "satisfied"}
            for item in (
                "RESOLVED_ASSET_CONTEXT", "LATEST_INSPECTION_DATE",
                "LATEST_INSPECTION_MEASUREMENT",
            )
        ],
    }


def _cp3c_response():
    return {
        "answer": "43 actuele geregistreerde schraperposities over 19 banden",
        "query_plan": {"intent": "inspection_latest", "multi_intent": False},
        "evidence_pipeline": {
            "initial_assessment": _assessment(),
            "initial_evidence_items": [
                {"subject": "resolved_asset_context", "value": {
                    "band_code": "MV1", "installation_name": "Mengveld 1"}},
                {"subject": "latest_inspection_date", "value": {
                    "document_date": "2026-05-27"}},
                {"subject": "latest_blade_height", "value": {
                    "document_date": "2026-05-27", "measurement_count": 4,
                    "min_meshoogte_mm": 3.0, "max_meshoogte_mm": 6.0}},
            ],
        },
    }


def test_cp3c_replaces_only_single_latest_sufficient_scope_overview():
    response = _cp3c_response()
    changed = service._p4_15cp3c_apply_public_answer_repair(response)
    assert changed["answer"].startswith("Laatste inspectie voor MV1")
    assert changed["observability"]["p4_15cp3c_public_answer_replaced"] is True
    for mutate in (
        lambda value: value["query_plan"].update(
            multi_intent=True,
            intent_tasks=[{"intent": "inspection_latest"}, {"intent": "maintenance_priority"}],
        ),
        lambda value: value["evidence_pipeline"]["initial_assessment"].update(status="insufficient"),
        lambda value: value.update(answer="Reeds een laatste inspectie: 2026-05-27"),
        lambda value: value["evidence_pipeline"].update(initial_evidence_items=[]),
    ):
        candidate = _cp3c_response()
        mutate(candidate)
        assert service._p4_15cp3c_apply_public_answer_repair(candidate) is candidate


def _cp4b_response():
    raw = "latest_blade_height:\n" + ("raw evidence 3 mm\n" * 100)
    return {
        "answer": raw, "final_answer": raw, "antwoord": raw,
        "query_plan": {"intent_tasks": [
            {"intent": "inspection_latest"}, {"intent": "maintenance_priority"}]},
        "evidence_pipeline": {"initial_evidence_items": [
            {"subject": "resolved_asset_context", "value": {
                "band_code": "MV1", "installation_name": "Mengveld 1"}},
            {"subject": "latest_blade_height", "value": {
                "band_code": "MV1", "document_date": "2026-05-27",
                "measurement_count": 4, "min_meshoogte_mm": 3.0,
                "max_meshoogte_mm": 6.0}},
        ]},
    }


def test_cp4b_guard_matrix_alias_sync_and_cp3c_ownership():
    changed = service._p4_15cp4b_apply_public_answer_repair(_cp4b_response())
    assert changed["answer"] == changed["final_answer"] == changed["antwoord"]
    assert changed["p4_15cp4b_public_answer_replaced"] is True
    for mutate in (
        lambda value: value.update(answer="short answer"),
        lambda value: value.update(query_plan={"intent": "inspection_latest"}),
        lambda value: value["evidence_pipeline"].update(initial_evidence_items=[]),
        lambda value: value.update(answer="43 actuele geregistreerde schraperposities"),
    ):
        candidate = _cp4b_response()
        mutate(candidate)
        before = candidate.get("answer")
        assert service._p4_15cp4b_apply_public_answer_repair(candidate)["answer"] == before


def test_cp4f_raw_and_old_scope_paths_are_narrow_and_lazy_import(monkeypatch):
    raw = "Inspection: MV1 latest_blade_height 2026-05-27 status_3mm " + "x" * 1300
    candidate = {"answer": raw, "final_answer": raw, "evidence_pipeline": {}}
    called = []
    monkeypatch.setattr(service, "_p4_15cp4f_compose_from_raw_text",
                        lambda text: called.append(text) or "repaired")
    changed = service._p4_15cp4f_apply(candidate)
    assert changed["answer"] == changed["final_answer"] == "repaired"
    assert changed["p4_15cp4f_public_answer_replaced"] is True
    assert len(called) == 1

    called.clear()
    untouched = {"answer": "Inspection: A319 latest_blade_height 2026-05-28 " + "x" * 1300}
    assert service._p4_15cp4f_apply(untouched) is untouched
    assert called == []

    old = {"answer": "43 actuele geregistreerde schraperposities Mengveld 1"}
    changed_old = service._p4_15cp4f_apply(old)
    assert "2026-05-27" in changed_old["answer"] and "MV1" in changed_old["answer"]


def test_compact_boundary_repairs_then_calls_composer_without_cp10_cp11(monkeypatch):
    calls = []
    monkeypatch.setattr(response_shaping, "_repair_raw_mv1_inspection_answer",
                        lambda response: "boundary repair")
    def composer(candidate, fallback, **kwargs):
        calls.append((candidate, fallback, kwargs))
        return candidate, {"authoritative": False}
    monkeypatch.setattr(response_shaping, "compose_concise_public_answer", composer)
    raw = {
        "status": "ok", "answer": "raw", "trace_id": "trace-synthetic",
        "query_plan": {"domains": ["inspection"], "intent_tasks": []},
        "results": [{"accepted": True}], "evidence_pipeline": {"secret": True},
    }
    compact = response_shaping.compact_orchestrator_response(raw)
    assert calls == [("boundary repair", "boundary repair", {"response_profile": "compact"})]
    assert compact["answer"] == "boundary repair"
    assert compact["trace_id"] == "trace-synthetic"
    assert "evidence_pipeline" not in compact and "results" not in compact
    assert response_shaping.shape_orchestrator_response(raw, "debug") is raw


@pytest.mark.parametrize("marker", ["latest_blade_height:", "latest_position_measurement:"])
def test_compact_boundary_blocks_raw_markers_when_composition_fails(monkeypatch, marker):
    monkeypatch.setattr(response_shaping, "compose_mv1_inspection_answer", lambda text: None)
    compact = response_shaping.compact_orchestrator_response({
        "status": "ok", "answer": marker, "query_plan": {}, "results": []})
    assert marker not in compact["answer"]
