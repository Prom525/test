"""CP15 release observation after concise public composition."""

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class CP15ReleaseObserverStageResult:
    evidence_pipeline: Any


def run_cp15_release_observer_stage(
    task_execution_shadow: Any,
    evidence_pipeline: Any,
    *,
    build_release_gate_cp15: Callable[..., Any],
) -> CP15ReleaseObserverStageResult:
    try:
        evidence_pipeline["release_gate_cp15"] = build_release_gate_cp15(
            task_execution_shadow, evidence_pipeline,
        )
    except Exception as exc:
        evidence_pipeline["release_gate_cp15"] = {
            "contract_version": "promati.orchestrator.release_gate.cp15.v1",
            "evaluated": False,
            "release_allowed": False,
            "public_authoritative": False,
            "blocking_reasons": ["cp15_internal_error_fail_closed"],
            "blocked_gate_ids": ["cp15"],
            "internal_error_type": type(exc).__name__,
        }
    return CP15ReleaseObserverStageResult(evidence_pipeline=evidence_pipeline)


__all__ = ["CP15ReleaseObserverStageResult", "run_cp15_release_observer_stage"]
