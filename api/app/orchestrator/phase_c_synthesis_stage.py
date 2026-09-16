from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class PhaseCSynthesisStageResult:
    synthesis: Any


def run_phase_c_synthesis_stage(
    timings: Any,
    reconciliation: Any,
    *,
    observability_call: Callable[..., Any],
    synthesize_grounded_evidence_callable: Callable[..., Any],
) -> PhaseCSynthesisStageResult:
    synthesis = observability_call(
        timings,
        "synthesis",
        synthesize_grounded_evidence_callable,
        reconciliation,
    )
    return PhaseCSynthesisStageResult(synthesis)
