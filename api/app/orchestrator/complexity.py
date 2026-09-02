from __future__ import annotations

from app.orchestrator.models import QueryPlan


# Research-mode is bewust conservatief.
# Score 0-2: eenvoudige/directe vraag
# Score 3-5: analytisch, maar bestaande PROMATI-specialisten blijven leidend
# Score 6+: research-kandidaat
RESEARCH_REQUIRED_THRESHOLD = 6


PRODUCT_SIGNALS = (
    "schraper",
    "schrapertype",
    "bandschraper",
    "belle banne",
    "bb-u",
    "bb-r",
    "bb-p",
    "bb-h",
    "promati kf",
    "promati ks",
    "product",
    "productfamilie",
    "artikel",
    "voorraad",
    "prijs",
    "uitvoering",
    "ander type",
)

INSPECTION_SIGNALS = (
    "inspectie",
    "inspecties",
    "meshoogte",
    "slijtage",
    "slijt",
    "slijten",
    "bandconditie",
    "carryback",
    "vervanging",
    "vervangen",
    "onderhoud",
    "afstelling",
    "slijtagehistorie",
)

TECHNICAL_SIGNALS = (
    "cema",
    "bereken",
    "berekening",
    "formule",
    "bandsnelheid",
    "bandsterkte",
    "capaciteit",
    "trogrol",
    "idler",
    "trommeldiameter",
    "vermogen",
    "koppel",
)

ORG_SIGNALS = (
    "organisatie",
    "organigram",
    "afdeling",
    "functie",
    "collega",
    "manager",
    "contactpersoon",
    "wie is",
)

RFQ_SIGNALS = (
    "rfq",
    "offerte",
    "offerteaanvraag",
    "aanvraag",
    "leverancier",
    "supplier",
    "inkoop",
)

CAUSAL_SIGNALS = (
    "waarom",
    "oorzaak",
    "oorzaken",
    "waardoor",
    "hangt dat samen",
    "hangt samen",
    "samenhang",
    "verklaar",
    "verklaring",
    "veroorzaakt",
    "invloed op",
    "leidt tot",
)

RECOMMENDATION_SIGNALS = (
    "advies",
    "adviseer",
    "aanbevel",
    "zouden we",
    "zou ik",
    "beter",
    "ander type",
    "alternatief",
    "alternatieven",
    "vergelijk",
    "verschil",
    "welke uitvoering",
    "welke schraper",
    "welke keuze",
)

HISTORY_SIGNALS = (
    "historie",
    "historisch",
    "slijtagehistorie",
    "trend",
    "trends",
    "verloop",
    "lifecycle",
    "over tijd",
    "eerdere inspecties",
    "vorige inspecties",
    "laatste maanden",
    "laatste jaren",
)

TECHNICAL_CONTEXT_SIGNALS = (
    "bandsnelheid",
    "bandconditie",
    "materiaal",
    "vochtig",
    "vochtige",
    "nat materiaal",
    "temperatuur",
    "draairichting",
    "reverserend",
    "abrasief",
    "abrasieve",
    "kleverig",
    "kleverige",
    "omstandigheden",
    "montagepositie",
    "afstelling",
    "tph",
)

EXPERIENCE_SIGNALS = (
    "ervaring",
    "praktijkervaring",
    "praktijk",
    "vergelijkbare installaties",
    "andere installaties",
    "installed base",
    "referenties",
    "historische gevallen",
    "vergelijkbare gevallen",
    "cases",
)

EXPLICIT_RESEARCH_SIGNALS = (
    "volledige analyse",
    "uitgebreide analyse",
    "diepe analyse",
    "diepgaande analyse",
    "onderzoek",
    "onderzoeken",
    "analyseer",
    "combineer alle",
    "beoordeel samen",
    "integreer",
)


def _contains_any(question: str, terms: tuple[str, ...]) -> bool:
    return any(term in question for term in terms)


def _inferred_domain_signals(question: str) -> set[str]:
    """
    Alleen voor complexiteitsinschatting.

    Dit verandert plan.domains NIET en routeert dus geen specialist.
    De normale query-understanding blijft verantwoordelijk voor routing.
    """
    found: set[str] = set()

    if _contains_any(question, PRODUCT_SIGNALS):
        found.add("product")

    if _contains_any(question, INSPECTION_SIGNALS):
        found.add("inspection")

    if _contains_any(question, TECHNICAL_SIGNALS):
        found.add("technical")

    if _contains_any(question, ORG_SIGNALS):
        found.add("org")

    if _contains_any(question, RFQ_SIGNALS):
        found.add("rfq")

    return found


def assess_research_requirement(plan: QueryPlan) -> QueryPlan:
    """
    Bepaalt deterministisch of een vraag research-waardig is.

    Belangrijk:
    - geen OpenAI/Ollama-aanroep;
    - geen wijziging van domeinrouting;
    - geen wijziging van execution_steps;
    - multi-intent is een signaal, nooit op zichzelf een AI-trigger;
    - bij vereiste verduidelijking wordt research altijd geblokkeerd.
    """
    question = (plan.normalized_question or "").lower()

    route_domains = {
        str(getattr(domain, "value", domain))
        for domain in plan.domains
    }
    inferred_domains = _inferred_domain_signals(question)
    effective_domains = route_domains | inferred_domains

    requested_information = {
        str(item).strip().lower()
        for item in (plan.requested_information or [])
        if str(item).strip()
    }

    # PROMATI_REQUESTED_INFORMATION_COMPLEXITY_SCOPE_V1
    #
    # requested_information bestond vóór P1.1 alleen voor PRODUCT.
    # Inspection-facetten zijn voorlopig presentation-only en mogen
    # daarom niet stilzwijgend de research-threshold verhogen.
    multiple_information_requests = (
        len(requested_information) > 1
    )

    multi_intent = (
        len(effective_domains) > 1
        or multiple_information_requests
    )

    primary_domain_value = str(
        getattr(
            plan.primary_domain,
            "value",
            plan.primary_domain,
        )
        or ""
    ).lower()

    requested_information_affects_complexity = (
        primary_domain_value == "product"
        and multiple_information_requests
    )

    score = 0
    reasons: list[str] = []

    if len(effective_domains) > 1:
        score += 2
        reasons.append("multiple_domains")

    if requested_information_affects_complexity:
        score += 1
        reasons.append("multiple_information_requests")

    if _contains_any(question, CAUSAL_SIGNALS):
        score += 2
        reasons.append("causal_analysis")

    if _contains_any(question, RECOMMENDATION_SIGNALS):
        score += 2
        reasons.append("recommendation_or_comparison")

    if _contains_any(question, HISTORY_SIGNALS):
        score += 1
        reasons.append("historical_context")

    if _contains_any(question, TECHNICAL_CONTEXT_SIGNALS):
        score += 1
        reasons.append("technical_context")

    if _contains_any(question, EXPERIENCE_SIGNALS):
        score += 1
        reasons.append("application_experience")

    if _contains_any(question, EXPLICIT_RESEARCH_SIGNALS):
        score += 3
        reasons.append("explicit_research_request")

    research_required = (
        score >= RESEARCH_REQUIRED_THRESHOLD
        and not plan.clarification_required
    )

    if plan.clarification_required and score >= RESEARCH_REQUIRED_THRESHOLD:
        reasons.append("clarification_required_blocks_research")

    plan.multi_intent = multi_intent
    plan.complexity_score = score
    plan.complexity_reasons = reasons
    plan.research_required = research_required

    return plan