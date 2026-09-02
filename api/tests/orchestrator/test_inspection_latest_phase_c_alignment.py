from __future__ import annotations

from datetime import datetime, timezone

from app.orchestrator.evidence_adapters import (
    normalize_execution_result_evidence,
)
from app.orchestrator.evidence_contracts import (
    EvidenceFreshnessStatus,
    EvidenceGroundingStatus,
    EvidenceQualityStatus,
    EvidenceType,
)
from app.orchestrator.evidence_requirement_catalog import (
    get_requirement_set,
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
    29,
    12,
    0,
    tzinfo=timezone.utc,
)


def _execution_result(
    *,
    resolved: bool = True,
    include_measurement: bool = True,
    duplicate_checks: bool = True,
) -> ExecutionResult:
    latest_rows = [
        {
            "inspection_key": "TATA|A660|2026-05-05",
            "document_date": "2026-05-05",
            "line_hint": "GSL",
            "band_code": "A660",
            "locatie_raw": None,
            "scraper_type_raw": "RI 1400-1350",
            "band_width_mm": 1400,
            "meshoogte_mm": (
                5 if include_measurement else None
            ),
            "mes_vervangen": False,
            "commentaar": "",
            "check_code": "afdichting_stortpunt",
            "status": "DONE",
            "source_file": "Sinterlijn.xlsx",
            "source_name": None,
            "source_system": "excel",
            "provenance_basis": "excel_inspection_key",
        },
        {
            "inspection_key": "TATA|A660|2026-05-05",
            "document_date": "2026-05-05",
            "line_hint": "GSL",
            "band_code": "A660",
            "locatie_raw": "Kap Br.1700",
            "scraper_type_raw": "UI 140 midden",
            "band_width_mm": 1400,
            "meshoogte_mm": 6,
            "mes_vervangen": False,
            "commentaar": "",
            "check_code": "werking_schrapers",
            "status": "DONE",
            "source_file": "Sinterlijn.xlsx",
            "source_name": None,
            "source_system": "excel",
            "provenance_basis": "excel_inspection_key",
        },
    ]

    if duplicate_checks:
        latest_rows.extend(
            [
                {
                    **latest_rows[0],
                    "check_code": "band_loop_tov_trommels",
                },
                {
                    **latest_rows[1],
                    "check_code": "vervuiling_onder_band",
                },
            ]
        )

    latest_rows.append(
        {
            "inspection_key": "TATA|A660|2026-03-10",
            "document_date": "2026-03-10",
            "line_hint": "GSL",
            "band_code": "A660",
            "locatie_raw": None,
            "scraper_type_raw": "RI 1400-1350",
            "band_width_mm": 1400,
            "meshoogte_mm": 7,
            "mes_vervangen": False,
            "commentaar": "",
            "check_code": "werking_schrapers",
            "status": "DONE",
            "source_file": "Sinterlijn.xlsx",
            "source_name": None,
            "source_system": "excel",
            "provenance_basis": "excel_inspection_key",
        }
    )

    return ExecutionResult(
        contract_version=EXECUTION_CONTRACT_VERSION,
        step_id="step_1_inspection",
        action="analysis_assistant",
        domain="inspection",
        endpoint="/analysis/assistant/ask",
        transport_state=ExecutionTransportState.COMPLETED,
        semantic_outcome=ExecutionOutcome.UNKNOWN,
        specialist_status=None,
        legacy_accepted=True,
        result={
            "intent": "inspection_summary",
            "resultaat": latest_rows,
            "asset_context": {
                "customer_code": "TATA_STEEL",
                "site_code": "IJMUIDEN",
                "area_code": "GSL",
                "installation_code": "SINTER",
                "band_code": "A660",
                "band_code_norm": "A660",
            },
            "asset_resolution": {
                "status": (
                    "resolved"
                    if resolved
                    else "not_found"
                ),
                "match_count": (
                    1 if resolved else 0
                ),
                "normalized_band_code": "A660",
                "normalized_installation_code": "SINTER",
            },
        },
        error=None,
        attempt_count=1,
        duration_ms=40,
        evidence_metadata=None,
        provenance_metadata=None,
    )


def _evidence(**kwargs):
    return normalize_execution_result_evidence(
        _execution_result(**kwargs),
        retrieved_at=RETRIEVED_AT,
    )


def test_inspection_latest_requirement_set_exists():
    requirement_set = get_requirement_set(
        "inspection_latest"
    )

    assert requirement_set is not None
    assert (
        requirement_set.requirement_set_id
        == "inspection_latest.v1"
    )

    requirement_ids = {
        item.requirement_id
        for item in requirement_set.requirements
    }

    assert "RESOLVED_ASSET_CONTEXT" in requirement_ids
    assert "LATEST_INSPECTION_DATE" in requirement_ids
    assert (
        "LATEST_INSPECTION_MEASUREMENT"
        in requirement_ids
    )


def test_latest_measurements_are_deduplicated():
    items = _evidence()

    measurements = [
        item
        for item in items
        if item.evidence_type
        is EvidenceType.MEASUREMENT
    ]

    assert len(measurements) == 2

    heights = sorted(
        item.value["meshoogte_mm"]
        for item in measurements
    )

    assert heights == [5, 6]


def test_only_latest_date_is_used_for_measurements():
    items = _evidence()

    measurements = [
        item
        for item in items
        if item.evidence_type
        is EvidenceType.MEASUREMENT
    ]

    assert measurements

    assert {
        item.observed_at.date().isoformat()
        for item in measurements
    } == {"2026-05-05"}


def test_measurements_are_scraper_position_evidence():
    items = _evidence()

    measurements = [
        item
        for item in items
        if item.evidence_type
        is EvidenceType.MEASUREMENT
    ]

    assert measurements

    assert all(
        item.entity_type == "scraper_position"
        for item in measurements
    )

    assert all(
        item.entity_id
        for item in measurements
    )


def test_latest_measurements_are_latest_known_valid_grounded():
    items = _evidence()

    measurements = [
        item
        for item in items
        if item.evidence_type
        is EvidenceType.MEASUREMENT
    ]

    assert measurements

    assert all(
        item.freshness_status
        is EvidenceFreshnessStatus.LATEST_KNOWN
        for item in measurements
    )

    assert all(
        item.quality_status
        is EvidenceQualityStatus.VALID
        for item in measurements
    )

    assert all(
        item.grounding_status
        is EvidenceGroundingStatus.GROUNDED
        for item in measurements
    )


def test_missing_meshoogte_is_not_measurement():
    items = _evidence(
        include_measurement=False,
        duplicate_checks=False,
    )

    measurements = [
        item
        for item in items
        if item.evidence_type
        is EvidenceType.MEASUREMENT
    ]

    assert len(measurements) == 1
    assert (
        measurements[0].value["meshoogte_mm"]
        == 6
    )


def test_unresolved_asset_does_not_ground_measurements():
    items = _evidence(
        resolved=False,
    )

    measurements = [
        item
        for item in items
        if item.evidence_type
        is EvidenceType.MEASUREMENT
    ]

    assert measurements

    assert all(
        item.grounding_status
        is EvidenceGroundingStatus.UNKNOWN
        for item in measurements
    )


def test_asset_and_latest_date_evidence_are_created():
    items = _evidence()

    asset_items = [
        item
        for item in items
        if item.evidence_type
        is EvidenceType.ASSET_RESOLUTION
    ]

    date_items = [
        item
        for item in items
        if item.evidence_type is EvidenceType.EVENT
    ]

    assert len(asset_items) == 1
    assert (
        asset_items[0].entity_type
        == "conveyor_belt"
    )
    assert asset_items[0].entity_id == "A660"

    assert len(date_items) == 1
    assert (
        date_items[0].entity_type
        == "inspection"
    )
    assert (
        date_items[0].value["document_date"]
        == "2026-05-05"
    )

def test_inspection_latest_v1_has_only_core_required_requirements():
    requirement_set = get_requirement_set(
        "inspection_latest"
    )

    assert requirement_set is not None

    assert [
        item.requirement_id
        for item in requirement_set.requirements
    ] == [
        "RESOLVED_ASSET_CONTEXT",
        "LATEST_INSPECTION_DATE",
        "LATEST_INSPECTION_MEASUREMENT",
    ]