from __future__ import annotations

import copy
import unittest
from datetime import datetime, timezone

from app.orchestrator.evidence_adapters import (
    normalize_execution_result_evidence,
)
from app.orchestrator.evidence_contracts import (
    EVIDENCE_CONTRACT_VERSION,
    EvidenceDirectness,
    EvidenceFreshnessStatus,
    EvidenceGroundingStatus,
    EvidenceQualityStatus,
    EvidenceSourceType,
    EvidenceType,
)
from app.orchestrator.execution_contracts import (
    EXECUTION_CONTRACT_VERSION,
    ExecutionOutcome,
    ExecutionResult,
    ExecutionTransportState,
)


RETRIEVED_AT = datetime(
    2026,
    8,
    27,
    13,
    45,
    tzinfo=timezone.utc,
)


def _technical_result():
    return {
        "status": "ok",
        "technical_context": {
            "status": "ok",
            "source_code": "CEMA",
            "results": [
                {
                    "item_id": "CEMA-001",
                    "item_type": "definition",
                    "title": "CEMA definition",
                    "summary_nl": (
                        "Conveyor Equipment Manufacturers "
                        "Association"
                    ),
                    "source_code": "CEMA",
                    "source_title": "CEMA reference",
                    "page_start": 1,
                    "page_end": 1,
                    "structured_data": None,
                },
                {
                    "item_id": "CEMA-002",
                    "item_type": "table",
                    "title": "Capacity table",
                    "summary_nl": "Controlled capacity data",
                    "source_code": "CEMA",
                    "source_title": "CEMA reference",
                    "page_start": 20,
                    "page_end": 21,
                    "structured_data": {
                        "table_type": "capacity",
                    },
                },
            ],
        },
        "rag_context": {
            "used_context": [
                {
                    "doc_id": "rag-ignored-in-this-adapter",
                    "text": "Broad RAG context",
                }
            ]
        },
    }


def _execution_result(
    *,
    action="technical_assistant",
    result=None,
):
    if result is None:
        result = _technical_result()

    return ExecutionResult(
        contract_version=EXECUTION_CONTRACT_VERSION,
        step_id="step-technical-001",
        action=action,
        domain="technical",
        endpoint="/technical/assistant/ask",
        transport_state=ExecutionTransportState.COMPLETED,
        semantic_outcome=ExecutionOutcome.SUCCESS,
        specialist_status="ok",
        legacy_accepted=True,
        result=result,
        error=None,
        attempt_count=1,
        duration_ms=25,
        evidence_metadata=None,
        provenance_metadata=None,
    )


class TechnicalEvidenceAdapterV1Tests(
    unittest.TestCase
):
    def test_structured_results_normalize_deterministically(self):
        execution_result = _execution_result()

        first = normalize_execution_result_evidence(
            execution_result,
            retrieved_at=RETRIEVED_AT,
        )

        second = normalize_execution_result_evidence(
            execution_result,
            retrieved_at=RETRIEVED_AT,
        )

        self.assertIsInstance(first, tuple)
        self.assertEqual(len(first), 2)

        self.assertEqual(
            tuple(item.evidence_id for item in first),
            tuple(item.evidence_id for item in second),
        )

        item = first[0]

        self.assertEqual(
            item.contract_version,
            EVIDENCE_CONTRACT_VERSION,
        )
        self.assertEqual(
            item.execution_step_id,
            "step-technical-001",
        )
        self.assertEqual(
            item.specialist_id,
            "technical_assistant",
        )
        self.assertEqual(item.domain, "technical")
        self.assertEqual(item.subject, "CEMA definition")
        self.assertEqual(item.entity_type, "technical_item")
        self.assertEqual(item.entity_id, "CEMA-001")
        self.assertEqual(
            item.evidence_type,
            EvidenceType.RECORD,
        )
        self.assertEqual(
            item.source_type,
            EvidenceSourceType.STRUCTURED_KNOWLEDGE,
        )
        self.assertEqual(item.source_name, "CEMA")
        self.assertEqual(
            item.source_reference,
            "CEMA:CEMA-001",
        )
        self.assertIsNone(item.source_priority)
        self.assertIsNone(item.observed_at)
        self.assertEqual(item.retrieved_at, RETRIEVED_AT)
        self.assertIsNone(item.effective_at)
        self.assertIsNone(item.unit)
        self.assertEqual(item.claim_scope, ())
        self.assertEqual(
            item.freshness_status,
            EvidenceFreshnessStatus.
            NOT_APPLICABLE,
        )
        self.assertEqual(
            item.grounding_status,
            EvidenceGroundingStatus.GROUNDED,
        )
        self.assertEqual(
            item.quality_status,
            EvidenceQualityStatus.VALID,
        )
        self.assertEqual(
            item.direct_or_derived,
            EvidenceDirectness.DIRECT,
        )
        self.assertIsNone(item.derivation_reference)

        self.assertEqual(
            item.provenance,
            {
                "source_code": "CEMA",
                "source_title": "CEMA reference",
                "page_start": 1,
                "page_end": 1,
            },
        )

    def test_raw_value_is_preserved(self):
        execution_result = _execution_result()

        evidence = normalize_execution_result_evidence(
            execution_result,
            retrieved_at=RETRIEVED_AT,
        )

        self.assertEqual(
            evidence[0].value,
            execution_result.result[
                "technical_context"
            ]["results"][0],
        )

    def test_adapter_does_not_mutate_execution_result(self):
        execution_result = _execution_result()
        original_result = copy.deepcopy(
            execution_result.result
        )

        normalize_execution_result_evidence(
            execution_result,
            retrieved_at=RETRIEVED_AT,
        )

        self.assertEqual(
            execution_result.result,
            original_result,
        )

    def test_evidence_value_is_detached_from_raw_result(self):
        execution_result = _execution_result()

        evidence = normalize_execution_result_evidence(
            execution_result,
            retrieved_at=RETRIEVED_AT,
        )

        evidence[0].value["summary_nl"] = "changed"

        self.assertNotEqual(
            evidence[0].value["summary_nl"],
            execution_result.result[
                "technical_context"
            ]["results"][0]["summary_nl"],
        )

    def test_missing_results_yields_empty_tuple(self):
        execution_result = _execution_result(
            result={
                "status": "ok",
                "technical_context": {
                    "status": "ok",
                    "results": None,
                },
            }
        )

        self.assertEqual(
            normalize_execution_result_evidence(
                execution_result,
                retrieved_at=RETRIEVED_AT,
            ),
            (),
        )

    def test_other_specialists_are_not_guessed(self):
        execution_result = _execution_result(
            action="analysis_assistant",
        )

        self.assertEqual(
            normalize_execution_result_evidence(
                execution_result,
                retrieved_at=RETRIEVED_AT,
            ),
            (),
        )

    def test_rag_context_is_not_silently_selected(self):
        execution_result = _execution_result()

        evidence = normalize_execution_result_evidence(
            execution_result,
            retrieved_at=RETRIEVED_AT,
        )

        self.assertEqual(len(evidence), 2)
        self.assertTrue(
            all(
                item.source_type
                is EvidenceSourceType.STRUCTURED_KNOWLEDGE
                for item in evidence
            )
        )




def _product_execution_result(
    *,
    result=None,
):
    if result is None:
        result = {
            "status": "ok",
            "article_search_v2": {
                "status": "ok",
                "source_view": "product_article_view",
                "results": [
                    {
                        "stg_article_id": 101,
                        "internal_ref": "ABUBL1800",
                        "product_name": "U1800 blade",
                        "family_code": "U1800",
                        "family_name": "U1800",
                        "sale_price": 125.50,
                        "available_qty": 4,
                        "expected_qty": 2,
                        "uom": "pcs",
                    },
                    {
                        "stg_article_id": 102,
                        "internal_ref": "ABUHD1800",
                        "product_name": "U1800 holder",
                        "family_code": "U1800",
                        "family_name": "U1800",
                        "sale_price": 80.00,
                        "available_qty": 0,
                        "expected_qty": 5,
                        "uom": "pcs",
                    },
                ],
            },
            "family_context": {
                "results": [
                    {
                        "family_code": "U1800",
                        "short_description": "Not selected here",
                    }
                ]
            },
            "rag_context": {
                "used_context": [
                    {
                        "doc_id": "product-rag-ignored",
                        "text": "Not selected here",
                    }
                ]
            },
            "config_options": {
                "results": [
                    {
                        "internal_ref": "config-ignored",
                    }
                ]
            },
        }

    return ExecutionResult(
        contract_version=EXECUTION_CONTRACT_VERSION,
        step_id="step-product-001",
        action="product_assistant",
        domain="product",
        endpoint="/product/assistant/ask",
        transport_state=ExecutionTransportState.COMPLETED,
        semantic_outcome=ExecutionOutcome.SUCCESS,
        specialist_status="ok",
        legacy_accepted=True,
        result=result,
        error=None,
        attempt_count=1,
        duration_ms=30,
        evidence_metadata=None,
        provenance_metadata=None,
    )


class ProductArticleEvidenceAdapterV1Tests(
    unittest.TestCase
):
    def test_article_records_are_normalized(self):
        execution_result = (
            _product_execution_result()
        )

        evidence = (
            normalize_execution_result_evidence(
                execution_result,
                retrieved_at=RETRIEVED_AT,
            )
        )

        self.assertIsInstance(evidence, tuple)
        self.assertEqual(len(evidence), 2)

        item = evidence[0]

        self.assertEqual(
            item.execution_step_id,
            "step-product-001",
        )
        self.assertEqual(
            item.specialist_id,
            "product_assistant",
        )
        self.assertEqual(item.domain, "product")
        self.assertEqual(
            item.subject,
            "U1800 blade",
        )
        self.assertEqual(
            item.entity_type,
            "product_article",
        )
        self.assertEqual(
            item.entity_id,
            "ABUBL1800",
        )
        self.assertEqual(
            item.evidence_type,
            EvidenceType.RECORD,
        )
        self.assertEqual(
            item.source_type,
            EvidenceSourceType.LIVE_CANONICAL,
        )
        self.assertEqual(
            item.source_name,
            "product_article_view",
        )
        self.assertEqual(
            item.source_reference,
            "product_article_view:ABUBL1800",
        )
        self.assertIsNone(item.source_priority)
        self.assertIsNone(item.observed_at)
        self.assertEqual(
            item.retrieved_at,
            RETRIEVED_AT,
        )
        self.assertIsNone(item.effective_at)
        self.assertIsNone(item.unit)
        self.assertEqual(item.claim_scope, ())
        self.assertEqual(
            item.freshness_status,
            EvidenceFreshnessStatus.UNKNOWN,
        )
        self.assertEqual(
            item.grounding_status,
            EvidenceGroundingStatus.GROUNDED,
        )
        self.assertEqual(
            item.quality_status,
            EvidenceQualityStatus.UNKNOWN,
        )
        self.assertEqual(
            item.direct_or_derived,
            EvidenceDirectness.DIRECT,
        )
        self.assertEqual(
            item.provenance,
            {
                "source_view": "product_article_view",
                "stg_article_id": 101,
                "family_code": "U1800",
            },
        )

    def test_product_ids_are_deterministic(self):
        execution_result = (
            _product_execution_result()
        )

        first = normalize_execution_result_evidence(
            execution_result,
            retrieved_at=RETRIEVED_AT,
        )

        second = normalize_execution_result_evidence(
            execution_result,
            retrieved_at=RETRIEVED_AT,
        )

        self.assertEqual(
            tuple(item.evidence_id for item in first),
            tuple(item.evidence_id for item in second),
        )

    def test_product_value_is_detached(self):
        execution_result = (
            _product_execution_result()
        )

        evidence = (
            normalize_execution_result_evidence(
                execution_result,
                retrieved_at=RETRIEVED_AT,
            )
        )

        evidence[0].value["sale_price"] = 999

        self.assertEqual(
            execution_result.result[
                "article_search_v2"
            ]["results"][0]["sale_price"],
            125.50,
        )

    def test_missing_article_results_is_empty(self):
        execution_result = (
            _product_execution_result(
                result={
                    "status": "ok",
                    "article_search_v2": {
                        "status": "ok",
                        "source_view": (
                            "product_article_view"
                        ),
                        "results": None,
                    },
                }
            )
        )

        self.assertEqual(
            normalize_execution_result_evidence(
                execution_result,
                retrieved_at=RETRIEVED_AT,
            ),
            (),
        )



def _analysis_execution_result(
    *,
    result=None,
):
    if result is None:
        result = {
            "laatste_meshoogte": [
                {
                    "canonical_inspection_key": (
                        "A319:WEST:U1800"
                    ),
                    "band_norm": "A319",
                    "position_hint": "WEST",
                    "scraper_type_norm": "U1800",
                    "meshoogte_mm": 5.0,
                    "laatste_meting_datum": (
                        "2026-08-01"
                    ),
                    "source_file": "inspection.xlsx",
                    "sheet_raw": "A319",
                    "sheet_analysis_key": (
                        "analysis:A319:WEST"
                    ),
                    "sheet_instance_key": (
                        "instance:A319:WEST"
                    ),
                },
                {
                    "canonical_inspection_key": (
                        "A319:EAST:U1800"
                    ),
                    "band_norm": "A319",
                    "position_hint": "EAST",
                    "scraper_type_norm": "U1800",
                    "meshoogte_mm": 7.0,
                    "laatste_meting_datum": (
                        "2026-08-02T10:30:00+00:00"
                    ),
                    "source_file": "inspection.xlsx",
                    "sheet_raw": "A319",
                    "sheet_analysis_key": (
                        "analysis:A319:EAST"
                    ),
                    "sheet_instance_key": (
                        "instance:A319:EAST"
                    ),
                },
            ],
            "lifecycle": [
                {
                    "canonical_inspection_key": (
                        "lifecycle-must-not-be-selected"
                    ),
                    "meshoogte_mm": 10.0,
                }
            ],
            "forecast_3mm": [
                {
                    "geschatte_vervangdatum_bij_3mm": (
                        "2027-01-01"
                    )
                }
            ],
        }

    return ExecutionResult(
        contract_version=EXECUTION_CONTRACT_VERSION,
        step_id="step-analysis-001",
        action="analysis_assistant",
        domain="inspection",
        endpoint="/analysis/assistant/ask",
        transport_state=ExecutionTransportState.COMPLETED,
        semantic_outcome=ExecutionOutcome.UNKNOWN,
        specialist_status=None,
        legacy_accepted=True,
        result=result,
        error=None,
        attempt_count=1,
        duration_ms=40,
        evidence_metadata=None,
        provenance_metadata=None,
    )


class AnalysisLatestEvidenceAdapterV1Tests(
    unittest.TestCase
):
    def test_latest_measurements_are_normalized(self):
        execution_result = (
            _analysis_execution_result()
        )

        evidence = (
            normalize_execution_result_evidence(
                execution_result,
                retrieved_at=RETRIEVED_AT,
            )
        )

        self.assertIsInstance(evidence, tuple)
        self.assertEqual(len(evidence), 2)

        item = evidence[0]

        self.assertEqual(
            item.execution_step_id,
            "step-analysis-001",
        )
        self.assertEqual(
            item.specialist_id,
            "analysis_assistant",
        )
        self.assertEqual(
            item.domain,
            "inspection",
        )
        self.assertEqual(
            item.subject,
            "latest_blade_height",
        )
        self.assertEqual(
            item.entity_type,
            "scraper_position",
        )
        self.assertEqual(
            item.entity_id,
            "A319:WEST:U1800",
        )
        self.assertEqual(
            item.evidence_type,
            EvidenceType.MEASUREMENT,
        )
        self.assertEqual(
            item.source_type,
            EvidenceSourceType.LIVE_CANONICAL,
        )
        self.assertEqual(
            item.source_name,
            "inspection.xlsx",
        )
        self.assertEqual(
            item.source_reference,
            "A319:WEST:U1800",
        )
        self.assertEqual(
            item.observed_at,
            datetime(2026, 8, 1),
        )
        self.assertEqual(
            item.retrieved_at,
            RETRIEVED_AT,
        )
        self.assertIsNone(item.effective_at)
        self.assertEqual(item.unit, "mm")
        self.assertEqual(item.claim_scope, ())
        self.assertEqual(
            item.freshness_status,
            EvidenceFreshnessStatus.UNKNOWN,
        )
        self.assertEqual(
            item.grounding_status,
            EvidenceGroundingStatus.GROUNDED,
        )
        self.assertEqual(
            item.quality_status,
            EvidenceQualityStatus.UNKNOWN,
        )
        self.assertEqual(
            item.direct_or_derived,
            EvidenceDirectness.DIRECT,
        )
        self.assertEqual(
            item.provenance,
            {
                "source_file": "inspection.xlsx",
                "sheet_raw": "A319",
                "sheet_analysis_key": (
                    "analysis:A319:WEST"
                ),
                "sheet_instance_key": (
                    "instance:A319:WEST"
                ),
                "observed_at_raw": "2026-08-01",
            },
        )

    def test_offset_timestamp_is_preserved(self):
        evidence = (
            normalize_execution_result_evidence(
                _analysis_execution_result(),
                retrieved_at=RETRIEVED_AT,
            )
        )

        self.assertEqual(
            evidence[1].observed_at,
            datetime.fromisoformat(
                "2026-08-02T10:30:00+00:00"
            ),
        )

    def test_invalid_observed_date_remains_unknown(self):
        execution_result = (
            _analysis_execution_result(
                result={
                    "laatste_meshoogte": [
                        {
                            "canonical_inspection_key": (
                                "A319:UNKNOWN"
                            ),
                            "meshoogte_mm": 5.0,
                            "laatste_meting_datum": (
                                "not-a-date"
                            ),
                        }
                    ]
                }
            )
        )

        evidence = (
            normalize_execution_result_evidence(
                execution_result,
                retrieved_at=RETRIEVED_AT,
            )
        )

        self.assertEqual(len(evidence), 1)
        self.assertIsNone(
            evidence[0].observed_at
        )
        self.assertEqual(
            evidence[0].freshness_status,
            EvidenceFreshnessStatus.UNKNOWN,
        )

    def test_analysis_value_is_detached(self):
        execution_result = (
            _analysis_execution_result()
        )

        evidence = (
            normalize_execution_result_evidence(
                execution_result,
                retrieved_at=RETRIEVED_AT,
            )
        )

        evidence[0].value["meshoogte_mm"] = 999

        self.assertEqual(
            execution_result.result[
                "laatste_meshoogte"
            ][0]["meshoogte_mm"],
            5.0,
        )

    def test_missing_latest_measurements_is_empty(self):
        execution_result = (
            _analysis_execution_result(
                result={
                    "laatste_meshoogte": None,
                    "lifecycle": [
                        {
                            "meshoogte_mm": 8.0,
                        }
                    ],
                }
            )
        )

        self.assertEqual(
            normalize_execution_result_evidence(
                execution_result,
                retrieved_at=RETRIEVED_AT,
            ),
            (),
        )



def _rfq_execution_result(
    *,
    result=None,
):
    if result is None:
        result = {
            "status": "ok",
            "source_route": "rfq_backend",
            "result": {
                "status": "ok",
                "type": "rfq_list",
                "rfqs": [
                    {
                        "rfq_id": "RFQ-001",
                        "odoo_reference": "ODOO-1001",
                        "status": "open",
                        "commercial_status": None,
                        "created_at": (
                            "2026-08-01T08:00:00+00:00"
                        ),
                        "updated_at": (
                            "2026-08-27T12:00:00+00:00"
                        ),
                        "position_count": 3,
                        "received_count": 1,
                        "supplier_rfq_count": 2,
                        "selected_route": "rfq_backend",
                    },
                    {
                        "rfq_id": "RFQ-002",
                        "odoo_reference": "ODOO-1002",
                        "status": "draft",
                        "commercial_status": "pending",
                        "created_at": "2026-08-20",
                        "updated_at": "2026-08-26",
                        "position_count": 1,
                        "received_count": 0,
                        "supplier_rfq_count": 0,
                        "selected_route": "rfq_backend",
                    },
                ],
            },
        }

    return ExecutionResult(
        contract_version=EXECUTION_CONTRACT_VERSION,
        step_id="step-rfq-001",
        action="rfq_assistant",
        domain="rfq",
        endpoint="/rfq/assistant/ask",
        transport_state=ExecutionTransportState.COMPLETED,
        semantic_outcome=ExecutionOutcome.UNKNOWN,
        specialist_status="ok",
        legacy_accepted=True,
        result=result,
        error=None,
        attempt_count=1,
        duration_ms=20,
        evidence_metadata=None,
        provenance_metadata=None,
    )


class RfqEvidenceAdapterV1Tests(
    unittest.TestCase
):
    def test_rfq_records_are_normalized(self):
        evidence = (
            normalize_execution_result_evidence(
                _rfq_execution_result(),
                retrieved_at=RETRIEVED_AT,
            )
        )

        self.assertIsInstance(evidence, tuple)
        self.assertEqual(len(evidence), 2)

        item = evidence[0]

        self.assertEqual(
            item.execution_step_id,
            "step-rfq-001",
        )
        self.assertEqual(
            item.specialist_id,
            "rfq_assistant",
        )
        self.assertEqual(item.domain, "rfq")
        self.assertEqual(item.subject, "rfq_status")
        self.assertEqual(item.entity_type, "rfq")
        self.assertEqual(item.entity_id, "RFQ-001")
        self.assertEqual(
            item.evidence_type,
            EvidenceType.STATUS,
        )
        self.assertEqual(
            item.source_type,
            EvidenceSourceType.SPECIALIST_RESULT,
        )
        self.assertEqual(
            item.source_name,
            "rfq_backend",
        )
        self.assertEqual(
            item.source_reference,
            "RFQ-001",
        )
        self.assertIsNone(item.source_priority)
        self.assertEqual(
            item.observed_at,
            datetime.fromisoformat(
                "2026-08-27T12:00:00+00:00"
            ),
        )
        self.assertEqual(
            item.retrieved_at,
            RETRIEVED_AT,
        )
        self.assertIsNone(item.effective_at)
        self.assertIsNone(item.unit)
        self.assertEqual(item.claim_scope, ())
        self.assertEqual(
            item.freshness_status,
            EvidenceFreshnessStatus.UNKNOWN,
        )
        self.assertEqual(
            item.grounding_status,
            EvidenceGroundingStatus.GROUNDED,
        )
        self.assertEqual(
            item.quality_status,
            EvidenceQualityStatus.UNKNOWN,
        )
        self.assertEqual(
            item.direct_or_derived,
            EvidenceDirectness.DIRECT,
        )
        self.assertEqual(
            item.provenance,
            {
                "source_route": "rfq_backend",
                "selected_route": "rfq_backend",
                "odoo_reference": "ODOO-1001",
                "created_at_raw": (
                    "2026-08-01T08:00:00+00:00"
                ),
                "updated_at_raw": (
                    "2026-08-27T12:00:00+00:00"
                ),
            },
        )

    def test_rfq_status_is_preserved_not_interpreted(self):
        evidence = (
            normalize_execution_result_evidence(
                _rfq_execution_result(),
                retrieved_at=RETRIEVED_AT,
            )
        )

        self.assertEqual(
            evidence[0].value["status"],
            "open",
        )
        self.assertEqual(
            evidence[0].quality_status,
            EvidenceQualityStatus.UNKNOWN,
        )
        self.assertEqual(
            evidence[0].claim_scope,
            (),
        )

    def test_rfq_ids_are_deterministic(self):
        execution_result = (
            _rfq_execution_result()
        )

        first = normalize_execution_result_evidence(
            execution_result,
            retrieved_at=RETRIEVED_AT,
        )

        second = normalize_execution_result_evidence(
            execution_result,
            retrieved_at=RETRIEVED_AT,
        )

        self.assertEqual(
            tuple(item.evidence_id for item in first),
            tuple(item.evidence_id for item in second),
        )

    def test_invalid_rfq_timestamp_remains_unknown(self):
        evidence = (
            normalize_execution_result_evidence(
                _rfq_execution_result(
                    result={
                        "status": "ok",
                        "source_route": "rfq_backend",
                        "result": {
                            "rfqs": [
                                {
                                    "rfq_id": "RFQ-X",
                                    "updated_at": (
                                        "not-a-date"
                                    ),
                                }
                            ]
                        },
                    }
                ),
                retrieved_at=RETRIEVED_AT,
            )
        )

        self.assertEqual(len(evidence), 1)
        self.assertIsNone(
            evidence[0].observed_at
        )
        self.assertEqual(
            evidence[0].freshness_status,
            EvidenceFreshnessStatus.UNKNOWN,
        )

    def test_rfq_value_is_detached(self):
        execution_result = (
            _rfq_execution_result()
        )

        evidence = (
            normalize_execution_result_evidence(
                execution_result,
                retrieved_at=RETRIEVED_AT,
            )
        )

        evidence[0].value["status"] = "changed"

        self.assertEqual(
            execution_result.result[
                "result"
            ]["rfqs"][0]["status"],
            "open",
        )

    def test_missing_rfq_list_is_empty(self):
        execution_result = (
            _rfq_execution_result(
                result={
                    "status": "ok",
                    "source_route": "rfq_backend",
                    "result": {
                        "rfqs": None,
                    },
                }
            )
        )

        self.assertEqual(
            normalize_execution_result_evidence(
                execution_result,
                retrieved_at=RETRIEVED_AT,
            ),
            (),
        )



def _org_execution_result(
    *,
    result=None,
):
    if result is None:
        result = {
            "status": "ok",
            "source_route": "org_backend",
            "result": {
                "status": "ok",
                "person_name": "Aaron Thys",
                "results": [
                    {
                        "person_id": 42,
                        "persoon_functie_id": 4201,
                        "weergavenaam": "Aaron Thys",
                        "functie_code": "IT_MANAGER",
                        "functie_naam": "IT Manager",
                        "officiele_functienaam": (
                            "IT Manager"
                        ),
                        "primair": True,
                        "geldig_vanaf": None,
                        "geldig_tot": None,
                        "bron_doc_id": "ORG-DOC-001",
                        "email": "aaron@example.test",
                        "afdeling": "IT",
                    }
                ],
            },
        }

    return ExecutionResult(
        contract_version=EXECUTION_CONTRACT_VERSION,
        step_id="step-org-001",
        action="org_assistant",
        domain="org",
        endpoint="/org/assistant/ask",
        transport_state=ExecutionTransportState.COMPLETED,
        semantic_outcome=ExecutionOutcome.UNKNOWN,
        specialist_status="ok",
        legacy_accepted=True,
        result=result,
        error=None,
        attempt_count=1,
        duration_ms=15,
        evidence_metadata=None,
        provenance_metadata=None,
    )


class OrgEvidenceAdapterV1Tests(
    unittest.TestCase
):
    def test_org_records_are_normalized(self):
        evidence = (
            normalize_execution_result_evidence(
                _org_execution_result(),
                retrieved_at=RETRIEVED_AT,
            )
        )

        self.assertIsInstance(evidence, tuple)
        self.assertEqual(len(evidence), 1)

        item = evidence[0]

        self.assertEqual(
            item.execution_step_id,
            "step-org-001",
        )
        self.assertEqual(
            item.specialist_id,
            "org_assistant",
        )
        self.assertEqual(item.domain, "org")
        self.assertEqual(
            item.subject,
            "Aaron Thys",
        )
        self.assertEqual(
            item.entity_type,
            "person_role",
        )
        self.assertEqual(item.entity_id, "42")
        self.assertEqual(
            item.evidence_type,
            EvidenceType.RECORD,
        )
        self.assertEqual(
            item.source_type,
            EvidenceSourceType.SPECIALIST_RESULT,
        )
        self.assertEqual(
            item.source_name,
            "org_backend",
        )
        self.assertEqual(
            item.source_reference,
            "42",
        )
        self.assertIsNone(item.source_priority)
        self.assertIsNone(item.observed_at)
        self.assertEqual(
            item.retrieved_at,
            RETRIEVED_AT,
        )
        self.assertIsNone(item.effective_at)
        self.assertIsNone(item.unit)
        self.assertEqual(item.claim_scope, ())
        self.assertEqual(
            item.freshness_status,
            EvidenceFreshnessStatus.UNKNOWN,
        )
        self.assertEqual(
            item.grounding_status,
            EvidenceGroundingStatus.GROUNDED,
        )
        self.assertEqual(
            item.quality_status,
            EvidenceQualityStatus.UNKNOWN,
        )
        self.assertEqual(
            item.direct_or_derived,
            EvidenceDirectness.DIRECT,
        )
        self.assertEqual(
            item.provenance,
            {
                "source_route": "org_backend",
                "bron_doc_id": "ORG-DOC-001",
                "persoon_functie_id": 4201,
                "functie_code": "IT_MANAGER",
                "geldig_vanaf_raw": None,
                "geldig_tot_raw": None,
            },
        )

    def test_null_validity_does_not_imply_current(self):
        evidence = (
            normalize_execution_result_evidence(
                _org_execution_result(),
                retrieved_at=RETRIEVED_AT,
            )
        )

        self.assertIsNone(
            evidence[0].effective_at
        )
        self.assertEqual(
            evidence[0].freshness_status,
            EvidenceFreshnessStatus.UNKNOWN,
        )
        self.assertEqual(
            evidence[0].quality_status,
            EvidenceQualityStatus.UNKNOWN,
        )
        self.assertEqual(
            evidence[0].claim_scope,
            (),
        )

    def test_valid_from_is_normalized_as_effective_at(self):
        evidence = (
            normalize_execution_result_evidence(
                _org_execution_result(
                    result={
                        "status": "ok",
                        "source_route": "org_backend",
                        "result": {
                            "results": [
                                {
                                    "person_id": 43,
                                    "weergavenaam": (
                                        "Test Person"
                                    ),
                                    "geldig_vanaf": (
                                        "2026-01-15"
                                    ),
                                    "geldig_tot": None,
                                }
                            ]
                        },
                    }
                ),
                retrieved_at=RETRIEVED_AT,
            )
        )

        self.assertEqual(len(evidence), 1)
        self.assertEqual(
            evidence[0].effective_at,
            datetime(2026, 1, 15),
        )
        self.assertEqual(
            evidence[0].freshness_status,
            EvidenceFreshnessStatus.UNKNOWN,
        )

    def test_org_value_is_detached(self):
        execution_result = (
            _org_execution_result()
        )

        evidence = (
            normalize_execution_result_evidence(
                execution_result,
                retrieved_at=RETRIEVED_AT,
            )
        )

        evidence[0].value["functie_code"] = (
            "CHANGED"
        )

        self.assertEqual(
            execution_result.result[
                "result"
            ]["results"][0]["functie_code"],
            "IT_MANAGER",
        )

    def test_missing_org_results_is_empty(self):
        execution_result = (
            _org_execution_result(
                result={
                    "status": "ok",
                    "source_route": "org_backend",
                    "result": {
                        "results": None,
                    },
                }
            )
        )

        self.assertEqual(
            normalize_execution_result_evidence(
                execution_result,
                retrieved_at=RETRIEVED_AT,
            ),
            (),
        )



def _diagnostics_execution_result(
    *,
    result=None,
):
    if result is None:
        result = {
            "status": "ok",
            "domain": "inspection",
            "topic": "data_quality",
            "mode": "overview",
            "evidence": {
                "source_tables": [
                    "inspection",
                    "inspection_item",
                ],
            },
            "summary": {
                "total_inspections": 100,
                "total_inspection_items": 250,
                "inspections_without_items": 2,
                "orphan_items": 1,
            },
            "findings": [
                {
                    "finding_id": "F-001",
                    "title": "Orphan inspection item",
                    "severity": "medium",
                    "count": 1,
                }
            ],
            "limitations": [
                "No external source validation",
            ],
            "recommended_actions": [
                "Review orphan item",
            ],
        }

    return ExecutionResult(
        contract_version=EXECUTION_CONTRACT_VERSION,
        step_id="step-diagnostics-001",
        action="diagnostics_assistant",
        domain="diagnostics",
        endpoint="/diagnostics/assistant/ask",
        transport_state=ExecutionTransportState.COMPLETED,
        semantic_outcome=ExecutionOutcome.UNKNOWN,
        specialist_status="ok",
        legacy_accepted=True,
        result=result,
        error=None,
        attempt_count=1,
        duration_ms=18,
        evidence_metadata=None,
        provenance_metadata=None,
    )


class DiagnosticsEvidenceAdapterV1Tests(
    unittest.TestCase
):
    def test_summary_and_findings_are_normalized(self):
        evidence = (
            normalize_execution_result_evidence(
                _diagnostics_execution_result(),
                retrieved_at=RETRIEVED_AT,
            )
        )

        self.assertIsInstance(evidence, tuple)
        self.assertEqual(len(evidence), 2)

        summary_item = evidence[0]
        finding_item = evidence[1]

        self.assertEqual(
            summary_item.subject,
            "diagnostic_summary",
        )
        self.assertEqual(
            summary_item.entity_type,
            "diagnostic_scope",
        )
        self.assertEqual(
            summary_item.entity_id,
            "inspection:data_quality:overview",
        )
        self.assertEqual(
            summary_item.evidence_type,
            EvidenceType.RECORD,
        )
        self.assertEqual(
            summary_item.source_type,
            EvidenceSourceType.DIAGNOSTIC,
        )
        self.assertEqual(
            summary_item.source_name,
            "diagnostics_assistant",
        )
        self.assertEqual(
            summary_item.source_reference,
            "inspection:data_quality:overview",
        )
        self.assertEqual(
            summary_item.grounding_status,
            EvidenceGroundingStatus.PARTIAL,
        )
        self.assertEqual(
            summary_item.direct_or_derived,
            EvidenceDirectness.UNKNOWN,
        )

        self.assertEqual(
            finding_item.subject,
            "Orphan inspection item",
        )
        self.assertEqual(
            finding_item.entity_type,
            "diagnostic_finding",
        )
        self.assertEqual(
            finding_item.entity_id,
            "F-001",
        )
        self.assertEqual(
            finding_item.evidence_type,
            EvidenceType.DIAGNOSTIC_FINDING,
        )
        self.assertEqual(
            finding_item.grounding_status,
            EvidenceGroundingStatus.GROUNDED,
        )
        self.assertEqual(
            finding_item.direct_or_derived,
            EvidenceDirectness.UNKNOWN,
        )

    def test_diagnostics_metadata_is_explicit(self):
        evidence = (
            normalize_execution_result_evidence(
                _diagnostics_execution_result(),
                retrieved_at=RETRIEVED_AT,
            )
        )

        for item in evidence:
            self.assertIsNone(item.source_priority)
            self.assertIsNone(item.observed_at)
            self.assertEqual(
                item.retrieved_at,
                RETRIEVED_AT,
            )
            self.assertIsNone(item.effective_at)
            self.assertIsNone(item.unit)
            self.assertEqual(item.claim_scope, ())
            self.assertEqual(
                item.freshness_status,
                EvidenceFreshnessStatus.UNKNOWN,
            )
            self.assertEqual(
                item.quality_status,
                EvidenceQualityStatus.UNKNOWN,
            )
            self.assertEqual(
                item.provenance,
                {
                    "source_tables": [
                        "inspection",
                        "inspection_item",
                    ],
                    "diagnostic_status": "ok",
                    "domain": "inspection",
                    "topic": "data_quality",
                    "mode": "overview",
                },
            )

    def test_status_ok_is_not_health_evidence(self):
        execution_result = (
            _diagnostics_execution_result(
                result={
                    "status": "ok",
                    "domain": "inspection",
                    "topic": "health",
                    "mode": "overview",
                    "evidence": {
                        "source_tables": [],
                    },
                    "summary": {},
                    "findings": [],
                    "limitations": [
                        "No health sources available",
                    ],
                    "recommended_actions": [],
                }
            )
        )

        evidence = (
            normalize_execution_result_evidence(
                execution_result,
                retrieved_at=RETRIEVED_AT,
            )
        )

        self.assertEqual(len(evidence), 1)
        self.assertEqual(
            evidence[0].quality_status,
            EvidenceQualityStatus.UNKNOWN,
        )
        self.assertEqual(
            evidence[0].claim_scope,
            (),
        )
        self.assertEqual(
            evidence[0].direct_or_derived,
            EvidenceDirectness.UNKNOWN,
        )

    def test_recommendations_are_not_selected(self):
        evidence = (
            normalize_execution_result_evidence(
                _diagnostics_execution_result(),
                retrieved_at=RETRIEVED_AT,
            )
        )

        self.assertEqual(len(evidence), 2)

        self.assertTrue(
            all(
                item.evidence_type
                is not EvidenceType.CALCULATION_RESULT
                for item in evidence
            )
        )

        self.assertTrue(
            all(
                item.value
                != ["Review orphan item"]
                for item in evidence
            )
        )

    def test_diagnostics_values_are_detached(self):
        execution_result = (
            _diagnostics_execution_result()
        )

        evidence = (
            normalize_execution_result_evidence(
                execution_result,
                retrieved_at=RETRIEVED_AT,
            )
        )

        evidence[0].value[
            "total_inspections"
        ] = 999

        evidence[1].value["severity"] = "changed"

        self.assertEqual(
            execution_result.result[
                "summary"
            ]["total_inspections"],
            100,
        )
        self.assertEqual(
            execution_result.result[
                "findings"
            ][0]["severity"],
            "medium",
        )

    def test_missing_summary_and_findings_is_empty(self):
        execution_result = (
            _diagnostics_execution_result(
                result={
                    "status": "ok",
                    "domain": "inspection",
                    "topic": "data_quality",
                    "mode": "overview",
                    "evidence": {
                        "source_tables": [],
                    },
                    "summary": None,
                    "findings": None,
                }
            )
        )

        self.assertEqual(
            normalize_execution_result_evidence(
                execution_result,
                retrieved_at=RETRIEVED_AT,
            ),
            (),
        )

if __name__ == "__main__":
    unittest.main()