import re
from dataclasses import dataclass

from app.orchestrator.models import (
    DetectedEntity,
    Domain,
    IntentTask,
    QueryPlan,
)
from app.orchestrator.models import (
    ExecutionBlocker,
    ExecutionBlockerType,
)
from app.orchestrator.normalizer import normalize_question
from app.orchestrator.evidence_requirement_catalog import get_requirement_set
from app.services.scope_resolver import (
    get_scope_catalog,
    resolve_scope,
    resolve_scope_context,
    validate_scope_code,
)

from app.orchestrator.query_classification import classify_query, is_pure_system_meta_query
from app.orchestrator.band_candidate_shadow import classify_band_candidate_shadow

# PROMATI_CANONICAL_SCOPE_UNDERSTANDING_V13_1


@dataclass(frozen=True)
class FamilyPattern:
    code: str
    patterns: tuple[str, ...]


PRODUCT_FAMILY_PATTERNS = (
    FamilyPattern(
        code="BB-U",
        patterns=(
            r"\bbelle\s+banne\s+u\b",
            r"\bbb[\s-]*u\b",
            r"\bbb[\s-]*u\s*\d{3,4}\b",
            r"\bu(?:\s+\d{3,4})?\s+bb\s+schraper\b",
            r"\bu(?:\s+\d{3,4})?\s+schraper\b",
        ),
    ),
    FamilyPattern(
        code="BB-H",
        patterns=(
            r"\bbelle\s+banne\s+h\b",
            r"\bbb[\s-]*h\b",
            r"\bh(?:\s+\d{3,4})?\s+bb\s+schraper\b",
            r"\bh(?:\s+\d{3,4})?\s+schraper\b",
        ),
    ),
    FamilyPattern(
        code="BB-P",
        patterns=(
            r"\bbelle\s+banne\s+p\b",
            r"\bbb[\s-]*p\b",
            r"\bp(?:\s+\d{3,4})?\s+schraper\b",
        ),
    ),
    FamilyPattern(
        code="BB-R",
        patterns=(
            r"\bbelle\s+banne\s+r\b",
            r"\bbb[\s-]*r\b",
            r"\br(?:\s+\d{3,4})?\s+schraper\b",
        ),
    ),
    # PROMATI_P4_5B7_CANONICAL_PROM_KF_KS_ALIAS_FIX
    # Canonical PROM-KF / PROM-KS codes use the short PROM prefix.
    # Keep PROMATI aliases, and accept whitespace or hyphen separators.
    FamilyPattern(
        code="PROM-KF",
        patterns=(
            r"\bpromati[\s-]+kf\b",
            r"\bprom[\s-]+kf\b",
            r"\bkf[\s-]*schraper\b",
        ),
    ),
    FamilyPattern(
        code="PROM-KS",
        patterns=(
            r"\bpromati[\s-]+ks\b",
            r"\bprom[\s-]+ks\b",
            r"\bks[\s-]*schraper\b",
        ),
    ),
    FamilyPattern(
        code="PROM-TPH-HD",
        patterns=(
            r"\btph[\s-]*hd\b",
            r"\bpromati\s+tph[\s-]*hd\b",
        ),
    ),
    FamilyPattern(
        code="PROM-TPH-ND",
        patterns=(
            r"\btph[\s-]*nd\b",
            r"\bpromati\s+tph[\s-]*nd\b",
        ),
    ),
    FamilyPattern(
        code="PROLOAD",
        patterns=(
            r"\bproload\b",
            r"\bblu[\s-]*tec\s+proload\b",
            r"\bblutec\s+proload\b",
        ),
    ),
    FamilyPattern(
        code="IMPACT-BARS",
        patterns=(
            r"\bimpact[\s-]*bars?\b",
            r"\bblu[\s-]*tec\s+impact[\s-]*bars?\b",
            r"\bblutec\s+impact[\s-]*bars?\b",
        ),
    ),
)


PRODUCT_DOMAIN_TERMS = (
    "schraper",
    "bandschraper",
    "belle banne",
    "promati kf",
    "promati ks",
    "tph",
    "proload",
    "artikel",
    "artikelen",
    "voorraad",
    "prijs",
)

INSPECTION_DOMAIN_TERMS = (
    "inspectie",
    "inspecties",
    "inspectierapport",
    "rapport",
    "slijtage",

    "slijt",
    "meshoogte",
    "trend",
    "historie",
    "tijdlijn",
    "onderhoud",
    "vervangen",
    "vervanging",
    "laatste meting",

    # PROMATI_P4_15D_CROSS_DOMAIN_ROUTING_TERMS_V1
    "scheefloop",
    "scheef loop",
    "scheeflopen",
    "band loopt scheef",
    "bandscheefloop",
    "ongelijke slijtage",
    "ongelijkmatige slijtage",
    "schuin afgesleten",
    "scheef afgesleten",
    "waar moet de monteur op letten",
    "waar moet ik op letten",
    "controlepunten",
    "werkinstructie",
    "artikel",
    "artikelen",
    "artikelnummer",
    "klaarleggen",
    "meenemen",
    "welk mes",
    "welke messen",
    "kritieke schraperposities",
    "schraperposities",
    "selectiecriteria",
    "selectie criteria",
    "materiaal dat over de band gaat",
    "materiaal over de band",
    "slijt snel",
    "snel slijt",
    "snelle slijtage",
    "ongewone slijtage",
    "slechte prestatie",
    "presteert slecht",
)


# CP3: explicit negative domain mentions are constraints, not routing signals.
# Keep this deliberately lexical and bounded to the negated clause.
NEGATED_DOMAIN_PATTERNS = {
    Domain.PRODUCT: r"\b(?:product(?:advies|informatie|info|selectie)?|producten?|schraperselectie)\b",
    Domain.INSPECTION: r"\b(?:inspectie(?:analyse|advies|rapport)?|inspecties?)\b",
    Domain.TECHNICAL: r"\b(?:techniek|technisch(?:e)?|cema)\b",
    Domain.ORG: r"\b(?:org|organisatie(?:analyse|advies)?)\b",
    Domain.RFQ: r"\b(?:rfq(?:-?vraag)?|offerte(?:vraag)?)\b",
}

NEGATED_RFQ_PATTERN = r"\b(?:rfq(?:-?vraag)?|offerte(?:vraag)?)\b"


def _is_explicitly_negated(question: str, pattern: str) -> bool:
    """Recognize a domain inside a short Dutch negative constraint clause."""
    q = (question or "").casefold()
    for match in re.finditer(r"\b(?:geen|zonder|niet)\b", q):
        clause = re.split(
            r"[.;!?]|\b(?:maar|echter)\b",
            q[match.end():],
            maxsplit=1,
        )[0]
        if re.search(pattern, clause):
            return True
    return False


def _domain_is_negated(question: str, domain: Domain) -> bool:
    pattern = NEGATED_DOMAIN_PATTERNS.get(domain)
    return bool(pattern and _is_explicitly_negated(question, pattern))

BAND_CONTEXT_INSPECTION_TERMS = (
    "hoe staat",
    "ervoor",
    "vorige keer",
    "laatste keer",
    "mis met",
    "status",
    "conditie",
)


# Alleen in combinatie met een door PROMATI-data bevestigde
# area/installatie vormen deze termen sterke inspectie-/assetcontext.
SCOPE_INSPECTION_TERMS = (
    "positie",
    "posities",
    "schraperpositie",
    "schraperposities",
    "schraper positie",
    "schraper posities",
    "bandpositie",
    "bandposities",
    "band",
    "banden",
    "schraper",
    "schrapers",
    "inspectie",
    "inspecties",
    "slijtage",
    "slijt",
    "slijtagepatroon",
    "meshoogte",
    "onderhoud",
    "vervangen",
    "vervanging",
    "status",
    "conditie",
    "kritiek",
    "ranglijst",
    "hoeveel",
    "wat staat er",
    "welke staan",
    "analyse",
    "analyseer",
    "analyseren",
    "diepgaande analyse",
    "overzicht",
    "patroon",
    "laatste",
    "actuele",

    # PROMATI_P4_15D_CROSS_DOMAIN_ROUTING_TERMS_V1
    "scheefloop",
    "bandscheefloop",
    "artikel",
    "klaarleggen",
    "welk mes",
    "kritieke schraperposities",
    "selectiecriteria",
    "materiaal over de band",
    "slijt snel",
    "snelle slijtage",
)


def detect_requested_information(
    question: str,
    primary_domain: Domain | None,
) -> list[str]:
    """
    Bepaalt welke concrete informatie-elementen de gebruiker vraagt.

    Dit is bewust deterministisch. De lijst stuurt alleen de
    presentatielaag; bronselectie en domeinlogica blijven bij de
    bestaande specialists.
    """
    q = (question or "").casefold()
    requested: list[str] = []
    product_negated = _domain_is_negated(q, Domain.PRODUCT)

    def add(name: str) -> None:
        if name not in requested:
            requested.append(name)

    if primary_domain == Domain.PRODUCT:
        if any(term in q for term in (
            "voordelen",
            "sterktes",
            "sterke punten",
            "voor- en nadelen",
        )):
            add("strengths")

        if any(term in q for term in (
            "nadelen",
            "beperkingen",
            "zwakke punten",
            "voor- en nadelen",
        )):
            add("limitations")

        if any(term in q for term in (
            "voorraad",
            "op voorraad",
            "beschikbaar",
        )):
            add("inventory")

        if any(term in q for term in (
            "prijs",
            "kost",
            "kosten",
        )):
            add("price")

        if any(term in q for term in (
            "selectieadvies",
            "welke uitvoering",
            "welke schraper",
            "kiezen",
            "keuze",
        )):
            add("selection_advice")

    # PROMATI_INSPECTION_REQUESTED_INFORMATION_V1
    #
    # Inspection-facetten zijn in P1.1 presentation-intent.
    # Ze wijzigen hier geen primary intent, routing of specialistcall.
    if primary_domain == Domain.INSPECTION:
        if any(term in q for term in (
            "laatste meshoogte",
            "laatste meting",
            "laatste metingen",
            "meest recente meshoogte",
            "actuele meshoogte",
            "recentste meshoogte",
        )):
            add("latest_measurements")

        if any(term in q for term in (
            "lifecycle",
            "trend",
            "slijtage",
            "slijtageanalyse",
            "slijtage analyse",
            "historie",
            "tijdlijn",
            "verloop",
            "ontwikkeling",
            "ontwikkelt",
        )):
            add("lifecycle_trend")

        if (
            any(term in q for term in (
                "vervangevent",
                "vervangevents",
                "vervanghistorie",
                "vervanggeschiedenis",
                "vervangingen",
                "laatste vervanging",
            ))
            or (
                "wanneer" in q
                and "vervangen" in q
            )
        ):
            add("replacement_events")

        if any(term in q for term in (
            "vervangadvies",
            "vervang advies",
            "moet er iets vervangen",
            "moet iets vervangen",
            "moet vervangen worden",
            "moeten vervangen worden",
            "wat moet vervangen",
            "welke schraper moet vervangen",
            "welke schrapers moeten vervangen",
        )):
            add("replacement_advice")

        if any(term in q for term in (
            "onzekerheid",
            "onzekerheden",
            "betrouwbaarheid",
            "hoe betrouwbaar",
        )):
            add("uncertainties")



    # PROMATI_P4_15B_CROSS_DOMAIN_REQUESTED_INFO_V1
    if primary_domain == Domain.INSPECTION:
        cross_domain_observation_terms = (
            "scheefloop", "scheef loop", "scheeflopen",
            "band loopt scheef", "bandscheefloop",
            "ongelijke slijtage", "ongelijkmatige slijtage",
            "schuin afgesleten", "scheef afgesleten",
            "materiaalophoping", "materiaal ophoping",
            "niet goed aanliggen", "slecht aanliggen",
        )
        cross_domain_theory_terms = (
            "theorie", "waar moet de monteur op letten",
            "waar moet ik op letten", "controlepunten",
            "controleren", "werkinstructie", "instructie",
            "oorzaak", "oorzaken", "verklaring",
        )
        cross_domain_article_terms = (
            "artikel", "artikelen", "artikelnummer",
            "onderdeel", "onderdelen", "bestellen",
            "klaarleggen", "meenemen", "welk mes",
            "welke mes", "welke messen",
        )
        cross_domain_product_terms = (
            "productinformatie", "product informatie",
            "productinfo", "product info", "product",
            "schrapertype", "scraper type", "type schraper",
        )
        cross_domain_selection_terms = (
            "selectiecriteria", "selectie criteria",
            "selectieadvies", "selectie advies",
            "past de huidige schraper", "past deze schraper",
            "materiaal dat over de band gaat",
            "materiaal over de band", "abrasief", "abrasive",
        )
        cross_domain_performance_terms = (
            "slijt snel", "snel slijt", "snelle slijtage",
            "slechte prestatie", "slecht presteert",
            "presteert slecht", "vaak vervangen",
            "vaker vervangen", "gaat niet lang mee",
            "ongewone slijtage",
        )

        has_observation = any(term in q for term in cross_domain_observation_terms)
        has_theory = any(term in q for term in cross_domain_theory_terms)
        has_article = any(term in q for term in cross_domain_article_terms)
        # PROMATI_P4_15D_CROSS_DOMAIN_TRIGGER_REPAIR_V1
        has_product = not product_negated and (
            any(term in q for term in cross_domain_product_terms)
            or "schraper" in q
            or "bandschraper" in q
            or "scraper" in q
        )
        has_selection = not product_negated and any(
            term in q for term in cross_domain_selection_terms
        )
        has_performance = (
            any(term in q for term in cross_domain_performance_terms)
            or ("slijt" in q and "snel" in q)
            or ("slijtage" in q and "snel" in q)
            or ("presteert" in q and "slecht" in q)
            or ("prestatie" in q and "slecht" in q)
        )

        if has_observation:
            add("inspection_observation")
        if has_observation and has_theory:
            add("theory_guidance")
        if has_article:
            add("article_lookup")
            if (
                "schraper" in q
                or "schraperpositie" in q
                or "schraperposities" in q
                or "kritieke" in q
                or "mes" in q
                or "positie" in q
            ):
                add("inspection_observation")
        if has_product:
            add("product_information")
        if has_selection:
            add("selection_criteria")
            add("product_information")
            add("product_fit_analysis")
        if has_performance:
            add("performance_history")
            add("product_information")
            add("product_fit_analysis")
        if has_product and (has_selection or has_performance):
            add("product_fit_analysis")


    # PROMATI_P4_14W_GOLDEN_MV1_INSPECTION_MAINTENANCE_TASKS_V1
    # Golden MV1-vraag: "laatste inspectiestatus" + "onderhoudsprioriteit"
    # moet als twee inspection-taken beschikbaar zijn voor task public
    # composition. Dit blijft deterministisch en verandert geen specialist
    # endpoint of writes.
    if primary_domain == Domain.INSPECTION:
        if any(term in q for term in (
            "laatste inspectiestatus",
            "inspectiestatus",
            "laatste inspectie",
            "laatste inspectiedatum",
            "meest recente inspectie",
            "recentste inspectie",
        )):
            add("latest_measurements")

        if any(term in q for term in (
            "onderhoudsprioriteit",
            "onderhoud prioriteit",
            "onderhoudsadvies",
            "onderhoud advies",
            "prioriteit",
            "wat moet eerst",
            "welke onderhoudsprioriteit",
        )):
            add("maintenance_priority")

    return requested


def _entity(
    name: str,
    raw_value,
    value,
    confidence: float,
    source: str,
) -> DetectedEntity:
    return DetectedEntity(
        name=name,
        raw_value=raw_value,
        value=value,
        confidence=confidence,
        source=source,
    )



# PROMATI_MULTI_PRODUCT_UNDERSTANDING_P4_5B2
def detect_product_families(
    question: str,
) -> list[DetectedEntity]:
    """
    Detecteer alle expliciet genoemde productfamilies.

    Eigenschappen:
    - deduplicatie op canonieke family-code;
    - behoud volgorde van eerste vermelding;
    - langste match wint bij gelijke startpositie;
    - bestaande contextgevoelige BB-U fallback blijft
      alleen gelden wanneer geen expliciete familie matcht.
    """

    q = question or ""

    best_by_code: dict[
        str,
        tuple[
            tuple[int, int, int, int],
            DetectedEntity,
        ],
    ] = {}

    for family_index, family in enumerate(
        PRODUCT_FAMILY_PATTERNS
    ):
        for pattern_index, pattern in enumerate(
            family.patterns
        ):
            for match in re.finditer(
                pattern,
                q,
                re.IGNORECASE,
            ):
                raw = match.group(0)

                sort_key = (
                    match.start(),
                    -len(raw),
                    family_index,
                    pattern_index,
                )

                entity = _entity(
                    name="family_code",
                    raw_value=raw,
                    value=family.code,
                    confidence=0.96,
                    source="family_pattern",
                )

                current = best_by_code.get(
                    family.code
                )

                if (
                    current is None
                    or sort_key < current[0]
                ):
                    best_by_code[
                        family.code
                    ] = (
                        sort_key,
                        entity,
                    )

    if best_by_code:
        ordered = sorted(
            best_by_code.values(),
            key=lambda item: item[0],
        )

        return [
            entity
            for _sort_key, entity in ordered
        ]

    # Bestaande contextgevoelige fallback voor
    # natuurlijke BB-U-vragen.
    bb_u_context_terms = (
        "voorraad",
        "op voorraad",
        "beschikbaar",
        "prijs",
        "kost",
        "kosten",
        "voordelen",
        "nadelen",
        "voor- en nadelen",
    )

    if any(
        term in q.lower()
        for term in bb_u_context_terms
    ):
        match = re.search(
            r"\bu(?:\s+voor)?\s+(\d{3,4})\b",
            q,
            re.IGNORECASE,
        )

        if match:
            return [
                _entity(
                    name="family_code",
                    raw_value=match.group(0),
                    value="BB-U",
                    confidence=0.90,
                    source=(
                        "contextual_bb_u_pattern"
                    ),
                )
            ]

    return []


def detect_product_family(
    question: str,
) -> DetectedEntity | None:
    """
    Backward-compatible singular wrapper.
    """

    families = detect_product_families(
        question
    )

    return (
        families[0]
        if families
        else None
    )



def detect_belt_width(
    question: str,
    family_code: str | None,
) -> DetectedEntity | None:
    q = question or ""

    explicit_patterns = (
        r"\bbandbreedte\s*(?:van\s*)?(\d{3,4})\b",
        r"\bbb\s*(\d{3,4})\b",
        r"\bb\s*=\s*(\d{3,4})\b",
        r"\bband\s+van\s+(\d{3,4})\s*mm\b",
        r"\b(\d{3,4})\s*mm\s*(?:band|bandbreedte)\b",
        r"\bvoor\s*(\d{3,4})\b",
    )

    for pattern in explicit_patterns:
        match = re.search(pattern, q, re.IGNORECASE)
        if not match:
            continue

        width = int(match.group(1))

        if 300 <= width <= 3000:
            return _entity(
                name="belt_width_mm",
                raw_value=match.group(1),
                value=width,
                confidence=0.98,
                source="explicit_width_pattern",
            )

    # Voor Belle Banne-families is één los maatgetal meestal
    # voldoende sterk om als bandbreedte te interpreteren.
    #
    # Dit doen we bewust NIET voor TPH, omdat daar een los getal
    # ook een andere constructiemaat kan zijn.
    loose_width_families = {
        "BB-U",
        "BB-H",
        "BB-P",
        "BB-R",
    }

    # Compacte BB-U-notaties zoals "BB U1800" bevatten geen
    # woordgrens v??r het maatgetal en worden daarom niet door
    # de generieke losse-getal-detectie gevonden.
    if family_code == "BB-U":
        match = re.search(
            r"\bu\s*(\d{3,4})\b",
            q,
            re.IGNORECASE,
        )

        if match:
            width = int(match.group(1))

            if 300 <= width <= 3000:
                return _entity(
                    name="belt_width_mm",
                    raw_value=match.group(1),
                    value=width,
                    confidence=0.94,
                    source="bb_u_compact_width_pattern",
                )

    if family_code not in loose_width_families:
        return None

    candidates = []

    for raw in re.findall(r"\b(\d{3,4})\b", q):
        value = int(raw)

        if 300 <= value <= 3000:
            candidates.append(value)

    candidates = list(dict.fromkeys(candidates))

    if len(candidates) == 1:
        return _entity(
            name="belt_width_mm",
            raw_value=str(candidates[0]),
            value=candidates[0],
            confidence=0.90,
            source="family_context_width_inference",
        )

    return None


def detect_band_code(
    question: str,
) -> DetectedEntity | None:
    q = question or ""

    natural_language_prefixes = {
        "VAN",
        "VOOR",
        "MET",
        "ZONDER",
        "TOT",
        "PER",
        "BIJ",
        "EN",
        "AAN",
        "OP",
        "VIA",
        "FOR",
        "AND",
        "THE",
    }

    # Expliciet "band B12" heeft de hoogste zekerheid.
    match = re.search(
        r"\bband\s+([a-z]{1,3}[\s-]?\d{1,3})\b",
        q,
        re.IGNORECASE,
    )

    if match:
        value = re.sub(
            r"[\s-]+",
            "",
            match.group(1),
        ).upper()
        prefix_match = re.match(r"[A-Z]+", value)
        prefix = prefix_match.group(0) if prefix_match else ""
        has_separator = bool(re.search(r"[\s-]", match.group(1)))

        # "band van 120 mm" beschrijft een dimensie en is geen
        # expliciete bandcode. Pas dezelfde lexicale guard toe
        # voordat het vroege explicit-band pad een entity teruggeeft.
        if not (
            has_separator
            and prefix in natural_language_prefixes
        ):
            return _entity(
                name="band_code",
                raw_value=match.group(1),
                value=value,
                confidence=0.96,
                source="explicit_band_pattern",
            )

    # PROMATI_BANDCODE_VERSION_GUARD_V1
    #
    # Daarna een voorzichtig standalone patroon, zoals B12.
    #
    # Gebruik finditer zodat we ook de positie/context van een
    # kandidaat kennen. Dat voorkomt dat softwareversies zoals
    # V3, V4, V10 of V13 per ongeluk als transportbandcode
    # worden geÃ¯nterpreteerd.
    matches = re.finditer(
        r"\b([a-z]{1,3}[\s-]?\d{1,3})\b",
        q,
        re.IGNORECASE,
    )

    version_context = bool(
        re.search(
            r"\b(?:"
            r"versie|version|release|patch|build|"
            r"comparison|diagnostics?|orchestrator|"
            r"api|openapi|endpoint|parser|software|"
            r"model|schema|code|runtime"
            r")\b",
            q,
            re.IGNORECASE,
        )
    )

    for match in matches:
        raw = match.group(1)
        value = re.sub(r"[\s-]+", "", raw).upper()

        # PROMATI_BANDCODE_FALSE_POSITIVE_GUARD_V3
        #
        # Standalone kandidaten direct na een punt zijn
        # bestandsextensies en geen transportbandcodes.
        #
        # Voorbeelden:
        # - script.ps1
        # - test_promati_regression_v1.ps1
        #
        # Een echte standalone PS1 blijft geldig, omdat daar
        # geen punt direct voor de match staat.
        match_start = match.start(1)

        if (
            match_start > 0
            and q[match_start - 1] == "."
        ):
            continue

        # PROMATI_BANDCODE_FALSE_POSITIVE_GUARD_V2
        #
        # Het standalone patroon staat ook vormen toe zoals
        # "R 5". Daardoor werden natuurlijke taalconstructies
        # zoals "van 5" ten onrechte VAN5.
        #
        # Alleen woord+nummer-kandidaten met een separator
        # worden tegen deze lexicale denylist gecontroleerd.
        # Compact geschreven codes zoals R5/E950/B12 blijven
        # daardoor ongemoeid.
        #
        # Expliciete formuleringen zoals "band VAN5" of
        # "band V3" zijn al eerder door explicit_band_pattern
        # afgehandeld en worden hier dus niet geraakt.
        raw_prefix_match = re.match(
            r"^([a-z]{1,3})",
            raw,
            re.IGNORECASE,
        )

        raw_prefix = (
            raw_prefix_match.group(1).upper()
            if raw_prefix_match
            else ""
        )

        has_separator = bool(
            re.search(r"[\s-]", raw)
        )

        if (
            has_separator
            and raw_prefix
            in natural_language_prefixes
        ):
            continue

        # Een losse V+nummer-kandidaat in software-/versiecontext
        # is gÃ©Ã©n bandcode.
        #
        # Voorbeelden die hierdoor worden genegeerd:
        # - Comparison V3.1
        # - patch V4
        # - API V10
        # - PromatiGPT V13
        #
        # Expliciet "band V3" blijft geldig, omdat het expliciete
        # band-patroon hierboven al vÃ³Ã³r deze standalone-logica
        # wordt afgehandeld.
        if re.fullmatch(
            r"V\d{1,3}",
            value,
            re.IGNORECASE,
        ):
            suffix = q[
                match.end():
                min(len(q), match.end() + 10)
            ]

            decimal_version = bool(
                re.match(
                    r"\.\d+\b",
                    suffix,
                    re.IGNORECASE,
                )
            )

            if version_context or decimal_version:
                continue

        # Productnotaties zoals BB 1800 horen hier niet thuis.
        if value.startswith("BB") and len(re.sub(r"\D", "", value)) >= 3:
            continue

        # Bekende product-/materiaalcodes mogen niet als
        # standalone transportbandcode worden ge?nterpreteerd.
        #
        # Expliciete formuleringen zoals "band B12" zijn hierboven
        # al afgehandeld en blijven dus altijd geldig.
        if (
            re.fullmatch(r"RVS(?:304|316)", value, re.IGNORECASE)
            or value.upper() == "M3"
        ):
            continue

        # In TPH-productcontext zijn HD/ND + maatnotaties geen
        # transportbandcodes. Een expliciete formulering
        # "band HD750" is hierboven al met hogere zekerheid verwerkt.
        if (
            re.search(r"\btph\b", q, re.IGNORECASE)
            and re.fullmatch(
                r"(?:HD|ND)\d{2,4}",
                value,
                re.IGNORECASE,
            )
        ):
            continue

        return _entity(
            name="band_code",
            raw_value=raw,
            value=value,
            confidence=0.82,
            source="standalone_band_pattern",
        )

    return None


def detect_multi_band_codes(
    question: str,
) -> DetectedEntity | None:
    q = question or ""

    match = re.search(
        r"\b([A-Z]{1,3}\d{2,4})\s+of\s+([A-Z]{1,3}\d{2,4})\b",
        q,
        re.IGNORECASE,
    )

    if match is None:
        return None

    code_1 = match.group(1).upper()
    code_2 = match.group(2).upper()

    if code_1 == code_2:
        return None

    return _entity(
        name="band_codes",
        raw_value=match.group(0),
        value=[code_1, code_2],
        confidence=0.95,
        source="multi_band_pair_pattern",
    )


def detect_line_code(
    question: str,
) -> DetectedEntity | None:
    q = question or ""

    # Bestaand expliciet patroon:
    # "lijn MV2" / "line MV2".
    match = re.search(
        r"\b(?:lijn|line)\s+([a-z0-9_-]+)\b",
        q,
        re.IGNORECASE,
    )

    if match:
        return _entity(
            name="lijn_code",
            raw_value=match.group(1),
            value=match.group(1).upper(),
            confidence=0.82,
            source="explicit_line_pattern",
        )

    # Natuurlijke assetcontext:
    # "band R5 op MV2", "band R5 op GSL".
    #
    # Dit is uitsluitend een context-HINT.
    # De asset resolver blijft de autoriteit die bepaalt
    # of band, installatie en gebied werkelijk bij elkaar horen.
    match = re.search(
        r"\bop\s+([a-z][a-z0-9_-]{1,20})\b",
        q,
        re.IGNORECASE,
    )

    if not match:
        return None

    raw_value = match.group(1)
    value = raw_value.upper()

    # Alleen code-achtige waarden accepteren.
    #
    # Cijfers:
    # MV1, MV2, HOO6, HOO7, BR1, E200, E300...
    #
    # Underscore:
    # GROTE_KADE, KLEINE_KADE, STORT_O, STORT_W...
    #
    # Letter-only bekende installatie-/gebiedcodes:
    # GSL, PEFA, SIFA, MENGERIJ, PELLET, SINTER.
    looks_like_context_code = (
        bool(re.search(r"\d", value))
        or "_" in value
        or value in {
            "GSL",
            "PEFA",
            "SIFA",
            "MENGERIJ",
            "PELLET",
            "SINTER",
        }
    )

    if not looks_like_context_code:
        return None

    return _entity(
        name="lijn_code",
        raw_value=raw_value,
        value=value,
        confidence=0.90,
        source="explicit_context_code_pattern",
    )



# PROMATI_DIAGNOSTICS_ROUTING_V1

DIAGNOSTICS_STRONG_TERMS = (
    "diagnose",
    "diagnostiek",
    "diagnostics",
    "debug",
    "foutanalyse",
    "root cause",
    "sql",
    "database",
    "postgres",
    "postgresql",
    "openapi",
    "orchestrator",
    "viewdef",
    "view definition",
    "view-definition",
    "view health",
    "dependency",
    "dependencies",
    "afhankelijkheid",
    "afhankelijkheden",
    "lineage",
    "inspection pipeline",
    "inspectie pipeline",
    "inspectieketen",
    "rowcount",
    "row_count",
    "parser",
    "vw_",
    "sb_",
)

DIAGNOSTICS_CONTEXT_TERMS = (
    "api",
    "endpoint",
    "route",
    "service",
    "database",
    "postgres",
    "postgresql",
    "sql",
    "schema",
    "tabel",
    "table",
    "pipeline",
    "lineage",
    "parser",
    "dependency",
    "afhankelijk",
    "orchestrator",
    "openapi",
    "rowcount",
    "row_count",
)

DIAGNOSTICS_ACTION_TERMS = (
    "waarom",
    "controleer",
    "onderzoek",
    "diagnose",
    "debug",
    "zoek uit",
    "analyseer",
    "vergelijk",
    "oorzaak",
    "fout",
    "probleem",
    "ontbreekt",
    "ontbreken",
    "valt weg",
    "vallen weg",
)


# PROMATI_DIAGNOSTICS_META_ROUTING_V1

DIAGNOSTICS_META_SYSTEM_TERMS = (
    "comparison",
    "api",
    "openapi",
    "orchestrator",
    "endpoint",
)

DIAGNOSTICS_META_ACTION_TERMS = (
    "status",
    "controleer",
    "controleren",
    "check",
    "actief",
    "active",
    "werkt",
    "werking",
    "draait",
    "running",
    "routing",
    "route",
)

DIAGNOSTICS_META_CONTROL_TERMS = (
    "status",
    "controleer",
    "controleren",
    "check",
    "actief",
    "active",
    "werkt",
    "werking",
    "draait",
    "running",
)


def is_diagnostics_meta_system_query(
    question: str,
) -> bool:
    """
    Herkent smalle beheer/meta-vragen over PROMATI runtime,
    routing en comparison-versies.

    Belangrijk:
    expliciete asset-/inspectiesignalen krijgen voorrang en
    worden niet door deze meta-route overgenomen.
    """

    q = (question or "").casefold()

    has_meta_subject = any(
        term in q
        for term in DIAGNOSTICS_META_SYSTEM_TERMS
    )

    has_meta_action = any(
        term in q
        for term in DIAGNOSTICS_META_ACTION_TERMS
    )

    # "routing" kan ook zelf het systeemonderwerp zijn,
    # maar routing allÃ©Ã©n is niet genoeg.
    has_routing_control = (
        "routing" in q
        and any(
            term in q
            for term in DIAGNOSTICS_META_CONTROL_TERMS
        )
    )

    # Expliciete assetcontext moet inspection blijven.
    explicit_asset_signal = bool(
        re.search(
            r"\b(?:"
            r"band|bandcode|band_code|"
            r"schraper|scraper|"
            r"meshoogte|"
            r"inspection_key|"
            r"lijn_code"
            r")\b",
            q,
            re.IGNORECASE,
        )
    )

    # Ook concrete lijnvragen beschermen, bv. "lijn EO1".
    explicit_line_signal = bool(
        re.search(
            r"\blijn\s+[a-z]{1,4}\s*-?\s*\d+\b",
            q,
            re.IGNORECASE,
        )
    )

    if explicit_asset_signal or explicit_line_signal:
        return False

    return (
        (has_meta_subject and has_meta_action)
        or has_routing_control
    )



# PROMATI_ORCHESTRATOR_CROSS_SOURCE_ROUTING_V1
def is_cross_source_diagnostics_query(
    question: str,
) -> bool:
    q = (question or "").casefold()

    explicit_cross_source = any(
        term in q
        for term in (
            "cross_source",
            "cross-source",
            "cross source",
            "crosssource",
        )
    )

    explicit_chain = any(
        term in q
        for term in (
            "productketen",
            "product keten",
            "product chain",
            "org-keten",
            "org keten",
            "organisatieketen",
            "organisatie keten",
        )
    )

    multi_source_check = (
        "rag" in q
        and "api" in q
        and any(
            term in q
            for term in (
                "sql",
                "odoo",
                "routering",
                "routing",
                "functie",
                "functies",
            )
        )
        and any(
            term in q
            for term in (
                "controleer",
                "diagnose",
                "diagnostiek",
                "diagnostics",
                "vergelijk",
                "check",
            )
        )
    )

    return (
        explicit_cross_source
        or explicit_chain
        or multi_source_check
    )


def detect_diagnostics_score(
    question: str,
) -> float:
    q = (question or "").casefold()

    score = 0.0

    # Cross-source is een expliciete diagnostics-vraag en moet
    # zelfstandig boven de diagnostics threshold van 0.55 komen.
    if is_cross_source_diagnostics_query(q):
        score += 0.70

    # Diagnostics Meta-Routing V1:
    # smalle runtime/routing/comparison-vragen moeten de
    # diagnostics threshold van 0.55 zelfstandig kunnen halen.
    if is_diagnostics_meta_system_query(q):
        score += 0.60

    if any(term in q for term in DIAGNOSTICS_STRONG_TERMS):
        score += 0.70

    if any(term in q for term in DIAGNOSTICS_CONTEXT_TERMS):
        score += 0.20

    if any(term in q for term in DIAGNOSTICS_ACTION_TERMS):
        score += 0.15

    # "beheer" alleen is nog niet voldoende om bijvoorbeeld
    # productbeheer foutief als database-diagnose te behandelen.
    if "beheer" in q:
        score += 0.45

        if any(
            term in q
            for term in DIAGNOSTICS_CONTEXT_TERMS
        ):
            score += 0.20

    return min(score, 1.0)


def detect_diagnostics_objects(
    question: str,
) -> list[str]:
    q = (question or "").casefold()

    matches = re.findall(
        r"\b(?:public\.)?(?:vw|sb|fact)_[a-z0-9_]+\b",
        q,
    )

    result: list[str] = []

    for value in matches:
        value = value.strip()

        if value.startswith("public."):
            value = value.split(".", 1)[1]

        if value not in result:
            result.append(value)

    return result


def detect_diagnostics_domain(
    question: str,
) -> str:
    q = (question or "").casefold()
    objects = detect_diagnostics_objects(q)

    # CP6: concrete diagnostics objects are stronger evidence than loose domain
    # words elsewhere in the question. Keep RFQ polarity protected by CP3.
    if any(
        marker in object_name
        for object_name in objects
        for marker in (
            "vw_mes_lifecycle",
            "inspection",
            "inspectie",
            "meshoogte",
            "sb_inspection",
        )
    ):
        return "inspections"

    if any(
        re.search(
            r"(?:^|_)(?:org|organisatie|function|functie|user|gebruiker|vca)(?:_|$)|internal_help",
            object_name,
        )
        for object_name in objects
    ):
        return "org"

    rfq_is_negated = _is_explicitly_negated(q, NEGATED_RFQ_PATTERN)
    if not rfq_is_negated and any(
        marker in object_name
        for object_name in objects
        for marker in ("rfq", "offerte")
    ):
        return "rfq"

    if is_cross_source_diagnostics_query(q):

        # Expliciete domeinnotatie heeft hoogste prioriteit.
        if re.search(
            r"\b(?:domain|domein)\s*[:=]?\s*products?\b",
            q,
            re.IGNORECASE,
        ):
            return "products"

        if re.search(
            r"\b(?:domain|domein)\s*[:=]?\s*org\b",
            q,
            re.IGNORECASE,
        ):
            return "org"

        product_signal = any(
            term in q
            for term in (
                "productfamilie",
                "product family",
                "productketen",
                "product keten",
                "product-",
                "product ",
                "belle banne",
                "bb-u",
                "bb-h",
                "bb-p",
                "bb-r",
                "prom-kf",
                "prom-ks",
                "belt cleaner",
                "belt-cleaner",
                "odoo",
            )
        )

        org_signal = any(
            term in q
            for term in (
                "org-taak",
                "org taak",
                "organisatie",
                "organisatieketen",
                "organisatie keten",
                "routering",
                "functie",
                "functies",
                "primair",
                "backup",
                "escalatie",
                "wifi_support",
            )
        )

        if product_signal and not org_signal:
            return "products"

        if org_signal and not product_signal:
            return "org"

        # Geen betrouwbare cross-source domeinkeuze:
        # laat bestaande systeem/database-semantiek verder beslissen.

    if is_diagnostics_meta_system_query(q):
        return "system"

    general_org_signal = any(
        term in q
        for term in (
            "organisatiegegevens",
            "organisatie gegevens",
            "organisatie-data",
            "organisatie data",
            "org-gegevens",
            "org gegevens",
            "org-data",
            "org data",
            "org-diagnose",
            "org diagnose",
            "organisatie-diagnose",
            "organisatie diagnose",
            "organisatiekoppeling",
            "organisatie koppeling",
            "org-koppeling",
            "org koppeling",
            "vca-documentatie",
            "vca documentatie",
        )
    )

    org_responsibility_context = (
        any(term in q for term in ("verantwoordelijk", "verantwoordelijke"))
        and any(term in q for term in ("vca", "organisatie", "org"))
    )

    if general_org_signal or org_responsibility_context:
        return "org"

    if not rfq_is_negated and any(
        term in q
        for term in (
            "rfq",
            "offerte",
            "supplier",
            "leverancier",
        )
    ):
        return "rfq"

    if "crm" in q:
        return "crm"

    if any(
        term in q
        for term in (
            "inspectie",
            "inspection",
            "excel",
            "parser",
            "band_code",
            "bandcode",
            "schraper",
            "scraper",
            "meshoogte",
            "inspection_key",
            "vw_mes_lifecycle",
            "position",
            "positie",
        )
    ):
        return "inspections"

    if any(
        term in q
        for term in (
            "api",
            "orchestrator",
            "openapi",
            "endpoint",
            "route",
            "server",
            "service",
            "healthz",
        )
    ):
        return "system"

    return "database"


def detect_diagnostics_mode(
    question: str,
) -> str:
    q = (question or "").casefold()
    objects = detect_diagnostics_objects(q)

    if is_cross_source_diagnostics_query(q):
        return "cross_source"

    if (
        bool(objects)
        and any(
            term in q
            for term in (
                "dependency",
                "dependencies",
                "dependents",
                "afhankelijkheid",
                "afhankelijkheden",
                "waar hangt",
            )
        )
    ):
        return "view_dependencies"

    if (
        bool(objects)
        and (
            "viewdef" in q
            or "view definition" in q
            or "view-definition" in q
            or "pg_get_viewdef" in q
            or "definitie" in q
        )
    ):
        return "view_definition"

    specific_inspection_lineage = any(
        term in q
        for term in (
            "inspection_key",
            "orphan",
            "zonder items",
            "bronbestand",
            "source_file",
            "sheet",
        )
    )

    generic_inspection_lineage = (
        "lineage" in q
        and any(
            term in q
            for term in (
                "inspectie",
                "inspection",
                "inspectieketen",
                "inspection pipeline",
            )
        )
    )

    if (
        specific_inspection_lineage
        or generic_inspection_lineage
    ):
        return "inspection_lineage"

    if any(
        term in q
        for term in (
            "assetmodel",
            "asset model",
            "bandmapping",
            "band mapping",
            "scraper_family",
            "scraper_role",
            "record_role",
            "parser root cause",
            "parser_root_cause",
            "onbekend",
        )
    ):
        return "asset_model_health"

    if any(
        term in q
        for term in (
            "inspection pipeline",
            "inspectie pipeline",
            "inspectieketen",
        )
    ):
        return "inspection_pipeline"

    if any(
        term in q
        for term in (
            "sql deep dive",
            "sql-deep-dive",
            "deep dive",
            "deep-dive",
            "zoek uit waarom",
            "waarom valt",
            "waarom vallen",
            "waarom ontbreekt",
            "waarom ontbreken",
            "waarom mist",
            "wegvallen",
            "valt weg",
            "vallen weg",
            "vergelijk de views",
            "vergelijk views",
        )
    ):
        return "sql_deep_dive"

    if any(
        term in q
        for term in (
            "view health",
            "rowcount",
            "row count",
            "row_count",
            "daling",
            "data drop",
            "keten health",
            "database health",
        )
    ):
        return "view_health"

    if "sql" in q:
        return "sql_deep_dive"

    return "overview"


def detect_diagnostics_depth(
    question: str,
    mode: str,
) -> str:
    q = (question or "").casefold()

    if mode in {
        "sql_deep_dive",
        "view_health",
        "cross_source",
    }:
        return "deep"

    if any(
        term in q
        for term in (
            "deep",
            "diep",
            "diepgaand",
            "volledig",
            "recursive",
            "recursief",
        )
    ):
        return "deep"

    return "normal"


def _score_domain(
    question: str,
    family: DetectedEntity | None,
    band: DetectedEntity | None,
    line: DetectedEntity | None,
    scope: DetectedEntity | None,
) -> tuple[float, float, float, float, float]:
    q = question or ""

    product_score = 0.0
    inspection_score = 0.0
    technical_score = 0.0
    rfq_score = 0.0
    org_score = 0.0

    product_negated = _domain_is_negated(q, Domain.PRODUCT)
    inspection_negated = _domain_is_negated(q, Domain.INSPECTION)
    technical_negated = _domain_is_negated(q, Domain.TECHNICAL)
    rfq_negated = _domain_is_negated(q, Domain.RFQ)
    org_negated = _domain_is_negated(q, Domain.ORG)

    if family and not product_negated:
        product_score += 0.75

    if not product_negated and any(term in q for term in PRODUCT_DOMAIN_TERMS):
        product_score += 0.20

    if not inspection_negated and any(term in q for term in INSPECTION_DOMAIN_TERMS):
        inspection_score += 0.65

    if band and not inspection_negated:
        inspection_score += 0.20

        # Een expliciete formulering "band <code>" is een sterke
        # asset-intentie, ook zonder woorden als inspectie/slijtage.
        #
        # Productcontext krijgt bewust voorrang:
        # "prijs van band X" wordt dus niet automatisch inspection.
        #
        # Een losse code zonder het woord "band" blijft eveneens
        # conservatief via standalone_band_pattern.
        #
        # explicit_band_pattern routes to inspection
        if (
            band.source == "explicit_band_pattern"
            and band.confidence >= 0.90
            and family is None
            and not any(
                term in q
                for term in PRODUCT_DOMAIN_TERMS
            )
        ):
            inspection_score += 0.40

        # Een betrouwbare bandcode plus natuurlijke statuscontext
        # is voldoende om de vraag als inspectievraag te behandelen.
        if (
            band.confidence >= 0.80
            and any(
                term in q
                for term in BAND_CONTEXT_INSPECTION_TERMS
            )
        ):
            inspection_score += 0.45

    if line and not inspection_negated:
        inspection_score += 0.15

    # Alleen een door PROMATI-data bevestigde scope telt mee.
    # Scope alleen is bewust onvoldoende om alles naar inspection te sturen.
    if scope and not inspection_negated:
        inspection_score += 0.25

        if any(
            term in q
            for term in SCOPE_INSPECTION_TERMS
        ):
            inspection_score += 0.45

        # PROMATI_SCOPE_BAND_PAIR_ROUTING_V13_1
        #
        # Een canonical scope + betrouwbare bandcandidate is op zichzelf
        # voldoende assetcontext om INSPECTION te routeren. De band hoeft
        # hier nog niet bij de scope bewezen te zijn: dat wordt downstream
        # door de asset-resolver gevalideerd. Zo levert een conflict een
        # gerichte clarification op in plaats van geen execution step.
        #
        # Productcontext blokkeert deze bonus bewust.
        if (
            band is not None
            and band.confidence >= 0.80
            and family is None
            and not any(
                term in q
                for term in PRODUCT_DOMAIN_TERMS
            )
        ):
            inspection_score += 0.25

    # Conservatieve technische routering.
    # Alleen duidelijke technische termen zijn hier voldoende.
    # Productnamen blijven via de bestaande productrouter lopen.
    if not technical_negated and any(
        term in q
        for term in (
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
            "technische punten",
        )
    ):
        technical_score += 0.75

    # CP5: RFQ is a first-class business domain. Explicit RFQ/offerte
    # terminology is sufficient; readiness and data-quality terminology is
    # deliberately bounded to RFQ context to avoid hijacking generic status
    # or diagnostics questions.
    if not rfq_negated:
        has_explicit_rfq = any(
            term in q
            for term in (
                "rfq",
                "offerte",
                "offertevraag",
                "offerte vraag",
                "offerte-aanvraag",
                "offerteaanvraag",
                "request for quotation",
            )
        )
        if has_explicit_rfq:
            rfq_score += 0.85

        # Readiness is an established RFQ-specialist mode and can therefore
        # route without repeating the acronym in the same question.
        if any(
            term in q
            for term in (
                "readiness",
                "rfq-ready",
                "rfq ready",
            )
        ):
            rfq_score += 0.65

        if has_explicit_rfq and any(
            term in q
            for term in (
                "readiness",
                "ready",
                "datakwaliteit",
                "data kwaliteit",
                "status",
                "bestaande",
                "record",
                "records",
            )
        ):
            rfq_score += 0.15

    # Conservatieve organisatie-routering.
    # PROMATI_ORG_ROLE_ROUTING_V2
    #
    # Conservatieve organisatie-routering voor natuurlijke
    # vragen over rollen, personen en verantwoordelijkheden.
    #
    # Het losse woord "functie" wordt hieronder apart
    # behandeld, omdat dit ook technisch/productmatig kan zijn.
    #
    # Gebruik bewust niet het losse token "it":
    # dat is te kort en mag geen functie/persoon impliceren.
    org_role_terms = (
        "rol",
        "coördinator",
        "coordinator",
        "verantwoordelijk",
        "contactpersoon",
        "kerntaken",
        "bevoegdheden",
        "organigram",
        "functieomschrijving",
        "documentverantwoordelijkheden",
    )

    if not org_negated and any(
        term in q
        for term in org_role_terms
    ):
        org_score += 0.75

    # "Functie" is ambigu:
    #
    #   "Wat is de functie van Aaron Thys?"
    #       -> organisatie
    #
    #   "Wat is de functie van een bandschraper?"
    #       -> product/techniek
    #
    # Daarom alleen ORG-score toevoegen wanneer geen duidelijke
    # product- of technische context aanwezig is.
    if "functie" in q and not org_negated:
        product_or_technical_terms = (
            "bandschraper",
            "schraper",
            "transportband",
            "bandtransporteur",
            "product",
            "machine",
            "installatie",
            "component",
            "onderdeel",
        )

        has_product_or_technical_context = any(
            term in q
            for term in product_or_technical_terms
        )

        if not has_product_or_technical_context:
            org_score += 0.75

    # Natuurlijke Promati-locatievragen.
    # Locatietermen alleen zijn niet genoeg: de vraag moet
    # expliciet over Promati gaan.
    if (
        not org_negated
        and "promati" in q
        and any(
            term in q
            for term in (
                "gevestigd",
                "vestiging",
                "vestigingen",
                "adres",
                "locatie",
                "telefoonnummer",
                "openingstijden",
            )
        )
    ):
        org_score += 0.80

    return (
        min(product_score, 1.0),
        min(inspection_score, 1.0),
        min(technical_score, 1.0),
        min(rfq_score, 1.0),
        min(org_score, 1.0),
    )


def detect_intent(
    question: str,
    primary_domain: Domain | None,
) -> str:
    q = question or ""

    if primary_domain == Domain.PRODUCT:
        if any(
            term in q
            for term in (
                "voorraad",
                "op voorraad",
                "beschikbaar",
            )
        ):
            return "inventory_lookup"

        if any(
            term in q
            for term in (
                "prijs",
                "kost",
                "kosten",
            )
        ):
            return "price_lookup"

        if any(
            term in q
            for term in (
                "vergelijk",
                "verschil",
                "welke schraper",
                "welke uitvoering",
                "kiezen",
                "keuze",
            )
        ):
            return "product_selection"

        if any(
            term in q
            for term in (
                "voordelen",
                "nadelen",
                "voor- en nadelen",
            )
        ):
            return "advantages_disadvantages"

        return "product_lookup"

    if primary_domain == Domain.INSPECTION:
        if any(
            term in q
            for term in (
                "trend",
                "slijtage",
                "ontwikkelt",
                "ontwikkeling",
                "historie",
                "tijdlijn",
                "verloop",
                "lifecycle",
            )
        ):
            return "inspection_trend"

        if any(
            term in q
            for term in (
                "laatste",
                "meest recente",
                "actuele",
                "recentste",
                "vorige keer",
                "laatste keer",
            )
        ):
            return "inspection_latest"

        # PROMATI_REPLACEMENT_ADVICE_ROUTING_V1
        #
        # Alleen expliciete toekomstige/actieve vervangadviesvragen.
        # Historische vervangvragen worden hier bewust niet op
        # het losse woord "vervangen" gematcht.
        if any(
            term in q
            for term in (
                "moet er iets vervangen",
                "moet iets vervangen",
                "moet vervangen worden",
                "moeten vervangen worden",
                "wat moet vervangen",
                "welke schraper moet vervangen",
                "welke schrapers moeten vervangen",
                "vervangadvies",
                "vervang advies",
            )
        ):
            return "replacement_advice"

        if any(
            term in q
            for term in (
                "onderhoud",
                "prioriteit",
                "wat moet eerst",
            )
        ):
            return "maintenance_priority"

        return "inspection_lookup"

    if primary_domain == Domain.TECHNICAL:
        return "technical_lookup"

    if primary_domain == Domain.RFQ:
        if any(
            term in q
            for term in (
                "readiness",
                "ready",
                "datakwaliteit",
                "data kwaliteit",
                "vrijgeven",
                "klaar",
            )
        ):
            return "rfq_readiness"

        if "status" in q:
            return "rfq_status"

        return "rfq_lookup"

    if primary_domain == Domain.DIAGNOSTICS:
        return (
            "diagnostics_"
            + detect_diagnostics_mode(q)
        )

    if primary_domain == Domain.ORG:
        return "org_lookup"

    return "unknown"


# PROMATI_MULTI_INTENT_TASK_DERIVATION_SHADOW_V1
def _ordered_intent_task_domains(
    primary_domain: Domain | None,
    domains: list[Domain],
) -> list[Domain]:
    """Stable primary-first domain order, without changing QueryPlan.domains."""
    ordered: list[Domain] = []

    if primary_domain is not None:
        ordered.append(primary_domain)

    for domain in domains or []:
        if domain not in ordered:
            ordered.append(domain)

    return ordered


def _intent_task_scope(
    domain: Domain,
    entities: dict[str, DetectedEntity],
    product_families: list[DetectedEntity],
) -> dict[str, object]:
    """Copy only already-grounded deterministic scope into the shadow task."""
    scope: dict[str, object] = {}

    if domain == Domain.PRODUCT:
        family_codes = [
            str(item.value).strip()
            for item in (product_families or [])
            if item.value is not None
            and str(item.value).strip()
        ]
        if family_codes:
            scope["product_family_codes"] = list(
                dict.fromkeys(family_codes)
            )

    if domain in {
        Domain.INSPECTION,
        Domain.DIAGNOSTICS,
    }:
        for entity_name in (
            "band_code",
            "lijn_code",
            "scope_code",
            "scope_type",
            "area_code",
            "installation_code",
            "scraper_family",
        ):
            entity = entities.get(entity_name)
            if (
                entity is not None
                and entity.value is not None
            ):
                scope[entity_name] = entity.value

    return scope


# PROMATI_MULTI_INTENT_SAME_DOMAIN_FACET_SHADOW_V2
def _requested_subset(
    requested: list[str],
    allowed: tuple[str, ...],
) -> list[str]:
    """Preserve existing requested-information order inside one facet group."""
    return [
        item
        for item in requested
        if item in allowed
    ]


def _product_facet_task_specs(
    primary_intent: str,
    requested: list[str],
) -> list[dict[str, object]] | None:
    """Split live commerce from descriptive product evidence when both exist.

    V2 remains shadow-only. It deliberately does not split product families: the
    existing family scope stays attached to every semantic task.
    """
    commerce = _requested_subset(
        requested,
        ("inventory", "price"),
    )
    profile = _requested_subset(
        requested,
        ("strengths", "limitations", "selection_advice"),
    )

    if not commerce or not profile:
        return None

    commerce_intent = (
        primary_intent
        if primary_intent in {"inventory_lookup", "price_lookup"}
        else (
            "inventory_lookup"
            if "inventory" in commerce
            else "price_lookup"
        )
    )

    if "selection_advice" in profile:
        profile_intent = "product_selection"
    elif any(
        item in profile
        for item in ("strengths", "limitations")
    ):
        profile_intent = "advantages_disadvantages"
    else:
        profile_intent = "product_lookup"

    specs = [
        {
            "label": "commerce",
            "intent": commerce_intent,
            "requested_information": commerce,
        },
        {
            "label": "profile",
            "intent": profile_intent,
            "requested_information": profile,
        },
    ]

    specs.sort(
        key=lambda spec: (
            0
            if spec["intent"] == primary_intent
            else 1
        )
    )
    return specs


def _inspection_facet_task_specs(
    primary_intent: str,
    requested: list[str],
) -> list[dict[str, object]] | None:
    # PROMATI_P4_15B_CROSS_DOMAIN_TASK_SPECS_V1
    p4_15b_cross_domain_specs = []

    def _p4_15b_add_cross_domain_spec(label, domain, intent, requirement_set_id, requested_information):
        p4_15b_cross_domain_specs.append(
            {
                "label": label,
                "domain": domain,
                "intent": intent,
                "requirement_set_id": requirement_set_id,
                "requested_information": tuple(requested_information),
            }
        )

    if "inspection_observation" in requested:
        _p4_15b_add_cross_domain_spec(
            "inspection_observation", Domain.INSPECTION,
            "inspection_observation", "inspection_observation.v1",
            ("inspection_observation",),
        )

    if "theory_guidance" in requested:
        _p4_15b_add_cross_domain_spec(
            "theory_guidance", Domain.TECHNICAL,
            "theory_guidance", "theory_guidance.v1",
            ("theory_guidance",),
        )

    if "replacement_advice" in requested:
        _p4_15b_add_cross_domain_spec(
            "replacement_advice", Domain.INSPECTION,
            "replacement_advice", "replacement_advice.v1",
            ("replacement_advice",),
        )

    if "article_lookup" in requested:
        _p4_15b_add_cross_domain_spec(
            "article_lookup", Domain.PRODUCT,
            "article_lookup", "article_lookup.v1",
            ("article_lookup",),
        )

    if "performance_history" in requested:
        _p4_15b_add_cross_domain_spec(
            "performance_history", Domain.INSPECTION,
            "performance_history", "performance_history.v1",
            ("performance_history",),
        )

    if "product_information" in requested:
        _p4_15b_add_cross_domain_spec(
            "product_information", Domain.PRODUCT,
            "product_lookup", "product_lookup.v1",
            ("product_information",),
        )

    if "selection_criteria" in requested:
        _p4_15b_add_cross_domain_spec(
            "selection_criteria", Domain.PRODUCT,
            "product_selection", "product_selection.v1",
            ("selection_criteria",),
        )

    if "product_fit_analysis" in requested:
        _p4_15b_add_cross_domain_spec(
            "product_fit_analysis", Domain.PRODUCT,
            "product_fit_analysis", "product_fit_analysis.v1",
            ("product_fit_analysis",),
        )

    if p4_15b_cross_domain_specs:
        return p4_15b_cross_domain_specs

    """Split latest-state evidence from lifecycle/history evidence.

    Explicit replacement advice stays integrated because the existing richer
    replacement_advice route intentionally covers latest state, lifecycle,
    executed replacement history and advice together.
    """
    if "replacement_advice" in requested:
        return None

    # PROMATI_P4_14W_GOLDEN_MV1_INSPECTION_MAINTENANCE_TASKS_V1_FACET_SPLIT
    maintenance = _requested_subset(
        requested,
        ("maintenance_priority",),
    )
    if maintenance:
        latest_for_status = _requested_subset(
            requested,
            ("latest_measurements",),
        )
        specs = []
        if latest_for_status or primary_intent in {
            "inspection_latest",
            "inspection_lookup",
            "maintenance_priority",
        }:
            specs.append(
                {
                    "label": "latest",
                    "intent": "inspection_latest",
                    "requested_information": (
                        latest_for_status
                        or ["latest_measurements"]
                    ),
                }
            )

        specs.append(
            {
                "label": "maintenance",
                "intent": "maintenance_priority",
                "requested_information": maintenance,
            }
        )

        if len(specs) >= 2:
            specs.sort(
                key=lambda spec: (
                    0
                    if spec["intent"] == primary_intent
                    else 1
                )
            )
            return specs

    latest = _requested_subset(
        requested,
        ("latest_measurements",),
    )
    history = _requested_subset(
        requested,
        ("lifecycle_trend", "replacement_events"),
    )

    if not latest or not history:
        return None

    specs = [
        {
            "label": "latest",
            "intent": "inspection_latest",
            "requested_information": latest,
        },
        {
            "label": "history",
            "intent": "inspection_trend",
            "requested_information": history,
        },
    ]

    unassigned = [
        item
        for item in requested
        if item not in {
            "latest_measurements",
            "lifecycle_trend",
            "replacement_events",
        }
    ]

    specs.sort(
        key=lambda spec: (
            0
            if spec["intent"] == primary_intent
            else 1
        )
    )

    if unassigned:
        specs[0]["requested_information"] = (
            list(specs[0]["requested_information"])
            + unassigned
        )

    return specs


def _same_domain_facet_task_specs(
    domain: Domain,
    primary_intent: str,
    requested: list[str],
) -> list[dict[str, object]] | None:
    if domain == Domain.PRODUCT:
        return _product_facet_task_specs(
            primary_intent,
            requested,
        )

    if domain == Domain.INSPECTION:
        return _inspection_facet_task_specs(
            primary_intent,
            requested,
        )

    return None


def build_intent_tasks_shadow(
    question: str,
    *,
    primary_domain: Domain | None,
    domains: list[Domain],
    primary_intent: str,
    entities: dict[str, DetectedEntity],
    product_families: list[DetectedEntity],
) -> list[IntentTask]:
    """Derive semantic shadow tasks without activating runtime behavior.

    V2 preserves the V1 cross-domain contract and adds bounded same-domain
    decomposition only where distinct existing evidence intents already exist.
    Planner, executor, Phase C and presentation still consume legacy fields.
    """
    tasks: list[IntentTask] = []
    task_index = 0

    for domain in _ordered_intent_task_domains(
        primary_domain,
        domains,
    ):
        task_intent = (
            primary_intent
            if domain == primary_domain
            else detect_intent(
                question,
                domain,
            )
        )
        requested = detect_requested_information(
            question,
            domain,
        )
        scope = _intent_task_scope(
            domain,
            entities,
            product_families,
        )
        facet_specs = _same_domain_facet_task_specs(
            domain,
            task_intent,
            requested,
        )

        if facet_specs is None:
            requirement_set = get_requirement_set(task_intent)
            requirement_set_id = (
                requirement_set.requirement_set_id
                if requirement_set is not None
                else None
            )
            task_index += 1
            tasks.append(
                IntentTask(
                    task_id=(
                        f"task_{task_index}_{domain.value}"
                    ),
                    domain=domain,
                    intent=task_intent,
                    requested_information=requested,
                    scope=scope,
                    primary=(
                        domain == primary_domain
                    ),
                    required=True,
                    polarity="requested",
                    evidence_requirement_set_id=requirement_set_id,
                    coverage_requirement=requirement_set_id,
                )
            )
            continue

        for facet_position, spec in enumerate(
            facet_specs,
            start=1,
        ):
            facet_intent = str(spec["intent"])
            requirement_set = get_requirement_set(facet_intent)
            requirement_set_id = (
                requirement_set.requirement_set_id
                if requirement_set is not None
                else spec.get("requirement_set_id")
            )
            task_index += 1
            tasks.append(
                IntentTask(
                    task_id=(
                        f"task_{task_index}_{spec.get('domain', domain).value}_"
                        f"{spec['label']}"
                    ),
                    domain=spec.get("domain", domain),
                    intent=facet_intent,
                    requested_information=list(
                        spec["requested_information"]
                    ),
                    scope=dict(scope),
                    primary=(
                        domain == primary_domain
                        and facet_position == 1
                    ),
                    required=True,
                    polarity="requested",
                    evidence_requirement_set_id=requirement_set_id,
                    coverage_requirement=requirement_set_id,
                    source=(
                        "deterministic_same_domain_facet_shadow_v2"
                    ),
                )
            )

    return tasks


# PROMATI_CONVERSATION_SCOPE_GROUNDING_V1
#
# Bounded conversationele grounding.
#
# De actuele gebruikersvraag blijft altijd ongewijzigd.
# Alleen expliciete structured active_scope mag worden
# geerfd en die scope wordt opnieuw canonical gevalideerd.
def _conversation_active_scope(
    conversation_context: dict | None,
) -> dict:

    if not isinstance(
        conversation_context,
        dict,
    ):
        return {}

    mode = str(
        conversation_context.get(
            "reference_mode"
        )
        or ""
    ).strip().lower()

    if mode != "inherit_active_scope":
        return {}

    active_scope = (
        conversation_context.get(
            "active_scope"
        )
    )

    if not isinstance(
        active_scope,
        dict,
    ):
        return {}

    return active_scope


def _conversation_code(
    value,
) -> str | None:

    if value is None:
        return None

    code = str(
        value
    ).strip()

    if not code:
        return None

    return (
        code
        .replace(" ", "_")
        .upper()
    )


def _validated_conversation_scope(
    active_scope: dict,
) -> dict | None:
    """
    Valideer geerfde scope tegen dezelfde canonical
    assetcatalogus als de gewone scope-resolver.

    Fail-closed:
    - geen invented scopes;
    - typed area blijft area;
    - typed installation blijft installation;
    - conflicterende contextvelden worden geweigerd.
    """

    if not isinstance(
        active_scope,
        dict,
    ):
        return None

    scope_code = _conversation_code(
        active_scope.get(
            "scope_code"
        )
    )

    scope_type = str(
        active_scope.get(
            "scope_type"
        )
        or ""
    ).strip().lower()

    area_code = _conversation_code(
        active_scope.get(
            "area_code"
        )
    )

    installation_code = (
        _conversation_code(
            active_scope.get(
                "installation_code"
            )
        )
    )

    if (
        scope_type
        and scope_type
        not in {
            "area",
            "installation",
        }
    ):
        return None

    # Typed area moet via catalog["areas"] worden
    # gevalideerd. De generieke validate_scope_code()
    # kiest bij gedeelde codes bewust installation eerst.
    if (
        scope_type == "area"
        or (
            not scope_type
            and area_code
            and not scope_code
            and not installation_code
        )
    ):
        candidate_code = (
            scope_code
            or area_code
        )

        if not candidate_code:
            return None

        try:
            catalog = get_scope_catalog()
        except Exception:
            return None

        candidate = (
            catalog
            .get(
                "areas",
                {},
            )
            .get(
                candidate_code
            )
        )

        if not isinstance(
            candidate,
            dict,
        ):
            return None

        payload = dict(
            candidate
        )

    else:
        candidate_code = (
            scope_code
            or installation_code
            or area_code
        )

        if not candidate_code:
            return None

        try:
            check = validate_scope_code(
                candidate_code
            )
        except Exception:
            return None

        if not isinstance(
            check,
            dict,
        ):
            return None

        if not check.get(
            "valid"
        ):
            return None

        candidate = check.get(
            "scope"
        )

        if not isinstance(
            candidate,
            dict,
        ):
            return None

        payload = dict(
            candidate
        )

    canonical_code = (
        _conversation_code(
            payload.get(
                "canonical_code"
            )
        )
    )

    resolved_type = str(
        payload.get(
            "scope_type"
        )
        or ""
    ).strip().lower()

    resolved_area = (
        _conversation_code(
            payload.get(
                "area_code"
            )
        )
    )

    resolved_installation = (
        _conversation_code(
            payload.get(
                "installation_code"
            )
        )
    )

    if not canonical_code:
        return None

    if (
        scope_type
        and resolved_type
        != scope_type
    ):
        return None

    if (
        scope_code
        and canonical_code
        != scope_code
    ):
        return None

    if (
        area_code
        and resolved_area
        != area_code
    ):
        return None

    if (
        installation_code
        and resolved_installation
        != installation_code
    ):
        return None

    payload[
        "canonical_code"
    ] = canonical_code

    payload[
        "area_code"
    ] = resolved_area

    payload[
        "installation_code"
    ] = resolved_installation

    payload[
        "matched_alias"
    ] = canonical_code

    payload[
        "source"
    ] = (
        "conversation_context_validated"
    )

    payload[
        "confidence"
    ] = 1.0

    return {
        "status": "resolved",
        "scope": payload,
        "candidates": [],
        "roles": {
            "active": [],
            "excluded": [],
            "comparison": [],
            "mentioned": [],
        },
        "mode":
            "inherited_active_scope",
    }


# PROMATI_SCOPE_SCRAPER_FAMILY_FILTER_V1
#
# Smalle inspection-filter voor expliciete
# scraperfamilie-verwijzingen zoals "U-posities".
#
# Dit is bewust NIET hetzelfde als scraper_type:
# U 1000, U 1200, U 1200 REV en U 1400
# behoren allemaal tot scraper_family U.
def detect_inspection_scraper_family_filter(
    question: str,
) -> DetectedEntity | None:

    q = (
        question
        or ""
    ).casefold()

    match = re.search(
        r"\bu\s*[- ]?\s*posities?\b",
        q,
    )

    if match is None:
        return None

    return _entity(
        name="scraper_family",
        raw_value=match.group(0),
        value="U",
        confidence=0.99,
        source=(
            "inspection_scraper_family_pattern"
        ),
    )


def understand_query(
    question: str,
    conversation_context: dict | None = None,
) -> QueryPlan:
    normalized = normalize_question(question)

    inherited_active_scope = (
        _conversation_active_scope(
            conversation_context
        )
    )

    # PROMATI_PHASE_A_QUERY_CLASS_SHADOW_A1A
    query_class = classify_query(normalized)

    # PROMATI_PHASE_A_QUERYCLASS_GATE_A1B
    #
    # Gate v????r entity extraction.
    # BUSINESS en diagnostics-SYSTEM_META vallen hier doorheen.
    query_class_value = query_class.value

    if query_class_value == "conversational":
        return QueryPlan(
            original_question=question,
            normalized_question=normalized,
            query_class=query_class,
            primary_domain=None,
            domains=[],
            intent="none",
            entities={},
            requested_information=[],
            residual_terms=[],
            confidence=1.0,
            clarification_required=False,
            clarification_question=None,
            execution_steps=[],
        )

    if query_class_value == "unknown":
        return QueryPlan(
            original_question=question,
            normalized_question=normalized,
            query_class=query_class,
            primary_domain=None,
            domains=[],
            intent="unknown",
            entities={},
            requested_information=[],
            residual_terms=[],
            confidence=0.0,
            clarification_required=True,
            clarification_question=(
                "Kun je aangeven of je informatie zoekt over "
                "een product, inspectie, technische vraag, "
                "RFQ of organisatie?"
            ),
            execution_steps=[],
        )

    if (
        query_class_value == "system_meta"
        and is_pure_system_meta_query(normalized)
    ):
        return QueryPlan(
            original_question=question,
            normalized_question=normalized,
            query_class=query_class,
            primary_domain=None,
            domains=[],
            intent="system_meta",
            entities={},
            requested_information=[],
            residual_terms=[],
            confidence=1.0,
            clarification_required=False,
            clarification_question=None,
            execution_steps=[],
        )


    product_families = detect_product_families(
        normalized
    )

    family = (
        product_families[0]
        if product_families
        else None
    )

    family_code = (
        str(product_families[0].value)
        if len(product_families) == 1
        else None
    )

    width = detect_belt_width(
        normalized,
        family_code,
    )

    band = detect_band_code(normalized)
    multi_band = detect_multi_band_codes(normalized)

    # PROMATI_PHASE_A_BAND_CANDIDATE_SHADOW_A2B
    # Shadow only: this value is deliberately not used by
    # entities, routing, clarification or QueryPlan.
    _band_candidate_shadow = classify_band_candidate_shadow(
        normalized,
        band,
    )

    # PROMATI_PHASE_A2C_SAFE_PARTIAL_ACTIVATION_V1
    #
    # Only statuses proven safe by the A2c runtime
    # counterfactual are activated:
    #
    # - MENTION_ONLY:
    #   mentioned code is not the active business object.
    #
    # - COMPARISON_MEMBER:
    #   singular band_code is replaced by typed comparison
    #   context such as comparison_scope_codes.
    #
    # VALIDATED and UNRESOLVED intentionally retain legacy
    # behavior in A2c V1.
    if (
        _band_candidate_shadow is not None
        and _band_candidate_shadow.status.value
        in {"mention_only", "comparison_member"}
    ):
        band = None
    line = detect_line_code(normalized)

    # PROMATI_SCOPE_CONTEXT_UNDERSTANDING_V13_1
    #
    # Resolve canonical scope plus pragmatische rol:
    # active / excluded / comparison / mentioned.
    scope_resolution = resolve_scope_context(
        normalized
    )

    # PROMATI_CONVERSATION_SCOPE_GROUNDING_V1
    #
    # Expliciete scope/band/lijn uit de actuele vraag
    # wint altijd van oudere conversationele context.
    current_scope_status = str(
        scope_resolution.get(
            "status"
        )
        if isinstance(
            scope_resolution,
            dict,
        )
        else ""
    ).strip().lower()

    may_inherit_scope = (
        bool(
            inherited_active_scope
        )
        and current_scope_status
        not in {
            "resolved",
            "ambiguous",
            "comparison",
        }
        and band is None
        and line is None
        and not multi_band
    )

    if may_inherit_scope:
        inherited_resolution = (
            _validated_conversation_scope(
                inherited_active_scope
            )
        )

        if inherited_resolution is not None:
            scope_resolution = (
                inherited_resolution
            )

    scope_status = str(
        scope_resolution.get("status") or ""
    ).lower()

    scope_payload = (
        scope_resolution.get("scope")
        if isinstance(scope_resolution, dict)
        else None
    )

    scope: DetectedEntity | None = None

    if (
        scope_status == "resolved"
        and isinstance(scope_payload, dict)
        and scope_payload.get("canonical_code")
    ):
        scope = _entity(
            name="scope_code",
            raw_value=scope_payload.get("matched_alias"),
            value=scope_payload.get("canonical_code"),
            confidence=float(
                scope_payload.get("confidence", 1.0)
            ),
            source=str(
                scope_payload.get(
                    "source",
                    "scope_resolver",
                )
            ),
        )

        # Voorkom dat installatiecodes zoals MV1, MV2, BR1 of EO1
        # door het generieke standalone-bandpatroon als transportband
        # worden doorgegeven. Expliciet "band MV1" blijft ongemoeid.
        if (
            band is not None
            and band.source == "standalone_band_pattern"
            and str(band.value).upper()
            == str(scope.value).upper()
        ):
            band = None

    scope_candidates: list[str] = []

    if (
        scope_status == "ambiguous"
        and isinstance(scope_resolution, dict)
    ):
        for candidate in (
            scope_resolution.get("candidates")
            or []
        ):
            if not isinstance(candidate, dict):
                continue

            code = candidate.get("canonical_code")
            if code:
                scope_candidates.append(str(code))

        scope_candidates = list(
            dict.fromkeys(scope_candidates)
        )

    # PROMATI_PHASE_A2D_EXECUTION_GROUNDING_V1
    # Preserve candidate evidence for routing/scoring,
    # but distinguish it from validated execution identity.
    _band_unresolved = (
        band is not None
        and _band_candidate_shadow is not None
        and _band_candidate_shadow.status.value == "unresolved"
    )
    (
        product_score,
        inspection_score,
        technical_score,
        rfq_score,
        org_score,
    ) = _score_domain(
        normalized,
        family,
        band,
        line,
        scope,
    )

    diagnostics_score = detect_diagnostics_score(
        normalized
    )

    diagnostics_mode = detect_diagnostics_mode(
        normalized
    )

    diagnostics_domain = detect_diagnostics_domain(
        normalized
    )

    diagnostics_objects = detect_diagnostics_objects(
        normalized
    )

    diagnostics_depth = detect_diagnostics_depth(
        normalized,
        diagnostics_mode,
    )

    primary_domain: Domain | None = None
    domains: list[Domain] = []

    domain_scores = [
        (Domain.PRODUCT, product_score),
        (Domain.INSPECTION, inspection_score),
        (Domain.TECHNICAL, technical_score),
        (Domain.RFQ, rfq_score),
        (Domain.ORG, org_score),
        (Domain.DIAGNOSTICS, diagnostics_score),
    ]

    for domain, score in domain_scores:
        if score >= 0.55:
            domains.append(domain)

    qualified_domains = [
        (domain, score)
        for domain, score in domain_scores
        if score >= 0.55
    ]

    if qualified_domains:
        primary_domain = max(
            qualified_domains,
            key=lambda item: item[1],
        )[0]

    confidence = max(
        product_score,
        inspection_score,
        technical_score,
        rfq_score,
        org_score,
        diagnostics_score,
    )

    entities: dict[str, DetectedEntity] = {}

    # PROMATI_SCOPE_SCRAPER_FAMILY_FILTER_V1
    #
    # Alleen scoped inspection-vragen krijgen deze
    # family-filter. Band-specifieke legacy-routes
    # blijven hierdoor ongemoeid.
    if (
        scope is not None
        and primary_domain == Domain.INSPECTION
    ):
        scraper_family_filter = (
            detect_inspection_scraper_family_filter(
                normalized
            )
        )

        if scraper_family_filter is not None:
            entities[
                "scraper_family"
            ] = scraper_family_filter

    # PROMATI_PHASE_A2D_EXECUTION_GROUNDING_V1
    execution_blockers: list[ExecutionBlocker] = []

    if _band_unresolved and band is not None:
        execution_blockers.append(
            ExecutionBlocker(
                blocker_type=(
                    ExecutionBlockerType.UNRESOLVED_REQUIRED_ENTITY
                ),
                entity_name="band_code",
                candidate_value=band.value,
                reason="band_candidate_unresolved",
            )
        )

    # Legacy family_code blijft alleen bestaan
    # wanneer exact één productfamilie is genoemd.
    if len(product_families) == 1:
        entities["family_code"] = (
            product_families[0]
        )

    if width:
        entities["belt_width_mm"] = width

    if band and not _band_unresolved:
        entities["band_code"] = band

    if line:
        entities["lijn_code"] = line

    if diagnostics_score >= 0.55:
        entities["diagnostics_mode"] = _entity(
            name="diagnostics_mode",
            raw_value=diagnostics_mode,
            value=diagnostics_mode,
            confidence=diagnostics_score,
            source="diagnostics_router",
        )

        entities["diagnostics_domain"] = _entity(
            name="diagnostics_domain",
            raw_value=diagnostics_domain,
            value=diagnostics_domain,
            confidence=diagnostics_score,
            source="diagnostics_router",
        )

        entities["diagnostics_depth"] = _entity(
            name="diagnostics_depth",
            raw_value=diagnostics_depth,
            value=diagnostics_depth,
            confidence=diagnostics_score,
            source="diagnostics_router",
        )

        if diagnostics_objects:
            entities["diagnostics_objects"] = _entity(
                name="diagnostics_objects",
                raw_value=diagnostics_objects,
                value=diagnostics_objects,
                confidence=0.98,
                source="diagnostics_object_pattern",
            )

    if scope and isinstance(scope_payload, dict):
        entities["scope_code"] = scope

        scope_type = scope_payload.get("scope_type")
        area_code = scope_payload.get("area_code")
        installation_code = scope_payload.get(
            "installation_code"
        )

        if scope_type:
            entities["scope_type"] = _entity(
                name="scope_type",
                raw_value=scope_type,
                value=scope_type,
                confidence=scope.confidence,
                source="scope_resolver",
            )

        if area_code:
            entities["area_code"] = _entity(
                name="area_code",
                raw_value=area_code,
                value=area_code,
                confidence=scope.confidence,
                source="scope_resolver",
            )

        if installation_code:
            entities["installation_code"] = _entity(
                name="installation_code",
                raw_value=installation_code,
                value=installation_code,
                confidence=scope.confidence,
                source="scope_resolver",
            )

    if scope_candidates:
        entities["scope_candidates"] = _entity(
            name="scope_candidates",
            raw_value=scope_candidates,
            value=scope_candidates,
            confidence=0.50,
            source="scope_resolver_ambiguous",
        )

    scope_roles = (
        scope_resolution.get("roles")
        if isinstance(scope_resolution, dict)
        else None
    )

    if isinstance(scope_roles, dict):
        role_entity_names = {
            "excluded": "excluded_scope_codes",
            "comparison": "comparison_scope_codes",
            "mentioned": "mentioned_scope_codes",
        }

        for role_name, entity_name in role_entity_names.items():
            codes = []

            for candidate in (
                scope_roles.get(role_name)
                or []
            ):
                if not isinstance(candidate, dict):
                    continue

                code = candidate.get("canonical_code")

                if code:
                    codes.append(str(code))

            codes = list(dict.fromkeys(codes))

            if codes:
                entities[entity_name] = _entity(
                    name=entity_name,
                    raw_value=codes,
                    value=codes,
                    confidence=0.95,
                    source="scope_context_roles",
                )

    scope_mode = str(
        scope_resolution.get("mode")
        or ""
    )

    if scope_mode:
        entities["scope_context_mode"] = _entity(
            name="scope_context_mode",
            raw_value=scope_mode,
            value=scope_mode,
            confidence=1.0,
            source="scope_context_roles",
        )

    intent = detect_intent(
        normalized,
        primary_domain,
    )

    requested_information = detect_requested_information(
        normalized,
        primary_domain,
    )

    # PROMATI_INSPECTION_RICHEST_FIT_INTENT_V1
    #
    # Een expliciet gevraagd vervangadvies vereist de rijkere
    # band_deep_analysis-bron. requested_information bewaart de
    # overige gevraagde inspection-facetten.
    #
    # Dit is geen multi-step routing:
    # - original_question blijft ongewijzigd;
    # - er blijft één inspection execution step;
    # - pure trendvragen blijven inspection_trend;
    # - historische vervangvragen hebben geen replacement_advice
    #   facet en worden dus niet gepromoveerd.
    if (
        primary_domain == Domain.INSPECTION
        and "replacement_advice"
        in requested_information
    ):
        intent = "replacement_advice"

    scope_ambiguous = (
        scope_status == "ambiguous"
        and bool(scope_candidates)
    )

    comparison_codes = []

    if isinstance(scope_roles, dict):
        for candidate in (
            scope_roles.get("comparison")
            or []
        ):
            if not isinstance(candidate, dict):
                continue

            code = candidate.get("canonical_code")

            if code:
                comparison_codes.append(str(code))

    comparison_codes = list(
        dict.fromkeys(comparison_codes)
    )

    scope_comparison = (
        scope_status == "comparison"
        and len(comparison_codes) >= 2
    )

    clarification_required = (
        (
            primary_domain != Domain.DIAGNOSTICS
            and (
                scope_ambiguous
                or scope_comparison
            )
        )
        or primary_domain is None
        or confidence < 0.55
    )
    # PROMATI_PHASE_A2D_EXECUTION_GROUNDING_V1
    # Clarification is derived UX; execution safety is
    # independently enforced by the planner blocker gate.
    if execution_blockers:
        clarification_required = True

    clarification_question = None

    if (
        primary_domain != Domain.DIAGNOSTICS
        and scope_comparison
    ):
        clarification_question = (
            "Ik herken een vergelijking tussen "
            + " en ".join(comparison_codes)
            + ". Multi-scope vergelijking wordt nog "
            + "niet stil als Ã©Ã©n actief filter uitgevoerd."
        )
    elif (
        primary_domain != Domain.DIAGNOSTICS
        and scope_ambiguous
    ):
        clarification_question = (
            "Welke PROMATI-installatie bedoel je: "
            + ", ".join(scope_candidates)
            + "?"
        )
    elif clarification_required:
        clarification_question = (
            "Kun je aangeven of je informatie zoekt over "
            "een product, inspectie, technische vraag, RFQ of organisatie?"
        )

    # PROMATI_PHASE_A2D_EXECUTION_GROUNDING_V1
    if execution_blockers:
        clarification_question = (
            "Ik herken de inspectievraag, maar bandcode "
            + str(execution_blockers[0].candidate_value)
            + " is nog niet gevalideerd. "
            + "Kun je deze bandcode bevestigen?"
        )
    # PROMATI_PHASE_A2E_MULTI_BAND_EXECUTION_GROUNDING_V1
    # Multi-band grounding is valid, but execution currently only
    # supports a singular band_code. Preserve singular routing/scoring
    # upstream, then replace the execution entity at this final boundary.
    if (
        multi_band is not None
        and band is not None
        and isinstance(multi_band.value, list)
        and len(multi_band.value) == 2
        and str(band.value).upper()
        == str(multi_band.value[0]).upper()
        and "comparison_scope_codes" not in entities
        and not execution_blockers
    ):
        entities.pop(
            "band_code",
            None,
        )

        entities["band_codes"] = multi_band

        execution_blockers.append(
            ExecutionBlocker(
                blocker_type=(
                    ExecutionBlockerType.UNSUPPORTED_MULTI_BAND_EXECUTION
                ),
                entity_name="band_codes",
                candidate_value=multi_band.value,
                reason="multi_band_execution_unsupported",
            )
        )

    intent_tasks = build_intent_tasks_shadow(
        normalized,
        primary_domain=primary_domain,
        domains=domains,
        primary_intent=intent,
        entities=entities,
        product_families=product_families,
    )
    excluded_domains = [
        domain
        for domain in NEGATED_DOMAIN_PATTERNS
        if _domain_is_negated(normalized, domain)
    ]

    return QueryPlan(
        original_question=question,
        normalized_question=normalized,
        query_class=query_class,
        primary_domain=primary_domain,
        domains=domains,
        intent=intent,
        intent_tasks=intent_tasks,
        excluded_domains=excluded_domains,
        multi_intent=(len(intent_tasks) >= 2),
        entities=entities,
        product_families=product_families,
        requested_information=requested_information,
        residual_terms=[],
        confidence=confidence,
        clarification_required=clarification_required,
        clarification_question=clarification_question,
        execution_blockers=execution_blockers,
        execution_steps=[],
    )



# PROMATI_DIAGNOSTICS_DISCOVERY_GUARDS_V1
