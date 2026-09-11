from __future__ import annotations

from typing import Any

MAX_COMPACT_ANSWER_CHARS = 8_000
MAX_COMPACT_TASKS = 12


def _compact_answer(value: Any) -> str:
    answer = str(value or "")
    if len(answer) <= MAX_COMPACT_ANSWER_CHARS:
        return answer
    return answer[:MAX_COMPACT_ANSWER_CHARS].rstrip() + "\n\n[antwoord ingekort]"


def _compact_tasks(query_plan: Any) -> list[dict[str, Any]]:
    if not isinstance(query_plan, dict) or not isinstance(query_plan.get("intent_tasks"), list):
        return []
    return [
        {
            key: task[key]
            for key in (
                "task_id",
                "domain",
                "intent",
                "primary",
                "required",
                "polarity",
            )
            if key in task
        }
        for task in query_plan["intent_tasks"][:MAX_COMPACT_TASKS]
        if isinstance(task, dict)
    ]


def _coverage(results: Any) -> dict[str, int]:
    rows = results if isinstance(results, list) else []
    return {
        "total": len(rows),
        "accepted": sum(isinstance(row, dict) and row.get("accepted") is True for row in rows),
        "failed": sum(isinstance(row, dict) and row.get("accepted") is False for row in rows),
    }


def _task_execution_shadow_summary(response: dict[str, Any]) -> dict[str, Any] | None:
    shadow = response.get("task_execution_shadow")
    if not isinstance(shadow, dict) or not isinstance(shadow.get("summary"), dict):
        return None
    summary = shadow["summary"]
    return {
        key: summary[key]
        for key in (
            "required_total",
            "required_planned",
            "required_executed",
            "required_missing",
            "missing_required_tasks",
        )
        if key in summary
    }


def compact_orchestrator_response(response: Any) -> Any:
    """Return the bounded, high-signal response used by public GPT Actions."""
    if not isinstance(response, dict):
        return response
    query_plan = response.get("query_plan")
    plan = query_plan if isinstance(query_plan, dict) else {}
    compact: dict[str, Any] = {
        "status": response.get("status"),
        "answer": _compact_answer(response.get("answer")),
        "response_profile": "compact",
        "domains": list(plan.get("domains") or [])[:8],
        "tasks": _compact_tasks(plan),
        "coverage": _coverage(response.get("results")),
    }
    for key in ("trace_id", "request_id"):
        if response.get(key):
            compact[key] = response[key]
    if response.get("clarification"):
        compact["clarification"] = response["clarification"]
    shadow_summary = _task_execution_shadow_summary(response)
    if shadow_summary is not None:
        compact["task_execution_shadow_summary"] = shadow_summary
    return compact


def shape_orchestrator_response(response: Any, response_profile: str) -> Any:
    if response_profile == "debug":
        return response
    return compact_orchestrator_response(response)
