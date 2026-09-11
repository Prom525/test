import time
from collections.abc import Callable
from typing import Any

import requests

from app.config import settings

from app.orchestrator.models import (
    OrchestratorTrace,
    QueryPlan,
    TraceAttempt,
)
from app.orchestrator.execution_contracts import (
    EXECUTION_CONTRACT_VERSION,
    ExecutionRequest,
    ExecutionTransportState,
    FallbackPolicy,
)
from app.orchestrator.execution_shadow import derive_execution_result


ACTION_ENDPOINTS = {
    "product_assistant": "/product/assistant/ask",
    "analysis_assistant": "/analysis/assistant/ask",

    # Later eenvoudig uitbreidbaar:
    "technical_assistant": "/technical/assistant/ask",
    "rfq_assistant": "/rfq/assistant/ask",
    "org_assistant": "/org/assistant/ask",
    "diagnostics_assistant": "/diagnostics/assistant/ask",
}


Sender = Callable[
    [str, dict[str, Any]],
    dict[str, Any],
]


def _api_base_url() -> str:
    return settings.PROMATI_API_BASE_URL.rstrip("/")


def default_sender(
    path: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    Kleine zelfstandige transportlaag.

    Bewust geen import uit hybrid_api.py:
    zo voorkomen we afhankelijkheid van router-private helpers
    en toekomstige cirkelimports.
    """
    url = f"{_api_base_url()}{path}"

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()

        data = response.json()

        if isinstance(data, dict):
            return data

        return {
            "status": "error",
            "context_type": "orchestrator_transport",
            "error": "Assistant response is geen JSON-object.",
        }

    except Exception as exc:
        return {
            "status": "error",
            "context_type": "orchestrator_transport",
            "path": path,
            "error": str(exc),
            "write_actions_available": False,
        }


def _infer_result_count(
    result: dict[str, Any],
) -> int | None:
    """
    Alleen observability.

    Deze functie bepaalt NIET of een resultaat inhoudelijk goed is.
    Een geldige zero-match (count=0) blijft dus een geaccepteerd
    assistant-resultaat.
    """
    article_search = result.get(
        "article_search_v2"
    )

    if isinstance(article_search, dict):
        count = article_search.get("count")

        if isinstance(count, int):
            return count

    for key in (
        "results",
        "rows",
        "items",
        "data",
    ):
        value = result.get(key)

        if isinstance(value, list):
            return len(value)

    count = result.get("count")

    if isinstance(count, int):
        return count

    return None


def _is_accepted(
    result: dict[str, Any],
) -> bool:
    status = str(
        result.get("status", "ok")
    ).lower()

    return status not in {
        "error",
        "failed",
        "failure",
    }


def execute_plan(
    plan: QueryPlan,
    sender: Sender | None = None,
) -> tuple[
    list[dict[str, Any]],
    OrchestratorTrace,
]:
    """
    Voert de reeds geplande stappen uit.

    V1:
    - geen query-relaxation;
    - geen automatische retry;
    - geen resultaatfusie;
    - wel volledige trace per stap.

    Fallback komt later als aparte orchestratorlaag boven deze executor.
    """
    transport = sender or default_sender

    trace = OrchestratorTrace()
    results: list[dict[str, Any]] = []

    if plan.clarification_required:
        trace.clarification_used = True
        return results, trace

    for step in plan.execution_steps:
        endpoint = ACTION_ENDPOINTS.get(
            step.action
        )

        started = time.perf_counter()

        if endpoint is None:
            duration_ms = int(
                (
                    time.perf_counter()
                    - started
                )
                * 1000
            )

            trace.attempts.append(
                TraceAttempt(
                    attempt_no=len(
                        trace.attempts
                    ) + 1,
                    step_id=step.step_id,
                    domain=step.domain,
                    action=step.action,
                    status="error",
                    request_summary=dict(
                        step.params
                    ),
                    accepted=False,
                    error=(
                        "Geen endpoint geregistreerd "
                        f"voor action={step.action}"
                    ),
                    duration_ms=duration_ms,
                )
            )

            continue

        result = transport(
            endpoint,
            dict(step.params),
        )

        duration_ms = int(
            (
                time.perf_counter()
                - started
            )
            * 1000
        )

        accepted = _is_accepted(result)
        result_count = _infer_result_count(
            result
        )

        trace.attempts.append(
            TraceAttempt(
                attempt_no=len(
                    trace.attempts
                ) + 1,
                step_id=step.step_id,
                domain=step.domain,
                action=step.action,
                status=str(
                    result.get(
                        "status",
                        "ok",
                    )
                ),
                request_summary=dict(
                    step.params
                ),
                result_count=result_count,
                accepted=accepted,
                error=(
                    str(result.get("error"))
                    if result.get("error")
                    else None
                ),
                duration_ms=duration_ms,
            )
        )

        try:
            _shadow_request = ExecutionRequest(
                contract_version=EXECUTION_CONTRACT_VERSION,
                step_id=step.step_id,
                domain=step.domain.value,
                action=step.action,
                endpoint=endpoint,
                params=dict(step.params),
                required=step.required,
                timeout_seconds=30.0,
                retry_count=0,
                fallback_policy=FallbackPolicy.UNRESOLVED,
                legacy_fallback_allowed=step.fallback_allowed,
            )

            _shadow_execution_result = derive_execution_result(
                request=_shadow_request,
                raw_result=result,
                legacy_accepted=accepted,
                transport_state=ExecutionTransportState.COMPLETED,
                duration_ms=duration_ms,
            )
        except Exception:
            _shadow_execution_result = None
        results.append(
            {
                "step_id": step.step_id,
                "domain": step.domain.value,
                "action": step.action,
                "endpoint": endpoint,
                "accepted": accepted,
                "result": result,
            }
        )

    return results, trace