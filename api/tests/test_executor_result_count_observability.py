from __future__ import annotations

from app.orchestrator.executor import (
    _infer_result_count,
)


def test_resultaat_list_is_counted():
    result = {
        "status": "ok",
        "resultaat": [
            {"value": 1},
            {"value": 2},
            {"value": 3},
        ],
    }

    assert _infer_result_count(
        result
    ) == 3


def test_empty_resultaat_is_valid_zero():
    result = {
        "status": "ok",
        "resultaat": [],
    }

    assert _infer_result_count(
        result
    ) == 0


def test_existing_results_shape_remains_supported():
    result = {
        "status": "ok",
        "results": [
            {"value": 1},
            {"value": 2},
        ],
    }

    assert _infer_result_count(
        result
    ) == 2


def test_unknown_shape_remains_unknown():
    result = {
        "status": "ok",
        "kort_resultaat": (
            "20 lifecycle-regels gevonden."
        ),
    }

    assert (
        _infer_result_count(
            result
        )
        is None
    )