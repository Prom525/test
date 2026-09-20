"""Build the final public response before outer observability."""

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class FinalResponseBuildStageResult:
    response: Any


def run_final_response_build_stage(
    payload: Any,
    cp11_debug_response: Any,
    evidence_pipeline: Any,
    task_coverage_gate_cp10: Any,
    results: Any,
    plan: Any,
    status: Any,
    answer: Any,
    question: Any,
    research: Any,
    clarification: Any,
    task_execution_shadow: Any,
    task_planner_canary: Any,
    trace: Any,
    timings: Any,
    *,
    observability_now: Callable[..., Any],
    compact_evidence_pipeline_for_public_response: Callable[..., Any],
    compact_results_for_public_response: Callable[..., Any],
    model_to_dict: Callable[..., Any],
    observability_elapsed_ms: Callable[..., Any],
) -> FinalResponseBuildStageResult:
    response_build_started = observability_now()

    try:
        debug_response = cp11_debug_response
        if debug_response and not isinstance(evidence_pipeline, dict):
            evidence_pipeline = {
                "task_coverage_gate_cp10": task_coverage_gate_cp10,
            }

        public_evidence_pipeline = (
            evidence_pipeline
            if payload.include_trace or debug_response
            else compact_evidence_pipeline_for_public_response(
                evidence_pipeline
            )
        )

        public_results = (
            results
            if payload.include_trace
            else compact_results_for_public_response(
                results,
                requested_information=plan.requested_information,
            )
        )

        response = {
            "status": status,
            "answer": answer,
            "context_type": "orchestrator",
            "question": question,
            "query_plan": model_to_dict(plan),
            "research": research,
            "clarification": clarification,
            "results": public_results,
            "evidence_pipeline": public_evidence_pipeline,
            "task_execution_shadow": task_execution_shadow,
            "task_planner_canary": task_planner_canary,
        }

        if payload.include_trace:
            response["trace"] = model_to_dict(trace)
        else:
            response["trace"] = None

    finally:
        timings["response_build"] = observability_elapsed_ms(
            response_build_started
        )

    return FinalResponseBuildStageResult(response=response)


__all__ = [
    "FinalResponseBuildStageResult",
    "run_final_response_build_stage",
]
