from __future__ import annotations

import inspect

from app.orchestrator import operability


def test_operability_contract_is_exact():

    assert (
        operability
        .OPERABILITY_CONTRACT_VERSION
        == "promati.diagnostics.operability.v1"
    )

    assert (
        operability
        .WINDOW_HOURS
        == (
            24,
            168,
        )
    )


def test_operability_uses_fixed_aggregate_windows():

    source = inspect.getsource(
        operability
    )

    assert (
        "observability.orchestrator_runs"
        in source
    )

    assert (
        "make_interval"
        in source
    )

    assert (
        "percentile_cont(0.50)"
        in source
    )

    assert (
        "percentile_cont(0.95)"
        in source
    )


def test_operability_contains_required_dimensions():

    source = inspect.getsource(
        operability
    )

    for token in (
        "health_status",
        "error_category",
        "primary_domain",
        "intent",
        "research_required",
        "research_status",
        "total_ai_calls",
        "total_specialist_calls",
    ):

        assert (
            token
            in source
        )


def test_operability_has_no_raw_question_or_answer_fields():

    source = inspect.getsource(
        operability
    )

    forbidden = (
        '"question"',
        '"vraag"',
        '"answer"',
        '"trace"',
        '"entities"',
        '"conversation_context"',
        '"results"',
        '"evidence_pipeline"',
    )

    for token in forbidden:

        assert (
            token
            not in source
        )


def test_operability_is_read_only():

    source = inspect.getsource(
        operability
    ).lower()

    forbidden_sql = (
        "insert into",
        "delete from",
        "update observability",
        "truncate ",
        "drop table",
        "alter table",
    )

    for token in forbidden_sql:

        assert (
            token
            not in source
        )
