from __future__ import annotations

import traceback
from collections.abc import Mapping
from typing import Any


HEALTH_CONTRACT_VERSION = (
    "promati.orchestrator.health.v1"
)


ERROR_CATEGORIES = (
    "routing_error",
    "clarification_required",
    "specialist_unavailable",
    "contract_violation",
    "evidence_insufficient",
    "research_failed",
    "timeout",
    "response_projection_error",
    "unexpected_exception",
)


ATTENTION_CATEGORIES = {
    "clarification_required",
    "evidence_insufficient",
}


STATUS_ALIASES = {
    "routing_error":
        "routing_error",

    "route_error":
        "routing_error",

    "unsupported_route":
        "routing_error",

    "clarification_required":
        "clarification_required",

    "unavailable":
        "specialist_unavailable",

    "specialist_unavailable":
        "specialist_unavailable",

    "contract_violation":
        "contract_violation",

    "invalid_contract":
        "contract_violation",

    "evidence_insufficient":
        "evidence_insufficient",

    "research_failed":
        "research_failed",

    "timeout":
        "timeout",

    "timed_out":
        "timeout",

    "response_projection_error":
        "response_projection_error",

    "unexpected_exception":
        "unexpected_exception",
}


PROJECTION_FRAMES = {
    "_build_user_answer",
    "_project_public_results",
    "_project_public_evidence_pipeline",
    "project_public_results",
}


def _mapping(
    value: Any,
) -> Mapping[str, Any]:

    if isinstance(
        value,
        Mapping,
    ):
        return value

    return {}


def _status(
    value: Any,
) -> str:

    if value is None:
        return ""

    return str(
        value
    ).strip().lower()


def _health(
    category: str | None,
) -> dict[str, Any]:

    if category is None:

        health_status = (
            "healthy"
        )

    elif category in ATTENTION_CATEGORIES:

        health_status = (
            "attention"
        )

    else:

        health_status = (
            "error"
        )


    return {
        "contract_version":
            HEALTH_CONTRACT_VERSION,

        "status":
            health_status,

        "category":
            category,
    }


def _category_from_status(
    value: Any,
) -> str | None:

    return STATUS_ALIASES.get(
        _status(
            value
        )
    )


def _existing_health(
    response: Mapping[str, Any],
) -> dict[str, Any] | None:

    health = _mapping(
        response.get(
            "health"
        )
    )

    if not health:
        return None


    if (
        health.get(
            "contract_version"
        )
        != HEALTH_CONTRACT_VERSION
    ):
        return None


    category = health.get(
        "category"
    )

    if (
        category is not None
        and category not in ERROR_CATEGORIES
    ):
        return None


    status = _status(
        health.get(
            "status"
        )
    )

    if status not in {
        "healthy",
        "attention",
        "error",
    }:

        return None


    return {
        "contract_version":
            HEALTH_CONTRACT_VERSION,

        "status":
            status,

        "category":
            category,
    }


def _result_categories(
    response: Mapping[str, Any],
) -> tuple[str, ...]:

    raw_results = response.get(
        "results"
    )

    if not isinstance(
        raw_results,
        (
            list,
            tuple,
        ),
    ):
        return ()


    categories: list[str] = []


    for item in raw_results:

        item_map = _mapping(
            item
        )

        result_map = _mapping(
            item_map.get(
                "result"
            )
        )


        values = (
            item_map.get(
                "status"
            ),
            item_map.get(
                "semantic_outcome"
            ),
            result_map.get(
                "status"
            ),
            result_map.get(
                "semantic_outcome"
            ),
        )


        for value in values:

            category = (
                _category_from_status(
                    value
                )
            )

            if (
                category
                and category not in categories
            ):

                categories.append(
                    category
                )


    return tuple(
        categories
    )


def classify_response(
    response: Mapping[str, Any],
) -> dict[str, Any]:

    existing = _existing_health(
        response
    )

    if existing is not None:
        return existing


    top_status = _status(
        response.get(
            "status"
        )
    )

    clarification = _mapping(
        response.get(
            "clarification"
        )
    )


    if (
        top_status
        == "clarification_required"
        or clarification.get(
            "required"
        )
        is True
    ):

        return _health(
            "clarification_required"
        )


    top_category = (
        _category_from_status(
            top_status
        )
    )

    if (
        top_category
        and top_category
        != "clarification_required"
    ):

        return _health(
            top_category
        )


    result_categories = (
        _result_categories(
            response
        )
    )


    for category in (
        "timeout",
        "contract_violation",
        "specialist_unavailable",
        "response_projection_error",
        "routing_error",
    ):

        if category in result_categories:

            return _health(
                category
            )


    research = _mapping(
        response.get(
            "research"
        )
    )

    if _status(
        research.get(
            "status"
        )
    ) in {
        "failed",
        "error",
        "research_failed",
    }:

        return _health(
            "research_failed"
        )


    pipeline = _mapping(
        response.get(
            "evidence_pipeline"
        )
    )

    research_execution = _mapping(
        pipeline.get(
            "research_execution"
        )
    )

    if _status(
        research_execution.get(
            "status"
        )
    ) in {
        "failed",
        "error",
        "research_failed",
    }:

        return _health(
            "research_failed"
        )


    reconciliation = _mapping(
        pipeline.get(
            "reconciliation"
        )
    )

    reconciled_assessment = _mapping(
        reconciliation.get(
            "reconciled_assessment"
        )
    )

    initial_assessment = _mapping(
        pipeline.get(
            "initial_assessment"
        )
    )

    synthesis = _mapping(
        pipeline.get(
            "synthesis"
        )
    )


    evidence_statuses = (
        _status(
            reconciled_assessment.get(
                "status"
            )
        ),
        _status(
            initial_assessment.get(
                "status"
            )
        ),
        _status(
            synthesis.get(
                "status"
            )
        ),
    )


    if any(
        value
        in {
            "insufficient",
            "evidence_insufficient",
        }
        for value
        in evidence_statuses
    ):

        return _health(
            "evidence_insufficient"
        )


    if (
        top_status
        == "error"
    ):

        return _health(
            "routing_error"
        )


    return _health(
        None
    )


def classify_exception(
    exc: BaseException,
) -> dict[str, Any]:

    if isinstance(
        exc,
        TimeoutError,
    ):

        return _health(
            "timeout"
        )


    type_name = (
        type(
            exc
        )
        .__name__
        .lower()
    )


    try:

        frames = traceback.extract_tb(
            exc.__traceback__
        )

    except Exception:

        frames = []


    if any(
        frame.name
        in PROJECTION_FRAMES
        for frame
        in frames
    ):

        return _health(
            "response_projection_error"
        )


    if (
        "timeout"
        in type_name
    ):

        return _health(
            "timeout"
        )


    if (
        "contract"
        in type_name
    ):

        return _health(
            "contract_violation"
        )


    if (
        "routing"
        in type_name
        or "route"
        in type_name
    ):

        return _health(
            "routing_error"
        )


    if (
        "unavailable"
        in type_name
    ):

        return _health(
            "specialist_unavailable"
        )


    if (
        "research"
        in type_name
    ):

        return _health(
            "research_failed"
        )


    if (
        "evidence"
        in type_name
        and "insufficient"
        in type_name
    ):

        return _health(
            "evidence_insufficient"
        )


    return _health(
        "unexpected_exception"
    )


def build_exception_run_response(
    exc: BaseException,
) -> dict[str, Any]:

    return {
        "status":
            "error",

        "context_type":
            "orchestrator",

        "health":
            classify_exception(
                exc
            ),
    }
