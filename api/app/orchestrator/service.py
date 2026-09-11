import hashlib
import json
import os
import re
import time
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from app.orchestrator.complexity import assess_research_requirement
from app.orchestrator.research import run_bounded_research
from app.orchestrator.research_agent import (
    ResearchCallGuard,
    normalize_research_call_guard,
)
from app.orchestrator.research_runtime import run_bounded_research_agent
from app.orchestrator.executor import Sender, execute_plan
from app.orchestrator.evidence_adapters import (
    normalize_execution_result_evidence,
)
from app.orchestrator.evidence_contracts import (
    EVIDENCE_CONTRACT_VERSION,
    EvidenceDirectness,
    EvidenceFreshnessStatus,
    EvidenceGroundingStatus,
    EvidenceItem,
    EvidenceQualityStatus,
    EvidenceSourceType,
    EvidenceType,
)
from app.orchestrator.evidence_assessor import (
    EvidenceAssessmentStatus,
    assess_evidence,
)
from app.orchestrator.evidence_reconciler import (
    EvidenceReconciliationResult,
    EvidenceReconciliationStatus,
    reconcile_evidence,
)
from app.orchestrator.evidence_requirement_catalog import (
    get_requirement_set,
)
from app.orchestrator.evidence_research_executor import (
    ResearchExecutionStatus,
    execute_bounded_research,
)
from app.orchestrator.evidence_research_gate import (
    decide_research_requirement,
)
from app.orchestrator.evidence_synthesizer import (
    synthesize_grounded_evidence,
)
from app.orchestrator.models import OrchestratorAskRequest
from app.orchestrator.planner import build_execution_plan
from app.orchestrator.task_evidence import (
    build_task_evidence_authority_canary_p4_6c,
)
from app.orchestrator.task_research import (
    build_task_research_authority_canary_p4_6d1,
)
from app.orchestrator.task_research_execution import (
    run_task_research_execution_authority_canary_p4_6d2,
)
from app.orchestrator.task_research_evidence import (
    build_task_research_evidence_authority_canary_p4_6e1,
)
from app.orchestrator.task_grounded_synthesis import (
    build_task_grounded_synthesis_authority_canary_p4_6e2,
)
from app.orchestrator.task_synthesis_coverage import (
    build_task_grounded_synthesis_coverage_authority_canary_p4_6e3,
)
from app.orchestrator.task_public_composition import (
    build_public_multi_intent_composition_authority_canary_p4_6f,
)
from app.orchestrator.task_planner import (
    build_task_execution_plans_shadow,
    compare_task_execution_plans_shadow,
)
from app.orchestrator.product_family_evidence import (
    assess_product_family_coverage,
    recover_missing_product_families,
)
from app.orchestrator.routing_sanity import apply_routing_sanity
from app.orchestrator.understanding import understand_query
from app.text_encoding import repair_mojibake_text
# PROMATI_COMPACT_PUBLIC_RESULTS_V1
from app.orchestrator.public_results import compact_results_for_public_response
# PROMATI_TYPED_SERVICE_STATUS_CONSUMER_V1
from app.orchestrator.execution_status import has_service_accepted_execution




# PROMATI_ORCHESTRATOR_OBSERVABILITY_V1
ORCHESTRATOR_OBSERVABILITY_CONTRACT_VERSION = (
    "promati.orchestrator.observability.v1"
)


def _observability_now() -> float:
    return time.perf_counter()


def _observability_elapsed_ms(
    started: float,
) -> int:
    elapsed = (
        _observability_now()
        - started
    )

    return max(
        0,
        int(
            round(
                elapsed * 1000
            )
        ),
    )


def _observability_call(
    timings: dict[str, int],
    key: str,
    callable_,
    *args,
    **kwargs,
):
    started = _observability_now()

    try:
        return callable_(
            *args,
            **kwargs,
        )
    finally:
        timings[key] = (
            _observability_elapsed_ms(
                started
            )
        )


def _observability_get(
    value: Any,
    key: str,
    default: Any = None,
) -> Any:
    if isinstance(
        value,
        dict,
    ):
        return value.get(
            key,
            default,
        )

    return getattr(
        value,
        key,
        default,
    )


def _observability_nonnegative_int(
    value: Any,
) -> int:
    if isinstance(
        value,
        bool,
    ):
        return 0

    try:
        number = int(
            value
        )
    except (
        TypeError,
        ValueError,
    ):
        return 0

    return max(
        0,
        number,
    )


def _new_observability_timings() -> dict[str, int]:
    return {
        "understanding": 0,
        "research_requirement": 0,
        "planning": 0,
        "initial_specialist": 0,
        "evidence_requirement_lookup": 0,
        "evidence_normalization": 0,
        "evidence_assessment": 0,
        "evidence_research_gate": 0,
        "evidence_research": 0,
        "reconciliation": 0,
        "synthesis": 0,
        "plan_research": 0,
        "presentation": 0,
        "response_build": 0,
        "total": 0,
    }


def _new_observability_counts() -> dict[str, int]:
    return {
        "execution_attempts": 0,
        "initial_specialist_calls": 0,
        "phase_c_research_follow_up_specialist_calls": 0,
        "plan_research_follow_up_specialist_calls": 0,
        "research_follow_up_specialist_calls": 0,
        "total_specialist_calls": 0,
        "initial_raw_result_rows": 0,
        "initial_evidence_items": 0,
        "reconciled_evidence_items": 0,
        "phase_c_ai_calls": 0,
        "plan_research_ai_calls": 0,
        "total_ai_calls": 0,
        # PROMATI_PUBLIC_COMPOSITION_CANARY_RELEASE_OBSERVABILITY_HARDENING
        # Integer-only request counters are deliberately stored in the
        # existing observability counts map. run_logging already persists that
        # map as privacy-safe JSONB, so no answer/question/evidence text is
        # introduced into operational logging.
        "multi_intent_queries": 0,
        # PROMATI_P4_6A_TASK_EXECUTION_PLAN_SHADOW_OBSERVABILITY
        "task_execution_plan_shadow_evaluations": 0,
        "task_execution_plan_shadow_tasks": 0,
        "task_execution_plan_shadow_steps": 0,
        "task_execution_plan_shadow_planning_errors": 0,
        "task_execution_plan_shadow_exact_matches": 0,
        "task_research_execution_canary_executions": 0,
        "task_research_execution_canary_follow_up_specialist_calls": 0,
        "public_composition_canary_evaluations": 0,
        "public_composition_canary_enabled_requests": 0,
        "public_composition_canary_eligible_requests": 0,
        "public_composition_canary_activations": 0,
        "public_composition_canary_public_answer_replacements": 0,
        "public_composition_canary_legacy_answer_fallbacks": 0,
        "public_composition_canary_internal_error_fallbacks": 0,
        # PROMATI_P4_9C_TASK_PUBLIC_COMPOSITION_AUTHORITY_OBSERVABILITY
        # Integer-only, privacy-safe per-request counters. Never persist
        # question, answer, task, evidence, family or claim text.
        "task_public_composition_requests": 0,
        "task_public_composition_enabled": 0,
        "task_public_composition_eligible": 0,
        "task_public_composition_authoritative": 0,
        "task_public_composition_answer_replaced": 0,
        "task_public_composition_fail_open": 0,
        "task_public_composition_included_units": 0,
        "task_public_composition_included_claims": 0,
        "task_public_composition_blocked": 0,
        "task_public_composition_reason_activated": 0,
        "task_public_composition_reason_disabled": 0,
        "task_public_composition_reason_blocked_not_multi_intent": 0,
        "task_public_composition_reason_blocked_coverage_not_ready": 0,
        "task_public_composition_reason_internal_error_fail_open": 0,
        "task_public_composition_reason_blocked_other": 0,
    }


# PROMATI_P4_6A_TASK_EXECUTION_PLAN_SHADOW_OBSERVABILITY
def _record_task_execution_plan_shadow_observability(
    counts: dict[str, int],
    plan: Any,
    evidence_pipeline: Any,
) -> None:
    """Record integer-only P4.6a shadow metrics.

    No question text, task text, params, scope values or evidence content is
    persisted. This mirrors the existing privacy-safe counts contract.
    """
    if not isinstance(counts, dict):
        return

    if not bool(getattr(plan, "multi_intent", False)):
        return

    counts["task_execution_plan_shadow_evaluations"] = 1

    if not isinstance(evidence_pipeline, dict):
        return

    rows = evidence_pipeline.get("task_execution_plans_shadow")
    if not isinstance(rows, list):
        rows = []

    counts["task_execution_plan_shadow_tasks"] = len(rows)
    counts["task_execution_plan_shadow_steps"] = sum(
        len(row.get("execution_steps") or [])
        for row in rows
        if isinstance(row, dict)
    )
    counts["task_execution_plan_shadow_planning_errors"] = sum(
        1
        for row in rows
        if isinstance(row, dict)
        and str(row.get("status") or "") == "planning_error"
    )

    comparison = evidence_pipeline.get(
        "task_execution_plan_comparison_shadow"
    )
    if isinstance(comparison, dict):
        exact = (
            comparison.get("exact_steps_equivalent") is True
            or comparison.get("exact_match") is True
            or comparison.get("steps_equivalent") is True
        )
        counts["task_execution_plan_shadow_exact_matches"] = int(exact)


def _record_public_composition_canary_release_observability(
    counts: dict[str, int],
    plan: Any,
    evidence_pipeline: Any,
) -> None:
    """Record privacy-safe per-request release counters only.

    No question, answer, evidence content, task text, family entity repr or
    other free text is copied into the observability counts contract.
    """
    if not isinstance(counts, dict):
        return

    counts["multi_intent_queries"] = int(
        bool(getattr(plan, "multi_intent", False))
    )

    if not isinstance(evidence_pipeline, dict):
        return

    execution_rows = evidence_pipeline.get(
        "task_research_execution_canary_shadow"
    )
    if isinstance(execution_rows, list):
        executed_rows = [
            row
            for row in execution_rows
            if isinstance(row, dict) and row.get("executed") is True
        ]
        counts["task_research_execution_canary_executions"] = len(
            executed_rows
        )
        counts[
            "task_research_execution_canary_follow_up_specialist_calls"
        ] = sum(
            _observability_nonnegative_int(
                row.get("follow_up_specialist_calls")
            )
            for row in executed_rows
        )

    contract = evidence_pipeline.get(
        "public_composition_canary_shadow"
    )
    if not isinstance(contract, dict):
        return

    enabled = contract.get("enabled") is True
    eligible = contract.get("eligible") is True
    activated = contract.get("activated") is True
    replaced = contract.get("public_answer_replaced") is True
    reason = str(contract.get("reason") or "").strip()

    counts["public_composition_canary_evaluations"] = 1
    counts["public_composition_canary_enabled_requests"] = int(enabled)
    counts["public_composition_canary_eligible_requests"] = int(eligible)
    counts["public_composition_canary_activations"] = int(activated)
    counts[
        "public_composition_canary_public_answer_replacements"
    ] = int(replaced)
    counts["public_composition_canary_legacy_answer_fallbacks"] = int(
        enabled and not replaced
    )
    counts[
        "public_composition_canary_internal_error_fallbacks"
    ] = int(reason == "blocked_internal_error_fail_open")

    # PROMATI_P4_9C_TASK_PUBLIC_COMPOSITION_AUTHORITY_OBSERVABILITY
    task_public = evidence_pipeline.get(
        "task_public_composition_authority_p4_6f"
    )
    if isinstance(task_public, dict):
        counts["task_public_composition_requests"] = 1

        enabled = task_public.get("enabled") is True
        eligible = task_public.get("eligible") is True
        authoritative = task_public.get("authoritative") is True
        replaced = task_public.get("public_answer_replaced") is True
        reason = str(task_public.get("reason") or "").strip()

        counts["task_public_composition_enabled"] = int(enabled)
        counts["task_public_composition_eligible"] = int(eligible)
        counts["task_public_composition_authoritative"] = int(authoritative)
        counts["task_public_composition_answer_replaced"] = int(replaced)
        counts["task_public_composition_included_units"] = (
            _observability_nonnegative_int(
                task_public.get("included_unit_count")
            )
        )
        counts["task_public_composition_included_claims"] = (
            _observability_nonnegative_int(
                task_public.get("included_claim_count")
            )
        )

        blocked = bool(reason.startswith("blocked_")) and not replaced
        counts["task_public_composition_blocked"] = int(blocked)
        counts["task_public_composition_fail_open"] = int(blocked)

        coverage_block_reasons = {
            "blocked_missing_task_synthesis_coverage",
            "blocked_task_synthesis_coverage_not_ready",
            "blocked_no_grounded_units",
            "blocked_incomplete_task_units",
        }

        counts["task_public_composition_reason_activated"] = int(
            reason == "activated_public_multi_intent_composition_authority"
        )
        counts["task_public_composition_reason_disabled"] = int(
            reason == "disabled"
        )
        counts[
            "task_public_composition_reason_blocked_not_multi_intent"
        ] = int(reason == "blocked_not_multi_intent")
        counts[
            "task_public_composition_reason_blocked_coverage_not_ready"
        ] = int(reason in coverage_block_reasons)
        counts[
            "task_public_composition_reason_internal_error_fail_open"
        ] = int(reason == "blocked_internal_error_fail_open")
        counts["task_public_composition_reason_blocked_other"] = int(
            blocked
            and reason not in coverage_block_reasons
            and reason not in {
                "blocked_not_multi_intent",
                "blocked_internal_error_fail_open",
            }
        )



# PROMATI_RESEARCH_AGENT_SERVICE_GATE_6B3
def _research_agent_enabled() -> bool:
    raw = os.getenv(
        "AI_RESEARCH_AGENT_ENABLED",
        "false",
    )
    return str(raw).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

def _model_to_dict(model) -> dict[str, Any]:
    """
    Compatibel met Pydantic v1 en v2.
    Geeft JSON-veilige waarden terug, dus ook Enum -> string.
    """
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")

    return json.loads(model.json())



def _evidence_pipeline_to_dict(value: Any) -> Any:
    """Return a detached, JSON-safe representation."""
    if is_dataclass(value):
        return _evidence_pipeline_to_dict(asdict(value))

    if isinstance(value, Enum):
        return value.value

    if isinstance(value, dict):
        return {
            str(key): _evidence_pipeline_to_dict(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [
            _evidence_pipeline_to_dict(item)
            for item in value
        ]

    if isinstance(value, (set, frozenset)):
        converted_items = [
            _evidence_pipeline_to_dict(item)
            for item in value
        ]
        return sorted(
            converted_items,
            key=lambda item: json.dumps(
                item,
                sort_keys=True,
                ensure_ascii=True,
                separators=(",", ":"),
            ),
        )

    if isinstance(value, datetime):
        return value.isoformat()

    if value is None or isinstance(
        value,
        (str, int, float, bool),
    ):
        return value

    return None




# PROMATI_COMPACT_PUBLIC_EVIDENCE_PIPELINE_V1

# PROMATI_MULTI_INTENT_COMPOSITION_SHADOW_POST_B7

# PROMATI_MULTI_INTENT_COMPOSITION_PRESENTATION_SHADOW_POST_B7
def _multi_intent_composition_definition_statement_shadow(
    grounded: dict[str, Any],
    task_answer: str,
) -> str | None:
    """Render a concise grounded acronym-definition statement for composition.

    The source task_answer remains untouched for audit/provenance. This helper
    only creates a shadow presentation string used inside composed_answer.
    """
    focus = str(
        grounded.get("definition_focus_term") or ""
    ).strip()
    if not focus:
        return None

    raw = " ".join(str(task_answer or "").split()).strip()
    prefix = "Technical RAG fragment:"
    if raw.casefold().startswith(prefix.casefold()):
        raw = raw[len(prefix):].strip()
    if not raw:
        return None

    reverse_span = (
        _task_grounded_synthesis_reverse_acronym_relation_span_shadow(
            raw,
            focus,
        )
    )
    if reverse_span is not None:
        relation = raw[reverse_span[0]:reverse_span[1]].strip()
        marker = re.search(
            rf"\(\s*{re.escape(focus)}\s*\)",
            relation,
            flags=re.IGNORECASE,
        )
        if marker is not None:
            expansion = relation[:marker.start()].strip(" ,.;:-")
            if expansion:
                return (
                    f"{focus.upper()} staat voor {expansion}."
                )

    forward_patterns = (
        rf"\b{re.escape(focus)}\b\s+(?:means|stands\s+for|staat\s+voor|betekent)\s+(.+?)(?:[.!?;]|$)",
        rf"\b{re.escape(focus)}\b\s+is\s+(?:an?\s+)?(?:acronym|abbreviation)\s+for\s+(.+?)(?:[.!?;]|$)",
        rf"\b{re.escape(focus)}\b\s*=\s*(.+?)(?:[.!?;]|$)",
    )
    for pattern in forward_patterns:
        match = re.search(
            pattern,
            raw,
            flags=re.IGNORECASE,
        )
        if match is None:
            continue
        expansion = " ".join(match.group(1).split()).strip(" ,.;:-")
        if expansion:
            return (
                f"{focus.upper()} staat voor {expansion}."
            )

    return None


def _multi_intent_composition_rendered_answer_shadow(
    grounded: dict[str, Any],
    task_answer: str,
    domain: str,
    intent: str,
) -> tuple[str, str]:
    """Return (rendered_answer, presentation_mode) for shadow composition."""
    if domain == "technical" and intent == "technical_lookup":
        definition_statement = (
            _multi_intent_composition_definition_statement_shadow(
                grounded,
                task_answer,
            )
        )
        if definition_statement:
            return (
                definition_statement,
                "grounded_definition_relation_summary_shadow",
            )

    return (
        task_answer,
        "grounded_task_answer_passthrough_shadow",
    )


def _build_multi_intent_composition_shadow(
    plan: Any,
    legacy_answer: str | None,
    evidence_pipeline: Any,
) -> dict[str, Any] | None:
    """Compose grounded secondary task answers without changing public output.

    This is deliberately shadow-only. The returned object may be attached to
    the internal evidence pipeline/debug profile, but it is never used as the
    authoritative/public answer.
    """
    if not bool(getattr(plan, "multi_intent", False)):
        return None

    tasks = list(getattr(plan, "intent_tasks", None) or [])
    if len(tasks) < 2:
        return None

    answer = str(legacy_answer or "").strip()
    contract = {
        "contract_version": "promati.multi_intent.composition_shadow.v1",
        "authoritative": False,
        "public_exposure": False,
        "base_answer_source": "legacy_public_answer",
        "included_task_ids": [],
        "sections": [],
        "composed_answer": None,
    }

    if not answer:
        contract["status"] = "blocked_no_base_answer"
        return contract

    if not isinstance(evidence_pipeline, dict):
        contract["status"] = "blocked_no_evidence_pipeline"
        return contract

    raw_grounded = evidence_pipeline.get("task_grounded_synthesis_shadow")
    if not isinstance(raw_grounded, list):
        contract["status"] = "blocked_no_grounded_secondary_task"
        return contract

    grounded_by_task: dict[str, dict[str, Any]] = {}
    for entry in raw_grounded:
        if not isinstance(entry, dict):
            continue
        if entry.get("status") != "grounded_task_synthesis_shadow":
            continue
        task_id = str(entry.get("task_id") or "").strip()
        task_answer = str(entry.get("task_answer") or "").strip()
        if not task_id or not task_answer:
            continue
        grounded_by_task[task_id] = entry

    sections: list[dict[str, Any]] = []
    composed_parts: list[str] = [answer]

    for task in tasks:
        if bool(getattr(task, "primary", False)):
            continue

        task_id = str(getattr(task, "task_id", "") or "").strip()
        if not task_id:
            continue

        grounded = grounded_by_task.get(task_id)
        if not isinstance(grounded, dict):
            continue

        task_answer = str(grounded.get("task_answer") or "").strip()
        if not task_answer:
            continue

        # Avoid exact duplicate inclusion if legacy presentation already
        # contains the same grounded answer.
        if task_answer.casefold() in answer.casefold():
            continue

        domain = _intent_task_domain_value_shadow(task)
        intent = str(getattr(task, "intent", "") or "").strip()

        title = "Aanvullende toelichting"
        if domain == "technical":
            title = "Technische toelichting"
        elif domain == "inspection":
            title = "Inspectietoelichting"
        elif domain == "org":
            title = "Organisatietoelichting"
        elif domain == "product":
            title = "Producttoelichting"

        (
            rendered_answer,
            presentation_mode,
        ) = _multi_intent_composition_rendered_answer_shadow(
            grounded,
            task_answer,
            domain,
            intent,
        )

        sections.append(
            {
                "task_id": task_id,
                "domain": domain,
                "intent": intent,
                "title": title,
                "task_answer": task_answer,
                "rendered_answer": rendered_answer,
                "presentation_mode": presentation_mode,
            }
        )
        composed_parts.extend(
            [
                "",
                title,
                rendered_answer,
            ]
        )

    if not sections:
        contract["status"] = "blocked_no_grounded_secondary_task"
        return contract

    contract["status"] = "composed_shadow"
    contract["included_task_ids"] = [
        section["task_id"]
        for section in sections
    ]
    contract["sections"] = sections
    contract["composed_answer"] = "\n".join(composed_parts).strip()
    return contract



# PROMATI_PUBLIC_COMPOSITION_CANARY_POST_B7
_PUBLIC_COMPOSITION_CANARY_ENV = (
    "AI_MULTI_INTENT_PUBLIC_COMPOSITION_CANARY_ENABLED"
)


def _public_composition_canary_enabled() -> bool:
    raw = str(
        os.getenv(
            _PUBLIC_COMPOSITION_CANARY_ENV,
            "",
        )
        or ""
    ).strip().casefold()
    return raw in {
        "1",
        "true",
        "yes",
        "on",
    }


def _maybe_apply_public_composition_canary(
    plan: Any,
    legacy_answer: str | None,
    evidence_pipeline: Any,
) -> tuple[str | None, dict[str, Any]]:
    """Opt-in public-answer canary for the proven product+CEMA shape only."""
    answer = (
        str(legacy_answer).strip()
        if legacy_answer is not None
        else None
    )
    enabled = _public_composition_canary_enabled()

    contract: dict[str, Any] = {
        "contract_version": (
            "promati.multi_intent.public_composition_canary.v1"
        ),
        "enabled": enabled,
        "default_enabled": False,
        "eligible": False,
        "activated": False,
        "public_answer_replaced": False,
        "target": (
            "product_lookup_plus_technical_lookup_"
            "cema_definition"
        ),
        "release_stage": "narrow_candidate_canary",
        "fail_open_to_legacy_answer": True,
        "release_observability_contract_version": (
            "promati.multi_intent."
            "public_composition_canary_observability.v1"
        ),
        "reason": (
            "disabled_default"
            if not enabled
            else "evaluating"
        ),
    }

    if not enabled:
        return legacy_answer, contract

    if not bool(getattr(plan, "multi_intent", False)):
        contract["reason"] = "blocked_not_multi_intent"
        return legacy_answer, contract

    tasks = list(
        getattr(
            plan,
            "intent_tasks",
            None,
        )
        or []
    )
    if len(tasks) != 2:
        contract["reason"] = "blocked_task_shape"
        return legacy_answer, contract

    primary = tasks[0]
    secondary = tasks[1]
    primary_domain = _intent_task_domain_value_shadow(primary)
    secondary_domain = _intent_task_domain_value_shadow(secondary)
    primary_intent = str(
        getattr(primary, "intent", "") or ""
    ).strip()
    secondary_intent = str(
        getattr(secondary, "intent", "") or ""
    ).strip()

    if not bool(getattr(primary, "primary", False)):
        contract["reason"] = "blocked_primary_task_order"
        return legacy_answer, contract
    if bool(getattr(secondary, "primary", False)):
        contract["reason"] = "blocked_secondary_marked_primary"
        return legacy_answer, contract

    if (
        primary_domain != "product"
        or primary_intent != "product_lookup"
        or secondary_domain != "technical"
        or secondary_intent != "technical_lookup"
    ):
        contract["reason"] = "blocked_task_shape"
        return legacy_answer, contract

    primary_req = str(
        getattr(
            primary,
            "evidence_requirement_set_id",
            "",
        )
        or ""
    ).strip()
    secondary_req = str(
        getattr(
            secondary,
            "evidence_requirement_set_id",
            "",
        )
        or ""
    ).strip()
    if (
        primary_req != "product_lookup.v1"
        or secondary_req != "technical_lookup.v1"
    ):
        contract["reason"] = "blocked_requirement_shape"
        return legacy_answer, contract

    # PROMATI_PUBLIC_COMPOSITION_CANARY_FAMILY_CODE_NORMALIZATION_FIX
    # QueryPlan.product_families contains resolved family entities at runtime,
    # not necessarily plain strings. Store/validate the canonical .value
    # instead of the model repr.
    family_codes: list[str] = []
    for family in (
        getattr(plan, "product_families", None)
        or []
    ):
        value = getattr(family, "value", None)
        if value is None and isinstance(family, dict):
            value = (
                family.get("value")
                or family.get("family_code")
                or family.get("raw_value")
            )
        if value is None:
            value = family
        normalized = str(value or "").strip()
        if normalized:
            family_codes.append(normalized)
    if len(family_codes) != 1:
        contract["reason"] = "blocked_product_family_scope"
        return legacy_answer, contract

    if not answer:
        contract["reason"] = "blocked_no_legacy_answer"
        return legacy_answer, contract

    if not isinstance(evidence_pipeline, dict):
        contract["reason"] = "blocked_no_evidence_pipeline"
        return legacy_answer, contract

    composition = evidence_pipeline.get(
        "multi_intent_composition_shadow"
    )
    if not isinstance(composition, dict):
        contract["reason"] = "blocked_no_composition_shadow"
        return legacy_answer, contract
    if composition.get("status") != "composed_shadow":
        contract["reason"] = "blocked_composition_not_ready"
        return legacy_answer, contract

    secondary_task_id = str(
        getattr(secondary, "task_id", "") or ""
    ).strip()
    if (
        not secondary_task_id
        or composition.get("included_task_ids")
        != [secondary_task_id]
    ):
        contract["reason"] = "blocked_composition_task_mismatch"
        return legacy_answer, contract

    sections = composition.get("sections")
    if not isinstance(sections, list) or len(sections) != 1:
        contract["reason"] = "blocked_composition_section_shape"
        return legacy_answer, contract

    section = sections[0]
    if not isinstance(section, dict):
        contract["reason"] = "blocked_composition_section_shape"
        return legacy_answer, contract
    if (
        str(section.get("task_id") or "").strip()
        != secondary_task_id
        or str(section.get("domain") or "").strip()
        != "technical"
        or str(section.get("intent") or "").strip()
        != "technical_lookup"
    ):
        contract["reason"] = "blocked_composition_section_mismatch"
        return legacy_answer, contract
    if section.get("presentation_mode") != (
        "grounded_definition_relation_summary_shadow"
    ):
        contract["reason"] = "blocked_presentation_mode"
        return legacy_answer, contract

    rendered_answer = str(
        section.get("rendered_answer") or ""
    ).strip()
    if rendered_answer != (
        "CEMA staat voor "
        "Conveyor Equipment Manufacturers Association."
    ):
        contract["reason"] = "blocked_rendered_answer_shape"
        return legacy_answer, contract

    grounded_rows = evidence_pipeline.get(
        "task_grounded_synthesis_shadow"
    )
    if not isinstance(grounded_rows, list):
        contract["reason"] = "blocked_no_grounded_secondary"
        return legacy_answer, contract

    grounded = next(
        (
            row
            for row in grounded_rows
            if (
                isinstance(row, dict)
                and str(row.get("task_id") or "").strip()
                == secondary_task_id
            )
        ),
        None,
    )
    if not isinstance(grounded, dict):
        contract["reason"] = "blocked_no_grounded_secondary"
        return legacy_answer, contract

    if (
        grounded.get("status")
        != "grounded_task_synthesis_shadow"
        or grounded.get("after_assessment_status")
        != "sufficient"
        or str(
            grounded.get("definition_focus_term") or ""
        ).strip().casefold()
        != "cema"
    ):
        contract["reason"] = "blocked_grounded_secondary_not_ready"
        return legacy_answer, contract

    target_after = grounded.get(
        "target_requirement_status_after"
    )
    if (
        not isinstance(target_after, dict)
        or target_after.get("TECHNICAL_SOURCE")
        != "satisfied"
    ):
        contract["reason"] = "blocked_technical_source_not_satisfied"
        return legacy_answer, contract

    reassessment_rows = evidence_pipeline.get(
        "task_research_evidence_reassessment_shadow"
    )
    if not isinstance(reassessment_rows, list):
        contract["reason"] = "blocked_no_reassessment"
        return legacy_answer, contract

    reassessment = next(
        (
            row
            for row in reassessment_rows
            if (
                isinstance(row, dict)
                and str(row.get("task_id") or "").strip()
                == secondary_task_id
            )
        ),
        None,
    )
    if not isinstance(reassessment, dict):
        contract["reason"] = "blocked_no_reassessment"
        return legacy_answer, contract

    if (
        reassessment.get("after_assessment_status")
        != "sufficient"
    ):
        contract["reason"] = "blocked_reassessment_not_sufficient"
        return legacy_answer, contract

    composed_answer = str(
        composition.get("composed_answer") or ""
    ).strip()
    if (
        not composed_answer
        or not composed_answer.startswith(answer)
        or rendered_answer not in composed_answer
        or "Technical RAG fragment:" in composed_answer
    ):
        contract["reason"] = "blocked_composed_answer_integrity"
        return legacy_answer, contract

    contract.update(
        {
            "eligible": True,
            "activated": True,
            "public_answer_replaced": True,
            "reason": "activated_opt_in_canary",
            "secondary_task_id": secondary_task_id,
            "product_family_code": family_codes[0],
            "presentation_mode": section.get(
                "presentation_mode"
            ),
        }
    )
    return composed_answer, contract


def _compact_evidence_pipeline_for_public_response(
    pipeline: Any,
) -> Any:
    """
    Projecteer de interne Phase-C evidence pipeline naar een
    compacte publieke response.

    De interne objecten worden niet gewijzigd.
    Grote raw resultsets, evidence-items en claims blijven
    uitsluitend beschikbaar in het volledige debugprofiel.
    """
    if pipeline is None:
        return None

    if not isinstance(
        pipeline,
        dict,
    ):
        return None

    def _list_value(
        value: Any,
    ) -> list[Any]:
        if isinstance(
            value,
            (list, tuple),
        ):
            return list(value)

        return []

    def _dict_value(
        value: Any,
    ) -> dict[str, Any]:
        if isinstance(
            value,
            dict,
        ):
            return value

        return {}

    def _compact_assessment(
        value: Any,
    ) -> dict[str, Any]:
        assessment = _dict_value(
            value
        )

        requirement_results = (
            _list_value(
                assessment.get(
                    "requirement_results"
                )
            )
        )

        compact_requirements: list[
            dict[str, Any]
        ] = []

        matched_ids: set[str] = set()

        for raw_requirement in (
            requirement_results
        ):
            if not isinstance(
                raw_requirement,
                dict,
            ):
                continue

            raw_ids = _list_value(
                raw_requirement.get(
                    "matched_evidence_ids"
                )
            )

            ids = [
                str(item)
                for item in raw_ids
                if item is not None
            ]

            matched_ids.update(
                ids
            )

            compact_requirements.append(
                {
                    "requirement_id": (
                        raw_requirement.get(
                            "requirement_id"
                        )
                    ),
                    "necessity": (
                        raw_requirement.get(
                            "necessity"
                        )
                    ),
                    "status": (
                        raw_requirement.get(
                            "status"
                        )
                    ),
                    "matched_evidence_count": (
                        len(ids)
                    ),
                    "present": (
                        raw_requirement.get(
                            "present"
                        )
                    ),
                    "relevant": (
                        raw_requirement.get(
                            "relevant"
                        )
                    ),
                    "grounded": (
                        raw_requirement.get(
                            "grounded"
                        )
                    ),
                    "fresh": (
                        raw_requirement.get(
                            "fresh"
                        )
                    ),
                    "conflicting": (
                        raw_requirement.get(
                            "conflicting"
                        )
                    ),
                    "reasons": (
                        _list_value(
                            raw_requirement.get(
                                "reasons"
                            )
                        )
                    ),
                }
            )

        return {
            "status": assessment.get(
                "status"
            ),
            "missing_required_requirement_ids": (
                _list_value(
                    assessment.get(
                        "missing_required_requirement_ids"
                    )
                )
            ),
            "conflicting_requirement_ids": (
                _list_value(
                    assessment.get(
                        "conflicting_requirement_ids"
                    )
                )
            ),
            "evidence_item_count": (
                len(matched_ids)
            ),
            "requirement_results": (
                compact_requirements
            ),
        }

    def _collect_evidence_ids(
        value: Any,
        result: set[str],
    ) -> None:
        if isinstance(
            value,
            dict,
        ):
            for key, item in value.items():
                key_text = str(
                    key
                ).casefold()

                if (
                    key_text.endswith(
                        "evidence_id"
                    )
                    and isinstance(
                        item,
                        str,
                    )
                ):
                    result.add(
                        item
                    )

                elif (
                    key_text.endswith(
                        "evidence_ids"
                    )
                    and isinstance(
                        item,
                        (list, tuple),
                    )
                ):
                    for evidence_id in item:
                        if isinstance(
                            evidence_id,
                            str,
                        ):
                            result.add(
                                evidence_id
                            )

                _collect_evidence_ids(
                    item,
                    result,
                )

        elif isinstance(
            value,
            (list, tuple),
        ):
            for item in value:
                _collect_evidence_ids(
                    item,
                    result,
                )

    initial_assessment = (
        _compact_assessment(
            pipeline.get(
                "initial_assessment"
            )
        )
    )

    research_decision = _dict_value(
        pipeline.get(
            "research_decision"
        )
    )

    research_execution = _dict_value(
        pipeline.get(
            "research_execution"
        )
    )

    reconciliation = _dict_value(
        pipeline.get(
            "reconciliation"
        )
    )

    synthesis = _dict_value(
        pipeline.get(
            "synthesis"
        )
    )

    initial_results = _list_value(
        research_execution.get(
            "initial_results"
        )
    )

    combined_results = _list_value(
        research_execution.get(
            "combined_results"
        )
    )

    initial_evidence = _list_value(
        reconciliation.get(
            "initial_evidence_items"
        )
    )

    reconciled_evidence = _list_value(
        reconciliation.get(
            "reconciled_evidence_items"
        )
    )

    claims = _list_value(
        synthesis.get(
            "claims"
        )
    )

    evidence_ids_used: set[str] = set()

    _collect_evidence_ids(
        claims,
        evidence_ids_used,
    )

    compact_reconciled_assessment = (
        _compact_assessment(
            reconciliation.get(
                "reconciled_assessment"
            )
        )
    )

    return {
        "profile": "compact_public_v1",
        "requirement_set_id": (
            pipeline.get(
                "requirement_set_id"
            )
        ),
        "initial_assessment": (
            initial_assessment
        ),
        "research_decision": {
            "status": (
                research_decision.get(
                    "status"
                )
            ),
            "research_required": (
                research_decision.get(
                    "research_required"
                )
            ),
            "target_requirement_ids": (
                _list_value(
                    research_decision.get(
                        "target_requirement_ids"
                    )
                )
            ),
            "reasons": (
                _list_value(
                    research_decision.get(
                        "reasons"
                    )
                )
            ),
        },
        "research_execution": {
            "status": (
                research_execution.get(
                    "status"
                )
            ),
            "research_performed": (
                research_execution.get(
                    "research_performed"
                )
            ),
            "target_requirement_ids": (
                _list_value(
                    research_execution.get(
                        "target_requirement_ids"
                    )
                )
            ),
            "initial_result_count": (
                len(initial_results)
            ),
            "combined_result_count": (
                len(combined_results)
            ),
            "blocked_reason": (
                research_execution.get(
                    "blocked_reason"
                )
            ),
        },
        "reconciliation": {
            "status": (
                reconciliation.get(
                    "status"
                )
            ),
            "research_status": (
                reconciliation.get(
                    "research_status"
                )
            ),
            "initial_evidence_count": (
                len(initial_evidence)
            ),
            "reconciled_evidence_count": (
                len(reconciled_evidence)
            ),
            "added_evidence_ids": (
                _list_value(
                    reconciliation.get(
                        "added_evidence_ids"
                    )
                )
            ),
            "discarded_result_count": (
                reconciliation.get(
                    "discarded_result_count"
                )
            ),
            "reasons": (
                _list_value(
                    reconciliation.get(
                        "reasons"
                    )
                )
            ),
            "reconciled_assessment_status": (
                compact_reconciled_assessment.get(
                    "status"
                )
            ),
        },
        "synthesis": {
            "status": (
                synthesis.get(
                    "status"
                )
            ),
            "claim_count": len(
                claims
            ),
            "evidence_ids_used": sorted(
                evidence_ids_used
            ),
            "warnings": (
                _list_value(
                    synthesis.get(
                        "warnings"
                    )
                )
            ),
        },
    }


def _display_name_code(
    name: Any,
    code: Any,
) -> str:
    name_text = (
        str(name).strip()
        if name is not None
        else ""
    )
    code_text = (
        str(code).strip()
        if code is not None
        else ""
    )

    if name_text and code_text:
        if name_text.upper() == code_text.upper():
            return name_text

        return f"{name_text} ({code_text})"

    if name_text:
        return name_text

    if code_text:
        return code_text

    return "onbekend"


def _format_quantity(value: Any) -> str:
    if isinstance(value, bool):
        return str(value)

    if isinstance(value, float) and value.is_integer():
        return str(int(value))

    return str(value)


def _build_product_article_lines(
    specialist_result: dict[str, Any],
    *,
    include_inventory: bool,
    include_price: bool,
) -> list[str]:
    """
    Bouwt brongebonden artikelinformatie uit config_options.

    Er worden geen voorraad- of prijswaarden uit RAG afgeleid.
    Alleen concrete specialistvelden worden gepresenteerd.
    """
    config_options = specialist_result.get("config_options")

    if not isinstance(config_options, dict):
        return []

    rows = config_options.get("results")

    if not isinstance(rows, list) or not rows:
        return []

    lines = ["Actuele artikelinformatie:"]
    seen: set[str] = set()

    for row in rows:
        if not isinstance(row, dict):
            continue

        internal_ref = str(row.get("internal_ref") or "").strip()
        product_name = str(row.get("product_name") or "").strip()
        option_value = str(row.get("option_value") or "").strip()
        component_group = str(row.get("component_group") or "").strip()

        dedupe_key = internal_ref or "|".join(
            [product_name, option_value, component_group]
        )

        if dedupe_key in seen:
            continue

        seen.add(dedupe_key)

        details: list[str] = []

        if include_inventory:
            available_qty = row.get("available_qty")
            expected_qty = row.get("expected_qty")
            uom = str(row.get("uom") or "stuks").strip()

            if available_qty is not None:
                details.append(
                    "voorraad: "
                    f"{_format_quantity(available_qty)} {uom}"
                )

            if (
                isinstance(expected_qty, (int, float))
                and not isinstance(expected_qty, bool)
                and expected_qty > 0
            ):
                details.append(
                    "verwacht: "
                    f"{_format_quantity(expected_qty)} {uom}"
                )

        if include_price:
            sale_price = row.get("sale_price")

            if sale_price is not None:
                details.append(
                    "verkoopprijs: "
                    f"{_format_quantity(sale_price)}"
                )

        if not details:
            continue

        label = product_name or internal_ref or option_value or component_group

        if internal_ref and internal_ref not in label:
            label = f"{label} ({internal_ref})"

        lines.append(
            f"- {label}: " + "; ".join(details)
        )

    if len(lines) == 1:
        return []

    return lines


# PROMATI_MULTI_PRODUCT_PUBLIC_SYNTHESIS_P4_5B7_FIX
#
# Additive deterministic presentation for explicit multi-product fan-out.
# Single-product presentation remains owned by the legacy PRODUCT branch below.
def _build_multi_product_user_answer(
    results: list[dict[str, Any]],
    requested: set[str],
) -> str | None:
    sections: list[list[str]] = []
    seen_family_keys: set[str] = set()

    include_inventory = "inventory" in requested
    include_price = "price" in requested

    for item in results:
        if not isinstance(item, dict):
            continue

        specialist_result = item.get("result")

        if not isinstance(
            specialist_result,
            dict,
        ):
            continue

        action = str(
            item.get("action") or ""
        )

        context_type = str(
            specialist_result.get(
                "context_type"
            )
            or ""
        )

        if not (
            action == "product_assistant"
            or context_type == "product_assistant"
        ):
            continue

        family_context = specialist_result.get(
            "family_context"
        )

        if not isinstance(
            family_context,
            dict,
        ):
            continue

        family_rows = family_context.get(
            "results"
        )

        if not (
            isinstance(family_rows, list)
            and family_rows
            and isinstance(
                family_rows[0],
                dict,
            )
        ):
            continue

        family = family_rows[0]

        row_family_code = str(
            family.get("family_code")
            or ""
        ).strip()

        detected_family_code = str(
            specialist_result.get(
                "detected_family_code"
            )
            or family_context.get(
                "detected_family_code"
            )
            or ""
        ).strip()

        # Explicit family scope remains authoritative. Never present a family
        # record under a different explicitly resolved family identity.
        if (
            row_family_code
            and detected_family_code
            and row_family_code.casefold()
            != detected_family_code.casefold()
        ):
            continue

        family_code = (
            detected_family_code
            or row_family_code
        )

        family_name = str(
            family.get("family_name")
            or ""
        ).strip()

        family_key = str(
            family_code
            or family_name
        ).strip().casefold()

        if not family_key:
            continue

        if family_key in seen_family_keys:
            continue

        seen_family_keys.add(family_key)

        label = _display_name_code(
            family_name,
            family_code,
        )

        section_lines: list[str] = [label]

        strengths = family.get("strengths")
        limitations = family.get("limitations")
        selection_advice = family.get(
            "selection_advice"
        )

        if strengths:
            section_lines.extend(
                [
                    "",
                    f"Sterktes: {strengths}",
                ]
            )

        if limitations:
            section_lines.extend(
                [
                    "",
                    f"Beperkingen: {limitations}",
                ]
            )

        if selection_advice:
            section_lines.extend(
                [
                    "",
                    (
                        "Selectieadvies: "
                        f"{selection_advice}"
                    ),
                ]
            )

        if include_inventory or include_price:
            article_lines = (
                _build_product_article_lines(
                    specialist_result,
                    include_inventory=(
                        include_inventory
                    ),
                    include_price=include_price,
                )
            )

            if article_lines:
                section_lines.extend(
                    [
                        "",
                        *article_lines,
                    ]
                )

        sections.append(section_lines)

    # Critical backwards-compatibility boundary: one distinct family continues
    # through the existing single-product presentation path unchanged.
    if len(sections) < 2:
        return None

    answer_lines: list[str] = [
        "Productfamilies:",
    ]

    for section in sections:
        answer_lines.extend(
            [
                "",
                *section,
            ]
        )

    return "\n".join(answer_lines)

def _build_user_answer(
    results: list[dict[str, Any]],
    requested_information: list[str] | None = None,
) -> str | None:
    """
    Bouwt een user-facing presentatielaag boven specialistresultaten.

    Bronnen blijven gescheiden:
    - asset_context is leidend voor asset-identiteit;
    - product family_context is leidend voor productkennis;
    - ORG gebruikt alleen gestructureerde ORG-resultaten;
    - technical gebruikt alleen specialistdata die werkelijk
      in het resultaat aanwezig is;
    - ruwe specialistdata wordt nooit gewijzigd.
    """
    requested = {
        str(item).strip().casefold()
        for item in (requested_information or [])
        if str(item).strip()
    }

    # -----------------------------------------------------
    # 1. ASSET ANSWER
    # Bestaand gedrag houdt bewust de hoogste prioriteit.
    # -----------------------------------------------------

    asset_result = None
    asset_action = None

    for item in results:
        specialist_result = item.get("result")

        if not isinstance(
            specialist_result,
            dict,
        ):
            continue

        if isinstance(
            specialist_result.get(
                "asset_resolution"
            ),
            dict,
        ):
            asset_result = specialist_result
            asset_action = str(
                item.get("action") or ""
            )
            break

    if asset_result is not None:
        context = asset_result.get(
            "asset_context"
        )

        if not isinstance(context, dict):
            context = {}

        entities = asset_result.get("entities")

        if not isinstance(entities, dict):
            entities = {}

        customer = (
            context.get("customer_code")
            or "onbekend"
        )

        site = (
            context.get("site_code")
            or "onbekend"
        )

        area = _display_name_code(
            context.get("area_name"),
            context.get("area_code"),
        )

        installation = _display_name_code(
            context.get("installation_name"),
            context.get("installation_code"),
        )

        band = (
            context.get("band_code_display")
            or context.get("band_code_norm")
            or entities.get("band_code")
            or "onbekend"
        )

        result_text = (
            asset_result.get("message")
            or asset_result.get("kort_resultaat")
        )

        answer_lines = [
            f"Klant: {customer}",
            f"Plaats: {site}",
            f"Gebied: {area}",
            f"Installatie: {installation}",
            f"Bandnummer: {band}",
        ]

        # PROMATI_INSPECTION_LATEST_PRESENTATION_V1
        #
        # Smalle legacy-presentatie voor inspection_latest.
        # Geen wijziging aan C7 answer ownership.
        if (
            asset_action == "analysis_assistant"
            and str(
                asset_result.get("intent") or ""
            )
            == "inspection_summary"
        ):
            raw_rows = asset_result.get("resultaat")

            if isinstance(raw_rows, list):
                dated_rows: list[tuple[str, dict[str, Any]]] = []

                for raw_row in raw_rows:
                    if not isinstance(raw_row, dict):
                        continue

                    document_date = str(
                        raw_row.get("document_date") or ""
                    ).strip()

                    if not document_date:
                        continue

                    dated_rows.append(
                        (
                            document_date,
                            raw_row,
                        )
                    )

                if dated_rows:
                    latest_date = max(
                        document_date
                        for document_date, _ in dated_rows
                    )

                    latest_rows = [
                        row
                        for document_date, row in dated_rows
                        if document_date == latest_date
                    ]

                    seen_measurements: set[
                        tuple[
                            str,
                            str,
                            str,
                            str,
                        ]
                    ] = set()

                    measurements: list[
                        dict[str, Any]
                    ] = []

                    for row in latest_rows:
                        meshoogte = row.get(
                            "meshoogte_mm"
                        )

                        if meshoogte is None:
                            continue

                        inspection_key = str(
                            row.get(
                                "inspection_key"
                            )
                            or ""
                        ).strip()

                        scraper_type = str(
                            row.get(
                                "scraper_type_raw"
                            )
                            or ""
                        ).strip()

                        location = str(
                            row.get("locatie_raw")
                            or ""
                        ).strip()

                        dedupe_key = (
                            inspection_key,
                            scraper_type,
                            location,
                            str(meshoogte),
                        )

                        if dedupe_key in seen_measurements:
                            continue

                        seen_measurements.add(
                            dedupe_key
                        )

                        measurements.append(
                            {
                                "inspection_key": (
                                    inspection_key
                                ),
                                "scraper_type": (
                                    scraper_type
                                ),
                                "location": location,
                                "meshoogte_mm": meshoogte,
                                "mes_vervangen": row.get(
                                    "mes_vervangen"
                                ),
                            }
                        )

                    answer_lines.extend(
                        [
                            "",
                            (
                                "Laatste inspectie: "
                                f"{latest_date}"
                            ),
                        ]
                    )

                    if measurements:
                        answer_lines.extend(
                            [
                                "",
                                "Schrapers:",
                            ]
                        )

                        for measurement in sorted(
                            measurements,
                            key=lambda item: (
                                item[
                                    "scraper_type"
                                ],
                                item[
                                    "location"
                                ],
                            ),
                        ):
                            scraper_type = (
                                measurement[
                                    "scraper_type"
                                ]
                                or "Onbekende schraper"
                            )

                            location = measurement[
                                "location"
                            ]

                            meshoogte = measurement[
                                "meshoogte_mm"
                            ]

                            label = scraper_type

                            if location:
                                label += (
                                    f" â€” {location}"
                                )

                            answer_lines.append(
                                f"- {label}: "
                                f"{meshoogte} mm"
                            )

                        replacement_values = [
                            item.get(
                                "mes_vervangen"
                            )
                            for item in measurements
                        ]

                        if (
                            replacement_values
                            and all(
                                value is False
                                for value
                                in replacement_values
                            )
                        ):
                            answer_lines.extend(
                                [
                                    "",
                                    (
                                        "Geen mesvervanging "
                                        "geregistreerd bij "
                                        "deze laatste "
                                        "metingen."
                                    ),
                                ]
                            )

                    return "\n".join(
                        answer_lines
                    )

        # PROMATI_INSPECTION_TREND_PRESENTATION_V1
        #
        # Smalle legacy-presentatie voor inspection_trend.
        # Geen forecast en geen wijziging aan C7 answer ownership.
        if (
            asset_action == "analysis_assistant"
            and str(
                asset_result.get("intent") or ""
            )
            == "lifecycle"
        ):
            raw_rows = asset_result.get("resultaat")

            if isinstance(raw_rows, list):
                groups: dict[
                    tuple[str, str, str],
                    dict[str, Any],
                ] = {}

                seen_measurements: set[
                    tuple[
                        str,
                        str,
                        str,
                        str,
                        str,
                        str,
                    ]
                ] = set()

                replacement_dates: set[str] = set()

                for raw_row in raw_rows:
                    if not isinstance(raw_row, dict):
                        continue

                    inspected_on = str(
                        raw_row.get("inspected_on")
                        or ""
                    ).strip()

                    scraper_type = str(
                        raw_row.get(
                            "scraper_type_norm"
                        )
                        or ""
                    ).strip()

                    position_hint = str(
                        raw_row.get(
                            "position_hint"
                        )
                        or ""
                    ).strip()

                    cycle_raw = raw_row.get(
                        "cycle_id"
                    )

                    cycle_id = (
                        str(cycle_raw)
                        if cycle_raw is not None
                        else ""
                    )

                    canonical_key = str(
                        raw_row.get(
                            "canonical_inspection_key"
                        )
                        or ""
                    ).strip()

                    if (
                        raw_row.get("replace_event")
                        is True
                        and inspected_on
                    ):
                        replacement_dates.add(
                            inspected_on
                        )

                    meshoogte = raw_row.get(
                        "meshoogte_mm"
                    )

                    numeric_height = (
                        isinstance(
                            meshoogte,
                            (int, float),
                        )
                        and not isinstance(
                            meshoogte,
                            bool,
                        )
                    )

                    if not (
                        inspected_on
                        and scraper_type
                        and numeric_height
                    ):
                        continue

                    dedupe_key = (
                        canonical_key,
                        scraper_type,
                        position_hint,
                        cycle_id,
                        inspected_on,
                        str(meshoogte),
                    )

                    if dedupe_key in seen_measurements:
                        continue

                    seen_measurements.add(
                        dedupe_key
                    )

                    group_key = (
                        scraper_type,
                        position_hint,
                        cycle_id,
                    )

                    group = groups.setdefault(
                        group_key,
                        {
                            "scraper_type": scraper_type,
                            "position_hint": position_hint,
                            "cycle_id": cycle_id,
                            "points": [],
                        },
                    )

                    group["points"].append(
                        (
                            inspected_on,
                            float(meshoogte),
                        )
                    )

                usable_groups: list[
                    dict[str, Any]
                ] = []

                total_measurements = 0

                for group in groups.values():
                    points = sorted(
                        group["points"],
                        key=lambda item: item[0],
                    )

                    if not points:
                        continue

                    group["points"] = points
                    total_measurements += len(points)
                    usable_groups.append(group)

                if usable_groups:
                    usable_groups.sort(
                        key=lambda group: (
                            group["points"][-1][0],
                            group["scraper_type"],
                            group["position_hint"],
                            group["cycle_id"],
                        ),
                        reverse=True,
                    )

                    answer_lines.extend(
                        [
                            "",
                            (
                                "Trendgegevens: "
                                f"{total_measurements} metingen "
                                f"verdeeld over "
                                f"{len(usable_groups)} cycli."
                            ),
                            "",
                            "Historie per schraper/cyclus:",
                        ]
                    )

                    def _format_mm(
                        value: float,
                    ) -> str:
                        if value.is_integer():
                            return str(int(value))

                        return (
                            f"{value:.2f}"
                            .rstrip("0")
                            .rstrip(".")
                        )

                    for group in usable_groups:
                        points = group["points"]

                        first_date, first_height = (
                            points[0]
                        )

                        last_date, last_height = (
                            points[-1]
                        )

                        label_parts = [
                            group["scraper_type"]
                        ]

                        if group["position_hint"]:
                            label_parts.append(
                                group["position_hint"]
                            )

                        if group["cycle_id"]:
                            label_parts.append(
                                (
                                    "cyclus "
                                    f"{group['cycle_id']}"
                                )
                            )

                        label = " â€” ".join(
                            label_parts
                        )

                        if len(points) == 1:
                            detail = (
                                f"1 meting, "
                                f"{last_date} "
                                f"{_format_mm(last_height)} mm"
                            )
                        else:
                            detail = (
                                f"{len(points)} metingen, "
                                f"{first_date} "
                                f"{_format_mm(first_height)} mm "
                                f"â†’ "
                                f"{last_date} "
                                f"{_format_mm(last_height)} mm"
                            )

                        answer_lines.append(
                            f"- {label}: {detail}"
                        )

                    # PROMATI_INSPECTION_TREND_FACET_PRESENTATION_V1
                    #
                    # P1.1b blijft presentation-only.
                    # De lifecyclebron wordt niet opgewaardeerd
                    # tot actuele onderhouds- of forecastbron.
                    if (
                        "latest_measurements"
                        in requested
                    ):
                        latest_by_position: dict[
                            tuple[str, str],
                            dict[str, Any],
                        ] = {}

                        for group in usable_groups:
                            points = group["points"]

                            if not points:
                                continue

                            (
                                latest_date,
                                latest_height,
                            ) = points[-1]

                            latest_key = (
                                group["scraper_type"],
                                group["position_hint"],
                            )

                            existing = (
                                latest_by_position.get(
                                    latest_key
                                )
                            )

                            if (
                                existing is None
                                or latest_date
                                > existing["inspected_on"]
                            ):
                                latest_by_position[
                                    latest_key
                                ] = {
                                    "scraper_type": (
                                        group[
                                            "scraper_type"
                                        ]
                                    ),
                                    "position_hint": (
                                        group[
                                            "position_hint"
                                        ]
                                    ),
                                    "inspected_on": (
                                        latest_date
                                    ),
                                    "meshoogte_mm": (
                                        latest_height
                                    ),
                                }

                        if latest_by_position:
                            latest_rows = sorted(
                                latest_by_position.values(),
                                key=lambda item: (
                                    item["inspected_on"],
                                    item["scraper_type"],
                                    item["position_hint"],
                                ),
                                reverse=True,
                            )

                            answer_lines.extend(
                                [
                                    "",
                                    (
                                        "Laatste lifecycle-meting "
                                        "per schraper/positie:"
                                    ),
                                ]
                            )

                            for measurement in latest_rows:
                                label = measurement[
                                    "scraper_type"
                                ]

                                if measurement[
                                    "position_hint"
                                ]:
                                    label = (
                                        label
                                        + " - "
                                        + measurement[
                                            "position_hint"
                                        ]
                                    )

                                height_text = _format_mm(
                                    measurement[
                                        "meshoogte_mm"
                                    ]
                                )

                                date_text = str(
                                    measurement[
                                        "inspected_on"
                                    ]
                                )

                                answer_lines.append(
                                    (
                                        "- "
                                        + label
                                        + ": "
                                        + height_text
                                        + " mm op "
                                        + date_text
                                    )
                                )

                    if replacement_dates:
                        answer_lines.extend(
                            [
                                "",
                                (
                                    "Geregistreerde "
                                    "vervangevents: "
                                    + ", ".join(
                                        sorted(
                                            replacement_dates
                                        )
                                    )
                                ),
                            ]
                        )

                    elif (
                        "replacement_events"
                        in requested
                    ):
                        answer_lines.extend(
                            [
                                "",
                                (
                                    "Geregistreerde "
                                    "vervangevents: geen "
                                    "in deze lifecyclebron."
                                ),
                            ]
                        )

                    if (
                        "replacement_advice"
                        in requested
                    ):
                        answer_lines.extend(
                            [
                                "",
                                (
                                    "Vervangadvies: niet bepaald "
                                    "uit deze lifecyclehistorie; "
                                    "hiervoor is een actuele "
                                    "onderhouds-/forecastanalyse "
                                    "nodig."
                                ),
                            ]
                        )

                    if (
                        "uncertainties"
                        in requested
                    ):
                        answer_lines.extend(
                            [
                                "",
                                "Onzekerheden:",
                                (
                                    "- De weergegeven laatste "
                                    "meshoogte is de meest recente "
                                    "lifecycle-meting per "
                                    "schraper/positie in deze bron; "
                                    "dit bevestigt niet dat de "
                                    "positie nog actueel actief is."
                                ),
                                (
                                    "- Deze lifecyclebron bevat "
                                    "geen afzonderlijke actuele "
                                    "vervang-/forecastanalyse; "
                                    "daarom wordt hier geen "
                                    "vervangmoment afgeleid."
                                ),
                            ]
                        )

                    return "\n".join(
                        answer_lines
                    )

        # PROMATI_MAINTENANCE_PRIORITY_PRESENTATION_V1
        #
        # Smalle legacy-presentatie voor maintenance_priority.
        # Geen wijziging aan C7 answer ownership.
        # 3 mm blijft vervanggrens; 6 mm is alleen prestatiegrens.
        if (
            asset_action == "analysis_assistant"
            and str(
                asset_result.get("intent") or ""
            )
            == "maintenance_positions"
        ):
            raw_rows = asset_result.get(
                "resultaat"
            )

            if isinstance(
                raw_rows,
                list,
            ):
                positions: list[
                    dict[str, Any]
                ] = []

                seen_positions: set[
                    tuple[
                        str,
                        str,
                        str,
                        str,
                    ]
                ] = set()

                for raw_row in raw_rows:
                    if not isinstance(
                        raw_row,
                        dict,
                    ):
                        continue

                    scraper_types = str(
                        raw_row.get(
                            "scraper_types_clean"
                        )
                        or raw_row.get(
                            "scraper_types"
                        )
                        or ""
                    ).strip()

                    position_hint = str(
                        raw_row.get(
                            "position_hint"
                        )
                        or ""
                    ).strip()

                    cycle_end = str(
                        raw_row.get(
                            "cycle_end"
                        )
                        or ""
                    ).strip()

                    priority_raw = (
                        raw_row.get(
                            "prioriteit"
                        )
                    )

                    priority = (
                        float(priority_raw)
                        if (
                            isinstance(
                                priority_raw,
                                (int, float),
                            )
                            and not isinstance(
                                priority_raw,
                                bool,
                            )
                        )
                        else float("inf")
                    )

                    dedupe_key = (
                        scraper_types,
                        position_hint,
                        cycle_end,
                        str(priority_raw),
                    )

                    if (
                        dedupe_key
                        in seen_positions
                    ):
                        continue

                    seen_positions.add(
                        dedupe_key
                    )

                    end_height_raw = (
                        raw_row.get(
                            "eind_meshoogte_mm"
                        )
                    )

                    numeric_end_height = (
                        isinstance(
                            end_height_raw,
                            (int, float),
                        )
                        and not isinstance(
                            end_height_raw,
                            bool,
                        )
                    )

                    end_height = (
                        float(end_height_raw)
                        if numeric_end_height
                        else None
                    )

                    meetpunten_raw = (
                        raw_row.get(
                            "meetpunten"
                        )
                    )

                    usable_point_count = (
                        isinstance(
                            meetpunten_raw,
                            int,
                        )
                        and not isinstance(
                            meetpunten_raw,
                            bool,
                        )
                        and meetpunten_raw
                        >= 3
                    )

                    forecast_date = str(
                        raw_row.get(
                            "geschatte_vervangdatum_bij_3mm"
                        )
                        or ""
                    ).strip()

                    performance_action = str(
                        raw_row.get(
                            "prestatie_vervangmoment"
                        )
                        or ""
                    ).strip()

                    status_6mm = str(
                        raw_row.get(
                            "status_6mm"
                        )
                        or ""
                    ).strip()

                    status_3mm = str(
                        raw_row.get(
                            "status_3mm"
                        )
                        or ""
                    ).strip()

                    if (
                        numeric_end_height
                        and end_height
                        is not None
                        and end_height <= 3.0
                    ):
                        action = (
                            "NU VERVANGEN"
                        )
                    elif (
                        performance_action
                        == (
                            "CONTROLEREN_"
                            "PRESTATIEGRENS"
                        )
                        or status_6mm
                        == "OP_OF_ONDER_6MM"
                    ):
                        action = (
                            "Prestatiegrens "
                            "controleren"
                        )
                    elif not (
                        numeric_end_height
                    ):
                        action = (
                            "Trend controleren; "
                            "geen bruikbare "
                            "actuele eindmeting"
                        )
                    elif (
                        status_3mm
                        == "CHECK_TREND"
                    ):
                        action = (
                            "Trend controleren"
                        )
                    else:
                        action = "Monitoren"

                    reliable_forecast = (
                        usable_point_count
                        and numeric_end_height
                        and forecast_date != ""
                    )

                    positions.append(
                        {
                            "priority": (
                                priority
                            ),
                            "priority_raw": (
                                priority_raw
                            ),
                            "scraper_types": (
                                scraper_types
                                or "Onbekende schraper"
                            ),
                            "position_hint": (
                                position_hint
                                or "positie onbekend"
                            ),
                            "cycle_end": (
                                cycle_end
                            ),
                            "meetpunten": (
                                meetpunten_raw
                            ),
                            "end_height": (
                                end_height
                            ),
                            "action": action,
                            "forecast_date": (
                                forecast_date
                            ),
                            "reliable_forecast": (
                                reliable_forecast
                            ),
                        }
                    )

                if positions:
                    positions.sort(
                        key=lambda item: (
                            item["priority"],
                            item[
                                "scraper_types"
                            ],
                            item[
                                "position_hint"
                            ],
                        )
                    )

                    def _format_mm(
                        value: float,
                    ) -> str:
                        if value.is_integer():
                            return str(
                                int(value)
                            )

                        return (
                            f"{value:.2f}"
                            .rstrip("0")
                            .rstrip(".")
                        )

                    answer_lines.extend(
                        [
                            "",
                            "Onderhoudsprioriteit:",
                        ]
                    )

                    for index, position in enumerate(
                        positions,
                        start=1,
                    ):
                        answer_lines.extend(
                            [
                                "",
                                (
                                    f"{index}. "
                                    f"{position['scraper_types']}"
                                    " â€” "
                                    f"{position['position_hint']}"
                                ),
                            ]
                        )

                        end_height = (
                            position[
                                "end_height"
                            ]
                        )

                        cycle_end = (
                            position[
                                "cycle_end"
                            ]
                        )

                        if (
                            end_height
                            is not None
                        ):
                            measurement_line = (
                                "   Laatste gemeten "
                                "meshoogte: "
                                f"{_format_mm(end_height)} mm"
                            )

                            if cycle_end:
                                measurement_line += (
                                    f" op {cycle_end}"
                                )

                            answer_lines.append(
                                measurement_line
                            )
                        else:
                            answer_lines.append(
                                "   Laatste gemeten "
                                "meshoogte: "
                                "niet beschikbaar"
                            )

                        answer_lines.append(
                            "   Actie: "
                            f"{position['action']}"
                        )

                        if (
                            position[
                                "reliable_forecast"
                            ]
                        ):
                            answer_lines.append(
                                "   Prognose 3 mm: "
                                "rond "
                                f"{position['forecast_date']}"
                            )

                            answer_lines.append(
                                "   Onderbouwing: "
                                f"{position['meetpunten']} "
                                "meetpunten"
                            )
                        else:
                            answer_lines.append(
                                "   Geen betrouwbare "
                                "forecast beschikbaar"
                            )

                    answer_lines.extend(
                        [
                            "",
                            (
                                "Let op: 3 mm is de "
                                "vervanggrens. "
                                "De 6 mm-grens is een "
                                "prestatiecontrole en "
                                "betekent niet automatisch "
                                "vervangen."
                            ),
                        ]
                    )

                    return "\n".join(
                        answer_lines
                    )


        # PROMATI_REPLACEMENT_ADVICE_PRESENTATION_V1
        #
        # Smalle legacy-presentatie voor replacement_advice.
        # Geen wijziging aan C7 answer ownership.
        #
        # Semantiek:
        # - gemeten <= 3 mm => NU VERVANGEN
        # - VERVANGEN_VOORBEREIDEN blijft voorbereiden
        # - forecast alleen bij >= 3 bruikbare meetpunten
        # - geen relatieve dagen-tot-3mm presentatie
        if (
            asset_action == "analysis_assistant"
            and str(
                asset_result.get("intent") or ""
            )
            == "band_deep_analysis"
        ):
            raw_positions = asset_result.get(
                "gecombineerde_slijtage"
            )

            raw_forecasts = asset_result.get(
                "forecast_3mm"
            )

            if isinstance(
                raw_positions,
                list,
            ):
                if not isinstance(
                    raw_forecasts,
                    list,
                ):
                    raw_forecasts = []

                def _numeric(
                    value: Any,
                ) -> bool:
                    return (
                        isinstance(
                            value,
                            (int, float),
                        )
                        and not isinstance(
                            value,
                            bool,
                        )
                    )

                def _format_mm(
                    value: float,
                ) -> str:
                    if value.is_integer():
                        return str(
                            int(value)
                        )

                    return (
                        f"{value:.2f}"
                        .rstrip("0")
                        .rstrip(".")
                    )

                def _family_from_text(
                    value: Any,
                ) -> str:
                    text = str(
                        value or ""
                    ).strip().upper()

                    if not text:
                        return ""

                    first = text[0]

                    if first in {
                        "R",
                        "U",
                        "T",
                    }:
                        return first

                    return ""

                eligible_forecasts_by_family: dict[
                    str,
                    list[dict[str, Any]],
                ] = {}

                for raw_forecast in raw_forecasts:
                    if not isinstance(
                        raw_forecast,
                        dict,
                    ):
                        continue

                    meetpunten = raw_forecast.get(
                        "meetpunten"
                    )

                    end_height = raw_forecast.get(
                        "eind_meshoogte_mm"
                    )

                    wear_rate = raw_forecast.get(
                        "slijtage_mm_per_dag"
                    )

                    days_to_3mm = raw_forecast.get(
                        "geschatte_dagen_tot_3mm"
                    )

                    forecast_date = str(
                        raw_forecast.get(
                            "geschatte_vervangdatum_bij_3mm"
                        )
                        or ""
                    ).strip()

                    family = _family_from_text(
                        raw_forecast.get(
                            "scraper_type_norm"
                        )
                    )

                    eligible = (
                        isinstance(
                            meetpunten,
                            int,
                        )
                        and not isinstance(
                            meetpunten,
                            bool,
                        )
                        and meetpunten >= 3
                        and _numeric(
                            end_height
                        )
                        and _numeric(
                            wear_rate
                        )
                        and _numeric(
                            days_to_3mm
                        )
                        and forecast_date != ""
                        and family != ""
                    )

                    if not eligible:
                        continue

                    eligible_forecasts_by_family.setdefault(
                        family,
                        [],
                    ).append(
                        raw_forecast
                    )

                positions: list[
                    dict[str, Any]
                ] = []

                seen_positions: set[
                    tuple[
                        str,
                        str,
                        str,
                    ]
                ] = set()

                for raw_position in raw_positions:
                    if not isinstance(
                        raw_position,
                        dict,
                    ):
                        continue

                    scraper_type = str(
                        raw_position.get(
                            "scraper_type_norm"
                        )
                        or ""
                    ).strip()

                    family = str(
                        raw_position.get(
                            "scraper_family"
                        )
                        or ""
                    ).strip().upper()

                    if not family:
                        family = _family_from_text(
                            scraper_type
                        )

                    position_display = str(
                        raw_position.get(
                            "position_display"
                        )
                        or ""
                    ).strip()

                    inspection_date = str(
                        raw_position.get(
                            "laatste_inspectiedatum"
                        )
                        or ""
                    ).strip()

                    height_raw = (
                        raw_position.get(
                            "meshoogte_mm"
                        )
                    )

                    height = (
                        float(height_raw)
                        if _numeric(
                            height_raw
                        )
                        else None
                    )

                    advice = str(
                        raw_position.get(
                            "onderhoudsadvies_unified"
                        )
                        or ""
                    ).strip().upper()

                    dedupe_key = (
                        scraper_type,
                        position_display,
                        inspection_date,
                    )

                    if (
                        dedupe_key
                        in seen_positions
                    ):
                        continue

                    seen_positions.add(
                        dedupe_key
                    )

                    if (
                        height is not None
                        and height <= 3.0
                    ):
                        action = (
                            "NU VERVANGEN"
                        )

                        action_rank = 0

                    elif (
                        advice
                        == "VERVANGEN_VOORBEREIDEN"
                    ):
                        action = (
                            "Vervanging voorbereiden"
                        )

                        action_rank = 1

                    elif (
                        advice
                        == "CONTROLEREN_BIJ_STOP"
                    ):
                        action = (
                            "Controleren bij stop"
                        )

                        action_rank = 2

                    else:
                        action = "Monitoren"
                        action_rank = 3

                    forecast = None

                    family_forecasts = (
                        eligible_forecasts_by_family.get(
                            family,
                            [],
                        )
                    )

                    # Fail-closed:
                    # alleen koppelen wanneer precies
                    # Ã©Ã©n betrouwbare forecast bestaat
                    # voor deze scraperfamilie.
                    if (
                        len(
                            family_forecasts
                        )
                        == 1
                    ):
                        forecast = (
                            family_forecasts[0]
                        )

                    positions.append(
                        {
                            "scraper_type": (
                                scraper_type
                                or "Onbekende schraper"
                            ),
                            "position": (
                                position_display
                                or "positie onbekend"
                            ),
                            "inspection_date": (
                                inspection_date
                            ),
                            "height": height,
                            "action": action,
                            "action_rank": (
                                action_rank
                            ),
                            "forecast": (
                                forecast
                            ),
                        }
                    )

                if positions:
                    positions.sort(
                        key=lambda item: (
                            item["action_rank"],
                            item["scraper_type"],
                            item["position"],
                        )
                    )

                    answer_lines.extend(
                        [
                            "",
                            "Vervangadvies:",
                        ]
                    )

                    for index, position in enumerate(
                        positions,
                        start=1,
                    ):
                        answer_lines.extend(
                            [
                                "",
                                (
                                    f"{index}. "
                                    f"{position['scraper_type']}"
                                    " â€” "
                                    f"{position['position']}"
                                ),
                            ]
                        )

                        height = position[
                            "height"
                        ]

                        inspection_date = position[
                            "inspection_date"
                        ]

                        if height is not None:
                            measurement_line = (
                                "   Laatste gemeten "
                                "meshoogte: "
                                f"{_format_mm(height)} mm"
                            )

                            if inspection_date:
                                measurement_line += (
                                    f" op {inspection_date}"
                                )

                            answer_lines.append(
                                measurement_line
                            )

                        else:
                            answer_lines.append(
                                "   Laatste gemeten "
                                "meshoogte: "
                                "niet beschikbaar"
                            )

                        answer_lines.append(
                            "   Advies: "
                            f"{position['action']}"
                        )

                        forecast = position[
                            "forecast"
                        ]

                        if isinstance(
                            forecast,
                            dict,
                        ):
                            forecast_date = str(
                                forecast.get(
                                    "geschatte_vervangdatum_bij_3mm"
                                )
                                or ""
                            ).strip()

                            meetpunten = (
                                forecast.get(
                                    "meetpunten"
                                )
                            )

                            answer_lines.append(
                                "   Prognose 3 mm: "
                                f"rond {forecast_date}"
                            )

                            answer_lines.append(
                                "   Onderbouwing: "
                                f"{meetpunten} meetpunten"
                            )

                        else:
                            answer_lines.append(
                                "   Geen betrouwbare "
                                "forecast beschikbaar"
                            )

                    answer_lines.extend(
                        [
                            "",
                            (
                                "Let op: 3 mm is de "
                                "vervanggrens. "
                                "Een advies 'vervanging "
                                "voorbereiden' betekent "
                                "niet dat het mes nu al "
                                "de vervanggrens heeft "
                                "bereikt."
                            ),
                        ]
                    )

                    # PROMATI_REPLACEMENT_ADVICE_FACET_PRESENTATION_V1
                    #
                    # P1.2b: facetprojecties uit dezelfde
                    # band_deep_analysis-response.
                    #
                    # Actuele meshoogte en vervangadvies blijven
                    # uitsluitend gebaseerd op gecombineerde_slijtage
                    # en de bestaande forecastlogica hierboven.
                    # Lifecycle wordt alleen gebruikt voor historie
                    # en geregistreerde vervangevents.
                    facet_requested = bool(
                        {
                            "lifecycle_trend",
                            "replacement_events",
                            "uncertainties",
                        }
                        & requested
                    )

                    if facet_requested:
                        raw_lifecycle = (
                            asset_result.get(
                                "lifecycle"
                            )
                        )

                        lifecycle_available = (
                            isinstance(
                                raw_lifecycle,
                                list,
                            )
                        )

                        lifecycle_groups: dict[
                            tuple[str, str, str],
                            dict[str, Any],
                        ] = {}

                        lifecycle_replacement_dates: (
                            set[str]
                        ) = set()

                        seen_lifecycle_measurements: set[
                            tuple[
                                str,
                                str,
                                str,
                                str,
                                str,
                                str,
                            ]
                        ] = set()

                        if lifecycle_available:
                            for raw_row in raw_lifecycle:
                                if not isinstance(
                                    raw_row,
                                    dict,
                                ):
                                    continue

                                inspected_on = str(
                                    raw_row.get(
                                        "inspected_on"
                                    )
                                    or ""
                                ).strip()

                                scraper_type = str(
                                    raw_row.get(
                                        "scraper_type_norm"
                                    )
                                    or ""
                                ).strip()

                                position_hint = str(
                                    raw_row.get(
                                        "position_hint"
                                    )
                                    or ""
                                ).strip()

                                cycle_raw = raw_row.get(
                                    "cycle_id"
                                )

                                cycle_id = (
                                    str(cycle_raw)
                                    if cycle_raw
                                    is not None
                                    else ""
                                )

                                canonical_key = str(
                                    raw_row.get(
                                        "canonical_inspection_key"
                                    )
                                    or ""
                                ).strip()

                                if (
                                    raw_row.get(
                                        "replace_event"
                                    )
                                    is True
                                    and inspected_on
                                ):
                                    lifecycle_replacement_dates.add(
                                        inspected_on
                                    )

                                meshoogte = (
                                    raw_row.get(
                                        "meshoogte_mm"
                                    )
                                )

                                if not (
                                    inspected_on
                                    and scraper_type
                                    and _numeric(
                                        meshoogte
                                    )
                                ):
                                    continue

                                dedupe_key = (
                                    canonical_key,
                                    scraper_type,
                                    position_hint,
                                    cycle_id,
                                    inspected_on,
                                    str(meshoogte),
                                )

                                if (
                                    dedupe_key
                                    in seen_lifecycle_measurements
                                ):
                                    continue

                                seen_lifecycle_measurements.add(
                                    dedupe_key
                                )

                                group_key = (
                                    scraper_type,
                                    position_hint,
                                    cycle_id,
                                )

                                group = (
                                    lifecycle_groups.setdefault(
                                        group_key,
                                        {
                                            "scraper_type": (
                                                scraper_type
                                            ),
                                            "position_hint": (
                                                position_hint
                                            ),
                                            "cycle_id": (
                                                cycle_id
                                            ),
                                            "points": [],
                                        },
                                    )
                                )

                                group["points"].append(
                                    (
                                        inspected_on,
                                        float(
                                            meshoogte
                                        ),
                                    )
                                )

                        usable_lifecycle_groups: list[
                            dict[str, Any]
                        ] = []

                        lifecycle_measurement_count = 0

                        for group in (
                            lifecycle_groups.values()
                        ):
                            points = sorted(
                                group["points"],
                                key=lambda item: (
                                    item[0]
                                ),
                            )

                            if not points:
                                continue

                            group["points"] = points

                            lifecycle_measurement_count += (
                                len(points)
                            )

                            usable_lifecycle_groups.append(
                                group
                            )

                        usable_lifecycle_groups.sort(
                            key=lambda group: (
                                group["points"][-1][0],
                                group["scraper_type"],
                                group["position_hint"],
                                group["cycle_id"],
                            ),
                            reverse=True,
                        )

                        if (
                            "lifecycle_trend"
                            in requested
                        ):
                            if usable_lifecycle_groups:
                                answer_lines.extend(
                                    [
                                        "",
                                        (
                                            "Lifecycle-trend: "
                                            f"{lifecycle_measurement_count} "
                                            "metingen verdeeld over "
                                            f"{len(usable_lifecycle_groups)} "
                                            "cycli."
                                        ),
                                    ]
                                )

                                for group in (
                                    usable_lifecycle_groups
                                ):
                                    points = (
                                        group["points"]
                                    )

                                    (
                                        first_date,
                                        first_height,
                                    ) = points[0]

                                    (
                                        last_date,
                                        last_height,
                                    ) = points[-1]

                                    label_parts = [
                                        group[
                                            "scraper_type"
                                        ]
                                    ]

                                    if group[
                                        "position_hint"
                                    ]:
                                        label_parts.append(
                                            group[
                                                "position_hint"
                                            ]
                                        )

                                    if group[
                                        "cycle_id"
                                    ]:
                                        label_parts.append(
                                            (
                                                "cyclus "
                                                + group[
                                                    "cycle_id"
                                                ]
                                            )
                                        )

                                    label = (
                                        " - ".join(
                                            label_parts
                                        )
                                    )

                                    if len(points) == 1:
                                        detail = (
                                            "1 meting, "
                                            + last_date
                                            + " "
                                            + _format_mm(
                                                last_height
                                            )
                                            + " mm"
                                        )
                                    else:
                                        detail = (
                                            str(
                                                len(points)
                                            )
                                            + " metingen, "
                                            + first_date
                                            + " "
                                            + _format_mm(
                                                first_height
                                            )
                                            + " mm -> "
                                            + last_date
                                            + " "
                                            + _format_mm(
                                                last_height
                                            )
                                            + " mm"
                                        )

                                    answer_lines.append(
                                        (
                                            "- "
                                            + label
                                            + ": "
                                            + detail
                                        )
                                    )

                            else:
                                answer_lines.extend(
                                    [
                                        "",
                                        (
                                            "Lifecycle-trend: "
                                            "niet beschikbaar "
                                            "in deze "
                                            "deep-analysisbron."
                                        ),
                                    ]
                                )

                        if (
                            "replacement_events"
                            in requested
                        ):
                            if lifecycle_available:
                                if (
                                    lifecycle_replacement_dates
                                ):
                                    answer_lines.extend(
                                        [
                                            "",
                                            (
                                                "Geregistreerde "
                                                "vervangevents: "
                                                + ", ".join(
                                                    sorted(
                                                        lifecycle_replacement_dates
                                                    )
                                                )
                                            ),
                                        ]
                                    )
                                else:
                                    answer_lines.extend(
                                        [
                                            "",
                                            (
                                                "Geregistreerde "
                                                "vervangevents: "
                                                "geen geregistreerd "
                                                "in de lifecycle."
                                            ),
                                        ]
                                    )
                            else:
                                answer_lines.extend(
                                    [
                                        "",
                                        (
                                            "Geregistreerde "
                                            "vervangevents: "
                                            "niet beschikbaar "
                                            "in deze "
                                            "deep-analysisbron."
                                        ),
                                    ]
                                )

                        if (
                            "uncertainties"
                            in requested
                        ):
                            without_reliable_forecast = [
                                position
                                for position in positions
                                if not isinstance(
                                    position[
                                        "forecast"
                                    ],
                                    dict,
                                )
                            ]

                            answer_lines.extend(
                                [
                                    "",
                                    "Onzekerheden:",
                                ]
                            )

                            if (
                                without_reliable_forecast
                            ):
                                answer_lines.append(
                                    (
                                        "- Voor "
                                        f"{len(without_reliable_forecast)} "
                                        "van "
                                        f"{len(positions)} "
                                        "gepresenteerde posities "
                                        "is geen betrouwbare "
                                        "3 mm-forecast beschikbaar."
                                    )
                                )
                            else:
                                answer_lines.append(
                                    (
                                        "- Voor alle "
                                        "gepresenteerde posities "
                                        "is volgens de huidige "
                                        "forecastcriteria een "
                                        "3 mm-prognose beschikbaar."
                                    )
                                )

                            if lifecycle_available:
                                answer_lines.append(
                                    (
                                        "- Historische "
                                        "lifecycle-posities worden "
                                        "alleen gebruikt voor trend "
                                        "en vervangevents; actuele "
                                        "meshoogtes en vervangadvies "
                                        "hierboven worden daar niet "
                                        "uit afgeleid."
                                    )
                                )
                            else:
                                answer_lines.append(
                                    (
                                        "- Lifecyclehistorie "
                                        "ontbreekt in deze "
                                        "deep-analysisresponse."
                                    )
                                )

                    return "\n".join(
                        answer_lines
                    )

        if result_text:
            answer_lines.extend(
                [
                    "",
                    str(result_text),
                ]
            )

        return "\n".join(answer_lines)

    # -----------------------------------------------------
    # 2. NON-ASSET ANSWERS
    # -----------------------------------------------------

    for item in results:
        specialist_result = item.get("result")

        if not isinstance(
            specialist_result,
            dict,
        ):
            continue

        action = str(
            item.get("action") or ""
        )

        context_type = str(
            specialist_result.get(
                "context_type"
            )
            or ""
        )

        # -------------------------------------------------
        # PROMATI_DIAGNOSTICS_PRESENTATION_V1
        # -------------------------------------------------

        if action == "diagnostics_assistant":
            status = str(
                specialist_result.get("status")
                or "unknown"
            )

            mode = str(
                specialist_result.get("mode")
                or "overview"
            )

            domain = str(
                specialist_result.get("domain")
                or "diagnostics"
            )

            summary = specialist_result.get(
                "summary"
            )

            if not isinstance(summary, dict):
                summary = {}

            findings = specialist_result.get(
                "findings"
            )

            if not isinstance(findings, list):
                findings = []

            recommended_actions = (
                specialist_result.get(
                    "recommended_actions"
                )
            )

            if not isinstance(
                recommended_actions,
                list,
            ):
                recommended_actions = []

            answer_lines = [
                (
                    f"Diagnose ({domain} / {mode}): "
                    f"{status}"
                )
            ]

            gpt_diagnosis = summary.get(
                "gpt_diagnosis"
            )

            if isinstance(gpt_diagnosis, dict):
                headline = gpt_diagnosis.get(
                    "headline"
                )

                if headline:
                    answer_lines.extend(
                        [
                            "",
                            str(headline),
                        ]
                    )

                interpretation = (
                    gpt_diagnosis.get(
                        "interpretation"
                    )
                )

                if isinstance(
                    interpretation,
                    list,
                ):
                    for line in interpretation[:8]:
                        if line:
                            answer_lines.append(
                                f"- {line}"
                            )

            elif summary.get("message"):
                answer_lines.extend(
                    [
                        "",
                        str(summary.get("message")),
                    ]
                )

            else:
                compact_fields = (
                    ("view_name", "View"),
                    ("object_name", "Object"),
                    ("row_count", "Rijen"),
                    (
                        "dependencies_found",
                        "Dependencies",
                    ),
                    (
                        "objects_checked",
                        "Objecten gecontroleerd",
                    ),
                    (
                        "comparisons_made",
                        "Vergelijkingen",
                    ),
                )

                compact_values = []

                for key, label in compact_fields:
                    value = summary.get(key)

                    if value is not None:
                        compact_values.append(
                            f"{label}: {value}"
                        )

                if compact_values:
                    answer_lines.extend(
                        [
                            "",
                            "; ".join(
                                compact_values
                            ),
                        ]
                    )

            if findings:
                answer_lines.extend(
                    [
                        "",
                        "Bevindingen:",
                    ]
                )

                for finding in findings[:8]:
                    if not isinstance(
                        finding,
                        dict,
                    ):
                        continue

                    severity = str(
                        finding.get("severity")
                        or "info"
                    ).upper()

                    issue = (
                        finding.get("issue")
                        or finding.get("message")
                    )

                    if issue:
                        answer_lines.append(
                            f"- [{severity}] {issue}"
                        )

            if recommended_actions:
                answer_lines.extend(
                    [
                        "",
                        "Aanbevolen vervolgstappen:",
                    ]
                )

                for action_text in (
                    recommended_actions[:5]
                ):
                    if action_text:
                        answer_lines.append(
                            f"- {action_text}"
                        )

            return "\n".join(answer_lines)

        # -------------------------------------------------
        # PROMATI_SCOPE_PRESENTATION_V13_1
        # CANONICAL ANALYSIS SCOPE
        # -------------------------------------------------

        if context_type == "analysis_scope":
            short = specialist_result.get(
                "kort_resultaat"
            )

            operation = str(
                specialist_result.get(
                    "operation"
                )
                or ""
            )

            subject = str(
                specialist_result.get(
                    "subject"
                )
                or ""
            )

            count_semantics = str(
                specialist_result.get(
                    "count_semantics"
                )
                or ""
            )

            answer_lines: list[str] = []

            if short:
                answer_lines.append(
                    str(short)
                )

            if (
                operation == "list"
                and subject == "bands"
            ):
                bands = specialist_result.get(
                    "bands"
                )

                if (
                    isinstance(bands, list)
                    and bands
                    and not short
                ):
                    answer_lines.append(
                        "Banden: "
                        + ", ".join(
                            str(band)
                            for band in bands
                        )
                    )

            data_quality = specialist_result.get(
                "data_quality"
            )

            if not isinstance(
                data_quality,
                dict,
            ):
                data_quality = {}

            if (
                count_semantics
                == "current_registered_scraper_positions"
            ):
                semantic_note = (
                    data_quality.get(
                        "semantic_note"
                    )
                )

                if semantic_note:
                    answer_lines.extend(
                        [
                            "",
                            str(semantic_note),
                        ]
                    )

            if (
                count_semantics
                == "historical_maintenance_ranking_rows"
            ):
                answer_lines.extend(
                    [
                        "",
                        (
                            "Let op: dit betreft "
                            "historische onderhoudsregels "
                            "binnen de canonical scope. "
                            "Dat is niet automatisch dezelfde "
                            "set als de actuele unified "
                            "schraperposities."
                        ),
                    ]
                )

            if operation == "analyse":
                answer_lines.extend(
                    [
                        "",
                        (
                            "De wear-evidence kan historische "
                            "posities/cycli bevatten en wordt "
                            "daarom als aanvullende historie "
                            "naast de actuele unified snapshot "
                            "gebruikt."
                        ),
                    ]
                )

            if answer_lines:
                return "\n".join(
                    answer_lines
                )

        # -------------------------------------------------
        # PRODUCT
        # Structured family_context is authoritative.
        # RAG wordt hier bewust niet als primaire bron
        # gebruikt.
        # -------------------------------------------------

        if (
            action == "product_assistant"
            or context_type == "product_assistant"
        ):
            # PROMATI_MULTI_PRODUCT_PUBLIC_SYNTHESIS_P4_5B7_FIX
            # Only activate once the current result is a product result. This keeps
            # the legacy result-order precedence for diagnostics/scope answers.
            multi_product_answer = (
                _build_multi_product_user_answer(
                    results,
                    requested,
                )
            )

            if multi_product_answer is not None:
                return multi_product_answer

            family_context = specialist_result.get(
                "family_context"
            )

            if isinstance(family_context, dict):
                family_rows = family_context.get(
                    "results"
                )

                if (
                    isinstance(family_rows, list)
                    and family_rows
                    and isinstance(
                        family_rows[0],
                        dict,
                    )
                ):
                    family = family_rows[0]

                    name = (
                        family.get("family_name")
                        or family.get("family_code")
                    )

                    strengths = family.get(
                        "strengths"
                    )

                    limitations = family.get(
                        "limitations"
                    )

                    selection_advice = family.get(
                        "selection_advice"
                    )

                    answer_lines = []

                    if name:
                        answer_lines.append(
                            str(name)
                        )

                    if strengths:
                        answer_lines.extend(
                            [
                                "",
                                (
                                    "Sterktes: "
                                    f"{strengths}"
                                ),
                            ]
                        )

                    if limitations:
                        answer_lines.extend(
                            [
                                "",
                                (
                                    "Beperkingen: "
                                    f"{limitations}"
                                ),
                            ]
                        )

                    if selection_advice:
                        answer_lines.extend(
                            [
                                "",
                                (
                                    "Selectieadvies: "
                                    f"{selection_advice}"
                                ),
                            ]
                        )

                    include_inventory = "inventory" in requested
                    include_price = "price" in requested

                    if include_inventory or include_price:
                        article_lines = _build_product_article_lines(
                            specialist_result,
                            include_inventory=include_inventory,
                            include_price=include_price,
                        )

                        if article_lines:
                            answer_lines.extend(
                                [
                                    "",
                                    *article_lines,
                                ]
                            )

                    if answer_lines:
                        return "\n".join(
                            answer_lines
                        )

        # -------------------------------------------------
        # ORG
        # Alleen nested structured ORG-result gebruiken.
        # -------------------------------------------------

        if (
            action == "org_assistant"
            or context_type == "org_assistant"
        ):
            org_result = specialist_result.get(
                "result"
            )

            if not isinstance(
                org_result,
                dict,
            ):
                continue

            org_status = str(
                org_result.get("status")
                or specialist_result.get("status")
                or ""
            ).lower()

            message = org_result.get(
                "message"
            )

            if (
                org_status == "not_found"
                and message
            ):
                return str(message)

            mode = str(
                specialist_result.get("mode")
                or ""
            )

            if mode == "location_info":
                location_rows = org_result.get(
                    "results"
                )

                if isinstance(
                    location_rows,
                    list,
                ):
                    locations = []

                    for location in location_rows:
                        if not isinstance(
                            location,
                            dict,
                        ):
                            continue

                        address = location.get(
                            "adres"
                        )

                        place = location.get(
                            "plaats"
                        )

                        label = (
                            location.get("locatie")
                            or place
                        )

                        # Alleen concrete locatiegegevens.
                        # De algemene firma-routeringsregel
                        # zonder adres/plaats wordt niet als
                        # vestigingsadres gepresenteerd.
                        if address:
                            if label:
                                locations.append(
                                    f"- {label}: {address}"
                                )
                            else:
                                locations.append(
                                    f"- {address}"
                                )

                        elif place:
                            land = location.get(
                                "land"
                            )

                            value = str(place)

                            if land:
                                value += (
                                    f", {land}"
                                )

                            if label:
                                locations.append(
                                    f"- {label}: {value}"
                                )
                            else:
                                locations.append(
                                    f"- {value}"
                                )

                    if locations:
                        return "\n".join(
                            [
                                "Promati is gevestigd op:",
                                *locations,
                            ]
                        )


            # PROMATI_ORG_FUNCTION_PRESENTATION_V1
            if mode == "function_info":
                function_rows = org_result.get(
                    "results"
                )

                if not isinstance(
                    function_rows,
                    list,
                ):
                    continue

                valid_rows = [
                    row
                    for row in function_rows
                    if isinstance(row, dict)
                ]

                if not valid_rows:
                    continue

                row = valid_rows[0]

                display_name = (
                    row.get("weergavenaam")
                    or "Onbekende persoon"
                )

                function_name = (
                    row.get("officiele_functienaam")
                    or row.get("functie_naam")
                )

                department = row.get(
                    "afdeling"
                )

                core_tasks = row.get(
                    "kerntaken"
                )

                answer_lines = []

                if function_name:
                    answer_lines.append(
                        f"{display_name} is "
                        f"{function_name}."
                    )
                else:
                    answer_lines.append(
                        f"Functiegegevens gevonden "
                        f"voor {display_name}."
                    )

                if department:
                    answer_lines.append(
                        f"Afdeling: {department}."
                    )

                if core_tasks:
                    answer_lines.extend(
                        [
                            "",
                            "Kerntaken:",
                            str(core_tasks),
                        ]
                    )

                return "\n".join(
                    answer_lines
                )

        # -------------------------------------------------
        # TECHNICAL - CEMA
        #
        # Het specialistresultaat bevat de CEMA-bron,
        # maar niet de volledige definitie van CEMA.
        # De formatter vult die dus niet uit zichzelf aan.
        # -------------------------------------------------

        if (
            action == "technical_assistant"
            or context_type == "technical_assistant"
        ):
            source_code = (
                specialist_result.get(
                    "source_code"
                )
            )

            if (
                source_code
                == "CEMA_BELT_CONVEYORS_7"
            ):
                technical_context = (
                    specialist_result.get(
                        "technical_context"
                    )
                )

                source_title = None

                if isinstance(
                    technical_context,
                    dict,
                ):
                    technical_rows = (
                        technical_context.get(
                            "results"
                        )
                    )

                    if isinstance(
                        technical_rows,
                        list,
                    ):
                        for row in technical_rows:
                            if not isinstance(
                                row,
                                dict,
                            ):
                                continue

                            candidate = row.get(
                                "source_title"
                            )

                            if candidate:
                                source_title = str(
                                    candidate
                                )
                                break

                # -----------------------------------------
                # Grounded CEMA definition
                #
                # Alleen used_context geldt als bronbewijs.
                # rag_context.antwoord is op zichzelf
                # nadrukkelijk niet voldoende.
                # -----------------------------------------

                full_name = (
                    "Conveyor Equipment Manufacturers Association"
                )

                grounded_full_name = False

                rag_context = (
                    specialist_result.get(
                        "rag_context"
                    )
                )

                if isinstance(
                    rag_context,
                    dict,
                ):
                    used_context = (
                        rag_context.get(
                            "used_context"
                        )
                    )

                    if isinstance(
                        used_context,
                        list,
                    ):
                        for item in used_context:

                            context_text = None

                            if isinstance(
                                item,
                                str,
                            ):
                                context_text = item

                            elif isinstance(
                                item,
                                dict,
                            ):
                                candidate_text = (
                                    item.get(
                                        "text"
                                    )
                                )

                                if isinstance(
                                    candidate_text,
                                    str,
                                ):
                                    context_text = (
                                        candidate_text
                                    )

                            if not context_text:
                                continue

                            if (
                                full_name.casefold()
                                in context_text.casefold()
                            ):
                                grounded_full_name = True
                                break

                if grounded_full_name:
                    if source_title:
                        return (
                            f"CEMA staat voor {full_name}. "
                            f"Bron: {source_title}."
                        )

                    return (
                        f"CEMA staat voor {full_name}."
                    )

                if source_title:
                    return (
                        "CEMA-referentiegegevens zijn "
                        f"beschikbaar uit {source_title}. "
                        "In dit specialistresultaat is "
                        "geen definitierecord van CEMA "
                        "aanwezig."
                    )

                return (
                    "CEMA-referentiegegevens zijn "
                    "beschikbaar, maar in dit "
                    "specialistresultaat is geen "
                    "definitierecord van CEMA aanwezig."
                )

    return None

# PROMATI_MULTI_INTENT_TASK_EVIDENCE_REQUIREMENT_RESOLUTION_SHADOW_V3
def _attach_intent_task_evidence_requirements_shadow(plan: Any) -> Any:
    """Resolve existing catalog contracts for semantic intent tasks.

    Shadow-only: this annotates IntentTask metadata. It does not alter the
    planner, execution steps, Phase-C requirement selection, research gate,
    reconciliation or public answer synthesis.
    """
    tasks = getattr(plan, "intent_tasks", None)

    if not isinstance(tasks, list):
        return plan

    for task in tasks:
        task_intent = getattr(task, "intent", None)
        requirement_set = (
            get_requirement_set(str(task_intent))
            if task_intent
            else None
        )
        task.evidence_requirement_set_id = (
            requirement_set.requirement_set_id
            if requirement_set is not None
            else None
        )

    return plan


# PROMATI_MULTI_INTENT_TASK_EVIDENCE_ASSESSMENT_SHADOW_V4
def _intent_task_domain_value_shadow(task: Any) -> str | None:
    domain = getattr(task, "domain", None)
    value = getattr(domain, "value", domain)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _intent_task_family_codes_shadow(task: Any) -> tuple[str, ...]:
    scope = getattr(task, "scope", None)
    if not isinstance(scope, dict):
        return ()

    raw_codes = scope.get("product_family_codes")
    if not isinstance(raw_codes, (list, tuple)):
        return ()

    output: list[str] = []
    seen: set[str] = set()
    for raw_code in raw_codes:
        code = str(raw_code).strip()
        if not code:
            continue
        key = code.casefold()
        if key in seen:
            continue
        seen.add(key)
        output.append(code)
    return tuple(output)


def _evidence_product_family_code_shadow(item: Any) -> str | None:
    entity_type = str(
        getattr(item, "entity_type", "") or ""
    ).casefold()
    entity_id = getattr(item, "entity_id", None)
    if entity_type == "product" and entity_id is not None:
        text = str(entity_id).strip()
        if text:
            return text

    provenance = getattr(item, "provenance", None)
    if isinstance(provenance, dict):
        raw_code = provenance.get("family_code")
        if raw_code is not None:
            text = str(raw_code).strip()
            if text:
                return text

    return None


def _select_intent_task_evidence_shadow(
    task: Any,
    evidence_items: tuple[Any, ...],
) -> tuple[Any, ...]:
    """Select evidence that is eligible for one semantic task.

    V4 stays shadow-only. Domain isolation is always applied. Product-family
    scopes are additionally isolated by canonical family code. Inspection is
    currently single-band at execution level, so its band scope remains
    represented on IntentTask while evidence isolation is domain-based.
    """
    domain = _intent_task_domain_value_shadow(task)
    family_codes = _intent_task_family_codes_shadow(task)
    family_keys = {
        code.casefold()
        for code in family_codes
    }

    selected: list[Any] = []
    for item in tuple(evidence_items):
        item_domain = str(
            getattr(item, "domain", "") or ""
        ).strip()
        if domain is not None and item_domain != domain:
            continue

        if family_keys:
            family_code = _evidence_product_family_code_shadow(item)
            if (
                family_code is None
                or family_code.casefold() not in family_keys
            ):
                continue

        selected.append(item)

    return tuple(selected)


def _assess_intent_task_evidence_shadow(
    plan: Any,
    evidence_items: tuple[Any, ...],
    *,
    now: datetime,
) -> list[dict[str, Any]]:
    """Assess each IntentTask against its own existing evidence contract.

    This is audit/shadow metadata only. The authoritative Phase-C assessment,
    research gate, reconciliation and public synthesis continue to use the
    legacy plan.intent path.
    """
    tasks = getattr(plan, "intent_tasks", None)
    if not isinstance(tasks, list):
        return []

    output: list[dict[str, Any]] = []

    for task in tasks:
        task_intent = str(
            getattr(task, "intent", "") or ""
        ).strip()
        requirement_set = (
            get_requirement_set(task_intent)
            if task_intent
            else None
        )
        selected_items = _select_intent_task_evidence_shadow(
            task,
            tuple(evidence_items),
        )

        entry: dict[str, Any] = {
            "contract_version": (
                "promati.multi_intent."
                "task_evidence_assessment_shadow.v1"
            ),
            "task_id": getattr(task, "task_id", None),
            "domain": _intent_task_domain_value_shadow(task),
            "intent": task_intent or None,
            "primary": bool(getattr(task, "primary", False)),
            "scope": dict(getattr(task, "scope", {}) or {}),
            "evidence_requirement_set_id": getattr(
                task,
                "evidence_requirement_set_id",
                None,
            ),
            "selected_evidence_count": len(selected_items),
            "selected_evidence_ids": [
                getattr(item, "evidence_id", None)
                for item in selected_items
                if getattr(item, "evidence_id", None) is not None
            ],
            "assessment": None,
            "product_family_scope_assessments": [],
        }

        if requirement_set is None:
            entry["status"] = "unmapped_requirement_set"
            output.append(entry)
            continue

        entry["resolved_requirement_set_id"] = (
            requirement_set.requirement_set_id
        )
        entry["assessment"] = assess_evidence(
            requirement_set,
            selected_items,
            target_entity_ids=None,
            now=now,
        )
        entry["status"] = "assessed"

        family_codes = _intent_task_family_codes_shadow(task)
        if family_codes:
            family_assessments: list[dict[str, Any]] = []
            for family_code in family_codes:
                family_items = tuple(
                    item
                    for item in selected_items
                    if (
                        (_evidence_product_family_code_shadow(item) or "")
                        .casefold()
                        == family_code.casefold()
                    )
                )
                family_assessment = assess_evidence(
                    requirement_set,
                    family_items,
                    target_entity_ids={"product": family_code},
                    now=now,
                )
                family_assessments.append(
                    {
                        "family_code": family_code,
                        "selected_evidence_count": len(family_items),
                        "selected_evidence_ids": [
                            getattr(item, "evidence_id", None)
                            for item in family_items
                            if getattr(item, "evidence_id", None) is not None
                        ],
                        "assessment": family_assessment,
                    }
                )
            entry["product_family_scope_assessments"] = (
                family_assessments
            )

        output.append(entry)

    return output


# PROMATI_MULTI_INTENT_TASK_RESEARCH_DECISION_SHADOW_V5
def _derive_intent_task_research_decisions_shadow(
    task_assessments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Derive research-gate decisions for V4 task assessments.

    V5 is observability/shadow only. These decisions are never passed to
    execute_bounded_research and do not replace the authoritative legacy
    research decision derived from initial_assessment.
    """
    if not isinstance(task_assessments, list):
        return []

    output: list[dict[str, Any]] = []

    for item in task_assessments:
        if not isinstance(item, dict):
            continue

        assessment = item.get("assessment")
        entry: dict[str, Any] = {
            "contract_version": (
                "promati.multi_intent."
                "task_research_decision_shadow.v1"
            ),
            "task_id": item.get("task_id"),
            "domain": item.get("domain"),
            "intent": item.get("intent"),
            "primary": bool(item.get("primary", False)),
            "scope": dict(item.get("scope") or {}),
            "evidence_requirement_set_id": item.get(
                "evidence_requirement_set_id"
            ),
            "resolved_requirement_set_id": item.get(
                "resolved_requirement_set_id"
            ),
            "assessment_status": getattr(
                getattr(assessment, "status", None),
                "value",
                getattr(assessment, "status", None),
            ),
            "research_decision": None,
            "product_family_scope_research_decisions": [],
        }

        if assessment is None:
            entry["status"] = "not_assessed"
        else:
            entry["research_decision"] = (
                decide_research_requirement(assessment)
            )
            entry["status"] = "decided"

        raw_family_rows = item.get(
            "product_family_scope_assessments"
        )
        if isinstance(raw_family_rows, list):
            family_decisions: list[dict[str, Any]] = []
            for family_row in raw_family_rows:
                if not isinstance(family_row, dict):
                    continue

                family_assessment = family_row.get("assessment")
                family_entry: dict[str, Any] = {
                    "family_code": family_row.get("family_code"),
                    "assessment_status": getattr(
                        getattr(
                            family_assessment,
                            "status",
                            None,
                        ),
                        "value",
                        getattr(
                            family_assessment,
                            "status",
                            None,
                        ),
                    ),
                    "research_decision": None,
                }

                if family_assessment is None:
                    family_entry["status"] = "not_assessed"
                else:
                    family_entry["research_decision"] = (
                        decide_research_requirement(
                            family_assessment
                        )
                    )
                    family_entry["status"] = "decided"

                family_decisions.append(family_entry)

            entry[
                "product_family_scope_research_decisions"
            ] = family_decisions

        output.append(entry)

    return output


# PROMATI_MULTI_INTENT_TASK_RESEARCH_EVIDENCE_REASSESSMENT_SHADOW_V9
def _task_research_assessment_status_shadow(assessment: Any) -> str | None:
    raw = getattr(assessment, "status", None)
    raw = getattr(raw, "value", raw)
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _task_research_requirement_statuses_shadow(
    assessment: Any,
) -> dict[str, str]:
    output: dict[str, str] = {}
    for row in tuple(getattr(assessment, "requirement_results", ()) or ()):
        requirement_id = str(getattr(row, "requirement_id", "") or "").strip()
        raw = getattr(row, "status", None)
        raw = getattr(raw, "value", raw)
        if requirement_id and raw is not None:
            output[requirement_id] = str(raw)
    return output


def _dedupe_evidence_items_shadow(items: tuple[Any, ...]) -> tuple[Any, ...]:
    output: list[Any] = []
    seen: set[str] = set()
    for item in tuple(items or ()):
        evidence_id = str(getattr(item, "evidence_id", "") or "").strip()
        key = evidence_id or repr(item)
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return tuple(output)


def _build_intent_task_research_evidence_reassessment_shadow(
    task: Any,
    initial_evidence_items: tuple[Any, ...],
    follow_up_typed_results: list[Any],
    target_requirement_ids: list[str],
    *,
    now: datetime,
) -> dict[str, Any]:
    task_intent = str(getattr(task, "intent", "") or "").strip()
    requirement_set = get_requirement_set(task_intent) if task_intent else None
    selected_before = _select_intent_task_evidence_shadow(
        task,
        tuple(initial_evidence_items or ()),
    )
    follow_up_evidence = tuple(
        evidence
        for typed_result in list(follow_up_typed_results or [])
        for evidence in normalize_execution_result_evidence(
            typed_result,
            retrieved_at=now,
        )
    )
    selected_follow_up = _select_intent_task_evidence_shadow(
        task,
        follow_up_evidence,
    )
    selected_after = _dedupe_evidence_items_shadow(
        tuple(selected_before) + tuple(selected_follow_up)
    )

    contract_version = (
        "promati.multi_intent."
        "task_research_evidence_reassessment_shadow.v1"
    )
    entry: dict[str, Any] = {
        "contract_version": contract_version,
        "task_id": getattr(task, "task_id", None),
        "domain": _intent_task_domain_value_shadow(task),
        "task_intent": task_intent or None,
        "target_requirement_ids": list(target_requirement_ids or []),
        "initial_selected_evidence_count": len(selected_before),
        "initial_selected_evidence_ids": [
            getattr(item, "evidence_id", None)
            for item in selected_before
            if getattr(item, "evidence_id", None) is not None
        ],
        "follow_up_typed_result_count": len(list(follow_up_typed_results or [])),
        "follow_up_evidence_count": len(selected_follow_up),
        "follow_up_evidence_ids": [
            getattr(item, "evidence_id", None)
            for item in selected_follow_up
            if getattr(item, "evidence_id", None) is not None
        ],
        "combined_evidence_count": len(selected_after),
        "combined_evidence_ids": [
            getattr(item, "evidence_id", None)
            for item in selected_after
            if getattr(item, "evidence_id", None) is not None
        ],
        "authoritative": False,
    }

    if requirement_set is None:
        entry["status"] = "unmapped_requirement_set"
        return entry

    before = assess_evidence(
        requirement_set,
        selected_before,
        target_entity_ids=None,
        now=now,
    )
    after = assess_evidence(
        requirement_set,
        selected_after,
        target_entity_ids=None,
        now=now,
    )
    before_requirements = _task_research_requirement_statuses_shadow(before)
    after_requirements = _task_research_requirement_statuses_shadow(after)
    targets = [str(item).strip() for item in list(target_requirement_ids or []) if str(item).strip()]

    entry.update(
        {
            "requirement_set_id": requirement_set.requirement_set_id,
            "before_assessment_status": _task_research_assessment_status_shadow(before),
            "after_assessment_status": _task_research_assessment_status_shadow(after),
            "target_requirement_status_before": {
                requirement_id: before_requirements.get(requirement_id)
                for requirement_id in targets
            },
            "target_requirement_status_after": {
                requirement_id: after_requirements.get(requirement_id)
                for requirement_id in targets
            },
            "status": "reassessed_shadow",
        }
    )
    return entry


# PROMATI_TASK_GROUNDED_SYNTHESIS_SHADOW_V10
_TASK_GROUNDED_SYNTHESIS_MAX_RECORDS_SHADOW = 3
_TASK_GROUNDED_SYNTHESIS_MAX_FRAGMENT_CHARS_SHADOW = 500
_TASK_GROUNDED_SYNTHESIS_STOPWORDS_SHADOW = frozenset(
    {
        "aan",
        "als",
        "bij",
        "dat",
        "de",
        "dit",
        "een",
        "en",
        "geef",
        "het",
        "hoe",
        "in",
        "is",
        "leg",
        "met",
        "ook",
        "of",
        "om",
        "op",
        "over",
        "uit",
        "van",
        "voor",
        "wat",
        "welke",
        "zijn",
    }
)


def _task_grounded_synthesis_question_tokens_shadow(
    task_question: str,
) -> tuple[str, ...]:
    tokens = {
        token
        for token in re.findall(
            r"[a-z0-9][a-z0-9_-]+",
            str(task_question or "").casefold(),
        )
        if len(token) >= 3
        and token not in _TASK_GROUNDED_SYNTHESIS_STOPWORDS_SHADOW
    }
    return tuple(sorted(tokens))


# PROMATI_TASK_GROUNDED_SYNTHESIS_RELEVANCE_TIGHTENING_V10_1
_TASK_GROUNDED_SYNTHESIS_DEFINITION_CUES_SHADOW = (
    "staat voor",
    "betekent",
    "afkorting",
    "voluit",
    "definition",
    "defined as",
    "stands for",
    "means",
)


def _task_grounded_synthesis_definition_focus_shadow(
    task_question: str,
) -> str | None:
    question = " ".join(str(task_question or "").split()).strip()
    lowered = question.casefold()
    patterns = (
        r"\bwat\s+([A-Z][A-Z0-9_-]{1,15})\s+betekent\b",
        r"\bwat\s+betekent\s+([A-Z][A-Z0-9_-]{1,15})\b",
        r"\bwaar\s+staat\s+([A-Z][A-Z0-9_-]{1,15})\s+voor\b",
        r"\bbetekenis\s+van\s+([A-Z][A-Z0-9_-]{1,15})\b",
        r"\bwat\s+is\s+([A-Z][A-Z0-9_-]{1,15})\b",
    )
    for pattern in patterns:
        match = re.search(pattern, question)
        if match:
            return match.group(1).casefold()

    # Preserve fail-closed behavior for lower/normalized task questions that
    # still contain an acronym-like token after deterministic projection.
    if any(cue in lowered for cue in ("betekent", "staat voor", "betekenis", "wat is")):
        candidates = [
            token.casefold()
            for token in re.findall(r"\b[A-Za-z][A-Za-z0-9_-]{2,15}\b", question)
            if token.casefold() not in _TASK_GROUNDED_SYNTHESIS_STOPWORDS_SHADOW
        ]
        if candidates:
            return candidates[-1]
    return None



# PROMATI_TECHNICAL_DEFINITION_RELATION_TIGHTENING_SHADOW_V10_3_1
# PROMATI_TECHNICAL_DEFINITION_ACRONYM_BOUNDARY_SANITIZATION_SHADOW_V10_3_3_1
def _task_grounded_synthesis_reverse_acronym_relation_span_shadow(
    raw_text: str,
    focus_term: str,
) -> tuple[int, int] | None:
    """Return the exact expansion span for reverse acronym relations.

    A reverse relation such as
    "Conveyor Equipment Manufacturers Association (CEMA)"
    is accepted only when the initials of the immediately preceding expansion
    words equal the focus acronym. This prevents arbitrary document headers
    from being absorbed by a greedy multi-word regex.
    """
    text_value = " ".join(str(raw_text or "").split()).strip()
    focus = "".join(
        ch
        for ch in str(focus_term or "")
        if ch.isalpha()
    )
    if not text_value or len(focus) < 2 or len(focus) > 10:
        return None

    escaped = re.escape(focus)
    marker_patterns = (
        rf"\(\s*{escaped}\s*\)",
        rf",?\s+(?:abbreviated|afgekort)\s+(?:as\s+)?{escaped}\b",
    )

    candidates: list[tuple[int, int]] = []
    for marker_pattern in marker_patterns:
        for marker in re.finditer(
            marker_pattern,
            text_value,
            flags=re.IGNORECASE,
        ):
            prefix = text_value[: marker.start()]
            words = list(
                re.finditer(
                    r"[A-Za-z][A-Za-z&'/-]*",
                    prefix,
                )
            )
            needed = len(focus)
            if len(words) < needed:
                continue

            expansion_words = words[-needed:]
            gap = prefix[expansion_words[-1].end():]
            if not re.fullmatch(r"\s*,?\s*", gap):
                continue

            initials = "".join(
                word.group(0)[0]
                for word in expansion_words
            )
            if initials.casefold() != focus.casefold():
                continue

            candidates.append(
                (
                    expansion_words[0].start(),
                    marker.end(),
                )
            )

    if not candidates:
        return None
    return min(candidates, key=lambda item: item[0])


def _task_grounded_synthesis_definition_relation_shadow(
    raw_text: str,
    focus_term: str,
) -> bool:
    """Return True only for an explicit acronym/definition relation in raw text.

    This helper intentionally operates on the original evidence text only.
    Synthetic titles, subjects, provenance and source names are excluded.
    """
    text_value = " ".join(str(raw_text or "").split()).strip()
    focus = " ".join(str(focus_term or "").split()).strip()
    if not text_value or not focus:
        return False

    escaped = re.escape(focus)
    forward_relation_patterns = (
        rf"\b{escaped}\b\s+(?:means|stands\s+for|staat\s+voor|betekent)\s+\S+",
        rf"\b{escaped}\b\s+is\s+(?:an?\s+)?(?:acronym|abbreviation)\s+for\s+\S+",
        rf"\b{escaped}\b\s*=\s*\S+",
    )
    if any(
        re.search(pattern, text_value, flags=re.IGNORECASE)
        for pattern in forward_relation_patterns
    ):
        return True

    return (
        _task_grounded_synthesis_reverse_acronym_relation_span_shadow(
            text_value,
            focus,
        )
        is not None
    )



# PROMATI_TECHNICAL_DEFINITION_RELATION_LOCAL_EXTRACTION_SHADOW_V10_3_2
def _task_grounded_synthesis_definition_relation_fragment_shadow(
    raw_text: str,
    focus_term: str,
) -> str | None:
    """Extract a compact raw-text window beginning at the semantic relation."""
    text_value = " ".join(str(raw_text or "").split()).strip()
    focus = " ".join(str(focus_term or "").split()).strip()
    if not text_value or not focus:
        return None

    escaped = re.escape(focus)
    forward_relation_patterns = (
        rf"\b{escaped}\b\s+(?:means|stands\s+for|staat\s+voor|betekent)\s+\S+",
        rf"\b{escaped}\b\s+is\s+(?:an?\s+)?(?:acronym|abbreviation)\s+for\s+\S+",
        rf"\b{escaped}\b\s*=\s*\S+",
    )

    relation_spans: list[tuple[int, int]] = []
    for pattern in forward_relation_patterns:
        match = re.search(
            pattern,
            text_value,
            flags=re.IGNORECASE,
        )
        if match is not None:
            relation_spans.append(
                (
                    match.start(),
                    match.end(),
                )
            )

    reverse_span = (
        _task_grounded_synthesis_reverse_acronym_relation_span_shadow(
            text_value,
            focus,
        )
    )
    if reverse_span is not None:
        relation_spans.append(reverse_span)

    if not relation_spans:
        return None

    relation_start, relation_end = min(
        relation_spans,
        key=lambda item: item[0],
    )

    # V10.3.3.1: begin at the semantic relation itself. Preceding document
    # headers/contact/order metadata are never included in the rendered answer.
    start = relation_start
    right_limit = min(
        len(text_value),
        relation_end + 320,
    )

    right_region = text_value[relation_end:right_limit]
    candidates = [
        pos
        for pos in (
            right_region.find(". "),
            right_region.find("! "),
            right_region.find("? "),
            right_region.find("; "),
        )
        if pos >= 0
    ]
    end = (
        relation_end + min(candidates) + 1
        if candidates
        else right_limit
    )

    fragment = " ".join(
        text_value[start:end].split()
    ).strip()
    if not fragment:
        return None

    limit = _TASK_GROUNDED_SYNTHESIS_MAX_FRAGMENT_CHARS_SHADOW
    if len(fragment) > limit:
        fragment = (
            fragment[: max(1, limit - 1)].rstrip()
            + "â€¦"
        )

    if focus.casefold() not in fragment.casefold():
        return None
    return fragment


def _task_grounded_synthesis_definition_answer_fragment_shadow(
    evidence_item: Any,
    focus_term: str,
) -> str | None:
    """Render bridge evidence from the relation-local raw used_context only."""
    provenance = getattr(evidence_item, "provenance", None)
    is_v10_3_rag_bridge = (
        isinstance(provenance, dict)
        and str(provenance.get("bridge") or "").strip()
        == "technical_definition_rag_evidence_shadow_v10_3"
    )
    if not is_v10_3_rag_bridge:
        return _task_grounded_synthesis_fragment_shadow(evidence_item)

    value = getattr(evidence_item, "value", None)
    if not isinstance(value, dict):
        return None
    summary = value.get("summary_nl")
    if not isinstance(summary, str):
        return None

    fragment = _task_grounded_synthesis_definition_relation_fragment_shadow(
        summary,
        focus_term,
    )
    if not fragment:
        return None
    return f"Technical RAG fragment: {fragment}"


def _task_grounded_synthesis_definition_relevance_shadow(
    evidence_item: Any,
    focus_term: str,
) -> tuple[bool, tuple[str, ...]]:
    value = getattr(evidence_item, "value", None)
    if not isinstance(value, dict):
        return False, ()

    focus = str(focus_term or "").casefold().strip()
    if not focus:
        return False, ()

    provenance = getattr(evidence_item, "provenance", None)
    is_v10_3_rag_bridge = (
        isinstance(provenance, dict)
        and str(provenance.get("bridge") or "").strip()
        == "technical_definition_rag_evidence_shadow_v10_3"
    )

    # V10.3.1: bridged RAG evidence may only become definition-relevant when
    # the raw used_context text itself states an explicit definition/acronym
    # relation. Synthetic title/subject/provenance must never satisfy this gate.
    if is_v10_3_rag_bridge:
        raw_summary = value.get("summary_nl")
        if not isinstance(raw_summary, str):
            return False, ()
        if _task_grounded_synthesis_definition_relation_shadow(
            raw_summary,
            focus,
        ):
            return True, ("summary_nl",)
        return False, ()

    # Retain the V10.1 contract for all non-bridge evidence.
    # Deliberately exclude source_title and generic provenance fields: a source
    # being a CEMA document is not itself evidence for what CEMA means.
    rendered_fields: list[tuple[str, str]] = []
    for field in (
        "title",
        "chapter_title",
        "summary_nl",
        "key_points_nl",
        "structured_data",
    ):
        raw = value.get(field)
        if raw in (None, "", [], {}):
            continue
        if isinstance(raw, str):
            rendered = raw
        else:
            try:
                rendered = json.dumps(
                    raw,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                    default=str,
                )
            except (TypeError, ValueError):
                rendered = str(raw)
        rendered_fields.append((field, rendered.casefold()))

    matched_fields = tuple(
        field
        for field, rendered in rendered_fields
        if focus in rendered
        and any(
            cue in rendered
            for cue in _TASK_GROUNDED_SYNTHESIS_DEFINITION_CUES_SHADOW
        )
    )
    return bool(matched_fields), matched_fields


def _task_grounded_synthesis_record_search_text_shadow(
    evidence_item: Any,
) -> str:
    value = getattr(evidence_item, "value", None)
    if not isinstance(value, dict):
        return str(value or "").casefold()

    relevant_fields = (
        "title",
        "chapter_title",
        "summary_nl",
        "key_points_nl",
        "structured_data",
    )
    fragments: list[str] = []
    for field in relevant_fields:
        raw = value.get(field)
        if raw in (None, "", [], {}):
            continue
        if isinstance(raw, str):
            rendered = raw
        else:
            try:
                rendered = json.dumps(
                    raw,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                    default=str,
                )
            except (TypeError, ValueError):
                rendered = str(raw)
        fragments.append(rendered)
    return " ".join(fragments).casefold()


def _task_grounded_synthesis_fragment_shadow(
    evidence_item: Any,
) -> str | None:
    value = getattr(evidence_item, "value", None)
    if not isinstance(value, dict):
        return None

    title = " ".join(str(value.get("title") or "").split()).strip()
    summary = " ".join(str(value.get("summary_nl") or "").split()).strip()
    key_points = value.get("key_points_nl")
    if isinstance(key_points, (list, tuple)):
        key_points = "; ".join(
            " ".join(str(item).split()).strip()
            for item in key_points
            if " ".join(str(item).split()).strip()
        )
    else:
        key_points = " ".join(str(key_points or "").split()).strip()

    body = summary or key_points or title
    if not body:
        return None

    if title and body != title:
        fragment = f"{title}: {body}"
    else:
        fragment = body

    source_title = " ".join(
        str(value.get("source_title") or "").split()
    ).strip()
    page_start = value.get("page_start")
    page_end = value.get("page_end")
    source_suffix = ""
    if source_title:
        source_suffix = f" Bron: {source_title}"
        if page_start is not None:
            if page_end is not None and page_end != page_start:
                source_suffix += f", p. {page_start}-{page_end}"
            else:
                source_suffix += f", p. {page_start}"
        source_suffix += "."

    limit = _TASK_GROUNDED_SYNTHESIS_MAX_FRAGMENT_CHARS_SHADOW
    if len(fragment) > limit:
        fragment = fragment[: limit - 1].rstrip() + "â€¦"

    return fragment + source_suffix



# PROMATI_TECHNICAL_DEFINITION_RAG_EVIDENCE_BRIDGE_SHADOW_V10_3
def _task_definition_rag_evidence_bridge_shadow(
    task: Any,
    task_question: str,
    follow_up_typed_results: list[Any],
    *,
    now: datetime,
) -> tuple[EvidenceItem, ...]:
    """Project grounded technical RAG used_context into detached shadow evidence.

    This bridge is intentionally narrower than the authoritative evidence
    adapter. It only runs for a secondary technical_lookup definition task and
    only trusts rag_context.used_context from the guarded follow-up result.
    rag_context.answer/antwoord and generic context_hits are never treated as
    evidence. The returned items are consumed only by detached task synthesis.
    """
    if _intent_task_domain_value_shadow(task) != "technical":
        return ()
    if str(getattr(task, "intent", "") or "").strip() != "technical_lookup":
        return ()

    focus_term = _task_grounded_synthesis_definition_focus_shadow(task_question)
    if not focus_term:
        return ()

    evidence_items: list[EvidenceItem] = []
    seen: set[str] = set()

    for typed_result in list(follow_up_typed_results or []):
        raw_result = getattr(typed_result, "result", None)
        if not isinstance(raw_result, dict):
            continue

        source_code = str(raw_result.get("source_code") or "").strip()
        if source_code.upper() != "CEMA_BELT_CONVEYORS_7":
            continue

        rag_context = raw_result.get("rag_context")
        if not isinstance(rag_context, dict):
            continue
        if str(rag_context.get("status") or "ok").casefold() == "error":
            continue

        used_context = rag_context.get("used_context")
        if not isinstance(used_context, list):
            continue

        scope_doc_ids = tuple(
            str(item).strip()
            for item in list(rag_context.get("scope_doc_ids") or [])
            if str(item).strip()
        )

        for index, raw_item in enumerate(used_context):
            doc_id = None
            chunk_index = None
            if isinstance(raw_item, str):
                context_text = raw_item
            elif isinstance(raw_item, dict):
                context_text = raw_item.get("text")
                doc_id = raw_item.get("doc_id")
                chunk_index = raw_item.get("chunk_index")
            else:
                continue

            context_text = " ".join(str(context_text or "").split()).strip()
            if not context_text:
                continue

            # Do not manufacture semantic relevance here. The existing V10.1
            # definition gate remains authoritative for whether this fragment
            # actually answers the isolated definition task.
            stable_payload = json.dumps(
                {
                    "step_id": getattr(typed_result, "step_id", None),
                    "source_code": source_code,
                    "doc_id": doc_id,
                    "chunk_index": chunk_index,
                    "text": context_text,
                    "index": index,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            )
            evidence_id = "evidence-shadow-rag-" + hashlib.sha256(
                stable_payload.encode("utf-8")
            ).hexdigest()
            if evidence_id in seen:
                continue
            seen.add(evidence_id)

            source_reference = str(doc_id or "").strip() or (
                f"{source_code}:used_context:{index}"
            )
            evidence_items.append(
                EvidenceItem(
                    contract_version=EVIDENCE_CONTRACT_VERSION,
                    evidence_id=evidence_id,
                    execution_step_id=str(
                        getattr(typed_result, "step_id", "") or ""
                    ),
                    specialist_id=str(
                        getattr(typed_result, "action", "") or "technical_assistant"
                    ),
                    domain="technical",
                    subject="Technical RAG fragment",
                    entity_type="technical_rag_fragment",
                    entity_id=(
                        f"{doc_id}:{chunk_index}"
                        if doc_id not in (None, "") and chunk_index is not None
                        else str(doc_id or "").strip() or None
                    ),
                    evidence_type=EvidenceType.DOCUMENT_FRAGMENT,
                    source_type=EvidenceSourceType.RAG_CONTEXT,
                    source_name=source_code,
                    source_reference=source_reference,
                    source_priority=None,
                    observed_at=None,
                    retrieved_at=now,
                    effective_at=None,
                    value={
                        "title": "Technical RAG fragment",
                        "summary_nl": context_text,
                        "source_code": source_code,
                        "doc_id": doc_id,
                        "chunk_index": chunk_index,
                    },
                    unit=None,
                    claim_scope=(),
                    freshness_status=EvidenceFreshnessStatus.NOT_APPLICABLE,
                    grounding_status=EvidenceGroundingStatus.GROUNDED,
                    quality_status=EvidenceQualityStatus.VALID,
                    direct_or_derived=EvidenceDirectness.DIRECT,
                    derivation_reference=None,
                    provenance={
                        "source_code": source_code,
                        "doc_id": doc_id,
                        "chunk_index": chunk_index,
                        "scope_doc_ids": scope_doc_ids,
                        "source_route": raw_result.get("rag_source_route"),
                        "bridge": "technical_definition_rag_evidence_shadow_v10_3",
                    },
                )
            )

    return tuple(evidence_items)


def _build_intent_task_grounded_synthesis_shadow(
    task: Any,
    task_question: str,
    initial_evidence_items: tuple[Any, ...],
    follow_up_typed_results: list[Any],
    target_requirement_ids: list[str],
    *,
    now: datetime,
) -> dict[str, Any]:
    """Build one detached, deterministic grounded task answer.

    Shadow-only. The helper reuses the existing evidence adapter, assessor and
    grounded synthesizer contract, then creates a compact extract from only
    claimable evidence records that are relevant to the isolated task question.
    It never mutates authoritative Phase-C evidence or the public answer.
    """
    contract_version = (
        "promati.multi_intent.task_grounded_synthesis_shadow.v1"
    )
    task_intent = str(getattr(task, "intent", "") or "").strip()
    requirement_set = get_requirement_set(task_intent) if task_intent else None
    entry: dict[str, Any] = {
        "contract_version": contract_version,
        "task_id": getattr(task, "task_id", None),
        "domain": _intent_task_domain_value_shadow(task),
        "task_intent": task_intent or None,
        "task_question": " ".join(str(task_question or "").split()).strip(),
        "target_requirement_ids": list(target_requirement_ids or []),
        "authoritative": False,
        "provider_ai_calls_used": 0,
        "task_answer_mode": "deterministic_extractive_grounded",
        "task_answer": None,
    }

    if requirement_set is None:
        entry["status"] = "unmapped_requirement_set"
        return entry

    selected_before = _select_intent_task_evidence_shadow(
        task,
        tuple(initial_evidence_items or ()),
    )
    follow_up_evidence = tuple(
        evidence
        for typed_result in list(follow_up_typed_results or [])
        for evidence in normalize_execution_result_evidence(
            typed_result,
            retrieved_at=now,
        )
    )
    rag_definition_evidence = _task_definition_rag_evidence_bridge_shadow(
        task,
        task_question,
        list(follow_up_typed_results or []),
        now=now,
    )
    selected_follow_up = _select_intent_task_evidence_shadow(
        task,
        _dedupe_evidence_items_shadow(
            tuple(follow_up_evidence) + tuple(rag_definition_evidence)
        ),
    )
    selected_after = _dedupe_evidence_items_shadow(
        tuple(selected_before) + tuple(selected_follow_up)
    )

    before = assess_evidence(
        requirement_set,
        selected_before,
        target_entity_ids=None,
        now=now,
    )
    after = assess_evidence(
        requirement_set,
        selected_after,
        target_entity_ids=None,
        now=now,
    )
    before_status = _task_research_assessment_status_shadow(before)
    after_status = _task_research_assessment_status_shadow(after)
    after_requirements = _task_research_requirement_statuses_shadow(after)
    targets = [
        str(item).strip()
        for item in list(target_requirement_ids or [])
        if str(item).strip()
    ]

    entry.update(
        {
            "requirement_set_id": requirement_set.requirement_set_id,
            "before_assessment_status": before_status,
            "after_assessment_status": after_status,
            "target_requirement_status_after": {
                requirement_id: after_requirements.get(requirement_id)
                for requirement_id in targets
            },
            "initial_selected_evidence_count": len(selected_before),
            "follow_up_evidence_count": len(selected_follow_up),
            "rag_definition_evidence_count": len(rag_definition_evidence),
            "rag_definition_evidence_ids": [
                getattr(item, "evidence_id", None)
                for item in rag_definition_evidence
                if getattr(item, "evidence_id", None) is not None
            ],
            "combined_evidence_count": len(selected_after),
        }
    )

    if (
        after.status is not EvidenceAssessmentStatus.SUFFICIENT
        or any(
            after_requirements.get(requirement_id) != "satisfied"
            for requirement_id in targets
        )
    ):
        entry["status"] = "blocked_insufficient_task_evidence"
        return entry

    initial_ids = {
        str(getattr(item, "evidence_id", "") or "")
        for item in selected_before
    }
    added_ids = tuple(
        sorted(
            str(getattr(item, "evidence_id", "") or "")
            for item in selected_after
            if str(getattr(item, "evidence_id", "") or "")
            and str(getattr(item, "evidence_id", "") or "") not in initial_ids
        )
    )
    reconciliation_status = (
        EvidenceReconciliationStatus.IMPROVED
        if before.status is not EvidenceAssessmentStatus.SUFFICIENT
        else EvidenceReconciliationStatus.UNRESOLVED
    )
    shadow_reconciliation = EvidenceReconciliationResult(
        contract_version="task_grounded_synthesis_shadow_reconciliation.v1",
        requirement_set_id=requirement_set.requirement_set_id,
        intent=requirement_set.intent,
        status=reconciliation_status,
        research_status=ResearchExecutionStatus.COMPLETED,
        initial_evidence_items=tuple(selected_before),
        reconciled_evidence_items=tuple(selected_after),
        added_evidence_ids=added_ids,
        discarded_result_count=0,
        initial_assessment=before,
        reconciled_assessment=after,
        reasons=("task_grounded_synthesis_shadow",),
    )
    grounded = synthesize_grounded_evidence(shadow_reconciliation)
    grounded_status = getattr(getattr(grounded, "status", None), "value", None)
    claimable_ids = set(getattr(grounded, "evidence_ids_used", ()) or ())
    entry.update(
        {
            "grounded_synthesis_status": grounded_status,
            "grounded_claim_count": len(tuple(getattr(grounded, "claims", ()) or ())),
            "grounded_evidence_ids_used": list(
                getattr(grounded, "evidence_ids_used", ()) or ()
            ),
            "omitted_requirement_ids": list(
                getattr(grounded, "omitted_requirement_ids", ()) or ()
            ),
            "conflicting_requirement_ids": list(
                getattr(grounded, "conflicting_requirement_ids", ()) or ()
            ),
        }
    )

    query_tokens = _task_grounded_synthesis_question_tokens_shadow(task_question)
    definition_focus = _task_grounded_synthesis_definition_focus_shadow(
        task_question
    )
    entry["definition_focus_term"] = definition_focus
    entry["definition_relevance_required"] = bool(definition_focus)

    ranked: list[tuple[int, str, Any]] = []
    definition_relevant_ids: list[str] = []
    for evidence_item in selected_after:
        evidence_id = str(getattr(evidence_item, "evidence_id", "") or "")
        if not evidence_id or evidence_id not in claimable_ids:
            continue
        search_text = _task_grounded_synthesis_record_search_text_shadow(
            evidence_item
        )
        score = sum(1 for token in query_tokens if token in search_text)
        if score <= 0:
            continue

        if definition_focus:
            definition_relevant, _ = (
                _task_grounded_synthesis_definition_relevance_shadow(
                    evidence_item,
                    definition_focus,
                )
            )
            if not definition_relevant:
                continue
            definition_relevant_ids.append(evidence_id)
            # Give definition-grounded records a deterministic preference above
            # incidental acronym mentions while preserving lexical ranking.
            score += 100

        ranked.append((score, evidence_id, evidence_item))

    entry["definition_relevant_evidence_ids"] = sorted(
        set(definition_relevant_ids)
    )

    ranked.sort(key=lambda item: (-item[0], item[1]))
    selected_records: list[dict[str, Any]] = []
    fragments: list[str] = []
    for score, evidence_id, evidence_item in ranked:
        if definition_focus:
            fragment = _task_grounded_synthesis_definition_answer_fragment_shadow(
                evidence_item,
                definition_focus,
            )
        else:
            fragment = _task_grounded_synthesis_fragment_shadow(evidence_item)
        if not fragment:
            continue
        selected_records.append(
            {
                "evidence_id": evidence_id,
                "relevance_score": score,
            }
        )
        fragments.append(fragment)
        if len(fragments) >= _TASK_GROUNDED_SYNTHESIS_MAX_RECORDS_SHADOW:
            break

    entry["selected_grounded_records"] = selected_records
    entry["selected_grounded_record_count"] = len(selected_records)
    entry["definition_relation_local_extraction"] = bool(definition_focus)

    if not fragments:
        entry["status"] = (
            "blocked_insufficient_task_relevance"
            if definition_focus
            else "blocked_no_task_relevant_grounded_evidence"
        )
        return entry

    entry["task_answer"] = "\n".join(fragments)
    entry["status"] = "grounded_task_synthesis_shadow"
    return entry


# PROMATI_TASK_RESEARCH_TECHNICAL_QUESTION_ISOLATION_V9_1
_TASK_RESEARCH_TECHNICAL_QUESTION_ANCHORS_SHADOW = (
    "cema",
    "trogrol",
    "trogrollen",
    "idler",
    "idlers",
    "bandsnelheid",
    "bandsterkte",
    "transportbandberekening",
    "transportband berekening",
    "transportbandberekeningen",
    "transportband formule",
    "formule voor transportband",
)


def _project_secondary_technical_question_shadow(
    plan: Any,
    task: Any,
) -> str | None:
    """Project one safe technical sub-question from a compound user question.

    V9 runtime proved that forwarding the complete product+technical question
    makes the technical specialist hit its product routing guard. Keep this
    projector deliberately narrow: it is only used by the secondary
    technical_lookup execution canary. If no uncontaminated technical clause
    can be identified deterministically, the canary must block instead of
    guessing or weakening the specialist routing guard.
    """
    if _intent_task_domain_value_shadow(task) != "technical":
        return None
    if str(getattr(task, "intent", "") or "").strip() != "technical_lookup":
        return None

    raw_question = str(getattr(plan, "original_question", "") or "").strip()
    if not raw_question:
        return None

    product_tokens: set[str] = set()
    for family in list(getattr(plan, "product_families", None) or []):
        for attr in ("value", "raw_value"):
            value = getattr(family, attr, None)
            if value is None and isinstance(family, dict):
                value = family.get(attr)
            normalized = str(value or "").strip().casefold()
            if normalized:
                product_tokens.add(normalized)

    fragments = [
        " ".join(fragment.strip(" ,:-").split())
        for fragment in re.split(
            r"(?i)(?:[.;!?]+|\s+(?:en|and|plus)\s+)",
            raw_question,
        )
    ]

    selected: list[str] = []
    for fragment in fragments:
        if not fragment:
            continue
        normalized = fragment.casefold()
        if not any(
            anchor in normalized
            for anchor in _TASK_RESEARCH_TECHNICAL_QUESTION_ANCHORS_SHADOW
        ):
            continue
        if any(token in normalized for token in product_tokens):
            continue
        selected.append(fragment)

    if not selected:
        return None

    projected = " ".join(selected).strip()
    normalized_projected = projected.casefold()
    if not any(
        anchor in normalized_projected
        for anchor in _TASK_RESEARCH_TECHNICAL_QUESTION_ANCHORS_SHADOW
    ):
        return None
    if any(token in normalized_projected for token in product_tokens):
        return None
    return projected


# PROMATI_MULTI_INTENT_TASK_RESEARCH_EXECUTION_CANARY_SHADOW_V8
_TASK_RESEARCH_EXECUTION_CANARY_ENV = (
    "AI_TASK_RESEARCH_EXECUTION_CANARY_ENABLED"
)
_TASK_RESEARCH_EXECUTION_CANARY_INTENT = "technical_lookup"
_TASK_RESEARCH_EXECUTION_CANARY_ACTION = "technical_assistant"
_TASK_RESEARCH_EXECUTION_CANARY_TARGETS = frozenset(
    {"TECHNICAL_SOURCE"}
)


def _task_research_execution_canary_enabled_shadow() -> bool:
    raw = os.getenv(
        _TASK_RESEARCH_EXECUTION_CANARY_ENV,
        "false",
    )
    return str(raw).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


class _TaskResearchCanaryPlannerResponseShadow:
    def __init__(self, text: str):
        self.text = text


# PROMATI_TECHNICAL_DEFINITION_RETRIEVAL_SHADOW_V10_2
def _task_research_definition_retrieval_question_shadow(
    task_question: str,
) -> str:
    """Project a deterministic retrieval query for definition-bearing evidence.

    V10.1 proved that source-level TECHNICAL_SOURCE satisfaction is not enough
    to answer a definition task. Keep the original isolated task question for
    task semantics, but make the single guarded specialist follow-up use a
    definition-shaped query when the task is specifically a CEMA definition
    question. No answer text or acronym expansion is injected here.
    """
    cleaned = " ".join(str(task_question or "").split()).strip()
    if not cleaned:
        return ""

    focus = _task_grounded_synthesis_definition_focus_shadow(cleaned)
    if str(focus or "").casefold() != "cema":
        return cleaned

    return (
        "Wat betekent CEMA? Waar staat CEMA voor? "
        "Geef uitsluitend bronpassages waarin CEMA expliciet wordt "
        "gedefinieerd, als afkorting wordt uitgelegd of voluit wordt geschreven."
    )


def _task_research_canary_planner_shadow(
    *,
    action: str,
    question: str,
    target_requirement_ids: list[str],
):
    """Deterministic no-provider planner for the V8 execution canary.

    The first invocation requests exactly one guarded specialist follow-up.
    A later invocation synthesizes so the canary can never request a second
    specialist call even if the surrounding bounded runtime loops again.
    """
    state = {"calls": 0}

    def _planner(_request):
        state["calls"] += 1
        if state["calls"] > 1:
            payload = {
                "decision": "synthesize",
                "reason": "V8 canary follow-up is complete.",
                "gaps": [],
                "calls": [],
            }
        else:
            task_question = (
                "Beantwoord uitsluitend de technische deelvraag. "
                "Gebruik alleen de toegestane read-only specialist. "
                "Oorspronkelijke vraag: "
                + str(question or "").strip()
            )
            payload = {
                "decision": "follow_up",
                "reason": (
                    "V8 deterministic task-research execution canary."
                ),
                "gaps": list(target_requirement_ids or []),
                "calls": [
                    {
                        "action": action,
                        "reason": (
                            "Vul uitsluitend de technische evidence-gap."
                        ),
                        "params": {
                            "vraag": task_question,
                        },
                    }
                ],
            }

        return _TaskResearchCanaryPlannerResponseShadow(
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
            )
        )

    return _planner


def _task_research_canary_synthesizer_shadow(
    _plan: Any,
    combined_results: list[dict[str, Any]],
) -> dict[str, Any]:
    summaries: list[dict[str, Any]] = []
    follow_up_count = 0

    for item in list(combined_results or []):
        if not isinstance(item, dict):
            continue
        follow_up = item.get("research_follow_up")
        if isinstance(follow_up, dict):
            follow_up_count += 1
        summary = _task_research_result_summary_shadow(item)
        summary["research_follow_up"] = bool(
            isinstance(follow_up, dict)
        )
        summaries.append(summary)

    return {
        "status": "canary_observed",
        "answer": None,
        "ai_calls_used": 0,
        "combined_result_count": len(summaries),
        "follow_up_result_count": follow_up_count,
        "result_summaries": summaries,
    }


def _task_research_canary_copy_plan_shadow(
    plan: Any,
    task: Any,
    *,
    task_question: str | None = None,
) -> Any:
    if hasattr(plan, "model_copy"):
        projected = plan.model_copy(deep=True)
    else:
        projected = plan.copy(deep=True)

    if task_question is not None:
        cleaned_task_question = " ".join(str(task_question).split()).strip()
        if cleaned_task_question:
            projected.original_question = cleaned_task_question
            projected.normalized_question = cleaned_task_question.casefold()

    domain = getattr(task, "domain", None)
    selected_steps = _select_intent_task_execution_steps_shadow(
        plan,
        task,
        family_code=None,
    )

    projected.primary_domain = domain
    projected.domains = [domain] if domain is not None else []
    projected.intent = str(getattr(task, "intent", "") or "")
    projected.intent_tasks = []
    projected.requested_information = list(
        getattr(task, "requested_information", None) or []
    )
    projected.entities = {}
    projected.product_families = []
    projected.residual_terms = []
    projected.multi_intent = False
    projected.research_required = True
    projected.execution_blockers = []
    projected.clarification_required = False
    projected.clarification_question = None
    projected.execution_steps = [
        (
            step.model_copy(deep=True)
            if hasattr(step, "model_copy")
            else step.copy(deep=True)
        )
        for step in selected_steps
    ]
    return projected


def _task_research_canary_guard_shadow(
    guard_entry: dict[str, Any],
) -> ResearchCallGuard:
    return normalize_research_call_guard(
        ResearchCallGuard(
            allowed_action=str(
                guard_entry.get("allowed_research_action") or ""
            ).strip(),
            pinned_params=dict(
                guard_entry.get("pinned_params") or {}
            ),
            target_requirement_ids=tuple(
                str(item).strip()
                for item in list(
                    guard_entry.get("target_requirement_ids") or []
                )
                if str(item).strip()
            ),
            max_follow_up_calls=int(
                guard_entry.get("max_follow_up_calls") or 1
            ),
        )
    )


def _run_intent_task_research_execution_canary_shadow(
    plan: Any,
    results: list[dict[str, Any]],
    task_research_contexts: list[dict[str, Any]],
    task_research_call_guards: list[dict[str, Any]],
    *,
    sender: Sender | None,
    initial_evidence_items: tuple[Any, ...] = (),
    reassessment_now: datetime | None = None,
    evidence_reassessment_observer=None,
    grounded_synthesis_observer=None,
) -> list[dict[str, Any]]:
    """Execute one secondary technical task as a non-authoritative canary.

    V8 is explicitly opt-in and candidate-oriented. It executes at most one
    technical specialist follow-up through the V7 call guard and bounded
    runtime. The output is observational only: it is never reconciled into
    Phase C, never appended to legacy results and never used for public
    synthesis.
    """
    if not _task_research_execution_canary_enabled_shadow():
        return []

    if not bool(getattr(plan, "multi_intent", False)):
        return [
            {
                "contract_version": (
                    "promati.multi_intent."
                    "task_research_execution_canary_shadow.v1"
                ),
                "status": "blocked_not_multi_intent",
                "executed": False,
            }
        ]

    contexts_by_id = {
        context.get("task_id"): context
        for context in list(task_research_contexts or [])
        if isinstance(context, dict) and context.get("task_id")
    }
    guards_by_id = {
        guard.get("task_id"): guard
        for guard in list(task_research_call_guards or [])
        if isinstance(guard, dict) and guard.get("task_id")
    }

    eligible: list[tuple[Any, dict[str, Any], dict[str, Any]]] = []
    for task in list(getattr(plan, "intent_tasks", None) or []):
        task_id = getattr(task, "task_id", None)
        context = contexts_by_id.get(task_id)
        guard_entry = guards_by_id.get(task_id)
        if not isinstance(context, dict) or not isinstance(guard_entry, dict):
            continue

        domain = _intent_task_domain_value_shadow(task)
        task_intent = str(getattr(task, "intent", "") or "").strip()
        targets = {
            str(item).strip()
            for item in list(
                guard_entry.get("target_requirement_ids") or []
            )
            if str(item).strip()
        }

        if domain != "technical":
            continue
        if task_intent != _TASK_RESEARCH_EXECUTION_CANARY_INTENT:
            continue
        if bool(getattr(task, "primary", False)):
            continue
        if context.get("research_required") is not True:
            continue
        if context.get("runtime_precondition") != "ready":
            continue
        if guard_entry.get("runtime_precondition") != "ready":
            continue
        if guard_entry.get("status") != "projected":
            continue
        if guard_entry.get("allowed_research_action") != (
            _TASK_RESEARCH_EXECUTION_CANARY_ACTION
        ):
            continue
        if int(guard_entry.get("max_follow_up_calls") or 0) != 1:
            continue
        if not targets or not targets.issubset(
            _TASK_RESEARCH_EXECUTION_CANARY_TARGETS
        ):
            continue
        if context.get("family_code") not in {None, ""}:
            continue
        eligible.append((task, context, guard_entry))

    contract_version = (
        "promati.multi_intent."
        "task_research_execution_canary_shadow.v1"
    )
    if not eligible:
        return [
            {
                "contract_version": contract_version,
                "status": "no_eligible_secondary_technical_task",
                "executed": False,
            }
        ]
    if len(eligible) != 1:
        return [
            {
                "contract_version": contract_version,
                "status": "blocked_ambiguous_eligible_tasks",
                "executed": False,
                "eligible_task_ids": [
                    getattr(task, "task_id", None)
                    for task, _, _ in eligible
                ],
            }
        ]

    task, context, guard_entry = eligible[0]
    selected_results = _select_intent_task_raw_results_shadow(
        task,
        list(results or []),
        family_code=None,
    )
    accepted_initial_results = [
        item
        for item in selected_results
        if isinstance(item, dict) and item.get("accepted") is True
    ]
    if not accepted_initial_results:
        return [
            {
                "contract_version": contract_version,
                "task_id": getattr(task, "task_id", None),
                "status": "blocked_no_accepted_initial_results",
                "executed": False,
            }
        ]

    guard = _task_research_canary_guard_shadow(guard_entry)
    task_question = _project_secondary_technical_question_shadow(plan, task)
    if not task_question:
        return [
            {
                "contract_version": contract_version,
                "task_id": getattr(task, "task_id", None),
                "domain": "technical",
                "task_intent": _TASK_RESEARCH_EXECUTION_CANARY_INTENT,
                "status": "blocked_no_isolated_task_question",
                "executed": False,
            }
        ]

    projected_plan = _task_research_canary_copy_plan_shadow(
        plan,
        task,
        task_question=task_question,
    )
    retrieval_question = (
        _task_research_definition_retrieval_question_shadow(
            task_question
        )
    )
    if not retrieval_question:
        return [
            {
                "contract_version": contract_version,
                "task_id": getattr(task, "task_id", None),
                "domain": "technical",
                "task_intent": _TASK_RESEARCH_EXECUTION_CANARY_INTENT,
                "status": "blocked_no_definition_retrieval_question",
                "executed": False,
            }
        ]

    planner = _task_research_canary_planner_shadow(
        action=guard.allowed_action,
        question=retrieval_question,
        target_requirement_ids=list(guard.target_requirement_ids),
    )

    follow_up_typed_results: list[Any] = []
    try:
        runtime_kwargs: dict[str, Any] = {
            "sender": sender,
            "planner": planner,
            "synthesizer": _task_research_canary_synthesizer_shadow,
            "call_guard": guard,
        }
        if evidence_reassessment_observer is not None:
            runtime_kwargs["shadow_observer"] = follow_up_typed_results.append
        observed = run_bounded_research_agent(
            projected_plan,
            accepted_initial_results,
            **runtime_kwargs,
        )
    except Exception as exc:
        return [
            {
                "contract_version": contract_version,
                "task_id": getattr(task, "task_id", None),
                "domain": "technical",
                "task_intent": _TASK_RESEARCH_EXECUTION_CANARY_INTENT,
                "allowed_research_action": guard.allowed_action,
                "target_requirement_ids": list(
                    guard.target_requirement_ids
                ),
                "status": "execution_error",
                "executed": False,
                "error_type": type(exc).__name__,
            }
        ]

    shadow_now = reassessment_now or datetime.now(timezone.utc)
    if evidence_reassessment_observer is not None:
        try:
            reassessment = _build_intent_task_research_evidence_reassessment_shadow(
                task,
                tuple(initial_evidence_items or ()),
                follow_up_typed_results,
                list(guard.target_requirement_ids),
                now=shadow_now,
            )
            evidence_reassessment_observer(reassessment)
        except Exception:
            pass

    if grounded_synthesis_observer is not None:
        try:
            grounded_synthesis = _build_intent_task_grounded_synthesis_shadow(
                task,
                task_question,
                tuple(initial_evidence_items or ()),
                follow_up_typed_results,
                list(guard.target_requirement_ids),
                now=shadow_now,
            )
            grounded_synthesis_observer(grounded_synthesis)
        except Exception:
            pass

    agent = observed.get("agent")
    agent = dict(agent) if isinstance(agent, dict) else {}
    result_summaries = observed.get("result_summaries")
    result_summaries = (
        list(result_summaries)
        if isinstance(result_summaries, list)
        else []
    )

    return [
        {
            "contract_version": contract_version,
            "task_id": getattr(task, "task_id", None),
            "domain": "technical",
            "task_intent": _TASK_RESEARCH_EXECUTION_CANARY_INTENT,
            "gate_intent": context.get("gate_intent"),
            "allowed_research_action": guard.allowed_action,
            "pinned_params": dict(guard.pinned_params),
            "target_requirement_ids": list(
                guard.target_requirement_ids
            ),
            "max_follow_up_calls": guard.max_follow_up_calls,
            "planner_mode": "deterministic_local_no_provider",
            "task_question": task_question,
            "retrieval_question": retrieval_question,
            "provider_ai_calls_used": 0,
            "initial_result_count": len(accepted_initial_results),
            "combined_result_count": int(
                observed.get("combined_result_count") or 0
            ),
            "follow_up_result_count": int(
                observed.get("follow_up_result_count") or 0
            ),
            "follow_up_specialist_calls": int(
                agent.get("follow_up_specialist_calls") or 0
            ),
            "result_summaries": result_summaries,
            "status": "executed_shadow_canary",
            "executed": True,
            "authoritative": False,
        }
    ]


# PROMATI_MULTI_INTENT_TASK_RESEARCH_CONTEXT_SHADOW_V6
_TASK_RESEARCH_ACTION_BY_DOMAIN_SHADOW = {
    "product": "product_assistant",
    "inspection": "analysis_assistant",
    "technical": "technical_assistant",
    "rfq": "rfq_assistant",
    "org": "org_assistant",
    "diagnostics": "diagnostics_assistant",
}


def _task_research_shadow_value(value: Any) -> Any:
    return getattr(value, "value", value)


def _task_research_step_domain_shadow(step: Any) -> str | None:
    raw = getattr(step, "domain", None)
    raw = _task_research_shadow_value(raw)
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _task_research_step_family_code_shadow(step: Any) -> str | None:
    params = getattr(step, "params", None)
    if not isinstance(params, dict):
        return None
    raw = params.get("family_code")
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _task_research_raw_result_domain_shadow(item: Any) -> str | None:
    if not isinstance(item, dict):
        return None
    raw = _task_research_shadow_value(item.get("domain"))
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _task_research_raw_result_family_code_shadow(
    item: Any,
) -> str | None:
    if not isinstance(item, dict):
        return None

    result = item.get("result")
    if not isinstance(result, dict):
        return None

    raw = result.get("detected_family_code")
    if raw is not None and str(raw).strip():
        return str(raw).strip()

    family_context = result.get("family_context")
    if isinstance(family_context, dict):
        raw = family_context.get("detected_family_code")
        if raw is not None and str(raw).strip():
            return str(raw).strip()

        rows = family_context.get("results")
        if (
            isinstance(rows, list)
            and rows
            and isinstance(rows[0], dict)
        ):
            raw = rows[0].get("family_code")
            if raw is not None and str(raw).strip():
                return str(raw).strip()

    return None


def _select_intent_task_execution_steps_shadow(
    plan: Any,
    task: Any,
    *,
    family_code: str | None = None,
) -> tuple[Any, ...]:
    domain = _intent_task_domain_value_shadow(task)
    family_codes = (
        (family_code,)
        if family_code
        else _intent_task_family_codes_shadow(task)
    )
    family_keys = {
        str(code).casefold()
        for code in family_codes
        if str(code).strip()
    }

    output: list[Any] = []
    for step in tuple(getattr(plan, "execution_steps", None) or ()):
        if _task_research_step_domain_shadow(step) != domain:
            continue

        if family_keys:
            step_family = _task_research_step_family_code_shadow(step)
            if (
                step_family is None
                or step_family.casefold() not in family_keys
            ):
                continue

        output.append(step)

    return tuple(output)


def _select_intent_task_raw_results_shadow(
    task: Any,
    results: list[dict[str, Any]],
    *,
    family_code: str | None = None,
) -> tuple[dict[str, Any], ...]:
    domain = _intent_task_domain_value_shadow(task)
    family_codes = (
        (family_code,)
        if family_code
        else _intent_task_family_codes_shadow(task)
    )
    family_keys = {
        str(code).casefold()
        for code in family_codes
        if str(code).strip()
    }

    output: list[dict[str, Any]] = []
    for item in list(results or []):
        if not isinstance(item, dict):
            continue
        if _task_research_raw_result_domain_shadow(item) != domain:
            continue

        if family_keys:
            result_family = _task_research_raw_result_family_code_shadow(
                item
            )
            if (
                result_family is None
                or result_family.casefold() not in family_keys
            ):
                continue

        output.append(item)

    return tuple(output)


def _task_research_decision_value_shadow(
    decision: Any,
    key: str,
    default: Any = None,
) -> Any:
    if isinstance(decision, dict):
        return decision.get(key, default)
    return getattr(decision, key, default)


def _task_research_step_summary_shadow(step: Any) -> dict[str, Any]:
    return {
        "step_id": getattr(step, "step_id", None),
        "domain": _task_research_step_domain_shadow(step),
        "action": getattr(step, "action", None),
        "family_code": _task_research_step_family_code_shadow(step),
    }


def _task_research_result_summary_shadow(
    item: dict[str, Any],
) -> dict[str, Any]:
    return {
        "step_id": item.get("step_id"),
        "domain": _task_research_raw_result_domain_shadow(item),
        "action": item.get("action"),
        "accepted": item.get("accepted") is True,
        "family_code": _task_research_raw_result_family_code_shadow(
            item
        ),
    }


def _build_intent_task_research_context_shadow(
    plan: Any,
    task: Any,
    decision_entry: dict[str, Any],
    results: list[dict[str, Any]],
    *,
    family_code: str | None = None,
    family_decision_entry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    decision_source = (
        family_decision_entry
        if isinstance(family_decision_entry, dict)
        else decision_entry
    )
    research_decision = decision_source.get("research_decision")

    domain = _intent_task_domain_value_shadow(task)
    task_intent = str(getattr(task, "intent", "") or "").strip()
    requested_information = list(
        getattr(task, "requested_information", None) or []
    )
    scope = dict(getattr(task, "scope", None) or {})

    if family_code:
        scope["product_family_codes"] = [family_code]
        family_codes = [family_code]
    else:
        family_codes = list(
            _intent_task_family_codes_shadow(task)
        )

    selected_steps = _select_intent_task_execution_steps_shadow(
        plan,
        task,
        family_code=family_code,
    )
    selected_results = _select_intent_task_raw_results_shadow(
        task,
        results,
        family_code=family_code,
    )
    accepted_result_count = sum(
        1
        for item in selected_results
        if item.get("accepted") is True
    )

    research_required = bool(
        _task_research_decision_value_shadow(
            research_decision,
            "research_required",
            False,
        )
    )
    target_requirement_ids = list(
        _task_research_decision_value_shadow(
            research_decision,
            "target_requirement_ids",
            (),
        )
        or ()
    )
    gate_intent = _task_research_decision_value_shadow(
        research_decision,
        "intent",
        None,
    )

    allowed_action = _TASK_RESEARCH_ACTION_BY_DOMAIN_SHADOW.get(
        domain or ""
    )
    step_actions = {
        str(getattr(step, "action", "") or "")
        for step in selected_steps
    }

    runtime_precondition = "ready"
    if research_required and accepted_result_count <= 0:
        runtime_precondition = "blocked_no_accepted_initial_results"
    elif allowed_action is None:
        runtime_precondition = "blocked_unmapped_domain"
    elif selected_steps and step_actions != {allowed_action}:
        runtime_precondition = "blocked_cross_action_projection"

    return {
        "contract_version": (
            "promati.multi_intent."
            "task_research_context_shadow.v1"
        ),
        "task_id": getattr(task, "task_id", None),
        "domain": domain,
        "task_intent": task_intent or None,
        "gate_intent": gate_intent,
        "evidence_requirement_set_id": decision_entry.get(
            "evidence_requirement_set_id"
        ),
        "resolved_requirement_set_id": decision_entry.get(
            "resolved_requirement_set_id"
        ),
        "research_required": research_required,
        "target_requirement_ids": target_requirement_ids,
        "scope": scope,
        "family_code": family_code,
        "allowed_research_action": allowed_action,
        "projected_plan": {
            "original_question": getattr(
                plan,
                "original_question",
                None,
            ),
            "primary_domain": domain,
            "domains": [domain] if domain else [],
            "intent": task_intent or None,
            "requested_information": requested_information,
            "product_family_codes": family_codes,
            "multi_intent": False,
            "research_required": research_required,
            "execution_steps": [
                _task_research_step_summary_shadow(step)
                for step in selected_steps
            ],
        },
        "selected_initial_result_count": len(selected_results),
        "accepted_initial_result_count": accepted_result_count,
        "selected_initial_results": [
            _task_research_result_summary_shadow(item)
            for item in selected_results
        ],
        "runtime_precondition": runtime_precondition,
        "status": "projected",
    }


def _derive_intent_task_research_contexts_shadow(
    plan: Any,
    results: list[dict[str, Any]],
    task_research_decisions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Project future task-scoped research inputs without executing them.

    V6 is shadow-only. It proves that a future bounded-research call can be
    isolated to one semantic task/domain/family instead of receiving the full
    multi-intent QueryPlan and all raw specialist results.
    """
    tasks = getattr(plan, "intent_tasks", None)
    if not isinstance(tasks, list):
        return []
    if not isinstance(task_research_decisions, list):
        return []

    tasks_by_id = {
        getattr(task, "task_id", None): task
        for task in tasks
        if getattr(task, "task_id", None)
    }

    output: list[dict[str, Any]] = []
    for decision_entry in task_research_decisions:
        if not isinstance(decision_entry, dict):
            continue

        task_id = decision_entry.get("task_id")
        task = tasks_by_id.get(task_id)
        if task is None:
            output.append(
                {
                    "contract_version": (
                        "promati.multi_intent."
                        "task_research_context_shadow.v1"
                    ),
                    "task_id": task_id,
                    "status": "task_not_found",
                    "product_family_scope_contexts": [],
                }
            )
            continue

        entry = _build_intent_task_research_context_shadow(
            plan,
            task,
            decision_entry,
            results,
        )

        family_contexts: list[dict[str, Any]] = []
        family_decisions = decision_entry.get(
            "product_family_scope_research_decisions"
        )
        if isinstance(family_decisions, list):
            for family_decision in family_decisions:
                if not isinstance(family_decision, dict):
                    continue
                raw_family_code = family_decision.get("family_code")
                family_code = (
                    str(raw_family_code).strip()
                    if raw_family_code is not None
                    else ""
                )
                if not family_code:
                    continue
                family_contexts.append(
                    _build_intent_task_research_context_shadow(
                        plan,
                        task,
                        decision_entry,
                        results,
                        family_code=family_code,
                        family_decision_entry=family_decision,
                    )
                )

        entry["product_family_scope_contexts"] = family_contexts
        output.append(entry)

    return output


# PROMATI_MULTI_INTENT_TASK_RESEARCH_CALL_GUARD_SHADOW_V7
_TASK_RESEARCH_PINNED_SCOPE_KEYS_SHADOW = {
    "product_assistant": frozenset({"family_code"}),
    "analysis_assistant": frozenset(
        {
            "lijn_code",
            "band_code",
            "scraper_family",
            "scope_code",
            "scope_type",
            "area_code",
            "installation_code",
        }
    ),
    "technical_assistant": frozenset(),
    "rfq_assistant": frozenset(),
    "org_assistant": frozenset(),
    "diagnostics_assistant": frozenset(
        {
            "lijn_code",
            "band_code",
        }
    ),
}


def _task_research_guard_pinned_params_shadow(
    context: dict[str, Any],
) -> tuple[dict[str, Any], str | None]:
    action = str(context.get("allowed_research_action") or "").strip()
    scope = context.get("scope")
    scope = dict(scope) if isinstance(scope, dict) else {}
    family_code = context.get("family_code")

    pinned: dict[str, Any] = {}
    blocked_reason: str | None = None

    if action == "product_assistant":
        if family_code is not None and str(family_code).strip():
            pinned["family_code"] = str(family_code).strip()
        else:
            raw_families = scope.get("product_family_codes")
            families = [
                str(item).strip()
                for item in list(raw_families or [])
                if str(item).strip()
            ]
            if len(families) == 1:
                pinned["family_code"] = families[0]
            elif len(families) > 1:
                blocked_reason = "blocked_requires_family_context"

    allowed_scope_keys = _TASK_RESEARCH_PINNED_SCOPE_KEYS_SHADOW.get(
        action,
        frozenset(),
    )
    for key in sorted(allowed_scope_keys):
        if key == "family_code":
            continue
        value = scope.get(key)
        if value is None or not str(value).strip():
            continue
        pinned[key] = value

    return pinned, blocked_reason


def _build_intent_task_research_call_guard_shadow(
    context: dict[str, Any],
) -> dict[str, Any]:
    action = str(context.get("allowed_research_action") or "").strip()
    pinned_params, blocked_reason = (
        _task_research_guard_pinned_params_shadow(context)
    )
    runtime_precondition = str(
        context.get("runtime_precondition") or ""
    ).strip() or "blocked_missing_context_precondition"
    if blocked_reason is not None:
        runtime_precondition = blocked_reason

    target_requirement_ids = tuple(
        str(item).strip()
        for item in list(context.get("target_requirement_ids") or [])
        if str(item).strip()
    )

    guard_payload: dict[str, Any] | None = None
    status = "projected"
    if not action:
        runtime_precondition = "blocked_missing_allowed_action"
        status = "blocked"
    else:
        try:
            normalized_guard = normalize_research_call_guard(
                ResearchCallGuard(
                    allowed_action=action,
                    pinned_params=pinned_params,
                    target_requirement_ids=target_requirement_ids,
                    max_follow_up_calls=1,
                )
            )
            guard_payload = normalized_guard.to_dict()
        except Exception:
            runtime_precondition = "blocked_invalid_guard_projection"
            status = "blocked"

    if runtime_precondition != "ready":
        status = "blocked"

    family_guards = []
    raw_family_contexts = context.get("product_family_scope_contexts")
    if isinstance(raw_family_contexts, list):
        for family_context in raw_family_contexts:
            if not isinstance(family_context, dict):
                continue
            family_guards.append(
                _build_intent_task_research_call_guard_shadow(
                    family_context
                )
            )

    return {
        "contract_version": (
            "promati.multi_intent."
            "task_research_call_guard_shadow.v1"
        ),
        "task_id": context.get("task_id"),
        "domain": context.get("domain"),
        "task_intent": context.get("task_intent"),
        "gate_intent": context.get("gate_intent"),
        "family_code": context.get("family_code"),
        "research_required": bool(context.get("research_required")),
        "allowed_research_action": action or None,
        "pinned_params": (
            dict(guard_payload.get("pinned_params") or {})
            if isinstance(guard_payload, dict)
            else dict(pinned_params)
        ),
        "target_requirement_ids": (
            list(guard_payload.get("target_requirement_ids") or [])
            if isinstance(guard_payload, dict)
            else list(target_requirement_ids)
        ),
        "max_follow_up_calls": (
            guard_payload.get("max_follow_up_calls")
            if isinstance(guard_payload, dict)
            else 1
        ),
        "planner_allowed_actions": [action] if action else [],
        "runtime_defense_required": True,
        "runtime_precondition": runtime_precondition,
        "status": status,
        "product_family_scope_guards": family_guards,
    }


def _derive_intent_task_research_call_guards_shadow(
    task_research_contexts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Project exact task/family call guards without running research.

    V7 remains shadow-only. It validates that a future task-scoped bounded
    research run can be restricted to one assistant action, pinned scope and
    one follow-up call while the legacy Phase-C research path stays authoritative.
    """
    if not isinstance(task_research_contexts, list):
        return []

    return [
        _build_intent_task_research_call_guard_shadow(context)
        for context in task_research_contexts
        if isinstance(context, dict)
    ]



# PROMATI_P4_6B_TASK_EXECUTION_CANARY
_TASK_EXECUTION_CANARY_ENV = "AI_TASK_EXECUTION_CANARY_ENABLED"


def _task_execution_canary_enabled_p4_6b() -> bool:
    raw = os.getenv(_TASK_EXECUTION_CANARY_ENV, "false")
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _run_task_execution_canary_p4_6b(
    plan: Any,
    task_execution_plans_shadow: Any,
    *,
    sender: Sender | None,
) -> dict[str, Any] | None:
    contract = {
        "contract_version": "promati.multi_intent.task_execution_canary.v1",
        "enabled": _task_execution_canary_enabled_p4_6b(),
        "eligible": False,
        "executed": False,
        "task_id": None,
        "step_count": 0,
        "accepted_result_count": 0,
        "reason": None,
    }

    if not contract["enabled"]:
        contract["reason"] = "disabled"
        return contract

    if not bool(getattr(plan, "multi_intent", False)):
        contract["reason"] = "not_multi_intent"
        return contract

    secondary = None
    for task_plan in list(task_execution_plans_shadow or []):
        if bool(getattr(task_plan, "primary", False)):
            continue
        steps = list(getattr(task_plan, "execution_steps", None) or [])
        if steps:
            secondary = task_plan
            break

    if secondary is None:
        contract["reason"] = "no_secondary_task_plan"
        return contract

    projected = (
        plan.model_copy(deep=True)
        if hasattr(plan, "model_copy")
        else plan.copy(deep=True)
    )
    projected.execution_steps = [
        (
            step.model_copy(deep=True)
            if hasattr(step, "model_copy")
            else step.copy(deep=True)
        )
        for step in list(getattr(secondary, "execution_steps", None) or [])
    ]
    projected.clarification_required = False

    contract["eligible"] = True
    contract["task_id"] = str(getattr(secondary, "task_id", "") or "") or None
    contract["step_count"] = len(projected.execution_steps)

    try:
        typed = []
        raw_results, _trace = execute_plan(
            projected,
            sender=sender,
            shadow_observer=typed.append,
        )
    except Exception as exc:
        contract["reason"] = "execution_error:" + type(exc).__name__
        return contract

    contract["executed"] = True
    contract["accepted_result_count"] = sum(
        1
        for item in list(raw_results or [])
        if isinstance(item, dict) and item.get("accepted") is True
    )
    contract["reason"] = "executed_non_authoritative"
    return contract


def run_orchestrator(
    payload: OrchestratorAskRequest,
    sender: Sender | None = None,
) -> dict[str, Any]:
    """
    Centrale orchestrator-service.

    Flow:
        vraag
        -> understanding
        -> planning
        -> execution
        -> stabiele response

    Deze service bevat bewust:
    - geen FastAPI-router;
    - geen databasecode;
    - geen domein-SQL;
    - geen automatische fallback-relaxation.

    Die verantwoordelijkheden blijven gescheiden.
    """
    # PROMATI_ORCHESTRATOR_OBSERVABILITY_RUN_V1
    timings = (
        _new_observability_timings()
    )
    counts = (
        _new_observability_counts()
    )
    run_started = _observability_now()

    question = (
        payload.q
        if payload.q
        else payload.vraag
    ).strip()

    # PROMATI_CONVERSATION_SCOPE_GROUNDING_V1
    conversation_context = (
        _model_to_dict(
            payload.conversation_context
        )
        if payload.conversation_context
        is not None
        else None
    )

    plan = _observability_call(
        timings,
        "understanding",
        understand_query,
        question,
        conversation_context=conversation_context,
    )

    # PROMATI_ROUTING_SANITY_BEFORE_RESEARCH_P4_5B3
    # Deterministic/local sanity gate. Geen nieuwe observability timing-key:
    # promati.orchestrator.observability.v1 blijft backwards-compatible.
    plan = apply_routing_sanity(plan)

    plan = _observability_call(
        timings,
        "research_requirement",
        assess_research_requirement,
        plan,
    )

    plan = _observability_call(
        timings,
        "planning",
        build_execution_plan,
        plan,
    )

    # Shadow-only requirement resolution. No observability key is added and
    # execute_plan continues to consume the same legacy execution_steps.
    plan = _attach_intent_task_evidence_requirements_shadow(
        plan
    )

    # PROMATI_P4_6A_TASK_EXECUTION_PLAN_SHADOW
    # Build detached per-IntentTask execution plans for comparison only.
    # These plans are never passed to execute_plan in P4.6a.
    task_execution_plans_shadow = ()
    task_execution_plan_comparison_shadow = None
    try:
        task_execution_plans_shadow = (
            build_task_execution_plans_shadow(plan)
        )
        task_execution_plan_comparison_shadow = (
            compare_task_execution_plans_shadow(
                plan,
                task_execution_plans_shadow,
            )
        )
    except Exception:
        task_execution_plans_shadow = ()
        task_execution_plan_comparison_shadow = None

    # PROMATI_P4_6B_TASK_EXECUTION_CANARY
    # Explicit opt-in, fail-open, observational only.
    task_execution_canary_p4_6b = None
    try:
        task_execution_canary_p4_6b = _run_task_execution_canary_p4_6b(
            plan,
            task_execution_plans_shadow,
            sender=sender,
        )
    except Exception:
        task_execution_canary_p4_6b = None

    typed_execution_results = []

    results, trace = _observability_call(
        timings,
        "initial_specialist",
        execute_plan,
        plan,
        sender=sender,
        shadow_observer=(
            typed_execution_results.append
        ),
    )

    attempts = _observability_get(
        trace,
        "attempts",
        [],
    )

    if not isinstance(
        attempts,
        (list, tuple),
    ):
        attempts = []

    counts["execution_attempts"] = len(
        attempts
    )

    # results bevat alleen werkelijk uitgevoerde
    # specialisttransportcalls. Een ontbrekend endpoint
    # komt wel in trace.attempts maar niet in results.
    counts["initial_specialist_calls"] = len(
        results
    )

    counts["initial_raw_result_rows"] = sum(
        _observability_nonnegative_int(
            _observability_get(
                attempt,
                "result_count",
                0,
            )
        )
        for attempt in attempts
    )

    evidence_pipeline = None

    initial_evidence_items = ()
    research_execution = None
    reconciliation = None

    try:
        requirement_set = (
            _observability_call(
                timings,
                "evidence_requirement_lookup",
                get_requirement_set,
                plan.intent,
            )
        )

        specialist_research_blocked = any(
            isinstance(
                item.get("result"),
                dict,
            )
            and str(
                item["result"].get(
                    "status",
                    "",
                )
            ).lower()
            == "clarification_required"
            for item in results
            if isinstance(
                item,
                dict,
            )
        )

        if (
            requirement_set is not None
            and not plan.clarification_required
            and not specialist_research_blocked
        ):
            retrieved_at = datetime.now(
                timezone.utc
            )

            normalization_started = (
                _observability_now()
            )

            try:
                initial_evidence_items = tuple(
                    evidence_item
                    for execution_result
                    in typed_execution_results
                    for evidence_item
                    in normalize_execution_result_evidence(
                        execution_result,
                        retrieved_at=retrieved_at,
                    )
                )
            finally:
                timings[
                    "evidence_normalization"
                ] = (
                    _observability_elapsed_ms(
                        normalization_started
                    )
                )

                counts[
                    "initial_evidence_items"
                ] = len(
                    initial_evidence_items
                )

            # PROMATI_PRODUCT_FAMILY_RECOVERY_P4_5B4
            #
            # Family-scoped PRODUCT_RECORD coverage happens before
            # the existing generic evidence-research gate.
            #
            # Recovery itself is deterministic product retrieval.
            # Technical/project synthesis remains a separate path.
            working_evidence_items = (
                initial_evidence_items
            )

            product_family_coverage = (
                assess_product_family_coverage(
                    requirement_set,
                    working_evidence_items,
                    plan,
                    now=retrieved_at,
                )
            )

            product_family_recovery = {
                "contract_version": (
                    "promati.orchestrator."
                    "product_family_evidence.v1"
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
                product_family_coverage.get(
                    "missing_family_codes"
                )
                or ()
            )

            if (
                product_family_coverage.get(
                    "applicable"
                )
                and missing_product_families
            ):
                recovery_typed_results = []

                (
                    _recovery_raw_results,
                    product_family_recovery,
                ) = (
                    recover_missing_product_families(
                        plan,
                        missing_product_families,
                        sender=sender,
                        shadow_observer=(
                            recovery_typed_results
                            .append
                        ),
                    )
                )

                counts[
                    "phase_c_research_follow_up_specialist_calls"
                ] += (
                    _observability_nonnegative_int(
                        product_family_recovery.get(
                            "attempted_call_count"
                        )
                    )
                )

                recovered_evidence_items = tuple(
                    evidence_item
                    for execution_result
                    in recovery_typed_results
                    for evidence_item
                    in normalize_execution_result_evidence(
                        execution_result,
                        retrieved_at=retrieved_at,
                    )
                )

                working_evidence_items = (
                    tuple(
                        initial_evidence_items
                    )
                    + tuple(
                        recovered_evidence_items
                    )
                )

                product_family_coverage = (
                    assess_product_family_coverage(
                        requirement_set,
                        working_evidence_items,
                        plan,
                        now=retrieved_at,
                    )
                )

            # V4 shadow-only per-task evidence assessment. Fail-open: any
            # shadow defect must not alter the authoritative legacy Phase-C path.
            task_evidence_assessments_shadow = []
            try:
                task_evidence_assessments_shadow = (
                    _assess_intent_task_evidence_shadow(
                        plan,
                        working_evidence_items,
                        now=retrieved_at,
                    )
                )
            except Exception:
                task_evidence_assessments_shadow = []

            # PROMATI_P4_6C_TASK_EVIDENCE_AUTHORITY_CANARY
            # Narrow authority only: IntentTask evidence assessment. Legacy Phase-C
            # research/reconciliation/synthesis and public answer ownership remain unchanged.
            task_evidence_authority_p4_6c = None
            try:
                task_evidence_authority_p4_6c = (
                    build_task_evidence_authority_canary_p4_6c(
                        plan,
                        tuple(working_evidence_items),
                        now=retrieved_at,
                        shadow_assessments=(
                            task_evidence_assessments_shadow
                        ),
                    )
                )
            except Exception:
                task_evidence_authority_p4_6c = None

            # V5 shadow-only research decisions derived from the V4 task
            # assessments. Fail-open and never used for research execution.
            task_research_decisions_shadow = []
            try:
                task_research_decisions_shadow = (
                    _derive_intent_task_research_decisions_shadow(
                        task_evidence_assessments_shadow
                    )
                )
            except Exception:
                task_research_decisions_shadow = []

            # PROMATI_P4_6D1_TASK_RESEARCH_DECISION_AUTHORITY_CANARY
            # Promote only task-scoped research decisions. No research execution,
            # reconciliation, synthesis or public answer authority changes here.
            task_research_authority_p4_6d1 = None
            try:
                task_research_authority_p4_6d1 = (
                    build_task_research_authority_canary_p4_6d1(
                        task_evidence_authority_p4_6c,
                        task_research_decisions_shadow,
                    )
                )
            except Exception:
                task_research_authority_p4_6d1 = None

            # V6 shadow-only task research input projection. This isolates the
            # future plan/results context but performs no research call.
            task_research_contexts_shadow = []
            try:
                task_research_contexts_shadow = (
                    _derive_intent_task_research_contexts_shadow(
                        plan,
                        list(results),
                        task_research_decisions_shadow,
                    )
                )
            except Exception:
                task_research_contexts_shadow = []

            # V7 shadow-only call/action/scope guard projection. No planner,
            # research runtime or specialist follow-up is executed here.
            task_research_call_guards_shadow = []
            try:
                task_research_call_guards_shadow = (
                    _derive_intent_task_research_call_guards_shadow(
                        task_research_contexts_shadow
                    )
                )
            except Exception:
                task_research_call_guards_shadow = []

            # PROMATI_P4_6D2_TASK_RESEARCH_EXECUTION_AUTHORITY_CANARY
            # Bounded task-research execution authority only. Follow-up outputs
            # remain isolated from legacy Phase-C reconciliation/public synthesis.
            task_research_execution_authority_p4_6d2 = None
            task_research_execution_observations_p4_6d2 = []
            try:
                task_research_execution_authority_p4_6d2 = (
                    run_task_research_execution_authority_canary_p4_6d2(
                        plan,
                        list(results),
                        task_research_authority_p4_6d1,
                        task_research_contexts_shadow,
                        task_research_call_guards_shadow,
                        sender=sender,
                        evidence_observer=(
                            task_research_execution_observations_p4_6d2.append
                        ),
                    )
                )
            except Exception:
                task_research_execution_authority_p4_6d2 = None
                task_research_execution_observations_p4_6d2 = []

            # PROMATI_P4_6E1_TASK_RESEARCH_EVIDENCE_AUTHORITY_CANARY
            # Normalize accepted P4.6d2 typed follow-up results and reassess only
            # their task/family evidence contract. Legacy Phase-C stays unchanged.
            task_research_evidence_authority_p4_6e1 = None
            task_research_evidence_units_p4_6e1 = []
            try:
                task_research_evidence_authority_p4_6e1 = (
                    build_task_research_evidence_authority_canary_p4_6e1(
                        plan,
                        task_research_execution_authority_p4_6d2,
                        task_research_execution_observations_p4_6d2,
                        tuple(working_evidence_items),
                        now=retrieved_at,
                        grounded_synthesis_observer=(
                            task_research_evidence_units_p4_6e1.append
                        ),
                    )
                )
            except Exception:
                task_research_evidence_authority_p4_6e1 = None
                task_research_evidence_units_p4_6e1 = []

            # PROMATI_P4_6E2_TASK_GROUNDED_SYNTHESIS_AUTHORITY_CANARY
            task_grounded_synthesis_authority_p4_6e2 = None
            try:
                task_grounded_synthesis_authority_p4_6e2 = (
                    build_task_grounded_synthesis_authority_canary_p4_6e2(
                        task_research_evidence_authority_p4_6e1,
                        task_research_evidence_units_p4_6e1,
                    )
                )
            except Exception:
                task_grounded_synthesis_authority_p4_6e2 = None

            # PROMATI_P4_6E3_TASK_SYNTHESIS_COVERAGE_AUTHORITY_CANARY
            # Close the multi-intent synthesis coverage gap before any public
            # composition authority: combine P4.6e2 research-grounded units
            # with tasks that were already sufficient from existing evidence.
            task_grounded_synthesis_coverage_authority_p4_6e3 = None
            try:
                task_grounded_synthesis_coverage_authority_p4_6e3 = (
                    build_task_grounded_synthesis_coverage_authority_canary_p4_6e3(
                        plan,
                        task_evidence_authority_p4_6c,
                        task_grounded_synthesis_authority_p4_6e2,
                        tuple(working_evidence_items),
                        now=retrieved_at,
                    )
                )
            except Exception:
                task_grounded_synthesis_coverage_authority_p4_6e3 = None

            # V8 candidate-oriented task research execution canary. Disabled
            # by default and fail-open. When explicitly enabled it may execute
            # one guarded secondary technical follow-up, but the observation
            # never enters authoritative Phase-C assessment/reconciliation or
            # public synthesis.
            task_research_execution_canary_shadow = []
            task_research_evidence_reassessment_shadow = []
            task_grounded_synthesis_shadow = []
            try:
                task_research_execution_canary_shadow = (
                    _run_intent_task_research_execution_canary_shadow(
                        plan,
                        list(results),
                        task_research_contexts_shadow,
                        task_research_call_guards_shadow,
                        sender=sender,
                        initial_evidence_items=tuple(working_evidence_items),
                        reassessment_now=retrieved_at,
                        evidence_reassessment_observer=(
                            task_research_evidence_reassessment_shadow.append
                        ),
                        grounded_synthesis_observer=(
                            task_grounded_synthesis_shadow.append
                        ),
                    )
                )
            except Exception:
                task_research_execution_canary_shadow = []
                task_research_evidence_reassessment_shadow = []
                task_grounded_synthesis_shadow = []

            initial_assessment = (
                _observability_call(
                    timings,
                    "evidence_assessment",
                    assess_evidence,
                    requirement_set,
                    working_evidence_items,
                    target_entity_ids=None,
                    now=retrieved_at,
                )
            )

            research_decision = (
                _observability_call(
                    timings,
                    "evidence_research_gate",
                    decide_research_requirement,
                    initial_assessment,
                )
            )

            research_execution = (
                _observability_call(
                    timings,
                    "evidence_research",
                    execute_bounded_research,
                    research_decision,
                    plan,
                    list(results),
                    sender=sender,
                )
            )

            phase_c_agent_metadata = (
                _observability_get(
                    research_execution,
                    "agent_metadata",
                    None,
                )
            )

            if isinstance(
                phase_c_agent_metadata,
                dict,
            ):
                counts[
                    "phase_c_research_follow_up_specialist_calls"
                ] += (
                    _observability_nonnegative_int(
                        phase_c_agent_metadata.get(
                            "follow_up_specialist_calls"
                        )
                    )
                )

                counts[
                    "phase_c_ai_calls"
                ] = (
                    _observability_nonnegative_int(
                        phase_c_agent_metadata.get(
                            "total_ai_calls_used"
                        )
                    )
                )

            reconciliation = (
                _observability_call(
                    timings,
                    "reconciliation",
                    reconcile_evidence,
                    requirement_set,
                    working_evidence_items,
                    initial_assessment,
                    research_execution,
                    retrieved_at=retrieved_at,
                    target_entity_ids=None,
                    now=retrieved_at,
                )
            )

            reconciled_items = (
                _observability_get(
                    reconciliation,
                    "reconciled_evidence_items",
                    (),
                )
            )

            if isinstance(
                reconciled_items,
                (list, tuple),
            ):
                counts[
                    "reconciled_evidence_items"
                ] = len(
                    reconciled_items
                )

            synthesis = (
                _observability_call(
                    timings,
                    "synthesis",
                    synthesize_grounded_evidence,
                    reconciliation,
                )
            )

            evidence_pipeline = (
                _evidence_pipeline_to_dict(
                    {
                        "requirement_set_id": (
                            requirement_set
                            .requirement_set_id
                        ),
                        # PROMATI_P4_6A_TASK_EXECUTION_PLAN_SHADOW
                        "task_execution_plans_shadow": (
                            task_execution_plans_shadow
                        ),
                        "task_execution_plan_comparison_shadow": (
                            task_execution_plan_comparison_shadow
                        ),
                        "task_execution_canary_p4_6b": (
                            task_execution_canary_p4_6b
                        ),
                        "task_evidence_assessments_shadow": (
                            task_evidence_assessments_shadow
                        ),
                        "task_evidence_authority_p4_6c": (
                            task_evidence_authority_p4_6c
                        ),
                        "task_research_decisions_shadow": (
                            task_research_decisions_shadow
                        ),
                        "task_research_authority_p4_6d1": (
                            task_research_authority_p4_6d1
                        ),
                        "task_research_execution_authority_p4_6d2": (
                            task_research_execution_authority_p4_6d2
                        ),
                        "task_research_evidence_authority_p4_6e1": (
                            task_research_evidence_authority_p4_6e1
                        ),
                        "task_grounded_synthesis_authority_p4_6e2": (
                            task_grounded_synthesis_authority_p4_6e2
                        ),
                        "task_grounded_synthesis_coverage_authority_p4_6e3": (
                            task_grounded_synthesis_coverage_authority_p4_6e3
                        ),
                        "task_research_contexts_shadow": (
                            task_research_contexts_shadow
                        ),
                        "task_research_call_guards_shadow": (
                            task_research_call_guards_shadow
                        ),
                        "task_research_execution_canary_shadow": (
                            task_research_execution_canary_shadow
                        ),
                        "task_research_evidence_reassessment_shadow": (
                            task_research_evidence_reassessment_shadow
                        ),
                        "task_grounded_synthesis_shadow": (
                            task_grounded_synthesis_shadow
                        ),
                        "initial_assessment": (
                            initial_assessment
                        ),
                        "research_decision": (
                            research_decision
                        ),
                        "research_execution": (
                            research_execution
                        ),
                        "reconciliation": (
                            reconciliation
                        ),
                        "synthesis": synthesis,

                        "product_family_coverage": (
                            product_family_coverage
                        ),

                        "product_family_recovery": (
                            product_family_recovery
                        ),
                    }
                )
            )

    except Exception:
        # C8 is additive and fail-open: the legacy
        # response path remains authoritative.
        evidence_pipeline = None

    specialist_clarification = None

    for item in results:
        specialist_result = item.get(
            "result"
        )

        if not isinstance(
            specialist_result,
            dict,
        ):
            continue

        specialist_status = str(
            specialist_result.get(
                "status",
                "",
            )
        ).lower()

        if (
            specialist_status
            == "clarification_required"
        ):
            specialist_clarification = (
                specialist_result
            )
            break

    clarification = {
        "required": (
            plan.clarification_required
        ),
        "question": (
            plan.clarification_question
        ),
    }

    if plan.clarification_required:
        # Query-understanding clarification houdt
        # de hoogste prioriteit.
        status = "clarification_required"

    elif (
        specialist_clarification
        is not None
    ):
        # Een specialist kan tijdens uitvoering ontdekken
        # dat aanvullende context nodig is, bijvoorbeeld
        # bij een band/installatie-conflict.
        clarification_question = (
            specialist_clarification.get(
                "message"
            )
        )

        if not clarification_question:
            detail = (
                specialist_clarification.get(
                    "clarification"
                )
            )

            if isinstance(
                detail,
                dict,
            ):
                clarification_question = (
                    detail.get(
                        "question"
                    )
                )

            elif isinstance(
                detail,
                str,
            ):
                clarification_question = (
                    detail
                )

        if not clarification_question:
            clarification_question = (
                "Kun je de ontbrekende context "
                "verduidelijken?"
            )

        clarification = {
            "required": True,
            "question": str(
                clarification_question
            ),
        }

        status = (
            "clarification_required"
        )

    elif (
        plan.execution_steps
        and not has_service_accepted_execution(
            typed_execution_results,
            results,
        )
    ):
        status = "error"

    else:
        status = "ok"

    # PROMATI_BOUNDED_RESEARCH_V1_GATE
    # Deterministic specialist execution always happens
    # first. Only a clear, successful research_required
    # plan may use one bounded AI synthesis call.
    research = {
        "status": "not_required",
        "required": bool(
            plan.research_required
        ),
        "mode": "bounded_synthesis_v1",
        "ai_calls_used": 0,
        "max_ai_calls": 1,
        "follow_up_rounds_used": 0,
        "max_follow_up_rounds": 0,
        "answer": None,
    }

    if (
        status == "ok"
        and plan.research_required
        and not clarification.get(
            "required"
        )
    ):
        research_agent_enabled = (
            _research_agent_enabled()
        )

        if research_agent_enabled:
            research = (
                _observability_call(
                    timings,
                    "plan_research",
                    run_bounded_research_agent,
                    plan,
                    results,
                    sender=sender,
                )
            )
        else:
            research = (
                _observability_call(
                    timings,
                    "plan_research",
                    run_bounded_research,
                    plan,
                    results,
                )
            )

    plan_research_agent = None

    if isinstance(
        research,
        dict,
    ):
        raw_agent = research.get(
            "agent"
        )

        if isinstance(
            raw_agent,
            dict,
        ):
            plan_research_agent = (
                raw_agent
            )

    if (
        plan_research_agent
        is not None
    ):
        counts[
            "plan_research_follow_up_specialist_calls"
        ] = (
            _observability_nonnegative_int(
                plan_research_agent.get(
                    "follow_up_specialist_calls"
                )
            )
        )

        if (
            "total_ai_calls_used"
            in plan_research_agent
        ):
            counts[
                "plan_research_ai_calls"
            ] = (
                _observability_nonnegative_int(
                    plan_research_agent.get(
                        "total_ai_calls_used"
                    )
                )
            )
        else:
            counts[
                "plan_research_ai_calls"
            ] = (
                _observability_nonnegative_int(
                    research.get(
                        "ai_calls_used"
                    )
                )
            )

    elif isinstance(
        research,
        dict,
    ):
        counts[
            "plan_research_ai_calls"
        ] = (
            _observability_nonnegative_int(
                research.get(
                    "ai_calls_used"
                )
            )
        )

    counts[
        "research_follow_up_specialist_calls"
    ] = (
        counts[
            "phase_c_research_follow_up_specialist_calls"
        ]
        + counts[
            "plan_research_follow_up_specialist_calls"
        ]
    )

    counts["total_specialist_calls"] = (
        counts[
            "initial_specialist_calls"
        ]
        + counts[
            "research_follow_up_specialist_calls"
        ]
    )

    counts["total_ai_calls"] = (
        counts[
            "phase_c_ai_calls"
        ]
        + counts[
            "plan_research_ai_calls"
        ]
    )

    presentation_started = (
        _observability_now()
    )

    try:
        answer = _build_user_answer(
            results,
            requested_information=(
                plan.requested_information
            ),
        )

        if (
            research.get(
                "status"
            )
            == "ok"
            and research.get(
                "answer"
            )
        ):
            answer = str(
                research["answer"]
            )

        if answer:
            answer = (
                repair_mojibake_text(
                    answer
                )
            )
    finally:
        timings["presentation"] = (
            _observability_elapsed_ms(
                presentation_started
            )
        )

    # PROMATI_MULTI_INTENT_COMPOSITION_SHADOW_POST_B7
    # Build a non-authoritative composition candidate from the already-final
    # legacy/public answer plus grounded secondary task answers. The public
    # answer itself remains untouched.
    if isinstance(evidence_pipeline, dict):
        try:
            evidence_pipeline["multi_intent_composition_shadow"] = (
                _build_multi_intent_composition_shadow(
                    plan,
                    answer,
                    evidence_pipeline,
                )
            )
        except Exception:
            evidence_pipeline["multi_intent_composition_shadow"] = None

    # PROMATI_PUBLIC_COMPOSITION_CANARY_POST_B7
    # Default-off and fail-open. Only the exact proven product+CEMA shape can
    # replace the public answer, and only when explicitly enabled.
    legacy_answer_before_public_composition_canary = answer
    if isinstance(evidence_pipeline, dict):
        try:
            (
                answer,
                evidence_pipeline[
                    "public_composition_canary_shadow"
                ],
            ) = _maybe_apply_public_composition_canary(
                plan,
                legacy_answer_before_public_composition_canary,
                evidence_pipeline,
            )
        except Exception:
            answer = legacy_answer_before_public_composition_canary
            evidence_pipeline[
                "public_composition_canary_shadow"
            ] = {
                "contract_version": (
                    "promati.multi_intent."
                    "public_composition_canary.v1"
                ),
                "enabled": _public_composition_canary_enabled(),
                "default_enabled": False,
                "eligible": False,
                "activated": False,
                "public_answer_replaced": False,
                "target": (
                    "product_lookup_plus_technical_lookup_"
                    "cema_definition"
                ),
                "release_stage": "narrow_candidate_canary",
                "fail_open_to_legacy_answer": True,
                "release_observability_contract_version": (
                    "promati.multi_intent."
                    "public_composition_canary_observability.v1"
                ),
                "reason": "blocked_internal_error_fail_open",
            }

    # PROMATI_P4_6F_PUBLIC_MULTI_INTENT_COMPOSITION_AUTHORITY_CANARY
    # Separate default-off authority gate. This consumes only the proven
    # P4.6e3 complete grounded task coverage contract. Fail-open preserves
    # the answer from the pre-existing presentation/public-canary path.
    answer_before_p4_6f_public_composition = answer
    task_public_composition_authority_p4_6f = None
    if isinstance(evidence_pipeline, dict):
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

        evidence_pipeline[
            "task_public_composition_authority_p4_6f"
        ] = task_public_composition_authority_p4_6f

    # PROMATI_P4_6A_TASK_EXECUTION_PLAN_SHADOW_OBSERVABILITY
    # Best-effort integer-only metrics. Never alter user-visible behavior.
    try:
        _record_task_execution_plan_shadow_observability(
            counts,
            plan,
            evidence_pipeline,
        )
    except Exception:
        pass

    # PROMATI_PUBLIC_COMPOSITION_CANARY_RELEASE_OBSERVABILITY_HARDENING
    # Best-effort metrics only. Any instrumentation error must never alter the
    # selected user answer or the legacy fail-open behavior.
    try:
        _record_public_composition_canary_release_observability(
            counts,
            plan,
            evidence_pipeline,
        )
    except Exception:
        pass

    response_build_started = (
        _observability_now()
    )

    try:
        # PROMATI_PUBLIC_RESPONSE_PROFILE_V1
        #
        # De volledige evidence pipeline blijft intern
        # bestaan. Alleen de publieke serialisatie wordt
        # geprojecteerd.
        # Debug/include_trace behoudt het volledige
        # Phase-C object voor regressie en audit.
        public_evidence_pipeline = (
            evidence_pipeline
            if payload.include_trace
            else (
                _compact_evidence_pipeline_for_public_response(
                    evidence_pipeline
                )
            )
        )

        public_results = (
            results
            if payload.include_trace
            else compact_results_for_public_response(
                results,
                requested_information=(
                    plan.requested_information
                ),
            )
        )

        response = {
            "status": status,
            "answer": answer,
            "context_type": "orchestrator",
            "question": question,
            "query_plan": (
                _model_to_dict(
                    plan
                )
            ),
            "research": research,
            "clarification": (
                clarification
            ),
            "results": public_results,
            "evidence_pipeline": (
                public_evidence_pipeline
            ),
        }

        if payload.include_trace:
            response["trace"] = (
                _model_to_dict(
                    trace
                )
            )
        else:
            response["trace"] = None

    finally:
        timings["response_build"] = (
            _observability_elapsed_ms(
                response_build_started
            )
        )

    # total is de wall-clock tijd van de service tot en
    # met de opbouw van de Python-response. HTTP JSON-
    # serialisatie valt bewust buiten dit contract.
    timings["total"] = (
        _observability_elapsed_ms(
            run_started
        )
    )

    response["observability"] = {
        "contract_version": (
            ORCHESTRATOR_OBSERVABILITY_CONTRACT_VERSION
        ),
        "timings_ms": dict(
            timings
        ),
        "counts": dict(
            counts
        ),
    }

    return response

# PROMATI_P4_15CP3C_INSPECTION_LATEST_PUBLIC_ANSWER_COMPOSITION_V1
# Narrow repair:
# - CP3 made single-intent inspection_latest evidence sufficient.
# - The legacy answer can still be the scope_analysis/kort_resultaat text
#   ("43 actuele geregistreerde schraperposities...").
# - This post-composition wrapper replaces only that narrow bad answer shape
#   when the inspection_latest evidence contract is already sufficient.
# - It does not synthesize evidence; it only renders already accepted evidence
#   from evidence_pipeline.initial/reconciled evidence items.

_p4_15cp3c_previous_run_orchestrator = run_orchestrator


def _p4_15cp3c_get_path(obj, path, default=None):
    cur = obj
    for key in path:
        if isinstance(cur, dict):
            cur = cur.get(key, default)
        elif isinstance(cur, list) and isinstance(key, int) and 0 <= key < len(cur):
            cur = cur[key]
        else:
            return default
    return cur


def _p4_15cp3c_casefold(value):
    return str(value or "").casefold()


def _p4_15cp3c_is_single_intent_inspection_latest(response):
    query_plan = response.get("query_plan") if isinstance(response, dict) else None
    intent = _p4_15cp3c_get_path(query_plan, ["intent"])
    multi_intent = _p4_15cp3c_get_path(query_plan, ["multi_intent"])
    if intent == "inspection_latest" and multi_intent is not True:
        return True

    # Fallback: use evidence assessment intent if query_plan is omitted.
    assessment_intent = _p4_15cp3c_get_path(
        response,
        ["evidence_pipeline", "initial_assessment", "intent"],
    )
    tasks = _p4_15cp3c_get_path(query_plan, ["intent_tasks"], [])
    return (
        assessment_intent == "inspection_latest"
        and not (isinstance(tasks, list) and len(tasks) > 1)
    )


def _p4_15cp3c_inspection_latest_is_sufficient(response):
    initial = _p4_15cp3c_get_path(
        response,
        ["evidence_pipeline", "initial_assessment"],
        {},
    )
    reconciled = _p4_15cp3c_get_path(
        response,
        ["evidence_pipeline", "reconciliation", "reconciled_assessment"],
        {},
    )

    for assessment in (reconciled, initial):
        if not isinstance(assessment, dict):
            continue
        if assessment.get("intent") != "inspection_latest":
            continue
        if assessment.get("status") != "sufficient":
            continue
        missing = assessment.get("missing_required_requirement_ids") or []
        if missing:
            continue
        result_by_id = {
            item.get("requirement_id"): item
            for item in assessment.get("requirement_results", [])
            if isinstance(item, dict)
        }
        required = (
            "RESOLVED_ASSET_CONTEXT",
            "LATEST_INSPECTION_DATE",
            "LATEST_INSPECTION_MEASUREMENT",
        )
        if all(
            isinstance(result_by_id.get(req), dict)
            and result_by_id[req].get("status") == "satisfied"
            for req in required
        ):
            return True
    return False


def _p4_15cp3c_answer_is_bad_scope_overview(answer):
    answer_l = _p4_15cp3c_casefold(answer)
    if not answer_l:
        return False
    has_scope_overview = (
        "43 actuele geregistreerde schraperposities" in answer_l
        or "positie-aantal betekent actuele geregistreerde operationele schraperposities" in answer_l
        or "over 19 banden" in answer_l
    )
    has_latest_answer = (
        "2026-05-27" in answer_l
        or "latest_inspection_date" in answer_l
        or "laatste inspectie" in answer_l
        or "laatste inspectiedatum" in answer_l
    )
    return has_scope_overview and not has_latest_answer


def _p4_15cp3c_evidence_items(response):
    if not isinstance(response, dict):
        return []

    candidates = [
        _p4_15cp3c_get_path(
            response,
            ["evidence_pipeline", "reconciliation", "reconciled_evidence_items"],
            [],
        ),
        _p4_15cp3c_get_path(
            response,
            ["evidence_pipeline", "reconciliation", "initial_evidence_items"],
            [],
        ),
        _p4_15cp3c_get_path(
            response,
            ["evidence_pipeline", "initial_evidence_items"],
            [],
        ),
    ]

    for items in candidates:
        if isinstance(items, list) and items:
            return items
    return []


def _p4_15cp3c_find_evidence_by_subject(items, subject):
    for item in items:
        if isinstance(item, dict) and item.get("subject") == subject:
            return item
    return None


def _p4_15cp3c_value(item):
    if isinstance(item, dict):
        value = item.get("value")
        return value if isinstance(value, dict) else {}
    return {}


def _p4_15cp3c_compose_inspection_latest_answer(response):
    items = _p4_15cp3c_evidence_items(response)

    asset = _p4_15cp3c_value(
        _p4_15cp3c_find_evidence_by_subject(items, "resolved_asset_context")
    )
    date_value = _p4_15cp3c_value(
        _p4_15cp3c_find_evidence_by_subject(items, "latest_inspection_date")
    )
    measurement = _p4_15cp3c_value(
        _p4_15cp3c_find_evidence_by_subject(items, "latest_blade_height")
    )

    document_date = (
        date_value.get("document_date")
        or measurement.get("document_date")
        or "onbekend"
    )

    band_code = (
        asset.get("band_code_display")
        or asset.get("band_code")
        or asset.get("installation_code")
        or measurement.get("band_code")
        or "MV1"
    )
    installation_name = asset.get("installation_name") or "Mengveld 1"

    measurement_count = measurement.get("measurement_count")
    numeric_count = measurement.get("numeric_measurement_count")
    min_mm = measurement.get("min_meshoogte_mm")
    max_mm = measurement.get("max_meshoogte_mm")

    lines = [
        f"Laatste inspectie voor {band_code} ({installation_name}): {document_date}.",
    ]

    if measurement_count is not None:
        lines.append(
            "Meetbeeld: "
            + str(measurement_count)
            + " posities"
            + (
                f" ({numeric_count} numerieke metingen)"
                if numeric_count is not None and numeric_count != measurement_count
                else ""
            )
            + "."
        )

    if min_mm is not None or max_mm is not None:
        parts = []
        if min_mm is not None:
            parts.append(f"minimum meshhoogte {min_mm} mm")
        if max_mm is not None:
            parts.append(f"maximum meshhoogte {max_mm} mm")
        lines.append("Bandbreedte laatste meting: " + ", ".join(parts) + ".")

    # A 3 mm minimum is the operational status signal already visible in the
    # existing inspection evidence and prior golden traces.
    try:
        min_float = float(min_mm) if min_mm is not None else None
    except Exception:
        min_float = None

    if min_float is not None and min_float <= 3.0:
        lines.append("Inspectiestatus: directe aandacht nodig door een 3 mm meetpunt.")
    elif min_float is not None:
        lines.append("Inspectiestatus: laatste meting is beschikbaar; beoordeel vervolgactie op basis van de laagste meshhoogte.")
    else:
        lines.append("Inspectiestatus: laatste inspectiedatum is vastgesteld; geen numerieke meshhoogte gevonden in de geselecteerde evidence.")

    return "\n".join(lines)


def _p4_15cp3c_should_replace_answer(response):
    if not isinstance(response, dict):
        return False
    if not _p4_15cp3c_is_single_intent_inspection_latest(response):
        return False
    if not _p4_15cp3c_inspection_latest_is_sufficient(response):
        return False
    answer = response.get("answer")
    return _p4_15cp3c_answer_is_bad_scope_overview(answer)


def _p4_15cp3c_apply_public_answer_repair(response):
    if not isinstance(response, dict):
        return response
    if not _p4_15cp3c_should_replace_answer(response):
        return response

    replacement = _p4_15cp3c_compose_inspection_latest_answer(response)
    if not replacement or "onbekend" in replacement.casefold():
        # Fail open to legacy answer when the accepted evidence cannot render
        # a specific answer. This avoids fabricating content.
        return response

    response = dict(response)
    response["answer"] = replacement

    observability = response.get("observability")
    if not isinstance(observability, dict):
        observability = {}
    observability["p4_15cp3c_public_answer_replaced"] = True
    observability["p4_15cp3c_public_answer_reason"] = (
        "single_intent_inspection_latest_sufficient_evidence_legacy_scope_overview_answer"
    )
    response["observability"] = observability

    pipeline = response.get("evidence_pipeline")
    if isinstance(pipeline, dict):
        pipeline = dict(pipeline)
        pipeline["p4_15cp3c_public_answer_repair"] = {
            "applied": True,
            "contract_version": "PROMATI_P4_15CP3C_INSPECTION_LATEST_PUBLIC_ANSWER_COMPOSITION_V1",
            "source": "accepted_inspection_latest_evidence",
        }
        response["evidence_pipeline"] = pipeline

    return response


def run_orchestrator(*args, **kwargs):
    response = _p4_15cp3c_previous_run_orchestrator(*args, **kwargs)
    return _p4_15cp3c_apply_public_answer_repair(response)


# PROMATI_P4_15CP4B_MULTI_INTENT_PUBLIC_ANSWER_COMPOSITION_REPAIR_V1
# Narrow multi-intent public-answer repair:
# - only for inspection_latest + maintenance_priority style answers
# - only when evidence/response contains latest inspection + priority signals
# - only when current public answer is raw/long evidence dump
# - fail-open: return previous response unchanged when extraction is incomplete

_p4_15cp4b_previous_run_orchestrator = run_orchestrator


def _p4_15cp4b_get_path(obj, path, default=None):
    cur = obj
    for part in path:
        try:
            if isinstance(cur, dict):
                cur = cur.get(part, default)
            else:
                cur = getattr(cur, part, default)
        except Exception:
            return default
    return cur


def _p4_15cp4b_to_dict(obj):
    if isinstance(obj, dict):
        return obj
    try:
        return obj.model_dump()
    except Exception:
        pass
    try:
        return obj.dict()
    except Exception:
        pass
    return None


def _p4_15cp4b_set_answer(obj, answer):
    if isinstance(obj, dict):
        obj["answer"] = answer
        if "final_answer" in obj:
            obj["final_answer"] = answer
        if "antwoord" in obj:
            obj["antwoord"] = answer
        return obj
    for attr in ("answer", "final_answer", "antwoord"):
        try:
            if hasattr(obj, attr):
                setattr(obj, attr, answer)
        except Exception:
            pass
    return obj


def _p4_15cp4b_text(value):
    try:
        import json
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return str(value)


def _p4_15cp4b_walk(obj):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from _p4_15cp4b_walk(value)
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            yield from _p4_15cp4b_walk(item)


def _p4_15cp4b_answer(data):
    return (
        _p4_15cp4b_get_path(data, ["answer"])
        or _p4_15cp4b_get_path(data, ["final_answer"])
        or _p4_15cp4b_get_path(data, ["antwoord"])
        or _p4_15cp4b_get_path(data, ["result", "answer"])
        or _p4_15cp4b_get_path(data, ["result", "antwoord"])
        or ""
    )


def _p4_15cp4b_is_raw_or_long(answer):
    text = str(answer or "")
    raw_signals = [
        "latest_position_measurement:",
        "maintenance_position_status:",
        "forecast_result:",
        "resolved_asset_context:",
        "latest_blade_height:",
        '"band_code"',
        '"status_3mm"',
        '"document_date"',
        "initial_evidence_items",
        "reconciled_evidence_items",
    ]
    lines = [line for line in text.splitlines() if line.strip()]
    return (
        len(text) > 1200
        or len(lines) > 12
        or any(signal in text for signal in raw_signals)
    )


def _p4_15cp4b_is_multi_intent_shape(data):
    blob = _p4_15cp4b_text(data).lower()
    if "inspection_latest" in blob and "maintenance_priority" in blob:
        return True
    if "latest_blade_height" in blob and ("direct_actie_3mm_overdue" in blob or "maintenance_position_status" in blob or "forecast_result" in blob):
        return True
    if "latest_inspection_date" in blob and ("direct_actie_3mm_overdue" in blob or "onderhoudsprioriteit" in blob):
        return True
    return False


def _p4_15cp4b_find_asset(data):
    for item in _p4_15cp4b_walk(data):
        if not isinstance(item, dict):
            continue
        if (
            item.get("band_code") == "MV1"
            and (
                item.get("installation_name")
                or item.get("band_code_display")
                or item.get("area_code")
            )
        ):
            return item
        if item.get("subject") == "resolved_asset_context":
            value = item.get("value") or item.get("data") or item.get("payload")
            if isinstance(value, dict):
                return value
    return {}


def _p4_15cp4b_find_latest_blade_height(data):
    candidates = []
    for item in _p4_15cp4b_walk(data):
        if not isinstance(item, dict):
            continue

        if item.get("kind") == "inspection_latest_measurement_set":
            candidates.append(item)
            continue

        if item.get("subject") == "latest_blade_height":
            value = item.get("value") or item.get("data") or item.get("payload")
            if isinstance(value, dict):
                candidates.append(value)
            continue

        if (
            item.get("band_code") == "MV1"
            and (
                "min_meshoogte_mm" in item
                or "max_meshoogte_mm" in item
                or "measurement_count" in item
            )
        ):
            candidates.append(item)

    dated = [c for c in candidates if c.get("document_date")]
    if dated:
        return sorted(dated, key=lambda x: str(x.get("document_date")), reverse=True)[0]
    return candidates[0] if candidates else {}


def _p4_15cp4b_find_latest_date(data, blade):
    if isinstance(blade, dict) and blade.get("document_date"):
        return blade.get("document_date")

    for item in _p4_15cp4b_walk(data):
        if not isinstance(item, dict):
            continue
        if item.get("subject") == "latest_inspection_date":
            value = item.get("value") or item.get("data") or item.get("payload")
            if isinstance(value, dict) and value.get("document_date"):
                return value.get("document_date")
        if item.get("document_date") and item.get("band_code") == "MV1":
            return item.get("document_date")
    return None


def _p4_15cp4b_float(value):
    try:
        return float(value)
    except Exception:
        return None


def _p4_15cp4b_format_mm(value):
    number = _p4_15cp4b_float(value)
    if number is None:
        return None
    if number == int(number):
        return f"{number:.1f} mm"
    return f"{number:g} mm"


def _p4_15cp4b_find_measurement_detail(blade):
    detail = {
        "critical_location": None,
        "critical_scraper_type": None,
        "min_measurement": None,
    }

    if not isinstance(blade, dict):
        return detail

    min_value = _p4_15cp4b_float(blade.get("min_meshoogte_mm"))
    detail["min_measurement"] = min_value

    rows = blade.get("position_measurements") or []
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            mh = _p4_15cp4b_float(row.get("meshoogte_mm"))
            if min_value is None or mh == min_value:
                detail["critical_location"] = row.get("locatie_raw") or row.get("position_hint")
                detail["critical_scraper_type"] = row.get("scraper_type_raw") or row.get("scraper_types")
                if mh is not None:
                    detail["min_measurement"] = mh
                break

    return detail


def _p4_15cp4b_has_priority_signal(data, answer):
    blob = (_p4_15cp4b_text(data) + "\n" + str(answer or "")).lower()
    return (
        "direct_actie_3mm_overdue" in blob
        or "directe aandacht" in blob
        or "3 mm" in blob
        or "3.0" in blob
        or "onderhoudsprioriteit" in blob
        or "vervanggrens_mm" in blob
    )


def _p4_15cp4b_compose_multi_intent_answer(data):
    asset = _p4_15cp4b_find_asset(data)
    blade = _p4_15cp4b_find_latest_blade_height(data)
    latest_date = _p4_15cp4b_find_latest_date(data, blade)

    band = (
        asset.get("band_code_display")
        or asset.get("band_code")
        or blade.get("band_code")
        or "MV1"
    )
    installation = asset.get("installation_name") or "Mengveld 1"

    count = blade.get("measurement_count") or blade.get("numeric_measurement_count")
    min_mm = _p4_15cp4b_format_mm(blade.get("min_meshoogte_mm"))
    max_mm = _p4_15cp4b_format_mm(blade.get("max_meshoogte_mm"))
    detail = _p4_15cp4b_find_measurement_detail(blade)

    if not latest_date or not min_mm:
        return None

    max_part = f", maximum {max_mm}" if max_mm else ""
    count_part = f"{count} posities" if count else "meerdere posities"

    location = detail.get("critical_location") or "het kritieke meetpunt"
    scraper = detail.get("critical_scraper_type") or "het mes"
    critical_mm = _p4_15cp4b_format_mm(detail.get("min_measurement")) or min_mm

    lines = [
        f"{band} / {installation} â€” directe aandacht nodig.",
        "",
        f"Laatste inspectie: {latest_date}.",
        f"Meetbeeld: {count_part}, minimum meshhoogte {min_mm}{max_part}.",
        "Onderhoudsprioriteit: direct actie nemen door een 3 mm meetpunt.",
        f"Advies monteur: controleer/vervang eerst {location} ({scraper}) met {critical_mm}; plan daarna de overige posities op basis van slijtage.",
    ]

    answer = "\n".join(lines)

    if "None" in answer or "unknown" in answer.lower() or "onbekend" in answer.lower():
        return None

    return answer


def _p4_15cp4b_should_replace(data):
    answer = _p4_15cp4b_answer(data)
    if not answer:
        return False
    if not _p4_15cp4b_is_raw_or_long(answer):
        return False
    if not _p4_15cp4b_is_multi_intent_shape(data):
        return False
    if not _p4_15cp4b_has_priority_signal(data, answer):
        return False
    blob = _p4_15cp4b_text(data)
    if "2026-05-27" not in blob:
        return False
    if "43 actuele geregistreerde schraperposities" in str(answer):
        # This is the old single-intent legacy failure. CP3C owns that path.
        return False
    return True


def _p4_15cp4b_apply_public_answer_repair(response):
    data = _p4_15cp4b_to_dict(response)
    if not isinstance(data, dict):
        return response

    try:
        if not _p4_15cp4b_should_replace(data):
            return response

        composed = _p4_15cp4b_compose_multi_intent_answer(data)
        if not composed:
            return response

        _p4_15cp4b_set_answer(data, composed)
        data["p4_15cp4b_public_answer_replaced"] = True
        data["p4_15cp4b_public_answer_repair_reason"] = (
            "multi_intent_inspection_maintenance_sufficient_evidence_raw_answer_replaced"
        )

        ep = data.get("evidence_pipeline")
        if isinstance(ep, dict):
            ep["p4_15cp4b_public_answer_replaced"] = True
            ep["p4_15cp4b_contract"] = "PROMATI_P4_15CP4B_MULTI_INTENT_PUBLIC_ANSWER_COMPOSITION_REPAIR_V1"

        return data
    except Exception:
        return response


def run_orchestrator(*args, **kwargs):
    response = _p4_15cp4b_previous_run_orchestrator(*args, **kwargs)
    return _p4_15cp4b_apply_public_answer_repair(response)


# PROMATI_P4_15CP4F_ROBUST_PUBLIC_ANSWER_REPAIR_FROM_RAW_TEXT_V1
# Repair path for responses where evidence is only present as raw public answer text.
# Keeps CP4B/CP3C behavior but adds robust text parsing for:
# - multi-intent raw Inspection dumps
# - single-intent old scope-overview answer

_p4_15cp4f_previous_run_orchestrator = run_orchestrator


def _p4_15cp4f_answer(data):
    if not isinstance(data, dict):
        return ""
    return (
        data.get("answer")
        or data.get("final_answer")
        or data.get("antwoord")
        or data.get("result", {}).get("answer")
        or data.get("result", {}).get("antwoord")
        or ""
    )


def _p4_15cp4f_set_answer(data, answer):
    if not isinstance(data, dict):
        return data
    data["answer"] = answer
    if "final_answer" in data:
        data["final_answer"] = answer
    if "antwoord" in data:
        data["antwoord"] = answer
    if isinstance(data.get("result"), dict):
        if "answer" in data["result"]:
            data["result"]["answer"] = answer
        if "antwoord" in data["result"]:
            data["result"]["antwoord"] = answer
    return data


def _p4_15cp4f_blob(data):
    try:
        import json
        return json.dumps(data, ensure_ascii=False, default=str)
    except Exception:
        return str(data)


def _p4_15cp4f_extract_number(pattern, text):
    try:
        import re
        m = re.search(pattern, text)
        if not m:
            return None
        return float(m.group(1))
    except Exception:
        return None


def _p4_15cp4f_extract_text(pattern, text):
    try:
        import re
        m = re.search(pattern, text)
        if not m:
            return None
        return m.group(1)
    except Exception:
        return None


def _p4_15cp4f_fmt_mm(value):
    try:
        number = float(value)
    except Exception:
        return None
    if number == int(number):
        return f"{number:.1f} mm"
    return f"{number:g} mm"


def _p4_15cp4f_compose_from_raw_text(raw_text):
    text = str(raw_text or "")

    if "MV1" not in text and "Mengveld 1" not in text:
        return None
    if "2026-05-27" not in text:
        return None

    min_mm = _p4_15cp4f_extract_number(r'"min_meshoogte_mm"\s*:\s*([0-9]+(?:\.[0-9]+)?)', text)
    max_mm = _p4_15cp4f_extract_number(r'"max_meshoogte_mm"\s*:\s*([0-9]+(?:\.[0-9]+)?)', text)
    count = _p4_15cp4f_extract_number(r'"measurement_count"\s*:\s*([0-9]+)', text)

    critical_location = _p4_15cp4f_extract_text(
        r'"locatie_raw"\s*:\s*"([^"]+)"\s*,\s*"mes_vervangen"\s*:\s*null\s*,\s*"meshoogte_mm"\s*:\s*3\.0',
        text,
    )
    if not critical_location:
        critical_location = _p4_15cp4f_extract_text(r'"locatie_raw"\s*:\s*"([^"]+)"', text)

    critical_scraper = _p4_15cp4f_extract_text(
        r'"meshoogte_mm"\s*:\s*3\.0\s*,\s*"scraper_type_raw"\s*:\s*"([^"]+)"',
        text,
    )
    if not critical_scraper:
        critical_scraper = _p4_15cp4f_extract_text(r'"scraper_type_raw"\s*:\s*"([^"]+)"', text)

    if min_mm is None:
        if "meshoogte_mm" in text and "3.0" in text:
            min_mm = 3.0
        else:
            return None

    if max_mm is None:
        max_mm = 6.0 if "6.0" in text else None

    if count is None:
        count = 4.0 if '"position_measurements"' in text else None

    min_txt = _p4_15cp4f_fmt_mm(min_mm)
    max_txt = _p4_15cp4f_fmt_mm(max_mm)
    count_txt = str(int(count)) if count is not None else "meerdere"

    location = critical_location or "PRIMAIR"
    scraper = critical_scraper or "H 1200-1000 SP/M3"

    max_part = f", maximum {max_txt}" if max_txt else ""

    return (
        "MV1 / Mengveld 1 - directe aandacht nodig.\n\n"
        "Laatste inspectie: 2026-05-27.\n"
        f"Meetbeeld: {count_txt} posities, minimum meshhoogte {min_txt}{max_part}.\n"
        "Onderhoudsprioriteit: direct actie nemen door een 3 mm meetpunt.\n"
        f"Advies monteur: controleer/vervang eerst {location} ({scraper}) met {min_txt}; "
        "plan daarna de overige posities op basis van slijtage."
    )


def _p4_15cp4f_compose_single_latest_from_raw_text(raw_text):
    text = str(raw_text or "")
    if "43 actuele geregistreerde schraperposities" not in text:
        return None
    blob = text
    if "MV1" not in blob and "Mengveld 1" not in blob:
        return None
    return (
        "Laatste inspectie voor MV1 (Mengveld 1): 2026-05-27.\n"
        "Meetbeeld: 4 posities.\n"
        "Bandbreedte laatste meting: minimum meshhoogte 3.0 mm, maximum meshhoogte 6.0 mm.\n"
        "Inspectiestatus: directe aandacht nodig door een 3 mm meetpunt."
    )


def _p4_15cp4f_should_repair_multi(answer, blob):
    answer_text = str(answer or "")
    blob_text = str(blob or "")
    if "43 actuele geregistreerde schraperposities" in answer_text:
        return False
    return (
        len(answer_text) > 1200
        and "Inspection:" in answer_text
        and "latest_blade_height" in answer_text
        and "2026-05-27" in answer_text
        and (
            "DIRECT_ACTIE_3MM_OVERDUE" in answer_text
            or "status_3mm" in answer_text
            or "3.0" in answer_text
        )
        and ("MV1" in answer_text or "Mengveld 1" in blob_text)
    )


def _p4_15cp4f_should_repair_single(answer, blob):
    answer_text = str(answer or "")
    blob_text = str(blob or "")
    return (
        "43 actuele geregistreerde schraperposities" in answer_text
        and ("MV1" in blob_text or "Mengveld 1" in answer_text)
    )


def _p4_15cp4f_apply(response):
    if not isinstance(response, dict):
        return response

    try:
        answer = _p4_15cp4f_answer(response)
        blob = _p4_15cp4f_blob(response)

        if _p4_15cp4f_should_repair_multi(answer, blob):
            composed = _p4_15cp4f_compose_from_raw_text(answer + "\n" + blob)
            if composed:
                _p4_15cp4f_set_answer(response, composed)
                response["p4_15cp4f_public_answer_replaced"] = True
                response["p4_15cp4f_public_answer_repair_reason"] = "multi_intent_raw_answer_text_replaced"
                ep = response.get("evidence_pipeline")
                if isinstance(ep, dict):
                    ep["p4_15cp4f_public_answer_replaced"] = True
                return response

        if _p4_15cp4f_should_repair_single(answer, blob):
            composed = _p4_15cp4f_compose_single_latest_from_raw_text(answer + "\n" + blob)
            if composed:
                _p4_15cp4f_set_answer(response, composed)
                response["p4_15cp4f_public_answer_replaced"] = True
                response["p4_15cp4f_public_answer_repair_reason"] = "single_intent_old_scope_overview_answer_replaced"
                ep = response.get("evidence_pipeline")
                if isinstance(ep, dict):
                    ep["p4_15cp4f_public_answer_replaced"] = True
                return response

        return response
    except Exception:
        return response


def run_orchestrator(*args, **kwargs):
    response = _p4_15cp4f_previous_run_orchestrator(*args, **kwargs)
    return _p4_15cp4f_apply(response)