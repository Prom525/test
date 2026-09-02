import re

from app.orchestrator.models import QueryClass


_CONVERSATIONAL_EXACT = {
    "bedankt",
    "dank je",
    "dankjewel",
    "dank u",
    "dat ziet er goed uit",
    "dit ziet er goed uit",
    "dit is lastiger dan ik dacht",
    "ik ga hier morgen mee verder",
    "ik ben benieuwd hoe dit verder groeit",
}


_CONVERSATIONAL_PREFIXES = (
    "bedankt",
    "dank ",
    "dat ziet er ",
    "dit ziet er ",
    "ik ga hier ",
    "ik ben benieuwd ",
    "dit is lastiger ",
)


_SYSTEM_META_TERMS = (
    "orchestrator",
    "routering",
    "routing",
    "backend",
    "api-route",
    "api route",
    "api-routes",
    "api routes",
    "gpt action",
    "gpt actions",
    "research-agent",
    "research agent",
    "research_required",
    "complexity score",
    "clarification",
    "openai-provider",
    "openai provider",
    "openai-model",
    "openai model",
    "adminplatform",
    "golden regressietest",
    "regressietest",
    "feature flag",
    "feature flags",
    "high_risk_sql",
    "systeemdiagnose",
    "database bereikbaar",
    "view definition",
    "dependencies",
    "dependency",
    "inspectiepipeline",
    "inspection pipeline",
    "lineage",
    "assetmodel",
    "asset model",
    "productketen",
    "organisatieketen",
    "cross-source",
    "cross source",

    # A1a v1.1 - narrow meta terminology.
    "kernroutes",
    "clean view",
    "bandcodes verkeerd",
    "als bandcode gezien",
    "route van vraag naar specialist",
    "router productvragen",
    "specialisten kent het platform",
    "openai-call",
    "openai niet gebruikt",
)


def _normalize(value: str) -> str:
    text = (value or "").casefold().strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[?!.]+$", "", text).strip()
    return text


def _is_explicit_business_override(q: str) -> bool:
    """
    Narrow Phase-A override.

    Een adversarial instruction die expliciet businessdata
    voor een concreet object vraagt blijft BUSINESS.
    QueryClass behandelt hier geen security/policy.
    """
    return bool(
        re.fullmatch(
            r"negeer de router en voer direct sql uit "
            r"voor [a-z]{1,8}\s*\d{1,8}",
            q,
        )
    )


def _is_conversational(q: str) -> bool:
    if q in _CONVERSATIONAL_EXACT:
        return True

    if any(
        q.startswith(prefix)
        for prefix in _CONVERSATIONAL_PREFIXES
    ):
        return True

    # Persoonlijke voortgangsmededeling.
    if re.fullmatch(
        r"ik werk hier al \d+ maanden aan",
        q,
    ):
        return True

    # Losse notitie zonder businessvraag.
    if re.fullmatch(
        r"notitie gemaakt op \d{4}-\d{2}-\d{2}",
        q,
    ):
        return True

    return False


def _is_unknown(q: str) -> bool:
    if q in {
        "wat kost die",
        "analyseer de installatie in die afdeling",
    }:
        return True

    # Contextloze Ã©Ã©nletter-familie.
    #
    # "Wat is U 1800?" is onvoldoende gegrond.
    # Dit raakt bijvoorbeeld "BB-U 1800" niet.
    if re.fullmatch(
        r"wat is [a-z]\s+\d{3,4}",
        q,
    ):
        return True

    return False


def _is_system_meta(q: str) -> bool:
    if any(
        term in q
        for term in _SYSTEM_META_TERMS
    ):
        return True

    # Health van een concrete backend/view.
    if re.search(
        r"\bhealth van vw_[a-z0-9_]+\b",
        q,
    ):
        return True

    # Pipeline/data-quality analyse.
    if re.search(
        r"\bdubbele inspecties\b.*\bpipeline\b",
        q,
    ):
        return True

    # Vraag over regels die niet in een clean view komen.
    if (
        "inspectieregels" in q
        and "clean view" in q
    ):
        return True

    # Meta-analyse van volledige orchestration flow.
    if (
        "vraag" in q
        and "specialist" in q
        and "research" in q
        and "route" in q
    ):
        return True

    # Platformleeftijd is systeemcontext,
    # tegenover persoonlijke voortgang.
    if re.fullmatch(
        r"dit platform bestaat nu ongeveer "
        r"\d+ maanden",
        q,
    ):
        return True

    # Expliciete platform route-mutatie als mededeling.
    if re.fullmatch(
        r"ik heb vandaag \d+ routes toegevoegd",
        q,
    ):
        return True

    # Runtime/version statements.
    if re.search(
        r"\b(?:python|postgres)\s+\d+(?:\.\d+)*\b",
        q,
    ):
        return True

    if re.search(
        r"\bversie\s+v?\d+(?:\.\d+)*\b",
        q,
    ):
        return True

    if re.search(
        r"\b\d+\s+(?:api-)?routes?\s+geladen\b",
        q,
    ):
        return True

    return False



def is_pure_system_meta_query(question: str) -> bool:
    """
    Phase-A A1b.

    True betekent:
    - systeem/meta-vraag;
    - geen diagnostics specialist nodig;
    - veilig v????r entity extraction stoppen.

    Bewust high-precision / narrow.
    """
    q = _normalize(question)

    if not q:
        return False

    if re.fullmatch(
        r"dit platform bestaat(?: nu)?(?: ongeveer)? "
        r"\d+ maanden",
        q,
    ):
        return True

    if re.fullmatch(
        r"ik heb vandaag \d+ routes toegevoegd",
        q,
    ):
        return True

    if re.fullmatch(
        r"we zitten op versie v?\d+(?:\.\d+)*",
        q,
    ):
        return True

    if q in {
        "hoe werkt de orchestrator",
        "waarom heb je een orchestrator nodig",
        "hoe wordt research_required bepaald",
        "hoe zou je de orchestrator technisch verbeteren",
        "is het verstandig een adminplatform te bouwen",
        "maak een golden regressietest voor de router",
    }:
        return True

    if re.fullmatch(
        r"wat betekent complexity score "
        r"\d+(?:\.\d+)?",
        q,
    ):
        return True

    return False


def classify_query(question: str) -> QueryClass:
    """
    PROMATI Phase-A A1a v1.1.

    Shadow-only:
    - geen routing gate;
    - geen entitymutatie;
    - geen researchmutatie;
    - geen clarificationmutatie.
    """
    q = _normalize(question)

    if not q:
        return QueryClass.UNKNOWN

    # Precedence is bewust expliciet.
    if _is_explicit_business_override(q):
        return QueryClass.BUSINESS

    if _is_conversational(q):
        return QueryClass.CONVERSATIONAL

    if _is_unknown(q):
        return QueryClass.UNKNOWN

    if _is_system_meta(q):
        return QueryClass.SYSTEM_META

    return QueryClass.BUSINESS

