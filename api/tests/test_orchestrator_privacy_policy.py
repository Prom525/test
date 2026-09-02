from __future__ import annotations

import json

import pytest

from app.orchestrator import privacy_policy
from app.orchestrator import run_logging


def test_privacy_contract_and_retention_are_exact():

    assert (
        privacy_policy
        .PRIVACY_CONTRACT_VERSION
        == "promati.orchestrator.privacy.v1"
    )

    assert (
        privacy_policy
        .DEFAULT_RETENTION_DAYS
        == 90
    )

    assert (
        privacy_policy
        .MIN_RETENTION_DAYS
        == 7
    )


def test_persisted_allowlist_contains_no_forbidden_fields():

    assert (
        privacy_policy
        .FORBIDDEN_SOURCE_KEYS
        .isdisjoint(
            set(
                privacy_policy
                .PERSISTED_RECORD_KEYS
            )
        )
    )


def test_unknown_and_raw_fields_are_dropped():

    sanitized = (
        privacy_policy
        .sanitize_run_record(
            {
                "run_id":
                    "12345678-1234-1234-1234-123456789012",

                "run_log_contract_version":
                    "promati.orchestrator.run_log.v1",

                "question":
                    "SECRET QUESTION",

                "answer":
                    "SECRET ANSWER",

                "trace":
                    "SECRET TRACE",

                "results":
                    "SECRET RESULTS",

                "unknown_field":
                    "SECRET UNKNOWN",
            }
        )
    )


    serialized = json.dumps(
        sanitized,
        ensure_ascii=False,
    )


    for secret in (
        "SECRET QUESTION",
        "SECRET ANSWER",
        "SECRET TRACE",
        "SECRET RESULTS",
        "SECRET UNKNOWN",
    ):

        assert (
            secret
            not in serialized
        )


    assert (
        set(
            sanitized
        )
        == set(
            privacy_policy
            .PERSISTED_RECORD_KEYS
        )
    )


def test_free_text_token_is_redacted():

    sanitized = (
        privacy_policy
        .sanitize_run_record(
            {
                "intent":
                    "customer john@example.com",
            }
        )
    )

    assert (
        sanitized[
            "intent"
        ]
        is None
    )


def test_metric_maps_accept_only_safe_keys_and_ints():

    sanitized = (
        privacy_policy
        .sanitize_run_record(
            {
                "counts_json":
                    json.dumps(
                        {
                            "total_ai_calls":
                                2,

                            "unsafe key":
                                99,

                            "negative":
                                -5,
                        }
                    )
            }
        )
    )


    counts = json.loads(
        sanitized[
            "counts_json"
        ]
    )


    assert (
        counts[
            "total_ai_calls"
        ]
        == 2
    )

    assert (
        counts[
            "negative"
        ]
        == 0
    )

    assert (
        "unsafe key"
        not in counts
    )


def test_retention_range_is_bounded():

    assert (
        privacy_policy
        .validate_retention_days(
            90
        )
        == 90
    )


    with pytest.raises(
        ValueError
    ):

        privacy_policy.validate_retention_days(
            0
        )


    with pytest.raises(
        ValueError
    ):

        privacy_policy.validate_retention_days(
            5000
        )


def test_run_record_has_privacy_contract_and_no_raw_data():

    response = {
        "status":
            "ok",

        "question":
            "SECRET QUESTION",

        "answer":
            "SECRET ANSWER",

        "trace": {
            "secret":
                "SECRET TRACE",
        },

        "results": [
            {
                "result":
                    "SECRET RESULT",
            }
        ],

        "query_plan": {
            "query_class":
                "business",

            "primary_domain":
                "inspection",

            "intent":
                "replacement_advice",

            "domains": [
                "inspection"
            ],

            "clarification_required":
                False,

            "research_required":
                False,
        },

        "research": {
            "status":
                "not_required",
        },

        "clarification": {
            "required":
                False,
        },

        "observability": {
            "contract_version":
                "promati.orchestrator.observability.v1",

            "timings_ms": {
                "total":
                    100,
            },

            "counts": {
                "total_ai_calls":
                    0,

                "total_specialist_calls":
                    1,
            },
        },
    }


    record = (
        run_logging
        .build_orchestrator_run_record(
            response
        )
    )


    serialized = json.dumps(
        record,
        ensure_ascii=False,
    )


    assert (
        record[
            "privacy_contract_version"
        ]
        == "promati.orchestrator.privacy.v1"
    )


    for secret in (
        "SECRET QUESTION",
        "SECRET ANSWER",
        "SECRET TRACE",
        "SECRET RESULT",
    ):

        assert (
            secret
            not in serialized
        )


def test_run_record_keys_equal_privacy_allowlist():

    record = (
        run_logging
        .build_orchestrator_run_record(
            {
                "status":
                    "ok",

                "observability": {
                    "timings_ms":
                        {},

                    "counts":
                        {},
                },
            }
        )
    )


    assert (
        set(
            record
        )
        == set(
            privacy_policy
            .PERSISTED_RECORD_KEYS
        )
    )
