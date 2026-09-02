from __future__ import annotations

import unittest
from pathlib import Path


SERVICE = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "orchestrator"
    / "service.py"
)


class ExecutionStatusWiringTests(
    unittest.TestCase
):
    def test_service_status_uses_typed_policy(
        self,
    ):
        text = SERVICE.read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            (
                "from app.orchestrator.execution_status "
                "import has_service_accepted_execution"
            ),
            text,
        )

        self.assertIn(
            (
                "not has_service_accepted_execution(\n"
                "            typed_execution_results,\n"
                "            results,\n"
                "        )"
            ),
            text,
        )

        old = (
            'not any(\n'
            '            item.get("accepted") is True\n'
            '            for item in results\n'
            '        )'
        )

        self.assertNotIn(
            old,
            text,
        )

        clarification_pos = text.index(
            "specialist_clarification"
        )

        typed_gate_pos = text.index(
            "not has_service_accepted_execution("
        )

        self.assertLess(
            clarification_pos,
            typed_gate_pos,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
