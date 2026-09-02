from __future__ import annotations

import json
import unittest
from types import SimpleNamespace

from app.orchestrator import service


class EvidencePipelineSerializerTrustBoundaryV1Tests(
    unittest.TestCase
):
    def test_unknown_object_is_discarded(self):
        value = {
            "valid": "retained",
            "unsupported": SimpleNamespace(
                secret="must-not-escape"
            ),
        }

        converted = (
            service._evidence_pipeline_to_dict(
                value
            )
        )

        self.assertEqual(
            converted,
            {
                "valid": "retained",
                "unsupported": None,
            },
        )
        self.assertEqual(
            json.loads(json.dumps(converted)),
            converted,
        )

    def test_set_is_sorted_deterministically(self):
        first = service._evidence_pipeline_to_dict(
            {"values": {"beta", "alpha"}}
        )
        second = service._evidence_pipeline_to_dict(
            {"values": {"alpha", "beta"}}
        )

        self.assertEqual(first, second)
        self.assertEqual(
            first,
            {"values": ["alpha", "beta"]},
        )
        self.assertEqual(
            json.loads(json.dumps(first)),
            first,
        )


if __name__ == "__main__":
    unittest.main()