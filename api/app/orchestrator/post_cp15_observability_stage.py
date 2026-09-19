"""Best-effort observability immediately after the CP15 boundary."""

from typing import Any, Callable


def run_post_cp15_observability_stage(
    counts: Any,
    plan: Any,
    evidence_pipeline: Any,
    *,
    record_task_execution_plan_shadow_observability: Callable[..., Any],
    record_public_composition_canary_release_observability: Callable[..., Any],
) -> None:
    try:
        record_task_execution_plan_shadow_observability(
            counts,
            plan,
            evidence_pipeline,
        )
    except Exception:
        pass

    try:
        record_public_composition_canary_release_observability(
            counts,
            plan,
            evidence_pipeline,
        )
    except Exception:
        pass


__all__ = ["run_post_cp15_observability_stage"]
