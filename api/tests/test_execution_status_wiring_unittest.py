from __future__ import annotations

import unittest
from pathlib import Path


SERVICE = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "orchestrator"
    / "service.py"
)
STAGE = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "orchestrator"
    / "post_phase_c_status_stage.py"
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
        stage_text = STAGE.read_text(
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
                "not has_service_accepted_execution_callable(\n"
                "            typed_execution_results,\n"
                "            results,\n"
                "        )"
            ),
            stage_text,
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
            "run_post_phase_c_status_stage("
        )

        typed_gate_pos = stage_text.index(
            "not has_service_accepted_execution_callable("
        )

        self.assertLess(
            clarification_pos,
            text.index("PROMATI_BOUNDED_RESEARCH_V1_GATE"),
        )
        self.assertIn("specialist_clarification", stage_text[:typed_gate_pos])


if __name__ == "__main__":
    unittest.main(verbosity=2)
