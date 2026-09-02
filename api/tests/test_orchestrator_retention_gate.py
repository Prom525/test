from __future__ import annotations

from pathlib import Path


ROOT = (
    Path(
        __file__
    )
    .resolve()
    .parents[
        1
    ]
)


SQL_FILE = (
    ROOT
    / "sql"
    / "2026_09_01_p3_3b_retention_daily_gate.sql"
)


def _sql() -> str:

    return SQL_FILE.read_text(
        encoding="utf-8"
    )


def test_retention_gate_contract_is_exact():

    sql = _sql()

    assert (
        "promati.orchestrator.retention_gate.v1"
        in sql
    )

    assert (
        "observability.orchestrator_retention_state"
        in sql
    )

    assert (
        "observability.run_orchestrator_retention_if_due"
        in sql
    )


def test_retention_gate_is_insert_driven_and_daily():

    sql = _sql()

    assert (
        "trg_orchestrator_runs_retention_gate"
        in sql
    )

    assert (
        "AFTER INSERT"
        in sql
    )

    assert (
        "FOR EACH STATEMENT"
        in sql
    )

    assert (
        "interval '1 day'"
        in sql
    )

    assert (
        "purge_orchestrator_runs"
        in sql
    )


def test_retention_gate_is_fixed_to_90_days():

    sql = _sql()

    assert (
        "retain_days integer DEFAULT 90"
        in sql
    )

    assert (
        "run_orchestrator_retention_if_due(\n            90"
        in sql
    )

    assert (
        "BETWEEN 7 AND 3650"
        in sql
    )


def test_trigger_is_fail_open():

    sql = _sql()

    assert (
        "WHEN OTHERS THEN"
        in sql
    )

    assert (
        "retention failure must never reject"
        in sql
    )

    assert (
        "RETURN NULL"
        in sql
    )


def test_retention_state_has_no_free_text_error_message():

    sql = _sql()

    assert (
        "last_sqlstate"
        in sql
    )

    assert (
        "SQLSTATE"
        in sql
    )

    assert (
        "SQLERRM"
        not in sql
    )


def test_pg_cron_is_not_introduced():

    sql = _sql().lower()

    assert (
        "cron.schedule"
        not in sql
    )

    assert (
        "create extension"
        not in sql
    )
