from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT),
    )


import app.orchestrator.understanding as understanding

from app.orchestrator.planner import (
    build_execution_plan,
)


NO_SCOPE = {
    "status": "not_found",
    "scope": None,
    "candidates": [],
    "roles": {
        "active": [],
        "excluded": [],
        "comparison": [],
        "mentioned": [],
    },
    "mode": "single",
}


MV1_SCOPE = {
    "scope_type": "installation",
    "canonical_code": "MV1",
    "canonical_name": "Mengveld 1",
    "area_code": "GSL",
    "installation_code": "MV1",
    "source": "canonical_scope_validation",
    "confidence": 1.0,
}


MV1_CONTEXT = {
    "reference_mode":
        "inherit_active_scope",

    "active_scope": {
        "scope_code": "MV1",
        "scope_type": "installation",
        "area_code": "GSL",
        "installation_code": "MV1",
    },
}


def validate_mv1(value):

    if str(value).upper() == "MV1":

        return {
            "valid": True,
            "scope": dict(
                MV1_SCOPE
            ),
        }

    return {
        "valid": False,
        "scope": None,
    }


class ScraperFamilyUnderstandingTests(
    unittest.TestCase
):

    def test_detects_u_positions_as_family(self):

        entity = (
            understanding
            .detect_inspection_scraper_family_filter(
                "en alleen de U-posities?"
            )
        )

        self.assertIsNotNone(
            entity
        )

        self.assertEqual(
            entity.name,
            "scraper_family",
        )

        self.assertEqual(
            entity.value,
            "U",
        )


    def test_does_not_treat_bb_u_product_as_position_filter(self):

        entity = (
            understanding
            .detect_inspection_scraper_family_filter(
                "ik zoek BB-U 1800"
            )
        )

        self.assertIsNone(
            entity
        )


    def test_does_not_treat_concrete_u_type_as_family_phrase(self):

        entity = (
            understanding
            .detect_inspection_scraper_family_filter(
                "toon U 1200"
            )
        )

        self.assertIsNone(
            entity
        )


    def test_inherited_mv1_plus_u_creates_family_entity(self):

        with (
            patch.object(
                understanding,
                "resolve_scope_context",
                return_value=NO_SCOPE,
            ),
            patch.object(
                understanding,
                "validate_scope_code",
                side_effect=validate_mv1,
            ),
        ):

            plan = (
                understanding
                .understand_query(
                    "en alleen de U-posities?",
                    conversation_context=MV1_CONTEXT,
                )
            )

        self.assertEqual(
            plan.entities[
                "scope_code"
            ].value,
            "MV1",
        )

        self.assertEqual(
            plan.entities[
                "scraper_family"
            ].value,
            "U",
        )


    def test_planner_passes_family_to_analysis(self):

        with (
            patch.object(
                understanding,
                "resolve_scope_context",
                return_value=NO_SCOPE,
            ),
            patch.object(
                understanding,
                "validate_scope_code",
                side_effect=validate_mv1,
            ),
        ):

            plan = (
                understanding
                .understand_query(
                    "en alleen de U-posities?",
                    conversation_context=MV1_CONTEXT,
                )
            )

        planned = build_execution_plan(
            plan
        )

        steps = [
            step
            for step
            in planned.execution_steps
            if step.action
            == "analysis_assistant"
        ]

        self.assertEqual(
            len(steps),
            1,
        )

        self.assertEqual(
            steps[0].params.get(
                "scope_code"
            ),
            "MV1",
        )

        self.assertEqual(
            steps[0].params.get(
                "scraper_family"
            ),
            "U",
        )


    def test_non_u_followup_keeps_family_absent(self):

        with (
            patch.object(
                understanding,
                "resolve_scope_context",
                return_value=NO_SCOPE,
            ),
            patch.object(
                understanding,
                "validate_scope_code",
                side_effect=validate_mv1,
            ),
        ):

            plan = (
                understanding
                .understand_query(
                    "welke daarvan moeten vervangen worden?",
                    conversation_context=MV1_CONTEXT,
                )
            )

        self.assertNotIn(
            "scraper_family",
            plan.entities,
        )


if __name__ == "__main__":

    unittest.main(
        verbosity=2
    )
