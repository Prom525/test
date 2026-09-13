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


import app.orchestrator.understanding as understanding_module

from app.orchestrator.planner import (
    build_execution_plan,
)


SERVICE_PATH = (
    ROOT
    / "app"
    / "orchestrator"
    / "service.py"
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


MV2_RESOLUTION = {
    "status": "resolved",
    "scope": {
        "scope_type": "installation",
        "canonical_code": "MV2",
        "canonical_name": "Mengveld 2",
        "area_code": "GSL",
        "installation_code": "MV2",
        "matched_alias": "mv2",
        "source":
            "vw_gpt_band_asset_context.installation",
        "confidence": 1.0,
    },
    "candidates": [],
    "roles": {
        "active": [],
        "excluded": [],
        "comparison": [],
        "mentioned": [],
    },
    "mode": "context_roles",
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


def valid_scope(
    value: str,
):
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


def entity(
    plan,
    name: str,
):
    return plan.entities.get(
        name
    )


class ConversationScopeGroundingTests(
    unittest.TestCase
):

    def test_turn_2_inherits_mv1(self):
        question = (
            "wat is de status van de schrapers "
            "van die banden, zitten daar posities "
            "bij die vervangen moeten worden?"
        )

        with (
            patch.object(
                understanding_module,
                "resolve_scope_context",
                return_value=NO_SCOPE,
            ),
            patch.object(
                understanding_module,
                "validate_scope_code",
                side_effect=valid_scope,
            ),
        ):
            plan = (
                understanding_module
                .understand_query(
                    question,
                    conversation_context=MV1_CONTEXT,
                )
            )

        self.assertEqual(
            plan.original_question,
            question,
        )

        self.assertEqual(
            entity(
                plan,
                "scope_code",
            ).value,
            "MV1",
        )

        self.assertEqual(
            entity(
                plan,
                "scope_type",
            ).value,
            "installation",
        )

        self.assertEqual(
            entity(
                plan,
                "area_code",
            ).value,
            "GSL",
        )

        self.assertEqual(
            entity(
                plan,
                "installation_code",
            ).value,
            "MV1",
        )

        self.assertEqual(
            entity(
                plan,
                "scope_code",
            ).source,
            "conversation_context_validated",
        )


    def test_turn_2_planner_receives_scope(self):
        question = (
            "wat is de status van de schrapers "
            "van die banden, zitten daar posities "
            "bij die vervangen moeten worden?"
        )

        with (
            patch.object(
                understanding_module,
                "resolve_scope_context",
                return_value=NO_SCOPE,
            ),
            patch.object(
                understanding_module,
                "validate_scope_code",
                side_effect=valid_scope,
            ),
        ):
            plan = (
                understanding_module
                .understand_query(
                    question,
                    conversation_context=MV1_CONTEXT,
                )
            )

        planned = build_execution_plan(
            plan
        )

        analysis_steps = [
            step
            for step
            in planned.execution_steps
            if step.action
            == "analysis_assistant"
        ]

        self.assertTrue(
            analysis_steps
        )

        params = (
            analysis_steps[0].params
        )

        self.assertEqual(
            params.get(
                "scope_code"
            ),
            "MV1",
        )

        self.assertEqual(
            params.get(
                "installation_code"
            ),
            "MV1",
        )

        self.assertEqual(
            params.get(
                "area_code"
            ),
            "GSL",
        )


    def test_turn_3_inherits_mv1(self):
        question = (
            "welke daarvan moeten "
            "vervangen worden?"
        )

        with (
            patch.object(
                understanding_module,
                "resolve_scope_context",
                return_value=NO_SCOPE,
            ),
            patch.object(
                understanding_module,
                "validate_scope_code",
                side_effect=valid_scope,
            ),
        ):
            plan = (
                understanding_module
                .understand_query(
                    question,
                    conversation_context=MV1_CONTEXT,
                )
            )

        self.assertEqual(
            entity(
                plan,
                "scope_code",
            ).value,
            "MV1",
        )


    def test_reference_mode_none_does_not_inherit(self):
        context = {
            "reference_mode": "none",
            "active_scope":
                MV1_CONTEXT["active_scope"],
        }

        with (
            patch.object(
                understanding_module,
                "resolve_scope_context",
                return_value=NO_SCOPE,
            ),
            patch.object(
                understanding_module,
                "validate_scope_code",
            ) as validate_mock,
        ):
            plan = (
                understanding_module
                .understand_query(
                    "welke daarvan moeten vervangen worden?",
                    conversation_context=context,
                )
            )

        validate_mock.assert_not_called()

        scope = entity(
            plan,
            "scope_code",
        )

        self.assertTrue(
            scope is None
            or scope.value != "MV1"
        )


    def test_explicit_current_scope_wins(self):
        with (
            patch.object(
                understanding_module,
                "resolve_scope_context",
                return_value=MV2_RESOLUTION,
            ),
            patch.object(
                understanding_module,
                "validate_scope_code",
            ) as validate_mock,
        ):
            plan = (
                understanding_module
                .understand_query(
                    "wat moet vervangen worden binnen MV2?",
                    conversation_context=MV1_CONTEXT,
                )
            )

        validate_mock.assert_not_called()

        self.assertEqual(
            entity(
                plan,
                "scope_code",
            ).value,
            "MV2",
        )

        self.assertEqual(
            entity(
                plan,
                "installation_code",
            ).value,
            "MV2",
        )


    def test_explicit_band_blocks_scope_inheritance(self):
        with (
            patch.object(
                understanding_module,
                "resolve_scope_context",
                return_value=NO_SCOPE,
            ),
            patch.object(
                understanding_module,
                "validate_scope_code",
            ) as validate_mock,
        ):
            plan = (
                understanding_module
                .understand_query(
                    "wanneer moet band S301 vervangen worden?",
                    conversation_context=MV1_CONTEXT,
                )
            )

        validate_mock.assert_not_called()

        self.assertEqual(
            entity(
                plan,
                "band_code",
            ).value,
            "S301",
        )

        inherited_scope = entity(
            plan,
            "scope_code",
        )

        self.assertTrue(
            inherited_scope is None
            or inherited_scope.value != "MV1"
        )


    def test_invalid_inherited_scope_is_rejected(self):
        context = {
            "reference_mode":
                "inherit_active_scope",

            "active_scope": {
                "scope_code":
                    "DITBESTAATNIET",
                "scope_type":
                    "installation",
                "installation_code":
                    "DITBESTAATNIET",
            },
        }

        with (
            patch.object(
                understanding_module,
                "resolve_scope_context",
                return_value=NO_SCOPE,
            ),
            patch.object(
                understanding_module,
                "validate_scope_code",
                return_value={
                    "valid": False,
                    "scope": None,
                },
            ),
        ):
            plan = (
                understanding_module
                .understand_query(
                    "welke daarvan moeten vervangen worden?",
                    conversation_context=context,
                )
            )

        scope = entity(
            plan,
            "scope_code",
        )

        self.assertTrue(
            scope is None
            or scope.value
            != "DITBESTAATNIET"
        )


    def test_context_field_conflict_is_rejected(self):
        context = {
            "reference_mode":
                "inherit_active_scope",

            "active_scope": {
                "scope_code": "MV1",
                "scope_type":
                    "installation",
                "area_code": "HOO7",
                "installation_code":
                    "MV1",
            },
        }

        with (
            patch.object(
                understanding_module,
                "resolve_scope_context",
                return_value=NO_SCOPE,
            ),
            patch.object(
                understanding_module,
                "validate_scope_code",
                side_effect=valid_scope,
            ),
        ):
            plan = (
                understanding_module
                .understand_query(
                    "welke daarvan moeten vervangen worden?",
                    conversation_context=context,
                )
            )

        scope = entity(
            plan,
            "scope_code",
        )

        self.assertTrue(
            scope is None
            or scope.value != "MV1"
        )


    def test_service_wires_typed_context(self):
        source = SERVICE_PATH.read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            "PROMATI_CONVERSATION_SCOPE_GROUNDING_V1",
            source,
        )

        self.assertIn(
            "payload.conversation_context",
            source,
        )

        self.assertIn(
            "run_initial_planning_stage(\n        question,\n        conversation_context,",
            source,
        )

        stage_source = (
            SERVICE_PATH.parent
            / "initial_planning_stage.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "conversation_context=conversation_context",
            stage_source,
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
