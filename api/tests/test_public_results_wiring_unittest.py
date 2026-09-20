from __future__ import annotations

import ast
import unittest
from pathlib import Path


SERVICE = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "orchestrator"
    / "service.py"
)


class PublicResultsWiringTests(
    unittest.TestCase
):
    def test_public_results_projection_is_wired_after_presentation(
        self,
    ):
        text = SERVICE.read_text(
            encoding="utf-8-sig"
        )
        tree = ast.parse(text)
        function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "run_orchestrator"
        )

        def calls_named(name):
            return [
                node
                for node in ast.walk(function)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == name
            ]

        post_observability = calls_named(
            "run_post_cp15_observability_stage"
        )
        response_build = calls_named(
            "run_final_response_build_stage"
        )

        self.assertEqual(
            (len(post_observability), len(response_build)),
            (1, 1),
        )

        stage_call = response_build[0]
        stage_statement = next(
            node
            for node in function.body
            if stage_call in ast.walk(node)
        )
        response_binding = next(
            node
            for node in function.body
            if isinstance(node, ast.Assign)
            and ast.unparse(node.targets[0]) == "response"
        )

        self.assertLess(
            post_observability[0].lineno,
            stage_call.lineno,
        )
        self.assertLess(
            stage_call.lineno,
            response_binding.lineno,
        )
        self.assertEqual(
            ast.unparse(stage_statement.targets[0]),
            "final_response_build_stage_result",
        )
        self.assertEqual(
            [ast.unparse(arg) for arg in stage_call.args],
            [
                "payload",
                "cp11_debug_response",
                "evidence_pipeline",
                "task_coverage_gate_cp10",
                "results",
                "plan",
                "status",
                "answer",
                "question",
                "research",
                "clarification",
                "task_execution_shadow",
                "task_planner_canary",
                "trace",
                "timings",
            ],
        )
        self.assertEqual(
            [
                (keyword.arg, ast.unparse(keyword.value))
                for keyword in stage_call.keywords
            ],
            [
                ("observability_now", "_observability_now"),
                (
                    "compact_evidence_pipeline_for_public_response",
                    "_compact_evidence_pipeline_for_public_response",
                ),
                (
                    "compact_results_for_public_response",
                    "compact_results_for_public_response",
                ),
                ("model_to_dict", "_model_to_dict"),
                (
                    "observability_elapsed_ms",
                    "_observability_elapsed_ms",
                ),
            ],
        )

        self.assertEqual(
            ast.unparse(response_binding.value),
            "final_response_build_stage_result.response",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
