from __future__ import annotations

from typing import Any

from app.orchestrator.execution_contracts import (
    EXECUTION_CONTRACT_VERSION,
    ExecutionOutcome,
    ExecutionRequest,
    ExecutionResult,
    ExecutionTransportState,
)
from app.orchestrator.specialist_registry import get_specialist_contract


_GLOBAL_STATUS_OUTCOME_MAP: dict[str, ExecutionOutcome] = {
    "ok": ExecutionOutcome.SUCCESS,
    "resolved": ExecutionOutcome.SUCCESS,
    "clarification_required": ExecutionOutcome.CLARIFICATION_REQUIRED,
    "ambiguous": ExecutionOutcome.AMBIGUOUS,
    "context_conflict": ExecutionOutcome.CONTEXT_CONFLICT,
    "not_found": ExecutionOutcome.NOT_FOUND,
    "unavailable": ExecutionOutcome.UNAVAILABLE,
    "redirect": ExecutionOutcome.REDIRECT,
    "error": ExecutionOutcome.ERROR,
    "failed": ExecutionOutcome.ERROR,
    "failure": ExecutionOutcome.ERROR,
}


def extract_specialist_status(
    result: dict[str, Any],
) -> str | None:
    value = result.get("status")

    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    return text


def derive_semantic_outcome(
    action: str,
    result: dict[str, Any],
) -> ExecutionOutcome:
    contract = get_specialist_contract(action)

    if contract is None:
        return ExecutionOutcome.UNKNOWN

    raw_status = extract_specialist_status(result)

    if raw_status is None:
        # PROMATI_ANALYSIS_STATUSLESS_SUCCESS_CONTRACT_V1
        #
        # Sommige bestaande specialistcontracten gebruiken
        # succesvol statusloos resultaat. Alleen specialists
        # die dit expliciet in hun registry-contract vastleggen
        # mogen statusloos als SUCCESS worden geïnterpreteerd.
        missing_status_value = (
            contract.status_map.get(
                "__missing__"
            )
        )

        if missing_status_value is not None:
            return missing_status_value

        return ExecutionOutcome.UNKNOWN

    normalized = raw_status.lower()

    specialist_value = contract.status_map.get(normalized)

    if specialist_value is not None:
        return specialist_value

    return _GLOBAL_STATUS_OUTCOME_MAP.get(
        normalized,
        ExecutionOutcome.UNKNOWN,
    )


def derive_execution_result(
    request: ExecutionRequest,
    raw_result: dict[str, Any],
    legacy_accepted: bool,
    transport_state: ExecutionTransportState = ExecutionTransportState.COMPLETED,
    error: str | None = None,
    attempt_count: int = 1,
    duration_ms: int | None = None,
    evidence_metadata: dict[str, Any] | None = None,
    provenance_metadata: dict[str, Any] | None = None,
) -> ExecutionResult:
    return ExecutionResult(
        contract_version=EXECUTION_CONTRACT_VERSION,
        step_id=request.step_id,
        action=request.action,
        domain=request.domain,
        endpoint=request.endpoint,
        transport_state=transport_state,
        semantic_outcome=derive_semantic_outcome(
            request.action,
            raw_result,
        ),
        specialist_status=extract_specialist_status(raw_result),
        legacy_accepted=legacy_accepted,
        result=dict(raw_result),
        error=error,
        attempt_count=attempt_count,
        duration_ms=duration_ms,
        evidence_metadata=evidence_metadata,
        provenance_metadata=provenance_metadata,
    )