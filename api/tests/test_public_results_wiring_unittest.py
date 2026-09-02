from __future__ import annotations

import unittest
from pathlib import Path


SERVICE = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "orchestrator"
    / "service.py"
)


class PublicResultsWiringTests(
    unittest.TestCase
):
    def test_public_results_projection_is_wired_after_presentation(
        self,
    ):
        text = SERVICE.read_text(
            encoding="utf-8-sig"
        )

        answer_pos = text.index(
            "answer = _build_user_answer("
        )

        public_pos = text.index(
            "public_results = ("
        )

        self.assertLess(
            answer_pos,
            public_pos,
        )

        self.assertIn(
            "results\n"
            "            if payload.include_trace",
            text,
        )

        self.assertIn(
            '"results": public_results,',
            text,
        )

        self.assertIn(
            "compact_results_for_public_response",
            text,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
