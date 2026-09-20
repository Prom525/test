"""Attach the final observability envelope to the public response."""

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class FinalObservabilityEnvelopeStageResult:
    response: Any


def run_final_observability_envelope_stage(
    response: Any,
    timings: Any,
    counts: Any,
    run_started: Any,
    observability_contract_version: Any,
    *,
    observability_elapsed_ms: Callable[..., Any],
) -> FinalObservabilityEnvelopeStageResult:
    timings["total"] = observability_elapsed_ms(run_started)

    response["observability"] = {
        "contract_version": observability_contract_version,
        "timings_ms": dict(timings),
        "counts": dict(counts),
    }

    return FinalObservabilityEnvelopeStageResult(response=response)


__all__ = [
    "FinalObservabilityEnvelopeStageResult",
    "run_final_observability_envelope_stage",
]
