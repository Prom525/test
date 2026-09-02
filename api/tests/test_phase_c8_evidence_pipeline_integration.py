from __future__ import annotations

import ast
import pathlib
import unittest


SERVICE_PATH = (
    pathlib.Path(__file__).resolve().parents[1]
    / "app"
    / "orchestrator"
    / "service.py"
)


def _dotted_name(node):
    if isinstance(node, ast.Name):
        return node.id

    if isinstance(node, ast.Attribute):
        parent = _dotted_name(node.value)
        return (
            f"{parent}.{node.attr}"
            if parent
            else node.attr
        )

    return ""


class EvidencePipelineServiceWiringV1Tests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(cls):
        cls.source = SERVICE_PATH.read_text(
            encoding="utf-8-sig",
        )
        cls.tree = ast.parse(
            cls.source,
            filename=str(SERVICE_PATH),
        )

        matches = [
            node
            for node in cls.tree.body
            if (
                isinstance(
                    node,
                    (
                        ast.FunctionDef,
                        ast.AsyncFunctionDef,
                    ),
                )
                and node.name == "run_orchestrator"
            )
        ]

        if len(matches) != 1:
            raise AssertionError(
                "run_orchestrator must be unique"
            )

        cls.run_node = matches[0]

    def test_evidence_pipeline_imports_are_present(self):
        required_imports = {
            (
                "app.orchestrator."
                "evidence_requirement_catalog",
                "get_requirement_set",
            ),
            (
                "app.orchestrator."
                "evidence_adapters",
                "normalize_execution_result_evidence",
            ),
            (
                "app.orchestrator."
                "evidence_assessor",
                "assess_evidence",
            ),
            (
                "app.orchestrator."
                "evidence_research_gate",
                "decide_research_requirement",
            ),
            (
                "app.orchestrator."
                "evidence_research_executor",
                "execute_bounded_research",
            ),
            (
                "app.orchestrator."
                "evidence_reconciler",
                "reconcile_evidence",
            ),
            (
                "app.orchestrator."
                "evidence_synthesizer",
                "synthesize_grounded_evidence",
            ),
        }

        observed_imports = set()

        for node in self.tree.body:
            if not isinstance(node, ast.ImportFrom):
                continue

            for alias in node.names:
                observed_imports.add(
                    (
                        node.module or "",
                        alias.name,
                    )
                )

        self.assertTrue(
            required_imports.issubset(
                observed_imports
            )
        )

    def test_execute_plan_collects_typed_shadow_results(self):
        execute_calls = [
            node
            for node in ast.walk(self.run_node)
            if (
                isinstance(node, ast.Call)
                and _dotted_name(node.func)
                == "execute_plan"
            )
        ]

        self.assertEqual(len(execute_calls), 1)

        keyword_names = {
            keyword.arg
            for keyword in execute_calls[0].keywords
        }

        self.assertIn(
            "shadow_observer",
            keyword_names,
        )

    def test_pipeline_call_order_is_exact(self):
        target_names = (
            "execute_plan",
            "get_requirement_set",
            "normalize_execution_result_evidence",
            "assess_evidence",
            "decide_research_requirement",
            "execute_bounded_research",
            "reconcile_evidence",
            "synthesize_grounded_evidence",
        )

        observed = []

        for node in ast.walk(self.run_node):
            if not isinstance(node, ast.Call):
                continue

            name = _dotted_name(node.func)

            if name in target_names:
                observed.append(
                    (
                        node.lineno,
                        name,
                    )
                )

        observed_names = tuple(
            name
            for _, name in sorted(observed)
        )

        self.assertEqual(
            observed_names,
            target_names,
        )

    def test_response_contains_additive_pipeline_key(self):
        response_assignments = [
            node
            for node in ast.walk(self.run_node)
            if (
                isinstance(node, ast.Assign)
                and any(
                    isinstance(target, ast.Name)
                    and target.id == "response"
                    for target in node.targets
                )
                and isinstance(node.value, ast.Dict)
            )
        ]

        self.assertEqual(
            len(response_assignments),
            1,
        )

        keys = {
            key.value
            for key in response_assignments[
                0
            ].value.keys
            if isinstance(key, ast.Constant)
        }

        self.assertIn(
            "evidence_pipeline",
            keys,
        )

    def test_legacy_response_keys_are_preserved(self):
        response_assignment = next(
            node
            for node in ast.walk(self.run_node)
            if (
                isinstance(node, ast.Assign)
                and any(
                    isinstance(target, ast.Name)
                    and target.id == "response"
                    for target in node.targets
                )
                and isinstance(node.value, ast.Dict)
            )
        )

        keys = {
            key.value
            for key in response_assignment.value.keys
            if isinstance(key, ast.Constant)
        }

        self.assertTrue(
            {
                "status",
                "answer",
                "context_type",
                "question",
                "query_plan",
                "research",
                "clarification",
                "results",
            }.issubset(keys)
        )


if __name__ == "__main__":
    unittest.main()