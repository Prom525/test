from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class PhaseCReconciliationStageResult:
    reconciliation: Any


def run_phase_c_reconciliation_stage(
    timings: Any,
    counts: Any,
    requirement_set: Any,
    working_evidence_items: Any,
    initial_assessment: Any,
    research_execution: Any,
    retrieved_at: Any,
    *,
    observability_call: Callable[..., Any],
    observability_get: Callable[..., Any],
    reconcile_evidence_callable: Callable[..., Any],
) -> PhaseCReconciliationStageResult:
    reconciliation = observability_call(
        timings,
        "reconciliation",
        reconcile_evidence_callable,
        requirement_set,
        working_evidence_items,
        initial_assessment,
        research_execution,
        retrieved_at=retrieved_at,
        target_entity_ids=None,
        now=retrieved_at,
    )
    reconciled_items = observability_get(
        reconciliation,
        "reconciled_evidence_items",
        (),
    )
    if isinstance(reconciled_items, (list, tuple)):
        counts["reconciled_evidence_items"] = len(reconciled_items)
    return PhaseCReconciliationStageResult(reconciliation)
