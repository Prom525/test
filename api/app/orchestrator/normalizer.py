import re


_CONVERSATIONAL_PREFIXES = (
    "wat weet je over ",
    "wat kun je vertellen over ",
    "wat kan je vertellen over ",
    "kun je vertellen over ",
    "kan je vertellen over ",
    "vertel me iets over ",
    "vertel eens iets over ",
    "welke informatie heb je over ",
    "welke informatie is er over ",
    "ik wil informatie over ",
    "ik zoek informatie over ",
)


def _collapse_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _strip_conversational_prefix(value: str) -> str:
    text = value.strip()

    for prefix in _CONVERSATIONAL_PREFIXES:
        if text.startswith(prefix):
            return text[len(prefix):].strip()

    return text


def normalize_question(question: str) -> str:
    """
    Domeinonafhankelijke normalisatie.

    Doel:
    - casing normaliseren;
    - overbodige whitespace verwijderen;
    - gewone conversatie-prefixes verwijderen;
    - inhoudelijke product-/inspectietermen intact laten.

    Geen domeinrouting en geen entity resolution in deze module.
    """
    text = question or ""

    text = text.strip().lower()

    # Typografische varianten normaliseren.
    text = (
        text
        .replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u00a0", " ")
    )

    text = _collapse_whitespace(text)

    # Alleen leidende gesprekstaal verwijderen.
    text = _strip_conversational_prefix(text)

    # Eindinterpunctie die niets aan de betekenis toevoegt.
    text = re.sub(r"[?!.]+$", "", text).strip()

    text = _collapse_whitespace(text)

    return text
