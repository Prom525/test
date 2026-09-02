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


from app.orchestrator.models import (  # noqa: E402
    ConversationContext,
    ConversationScopeContext,
    OrchestratorAskRequest,
)


def dump_model(model):
    if hasattr(
        model,
        "model_dump",
    ):
        return model.model_dump()

    return model.dict()


def schema_for(model):
    if hasattr(
        model,
        "model_json_schema",
    ):
        return model.model_json_schema()

    return model.schema()


class ConversationContextContractTests(
    unittest.TestCase
):

    def test_old_request_remains_valid(self):
        request = OrchestratorAskRequest(
            vraag="Geef vervangadvies voor band A660."
        )

        self.assertEqual(
            request.vraag,
            "Geef vervangadvies voor band A660.",
        )

        self.assertIsNone(
            request.conversation_context
        )


    def test_original_question_is_not_rewritten(self):
        original = (
            "wat is de status van de schrapers "
            "van die banden?"
        )

        request = OrchestratorAskRequest(
            vraag=original,
            conversation_context=ConversationContext(
                reference_mode="inherit_active_scope",
                active_scope=ConversationScopeContext(
                    scope_code="MV1",
                    area_code="MV1",
                ),
            ),
        )

        self.assertEqual(
            request.vraag,
            original,
        )


    def test_active_scope_accepts_mv1_context(self):
        request = OrchestratorAskRequest(
            vraag="welke daarvan moeten vervangen worden?",
            conversation_context={
                "reference_mode": "inherit_active_scope",
                "active_scope": {
                    "scope_code": "MV1",
                    "scope_type": "area",
                    "area_code": "MV1",
                },
            },
        )

        context = request.conversation_context

        self.assertIsNotNone(
            context
        )

        self.assertEqual(
            context.reference_mode,
            "inherit_active_scope",
        )

        self.assertEqual(
            context.active_scope.scope_code,
            "MV1",
        )

        self.assertEqual(
            context.active_scope.area_code,
            "MV1",
        )


    def test_active_scope_supports_single_band(self):
        context = ConversationContext(
            reference_mode="inherit_active_scope",
            active_scope=ConversationScopeContext(
                band_code="S301",
            ),
        )

        self.assertEqual(
            context.active_scope.band_code,
            "S301",
        )


    def test_context_contract_does_not_contain_band_list(self):
        fields = getattr(
            ConversationScopeContext,
            "model_fields",
            None,
        )

        if fields is None:
            fields = getattr(
                ConversationScopeContext,
                "__fields__",
            )

        self.assertNotIn(
            "band_codes",
            fields,
        )


    def test_request_schema_exposes_conversation_context(self):
        schema = schema_for(
            OrchestratorAskRequest
        )

        properties = schema.get(
            "properties",
            {},
        )

        self.assertIn(
            "conversation_context",
            properties,
        )


    def test_context_is_serializable(self):
        request = OrchestratorAskRequest(
            vraag="en alleen de U-posities?",
            conversation_context=ConversationContext(
                reference_mode="inherit_active_scope",
                active_scope=ConversationScopeContext(
                    scope_code="MV1",
                    area_code="MV1",
                ),
            ),
        )

        payload = dump_model(
            request
        )

        self.assertEqual(
            payload["vraag"],
            "en alleen de U-posities?",
        )

        self.assertEqual(
            payload["conversation_context"][
                "active_scope"
            ]["scope_code"],
            "MV1",
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
