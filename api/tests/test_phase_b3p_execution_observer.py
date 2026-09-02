from __future__ import annotations

import unittest

from tests.test_phase_b3g_executor_shadow_local_only import (
    _load_executor_core,
    _plan,
)


def _sender(path, payload):
    return {
        "status": "ok",
        "value": 123,
    }


class ExecutionObserverContractTests(
    unittest.TestCase
):
    def test_observer_receives_one_execution_result(self):
        execute_plan, _, _ = _load_executor_core()

        observed = []

        results, trace = execute_plan(
            _plan(),
            sender=_sender,
            shadow_observer=observed.append,
        )

        self.assertEqual(len(observed), 1)
        self.assertEqual(len(results), 1)
        self.assertEqual(len(trace.attempts), 1)
        self.assertEqual(
            observed[0].semantic_outcome,
            "shadow-only",
        )

    def test_observer_return_value_is_ignored(self):
        execute_plan, _, _ = _load_executor_core()

        def observer(execution_result):
            return {
                "must_not_replace_execution": True,
            }

        results, trace = execute_plan(
            _plan(),
            sender=_sender,
            shadow_observer=observer,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(len(trace.attempts), 1)
        self.assertEqual(
            set(results[0]),
            {
                "step_id",
                "domain",
                "action",
                "endpoint",
                "accepted",
                "result",
            },
        )

    def test_observer_exception_is_fail_open(self):
        execute_plan, _, _ = _load_executor_core()

        def observer(execution_result):
            raise RuntimeError(
                "intentional observer failure"
            )

        results, trace = execute_plan(
            _plan(),
            sender=_sender,
            shadow_observer=observer,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(len(trace.attempts), 1)
        self.assertTrue(results[0]["accepted"])


if __name__ == "__main__":
    unittest.main()