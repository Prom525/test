"""Conservative production applicability for the blade-height filter decision.

The parser and decision remain pure.  This adapter is the only place that
recognises the very small supported request shape and reads already-grounded
plan state.  It neither resolves a scope nor authorises an execution.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from .blade_height_filter_decision import (
    BladeHeightFilterApplicability,
    BladeHeightFilterCapabilityAvailability,
    BladeHeightFilterDecision,
    BladeHeightFilterDecisionInput,
    BladeHeightFilterDecisionOutcome,
    BladeHeightFilterScopeAssessment,
    decide_blade_height_filter,
)
from .blade_height_predicate_parser import parse_explicit_blade_height_predicate


_QUANTITY_RE = re.compile(r"\b(?:meshoogte|blade[_\s-]?height)\b", re.IGNORECASE)
_SELECTION_RE = re.compile(
    r"\b(?:toon|laat\s+(?:zien|me\s+zien)|geef|welke|selecteer|filter|"
    r"vind|zoek|lijst|overzicht)\b",
    re.IGNORECASE,
)
_FILTER_COMMAND_RE = re.compile(r"\b(?:filter|selecteer)\b", re.IGNORECASE)
_PREDICATE_CUE_RE = re.compile(
    r"\b(?:meshoogte|blade[_\s-]?height)\b\s*(?:"
    r"op\s+of\s+onder\b|minstens\b|onder\b|boven\b|exact\b|op\b|"
    r"<=|>=|<|>|=|rond\b|bijna\b|circa\b|[^\s]+\s*"
    r"(?:mm\b|millimeters?\b))",
    re.IGNORECASE,
)
_EXPLANATION_ONLY_RE = re.compile(
    r"^\s*(?:wat\s+betekent|leg\s+uit|verklaar|wat\s+is\s+de\s+definitie)\b",
    re.IGNORECASE,
)
_TEXT_PRESENTATION_RE = re.compile(
    r"\b(?:toon|laat\s+(?:zien|me\s+zien)|geef|citeer)\s+"
    r"(?:de\s+)?(?:tekst|zin|woorden|quote|citaat)\b",
    re.IGNORECASE,
)
_REQUEST_CONTINUATION_RE = re.compile(
    r"\b(?:en|maar|daarna)\s+(?=(?:toon|laat\s+(?:zien|me\s+zien)|"
    r"geef|welke|selecteer|filter|vind|zoek|leg\s+uit|verklaar|"
    r"wat\s+betekent|citeer)\b)",
    re.IGNORECASE,
)
_QUOTED_TEXT_RE = re.compile(r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'')
_OTHER_INTENT_RE = re.compile(
    r"\b(?:leg\s+uit|wat\s+betekent|verklaar|definitie|"
    r"onderhoudsadvies|geef\s+advies)\b",
    re.IGNORECASE,
)

# These are the authority sources emitted by the existing scope resolver.  A
# plan contains its flattened resolver output, not the raw resolver response,
# so acceptance also requires the accompanying scope-type contract below.
_CANONICAL_SCOPE_SOURCES = frozenset(
    {
        "canonical_scope_validation",
        "vw_gpt_band_asset_context.area",
        "vw_gpt_band_asset_context.installation",
        "sb_calendar_line_to_lijn",
    }
)


@dataclass(frozen=True)
class BladeHeightFilterBoundaryResult:
    """Private planning-boundary result; never added to a ``QueryPlan``."""

    decision: BladeHeightFilterDecision | None
    short_circuit: bool
    status: str | None
    answer: str | None
    clarification: dict[str, Any] | None


def _without_quoted_text(question: str) -> str:
    """Mask quotes for intent detection while retaining original parser input."""
    return _QUOTED_TEXT_RE.sub(lambda match: " " * len(match.group(0)), question)


def _local_request_text(question: str, position: int) -> str:
    """Return the request-sized prefix around one candidate, not all text."""
    start = max(question.rfind(".", 0, position), question.rfind(";", 0, position)) + 1
    for continuation in _REQUEST_CONTINUATION_RE.finditer(question, start, position):
        start = continuation.end()
    return question[start:position]


def _local_request_part(question: str, position: int) -> str:
    """Return the request-sized part containing one candidate.

    Request continuations begin at their next command, so a command for a
    band cannot borrow ``meshoogte`` from a following lookup (or vice versa).
    """
    start = max(question.rfind(".", 0, position), question.rfind(";", 0, position)) + 1
    for continuation in _REQUEST_CONTINUATION_RE.finditer(question, start, position):
        start = continuation.end()

    end = len(question)
    for separator in (".", ";"):
        next_separator = question.find(separator, position)
        if next_separator != -1:
            end = min(end, next_separator)
    next_continuation = _REQUEST_CONTINUATION_RE.search(question, position)
    if next_continuation is not None:
        end = min(end, next_continuation.start())
    return question[start:end]


def _is_explanatory_or_text_presentation(question: str, position: int) -> bool:
    """Exclude only a presentation/explanation clause containing this candidate."""
    local_text = _local_request_text(question, position)
    return bool(
        _EXPLANATION_ONLY_RE.search(local_text)
        or _TEXT_PRESENTATION_RE.search(local_text)
    )


def _is_explicit_result_selection(question: str) -> bool:
    """Recognise one local filter attempt without reclassifying data lookups.

    A request for the latest measured blade height is a legacy data lookup, not
    a filter.  A filter command or a comparison-shaped meshoogte condition is
    required.  Quotes are masked only for this recognition pass: if relevant,
    the parser still receives the original text exactly once.
    """
    visible_question = _without_quoted_text(question)

    for command in _FILTER_COMMAND_RE.finditer(visible_question):
        local_part = _local_request_part(visible_question, command.start())
        if (
            _QUANTITY_RE.search(local_part)
            and not _is_explanatory_or_text_presentation(
                visible_question, command.start()
            )
        ):
            return True

    for cue in _PREDICATE_CUE_RE.finditer(visible_question):
        local_part = _local_request_part(visible_question, cue.start())
        if (
            _SELECTION_RE.search(local_part)
            and not _is_explanatory_or_text_presentation(visible_question, cue.start())
        ):
            return True
    return False


def _scope_assessment(plan: Any) -> BladeHeightFilterScopeAssessment:
    """Accept the existing resolver's complete, internally coherent contract.

    Free text in a ``DetectedEntity`` and the absence of a blocker are not
    grounding.  The accepted shape is exactly the flattened result that
    ``understand_query`` constructs from ``resolve_scope_context``: a known
    authority source plus a coherent area/installatie relationship.
    """
    entities = getattr(plan, "entities", None)
    scope = entities.get("scope_code") if isinstance(entities, dict) else None
    candidates = entities.get("scope_candidates") if isinstance(entities, dict) else None
    if candidates is not None and getattr(candidates, "value", None):
        return BladeHeightFilterScopeAssessment.AMBIGUOUS

    if scope is None or not isinstance(entities, dict):
        return BladeHeightFilterScopeAssessment.UNRESOLVED

    scope_code = str(getattr(scope, "value", "") or "").strip()
    scope_source = str(getattr(scope, "source", "") or "").strip()
    scope_type = entities.get("scope_type")
    scope_type_value = str(getattr(scope_type, "value", "") or "").strip()
    area = entities.get("area_code")
    area_code = str(getattr(area, "value", "") or "").strip()
    installation = entities.get("installation_code")
    installation_code = str(getattr(installation, "value", "") or "").strip()
    try:
        scope_confidence = float(getattr(scope, "confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        return BladeHeightFilterScopeAssessment.UNRESOLVED

    has_authority_contract = (
        getattr(scope, "name", None) == "scope_code"
        and bool(scope_code)
        and scope_source in _CANONICAL_SCOPE_SOURCES
        and scope_confidence >= 0.98
        and scope_type_value in {"area", "installation"}
        and getattr(scope_type, "source", None) == "scope_resolver"
    )
    if not has_authority_contract:
        return BladeHeightFilterScopeAssessment.UNRESOLVED

    if scope_type_value == "area":
        if (
            area_code == scope_code
            and not installation_code
            and getattr(area, "source", None) == "scope_resolver"
        ):
            return BladeHeightFilterScopeAssessment.RESOLVED
        return BladeHeightFilterScopeAssessment.AMBIGUOUS

    if (
        installation_code == scope_code
        and getattr(installation, "source", None) == "scope_resolver"
    ):
        return BladeHeightFilterScopeAssessment.RESOLVED
    return BladeHeightFilterScopeAssessment.AMBIGUOUS


def _has_other_intent(question: str, plan: Any) -> bool:
    """Keep an unrepresented explanatory/advies request from being discarded.

    The existing classifier remains authoritative when it reports a compound
    plan.  This narrow supplement covers a filter joined to an explanation or
    advice request, combinations for which the legacy classifier has no task.
    It does not execute either component.
    """
    visible_question = _without_quoted_text(question)
    return bool(getattr(plan, "multi_intent", False)) or bool(
        _OTHER_INTENT_RE.search(visible_question)
        or _TEXT_PRESENTATION_RE.search(visible_question)
    )


def _clarification_for(decision: BladeHeightFilterDecision) -> dict[str, Any]:
    if decision.outcome is BladeHeightFilterDecisionOutcome.DEFERRED_COMPOSITION:
        question = (
            "Deze vraag combineert een meshoogtefilter met andere verzoeken. "
            "Welke vraag wil je eerst laten behandelen?"
        )
    elif decision.clarification and decision.clarification.value == "predicate":
        reason = decision.parser_reason.value if decision.parser_reason else ""
        questions = {
            "negative_value": "Gebruik een niet-negatieve meshoogte in mm.",
            "non_finite_value": "Gebruik een eindig getal voor de meshoogte in mm.",
            "invalid_number": "Gebruik een geldig getal voor de meshoogte in mm.",
            "missing_operator": "Geef een vergelijking, bijvoorbeeld: meshoogte onder 3 mm.",
            "missing_value": "Noem een waarde in mm bij de meshoogtevergelijking.",
            "missing_unit": "Vermeld de meshoogte in mm.",
            "missing_quantity": "Geef aan dat de vergelijking over meshoogte gaat.",
            "approximate_value": "Gebruik één exacte meshoogtevergelijking in mm, niet ‘rond’ of ‘circa’.",
            "multiple_measurements": "Geef één meshoogtevergelijking in mm.",
            "unsupported_composition": "Geef één meshoogtevergelijking in mm.",
            "unsupported_number_word": "Gebruik een numerieke meshoogte in mm.",
        }
        question = questions.get(
            reason,
            "Geef één duidelijke meshoogtevergelijking in mm.",
        )
    else:
        question = "Welke installatie of welk gebied wil je op meshoogte filteren?"
    return {"required": True, "question": question}


def assess_blade_height_filter_applicability(
    original_question: str,
    plan: Any,
) -> BladeHeightFilterBoundaryResult:
    """Evaluate the bounded filter policy from local text and proven plan facts.

    Existing clarification/blocker outcomes keep their historic priority.  The
    parser is nevertheless invoked exactly once for a relevant explicit filter
    request, so no normalisation can move its source span.
    """
    if not _is_explicit_result_selection(original_question):
        return BladeHeightFilterBoundaryResult(None, False, None, None, None)

    parser_result = parse_explicit_blade_height_predicate(original_question)
    decision = decide_blade_height_filter(
        BladeHeightFilterDecisionInput(
            applicability=BladeHeightFilterApplicability.EXPLICIT_FILTER_REQUEST,
            parser_result=parser_result,
            scope=_scope_assessment(plan),
            capability=BladeHeightFilterCapabilityAvailability.UNAVAILABLE,
            has_other_intents=_has_other_intent(original_question, plan),
        )
    )

    # CP9-CP12 and existing scope/blocker clarification retain precedence.
    if getattr(plan, "execution_blockers", None) or getattr(
        plan, "clarification_required", False
    ):
        return BladeHeightFilterBoundaryResult(decision, False, None, None, None)

    if decision.outcome is BladeHeightFilterDecisionOutcome.LEGACY:
        return BladeHeightFilterBoundaryResult(decision, False, None, None, None)

    if decision.outcome is BladeHeightFilterDecisionOutcome.UNSUPPORTED:
        return BladeHeightFilterBoundaryResult(
            decision,
            True,
            "unsupported",
            "Filteren op meshoogte wordt voor deze scope nog niet ondersteund.",
            {"required": False, "question": None},
        )

    clarification = _clarification_for(decision)
    return BladeHeightFilterBoundaryResult(
        decision,
        True,
        "clarification_required",
        clarification["question"],
        clarification,
    )


__all__ = [
    "BladeHeightFilterBoundaryResult",
    "assess_blade_height_filter_applicability",
]
