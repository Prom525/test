from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any


PRIVACY_CONTRACT_VERSION = (
    "promati.orchestrator.privacy.v1"
)


DEFAULT_RETENTION_DAYS = 90

MIN_RETENTION_DAYS = 7

MAX_RETENTION_DAYS = 3650


PERSISTED_RECORD_KEYS = (
    "run_id",
    "run_log_contract_version",
    "privacy_contract_version",
    "observability_contract_version",
    "operation_id",
    "health_contract_version",
    "health_status",
    "error_category",
    "status",
    "context_type",
    "query_class",
    "primary_domain",
    "intent",
    "domains_json",
    "clarification_required",
    "research_required",
    "research_status",
    "service_duration_ms",
    "execution_attempts",
    "initial_specialist_calls",
    "research_follow_up_specialist_calls",
    "total_specialist_calls",
    "initial_raw_result_rows",
    "initial_evidence_items",
    "reconciled_evidence_items",
    "total_ai_calls",
    "response_bytes",
    "timings_json",
    "counts_json",
)


FORBIDDEN_SOURCE_KEYS = frozenset(
    {
        "question",
        "vraag",
        "answer",
        "trace",
        "entities",
        "conversation_context",
        "scope_code",
        "scope_type",
        "area_code",
        "installation_code",
        "lijn_code",
        "band_code",
        "original_question",
        "normalized_question",
        "result",
        "results",
        "evidence_pipeline",
    }
)


TOKEN_FIELDS = frozenset(
    {
        "run_id",
        "run_log_contract_version",
        "privacy_contract_version",
        "observability_contract_version",
        "operation_id",
        "health_contract_version",
        "health_status",
        "error_category",
        "status",
        "context_type",
        "query_class",
        "primary_domain",
        "intent",
        "research_status",
    }
)


BOOLEAN_FIELDS = frozenset(
    {
        "clarification_required",
        "research_required",
    }
)


INTEGER_FIELDS = frozenset(
    {
        "service_duration_ms",
        "execution_attempts",
        "initial_specialist_calls",
        "research_follow_up_specialist_calls",
        "total_specialist_calls",
        "initial_raw_result_rows",
        "initial_evidence_items",
        "reconciled_evidence_items",
        "total_ai_calls",
        "response_bytes",
    }
)


TOKEN_PATTERN = re.compile(
    r"^[A-Za-z0-9_.:-]+$"
)


def _token(
    value: Any,
    *,
    max_length: int = 128,
) -> str | None:

    if value is None:
        return None


    text = str(
        value
    ).strip()


    if not text:
        return None


    if len(
        text
    ) > max_length:

        return None


    if not TOKEN_PATTERN.fullmatch(
        text
    ):

        return None


    return text


def _nonnegative_int(
    value: Any,
) -> int:

    try:

        parsed = int(
            value
        )

    except (
        TypeError,
        ValueError,
    ):

        return 0


    return max(
        0,
        parsed,
    )


def _json_value(
    value: Any,
) -> Any:

    if isinstance(
        value,
        str,
    ):

        try:

            return json.loads(
                value
            )

        except (
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ):

            return None


    return value


def _domains_json(
    value: Any,
) -> str:

    source = _json_value(
        value
    )


    if not isinstance(
        source,
        (
            list,
            tuple,
        ),
    ):

        source = []


    result: list[str] = []


    for item in source:

        token = _token(
            item,
            max_length=64,
        )

        if (
            token
            and token not in result
        ):

            result.append(
                token
            )


        if len(
            result
        ) >= 16:

            break


    return json.dumps(
        result,
        ensure_ascii=False,
    )


def _metric_json(
    value: Any,
) -> str:

    source = _json_value(
        value
    )


    if not isinstance(
        source,
        Mapping,
    ):

        source = {}


    result: dict[str, int] = {}


    for raw_key, raw_value in source.items():

        key = _token(
            raw_key,
            max_length=128,
        )

        if key is None:
            continue


        result[
            key
        ] = _nonnegative_int(
            raw_value
        )


        if len(
            result
        ) >= 128:

            break


    return json.dumps(
        result,
        ensure_ascii=False,
        sort_keys=True,
    )


def sanitize_run_record(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """
    P3.3 persistence boundary.

    Alleen expliciet toegestane operationele velden
    mogen deze functie verlaten. Vrije tekst en onbekende
    velden worden niet persistent gemaakt.
    """
    sanitized: dict[str, Any] = {}


    for key in PERSISTED_RECORD_KEYS:

        raw_value = record.get(
            key
        )


        if key == "privacy_contract_version":

            sanitized[
                key
            ] = (
                PRIVACY_CONTRACT_VERSION
            )

            continue


        if key in TOKEN_FIELDS:

            sanitized[
                key
            ] = _token(
                raw_value
            )

            continue


        if key in BOOLEAN_FIELDS:

            sanitized[
                key
            ] = bool(
                raw_value
            )

            continue


        if key in INTEGER_FIELDS:

            sanitized[
                key
            ] = _nonnegative_int(
                raw_value
            )

            continue


        if key == "domains_json":

            sanitized[
                key
            ] = _domains_json(
                raw_value
            )

            continue


        if key in {
            "timings_json",
            "counts_json",
        }:

            sanitized[
                key
            ] = _metric_json(
                raw_value
            )

            continue


    return sanitized


def validate_retention_days(
    value: Any,
) -> int:

    try:

        days = int(
            value
        )

    except (
        TypeError,
        ValueError,
    ):

        raise ValueError(
            "retention_days must be an integer"
        )


    if not (
        MIN_RETENTION_DAYS
        <= days
        <= MAX_RETENTION_DAYS
    ):

        raise ValueError(
            "retention_days outside allowed range"
        )


    return days
