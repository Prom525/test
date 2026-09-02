from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import app.orchestrator.product_family_evidence as family_evidence
from app.orchestrator.evidence_adapters import normalize_execution_result_evidence
from app.orchestrator.evidence_assessor import RequirementAssessmentStatus
from app.orchestrator.evidence_contracts import (
    EvidenceFreshnessStatus,
    EvidenceSourceType,
    EvidenceType,
)
from app.orchestrator.evidence_requirement_catalog import get_requirement_set


NOW = datetime(2026, 9, 2, tzinfo=timezone.utc)


def test_price_and_inventory_alias_to_live_price_stock_contract():
    for intent in ("inventory_lookup", "price_lookup", "price_stock"):
        requirement_set = get_requirement_set(intent)
        assert requirement_set is not None
        assert requirement_set.requirement_set_id == "price_stock.v1"
        assert [r.requirement_id for r in requirement_set.requirements] == [
            "CURRENT_PRICE", "CURRENT_STOCK"
        ]


def test_config_options_normalizes_explicit_live_price_and_stock():
    execution = SimpleNamespace(
        step_id="product-PROLOAD",
        action="product_assistant",
        domain="product",
        result={
            "status": "ok",
            "detected_family_code": "PROLOAD",
            "family_context": {"status": "ok", "results": []},
            "config_options": {
                "source_view": "vw_product_options_live",
                "results": [{
                    "internal_ref": "PL-100",
                    "product_name": "Proload 100",
                    "sale_price": 1250.0,
                    "currency": "EUR",
                    "available_qty": 4,
                    "expected_qty": 2,
                    "uom": "stuks",
                }],
            },
        },
    )
    items = normalize_execution_result_evidence(execution, retrieved_at=NOW)
    live = [item for item in items if item.source_type is EvidenceSourceType.LIVE_CANONICAL]
    assert [item.evidence_type for item in live] == [EvidenceType.RECORD, EvidenceType.STATUS]
    assert {item.entity_id for item in live} == {"PROLOAD"}
    assert all(item.freshness_status is EvidenceFreshnessStatus.CURRENT for item in live)
    assert {item.claim_scope for item in live} == {("CURRENT_PRICE",), ("CURRENT_STOCK",)}


def test_document_or_missing_fields_never_become_price_stock_evidence():
    execution = SimpleNamespace(
        step_id="product-BB-U", action="product_assistant", domain="product",
        result={
            "status": "ok", "detected_family_code": "BB-U",
            "family_context": {"status": "ok", "results": []},
            "rag_context": {"status": "ok", "text": "price 10 stock 99"},
            "config_options": {"results": [{"internal_ref": "BB-U-1"}]},
        },
    )
    items = normalize_execution_result_evidence(execution, retrieved_at=NOW)
    assert not [item for item in items if item.source_type is EvidenceSourceType.LIVE_CANONICAL]


def test_price_stock_coverage_requires_both_requirements_per_family(monkeypatch):
    requirement_set = get_requirement_set("inventory_lookup")
    plan = SimpleNamespace(product_families=["PROM-TPH-HD", "BB-U", "PROLOAD"])
    calls = []
    def fake_assess(_set, _items, *, target_entity_ids=None, now=None):
        family = target_entity_ids["product"]
        calls.append(family)
        return SimpleNamespace(requirement_results=tuple(
            SimpleNamespace(
                requirement_id=requirement_id,
                status=(RequirementAssessmentStatus.MISSING
                        if family == "PROLOAD" and requirement_id == "CURRENT_STOCK"
                        else RequirementAssessmentStatus.SATISFIED),
                matched_evidence_ids=(f"{family}:{requirement_id}",),
                reasons=(),
            )
            for requirement_id in ("CURRENT_PRICE", "CURRENT_STOCK")
        ))
    monkeypatch.setattr(family_evidence, "assess_evidence", fake_assess)
    coverage = family_evidence.assess_product_family_coverage(
        requirement_set, (), plan, now=NOW
    )
    assert calls == ["PROM-TPH-HD", "BB-U", "PROLOAD"]
    assert coverage["missing_family_codes"] == ["PROLOAD"]
    assert coverage["required_requirement_ids"] == ["CURRENT_PRICE", "CURRENT_STOCK"]
    assert coverage["all_satisfied"] is False


def test_existing_grounded_synthesizer_remains_service_output_path():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "app/orchestrator/service.py").read_text(
        encoding="utf-8-sig"
    )
    assert "synthesize_grounded_evidence," in source
    assert source.index("assess_product_family_coverage(") < source.index(
        "synthesize_grounded_evidence,", source.index("recover_missing_product_families(")
    )
