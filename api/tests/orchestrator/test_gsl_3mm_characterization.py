from __future__ import annotations

import json
from pathlib import Path

from app.orchestrator.planner import build_execution_plan
from app.orchestrator.routing_sanity import apply_routing_sanity
from app.orchestrator.understanding import understand_query


QUESTION = "Geef voor GSL de schrapers die nu op of rond de 3 mm grens zitten."
GAP = Path(__file__).resolve().parents[1] / "fixtures" / "gsl_3mm_known_gap.json"


def _value(value):
    return getattr(value, "value", value)


def test_gsl_3mm_current_observed_behavior_is_locked():
    plan = build_execution_plan(apply_routing_sanity(understand_query(QUESTION)))
    assert _value(plan.query_class) == "business"
    assert [_value(item) for item in plan.domains] == []
    assert [_value(item) for item in plan.excluded_domains] == []
    assert plan.intent == "unknown"
    assert plan.intent_tasks == []
    assert plan.execution_steps == []
    assert "band_code" not in plan.entities
    assert plan.clarification_required is True
    assert plan.execution_blockers[0].candidate_value == "DE3"
    assert "DE3" in (plan.clarification_question or "")


def test_gsl_3mm_gap_registration_distinguishes_current_and_desired():
    gap = json.loads(GAP.read_text(encoding="utf-8"))
    assert gap["classification"] == "known_baseline_gap"
    assert gap["current_observed"]["false_band_candidate"] == "DE3"
    assert gap["current_observed"]["action"] is None
    assert gap["current_observed"]["public_answer_detail_rows"] is False
    assert gap["desired_future"]["action"] == "analysis_maintenance_positions"
    assert gap["desired_future"]["endpoint"] == "/analysis/maintenance/positions"
    assert gap["desired_future"]["result_path"] == "resultaat"
    assert gap["desired_future"]["public_answer_detail_rows"] is True
    assert gap["desired_future"]["implemented"] is False

