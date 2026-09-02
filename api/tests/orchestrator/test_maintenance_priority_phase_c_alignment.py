from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

from app.orchestrator.evidence_adapters import (
    normalize_execution_result_evidence,
)
from app.orchestrator.evidence_assessor import (
    EvidenceAssessmentStatus,
    assess_evidence,
)
from app.orchestrator.evidence_contracts import (
    EvidenceDirectness,
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


NOW = datetime(
    2026,
    8,
    30,
    12,
    0,
    tzinfo=timezone.utc,
)


def _r_position():
    return {
        "lijn_code": "GSL",
        "band_norm": "A660",
        "position_hint": "POS A / SECUNDAIR",
        "scraper_types": "R 1400-1350 INOX",
        "cycle_start": "2025-03-05",
        "cycle_end": "2026-05-05",
        "meetpunten": 7,
        "avg_meshoogte_mm": None,
        "start_meshoogte_mm": 10.0,
        "eind_meshoogte_mm": 5.0,
        "slijtage_mm_per_dag": (
            0.011737089201877934
        ),
        "geschatte_dagen_tot_3mm": 170.4,
        "geschatte_vervangdatum_bij_3mm": (
            "2026-10-22"
        ),
        "status_3mm": "OK",
        "prioriteit": 4,
        "first_sheet_analysis_key": "2025-W10",
        "last_sheet_analysis_key": "2026-W19",
        "first_sheet_instance_key": "2025-03-05",
        "last_sheet_instance_key": "2026-05-05",
        "first_canonical_inspection_key": (
            "TATA_STEEL|IJMUIDEN|A660|"
            "2025-03-05"
        ),
        "last_canonical_inspection_key": (
            "TATA_STEEL|IJMUIDEN|A660|"
            "2026-05-05"
        ),
        "source_file": (
            r"C:\test\Sinterlijn.xlsx"
        ),
        "sheet_raw": "week 19",
        "dagen_sinds_laatste_meting": 117,
        "scraper_types_raw": (
            "R 1400-1350 INOX"
        ),
        "scraper_types_clean": (
            "R 1400-1350 INOX"
        ),
        "position_accessories": [],
        "prestatiegrens_mm": 6,
        "vervanggrens_mm": 3,
        "geschatte_dagen_tot_6mm": 0,
        "geschatte_datum_bij_6mm": (
            "2026-05-05"
        ),
        "dagen_tot_6mm_vanaf_vandaag": -117,
        "status_6mm": "OP_OF_ONDER_6MM",
        "vervuilingsrisico": True,
        "prestatie_vervangmoment": (
            "CONTROLEREN_PRESTATIEGRENS"
        ),
    }


def _u_position():
    return {
        "lijn_code": "GSL",
        "band_norm": "A660",
        "position_hint": (
            "POS A / SECUNDAIR / ZUID"
        ),
        "scraper_types": "U 1400 INOX",
        "cycle_start": "2023-12-05",
        "cycle_end": "2025-03-05",
        "meetpunten": 11,
        "avg_meshoogte_mm": None,
        "start_meshoogte_mm": 10.0,
        "eind_meshoogte_mm": None,
        "slijtage_mm_per_dag": None,
        "geschatte_dagen_tot_3mm": None,
        "geschatte_vervangdatum_bij_3mm": None,
        "status_3mm": "CHECK_TREND",
        "prioriteit": 10,
        "first_sheet_analysis_key": "2023-W49",
        "last_sheet_analysis_key": "2025-W10",
        "first_sheet_instance_key": "2023-12-05",
        "last_sheet_instance_key": "2025-03-05",
        "first_canonical_inspection_key": (
            "TATA_STEEL|IJMUIDEN|A660|"
            "2023-12-05"
        ),
        "last_canonical_inspection_key": (
            "TATA_STEEL|IJMUIDEN|A660|"
            "2025-03-05"
        ),
        "source_file": (
            r"C:\test\Sinterlijn.xlsx"
        ),
        "sheet_raw": "week 10",
        "dagen_sinds_laatste_meting": 543,
        "scraper_types_raw": "U 1400 INOX",
        "scraper_types_clean": "U 1400 INOX",
        "position_accessories": [],
        "prestatiegrens_mm": 6,
        "vervanggrens_mm": 3,
        "geschatte_dagen_tot_6mm": None,
        "geschatte_datum_bij_6mm": None,
        "dagen_tot_6mm_vanaf_vandaag": None,
        "status_6mm": "ONBEKEND",
        "vervuilingsrisico": False,
        "prestatie_vervangmoment": None,
    }


def _raw_result(
    *,
    resolved: bool = True,
):
    return {
        "intent": "maintenance_positions",
        "kort_resultaat": (
            "2 onderhoudsposities gevonden."
        ),
        "trend_patronen": [
            "Prioriteit 1: 0",
            "Prioriteit 2: 0",
            (
                "Prestatiegrens 6 mm "
                "geraakt/nabij: 1"
            ),
            "Op of onder 6 mm: 1",
        ],
        "resultaat": [
            _r_position(),
            _u_position(),
        ],
        "asset_context": {
            "customer_code": "TATA_STEEL",
            "site_code": "IJMUIDEN",
            "area_code": "GSL",
            "area_name": "GSL",
            "installation_code": "SINTER",
            "installation_name": "Sinter",
            "band_code": "A660",
            "band_code_norm": "A660",
            "band_code_display": "A660",
        },
        "asset_resolution": {
            "status": (
                "resolved"
                if resolved
                else "not_found"
            ),
            "match_count": (
                1
                if resolved
                else 0
            ),
            "normalized_band_code": "A660",
            "normalized_installation_code": (
                "SINTER"
            ),
        },
    }


def _execution_result(
    raw_result: dict | None = None,
):
    return ExecutionResult(
        contract_version=(
            EXECUTION_CONTRACT_VERSION
        ),
        step_id="step_maintenance_1",
        action="analysis_assistant",
        domain="inspection",
        endpoint="/analysis/assistant/ask",
        transport_state=(
            ExecutionTransportState.COMPLETED
        ),
        semantic_outcome=(
            ExecutionOutcome.UNKNOWN
        ),
        specialist_status=None,
        legacy_accepted=True,
        result=(
            raw_result
            if raw_result is not None
            else _raw_result()
        ),
        error=None,
        attempt_count=1,
        duration_ms=50,
        evidence_metadata=None,
        provenance_metadata=None,
    )


def _evidence(
    raw_result: dict | None = None,
):
    return normalize_execution_result_evidence(
        _execution_result(
            raw_result
        ),
        retrieved_at=NOW,
    )


def test_requirement_set_is_maintenance_priority_v1():
    requirement_set = get_requirement_set(
        "maintenance_priority"
    )

    assert requirement_set is not None

    assert (
        requirement_set.requirement_set_id
        == "maintenance_priority.v1"
    )

    assert [
        item.requirement_id
        for item in requirement_set.requirements
    ] == [
        "RESOLVED_ASSET_CONTEXT",
        "MAINTENANCE_POSITION_STATUS",
        "LATEST_POSITION_MEASUREMENT",
        "FORECAST_RESULT",
    ]


def test_adapter_creates_two_position_statuses():
    evidence = _evidence()

    statuses = [
        item
        for item in evidence
        if (
            item.evidence_type
            == EvidenceType.STATUS
        )
    ]

    assert len(statuses) == 2

    assert all(
        item.direct_or_derived
        == EvidenceDirectness.DERIVED
        for item in statuses
    )


def test_r_position_has_direct_latest_measurement():
    evidence = _evidence()

    measurements = [
        item
        for item in evidence
        if (
            item.evidence_type
            == EvidenceType.MEASUREMENT
        )
    ]

    assert len(measurements) == 1

    measurement = measurements[0]

    assert (
        measurement.value[
            "meshoogte_mm"
        ]
        == 5.0
    )

    assert (
        measurement.direct_or_derived
        == EvidenceDirectness.DIRECT
    )


def test_u_position_does_not_invent_measurement():
    evidence = _evidence()

    measurements = [
        item
        for item in evidence
        if (
            item.evidence_type
            == EvidenceType.MEASUREMENT
        )
    ]

    assert all(
        item.value["scraper_types"]
        != "U 1400 INOX"
        for item in measurements
    )


def test_only_r_position_gets_forecast():
    evidence = _evidence()

    forecasts = [
        item
        for item in evidence
        if (
            item.evidence_type
            == EvidenceType.CALCULATION_RESULT
        )
    ]

    assert len(forecasts) == 1

    forecast = forecasts[0]

    assert (
        forecast.value["scraper_types"]
        == "R 1400-1350 INOX"
    )

    assert (
        forecast.value[
            "geschatte_dagen_tot_3mm"
        ]
        == 170.4
    )

    assert (
        forecast.direct_or_derived
        == EvidenceDirectness.DERIVED
    )


def test_forecast_requires_at_least_three_points():
    raw = _raw_result()

    raw["resultaat"][0][
        "meetpunten"
    ] = 2

    evidence = _evidence(
        raw
    )

    forecasts = [
        item
        for item in evidence
        if (
            item.evidence_type
            == EvidenceType.CALCULATION_RESULT
        )
    ]

    assert forecasts == []


def test_evidence_is_latest_known_and_grounded():
    evidence = _evidence()

    position_evidence = [
        item
        for item in evidence
        if (
            item.entity_type
            == "maintenance_position"
        )
    ]

    assert position_evidence

    assert all(
        item.freshness_status
        == EvidenceFreshnessStatus.LATEST_KNOWN
        for item in position_evidence
    )

    assert all(
        item.grounding_status
        == EvidenceGroundingStatus.GROUNDED
        for item in position_evidence
    )

    assert all(
        item.quality_status
        == EvidenceQualityStatus.VALID
        for item in position_evidence
    )


def test_unresolved_asset_prevents_grounding():
    evidence = _evidence(
        _raw_result(
            resolved=False
        )
    )

    position_evidence = [
        item
        for item in evidence
        if (
            item.entity_type
            == "maintenance_position"
        )
    ]

    assert position_evidence

    assert all(
        item.grounding_status
        == EvidenceGroundingStatus.UNKNOWN
        for item in position_evidence
    )


def test_duplicate_rows_are_deduplicated():
    raw = _raw_result()

    raw["resultaat"].append(
        deepcopy(
            raw["resultaat"][0]
        )
    )

    evidence = _evidence(
        raw
    )

    statuses = [
        item
        for item in evidence
        if (
            item.evidence_type
            == EvidenceType.STATUS
        )
    ]

    measurements = [
        item
        for item in evidence
        if (
            item.evidence_type
            == EvidenceType.MEASUREMENT
        )
    ]

    forecasts = [
        item
        for item in evidence
        if (
            item.evidence_type
            == EvidenceType.CALCULATION_RESULT
        )
    ]

    assert len(statuses) == 2
    assert len(measurements) == 1
    assert len(forecasts) == 1


def test_live_shape_assesses_sufficient_without_conflict():
    requirement_set = get_requirement_set(
        "maintenance_priority"
    )

    assert requirement_set is not None

    assessment = assess_evidence(
        requirement_set,
        _evidence(),
        now=NOW,
    )

    assert (
        assessment.status
        == EvidenceAssessmentStatus.SUFFICIENT
    )

    assert (
        assessment.conflicting_requirement_ids
        == ()
    )