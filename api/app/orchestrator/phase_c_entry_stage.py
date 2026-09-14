"""Requirement gate and initial evidence normalization for Phase C."""

from dataclasses import dataclass
from typing import Any, Callable


__all__ = ["PhaseCEntryResult", "prepare_phase_c_entry"]


@dataclass(frozen=True)
class PhaseCEntryResult:
    requirement_set: Any
    retrieved_at: Any
    initial_evidence_items: tuple[Any, ...]
    working_evidence_items: tuple[Any, ...]


def prepare_phase_c_entry(
    plan: Any,
    results: Any,
    typed_execution_results: Any,
    timings: dict[str, int],
    counts: dict[str, int],
    *,
    observability_call: Callable[..., Any],
    get_requirement_set: Callable[..., Any],
    utc_now: Callable[[], Any],
    observability_now: Callable[[], float],
    observability_elapsed_ms: Callable[[float], int],
    normalize_execution_result_evidence: Callable[..., Any],
) -> PhaseCEntryResult | None:
    """Prepare the characterized Phase-C entry values, or close the gate."""
    requirement_set = observability_call(
        timings,
        "evidence_requirement_lookup",
        get_requirement_set,
        plan.intent,
    )

    specialist_research_blocked = any(
        isinstance(item.get("result"), dict)
        and str(item["result"].get("status", "")).lower()
        == "clarification_required"
        for item in results
        if isinstance(item, dict)
    )

    if (
        requirement_set is None
        or plan.clarification_required
        or specialist_research_blocked
    ):
        return None

    retrieved_at = utc_now()
    normalization_started = observability_now()
    initial_evidence_items: tuple[Any, ...] = ()

    try:
        initial_evidence_items = tuple(
            evidence_item
            for execution_result in typed_execution_results
            for evidence_item in normalize_execution_result_evidence(
                execution_result,
                retrieved_at=retrieved_at,
            )
        )
    finally:
        timings["evidence_normalization"] = observability_elapsed_ms(
            normalization_started
        )
        counts["initial_evidence_items"] = len(initial_evidence_items)

    working_evidence_items = initial_evidence_items
    return PhaseCEntryResult(
        requirement_set=requirement_set,
        retrieved_at=retrieved_at,
        initial_evidence_items=initial_evidence_items,
        working_evidence_items=working_evidence_items,
    )
