# PROMATI_P4_14C_TARGETED_GOLDEN_TEST_MARKERS_V1
# P4_14B_GOLDEN_001 inspection_latest complete coverage
# P4_14B_GOLDEN_002 maintenance_priority complete coverage
# P4_14B_GOLDEN_003 task_public_composition authoritative multi-intent
# P4_14B_GOLDEN_004 comparison MV1/MV2 guarded
# P4_14B_GUARD_005 coverage_not_ready fail-open guard
# PROMATI_P4_14C_TARGETED_GOLDENS_V1
"""P4.14c targeted golden tests for coverage/public-composition quality.

These tests intentionally define the desired behavior before product-code changes.
They focus on the observed gap:
- inspection_latest.v1 evidence must become sufficient for MV1 live-shaped data.
- maintenance_priority.v1 evidence must become sufficient for MV1 live-shaped data.
- multi-intent public composition may become authoritative only when task evidence
  coverage is sufficient.
- comparison must be grounded per scope, or be explicitly guarded.
- missing coverage must fail open safely without debug JSON in the public answer.
"""

from __future__ import annotations

import inspect
from typing import Any

import pytest


pytestmark = pytest.mark.p4_14c


def _value(value: Any) -> Any:
    return getattr(value, "value", value)


def _normalize_execution_result_evidence(intent: str, result: dict[str, Any]):
    from app.orchestrator.evidence_adapters import normalize_execution_result_evidence

    attempts = []
    attempts.append(lambda: normalize_execution_result_evidence(intent=intent, execution_result=result))
    attempts.append(lambda: normalize_execution_result_evidence(intent=intent, result=result))
    attempts.append(lambda: normalize_execution_result_evidence(execution_result=result))
    attempts.append(lambda: normalize_execution_result_evidence(result=result))
    attempts.append(lambda: normalize_execution_result_evidence(result, intent=intent))
    attempts.append(lambda: normalize_execution_result_evidence(result))

    errors: list[str] = []
    for attempt in attempts:
        try:
            evidence = tuple(attempt() or ())
            if evidence:
                return evidence
        except TypeError as exc:
            errors.append(str(exc))
        except Exception as exc:  # keep this as assertion feedback, not collection failure
            errors.append(type(exc).__name__ + ": " + str(exc))

    signature = str(inspect.signature(normalize_execution_result_evidence))
    pytest.fail(
        "Could not normalize P4.14c live-shaped execution result for intent "
        + intent
        + ". normalize_execution_result_evidence signature="
        + signature
        + "; errors="
        + " | ".join(errors[-4:])
    )


def _assess(intent: str, evidence_items):
    from app.orchestrator.evidence_assessor import EvidenceAssessmentStatus, assess_evidence
    from app.orchestrator.evidence_requirement_catalog import get_requirement_set

    requirement_set = get_requirement_set(intent)
    assessment = assess_evidence(requirement_set, tuple(evidence_items or ()))
    return assessment, EvidenceAssessmentStatus


def _requirement_diagnostics(assessment: Any) -> str:
    parts = []
    for attr in (
        "status",
        "required_count",
        "satisfied_required_count",
        "missing_required_ids",
        "missing_requirement_ids",
        "unsatisfied_required_ids",
        "requirement_results",
        "reasons",
        "evidence_ids_considered",
    ):
        if hasattr(assessment, attr):
            parts.append(attr + "=" + repr(getattr(assessment, attr)))
    return "; ".join(parts)


def _inspection_latest_mv1_live_shape() -> dict[str, Any]:
    return {
        "intent": "inspection_latest",
        "domain": "inspection",
        "scope": {
            "scope_code": "MV1",
            "scope_type": "line",
            "line_code": "MV1",
            "lijn_code": "MV1",
            "area_code": "GSL",
            "asset_name": "Mengveld 1",
        },
        "rows": [
            {
                "canonical_scope_code": "MV1",
                "scope_code": "MV1",
                "scope_type": "line",
                "line_code": "MV1",
                "lijn_code": "MV1",
                "area_code": "GSL",
                "asset_name": "Mengveld 1",
                "asset_label": "Mengveld 1",
                "latest_inspection_date": "2026-05-27",
                "inspection_date": "2026-05-27",
                "inspectiedatum": "2026-05-27",
                "observed_at": "2026-05-27T00:00:00+02:00",
                "position_code": "R5",
                "position_label": "R-5",
                "measurement_name": "meshoogte",
                "measurement_type": "blade_height",
                "measurement_value": 3.0,
                "value": 3.0,
                "value_mm": 3.0,
                "unit": "mm",
                "status": "DIRECT_ACTIE_3MM_OVERDUE",
                "quality_status": "valid",
                "freshness_status": "current",
            }
        ],
        "summary": {
            "latest_inspection_date": "2026-05-27",
            "current_registered_scraper_positions": 43,
            "scope_code": "MV1",
        },
    }


def _maintenance_priority_mv1_live_shape() -> dict[str, Any]:
    return {
        "intent": "maintenance_priority",
        "domain": "maintenance",
        "scope": {
            "scope_code": "MV1",
            "scope_type": "line",
            "line_code": "MV1",
            "lijn_code": "MV1",
            "area_code": "GSL",
            "asset_name": "Mengveld 1",
        },
        "rows": [
            {
                "canonical_scope_code": "MV1",
                "scope_code": "MV1",
                "scope_type": "line",
                "line_code": "MV1",
                "lijn_code": "MV1",
                "area_code": "GSL",
                "asset_name": "Mengveld 1",
                "asset_label": "Mengveld 1",
                "position_code": "R5",
                "position_label": "R-5",
                "maintenance_position_status": "DIRECT_ACTIE_3MM_OVERDUE",
                "status": "DIRECT_ACTIE_3MM_OVERDUE",
                "priority": "high",
                "priority_rank": 1,
                "priority_rationale": "meshoogte 3.0 mm is onder directe actiegrens",
                "latest_position_measurement": 3.0,
                "measurement_name": "meshoogte",
                "measurement_type": "blade_height",
                "measurement_value": 3.0,
                "value": 3.0,
                "value_mm": 3.0,
                "unit": "mm",
                "forecast_result": {
                    "status": "overdue",
                    "days_to_limit": 0,
                },
                "observed_at": "2026-05-27T00:00:00+02:00",
                "quality_status": "valid",
                "freshness_status": "current",
            }
        ],
        "summary": {
            "maintenance_rule_count": 16,
            "scope_code": "MV1",
            "highest_priority": "high",
        },
    }


def test_p4_14c_golden_001_inspection_latest_complete_coverage():
    evidence_items = _normalize_execution_result_evidence(
        "inspection_latest",
        _inspection_latest_mv1_live_shape(),
    )
    assessment, status_enum = _assess("inspection_latest", evidence_items)

    assert _value(assessment.status) == _value(status_enum.SUFFICIENT), (
        "inspection_latest.v1 must be sufficient when MV1 asset context, "
        "latest inspection date and latest inspection measurement are present. "
        + _requirement_diagnostics(assessment)
    )


def test_p4_14c_golden_002_maintenance_priority_complete_coverage_forecast_desired_not_blocking():
    evidence_items = _normalize_execution_result_evidence(
        "maintenance_priority",
        _maintenance_priority_mv1_live_shape(),
    )
    assessment, status_enum = _assess("maintenance_priority", evidence_items)

    assert _value(assessment.status) == _value(status_enum.SUFFICIENT), (
        "maintenance_priority.v1 must be sufficient when MV1 asset context, "
        "maintenance position status and latest position measurement are present; "
        "forecast_result is desired and must not block when core priority evidence is present. "
        + _requirement_diagnostics(assessment)
    )


def test_p4_14c_golden_003_multi_intent_public_composition_authoritative_contract_documented():
    pytest.fail(
        "P4.14c product fix pending: when inspection_latest and maintenance_priority "
        "task evidence units are both sufficient, task_public_composition must return "
        "authoritative=True, answer_replaced=True, blocked=False, and a user-safe answer "
        "containing both latest inspection status and maintenance priority."
    )


def test_p4_14c_golden_004_comparison_mv1_mv2_guarded_contract_documented():
    pytest.fail(
        "P4.14c product fix pending: MV1/MV2 comparison must either provide grounded "
        "per-scope latest status and priority rationale, or explicitly state which "
        "per-scope evidence is missing. It must not invent a comparison."
    )


def test_p4_14c_guard_005_fail_open_when_coverage_missing_contract_documented():
    pytest.fail(
        "P4.14c product fix pending: if required evidence is missing, "
        "coverage_not_ready must remain blocked, fail_open must be true, and the "
        "public answer must state missing context without internal JSON/debug fields."
    )

