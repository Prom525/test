from __future__ import annotations

from copy import deepcopy
from datetime import (
    datetime,
    timezone,
)

from app.orchestrator.evidence_adapters import (
    normalize_execution_result_evidence,
)
from app.orchestrator.evidence_assessor import (
    assess_evidence,
)
from app.orchestrator.evidence_contracts import (
    EvidenceDirectness,
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
    31,
    8,
    30,
    tzinfo=timezone.utc,
)


def _raw_result():
    return {
        "intent": (
            "band_deep_analysis"
        ),
        "entities": {
            "band_code": "A660",
            "lijn_code": None,
        },
        "asset_context": {
            "customer_code": (
                "TATA_STEEL"
            ),
            "site_code": "IJMUIDEN",
            "area_code": "GSL",
            "installation_code": (
                "SINTER"
            ),
            "band_code": "A660",
            "band_code_norm": "A660",
        },
        "asset_resolution": {
            "status": "resolved",
            "match_count": 1,
            "normalized_band_code": (
                "A660"
            ),
            "normalized_installation_code": (
                "SINTER"
            ),
        },
        "laatste_meshoogte": [
            {
                "laatste_meting_datum": (
                    "2026-05-05"
                ),
                "lijn_code": "GSL",
                "band_norm": "A660",
                "scraper_family": "R",
                "scraper_type_norm": (
                    "R 1400-1350 INOX"
                ),
                "position_hint": (
                    "SECUNDAIR"
                ),
                "meshoogte_mm": 5.0,
                "canonical_inspection_key": (
                    "A660|2026-05-05|R"
                ),
                "source_file": (
                    "Sinterlijn.xlsx"
                ),
                "sheet_raw": "week 19",
            },
        ],
        "lifecycle": [
            {
                "inspected_on": (
                    "2026-05-05"
                ),
                "band_norm": "A660",
                "scraper_type_norm": (
                    "R 1400-1350 INOX"
                ),
                "position_hint": (
                    "SECUNDAIR"
                ),
                "meshoogte_mm": 5.0,
                "replace_event": False,
                "cycle_id": 1,
                "canonical_inspection_key": (
                    "A660|2026-05-05|R"
                ),
                "source_file": (
                    "Sinterlijn.xlsx"
                ),
            },
            {
                "inspected_on": (
                    "2025-09-17"
                ),
                "band_norm": "A660",
                "scraper_type_norm": (
                    "R 1400-1350 INOX"
                ),
                "position_hint": (
                    "SECUNDAIR"
                ),
                "meshoogte_mm": 8.0,
                "replace_event": False,
                "cycle_id": 1,
                "canonical_inspection_key": (
                    "A660|2025-09-17|R"
                ),
                "source_file": (
                    "Sinterlijn.xlsx"
                ),
            },
            {
                "inspected_on": (
                    "2025-03-05"
                ),
                "band_norm": "A660",
                "scraper_type_norm": (
                    "R 1400-1350 INOX"
                ),
                "position_hint": (
                    "SECUNDAIR"
                ),
                "meshoogte_mm": 10.0,
                "replace_event": True,
                "cycle_id": 1,
                "canonical_inspection_key": (
                    "A660|2025-03-05|R"
                ),
                "source_file": (
                    "Sinterlijn.xlsx"
                ),
            },
        ],
        "forecast_3mm": [
            {
                "band_norm": "A660",
                "scraper_type_norm": (
                    "R 1400-1350 INOX"
                ),
                "position_hint": (
                    "POS A / SECUNDAIR"
                ),
                "cycle_start": (
                    "2025-03-05"
                ),
                "cycle_end": (
                    "2026-05-05"
                ),
                "meetpunten": 7,
                "start_meshoogte_mm": (
                    10.0
                ),
                "eind_meshoogte_mm": (
                    5.0
                ),
                "slijtage_mm_per_dag": (
                    0.0117370892
                ),
                "geschatte_dagen_tot_3mm": (
                    170.4
                ),
                "geschatte_vervangdatum_bij_3mm": (
                    "2026-10-22"
                ),
                "status_3mm": "OK",
                "vervanggrens_mm": 3,
                "last_canonical_inspection_key": (
                    "A660|2026-05-05|R"
                ),
                "source_file": (
                    "Sinterlijn.xlsx"
                ),
            },
        ],
        "gecombineerde_slijtage": [
            {
                "band_norm": "A660",
                "position_display": (
                    "SUB_POSITION"
                ),
                "position_key_unified": (
                    "A660|RI|SLOT_2"
                ),
                "scraper_type_norm": (
                    "RI 1400-1350"
                ),
                "meshoogte_mm": 5.0,
                "slijtage_actie_pct": (
                    71.4
                ),
                "betrouwbaarheid": (
                    "hoog"
                ),
                "score_bron": (
                    "BEREKEND_UIT_MESHOOGTE"
                ),
                "onderhoudsadvies_unified": (
                    "VERVANGEN_VOORBEREIDEN"
                ),
                "planned_replace_signal": (
                    False
                ),
                "mechanical_or_access_signal": (
                    False
                ),
                "laatste_inspectiedatum": (
                    "2026-05-05"
                ),
                "source_file": (
                    "Sinterlijn.xlsx"
                ),
                "inspection_key": (
                    "A660|2026-05-05|RI"
                ),
            },
        ],
        "ongewone_slijtage": {
            "ja_nee": True,
            "waarom": [
                "meerdere vervangevents",
            ],
        },
        "mogelijke_oorzaak": [
            (
                "mogelijk band- of "
                "trommelconditie"
            ),
        ],
    }


def _execution_result(
    raw=None,
):
    if raw is None:
        raw = _raw_result()

    return ExecutionResult(
        contract_version=(
            EXECUTION_CONTRACT_VERSION
        ),
        step_id=(
            "step_1_inspection"
        ),
        action=(
            "analysis_assistant"
        ),
        domain="inspection",
        endpoint=(
            "/analysis/assistant/ask"
        ),
        transport_state=(
            ExecutionTransportState
            .COMPLETED
        ),
        semantic_outcome=(
            ExecutionOutcome.UNKNOWN
        ),
        specialist_status=None,
        legacy_accepted=True,
        result=raw,
        error=None,
        attempt_count=1,
        duration_ms=20,
        evidence_metadata=None,
        provenance_metadata=None,
    )


def _evidence(
    raw=None,
):
    return (
        normalize_execution_result_evidence(
            _execution_result(
                raw
            ),
            retrieved_at=NOW,
        )
    )


def test_requirement_set_is_exact():
    requirement_set = (
        get_requirement_set(
            "replacement_advice"
        )
    )

    assert requirement_set is not None

    assert (
        requirement_set
        .requirement_set_id
        == "replacement_advice.v1"
    )

    assert [
        item.requirement_id
        for item
        in requirement_set.requirements
    ] == [
        "RESOLVED_ASSET_CONTEXT",
        "LATEST_POSITION_MEASUREMENT",
        "LIFECYCLE_HISTORY",
        "REPLACEMENT_HISTORY",
        "FORECAST_RESULT",
        "DIAGNOSTIC_FINDING",
    ]


def test_band_deep_analysis_dispatches_to_dedicated_adapter():
    evidence = _evidence()

    assert evidence

    assert any(
        item.evidence_type
        == EvidenceType.ASSET_RESOLUTION
        for item in evidence
    )

    assert any(
        item.subject
        == "latest_position_measurement"
        for item in evidence
    )

    assert any(
        item.subject
        == "lifecycle_measurement"
        for item in evidence
    )


def test_latest_measurement_is_direct_scraper_position():
    evidence = _evidence()

    latest = [
        item
        for item in evidence
        if (
            item.subject
            == "latest_position_measurement"
        )
    ]

    assert len(latest) == 1

    assert (
        latest[0].entity_type
        == "scraper_position"
    )

    assert (
        latest[0].direct_or_derived
        == EvidenceDirectness.DIRECT
    )

    assert (
        latest[0].value[
            "meshoogte_mm"
        ]
        == 5.0
    )


def test_lifecycle_is_semantically_separate_from_latest():
    evidence = _evidence()

    lifecycle = [
        item
        for item in evidence
        if (
            item.entity_type
            == "scraper_lifecycle"
        )
    ]

    assert len(lifecycle) >= 3

    assert all(
        (
            "LIFECYCLE_HISTORY"
            in item.claim_scope
        )
        for item in lifecycle
    )


def test_real_replace_event_becomes_replacement_history():
    evidence = _evidence()

    replacement_events = [
        item
        for item in evidence
        if (
            item.evidence_type
            == EvidenceType.EVENT
        )
    ]

    assert len(
        replacement_events
    ) == 1

    assert (
        replacement_events[0]
        .value["replace_event"]
        is True
    )

    assert (
        "REPLACEMENT_HISTORY"
        in replacement_events[0]
        .claim_scope
    )


def test_forecast_requires_three_usable_points():
    raw = _raw_result()

    raw["forecast_3mm"][0][
        "meetpunten"
    ] = 2

    evidence = _evidence(
        raw
    )

    assert not any(
        item.evidence_type
        == EvidenceType.CALCULATION_RESULT
        for item in evidence
    )


def test_incomplete_forecast_is_not_emitted():
    raw = _raw_result()

    raw["forecast_3mm"][0][
        "eind_meshoogte_mm"
    ] = None

    evidence = _evidence(
        raw
    )

    assert not any(
        item.evidence_type
        == EvidenceType.CALCULATION_RESULT
        for item in evidence
    )


def test_valid_forecast_is_derived():
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

    assert (
        forecasts[0]
        .direct_or_derived
        == EvidenceDirectness.DERIVED
    )

    assert (
        forecasts[0].value[
            "geschatte_vervangdatum_bij_3mm"
        ]
        == "2026-10-22"
    )


def test_prepare_replacement_is_not_hard_replace_at_five_mm():
    evidence = _evidence()

    findings = [
        item
        for item in evidence
        if (
            item.evidence_type
            == EvidenceType.DIAGNOSTIC_FINDING
        )
    ]

    assert len(findings) == 1

    finding = findings[0].value

    assert (
        finding[
            "onderhoudsadvies_unified"
        ]
        == "VERVANGEN_VOORBEREIDEN"
    )

    assert (
        finding[
            "hard_replacement_decision"
        ]
        is None
    )


def test_measured_three_mm_sets_hard_replacement_diagnostic():
    raw = _raw_result()

    raw[
        "gecombineerde_slijtage"
    ][0][
        "meshoogte_mm"
    ] = 3.0

    evidence = _evidence(
        raw
    )

    finding = next(
        item
        for item in evidence
        if (
            item.evidence_type
            == EvidenceType.DIAGNOSTIC_FINDING
        )
    )

    assert (
        finding.value[
            "hard_replacement_decision"
        ]
        == "NU_VERVANGEN"
    )


def test_live_shape_assesses_sufficient_without_conflict():
    requirement_set = (
        get_requirement_set(
            "replacement_advice"
        )
    )

    assert requirement_set is not None

    assessment = assess_evidence(
        requirement_set,
        _evidence(),
        now=NOW,
    )

    assert (
        assessment.status.value
        == "sufficient"
    )

    assert (
        assessment
        .missing_required_requirement_ids
        == ()
    )

    assert (
        assessment
        .conflicting_requirement_ids
        == ()
    )


def test_lifecycle_requirement_cannot_be_satisfied_by_latest_only():
    raw = _raw_result()

    raw["lifecycle"] = []

    assessment = assess_evidence(
        get_requirement_set(
            "replacement_advice"
        ),
        _evidence(raw),
        now=NOW,
    )

    assert (
        "LIFECYCLE_HISTORY"
        in assessment
        .missing_required_requirement_ids
    )


def test_unresolved_asset_does_not_ground_required_evidence():
    raw = deepcopy(
        _raw_result()
    )

    raw[
        "asset_resolution"
    ][
        "status"
    ] = "not_found"

    assessment = assess_evidence(
        get_requirement_set(
            "replacement_advice"
        ),
        _evidence(raw),
        now=NOW,
    )

    assert (
        assessment.status.value
        != "sufficient"
    )