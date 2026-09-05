# PROMATI_BOUNDED_RESEARCH_RUNTIME_6B2
from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from typing import Any

from app.orchestrator.executor import Sender, execute_plan
from app.orchestrator.models import Domain, ExecutionStep, QueryPlan
from app.orchestrator.research import run_bounded_research
from app.orchestrator.research_agent import (
    MAX_RESEARCH_ROUNDS,
    MAX_TOTAL_SPECIALIST_CALLS,
    ResearchBudget,
    ResearchCallGuard,
    ResearchPlannerDecision,
    ResearchToolCall,
    enforce_research_tool_call_guard,
    normalize_research_call_guard,
    plan_research_next_step,
)


SynthesisCallable = Callable[[QueryPlan, list[dict[str, Any]]], dict[str, Any]]

# PROMATI_TASK_RESEARCH_CALL_GUARD_RUNTIME_V7
_ACTION_DOMAINS: dict[str, Domain] = {
    "product_assistant": Domain.PRODUCT,
    "analysis_assistant": Domain.INSPECTION,
    "technical_assistant": Domain.TECHNICAL,
    "rfq_assistant": Domain.RFQ,
    "org_assistant": Domain.ORG,
    "diagnostics_assistant": Domain.DIAGNOSTICS,
}

DEFAULT_AGENT_DEADLINE_SECONDS = 75
MIN_AGENT_DEADLINE_SECONDS = 15
MAX_AGENT_DEADLINE_SECONDS = 180


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(value, maximum))


def _copy_plan(plan: QueryPlan) -> QueryPlan:
    if hasattr(plan, "model_copy"):
        return plan.model_copy(deep=True)
    return plan.copy(deep=True)


def _call_fingerprint(action: str, params: dict[str, Any]) -> str:
    return json.dumps(
        {
            "action": str(action),
            "params": params,
        },
        ensure_ascii=False,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )


def _initial_fingerprints(plan: QueryPlan) -> set[str]:
    fingerprints: set[str] = set()

    for step in plan.execution_steps or []:
        fingerprints.add(
            _call_fingerprint(
                step.action,
                dict(step.params or {}),
            )
        )

    return fingerprints


def _single_follow_up_plan(
    base_plan: QueryPlan,
    call: ResearchToolCall,
    *,
    round_number: int,
    call_number: int,
) -> QueryPlan:
    domain = _ACTION_DOMAINS.get(call.action)
    if domain is None:
        raise ValueError(
            f"Runtime weigert niet-allowlisted research-action: {call.action}"
        )

    follow_plan = _copy_plan(base_plan)
    follow_plan.clarification_required = False
    follow_plan.clarification_question = None
    follow_plan.execution_steps = [
        ExecutionStep(
            step_id=(
                f"research_r{round_number}_call_{call_number}_"
                f"{call.action}"
            ),
            domain=domain,
            action=call.action,
            params=dict(call.params),
            required=True,
            fallback_allowed=False,
        )
    ]
    return follow_plan


# PROMATI_TASK_RESEARCH_TYPED_FOLLOW_UP_OBSERVER_SHADOW_V9
def _execute_follow_up_call(
    base_plan: QueryPlan,
    call: ResearchToolCall,
    *,
    round_number: int,
    call_number: int,
    sender: Sender | None,
    call_guard: ResearchCallGuard | None = None,
    shadow_observer=None,
) -> list[dict[str, Any]]:
    # Defense in depth: enforce the same task action/scope immediately before
    # any follow-up ExecutionPlan can reach execute_plan.
    enforce_research_tool_call_guard(call, call_guard)

    follow_plan = _single_follow_up_plan(
        base_plan,
        call,
        round_number=round_number,
        call_number=call_number,
    )

    results, _trace = execute_plan(
        follow_plan,
        sender=sender,
        shadow_observer=shadow_observer,
    )

    enriched: list[dict[str, Any]] = []
    for item in results:
        if not isinstance(item, dict):
            continue

        copy = dict(item)
        copy["research_follow_up"] = {
            "round_number": round_number,
            "call_number": call_number,
            "reason": call.reason,
        }
        enriched.append(copy)

    return enriched


def _decision_record(
    decision: ResearchPlannerDecision,
    *,
    round_number: int,
) -> dict[str, Any]:
    record = decision.to_dict()
    record["round_number"] = round_number
    return record


def run_bounded_research_agent(
    plan: QueryPlan,
    initial_results: list[dict[str, Any]],
    sender: Sender | None = None,
    *,
    planner=None,
    synthesizer: SynthesisCallable | None = None,
    call_guard: ResearchCallGuard | None = None,
    shadow_observer=None,
) -> dict[str, Any]:
    """Run the bounded 6B.2 research runtime.

    Safety properties:
    - existing deterministic specialist run is round 0;
    - planner output is validated by research_agent.py before execution;
    - runtime executes only validated calls through the existing executor;
    - no arbitrary endpoint, URL or SQL execution is implemented here;
    - total specialist budget is enforced again at runtime;
    - exact duplicate calls are not executed twice;
    - round 2 can never trigger another follow-up;
    - final synthesis still passes through the existing 6A/6A.1 safeguards.

    6B.2 remains standalone: service.py is intentionally not switched yet.
    """
    synthesis_callable = synthesizer or run_bounded_research
    normalized_call_guard = (
        normalize_research_call_guard(call_guard)
        if call_guard is not None
        else None
    )

    if not plan.research_required:
        result = dict(
            synthesis_callable(
                plan,
                list(initial_results or []),
            )
        )
        result["agent"] = {
            "enabled": False,
            "mode": "bounded_agent_6b2",
            "planner_ai_calls_used": 0,
            "follow_up_specialist_calls": 0,
            "total_specialist_calls": len(plan.execution_steps or []),
            "rounds": [],
        }
        return result

    combined_results = list(initial_results or [])
    initial_specialist_calls = len(plan.execution_steps or [])
    follow_up_specialist_calls = 0
    planner_ai_calls_used = 0
    rounds: list[dict[str, Any]] = []

    seen_fingerprints = _initial_fingerprints(plan)
    deadline_seconds = _env_int(
        "AI_RESEARCH_AGENT_DEADLINE_SECONDS",
        DEFAULT_AGENT_DEADLINE_SECONDS,
        MIN_AGENT_DEADLINE_SECONDS,
        MAX_AGENT_DEADLINE_SECONDS,
    )
    started = time.monotonic()
    deadline_reached = False

    for round_number in range(1, MAX_RESEARCH_ROUNDS + 1):
        budget = ResearchBudget(
            round_number=round_number,
            initial_specialist_calls=initial_specialist_calls,
            follow_up_specialist_calls=follow_up_specialist_calls,
            planner_ai_calls_used=planner_ai_calls_used,
        )

        decision = plan_research_next_step(
            plan,
            combined_results,
            budget,
            planner=planner,
            call_guard=normalized_call_guard,
        )
        planner_ai_calls_used += max(
            0,
            int(decision.planner_ai_calls_used or 0),
        )

        record = _decision_record(
            decision,
            round_number=round_number,
        )
        record["executed_calls"] = 0
        record["duplicate_calls_skipped"] = 0
        record["deadline_reached"] = False

        if (
            decision.status != "ok"
            or decision.decision != "follow_up"
        ):
            rounds.append(record)
            break

        remaining_hard_budget = max(
            0,
            MAX_TOTAL_SPECIALIST_CALLS
            - initial_specialist_calls
            - follow_up_specialist_calls,
        )
        if normalized_call_guard is not None:
            remaining_guard_budget = max(
                0,
                normalized_call_guard.max_follow_up_calls
                - follow_up_specialist_calls,
            )
            remaining_hard_budget = min(
                remaining_hard_budget,
                remaining_guard_budget,
            )

        if remaining_hard_budget <= 0:
            record["runtime_blocked_reason"] = (
                "total_tool_budget_exhausted"
            )
            rounds.append(record)
            break

        executable_calls: list[ResearchToolCall] = []

        for call in decision.calls:
            fingerprint = _call_fingerprint(
                call.action,
                dict(call.params),
            )
            if fingerprint in seen_fingerprints:
                record["duplicate_calls_skipped"] += 1
                continue

            seen_fingerprints.add(fingerprint)
            executable_calls.append(call)

        executable_calls = executable_calls[
            :remaining_hard_budget
        ]

        if not executable_calls:
            record["runtime_blocked_reason"] = (
                "no_new_follow_up_calls"
            )
            rounds.append(record)
            break

        for call_number, call in enumerate(
            executable_calls,
            start=1,
        ):
            elapsed = time.monotonic() - started
            if elapsed >= deadline_seconds:
                deadline_reached = True
                record["deadline_reached"] = True
                record["runtime_blocked_reason"] = (
                    "agent_deadline_reached"
                )
                break

            follow_results = _execute_follow_up_call(
                plan,
                call,
                round_number=round_number,
                call_number=call_number,
                sender=sender,
                call_guard=normalized_call_guard,
                shadow_observer=shadow_observer,
            )

            follow_up_specialist_calls += 1
            record["executed_calls"] += 1
            combined_results.extend(follow_results)

        rounds.append(record)

        if deadline_reached or record["executed_calls"] == 0:
            break

    synthesis = dict(
        synthesis_callable(
            plan,
            combined_results,
        )
    )

    synthesis_ai_calls_used = max(
        0,
        int(synthesis.get("ai_calls_used") or 0),
    )

    synthesis["mode"] = "bounded_agent_6b2"
    synthesis["agent"] = {
        "enabled": True,
        "mode": "bounded_agent_6b2",
        "initial_specialist_calls": initial_specialist_calls,
        "follow_up_specialist_calls": follow_up_specialist_calls,
        "total_specialist_calls": (
            initial_specialist_calls
            + follow_up_specialist_calls
        ),
        "max_total_specialist_calls": MAX_TOTAL_SPECIALIST_CALLS,
        "planner_ai_calls_used": planner_ai_calls_used,
        "synthesis_ai_calls_used": synthesis_ai_calls_used,
        "total_ai_calls_used": (
            planner_ai_calls_used
            + synthesis_ai_calls_used
        ),
        "max_research_rounds": MAX_RESEARCH_ROUNDS,
        "deadline_seconds": deadline_seconds,
        "deadline_reached": deadline_reached,
        "rounds": rounds,
    }

    return synthesis
