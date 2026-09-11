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


_SYSTEM_META_TERMS = (
    "orchestrator",
    "router",
    "routering",
    "routing",
    "backend",
    "api-route",
    "api route",
    "api-routes",
    "api routes",
    "endpoint",
    "endpoints",
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
)


_DIAGNOSTICS_META_TERMS = (
    "systeemdiagnose",
    "database bereikbaar",
    "database health",
    "view definition",
    "dependencies",
    "dependency",
    "lineage",
    "inspectiepipeline",
    "inspection pipeline",
    "assetmodel",
    "asset model",
    "productketen",
    "organisatieketen",
    "org-keten",
    "cross-source",
    "cross source",
    "rag, api en sql",
    "rag api sql",
    "bandcodes verkeerd",
    "als bandcode gezien",
)


_CONVERSATIONAL_PREFIXES = (
    "bedankt",
    "dank ",
    "dat ziet er ",
    "dit ziet er ",
    "ik ga hier ",
    "ik ben benieuwd ",
    "dit is lastiger ",
)


def _normalize(value: str) -> str:
    text = (value or "").casefold().strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[?!.]+$", "", text).strip()
    return text


def classify_query(question: str) -> QueryClass:
    """
    Phase-A A1a shadow classifier.

    Belangrijk:
    - bepaalt nog GEEN route;
    - wijzigt geen entities;
    - wijzigt geen research;
    - wijzigt geen clarification;
    - levert alleen observability voor de golden set.
    """
    q = _normalize(question)

    if not q:
        return QueryClass.UNKNOWN

    if q in _CONVERSATIONAL_EXACT:
        return QueryClass.CONVERSATIONAL

    if any(
        q.startswith(prefix)
        for prefix in _CONVERSATIONAL_PREFIXES
    ):
        return QueryClass.CONVERSATIONAL

    if any(
        term in q
        for term in _SYSTEM_META_TERMS
    ):
        return QueryClass.SYSTEM_META

    if any(
        term in q
        for term in _DIAGNOSTICS_META_TERMS
    ):
        return QueryClass.SYSTEM_META

    # Expliciete platform/runtime mededelingen.
    if (
        re.search(
            r"\b(?:python|postgres)\s+\d+(?:\.\d+)*\b",
            q,
        )
        or re.search(
            r"\bversie\s+v?\d+(?:\.\d+)*\b",
            q,
        )
        or re.search(
            r"\b\d+\s+(?:api-)?routes?\s+geladen\b",
            q,
        )
    ):
        return QueryClass.SYSTEM_META

    # Contextloze anaforische vragen zijn bewust UNKNOWN.
    if q in {
        "wat kost die",
        "analyseer de installatie in die afdeling",
    }:
        return QueryClass.UNKNOWN

    # A1a blijft conservatief:
    # alles wat niet duidelijk meta/conversation/unknown is,
    # blijft BUSINESS. A1b mag pas na golden-evaluatie routeren.
    return QueryClass.BUSINESS
