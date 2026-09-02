from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.orchestrator.evidence_research_gate import (
    ResearchGateDecision,
    ResearchGateStatus,
)


RESEARCH_EXECUTION_CONTRACT_VERSION = (
    "promati.phase_c5."
    "bounded_research_execution_contract.v1"
)


class ResearchExecutionStatus(str, Enum):
    SKIPPED = "skipped"
    COMPLETED = "completed"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class ResearchExecutionResult:
    contract_version: str
    requirement_set_id: str
    intent: str
    status: ResearchExecutionStatus
    research_performed: bool
    target_requirement_ids: tuple[str, ...]
    initial_results: tuple[dict[str, Any], ...]
    combined_results: tuple[dict[str, Any], ...]
    agent_metadata: dict[str, Any] | None
    blocked_reason: str | None


ResearchRuntime = Callable[..., dict[str, Any]]


def _detached_results(
    results: Any,
) -> tuple[dict[str, Any], ...]:
    if not isinstance(results, (list, tuple)):
        return ()

    return tuple(
        deepcopy(item)
        for item in results
        if isinstance(item, dict)
    )


def _raw_result_passthrough(
    plan: Any,
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "results": [
            deepcopy(item)
            for item in (results or [])
            if isinstance(item, dict)
        ],
        "ai_calls_used": 0,
    }


def execute_bounded_research(
    decision: ResearchGateDecision,
    plan: Any,
    initial_results: list[dict[str, Any]],
    sender: Any = None,
    *,
    planner: Any = None,
    runtime: ResearchRuntime | None = None,
) -> ResearchExecutionResult:
    detached_initial = _detached_results(
        initial_results
    )

    if (
        decision.status
        is ResearchGateStatus.NOT_REQUIRED
        or not decision.research_required
    ):
        return ResearchExecutionResult(
            contract_version=(
                RESEARCH_EXECUTION_CONTRACT_VERSION
            ),
            requirement_set_id=(
                decision.requirement_set_id
            ),
            intent=decision.intent,
            status=ResearchExecutionStatus.SKIPPED,
            research_performed=False,
            target_requirement_ids=tuple(
                sorted(
                    set(
                        decision.target_requirement_ids
                    )
                )
            ),
            initial_results=detached_initial,
            combined_results=_detached_results(
                detached_initial
            ),
            agent_metadata=None,
            blocked_reason=None,
        )

    if runtime is None:
        from app.orchestrator.research_runtime import (
            run_bounded_research_agent,
        )

        runtime_callable = (
            run_bounded_research_agent
        )
    else:
        runtime_callable = runtime

    try:
        runtime_plan = deepcopy(plan)
        setattr(
            runtime_plan,
            "research_required",
            True,
        )

        raw_result = runtime_callable(
            runtime_plan,
            [
                deepcopy(item)
                for item in detached_initial
            ],
            sender=sender,
            planner=planner,
            synthesizer=_raw_result_passthrough,
        )

        if not isinstance(raw_result, dict):
            raise TypeError(
                "research runtime returned non-dict"
            )

        combined_results = _detached_results(
            raw_result.get("results")
        )

        raw_agent = raw_result.get("agent")
        agent_metadata = (
            deepcopy(raw_agent)
            if isinstance(raw_agent, dict)
            else None
        )

        return ResearchExecutionResult(
            contract_version=(
                RESEARCH_EXECUTION_CONTRACT_VERSION
            ),
            requirement_set_id=(
                decision.requirement_set_id
            ),
            intent=decision.intent,
            status=ResearchExecutionStatus.COMPLETED,
            research_performed=True,
            target_requirement_ids=tuple(
                sorted(
                    set(
                        decision.target_requirement_ids
                    )
                )
            ),
            initial_results=detached_initial,
            combined_results=combined_results,
            agent_metadata=agent_metadata,
            blocked_reason=None,
        )
    except Exception as exc:
        return ResearchExecutionResult(
            contract_version=(
                RESEARCH_EXECUTION_CONTRACT_VERSION
            ),
            requirement_set_id=(
                decision.requirement_set_id
            ),
            intent=decision.intent,
            status=ResearchExecutionStatus.BLOCKED,
            research_performed=False,
            target_requirement_ids=tuple(
                sorted(
                    set(
                        decision.target_requirement_ids
                    )
                )
            ),
            initial_results=detached_initial,
            combined_results=_detached_results(
                detached_initial
            ),
            agent_metadata=None,
            blocked_reason=(
                "research_runtime_error:"
                + type(exc).__name__
            ),
        )