from __future__ import annotations

from typing import Any, Iterable

from app.orchestrator.execution_contracts import (
    ExecutionOutcome,
    ExecutionResult,
    ExecutionTransportState,
)


def has_service_accepted_execution(
    typed_results: Iterable[ExecutionResult],
    legacy_results: list[dict[str, Any]],
) -> bool:
    """
    Service-status compatibility policy.

    Typed ExecutionResult is authoritative when a typed
    result exists for the same execution step.

    P2.1b intentionally preserves the historical service
    acceptance semantics:
    - completed SUCCESS => accepted;
    - completed non-ERROR semantic outcomes also remain
      accepted for now, because clarification/not-found/
      ambiguity have their own or future status handling;
    - ERROR => not accepted;
    - when typed derivation is unavailable for a step,
      legacy accepted is the fail-open compatibility path.

    This function does NOT define final public semantics for
    NOT_FOUND, AMBIGUOUS, UNAVAILABLE, etc.
    """

    typed_by_step: dict[str, ExecutionResult] = {
        item.step_id: item
        for item in typed_results
        if isinstance(item, ExecutionResult)
    }

    for legacy_item in legacy_results:
        if not isinstance(
            legacy_item,
            dict,
        ):
            continue

        step_id = str(
            legacy_item.get("step_id")
            or ""
        )

        typed = typed_by_step.get(
            step_id
        )

        if typed is not None:
            if (
                typed.transport_state
                is ExecutionTransportState.COMPLETED
                and typed.semantic_outcome
                is not ExecutionOutcome.ERROR
            ):
                return True

            # Typed result exists: do not let a contradictory
            # legacy accepted=True override typed ERROR/FAILED.
            continue

        # Fail-open only when no typed result was produced
        # for this execution step.
        if legacy_item.get("accepted") is True:
            return True

    return False
