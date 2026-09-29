from __future__ import annotations

import inspect

from app.orchestrator import operability


class _MappingResult:

    def __init__(
        self,
        *,
        first=None,
        all_rows=(),
    ):

        self._first = first
        self._all_rows = all_rows


    def mappings(
        self,
    ):

        return self


    def first(
        self,
    ):

        return self._first


    def all(
        self,
    ):

        return self._all_rows


class _OperabilityDb:

    def __init__(
        self,
    ):

        self._results = iter(
            (
                _MappingResult(
                    first={
                        "total_runs": 1,
                    },
                ),
                _MappingResult(
                    first={
                        "sample_count": 1,
                    },
                ),
                _MappingResult(
                    all_rows=(
                        {
                            "health_status": "healthy",
                            "error_category": "capability_unsupported",
                            "run_count": 1,
                        },
                    ),
                ),
                _MappingResult(),
                _MappingResult(),
                _MappingResult(),
            )
        )


    def execute(
        self,
        *_args,
        **_kwargs,
    ):

        return next(
            self._results
        )


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


def test_operability_groups_capability_unsupported_without_new_dimensions():

    snapshot = (
        operability
        ._window_snapshot(
            _OperabilityDb(),
            24,
        )
    )

    assert snapshot["health"] == [
        {
            "health_status": "healthy",
            "error_category": "capability_unsupported",
            "run_count": 1,
        }
    ]


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
