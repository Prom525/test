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
    return compact


def shape_orchestrator_response(response: Any, response_profile: str) -> Any:
    if response_profile == "debug":
        return response
    return compact_orchestrator_response(response)
