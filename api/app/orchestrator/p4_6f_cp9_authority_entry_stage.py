"""P4.6F public-composition authority entry through CP9."""

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class P46FCp9AuthorityEntryStageResult:
    answer: Any
    evidence_pipeline: Any
    task_research_semantics_cp13: Any
    task_coverage_gate_cp10: Any
    task_public_composition_authority_p4_6f: Any
    task_authority_gate_cp9: Any


def run_p4_6f_cp9_authority_entry_stage(
    plan: Any,
    answer: Any,
    legacy_answer_before_public_composition_canary: Any,
    evidence_pipeline: Any,
    task_execution_shadow: Any,
    cp11_debug_response: Any,
    *,
    build_task_coverage_gate_status: Callable[..., Any],
    build_task_research_semantics: Callable[..., Any],
    build_public_multi_intent_composition_authority_canary_p4_6f: Callable[..., Any],
    guard_public_composition_authority: Callable[..., Any],
    guard_public_composition_canary: Callable[..., Any],
) -> P46FCp9AuthorityEntryStageResult:
    answer_before_p4_6f_public_composition = answer
    task_public_composition_authority_p4_6f = None
    if cp11_debug_response and not isinstance(evidence_pipeline, dict):
        evidence_pipeline = {}
    task_coverage_gate_cp10 = build_task_coverage_gate_status(
        task_execution_shadow,
        (
            evidence_pipeline.get(
                "task_grounded_synthesis_coverage_authority_p4_6e3"
            )
            if isinstance(evidence_pipeline, dict)
            else None
        ),
    )
    task_research_semantics_cp13 = None
    task_authority_gate_cp9 = None
    if isinstance(evidence_pipeline, dict):
        try:
            task_research_semantics_cp13 = build_task_research_semantics(
                plan,
                task_execution_shadow,
                evidence_pipeline.get("task_research_authority_p4_6d1"),
                task_coverage_gate_cp10,
            )
        except Exception:
            task_research_semantics_cp13 = {
                "contract_version": (
                    "promati.orchestrator.task_research_semantics.cp13.v1"
                ),
                "evaluated": False,
                "authoritative": False,
                "authority_scope": "intent_task_research_eligibility_only",
                "public_answer_authority": False,
                "evidence_authority": False,
                "synthesis_authority": False,
                "legacy_generic_research_allowed": False,
                "explicit_research_requested": (
                    "explicit_research_request"
                    in set(getattr(plan, "complexity_reasons", None) or [])
                ),
                "allowed_task_ids": [],
                "tasks": [],
                "reason": "internal_error_fail_closed",
            }
        evidence_pipeline["task_research_semantics_cp13"] = (
            task_research_semantics_cp13
        )
        try:
            (
                answer,
                task_public_composition_authority_p4_6f,
            ) = build_public_multi_intent_composition_authority_canary_p4_6f(
                plan,
                answer_before_p4_6f_public_composition,
                evidence_pipeline.get(
                    "task_grounded_synthesis_coverage_authority_p4_6e3"
                ),
            )
        except Exception:
            answer = answer_before_p4_6f_public_composition
            task_public_composition_authority_p4_6f = None

        (
            answer,
            task_public_composition_authority_p4_6f,
            task_authority_gate_cp9,
        ) = guard_public_composition_authority(
            answer,
            legacy_answer_before_public_composition_canary,
            task_public_composition_authority_p4_6f,
            task_execution_shadow,
        )

        evidence_pipeline["public_composition_canary_shadow"] = (
            guard_public_composition_canary(
                evidence_pipeline.get("public_composition_canary_shadow"),
                task_authority_gate_cp9,
            )
        )
        evidence_pipeline["task_public_composition_authority_p4_6f"] = (
            task_public_composition_authority_p4_6f
        )
        evidence_pipeline["task_authority_gate_cp9"] = task_authority_gate_cp9

    return P46FCp9AuthorityEntryStageResult(
        answer=answer,
        evidence_pipeline=evidence_pipeline,
        task_research_semantics_cp13=task_research_semantics_cp13,
        task_coverage_gate_cp10=task_coverage_gate_cp10,
        task_public_composition_authority_p4_6f=(
            task_public_composition_authority_p4_6f
        ),
        task_authority_gate_cp9=task_authority_gate_cp9,
    )


__all__ = [
    "P46FCp9AuthorityEntryStageResult",
    "run_p4_6f_cp9_authority_entry_stage",
]
