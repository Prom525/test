"""Composition shadow and legacy public-canary stage."""

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class CompositionShadowCanaryStageResult:
    answer: Any
    legacy_answer_before_public_composition_canary: Any
    evidence_pipeline: Any


def run_composition_shadow_canary_stage(
    plan: Any,
    answer: Any,
    evidence_pipeline: Any,
    *,
    build_multi_intent_composition_shadow: Callable[..., Any],
    maybe_apply_public_composition_canary: Callable[..., Any],
    public_composition_canary_enabled: Callable[[], bool],
) -> CompositionShadowCanaryStageResult:
    if isinstance(evidence_pipeline, dict):
        try:
            evidence_pipeline["multi_intent_composition_shadow"] = (
                build_multi_intent_composition_shadow(
                    plan,
                    answer,
                    evidence_pipeline,
                )
            )
        except Exception:
            evidence_pipeline["multi_intent_composition_shadow"] = None

    legacy_answer_before_public_composition_canary = answer
    if isinstance(evidence_pipeline, dict):
        try:
            (
                answer,
                evidence_pipeline["public_composition_canary_shadow"],
            ) = maybe_apply_public_composition_canary(
                plan,
                legacy_answer_before_public_composition_canary,
                evidence_pipeline,
            )
        except Exception:
            answer = legacy_answer_before_public_composition_canary
            evidence_pipeline["public_composition_canary_shadow"] = {
                "contract_version": (
                    "promati.multi_intent.public_composition_canary.v1"
                ),
                "enabled": public_composition_canary_enabled(),
                "default_enabled": False,
                "eligible": False,
                "activated": False,
                "public_answer_replaced": False,
                "target": (
                    "product_lookup_plus_technical_lookup_cema_definition"
                ),
                "release_stage": "narrow_candidate_canary",
                "fail_open_to_legacy_answer": True,
                "release_observability_contract_version": (
                    "promati.multi_intent."
                    "public_composition_canary_observability.v1"
                ),
                "reason": "blocked_internal_error_fail_open",
            }

    return CompositionShadowCanaryStageResult(
        answer=answer,
        legacy_answer_before_public_composition_canary=(
            legacy_answer_before_public_composition_canary
        ),
        evidence_pipeline=evidence_pipeline,
    )


__all__ = [
    "CompositionShadowCanaryStageResult",
    "run_composition_shadow_canary_stage",
]
