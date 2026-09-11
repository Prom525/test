from __future__ import annotations

import ast
import pathlib
import time
import unittest
from types import SimpleNamespace


API_ROOT = pathlib.Path(__file__).resolve().parents[1]

EXECUTOR_PATH = (
    API_ROOT
    / "app"
    / "orchestrator"
    / "executor.py"
)


def _load_executor_core(
    *,
    derive_raises=False,
    request_raises=False,
):
    source = EXECUTOR_PATH.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(
        source,
        filename=str(EXECUTOR_PATH),
    )

    wanted = {
        "_infer_result_count",
        "_is_accepted",
        "execute_plan",
    }

    body = [
        node
        for node in tree.body
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        )
        and node.name in wanted
    ]

    names = {
        node.name
        for node in body
    }

    if names != wanted:
        raise AssertionError(
            f"executor core functions mismatch: {names}"
        )

    module = ast.Module(
        body=body,
        type_ignores=[],
    )

    module = ast.fix_missing_locations(
        module
    )

    derive_calls = []
    request_calls = []


    class DummyTrace:
        def __init__(self, *args, **kwargs):
            self.attempts = []

            for key, value in kwargs.items():
                setattr(
                    self,
                    key,
                    value,
                )

        def __getattr__(self, name):
            return None


    class DummyTraceAttempt:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(
                    self,
                    key,
                    value,
                )


    class DummyExecutionRequest:
        def __init__(self, **kwargs):
            request_calls.append(
                dict(kwargs)
            )

            if request_raises:
                raise RuntimeError(
                    "intentional request shadow failure"
                )

            for key, value in kwargs.items():
                setattr(
                    self,
                    key,
                    value,
                )


    class DummyExecutionTransportState:
        COMPLETED = "COMPLETED"


    class DummyFallbackPolicy:
        UNRESOLVED = "UNRESOLVED"


    def derive_execution_result(**kwargs):
        derive_calls.append(
            dict(kwargs)
        )

        if derive_raises:
            raise RuntimeError(
                "intentional derivation shadow failure"
            )

        return SimpleNamespace(
            semantic_outcome="shadow-only"
        )


    namespace = {
        "Any": object,
        "Callable": object,
        "QueryPlan": object,
        "OrchestratorTrace": DummyTrace,
        "TraceAttempt": DummyTraceAttempt,
        "ACTION_ENDPOINTS": {
            "analysis_assistant":
                "/analysis/assistant/ask",
        },
        "ExecutionRequest":
            DummyExecutionRequest,
        "EXECUTION_CONTRACT_VERSION":
            "promati.phase_b2e.execution_contract.v1",
        "ExecutionTransportState":
            DummyExecutionTransportState,
        "FallbackPolicy":
            DummyFallbackPolicy,
        "derive_execution_result":
            derive_execution_result,
        "time":
            time,
    }

    code = compile(
        module,
        str(EXECUTOR_PATH),
        "exec",
    )

    exec(
        code,
        namespace,
    )

    return (
        namespace["execute_plan"],
        request_calls,
        derive_calls,
    )


def _step():
    return SimpleNamespace(
        step_id="step_shadow_test",
        domain=SimpleNamespace(value="inspection"),
        action="analysis_assistant",
        params={
            "vraag": "testvraag",
        },
        required=True,
        fallback_allowed=True,
    )


def _plan():
    return SimpleNamespace(
        clarification_required=False,
        execution_steps=[
            _step()
        ],
    )


def _run(
    result,
    *,
    derive_raises=False,
    request_raises=False,
):
    (
        execute_plan,
        request_calls,
        derive_calls,
    ) = _load_executor_core(
        derive_raises=derive_raises,
        request_raises=request_raises,
    )

    sender_calls = []


    def sender(path, payload):
        sender_calls.append(
            (
                path,
                dict(payload),
            )
        )

        return dict(result)


    results, trace = execute_plan(
        _plan(),
        sender=sender,
    )

    return {
        "results": results,
        "trace": trace,
        "sender_calls": sender_calls,
        "request_calls": request_calls,
        "derive_calls": derive_calls,
    }


class ExecutorLocalOnlyShadowV1Tests(
    unittest.TestCase
):
    def test_shadow_deriver_called_once_with_custom_sender(self):
        run = _run(
            {
                "status": "ok",
                "value": 123,
            }
        )

        self.assertEqual(
            len(run["sender_calls"]),
            1,
        )

        self.assertEqual(
            len(run["request_calls"]),
            1,
        )

        self.assertEqual(
            len(run["derive_calls"]),
            1,
        )

        wrapper = run["results"][0]

        self.assertEqual(
            set(wrapper),
            {
                "step_id",
                "domain",
                "action",
                "endpoint",
                "accepted",
                "result",
            },
        )

        self.assertTrue(
            wrapper["accepted"]
        )

        derive = run["derive_calls"][0]

        self.assertEqual(
            derive["raw_result"],
            {
                "status": "ok",
                "value": 123,
            },
        )

        self.assertTrue(
            derive["legacy_accepted"]
        )

        self.assertEqual(
            derive["transport_state"],
            "COMPLETED",
        )

        self.assertIsInstance(
            derive["duration_ms"],
            int,
        )

        request = run["request_calls"][0]

        self.assertEqual(
            request["step_id"],
            "step_shadow_test",
        )

        self.assertEqual(
            request["action"],
            "analysis_assistant",
        )

        self.assertEqual(
            request["domain"],
            "inspection",
        )

        self.assertEqual(
            request["timeout_seconds"],
            30.0,
        )

        self.assertEqual(
            request["retry_count"],
            0,
        )

        self.assertEqual(
            request["fallback_policy"],
            "UNRESOLVED",
        )

        self.assertTrue(
            request["legacy_fallback_allowed"]
        )


    def test_deriver_exception_is_fail_open(self):
        run = _run(
            {
                "status": "ok",
                "value": 1,
            },
            derive_raises=True,
        )

        self.assertEqual(
            len(run["derive_calls"]),
            1,
        )

        self.assertEqual(
            len(run["results"]),
            1,
        )

        self.assertTrue(
            run["results"][0]["accepted"]
        )

        self.assertEqual(
            set(run["results"][0]),
            {
                "step_id",
                "domain",
                "action",
                "endpoint",
                "accepted",
                "result",
            },
        )


    def test_request_constructor_exception_is_fail_open(self):
        run = _run(
            {
                "status": "ok",
            },
            request_raises=True,
        )

        self.assertEqual(
            len(run["request_calls"]),
            1,
        )

        self.assertEqual(
            len(run["derive_calls"]),
            0,
        )

        self.assertEqual(
            len(run["results"]),
            1,
        )

        self.assertTrue(
            run["results"][0]["accepted"]
        )


    def test_semantic_non_success_keeps_legacy_acceptance(self):
        run = _run(
            {
                "status":
                    "clarification_required",
            }
        )

        wrapper = run["results"][0]

        # Existing legacy rule rejects only
        # error / failed / failure.
        self.assertTrue(
            wrapper["accepted"]
        )

        self.assertEqual(
            run["derive_calls"][0][
                "raw_result"
            ][
                "status"
            ],
            "clarification_required",
        )

        self.assertTrue(
            run["derive_calls"][0][
                "legacy_accepted"
            ]
        )


    def test_transport_error_dict_is_completed_but_legacy_rejected(self):
        run = _run(
            {
                "status": "error",
                "context_type":
                    "orchestrator_transport",
                "error":
                    "simulated transport failure",
            }
        )

        wrapper = run["results"][0]

        self.assertFalse(
            wrapper["accepted"]
        )

        derive = run["derive_calls"][0]

        self.assertFalse(
            derive["legacy_accepted"]
        )

        self.assertEqual(
            derive["transport_state"],
            "COMPLETED",
        )


    def test_custom_sender_path_requires_no_default_sender_or_network(self):
        run = _run(
            {
                "status": "ok",
            }
        )

        self.assertEqual(
            run["sender_calls"],
            [
                (
                    "/analysis/assistant/ask",
                    {
                        "vraag":
                            "testvraag",
                    },
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()