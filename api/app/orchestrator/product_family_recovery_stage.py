"""Product-family coverage and bounded recovery for Phase C."""

from dataclasses import dataclass
from typing import Any, Callable


__all__ = ["ProductFamilyRecoveryResult", "run_product_family_recovery_stage"]


@dataclass(frozen=True)
class ProductFamilyRecoveryResult:
    product_family_coverage: Any
    product_family_recovery: Any
    working_evidence_items: tuple[Any, ...]


def run_product_family_recovery_stage(
    plan: Any,
    requirement_set: Any,
    initial_evidence_items: tuple[Any, ...],
    working_evidence_items: tuple[Any, ...],
    retrieved_at: Any,
    counts: dict[str, int],
    sender: Any,
    *,
    assess_product_family_coverage: Callable[..., Any],
    recover_missing_product_families: Callable[..., Any],
    normalize_execution_result_evidence: Callable[..., Any],
    observability_nonnegative_int: Callable[[Any], int],
) -> ProductFamilyRecoveryResult:
    """Run the characterized product-family recovery boundary."""
    product_family_coverage = assess_product_family_coverage(
        requirement_set,
        working_evidence_items,
        plan,
        now=retrieved_at,
    )

    product_family_recovery = {
        "contract_version": (
            "promati.orchestrator.product_family_evidence.v1"
        ),
        "performed": False,
        "requested_family_codes": [],
        "attempted_family_codes": [],
        "attempted_call_count": 0,
        "accepted_result_count": 0,
        "skipped_budget_family_codes": [],
        "skipped_missing_step_family_codes": [],
    }

    missing_product_families = tuple(
        product_family_coverage.get("missing_family_codes") or ()
    )

    if product_family_coverage.get("applicable") and missing_product_families:
        recovery_typed_results = []

        _, product_family_recovery = recover_missing_product_families(
            plan,
            missing_product_families,
            sender=sender,
            shadow_observer=recovery_typed_results.append,
        )

        counts["phase_c_research_follow_up_specialist_calls"] += (
            observability_nonnegative_int(
                product_family_recovery.get("attempted_call_count")
            )
        )

        recovered_evidence_items = tuple(
            evidence_item
            for execution_result in recovery_typed_results
            for evidence_item in normalize_execution_result_evidence(
                execution_result,
                retrieved_at=retrieved_at,
            )
        )

        working_evidence_items = (
            tuple(initial_evidence_items) + tuple(recovered_evidence_items)
        )

        product_family_coverage = assess_product_family_coverage(
            requirement_set,
            working_evidence_items,
            plan,
            now=retrieved_at,
        )

    return ProductFamilyRecoveryResult(
        product_family_coverage=product_family_coverage,
        product_family_recovery=product_family_recovery,
        working_evidence_items=working_evidence_items,
    )
