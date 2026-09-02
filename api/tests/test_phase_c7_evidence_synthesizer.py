from __future__ import annotations

import ast
import dataclasses
import enum
import inspect
import pathlib
import unittest

import app.orchestrator.evidence_synthesizer as synthesizer


class GroundedSynthesisContractsV1Tests(unittest.TestCase):
    def test_contract_version_is_exact(self):
        self.assertEqual(
            synthesizer.GROUNDED_SYNTHESIS_CONTRACT_VERSION,
            "promati.phase_c7.grounded_synthesis.v1",
        )

    def test_status_values_are_exact(self):
        self.assertTrue(
            issubclass(
                synthesizer.GroundedSynthesisStatus,
                enum.Enum,
            )
        )
        self.assertEqual(
            {
                member.name: member.value
                for member in (
                    synthesizer.GroundedSynthesisStatus
                )
            },
            {
                "COMPLETE": "complete",
                "PARTIAL": "partial",
                "BLOCKED": "blocked",
            },
        )

    def test_claim_fields_are_exact(self):
        self.assertEqual(
            tuple(
                field.name
                for field in dataclasses.fields(
                    synthesizer.GroundedClaim
                )
            ),
            (
                "claim_id",
                "text",
                "evidence_ids",
                "requirement_ids",
            ),
        )

    def test_result_fields_are_exact(self):
        self.assertEqual(
            tuple(
                field.name
                for field in dataclasses.fields(
                    synthesizer.GroundedSynthesisResult
                )
            ),
            (
                "contract_version",
                "requirement_set_id",
                "intent",
                "status",
                "claims",
                "omitted_requirement_ids",
                "conflicting_requirement_ids",
                "evidence_ids_used",
                "reasons",
            ),
        )

    def test_collection_fields_are_typed_as_tuples(self):
        claim_fields = {
            field.name: str(field.type)
            for field in dataclasses.fields(
                synthesizer.GroundedClaim
            )
        }
        result_fields = {
            field.name: str(field.type)
            for field in dataclasses.fields(
                synthesizer.GroundedSynthesisResult
            )
        }

        self.assertEqual(
            claim_fields["evidence_ids"],
            "tuple[str, ...]",
        )
        self.assertEqual(
            claim_fields["requirement_ids"],
            "tuple[str, ...]",
        )
        self.assertEqual(
            result_fields["claims"],
            "tuple[GroundedClaim, ...]",
        )
        self.assertEqual(
            result_fields["omitted_requirement_ids"],
            "tuple[str, ...]",
        )
        self.assertEqual(
            result_fields["conflicting_requirement_ids"],
            "tuple[str, ...]",
        )
        self.assertEqual(
            result_fields["evidence_ids_used"],
            "tuple[str, ...]",
        )
        self.assertEqual(
            result_fields["reasons"],
            "tuple[str, ...]",
        )

    def test_contract_objects_are_frozen(self):
        claim = synthesizer.GroundedClaim(
            claim_id="claim-1",
            text="Measured value is 10 mm.",
            evidence_ids=("evidence-1",),
            requirement_ids=("MEASUREMENT",),
        )

        result = synthesizer.GroundedSynthesisResult(
            contract_version=(
                synthesizer
                .GROUNDED_SYNTHESIS_CONTRACT_VERSION
            ),
            requirement_set_id="example.v1",
            intent="example",
            status=(
                synthesizer
                .GroundedSynthesisStatus
                .COMPLETE
            ),
            claims=(claim,),
            omitted_requirement_ids=(),
            conflicting_requirement_ids=(),
            evidence_ids_used=("evidence-1",),
            reasons=(),
        )

        with self.assertRaises(
            dataclasses.FrozenInstanceError
        ):
            claim.text = "changed"

        with self.assertRaises(
            dataclasses.FrozenInstanceError
        ):
            result.status = (
                synthesizer
                .GroundedSynthesisStatus
                .BLOCKED
            )

    def test_synthesis_signature_is_exact(self):
        signature = inspect.signature(
            synthesizer.synthesize_grounded_evidence
        )

        self.assertEqual(
            tuple(signature.parameters),
            ("reconciliation",),
        )
        self.assertEqual(
            str(
                signature.parameters[
                    "reconciliation"
                ].annotation
            ),
            "EvidenceReconciliationResult",
        )
        self.assertEqual(
            str(signature.return_annotation),
            "GroundedSynthesisResult",
        )

    def test_c7_contains_no_external_actions(self):
        source_path = pathlib.Path(
            synthesizer.__file__
        )
        source = source_path.read_text(
            encoding="utf-8",
        )
        tree = ast.parse(
            source,
            filename=str(source_path),
        )

        forbidden_import_prefixes = (
            "app.ai",
            "app.orchestrator.research",
            "app.orchestrator.research_agent",
            "app.orchestrator.research_runtime",
            "app.orchestrator.service",
            "http",
            "requests",
            "urllib",
        )

        imported_modules = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.extend(
                    alias.name
                    for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom):
                imported_modules.append(
                    node.module or ""
                )

        forbidden_imports = tuple(
            module
            for module in imported_modules
            if module.startswith(
                forbidden_import_prefixes
            )
        )

        self.assertEqual(forbidden_imports, ())

        called_names = {
            node.func.id
            for node in ast.walk(tree)
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
            )
        }

        self.assertTrue(
            {
                "execute_plan",
                "run_bounded_research",
                "run_bounded_research_agent",
            }.isdisjoint(called_names)
        )


if __name__ == "__main__":
    unittest.main()