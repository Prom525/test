from datetime import datetime, timezone

from app.orchestrator.evidence_adapters import (
    normalize_execution_result_evidence,
)
from app.orchestrator.evidence_assessor import (
    EvidenceAssessmentStatus,
    RequirementAssessmentStatus,
    assess_evidence,
)
from app.orchestrator.evidence_contracts import (
    EvidenceFreshnessStatus,
    EvidenceQualityStatus,
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
    12,
    0,
    tzinfo=timezone.utc,
)


def _org_execution_result(
    record: dict,
    *,
    source_route: str = (
        "/analysis/context/org/function-info"
    ),
) -> ExecutionResult:
    return ExecutionResult(
        contract_version=EXECUTION_CONTRACT_VERSION,
        step_id="step_1_org",
        action="org_assistant",
        domain="org",
        endpoint="/org/assistant/ask",
        transport_state=(
            ExecutionTransportState.COMPLETED
        ),
        semantic_outcome=ExecutionOutcome.SUCCESS,
        specialist_status="ok",
        legacy_accepted=True,
        result={
            "status": "ok",
            "source_route": source_route,
            "result": {
                "results": [
                    record,
                ],
            },
        },
        error=None,
        attempt_count=1,
        duration_ms=1,
        evidence_metadata=None,
        provenance_metadata=None,
    )


def _requirements():
    requirement_set = get_requirement_set(
        "org_lookup"
    )

    assert requirement_set is not None

    assert (
        requirement_set.requirement_set_id
        == "person_role_lookup.v1"
    )

    return requirement_set


def test_org_explicit_current_role_is_sufficient():
    requirement_set = _requirements()

    execution_result = _org_execution_result(
        {
            "person_id": "P001",
            "weergavenaam": "Test Persoon",
            "functie_code": "VCA_COORDINATOR",
            "persoon_functie_id": 1001,
            "primair": True,
            "geldig_vanaf": (
                "2025-01-01T00:00:00+00:00"
            ),
            "geldig_tot": None,
        }
    )

    evidence = normalize_execution_result_evidence(
        execution_result,
        retrieved_at=NOW,
    )

    assert len(evidence) == 1

    item = evidence[0]

    assert (
        item.freshness_status
        is EvidenceFreshnessStatus.CURRENT
    )

    assert (
        item.quality_status
        is EvidenceQualityStatus.VALID
    )

    assessment = assess_evidence(
        requirement_set,
        evidence,
        now=NOW,
    )

    assert (
        assessment.status
        is EvidenceAssessmentStatus.SUFFICIENT
    )

    result = assessment.requirement_results[0]

    assert (
        result.status
        is RequirementAssessmentStatus.SATISFIED
    )


def test_org_expired_role_is_stale_and_not_sufficient():
    requirement_set = _requirements()

    execution_result = _org_execution_result(
        {
            "person_id": "P001",
            "weergavenaam": "Test Persoon",
            "functie_code": "VCA_COORDINATOR",
            "persoon_functie_id": 1001,
            "primair": True,
            "geldig_vanaf": (
                "2024-01-01T00:00:00+00:00"
            ),
            "geldig_tot": (
                "2025-12-31T23:59:59+00:00"
            ),
        }
    )

    evidence = normalize_execution_result_evidence(
        execution_result,
        retrieved_at=NOW,
    )

    assert len(evidence) == 1

    item = evidence[0]

    assert (
        item.freshness_status
        is EvidenceFreshnessStatus.STALE
    )

    assessment = assess_evidence(
        requirement_set,
        evidence,
        now=NOW,
    )

    assert (
        assessment.status
        is EvidenceAssessmentStatus.INSUFFICIENT
    )

    result = assessment.requirement_results[0]

    assert (
        result.status
        is not RequirementAssessmentStatus.SATISFIED
    )


def test_org_primary_function_info_without_dates_is_current():
    requirement_set = _requirements()

    execution_result = _org_execution_result(
        {
            "person_id": 11,
            "weergavenaam": "Aaron Thys",
            "functie_code": "OPERATIONS_MANAGER",
            "persoon_functie_id": 3,
            "primair": True,
            "geldig_vanaf": None,
            "geldig_tot": None,
            "bron_doc_id": (
                "functieomschrijvingen_promati_vca_2026"
            ),
        }
    )

    evidence = normalize_execution_result_evidence(
        execution_result,
        retrieved_at=NOW,
    )

    assert len(evidence) == 1

    item = evidence[0]

    assert (
        item.freshness_status
        is EvidenceFreshnessStatus.CURRENT
    )

    assert (
        item.quality_status
        is EvidenceQualityStatus.VALID
    )

    assert item.entity_id == "11"

    assessment = assess_evidence(
        requirement_set,
        evidence,
        now=NOW,
    )

    assert (
        assessment.status
        is EvidenceAssessmentStatus.SUFFICIENT
    )

    result = assessment.requirement_results[0]

    assert (
        result.status
        is RequirementAssessmentStatus.SATISFIED
    )


def test_org_non_primary_without_dates_remains_unknown():
    requirement_set = _requirements()

    execution_result = _org_execution_result(
        {
            "person_id": "P001",
            "weergavenaam": "Test Persoon",
            "functie_code": "VCA_COORDINATOR",
            "persoon_functie_id": 1001,
            "primair": False,
            "geldig_vanaf": None,
            "geldig_tot": None,
        }
    )

    evidence = normalize_execution_result_evidence(
        execution_result,
        retrieved_at=NOW,
    )

    assert len(evidence) == 1

    item = evidence[0]

    assert (
        item.freshness_status
        is EvidenceFreshnessStatus.UNKNOWN
    )

    assert (
        item.quality_status
        is EvidenceQualityStatus.VALID
    )

    assessment = assess_evidence(
        requirement_set,
        evidence,
        now=NOW,
    )

    assert (
        assessment.status
        is EvidenceAssessmentStatus.INSUFFICIENT
    )


def test_org_future_role_is_not_current():
    execution_result = _org_execution_result(
        {
            "person_id": "P001",
            "weergavenaam": "Test Persoon",
            "functie_code": "VCA_COORDINATOR",
            "persoon_functie_id": 1001,
            "primair": True,
            "geldig_vanaf": (
                "2027-01-01T00:00:00+00:00"
            ),
            "geldig_tot": None,
        }
    )

    evidence = normalize_execution_result_evidence(
        execution_result,
        retrieved_at=NOW,
    )

    assert len(evidence) == 1

    assert (
        evidence[0].freshness_status
        is EvidenceFreshnessStatus.UNKNOWN
    )


def test_org_malformed_validity_is_not_current():
    execution_result = _org_execution_result(
        {
            "person_id": "P001",
            "weergavenaam": "Test Persoon",
            "functie_code": "VCA_COORDINATOR",
            "persoon_functie_id": 1001,
            "primair": True,
            "geldig_vanaf": "geen-datum",
            "geldig_tot": None,
        }
    )

    evidence = normalize_execution_result_evidence(
        execution_result,
        retrieved_at=NOW,
    )

    assert len(evidence) == 1

    assert (
        evidence[0].freshness_status
        is EvidenceFreshnessStatus.UNKNOWN
    )


def test_org_incomplete_role_has_unknown_quality():
    execution_result = _org_execution_result(
        {
            "person_id": "P001",
            "weergavenaam": "Test Persoon",
            "functie_code": None,
            "persoon_functie_id": None,
            "primair": True,
            "geldig_vanaf": None,
            "geldig_tot": None,
        }
    )

    evidence = normalize_execution_result_evidence(
        execution_result,
        retrieved_at=NOW,
    )

    assert len(evidence) == 1

    item = evidence[0]

    assert (
        item.quality_status
        is EvidenceQualityStatus.UNKNOWN
    )

    assert (
        item.freshness_status
        is EvidenceFreshnessStatus.UNKNOWN
    )