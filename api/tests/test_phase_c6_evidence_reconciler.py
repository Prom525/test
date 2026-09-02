from __future__ import annotations

import ast
import dataclasses
import enum
import inspect
import pathlib
import unittest

import app.orchestrator.evidence_reconciler as reconciler


class EvidenceReconciliationContractsV1Tests(
    unittest.TestCase
):
    def test_contract_version_is_exact(self):
        self.assertEqual(
            reconciler.EVIDENCE_RECONCILIATION_CONTRACT_VERSION,
            "evidence_reconciliation.v1",
        )

    def test_status_values_are_exact(self):
        self.assertTrue(
            issubclass(
                reconciler.EvidenceReconciliationStatus,
                enum.Enum,
            )
        )

        self.assertEqual(
            {
                member.name: member.value
                for member in (
                    reconciler.EvidenceReconciliationStatus
                )
            },
            {
                "UNCHANGED": "unchanged",
                "IMPROVED": "improved",
                "UNRESOLVED": "unresolved",
                "BLOCKED": "blocked",
            },
        )

    def test_result_fields_are_exact(self):
        self.assertEqual(
            tuple(
                field.name
                for field in dataclasses.fields(
                    reconciler.EvidenceReconciliationResult
                )
            ),
            (
                "contract_version",
                "requirement_set_id",
                "intent",
                "status",
                "research_status",
                "initial_evidence_items",
                "reconciled_evidence_items",
                "added_evidence_ids",
                "discarded_result_count",
                "initial_assessment",
                "reconciled_assessment",
                "reasons",
            ),
        )

    def test_result_is_frozen(self):
        parameters = inspect.signature(
            reconciler.EvidenceReconciliationResult
        ).parameters

        self.assertEqual(
            tuple(parameters),
            (
                "contract_version",
                "requirement_set_id",
                "intent",
                "status",
                "research_status",
                "initial_evidence_items",
                "reconciled_evidence_items",
                "added_evidence_ids",
                "discarded_result_count",
                "initial_assessment",
                "reconciled_assessment",
                "reasons",
            ),
        )

        dataclass_parameters = (
            reconciler
            .EvidenceReconciliationResult
            .__dataclass_params__
        )

        self.assertTrue(
            dataclass_parameters.frozen
        )

    def test_collections_are_typed_as_tuples(self):
        annotations = (
            reconciler
            .EvidenceReconciliationResult
            .__annotations__
        )

        self.assertEqual(
            str(annotations["initial_evidence_items"]),
            "tuple[EvidenceItem, ...]",
        )
        self.assertEqual(
            str(annotations["reconciled_evidence_items"]),
            "tuple[EvidenceItem, ...]",
        )
        self.assertEqual(
            str(annotations["added_evidence_ids"]),
            "tuple[str, ...]",
        )
        self.assertEqual(
            str(annotations["reasons"]),
            "tuple[str, ...]",
        )

    def test_reconcile_signature_is_exact(self):
        signature = inspect.signature(
            reconciler.reconcile_evidence
        )

        self.assertEqual(
            tuple(signature.parameters),
            (
                "requirement_set",
                "initial_evidence_items",
                "initial_assessment",
                "research_execution",
                "retrieved_at",
                "target_entity_ids",
                "now",
            ),
        )

        self.assertEqual(
            signature.parameters[
                "retrieved_at"
            ].kind,
            inspect.Parameter.KEYWORD_ONLY,
        )
        self.assertEqual(
            signature.parameters[
                "target_entity_ids"
            ].kind,
            inspect.Parameter.KEYWORD_ONLY,
        )
        self.assertEqual(
            signature.parameters[
                "now"
            ].kind,
            inspect.Parameter.KEYWORD_ONLY,
        )

    def test_c6_contains_no_later_phase_actions(self):
        source_path = pathlib.Path(
            reconciler.__file__
        )

        source = source_path.read_text(
            encoding="utf-8"
        )

        tree = ast.parse(
            source,
            filename=str(source_path),
        )

        forbidden_names = {
            "run_bounded_research",
            "run_bounded_research_agent",
            "execute_bounded_research",
            "plan_research_next_step",
            "AIResearchRequest",
            "default_sender",
            "requests",
            "httpx",
        }

        referenced_names = {
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name)
        }

        imported_names = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_names.update(
                    alias.name.split(".")[0]
                    for alias in node.names
                )

            if isinstance(node, ast.ImportFrom):
                imported_names.update(
                    alias.name
                    for alias in node.names
                )

        self.assertFalse(
            forbidden_names
            & referenced_names
        )
        self.assertFalse(
            forbidden_names
            & imported_names
        )

        lowered = source.lower()

        self.assertNotIn(
            "synthes",
            lowered,
        )
        self.assertNotIn(
            "llm",
            lowered,
        )
        self.assertNotIn(
            "gateway",
            lowered,
        )


if __name__ == "__main__":
    unittest.main()
