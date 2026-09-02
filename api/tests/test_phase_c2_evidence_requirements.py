from __future__ import annotations

import dataclasses
import pathlib
import unittest

import app.orchestrator.evidence_requirements as requirements
from app.orchestrator.evidence_contracts import (
    EvidenceSourceType,
    EvidenceType,
)


class EvidenceRequirementContractsV1Tests(
    unittest.TestCase
):
    def _requirement(self):
        return requirements.EvidenceRequirement(
            contract_version=(
                requirements.EVIDENCE_REQUIREMENT_CONTRACT_VERSION
            ),
            requirement_id="LATEST_BLADE_HEIGHT",
            evidence_types=(
                EvidenceType.MEASUREMENT,
            ),
            necessity=(
                requirements.RequirementNecessity.REQUIRED
            ),
            description=(
                "Latest observed blade height."
            ),
            allowed_source_types=(
                EvidenceSourceType.STRUCTURED_KNOWLEDGE,
            ),
            minimum_items=1,
            entity_type="conveyor_belt",
            entity_id_required=True,
            maximum_age_seconds=None,
            forbidden_substitutions=(
                EvidenceType.DOCUMENT_FRAGMENT,
            ),
        )

    def test_contract_version_is_exact(self):
        self.assertEqual(
            requirements.EVIDENCE_REQUIREMENT_CONTRACT_VERSION,
            (
                "promati.phase_c2."
                "evidence_requirement_contract.v1"
            ),
        )

    def test_necessity_values_are_exact(self):
        self.assertEqual(
            {
                item.value
                for item in requirements.RequirementNecessity
            },
            {
                "required",
                "required_for_diagnosis",
                "desired",
            },
        )

    def test_evidence_requirement_fields_are_exact(self):
        self.assertEqual(
            tuple(
                field.name
                for field in dataclasses.fields(
                    requirements.EvidenceRequirement
                )
            ),
            (
                "contract_version",
                "requirement_id",
                "evidence_types",
                "necessity",
                "description",
                "allowed_source_types",
                "minimum_items",
                "entity_type",
                "entity_id_required",
                "maximum_age_seconds",
                "forbidden_substitutions",
            ),
        )

    def test_requirement_set_fields_are_exact(self):
        self.assertEqual(
            tuple(
                field.name
                for field in dataclasses.fields(
                    requirements.EvidenceRequirementSet
                )
            ),
            (
                "contract_version",
                "requirement_set_id",
                "intent",
                "requirements",
                "notes",
            ),
        )

    def test_requirement_is_constructible(self):
        requirement = self._requirement()

        self.assertEqual(
            requirement.requirement_id,
            "LATEST_BLADE_HEIGHT",
        )
        self.assertEqual(
            requirement.evidence_types,
            (EvidenceType.MEASUREMENT,),
        )
        self.assertEqual(
            requirement.minimum_items,
            1,
        )
        self.assertTrue(
            requirement.entity_id_required
        )
        self.assertIsNone(
            requirement.maximum_age_seconds
        )

    def test_requirement_set_is_constructible(self):
        requirement = self._requirement()

        requirement_set = (
            requirements.EvidenceRequirementSet(
                contract_version=(
                    requirements.
                    EVIDENCE_REQUIREMENT_CONTRACT_VERSION
                ),
                requirement_set_id=(
                    "band_status.v1"
                ),
                intent="band_status",
                requirements=(requirement,),
                notes=(),
            )
        )

        self.assertEqual(
            requirement_set.intent,
            "band_status",
        )
        self.assertEqual(
            requirement_set.requirements,
            (requirement,),
        )

    def test_contract_objects_are_frozen(self):
        requirement = self._requirement()

        with self.assertRaises(
            dataclasses.FrozenInstanceError
        ):
            requirement.minimum_items = 2

        requirement_set = (
            requirements.EvidenceRequirementSet(
                contract_version=(
                    requirements.
                    EVIDENCE_REQUIREMENT_CONTRACT_VERSION
                ),
                requirement_set_id=(
                    "band_status.v1"
                ),
                intent="band_status",
                requirements=(requirement,),
                notes=(),
            )
        )

        with self.assertRaises(
            dataclasses.FrozenInstanceError
        ):
            requirement_set.intent = "changed"

    def test_requirement_collections_are_tuples(self):
        requirement = self._requirement()

        self.assertIsInstance(
            requirement.evidence_types,
            tuple,
        )
        self.assertIsInstance(
            requirement.allowed_source_types,
            tuple,
        )
        self.assertIsInstance(
            requirement.forbidden_substitutions,
            tuple,
        )

    def test_c2_contains_no_assessor_or_research(self):
        source = pathlib.Path(
            requirements.__file__
        ).read_text(
            encoding="utf-8",
        ).lower()

        for forbidden in (
            "assess_evidence",
            "run_research",
            "reconcile_evidence",
            "synthesize_answer",
        ):
            self.assertNotIn(
                forbidden,
                source,
            )


if __name__ == "__main__":
    unittest.main()