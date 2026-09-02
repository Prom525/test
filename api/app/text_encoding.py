from __future__ import annotations

import re
from typing import Any


def _badness(text: str) -> int:
    if not text:
        return 0

    markers = (
        "\u00c3",          # classic UTF-8 -> latin1/cp1252 mojibake
        "\u00c2",
        "\u00e2\u20ac",  # smart punctuation decoded as cp1252
        "\u00ef\u00ac",  # ligature bytes decoded as latin1/cp1252
        "\ufffd",
    )

    score = sum(text.count(marker) * 4 for marker in markers)
    score += sum(1 for ch in text if 0x80 <= ord(ch) <= 0x9F)
    return score


def _try_utf8_redecode(text: str, encoding: str) -> str:
    try:
        candidate = text.encode(encoding).decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text

    return candidate if _badness(candidate) < _badness(text) else text


def repair_mojibake_text(value: str | None) -> str:
    """Repair common UTF-8/latin1/cp1252 mojibake without changing clean text."""
    if value is None:
        return ""
    if not isinstance(value, str) or not value:
        return value

    text = value

    # Two conservative passes handle double-encoded text while the badness
    # score prevents clean Unicode from being needlessly changed.
    for _ in range(2):
        before = text
        for encoding in ("cp1252", "latin1"):
            text = _try_utf8_redecode(text, encoding)
        if text == before:
            break

    replacements = {
        "\u00e2\u20ac\u00a2": "\u2022",
        "\u00e2\u20ac\u201c": "\u2013",
        "\u00e2\u20ac\u201d": "\u2014",
        "\u00e2\u20ac\u2122": "\u2019",
        "\u00e2\u20ac\u0153": "\u201c",
        "\u00c2\u00ae": "\u00ae",
        "\u00c2\u00a9": "\u00a9",
        "\u00c2\u00b0": "\u00b0",
        "\u00c2\u00b1": "\u00b1",
        "\ufb00": "ff",
        "\ufb01": "fi",
        "\ufb02": "fl",
        "\ufb03": "ffi",
        "\ufb04": "ffl",
        "\ufb05": "ft",
        "\ufb06": "st",
    }

    for bad, good in replacements.items():
        text = text.replace(bad, good)

    # Some old PDF text lost part of a smart-quote byte sequence and leaves
    # a lone 'a-circumflex' pair around a phrase. Only fix paired occurrences.
    text = re.sub(r"\u00e2([^\u00e2\n]{1,80})\u00e2", r"'\1'", text)

    return text


def repair_mojibake_data(value: Any) -> Any:
    """Recursively repair strings in JSON-like data without mutating input."""
    if isinstance(value, str):
        return repair_mojibake_text(value)
    if isinstance(value, dict):
        return {key: repair_mojibake_data(item) for key, item in value.items()}
    if isinstance(value, list):
        return [repair_mojibake_data(item) for item in value]
    if isinstance(value, tuple):
        return tuple(repair_mojibake_data(item) for item in value)
    return value