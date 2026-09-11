import re
from dataclasses import dataclass

from app.orchestrator.models import (
    DetectedEntity,
    Domain,
    QueryPlan,
)
from app.orchestrator.normalizer import normalize_question
from app.services.scope_resolver import (
    resolve_scope,
    resolve_scope_context,
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
    FamilyPattern(
        code="PROM-KF",
        patterns=(
            r"\bpromati\s+kf\b",
            r"\bkf[\s-]*schraper\b",
        ),
    ),
    FamilyPattern(
        code="PROM-KS",
        patterns=(
            r"\bpromati\s+ks\b",
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
)

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


def detect_product_family(
    question: str,
) -> DetectedEntity | None:
    q = question or ""

    for family in PRODUCT_FAMILY_PATTERNS:
        for pattern in family.patterns:
            match = re.search(pattern, q, re.IGNORECASE)
            if match:
                return _entity(
                    name="family_code",
                    raw_value=match.group(0),
                    value=family.code,
                    confidence=0.96,
                    source="family_pattern",
                )

    # Contextgevoelige fallback voor natuurlijke BB-U-vragen.
    #
    # Een losse notatie "U 1800" is op zichzelf te algemeen.
    # We accepteren die alleen wanneer de vraag duidelijke
    # product-/commerci?le context bevat.
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

    if any(term in q.lower() for term in bb_u_context_terms):
        match = re.search(
            r"\bu(?:\s+voor)?\s+(\d{3,4})\b",
            q,
            re.IGNORECASE,
        )

        if match:
            return _entity(
                name="family_code",
                raw_value=match.group(0),
                value="BB-U",
                confidence=0.90,
                source="contextual_bb_u_pattern",
            )

    return None


def detect_belt_width(
    question: str,
    family_code: str | None,
) -> DetectedEntity | None:
    q = question or ""

    explicit_patterns = (
        r"\bbandbreedte\s*(?:van\s*)?(\d{3,4})\b",
        r"\bbb\s*(\d{3,4})\b",
        r"\bb\s*=\s*(\d{3,4})\b",
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

        standalone_word_prefix_denylist = {
            # Nederlands
            "VAN",
            "MET",
            "TOT",
            "PER",
            "BIJ",
            "EN",

            # PROMATI_BANDCODE_FALSE_POSITIVE_GUARD_V4
            #
            # Natuurlijke voorzetsel + nummer-combinaties zijn
            # geen transportbandcodes.
            #
            # Voorbeelden:
            # - "aan 127" -> niet AAN127
            # - "op 127"  -> niet OP127
            # - "via 127" -> niet VIA127
            #
            # Alleen separatorvormen worden geraakt door de
            # bestaande V2-logica. Compacte codes zoals OP127
            # blijven geldig. Expliciet "band AAN127" wordt
            # eerder al door explicit_band_pattern afgehandeld.
            "AAN",
            "OP",
            "VIA",

            # Engels
            "FOR",
            "AND",
            "THE",
        }

        if (
            has_separator
            and raw_prefix
            in standalone_word_prefix_denylist
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
        )
    )

    if general_org_signal:
        return "org"

    if any(
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
) -> tuple[float, float, float, float]:
    q = question or ""

    product_score = 0.0
    inspection_score = 0.0
    technical_score = 0.0
    org_score = 0.0

    if family:
        product_score += 0.75

    if any(term in q for term in PRODUCT_DOMAIN_TERMS):
        product_score += 0.20

    if any(term in q for term in INSPECTION_DOMAIN_TERMS):
        inspection_score += 0.65

    if band:
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

    if line:
        inspection_score += 0.15

    # Alleen een door PROMATI-data bevestigde scope telt mee.
    # Scope alleen is bewust onvoldoende om alles naar inspection te sturen.
    if scope:
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
    if any(
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
        )
    ):
        technical_score += 0.75

    # Conservatieve organisatie-routering.
    # Gebruik bewust niet het losse token "it":
    # dat is te kort en mag geen functie/persoon impliceren.
    if any(
        term in q
        for term in (
            "wie is verantwoordelijk",
            "functieomschrijving",
            "kerntaken",
            "bevoegdheden",
            "documentverantwoordelijkheden",
            "contactpersoon",
            "organigram",
        )
    ):
        org_score += 0.75

    # Natuurlijke Promati-locatievragen.
    # Locatietermen alleen zijn niet genoeg: de vraag moet
    # expliciet over Promati gaan.
    if (
        "promati" in q
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

        if any(
            term in q
            for term in (
                "onderhoud",
                "prioriteit",
                "wat moet eerst",
                "wat moet vervangen",
            )
        ):
            return "maintenance_priority"

        return "inspection_lookup"

    if primary_domain == Domain.TECHNICAL:
        return "technical_lookup"

    if primary_domain == Domain.DIAGNOSTICS:
        return (
            "diagnostics_"
            + detect_diagnostics_mode(q)
        )

    if primary_domain == Domain.ORG:
        return "org_lookup"

    return "unknown"


def understand_query(question: str) -> QueryPlan:
    normalized = normalize_question(question)

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


    family = detect_product_family(normalized)

    family_code = (
        str(family.value)
        if family is not None
        else None
    )

    width = detect_belt_width(
        normalized,
        family_code,
    )

    band = detect_band_code(normalized)

    # PROMATI_PHASE_A_BAND_CANDIDATE_SHADOW_A2B
    # Shadow only: this value is deliberately not used by
    # entities, routing, clarification or QueryPlan.
    _band_candidate_shadow = classify_band_candidate_shadow(
        normalized,
        band,
    )
    line = detect_line_code(normalized)

    # PROMATI_SCOPE_CONTEXT_UNDERSTANDING_V13_1
    #
    # Resolve canonical scope plus pragmatische rol:
    # active / excluded / comparison / mentioned.
    scope_resolution = resolve_scope_context(
        normalized
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

    (
        product_score,
        inspection_score,
        technical_score,
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
        org_score,
        diagnostics_score,
    )

    entities: dict[str, DetectedEntity] = {}

    if family:
        entities["family_code"] = family

    if width:
        entities["belt_width_mm"] = width

    if band:
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

    return QueryPlan(
        original_question=question,
        normalized_question=normalized,
        query_class=query_class,
        primary_domain=primary_domain,
        domains=domains,
        intent=intent,
        entities=entities,
        requested_information=requested_information,
        residual_terms=[],
        confidence=confidence,
        clarification_required=clarification_required,
        clarification_question=clarification_question,
        execution_steps=[],
    )



# PROMATI_DIAGNOSTICS_DISCOVERY_GUARDS_V1
