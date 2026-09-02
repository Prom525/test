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
    29,
    15,
    0,
    tzinfo=timezone.utc,
)


def _row(
    inspected_on: str,
    height: float | None,
    *,
    scraper: str = "R 1400-1350 INOX",
    position: str = "SECUNDAIR",
    cycle_id: int = 1,
    replace_event: bool = False,
    comment: str | None = None,
    band: str = "A660",
):
    return {
        "inspected_on": inspected_on,
        "lijn_code": "GSL",
        "band_norm": band,
        "scraper_type_norm": scraper,
        "position_hint": position,
        "meshoogte_mm": height,
        "replace_event": replace_event,
        "cycle_id": cycle_id,
        "commentaar": comment,
        "sheet_analysis_key": (
            f"TEST-{inspected_on}"
        ),
        "sheet_instance_key": inspected_on,
        "sheet_period_key": (
            f"TEST-{inspected_on}"
        ),
        "inspection_year": int(
            inspected_on[:4]
        ),
        "week_no": 1,
        "canonical_inspection_key": (
            f"TATA_STEEL|IJMUIDEN|"
            f"A660|{scraper}|{position}|"
            f"{inspected_on}"
        ),
        "source_file": (
            r"C:\test\Sinterlijn.xlsx"
        ),
        "sheet_raw": "week test",
        "scraper_type_norm_raw": scraper,
    }


def _raw_result(
    *,
    resolved: bool = True,
):
    return {
        "intent": "lifecycle",
        "kort_resultaat": (
            "4 lifecycle-regels gevonden."
        ),
        "trend_patronen": [
            "4 lifecycle-regels gevonden.",
        ],
        "resultaat": [
            _row(
                "2026-05-05",
                5.0,
            ),
            _row(
                "2026-03-10",
                6.0,
            ),
            _row(
                "2026-01-21",
                7.0,
            ),
            _row(
                "2025-03-05",
                10.0,
                replace_event=True,
                comment="Schraper Geplaatst",
            ),
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
                1 if resolved else 0
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
        step_id="step_1_inspection",
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
        duration_ms=40,
        evidence_metadata=None,
        provenance_metadata=None,
    )


def _evidence(
    raw_result: dict | None = None,
):
    return normalize_execution_result_evidence(
        _execution_result(raw_result),
        retrieved_at=NOW,
    )


def test_inspection_trend_requirement_set_is_exact():
    requirement_set = get_requirement_set(
        "inspection_trend"
    )

    assert requirement_set is not None

    assert (
        requirement_set.requirement_set_id
        == "inspection_trend.v1"
    )

    assert [
        item.requirement_id
        for item in requirement_set.requirements
    ] == [
        "RESOLVED_ASSET_CONTEXT",
        "MEASUREMENT_HISTORY",
        "REPLACEMENT_HISTORY",
        "INSPECTION_COMMENTS",
    ]

    measurement_requirement = next(
        item
        for item in requirement_set.requirements
        if (
            item.requirement_id
            == "MEASUREMENT_HISTORY"
        )
    )

    assert (
        measurement_requirement.minimum_items
        == 2
    )


def test_lifecycle_adapter_preserves_all_measurements():
    evidence = _evidence()

    measurements = [
        item
        for item in evidence
        if (
            item.evidence_type
            == EvidenceType.MEASUREMENT
        )
    ]

    assert len(measurements) == 4

    assert sorted(
        item.value["meshoogte_mm"]
        for item in measurements
    ) == [
        5.0,
        6.0,
        7.0,
        10.0,
    ]


def test_lifecycle_adapter_creates_replacement_and_comment_evidence():
    evidence = _evidence()

    replacements = [
        item
        for item in evidence
        if (
            item.evidence_type
            == EvidenceType.EVENT
            and item.subject
            == "replacement_history"
        )
    ]

    comments = [
        item
        for item in evidence
        if (
            item.evidence_type
            == EvidenceType.RECORD
            and item.subject
            == "inspection_comment"
        )
    ]

    assert len(replacements) == 1
    assert len(comments) == 1

    assert (
        replacements[0].value[
            "replace_event"
        ]
        is True
    )

    assert (
        comments[0].value[
            "commentaar"
        ]
        == "Schraper Geplaatst"
    )


def test_historical_evidence_uses_not_applicable_freshness():
    evidence = _evidence()

    historical = [
        item
        for item in evidence
        if (
            item.evidence_type
            in {
                EvidenceType.MEASUREMENT,
                EvidenceType.EVENT,
                EvidenceType.RECORD,
            }
        )
    ]

    assert historical

    assert all(
        item.freshness_status
        == EvidenceFreshnessStatus.NOT_APPLICABLE
        for item in historical
    )


def test_resolved_matching_asset_is_grounded_and_valid():
    evidence = _evidence()

    measurements = [
        item
        for item in evidence
        if (
            item.evidence_type
            == EvidenceType.MEASUREMENT
        )
    ]

    assert measurements

    assert all(
        item.grounding_status
        == EvidenceGroundingStatus.GROUNDED
        for item in measurements
    )

    assert all(
        item.quality_status
        == EvidenceQualityStatus.VALID
        for item in measurements
    )


def test_duplicate_lifecycle_rows_are_deduplicated():
    raw = _raw_result()

    duplicate = deepcopy(
        raw["resultaat"][0]
    )

    raw["resultaat"].append(
        duplicate
    )

    evidence = _evidence(raw)

    measurements = [
        item
        for item in evidence
        if (
            item.evidence_type
            == EvidenceType.MEASUREMENT
        )
    ]

    assert len(measurements) == 4


def test_unresolved_asset_does_not_ground_measurements():
    raw = _raw_result(
        resolved=False
    )

    evidence = _evidence(raw)

    measurements = [
        item
        for item in evidence
        if (
            item.evidence_type
            == EvidenceType.MEASUREMENT
        )
    ]

    assert measurements

    assert all(
        item.grounding_status
        == EvidenceGroundingStatus.UNKNOWN
        for item in measurements
    )


def test_different_historical_values_do_not_conflict():
    requirement_set = get_requirement_set(
        "inspection_trend"
    )

    assert requirement_set is not None

    evidence = _evidence()

    assessment = assess_evidence(
        requirement_set,
        evidence,
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


def test_two_measurements_are_enough_for_trend_requirement():
    raw = _raw_result()

    raw["resultaat"] = [
        _row(
            "2026-05-05",
            5.0,
        ),
        _row(
            "2026-03-10",
            6.0,
        ),
        _row(
            "2025-03-05",
            None,
            replace_event=True,
            comment="Schraper Geplaatst",
        ),
    ]

    requirement_set = get_requirement_set(
        "inspection_trend"
    )

    assert requirement_set is not None

    evidence = _evidence(raw)

    assessment = assess_evidence(
        requirement_set,
        evidence,
        now=NOW,
    )

    measurement_result = next(
        item
        for item in assessment.requirement_results
        if (
            item.requirement_id
            == "MEASUREMENT_HISTORY"
        )
    )

    assert measurement_result.status.value == "satisfied"