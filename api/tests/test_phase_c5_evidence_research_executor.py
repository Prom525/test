from __future__ import annotations

import dataclasses
import inspect
import unittest
from types import SimpleNamespace

import app.orchestrator.evidence_research_executor as executor
from app.orchestrator.evidence_assessor import (
    EvidenceAssessmentStatus,
)
from app.orchestrator.evidence_research_gate import (
    RESEARCH_GATE_CONTRACT_VERSION,
    ResearchGateDecision,
    ResearchGateStatus,
)


def _decision(
    *,
    required: bool,
) -> ResearchGateDecision:
    return ResearchGateDecision(
        contract_version=(
            RESEARCH_GATE_CONTRACT_VERSION
        ),
        requirement_set_id="band_status.v1",
        intent="band_status",
        status=(
            ResearchGateStatus.REQUIRED
            if required
            else ResearchGateStatus.NOT_REQUIRED
        ),
        research_required=required,
        target_requirement_ids=(
            ("LATEST_BLADE_HEIGHT",)
            if required
            else ()
        ),
        reasons=(
            ("assessment_insufficient",)
            if required
            else ()
        ),
        assessment_status=(
            EvidenceAssessmentStatus.INSUFFICIENT
            if required
            else EvidenceAssessmentStatus.SUFFICIENT
        ),
    )


class BoundedResearchExecutionContractsV1Tests(
    unittest.TestCase
):
    def test_contract_version_is_exact(self):
        self.assertEqual(
            executor.RESEARCH_EXECUTION_CONTRACT_VERSION,
            (
                "promati.phase_c5."
                "bounded_research_execution_contract.v1"
            ),
        )

    def test_status_values_are_exact(self):
        self.assertEqual(
            tuple(
                status.value
                for status
                in executor.ResearchExecutionStatus
            ),
            (
                "skipped",
                "completed",
                "blocked",
            ),
        )

    def test_result_fields_are_exact(self):
        self.assertEqual(
            tuple(
                field.name
                for field in dataclasses.fields(
                    executor.ResearchExecutionResult
                )
            ),
            (
                "contract_version",
                "requirement_set_id",
                "intent",
                "status",
                "research_performed",
                "target_requirement_ids",
                "initial_results",
                "combined_results",
                "agent_metadata",
                "blocked_reason",
            ),
        )

    def test_result_is_frozen(self):
        result = executor.ResearchExecutionResult(
            contract_version=(
                executor.RESEARCH_EXECUTION_CONTRACT_VERSION
            ),
            requirement_set_id="band_status.v1",
            intent="band_status",
            status=(
                executor.ResearchExecutionStatus.SKIPPED
            ),
            research_performed=False,
            target_requirement_ids=(),
            initial_results=(),
            combined_results=(),
            agent_metadata=None,
            blocked_reason=None,
        )

        with self.assertRaises(
            dataclasses.FrozenInstanceError
        ):
            result.research_performed = True

    def test_contract_contains_no_direct_transport(self):
        source = inspect.getsource(executor).lower()

        forbidden = (
            "requests.",
            "urllib.",
            "httpx.",
            "execute_plan(",
            "openai",
        )

        for token in forbidden:
            self.assertNotIn(token, source)


class BoundedResearchExecutionV1Tests(
    unittest.TestCase
):
    def test_not_required_skips_runtime(self):
        calls = []

        def runtime(*args, **kwargs):
            calls.append((args, kwargs))
            raise AssertionError(
                "runtime must not be called"
            )

        result = executor.execute_bounded_research(
            _decision(required=False),
            SimpleNamespace(),
            [{"step_id": "initial"}],
            runtime=runtime,
        )

        self.assertEqual(calls, [])
        self.assertEqual(
            result.status,
            executor.ResearchExecutionStatus.SKIPPED,
        )
        self.assertFalse(result.research_performed)
        self.assertEqual(
            result.combined_results,
            ({"step_id": "initial"},),
        )

    def test_required_invokes_runtime_once(self):
        calls = []

        def runtime(
            plan,
            initial_results,
            sender=None,
            *,
            planner=None,
            synthesizer=None,
        ):
            calls.append(
                {
                    "plan": plan,
                    "initial_results": initial_results,
                    "sender": sender,
                    "planner": planner,
                    "synthesizer": synthesizer,
                }
            )

            return synthesizer(
                plan,
                initial_results
                + [{"step_id": "follow-up"}],
            ) | {
                "agent": {
                    "follow_up_specialist_calls": 1,
                }
            }

        plan = SimpleNamespace()
        sender = object()
        planner = object()

        result = executor.execute_bounded_research(
            _decision(required=True),
            plan,
            [{"step_id": "initial"}],
            sender=sender,
            planner=planner,
            runtime=runtime,
        )

        self.assertEqual(len(calls), 1)
        self.assertIsNot(calls[0]["plan"], plan)
        self.assertIs(calls[0]["sender"], sender)
        self.assertIs(calls[0]["planner"], planner)
        self.assertTrue(
            callable(calls[0]["synthesizer"])
        )
        self.assertEqual(
            result.status,
            executor.ResearchExecutionStatus.COMPLETED,
        )
        self.assertTrue(result.research_performed)
        self.assertEqual(
            result.combined_results,
            (
                {"step_id": "initial"},
                {"step_id": "follow-up"},
            ),
        )

    def test_passthrough_performs_no_synthesis(self):
        captured = {}

        def runtime(
            plan,
            initial_results,
            sender=None,
            *,
            planner=None,
            synthesizer=None,
        ):
            captured.update(
                synthesizer(
                    plan,
                    [{"raw": True}],
                )
            )
            return captured | {"agent": {}}

        executor.execute_bounded_research(
            _decision(required=True),
            SimpleNamespace(),
            [],
            runtime=runtime,
        )

        self.assertEqual(
            captured,
            {
                "results": [{"raw": True}],
                "ai_calls_used": 0,
            },
        )
        self.assertNotIn("answer", captured)

    def test_runtime_failure_is_typed_blocked(self):
        def runtime(*args, **kwargs):
            raise RuntimeError(
                "sensitive runtime detail"
            )

        result = executor.execute_bounded_research(
            _decision(required=True),
            SimpleNamespace(),
            [{"initial": True}],
            runtime=runtime,
        )

        self.assertEqual(
            result.status,
            executor.ResearchExecutionStatus.BLOCKED,
        )
        self.assertFalse(result.research_performed)
        self.assertEqual(
            result.blocked_reason,
            "research_runtime_error:RuntimeError",
        )
        self.assertNotIn(
            "sensitive runtime detail",
            result.blocked_reason,
        )

    def test_results_are_detached(self):
        initial = [
            {
                "value": {
                    "height": 12,
                }
            }
        ]

        result = executor.execute_bounded_research(
            _decision(required=False),
            SimpleNamespace(),
            initial,
            runtime=lambda *args, **kwargs: {},
        )

        result.combined_results[0][
            "value"
        ]["height"] = 99

        self.assertEqual(
            initial[0]["value"]["height"],
            12,
        )

    def test_inputs_are_not_mutated(self):
        decision = _decision(required=True)
        plan = SimpleNamespace(
            research_required=False
        )
        initial = [{"step_id": "initial"}]

        decision_before = repr(decision)
        plan_before = repr(plan)
        initial_before = repr(initial)

        def runtime(
            plan,
            initial_results,
            sender=None,
            *,
            planner=None,
            synthesizer=None,
        ):
            return synthesizer(
                plan,
                initial_results,
            ) | {"agent": {}}

        executor.execute_bounded_research(
            decision,
            plan,
            initial,
            runtime=runtime,
        )

        self.assertEqual(
            repr(decision),
            decision_before,
        )
        self.assertEqual(
            repr(plan),
            plan_before,
        )
        self.assertEqual(
            repr(initial),
            initial_before,
        )

    def test_agent_metadata_is_detached(self):
        metadata = {
            "rounds": [
                {
                    "executed_calls": 1,
                }
            ]
        }

        def runtime(
            plan,
            initial_results,
            sender=None,
            *,
            planner=None,
            synthesizer=None,
        ):
            return (
                synthesizer(
                    plan,
                    initial_results,
                )
                | {"agent": metadata}
            )

        result = executor.execute_bounded_research(
            _decision(required=True),
            SimpleNamespace(),
            [],
            runtime=runtime,
        )

        result.agent_metadata[
            "rounds"
        ][0]["executed_calls"] = 99

        self.assertEqual(
            metadata["rounds"][0][
                "executed_calls"
            ],
            1,
        )


class BoundedResearchPlanActivationV1Tests(
    unittest.TestCase
):
    def test_required_activates_detached_plan(self):
        original_plan = SimpleNamespace(
            research_required=False,
            marker={
                "value": "original",
            },
        )

        observed = {}

        def runtime(
            plan,
            initial_results,
            sender=None,
            *,
            planner=None,
            synthesizer=None,
        ):
            observed["same_object"] = (
                plan is original_plan
            )
            observed["research_required"] = (
                plan.research_required
            )

            plan.marker["value"] = "runtime"

            return (
                synthesizer(
                    plan,
                    initial_results,
                )
                | {
                    "agent": {
                        "follow_up_specialist_calls": 0,
                    }
                }
            )

        result = executor.execute_bounded_research(
            _decision(required=True),
            original_plan,
            [{"step_id": "initial"}],
            runtime=runtime,
        )

        self.assertEqual(
            result.status,
            executor.ResearchExecutionStatus.COMPLETED,
        )
        self.assertFalse(
            observed["same_object"]
        )
        self.assertTrue(
            observed["research_required"]
        )
        self.assertFalse(
            original_plan.research_required
        )
        self.assertEqual(
            original_plan.marker,
            {
                "value": "original",
            },
        )

if __name__ == "__main__":
    unittest.main()