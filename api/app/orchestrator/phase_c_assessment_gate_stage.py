from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class PhaseCAssessmentGateStageResult:
    initial_assessment: Any
    research_decision: Any


def run_phase_c_assessment_gate_stage(
    timings: Any,
    requirement_set: Any,
    working_evidence_items: Any,
    retrieved_at: Any,
    task_research_semantics_cp13: Any,
    *,
    _observability_call: Callable[..., Any],
    assess_evidence: Callable[..., Any],
    decide_research_requirement: Callable[..., Any],
    gate_legacy_generic_research: Callable[..., Any],
) -> PhaseCAssessmentGateStageResult:
    initial_assessment = _observability_call(
        timings,
        "evidence_assessment",
        assess_evidence,
        requirement_set,
        working_evidence_items,
        target_entity_ids=None,
        now=retrieved_at,
    )
    research_decision = _observability_call(
        timings,
        "evidence_research_gate",
        decide_research_requirement,
        initial_assessment,
    )
    research_decision = gate_legacy_generic_research(
        research_decision,
        task_research_semantics_cp13,
    )
    return PhaseCAssessmentGateStageResult(
        initial_assessment,
        research_decision,
    )
