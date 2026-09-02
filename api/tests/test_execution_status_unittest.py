from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT),
    )


from app.orchestrator.execution_contracts import (  # noqa: E402
    EXECUTION_CONTRACT_VERSION,
    ExecutionOutcome,
    ExecutionResult,
    ExecutionTransportState,
)
from app.orchestrator.execution_status import (  # noqa: E402
    has_service_accepted_execution,
)


def typed_result(
    *,
    step_id: str,
    outcome: ExecutionOutcome,
    transport: ExecutionTransportState = (
        ExecutionTransportState.COMPLETED
    ),
) -> ExecutionResult:
    return ExecutionResult(
        contract_version=(
            EXECUTION_CONTRACT_VERSION
        ),
        step_id=step_id,
        action="analysis_assistant",
        domain="inspection",
        endpoint="/analysis/assistant/ask",
        transport_state=transport,
        semantic_outcome=outcome,
        specialist_status=None,
        legacy_accepted=True,
        result={},
        error=None,
        attempt_count=1,
        duration_ms=1,
        evidence_metadata=None,
        provenance_metadata=None,
    )


class ExecutionStatusTests(
    unittest.TestCase
):
    def test_typed_success_is_accepted(
        self,
    ):
        self.assertTrue(
            has_service_accepted_execution(
                [
                    typed_result(
                        step_id="step_1",
                        outcome=(
                            ExecutionOutcome.SUCCESS
                        ),
                    )
                ],
                [
                    {
                        "step_id": "step_1",
                        "accepted": False,
                    }
                ],
            )
        )


    def test_typed_error_overrides_legacy_true(
        self,
    ):
        self.assertFalse(
            has_service_accepted_execution(
                [
                    typed_result(
                        step_id="step_1",
                        outcome=(
                            ExecutionOutcome.ERROR
                        ),
                    )
                ],
                [
                    {
                        "step_id": "step_1",
                        "accepted": True,
                    }
                ],
            )
        )


    def test_legacy_true_is_fallback_when_typed_missing(
        self,
    ):
        self.assertTrue(
            has_service_accepted_execution(
                [],
                [
                    {
                        "step_id": "step_1",
                        "accepted": True,
                    }
                ],
            )
        )


    def test_legacy_false_is_false_when_typed_missing(
        self,
    ):
        self.assertFalse(
            has_service_accepted_execution(
                [],
                [
                    {
                        "step_id": "step_1",
                        "accepted": False,
                    }
                ],
            )
        )


    def test_clarification_remains_service_accepted(
        self,
    ):
        self.assertTrue(
            has_service_accepted_execution(
                [
                    typed_result(
                        step_id="step_1",
                        outcome=(
                            ExecutionOutcome
                            .CLARIFICATION_REQUIRED
                        ),
                    )
                ],
                [
                    {
                        "step_id": "step_1",
                        "accepted": True,
                    }
                ],
            )
        )


    def test_not_found_remains_compatibility_accepted(
        self,
    ):
        self.assertTrue(
            has_service_accepted_execution(
                [
                    typed_result(
                        step_id="step_1",
                        outcome=(
                            ExecutionOutcome.NOT_FOUND
                        ),
                    )
                ],
                [
                    {
                        "step_id": "step_1",
                        "accepted": True,
                    }
                ],
            )
        )


    def test_failed_transport_is_not_accepted(
        self,
    ):
        self.assertFalse(
            has_service_accepted_execution(
                [
                    typed_result(
                        step_id="step_1",
                        outcome=(
                            ExecutionOutcome.UNKNOWN
                        ),
                        transport=(
                            ExecutionTransportState
                            .FAILED
                        ),
                    )
                ],
                [
                    {
                        "step_id": "step_1",
                        "accepted": True,
                    }
                ],
            )
        )


    def test_one_success_among_multiple_steps_is_enough(
        self,
    ):
        self.assertTrue(
            has_service_accepted_execution(
                [
                    typed_result(
                        step_id="step_1",
                        outcome=(
                            ExecutionOutcome.ERROR
                        ),
                    ),
                    typed_result(
                        step_id="step_2",
                        outcome=(
                            ExecutionOutcome.SUCCESS
                        ),
                    ),
                ],
                [
                    {
                        "step_id": "step_1",
                        "accepted": False,
                    },
                    {
                        "step_id": "step_2",
                        "accepted": True,
                    },
                ],
            )
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
