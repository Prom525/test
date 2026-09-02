from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.orchestrator import service


class _JsonModel:
    def __init__(
        self,
        **values,
    ):
        self.__dict__.update(
            values
        )

    def model_dump(
        self,
        mode="python",
    ):
        del mode
        return dict(
            self.__dict__
        )

    def json(self):
        return json.dumps(
            self.__dict__
        )


class EvidencePipelineServiceBehaviorV1Tests(
    unittest.TestCase
):
    def _plan(
        self,
        *,
        clarification_required=False,
        research_required=False,
    ):
        return _JsonModel(
            intent="diagnostics",
            clarification_required=(
                clarification_required
            ),
            clarification_question=(
                "Welke machine bedoel je?"
                if clarification_required
                else None
            ),
            execution_steps=[],
            research_required=(
                research_required
            ),
            requested_information=[],
        )

    def _payload(
        self,
        *,
        include_trace=False,
    ):
        return SimpleNamespace(
            q="testvraag",
            vraag=None,
            include_trace=(
                include_trace
            ),
            conversation_context=None,
        )

    def _run(
        self,
        plan,
        *,
        requirement_set=...,
        pipeline_error=None,
        include_trace=False,
    ):
        calls = []

        shadow_result = SimpleNamespace(
            step_id="step-1"
        )

        if requirement_set is ...:
            requirement_set = SimpleNamespace(
                requirement_set_id=(
                    "req-set-1"
                ),
                intent=plan.intent,
            )

        def execute_plan(
            observed_plan,
            sender=None,
            shadow_observer=None,
        ):
            self.assertIs(
                observed_plan,
                plan,
            )

            self.assertIsNone(
                sender
            )

            if (
                shadow_observer
                is not None
            ):
                shadow_observer(
                    shadow_result
                )

            return (
                [],
                _JsonModel(
                    attempts=[]
                ),
            )

        def mark(
            name,
            value,
        ):
            def side_effect(
                *args,
                **kwargs,
            ):
                del args, kwargs

                calls.append(
                    name
                )

                if (
                    pipeline_error
                    == name
                ):
                    raise RuntimeError(
                        f"forced:{name}"
                    )

                return value

            return side_effect

        assessment = {
            "status": "insufficient",
            "missing_required_requirement_ids": [
                "REQ_A",
            ],
            "conflicting_requirement_ids": [],
            "requirement_results": [
                {
                    "requirement_id": "REQ_A",
                    "necessity": "required",
                    "status": "missing",
                    "matched_evidence_ids": [],
                    "present": False,
                    "relevant": False,
                    "grounded": False,
                    "fresh": False,
                    "conflicting": False,
                    "reasons": [
                        "missing",
                    ],
                }
            ],
        }

        research_decision = {
            "status": "required",
            "research_required": True,
            "target_requirement_ids": [
                "REQ_A",
            ],
            "reasons": [
                "missing_required",
            ],
        }

        research_execution = {
            "status": "completed",
            "research_performed": True,
            "target_requirement_ids": [
                "REQ_A",
            ],
            "initial_results": [
                {
                    "large": (
                        "x" * 5000
                    )
                }
            ],
            "combined_results": [
                {
                    "large": (
                        "x" * 5000
                    )
                },
                {
                    "large": (
                        "y" * 5000
                    )
                },
            ],
            "blocked_reason": None,
        }

        reconciliation = {
            "status": "improved",
            "research_status": (
                "completed"
            ),
            "initial_evidence_items": [
                {
                    "evidence_id": (
                        "evidence-1"
                    ),
                    "large": (
                        "x" * 5000
                    ),
                }
            ],
            "reconciled_evidence_items": [
                {
                    "evidence_id": (
                        "evidence-1"
                    ),
                    "large": (
                        "x" * 5000
                    ),
                },
                {
                    "evidence_id": (
                        "evidence-2"
                    ),
                    "large": (
                        "y" * 5000
                    ),
                },
            ],
            "added_evidence_ids": [
                "evidence-2",
            ],
            "discarded_result_count": 0,
            "initial_assessment": (
                assessment
            ),
            "reconciled_assessment": {
                **assessment,
                "status": (
                    "sufficient"
                ),
                "missing_required_requirement_ids": [],
            },
            "reasons": [
                "research_added_evidence",
            ],
        }

        synthesis = {
            "status": "complete",
            "claims": [
                {
                    "claim_id": "claim-1",
                    "text": (
                        "grote claim "
                        + ("z" * 5000)
                    ),
                    "evidence_ids": [
                        "evidence-1",
                        "evidence-2",
                    ],
                }
            ],
            "warnings": [],
        }

        patches = (
            patch.object(
                service,
                "understand_query",
                return_value=plan,
            ),
            patch.object(
                service,
                "assess_research_requirement",
                return_value=plan,
            ),
            patch.object(
                service,
                "build_execution_plan",
                return_value=plan,
            ),
            patch.object(
                service,
                "execute_plan",
                side_effect=execute_plan,
            ),
            patch.object(
                service,
                "get_requirement_set",
                side_effect=mark(
                    "catalog",
                    requirement_set,
                ),
            ),
            patch.object(
                service,
                "normalize_execution_result_evidence",
                side_effect=mark(
                    "normalize",
                    (),
                ),
            ),
            patch.object(
                service,
                "assess_evidence",
                side_effect=mark(
                    "assess",
                    assessment,
                ),
            ),
            patch.object(
                service,
                "decide_research_requirement",
                side_effect=mark(
                    "gate",
                    research_decision,
                ),
            ),
            patch.object(
                service,
                "execute_bounded_research",
                side_effect=mark(
                    "research",
                    research_execution,
                ),
            ),
            patch.object(
                service,
                "reconcile_evidence",
                side_effect=mark(
                    "reconcile",
                    reconciliation,
                ),
            ),
            patch.object(
                service,
                "synthesize_grounded_evidence",
                side_effect=mark(
                    "synthesize",
                    synthesis,
                ),
            ),
            patch.object(
                service,
                "_build_user_answer",
                return_value=(
                    "legacy answer"
                ),
            ),
            patch.object(
                service,
                "repair_mojibake_text",
                side_effect=(
                    lambda value: value
                ),
            ),
        )

        with patches[0], \
             patches[1], \
             patches[2], \
             patches[3], \
             patches[4], \
             patches[5], \
             patches[6], \
             patches[7], \
             patches[8], \
             patches[9], \
             patches[10], \
             patches[11], \
             patches[12]:

            response = (
                service.run_orchestrator(
                    self._payload(
                        include_trace=(
                            include_trace
                        )
                    )
                )
            )

        return (
            response,
            tuple(calls),
        )

    def test_compact_public_profile_runs_pipeline_once(
        self,
    ):
        plan = self._plan()

        response, calls = self._run(
            plan,
            include_trace=False,
        )

        self.assertEqual(
            calls,
            (
                "catalog",
                "normalize",
                "assess",
                "gate",
                "research",
                "reconcile",
                "synthesize",
            ),
        )

        self.assertEqual(
            response["status"],
            "ok",
        )

        self.assertEqual(
            response["answer"],
            "legacy answer",
        )

        pipeline = response[
            "evidence_pipeline"
        ]

        self.assertEqual(
            pipeline["profile"],
            "compact_public_v1",
        )

        self.assertEqual(
            pipeline[
                "initial_assessment"
            ]["status"],
            "insufficient",
        )

        self.assertEqual(
            pipeline[
                "research_execution"
            ]["status"],
            "completed",
        )

        self.assertEqual(
            pipeline[
                "research_execution"
            ]["initial_result_count"],
            1,
        )

        self.assertEqual(
            pipeline[
                "research_execution"
            ]["combined_result_count"],
            2,
        )

        self.assertEqual(
            pipeline[
                "reconciliation"
            ]["initial_evidence_count"],
            1,
        )

        self.assertEqual(
            pipeline[
                "reconciliation"
            ]["reconciled_evidence_count"],
            2,
        )

        self.assertEqual(
            pipeline[
                "synthesis"
            ]["status"],
            "complete",
        )

        self.assertEqual(
            pipeline[
                "synthesis"
            ]["claim_count"],
            1,
        )

        self.assertEqual(
            pipeline[
                "synthesis"
            ]["evidence_ids_used"],
            [
                "evidence-1",
                "evidence-2",
            ],
        )

    def test_compact_public_profile_contains_no_raw_payloads(
        self,
    ):
        plan = self._plan()

        response, _ = self._run(
            plan,
            include_trace=False,
        )

        pipeline = response[
            "evidence_pipeline"
        ]

        research_execution = pipeline[
            "research_execution"
        ]

        reconciliation = pipeline[
            "reconciliation"
        ]

        synthesis = pipeline[
            "synthesis"
        ]

        self.assertNotIn(
            "initial_results",
            research_execution,
        )

        self.assertNotIn(
            "combined_results",
            research_execution,
        )

        self.assertNotIn(
            "initial_evidence_items",
            reconciliation,
        )

        self.assertNotIn(
            "reconciled_evidence_items",
            reconciliation,
        )

        self.assertNotIn(
            "initial_assessment",
            reconciliation,
        )

        self.assertNotIn(
            "reconciled_assessment",
            reconciliation,
        )

        self.assertNotIn(
            "claims",
            synthesis,
        )

    def test_include_trace_true_retains_full_pipeline(
        self,
    ):
        plan = self._plan()

        response, _ = self._run(
            plan,
            include_trace=True,
        )

        pipeline = response[
            "evidence_pipeline"
        ]

        self.assertNotIn(
            "profile",
            pipeline,
        )

        self.assertIn(
            "initial_results",
            pipeline[
                "research_execution"
            ],
        )

        self.assertIn(
            "combined_results",
            pipeline[
                "research_execution"
            ],
        )

        self.assertIn(
            "initial_evidence_items",
            pipeline[
                "reconciliation"
            ],
        )

        self.assertIn(
            "reconciled_evidence_items",
            pipeline[
                "reconciliation"
            ],
        )

        self.assertIn(
            "claims",
            pipeline[
                "synthesis"
            ],
        )

    def test_compact_projection_is_materially_smaller(
        self,
    ):
        plan = self._plan()

        compact_response, _ = self._run(
            plan,
            include_trace=False,
        )

        full_response, _ = self._run(
            plan,
            include_trace=True,
        )

        compact_bytes = len(
            json.dumps(
                compact_response[
                    "evidence_pipeline"
                ],
                ensure_ascii=False,
                separators=(
                    ",",
                    ":",
                ),
            ).encode(
                "utf-8"
            )
        )

        full_bytes = len(
            json.dumps(
                full_response[
                    "evidence_pipeline"
                ],
                ensure_ascii=False,
                separators=(
                    ",",
                    ":",
                ),
            ).encode(
                "utf-8"
            )
        )

        self.assertLess(
            compact_bytes,
            full_bytes * 0.25,
        )

    def test_unknown_intent_skips_evidence_pipeline(
        self,
    ):
        plan = self._plan()

        response, calls = self._run(
            plan,
            requirement_set=None,
            include_trace=False,
        )

        self.assertEqual(
            calls,
            (
                "catalog",
            ),
        )

        self.assertIsNone(
            response[
                "evidence_pipeline"
            ]
        )

        self.assertEqual(
            response["answer"],
            "legacy answer",
        )

    def test_pipeline_failure_is_legacy_fail_open(
        self,
    ):
        plan = self._plan()

        response, calls = self._run(
            plan,
            pipeline_error="assess",
            include_trace=False,
        )

        self.assertEqual(
            calls,
            (
                "catalog",
                "normalize",
                "assess",
            ),
        )

        self.assertIsNone(
            response[
                "evidence_pipeline"
            ]
        )

        self.assertEqual(
            response["status"],
            "ok",
        )

        self.assertEqual(
            response["answer"],
            "legacy answer",
        )

    def test_clarification_blocks_pipeline_research(
        self,
    ):
        plan = self._plan(
            clarification_required=True,
            research_required=True,
        )

        response, calls = self._run(
            plan,
            include_trace=False,
        )

        self.assertEqual(
            response["status"],
            "clarification_required",
        )

        self.assertNotIn(
            "research",
            calls,
        )

        self.assertNotIn(
            "reconcile",
            calls,
        )

        self.assertNotIn(
            "synthesize",
            calls,
        )

        self.assertIsNone(
            response[
                "evidence_pipeline"
            ]
        )


if __name__ == "__main__":
    unittest.main()