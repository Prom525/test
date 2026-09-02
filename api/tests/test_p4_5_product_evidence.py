from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from app.orchestrator.evidence_adapters import (
    normalize_execution_result_evidence,
)
from app.orchestrator.evidence_contracts import (
    EvidenceDirectness,
    EvidenceFreshnessStatus,
    EvidenceGroundingStatus,
    EvidenceQualityStatus,
    EvidenceSourceType,
    EvidenceType,
)


NOW = datetime(
    2026,
    9,
    2,
    tzinfo=timezone.utc,
)


def _execution(payload: dict):
    return SimpleNamespace(
        step_id="step-product-p45",
        action="product_assistant",
        domain="product",
        result=payload,
    )


def _structured_payload(
    family_code: str,
    family_name: str,
) -> dict:
    return {
        "status": "ok",
        "context_type": "product_assistant",
        "detected_family_code": family_code,
        "family_context": {
            "status": "ok",
            "context_type": (
                "product_family_context"
            ),
            "detected_family_code": (
                family_code
            ),
            "count": 1,
            "results": [
                {
                    "family_code": (
                        family_code
                    ),
                    "family_name": (
                        family_name
                    ),
                    "brand": "PROMATI",
                    "short_description": (
                        "controlled test record"
                    ),
                }
            ],
        },
        "family_document_scope": {
            "status": "ok",
            "family_code": family_code,
            "documents": [
                {
                    "doc_id": (
                        "document-only-context"
                    )
                }
            ],
        },
        "rag_context": {
            "status": "ok",
            "context_hits": [
                {
                    "text": (
                        "RAG must never become "
                        "structured product evidence"
                    )
                }
            ],
        },
        "article_search_v2": None,
    }


def _product_items(payload: dict):
    return normalize_execution_result_evidence(
        _execution(payload),
        retrieved_at=NOW,
    )


def test_tph_structured_family_becomes_product_record():
    items = _product_items(
        _structured_payload(
            "PROM-TPH-HD",
            "Promati TPH HD",
        )
    )

    assert len(items) == 1

    item = items[0]

    assert (
        item.evidence_type
        == EvidenceType.RECORD
    )
    assert (
        item.source_type
        == EvidenceSourceType.STRUCTURED_KNOWLEDGE
    )
    assert item.entity_type == "product"
    assert item.entity_id == "PROM-TPH-HD"
    assert item.subject == "Promati TPH HD"
    assert (
        item.grounding_status
        == EvidenceGroundingStatus.GROUNDED
    )
    assert (
        item.quality_status
        == EvidenceQualityStatus.VALID
    )
    assert (
        item.freshness_status
        == EvidenceFreshnessStatus.NOT_APPLICABLE
    )
    assert (
        item.direct_or_derived
        == EvidenceDirectness.DIRECT
    )


def test_bb_u_entity_identity_is_stable_family_code():
    items = _product_items(
        _structured_payload(
            "BB-U",
            "Belle Banne U",
        )
    )

    assert len(items) == 1
    item = items[0]

    assert item.entity_type == "product"
    assert item.entity_id == "BB-U"
    assert (
        item.provenance[
            "family_code"
        ]
        == "BB-U"
    )
    assert (
        item.value[
            "family_code"
        ]
        == "BB-U"
    )


def test_detected_family_mismatch_is_rejected():
    payload = _structured_payload(
        "BB-U",
        "Belle Banne U",
    )

    payload[
        "family_context"
    ][
        "results"
    ][0][
        "family_code"
    ] = "PROM-TPH-HD"

    items = _product_items(payload)

    assert items == ()


def test_document_and_rag_without_structured_row_do_not_create_record():
    payload = _structured_payload(
        "PROLOAD",
        "Proload",
    )

    payload[
        "family_context"
    ][
        "count"
    ] = 0

    payload[
        "family_context"
    ][
        "results"
    ] = []

    items = _product_items(payload)

    assert items == ()


def test_family_context_not_ok_is_rejected():
    payload = _structured_payload(
        "PROM-TPH-HD",
        "Promati TPH HD",
    )

    payload[
        "family_context"
    ][
        "status"
    ] = "error"

    items = _product_items(payload)

    assert items == ()


def test_structured_product_record_cannot_be_live_price_or_stock_evidence():
    items = _product_items(
        _structured_payload(
            "PROM-TPH-HD",
            "Promati TPH HD",
        )
    )

    assert len(items) == 1

    item = items[0]

    assert (
        item.source_type
        != EvidenceSourceType.LIVE_CANONICAL
    )
    assert (
        item.freshness_status
        == EvidenceFreshnessStatus.NOT_APPLICABLE
    )


def test_existing_article_evidence_path_remains_additive():
    payload = _structured_payload(
        "PROM-TPH-HD",
        "Promati TPH HD",
    )

    with patch(
        (
            "app.orchestrator."
            "evidence_adapters."
            "_product_article_evidence"
        ),
        return_value=(
            "ARTICLE_SENTINEL",
        ),
    ) as article_adapter:
        items = (
            normalize_execution_result_evidence(
                _execution(payload),
                retrieved_at=NOW,
            )
        )

    article_adapter.assert_called_once()

    assert len(items) == 2
    assert items[0].entity_type == "product"
    assert items[1] == "ARTICLE_SENTINEL"


def test_product_record_value_is_defensively_copied():
    payload = _structured_payload(
        "BB-U",
        "Belle Banne U",
    )

    items = _product_items(payload)

    assert len(items) == 1

    payload[
        "family_context"
    ][
        "results"
    ][0][
        "family_name"
    ] = "MUTATED"

    assert (
        items[0].value[
            "family_name"
        ]
        == "Belle Banne U"
    )
