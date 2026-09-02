# PROMATI_BOUNDED_RESEARCH_AGENT_6B1
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from app.ai.gateway import ai_gateway
from app.ai.models import AIResearchRequest
from app.orchestrator.models import QueryPlan
from app.services.scope_resolver import (
    get_scope_catalog,
    validate_scope_code,
)


# Round 0 is the existing deterministic specialist run.
# Research rounds 1-2 are evidence-assessment rounds. A follow-up is only
# allowed in round 1; round 2 must synthesize/stop.
MAX_RESEARCH_ROUNDS = 2
MAX_TOTAL_SPECIALIST_CALLS = 6
MAX_FOLLOW_UP_CALLS_PER_ROUND = 3
MAX_PLANNER_AI_CALLS = 2
MAX_PLANNER_EVIDENCE_CHARS = 18000
MAX_PLANNER_STRING_CHARS = 2500


# Contracts are intentionally narrower than the public request schemas.
# Every entry maps to an existing GPT-facing read-only assistant route.
# The model never receives endpoint/URL/SQL fields.
ALLOWED_RESEARCH_ACTIONS: dict[str, frozenset[str]] = {
    "product_assistant": frozenset(
        {"vraag", "family_code", "belt_width_mm", "choice_type", "component_group", "mode", "limit"}
    ),
    "analysis_assistant": frozenset(
        {
            "vraag",
            "lijn_code",
            "band_code",
            "scraper_type",

            # PROMATI_SCOPE_SCRAPER_FAMILY_FILTER_V1
            "scraper_family",

            "zijde",
            "date_from",
            "date_to",
            "mode",
            "limit",
            "scope_code",
            "scope_type",
            "area_code",
            "installation_code",
        }
    ),
    "technical_assistant": frozenset(
        {"vraag", "topic_group", "source_code", "item_type", "use_rag", "limit"}
    ),
    "rfq_assistant": frozenset(
        {"vraag", "rfq_id", "position_id", "product_type", "bearing_type", "rubber_material", "language", "mode", "limit"}
    ),
    "org_assistant": frozenset(
        {"vraag", "firma", "locatie", "afdeling", "mode"}
    ),
    "diagnostics_assistant": frozenset(
        {
            "vraag",
            "domain",
            "mode",
            "inspection_key",
            "lijn_code",
            "band_code",
            "source_file_contains",
            "sheet",
            "diagnosis_code",
            "depth",
            "limit",
        }
    ),
}

_ACTION_DEFAULTS: dict[str, dict[str, Any]] = {
    "product_assistant": {"mode": "auto"},
    "analysis_assistant": {"mode": "auto"},
    "technical_assistant": {"use_rag": True},
    "rfq_assistant": {"mode": "auto"},
    "org_assistant": {"firma": "Promati", "mode": "auto"},
    "diagnostics_assistant": {},
}

_SENSITIVE_KEY_PARTS = (
    "password",
    "passwd",
    "secret",
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "token",
    "cookie",
    "credential",
    "private_key",
)

_ALLOWED_DECISION_KEYS = frozenset({"decision", "reason", "gaps", "calls"})
_ALLOWED_CALL_KEYS = frozenset({"action", "reason", "params"})
_DIAGNOSTICS_DOMAINS = frozenset({"database", "inspections", "rfq", "crm", "system", "products", "org"})
_DIAGNOSTICS_DEPTHS = frozenset({"normal", "deep"})
_DIAGNOSTICS_MODES = frozenset(
    {
        "overview",
        "database_object",
        "view_definition",
        "view_dependencies",
        "view_health",
        "inspection_pipeline",
        "inspection_lineage",
        "asset_model_health",
        "sql_deep_dive",
        "cross_source",
    }
)
_RFQ_LANGUAGES = frozenset({"nl", "en", "de", "fr"})

PlannerCallable = Callable[[AIResearchRequest], Any]


@dataclass(frozen=True)
class ResearchBudget:
    round_number: int
    initial_specialist_calls: int
    follow_up_specialist_calls: int = 0
    planner_ai_calls_used: int = 0

    @property
    def total_specialist_calls_used(self) -> int:
        return max(0, self.initial_specialist_calls) + max(
            0, self.follow_up_specialist_calls
        )

    @property
    def specialist_calls_remaining(self) -> int:
        return max(0, MAX_TOTAL_SPECIALIST_CALLS - self.total_specialist_calls_used)

    @property
    def planner_ai_calls_remaining(self) -> int:
        return max(0, MAX_PLANNER_AI_CALLS - max(0, self.planner_ai_calls_used))


@dataclass(frozen=True)
class ResearchToolCall:
    action: str
    reason: str
    params: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "reason": self.reason,
            "params": dict(self.params),
        }


@dataclass(frozen=True)
class ResearchPlannerDecision:
    status: str
    decision: str
    reason: str
    calls: tuple[ResearchToolCall, ...] = field(default_factory=tuple)
    gaps: tuple[str, ...] = field(default_factory=tuple)
    planner_ai_calls_used: int = 0
    blocked_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "decision": self.decision,
            "reason": self.reason,
            "calls": [call.to_dict() for call in self.calls],
            "gaps": list(self.gaps),
            "planner_ai_calls_used": self.planner_ai_calls_used,
            "blocked_reason": self.blocked_reason,
        }


def _is_sensitive_key(key: Any) -> bool:
    text = str(key or "").strip().lower()
    return any(part in text for part in _SENSITIVE_KEY_PARTS)


def _safe_error(exc: Exception) -> str:
    text = f"{type(exc).__name__}: {exc}"
    text = re.sub(r"sk-[A-Za-z0-9_-]{8,}", "[REDACTED]", text)
    return text[:1000]


def sanitize_planner_context(value: Any, *, depth: int = 0) -> Any:
    """Bound and redact data before it can be sent to the planner model."""
    if depth >= 6:
        return "[TRUNCATED_DEPTH]"

    if value is None or isinstance(value, (bool, int, float)):
        return value

    if isinstance(value, str):
        if len(value) <= MAX_PLANNER_STRING_CHARS:
            return value
        return value[:MAX_PLANNER_STRING_CHARS] + "...[TRUNCATED]"

    if hasattr(value, "model_dump"):
        try:
            return sanitize_planner_context(value.model_dump(mode="json"), depth=depth)
        except Exception:
            pass

    if hasattr(value, "dict"):
        try:
            return sanitize_planner_context(value.dict(), depth=depth)
        except Exception:
            pass

    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= 80:
                output["__truncated_keys__"] = len(value) - 80
                break
            key_text = str(key)
            if _is_sensitive_key(key_text):
                output[key_text] = "[REDACTED]"
            else:
                output[key_text] = sanitize_planner_context(item, depth=depth + 1)
        return output

    if isinstance(value, (list, tuple, set)):
        items = list(value)
        output = [
            sanitize_planner_context(item, depth=depth + 1)
            for item in items[:20]
        ]
        if len(items) > 20:
            output.append({"__truncated_items__": len(items) - 20})
        return output

    return sanitize_planner_context(str(value), depth=depth + 1)


def _plan_summary(plan: QueryPlan) -> dict[str, Any]:
    return {
        "original_question": plan.original_question,
        "primary_domain": getattr(plan.primary_domain, "value", plan.primary_domain),
        "domains": [
            getattr(domain, "value", domain)
            for domain in (plan.domains or [])
        ],
        "intent": plan.intent,
        "entities": sanitize_planner_context(plan.entities),
        "requested_information": list(plan.requested_information or []),
        "complexity_score": plan.complexity_score,
        "complexity_reasons": list(plan.complexity_reasons or []),
        "research_required": plan.research_required,
    }


def _accepted_evidence(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    used_chars = 2

    for item in results or []:
        if not isinstance(item, dict) or item.get("accepted") is not True:
            continue

        safe_item = sanitize_planner_context(
            {
                "step_id": item.get("step_id"),
                "domain": item.get("domain"),
                "action": item.get("action"),
                "result": item.get("result"),
            }
        )
        encoded = json.dumps(safe_item, ensure_ascii=False, default=str)
        if used_chars + len(encoded) > MAX_PLANNER_EVIDENCE_CHARS:
            break
        evidence.append(safe_item)
        used_chars += len(encoded) + 1

    return evidence


def _planner_question(question: str) -> str:
    return (
        "Beoordeel of de huidige PROMATI specialist-evidence voldoende is om de vraag "
        "betrouwbaar te beantwoorden. Geef uitsluitend een JSON-object terug, zonder "
        "markdown. Gebruik exact een van deze beslissingen: synthesize of follow_up. "
        "Bij follow_up mag je alleen allowlisted PROMATI assistant-actions voorstellen. "
        "Je mag nooit SQL, URLs, endpoints, writes of vrije toolnamen voorstellen. "
        "Een follow-up moet een concrete evidence-gap dichten; geen algemene verkenning. "
        "Gebruik dit schema: "
        '{"decision":"synthesize|follow_up","reason":"...","gaps":["..."],'
        '"calls":[{"action":"analysis_assistant","reason":"...",'
        '"params":{"vraag":"...","mode":"auto"}}]}. '
        "Als bewijs voldoende is of het budget geen follow-up toelaat, kies synthesize.\n\n"
        f"Gebruikersvraag: {question.strip()}"
    )


def _extract_json_object(text: str) -> dict[str, Any]:
    raw = str(text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw)
        raw = raw.strip()

    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("Plannerresponse bevat geen geldig JSON-object.")
        value = json.loads(raw[start : end + 1])

    if not isinstance(value, dict):
        raise ValueError("Plannerresponse moet een JSON-object zijn.")
    return value


def _validate_scalar_param(action: str, name: str, value: Any) -> Any:
    if isinstance(value, (dict, list, tuple, set)):
        raise ValueError(f"Niet-scalar parameter geblokkeerd: {name}")

    if name == "limit":
        if isinstance(value, bool):
            raise ValueError("limit moet een geheel getal zijn.")
        try:
            number = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("limit moet een geheel getal zijn.") from exc
        # Research keeps a tighter response bound than some public endpoints.
        if not 1 <= number <= 50:
            raise ValueError("research limit buiten toegestane range 1..50.")
        return number

    if name == "belt_width_mm":
        if isinstance(value, bool):
            raise ValueError("belt_width_mm moet een geheel getal zijn.")
        try:
            number = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("belt_width_mm moet een geheel getal zijn.") from exc
        if not 300 <= number <= 3000:
            raise ValueError("belt_width_mm buiten toegestane range 300..3000.")
        return number

    if name == "use_rag":
        if not isinstance(value, bool):
            raise ValueError("use_rag moet boolean zijn.")
        return value

    if value is None:
        return None

    text = str(value).strip()
    if len(text) > 1200:
        raise ValueError(f"Parameter te lang: {name}")

    if name == "vraag" and not text:
        raise ValueError("vraag mag niet leeg zijn.")

    if name == "mode":
        if action in {"product_assistant", "analysis_assistant", "rfq_assistant", "org_assistant"}:
            if text != "auto":
                raise ValueError(f"{action} research mode moet 'auto' zijn.")
        elif action == "diagnostics_assistant":
            if text not in _DIAGNOSTICS_MODES:
                raise ValueError("Niet-toegestane diagnostics mode.")
        else:
            raise ValueError(f"mode is niet toegestaan voor {action}.")

    if name == "firma" and text.casefold() != "promati":
        raise ValueError("org research follow-up mag alleen firma Promati gebruiken.")

    if name == "domain" and action == "diagnostics_assistant":
        if text not in _DIAGNOSTICS_DOMAINS:
            raise ValueError("Niet-toegestaan diagnostics domain.")

    if name == "depth" and action == "diagnostics_assistant":
        if text not in _DIAGNOSTICS_DEPTHS:
            raise ValueError("Niet-toegestane diagnostics depth.")

    if name == "language" and action == "rfq_assistant":
        if text not in _RFQ_LANGUAGES:
            raise ValueError("Niet-toegestane RFQ language.")

    return text



# PROMATI_RESEARCH_CANONICAL_SCOPE_V13_1
def _validate_analysis_scope_params(
    params: dict[str, Any],
) -> dict[str, Any]:
    """
    Valideer planner-voorgestelde PROMATI scopevelden tegen
    dezelfde canonical assetcatalogus als de gewone orchestrator.

    Fail-closed:
    - geen vrije/invented scopecodes;
    - installation_code moet een canonical installation zijn;
    - area_code moet een canonical area zijn;
    - scope_type moet overeenkomen;
    - conflicterende scopevelden worden geweigerd.

    Geldige waarden worden gecanonicaliseerd en waar mogelijk
    aangevuld zodat de specialist exact dezelfde scopecontext krijgt.
    """

    scope_fields = {
        "scope_code",
        "scope_type",
        "area_code",
        "installation_code",
    }

    if not any(
        params.get(name)
        for name in scope_fields
    ):
        return params

    clean = dict(params)

    proposed_scope_type = str(
        clean.get("scope_type")
        or ""
    ).strip().lower()

    if (
        proposed_scope_type
        and proposed_scope_type
        not in {"area", "installation"}
    ):
        raise ValueError(
            "Niet-toegestane scope_type; "
            "verwacht area of installation."
        )

    scope_code = str(
        clean.get("scope_code")
        or ""
    ).strip()

    installation_code = str(
        clean.get("installation_code")
        or ""
    ).strip()

    area_code = str(
        clean.get("area_code")
        or ""
    ).strip()

    validated_scope = None
    validated_installation = None
    validated_area = None

    if scope_code:
        check = validate_scope_code(
            scope_code
        )

        if not check.get("valid"):
            raise ValueError(
                "Niet-canonical scope_code geblokkeerd: "
                + scope_code
            )

        validated_scope = (
            check.get("scope")
            or {}
        )

    if installation_code:
        check = validate_scope_code(
            installation_code
        )

        candidate = (
            check.get("scope")
            or {}
        )

        if (
            not check.get("valid")
            or candidate.get("scope_type")
            != "installation"
        ):
            raise ValueError(
                "Niet-canonical installation_code "
                "geblokkeerd: "
                + installation_code
            )

        validated_installation = candidate

    if area_code:
        # PROMATI_RESEARCH_TYPED_SCOPE_VALIDATION_V13_1
        #
        # area_code is een getypeerd veld. Gebruik daarom direct
        # catalog["areas"] in plaats van validate_scope_code().
        # De generieke validator kiest bewust installation eerst
        # wanneer dezelfde code zowel area als installation is.
        # Dat is correct voor ongetypeerde scope_code, maar niet
        # voor een expliciet area_code veld.
        target_area_code = re.sub(
            r"\s+",
            "_",
            area_code.strip(),
        ).upper()

        try:
            catalog = get_scope_catalog()
        except Exception as exc:
            raise ValueError(
                "Canonical area catalog niet beschikbaar: "
                + type(exc).__name__
            ) from exc

        area_target = (
            catalog.get("areas", {})
            .get(target_area_code)
        )

        if area_target is None:
            raise ValueError(
                "Niet-canonical area_code "
                "geblokkeerd: "
                + area_code
            )

        validated_area = {
            "scope_type": "area",
            "canonical_code": target_area_code,
            "canonical_name": area_target.get(
                "canonical_name"
            ),
            "area_code": target_area_code,
            "installation_code": None,
            "source": (
                "canonical_typed_area_validation"
            ),
            "confidence": 1.0,
        }

    base = (
        validated_scope
        or validated_installation
        or validated_area
    )

    if not base:
        raise ValueError(
            "Canonical scopevalidatie leverde "
            "geen scope op."
        )

    base_type = str(
        base.get("scope_type")
        or ""
    )

    base_code = str(
        base.get("canonical_code")
        or ""
    )

    base_area = str(
        base.get("area_code")
        or ""
    )

    base_installation = str(
        base.get("installation_code")
        or ""
    )

    if (
        proposed_scope_type
        and proposed_scope_type != base_type
    ):
        raise ValueError(
            "scope_type conflicteert met "
            "canonical scope_code."
        )

    if validated_installation:
        installation = str(
            validated_installation.get(
                "canonical_code"
            )
            or ""
        )

        installation_area = str(
            validated_installation.get(
                "area_code"
            )
            or ""
        )

        if (
            base_type == "installation"
            and installation != base_code
        ):
            raise ValueError(
                "installation_code conflicteert "
                "met scope_code."
            )

        if (
            base_type == "area"
            and installation_area != base_code
        ):
            raise ValueError(
                "installation_code ligt buiten "
                "de opgegeven area scope."
            )

        base_type = "installation"
        base_code = installation
        base_installation = installation
        base_area = installation_area

    if validated_area:
        area = str(
            validated_area.get(
                "canonical_code"
            )
            or ""
        )

        if base_area and area != base_area:
            raise ValueError(
                "area_code conflicteert met "
                "de canonical installation."
            )

        if (
            base_type == "area"
            and base_code != area
        ):
            raise ValueError(
                "area_code conflicteert met "
                "scope_code."
            )

        base_area = area

    clean["scope_code"] = base_code
    clean["scope_type"] = base_type

    if base_area:
        clean["area_code"] = base_area
    else:
        clean.pop(
            "area_code",
            None,
        )

    if base_type == "installation":
        clean["installation_code"] = (
            base_installation
            or base_code
        )
    else:
        clean.pop(
            "installation_code",
            None,
        )

    return clean

def _validate_call(raw_call: Any) -> ResearchToolCall:
    if not isinstance(raw_call, dict):
        raise ValueError("Iedere research-call moet een object zijn.")

    unknown_call_keys = set(raw_call) - _ALLOWED_CALL_KEYS
    if unknown_call_keys:
        raise ValueError(
            "Niet-toegestane call-velden: " + ", ".join(sorted(unknown_call_keys))
        )

    action = str(raw_call.get("action") or "").strip()
    if action not in ALLOWED_RESEARCH_ACTIONS:
        raise ValueError(f"Niet-toegestane research-action: {action or '[leeg]'}")

    reason = str(raw_call.get("reason") or "").strip()
    if not reason:
        raise ValueError("Iedere follow-up call vereist een reason.")
    if len(reason) > 600:
        reason = reason[:600]

    params = raw_call.get("params")
    if not isinstance(params, dict):
        raise ValueError("Research-call params moeten een object zijn.")

    allowed_params = ALLOWED_RESEARCH_ACTIONS[action]
    unknown_params = set(params) - allowed_params
    if unknown_params:
        raise ValueError(
            f"Niet-toegestane parameters voor {action}: "
            + ", ".join(sorted(unknown_params))
        )

    for key in params:
        if _is_sensitive_key(key):
            raise ValueError(f"Gevoelige parameternaam geblokkeerd: {key}")

    clean_params = {
        str(key): _validate_scalar_param(action, str(key), value)
        for key, value in params.items()
    }

    if action == "analysis_assistant":
        clean_params = _validate_analysis_scope_params(
            clean_params
        )

    if "vraag" not in clean_params or not clean_params["vraag"]:
        raise ValueError(f"{action} vereist een concrete vraag parameter.")

    for key, value in _ACTION_DEFAULTS[action].items():
        clean_params.setdefault(key, value)

    return ResearchToolCall(
        action=action,
        reason=reason,
        params=clean_params,
    )


def _validate_decision(
    payload: dict[str, Any],
    budget: ResearchBudget,
) -> ResearchPlannerDecision:
    unknown_keys = set(payload) - _ALLOWED_DECISION_KEYS
    if unknown_keys:
        raise ValueError(
            "Niet-toegestane planner-velden: " + ", ".join(sorted(unknown_keys))
        )

    decision = str(payload.get("decision") or "").strip().lower()
    if decision not in {"synthesize", "follow_up"}:
        raise ValueError("decision moet synthesize of follow_up zijn.")

    reason = str(payload.get("reason") or "").strip()
    if not reason:
        raise ValueError("Plannerdecision vereist een reason.")
    if len(reason) > 1000:
        reason = reason[:1000]

    raw_gaps = payload.get("gaps") or []
    if not isinstance(raw_gaps, list):
        raise ValueError("gaps moet een lijst zijn.")
    gaps = tuple(str(item).strip()[:500] for item in raw_gaps[:12] if str(item).strip())

    raw_calls = payload.get("calls") or []
    if not isinstance(raw_calls, list):
        raise ValueError("calls moet een lijst zijn.")

    if decision == "synthesize":
        if raw_calls:
            raise ValueError("synthesize mag geen toolcalls bevatten.")
        return ResearchPlannerDecision(
            status="ok",
            decision="synthesize",
            reason=reason,
            gaps=gaps,
            planner_ai_calls_used=1,
        )

    if budget.round_number >= MAX_RESEARCH_ROUNDS:
        return ResearchPlannerDecision(
            status="blocked",
            decision="synthesize",
            reason="Laatste researchronde bereikt; geen verdere follow-up toegestaan.",
            gaps=gaps,
            planner_ai_calls_used=1,
            blocked_reason="research_round_budget_exhausted",
        )

    if not raw_calls:
        raise ValueError("follow_up vereist minimaal een call.")

    if len(raw_calls) > MAX_FOLLOW_UP_CALLS_PER_ROUND:
        return ResearchPlannerDecision(
            status="blocked",
            decision="synthesize",
            reason="Planner vroeg meer follow-up calls dan per ronde toegestaan.",
            gaps=gaps,
            planner_ai_calls_used=1,
            blocked_reason="per_round_tool_budget_exceeded",
        )

    if len(raw_calls) > budget.specialist_calls_remaining:
        return ResearchPlannerDecision(
            status="blocked",
            decision="synthesize",
            reason="Totaal specialist-toolbudget is uitgeput.",
            gaps=gaps,
            planner_ai_calls_used=1,
            blocked_reason="total_tool_budget_exceeded",
        )

    calls = tuple(_validate_call(item) for item in raw_calls)
    return ResearchPlannerDecision(
        status="ok",
        decision="follow_up",
        reason=reason,
        calls=calls,
        gaps=gaps,
        planner_ai_calls_used=1,
    )


def plan_research_next_step(
    plan: QueryPlan,
    results: list[dict[str, Any]],
    budget: ResearchBudget,
    *,
    planner: PlannerCallable | None = None,
) -> ResearchPlannerDecision:
    """Return a bounded, validated next step. This function executes no tools."""
    if not plan.research_required:
        return ResearchPlannerDecision(
            status="not_required",
            decision="synthesize",
            reason="research_required is false.",
            planner_ai_calls_used=0,
        )

    if plan.clarification_required:
        return ResearchPlannerDecision(
            status="blocked",
            decision="synthesize",
            reason="Clarification is vereist voordat research mag starten.",
            planner_ai_calls_used=0,
            blocked_reason="clarification_required",
        )

    if budget.round_number < 1 or budget.round_number > MAX_RESEARCH_ROUNDS:
        return ResearchPlannerDecision(
            status="blocked",
            decision="synthesize",
            reason="Research round_number valt buiten de toegestane grenzen.",
            planner_ai_calls_used=0,
            blocked_reason="invalid_research_round",
        )

    if budget.planner_ai_calls_remaining <= 0:
        return ResearchPlannerDecision(
            status="blocked",
            decision="synthesize",
            reason="Planner AI-callbudget is uitgeput.",
            planner_ai_calls_used=0,
            blocked_reason="planner_ai_budget_exhausted",
        )

    evidence = _accepted_evidence(results)
    if not evidence:
        return ResearchPlannerDecision(
            status="blocked",
            decision="synthesize",
            reason="Geen geaccepteerde specialist-evidence beschikbaar voor planning.",
            planner_ai_calls_used=0,
            blocked_reason="insufficient_evidence",
        )

    context = {
        "research_agent_contract": {
            "mode": "bounded_planner_6b1",
            "read_only": True,
            "arbitrary_endpoints_allowed": False,
            "arbitrary_urls_allowed": False,
            "sql_allowed": False,
            "writes_allowed": False,
            "allowed_actions": sorted(ALLOWED_RESEARCH_ACTIONS),
            "max_research_rounds": MAX_RESEARCH_ROUNDS,
            "max_total_specialist_calls": MAX_TOTAL_SPECIALIST_CALLS,
            "max_follow_up_calls_per_round": MAX_FOLLOW_UP_CALLS_PER_ROUND,
            "max_planner_ai_calls": MAX_PLANNER_AI_CALLS,
        },
        "budget": {
            "round_number": budget.round_number,
            "initial_specialist_calls": budget.initial_specialist_calls,
            "follow_up_specialist_calls": budget.follow_up_specialist_calls,
            "total_specialist_calls_used": budget.total_specialist_calls_used,
            "specialist_calls_remaining": budget.specialist_calls_remaining,
            "planner_ai_calls_used": budget.planner_ai_calls_used,
            "planner_ai_calls_remaining": budget.planner_ai_calls_remaining,
        },
        "query_plan": _plan_summary(plan),
        "specialist_evidence": evidence,
    }

    planner_callable = planner or ai_gateway.research

    try:
        ai_result = planner_callable(
            AIResearchRequest(
                question=_planner_question(plan.original_question),
                context=context,
                max_output_tokens=900,
            )
        )
        payload = _extract_json_object(str(getattr(ai_result, "text", "") or ""))
        return _validate_decision(payload, budget)
    except ValueError as exc:
        return ResearchPlannerDecision(
            status="invalid_response",
            decision="synthesize",
            reason="Plannerresponse is afgekeurd door PROMATI-validatie.",
            planner_ai_calls_used=1,
            blocked_reason=_safe_error(exc),
        )
    except Exception as exc:
        return ResearchPlannerDecision(
            status="provider_error",
            decision="synthesize",
            reason="Research planner provider-call is mislukt.",
            planner_ai_calls_used=1,
            blocked_reason=_safe_error(exc),
        )
