from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import Any
from uuid import uuid4

from sqlalchemy import text

from app.db import SessionLocal
from app.orchestrator.error_taxonomy import classify_response
from app.orchestrator.privacy_policy import (
    PRIVACY_CONTRACT_VERSION,
    sanitize_run_record,
)


RUN_LOG_CONTRACT_VERSION = (
    "promati.orchestrator.run_log.v1"
)

OPERATION_ID = (
    "promati_orchestrator_ask"
)

logger = logging.getLogger(
    __name__
)


INSERT_SQL = text(
    """
    INSERT INTO observability.orchestrator_runs (
        run_id,
        run_log_contract_version,
        observability_contract_version,
        operation_id,
        privacy_contract_version,
        health_contract_version,
        health_status,
        error_category,
        status,
        context_type,
        query_class,
        primary_domain,
        intent,
        domains,
        clarification_required,
        research_required,
        research_status,
        service_duration_ms,
        execution_attempts,
        initial_specialist_calls,
        research_follow_up_specialist_calls,
        total_specialist_calls,
        initial_raw_result_rows,
        initial_evidence_items,
        reconciled_evidence_items,
        total_ai_calls,
        response_bytes,
        timings_ms,
        counts
    )
    VALUES (
        :run_id,
        :run_log_contract_version,
        :observability_contract_version,
        :operation_id,
        :privacy_contract_version,
        :health_contract_version,
        :health_status,
        :error_category,
        :status,
        :context_type,
        :query_class,
        :primary_domain,
        :intent,
        CAST(:domains_json AS jsonb),
        :clarification_required,
        :research_required,
        :research_status,
        :service_duration_ms,
        :execution_attempts,
        :initial_specialist_calls,
        :research_follow_up_specialist_calls,
        :total_specialist_calls,
        :initial_raw_result_rows,
        :initial_evidence_items,
        :reconciled_evidence_items,
        :total_ai_calls,
        :response_bytes,
        CAST(:timings_json AS jsonb),
        CAST(:counts_json AS jsonb)
    )
    """
)


def _mapping(
    value: Any,
) -> Mapping[str, Any]:

    if isinstance(
        value,
        Mapping,
    ):
        return value

    return {}


def _safe_text(
    value: Any,
    *,
    max_length: int = 128,
) -> str | None:

    if value is None:
        return None

    cleaned = str(
        value
    ).strip()

    if not cleaned:
        return None

    return cleaned[
        :max_length
    ]


def _safe_int(
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


def _metric_map(
    value: Any,
) -> dict[str, int]:

    source = _mapping(
        value
    )

    result: dict[str, int] = {}

    for key, raw_value in source.items():

        if not isinstance(
            key,
            str,
        ):
            continue

        result[
            key[:128]
        ] = _safe_int(
            raw_value
        )

    return result


def _safe_domains(
    value: Any,
) -> list[str]:

    if not isinstance(
        value,
        (
            list,
            tuple,
        ),
    ):
        return []

    result: list[str] = []

    for item in value:

        cleaned = _safe_text(
            item,
            max_length=64,
        )

        if (
            cleaned
            and cleaned not in result
        ):
            result.append(
                cleaned
            )

        if len(
            result
        ) >= 16:
            break

    return result


def _response_bytes(
    response: Mapping[str, Any],
) -> int:

    try:

        encoded = json.dumps(
            response,
            ensure_ascii=False,
            separators=(
                ",",
                ":",
            ),
            default=str,
        ).encode(
            "utf-8"
        )

        return len(
            encoded
        )

    except Exception:
        return 0


def build_orchestrator_run_record(
    response: Mapping[str, Any],
) -> dict[str, Any]:

    query_plan = _mapping(
        response.get(
            "query_plan"
        )
    )

    observability = _mapping(
        response.get(
            "observability"
        )
    )

    research = _mapping(
        response.get(
            "research"
        )
    )

    clarification = _mapping(
        response.get(
            "clarification"
        )
    )

    health = classify_response(
        response
    )

    timings = _metric_map(
        observability.get(
            "timings_ms"
        )
    )

    counts = _metric_map(
        observability.get(
            "counts"
        )
    )

    domains = _safe_domains(
        query_plan.get(
            "domains"
        )
    )

    record = {
        "run_id":
            (
                _safe_text(
                    response.get(
                        "trace_id"
                    )
                )
                or str(
                    uuid4()
                )
            ),

        "run_log_contract_version":
            RUN_LOG_CONTRACT_VERSION,

        "privacy_contract_version":
            PRIVACY_CONTRACT_VERSION,

        "observability_contract_version":
            _safe_text(
                observability.get(
                    "contract_version"
                )
            ),

        "operation_id":
            OPERATION_ID,

        "health_contract_version":
            _safe_text(
                health.get(
                    "contract_version"
                )
            ),

        "health_status":
            _safe_text(
                health.get(
                    "status"
                )
            ),

        "error_category":
            _safe_text(
                health.get(
                    "category"
                )
            ),

        "status":
            (
                _safe_text(
                    response.get(
                        "status"
                    )
                )
                or "unknown"
            ),

        "context_type":
            _safe_text(
                response.get(
                    "context_type"
                )
            ),

        "query_class":
            _safe_text(
                query_plan.get(
                    "query_class"
                )
            ),

        "primary_domain":
            _safe_text(
                query_plan.get(
                    "primary_domain"
                )
            ),

        "intent":
            _safe_text(
                query_plan.get(
                    "intent"
                )
            ),

        "domains_json":
            json.dumps(
                domains,
                ensure_ascii=False,
            ),

        "clarification_required":
            bool(
                query_plan.get(
                    "clarification_required"
                )
                or clarification.get(
                    "required"
                )
            ),

        "research_required":
            bool(
                query_plan.get(
                    "research_required"
                )
                or research.get(
                    "required"
                )
            ),

        "research_status":
            _safe_text(
                research.get(
                    "status"
                )
            ),

        "service_duration_ms":
            _safe_int(
                timings.get(
                    "total"
                )
            ),

        "execution_attempts":
            _safe_int(
                counts.get(
                    "execution_attempts"
                )
            ),

        "initial_specialist_calls":
            _safe_int(
                counts.get(
                    "initial_specialist_calls"
                )
            ),

        "research_follow_up_specialist_calls":
            _safe_int(
                counts.get(
                    "research_follow_up_specialist_calls"
                )
            ),

        "total_specialist_calls":
            _safe_int(
                counts.get(
                    "total_specialist_calls"
                )
            ),

        "initial_raw_result_rows":
            _safe_int(
                counts.get(
                    "initial_raw_result_rows"
                )
            ),

        "initial_evidence_items":
            _safe_int(
                counts.get(
                    "initial_evidence_items"
                )
            ),

        "reconciled_evidence_items":
            _safe_int(
                counts.get(
                    "reconciled_evidence_items"
                )
            ),

        "total_ai_calls":
            _safe_int(
                counts.get(
                    "total_ai_calls"
                )
            ),

        "response_bytes":
            _response_bytes(
                response
            ),

        "timings_json":
            json.dumps(
                timings,
                ensure_ascii=False,
            ),

        "counts_json":
            json.dumps(
                counts,
                ensure_ascii=False,
            ),
        }

    return sanitize_run_record(
        record
    )


def persist_orchestrator_run(
    response: Mapping[str, Any],
) -> bool:
    """
    Fail-open persistent operational logging.

    Geen vraag, antwoord, trace, entities,
    scopewaarden of ruwe specialistdata worden
    opgeslagen.
    """
    try:

        record = (
            build_orchestrator_run_record(
                response
            )
        )

    except Exception as exc:

        logger.warning(
            "orchestrator run record build failed: %s",
            type(
                exc
            ).__name__,
        )

        return False


    db = None

    try:

        db = SessionLocal()

        db.execute(
            INSERT_SQL,
            record,
        )

        db.commit()

        return True

    except Exception as exc:

        if db is not None:

            try:
                db.rollback()
            except Exception:
                pass

        logger.warning(
            "orchestrator run persistence failed: %s",
            type(
                exc
            ).__name__,
        )

        return False

    finally:

        if db is not None:

            try:
                db.close()
            except Exception:
                pass
