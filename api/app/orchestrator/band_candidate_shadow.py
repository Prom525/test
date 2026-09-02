from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Any


# PROMATI_PHASE_A_BAND_CANDIDATE_SHADOW_A2B
#
# Shadow only.
# Nothing in this module may mutate QueryPlan, entities or routing.


class BandGroundingStatus(str, Enum):
    VALIDATED = "validated"
    MENTION_ONLY = "mention_only"
    COMPARISON_MEMBER = "comparison_member"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class BandCandidateShadow:
    value: str
    raw_value: Any
    detector_source: str
    detector_confidence: float
    status: BandGroundingStatus
    reason: str


# Compact forms with prefixes that are also common natural-language
# tokens are not rejected here. They are deliberately marked
# UNRESOLVED so a later grounding stage can decide.
#
# This is fundamentally different from a denylist in detect_band_code:
# the candidate remains observable.
_AMBIGUOUS_LANGUAGE_PREFIXES = frozenset(
    {
        "AL",
        "DE",
        "DIE",
        "ER",
        "GAF",
        "MIN",
        "ORG",
    }
)


def _safe_confidence(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _prefix(value: str) -> str:
    match = re.match(
        r"^([A-Z]{1,3})",
        value or "",
        re.IGNORECASE,
    )

    if not match:
        return ""

    return match.group(1).upper()


def _is_bandcode_meta_mention(question: str) -> bool:
    q = question or ""

    if not re.search(
        r"\bbandcodes?\b",
        q,
        re.IGNORECASE,
    ):
        return False

    return bool(
        re.search(
            r"\b(?:"
            r"gezien|"
            r"herkend|"
            r"geinterpreteerd|"
            r"ge??nterpreteerd|"
            r"interpret\w*|"
            r"parse\w*|"
            r"parser"
            r")\b",
            q,
            re.IGNORECASE,
        )
    )


def _is_comparison_member(
    question: str,
    candidate_value: str,
) -> bool:
    """
    Shadow-only semantic comparison test.

    A comparison verb alone is NOT enough.

    The detected band candidate must itself belong to a
    comparison set containing at least two distinct code-like
    members.

    Examples:
    - "Vergelijk MV1 en MV2."          -> True for MV1
    - "Vergelijk A319 met A320."       -> True for A319
    - "Vergelijk slijtage A319 met
       vergelijkbare installaties."    -> False
    - "Vergelijk BB-U en BB-R met
       problemen op A319."             -> False for A319
    """

    q = question or ""

    if not re.search(
        r"\b(?:"
        r"vergelijk|"
        r"vergelijken|"
        r"versus|"
        r"vs"
        r")\b",
        q,
        re.IGNORECASE,
    ):
        return False

    candidate = re.sub(
        r"[\s-]+",
        "",
        candidate_value or "",
    ).upper()

    if not candidate:
        return False

    # Use the same broad lexical code shape as the legacy
    # standalone detector, but do NOT validate anything here.
    #
    # This is only evidence for comparison membership.
    matches = re.finditer(
        r"\b([a-z]{1,3}[\s-]?\d{1,3})\b",
        q,
        re.IGNORECASE,
    )

    comparison_codes = []

    for match in matches:
        value = re.sub(
            r"[\s-]+",
            "",
            match.group(1),
        ).upper()

        if value not in comparison_codes:
            comparison_codes.append(value)

    return (
        len(comparison_codes) >= 2
        and candidate in comparison_codes
    )




def _is_assumption_context(question: str) -> bool:
    return bool(
        re.search(
            r"\b(?:"
            r"neem\s+aan\s+dat|"
            r"veronderstel\s+dat|"
            r"doe\s+alsof"
            r")\b",
            question or "",
            re.IGNORECASE,
        )
    )


def classify_band_candidate_shadow(
    question: str,
    band: Any | None,
) -> BandCandidateShadow | None:
    """
    Phase-A A2b shadow interpretation.

    IMPORTANT:
    - returns metadata only;
    - does not alter the supplied DetectedEntity;
    - does not determine production validation yet.
    """

    if band is None:
        return None

    value = str(
        getattr(
            band,
            "value",
            "",
        )
        or ""
    ).strip().upper()

    raw_value = getattr(
        band,
        "raw_value",
        None,
    )

    source = str(
        getattr(
            band,
            "source",
            "",
        )
        or ""
    )

    confidence = _safe_confidence(
        getattr(
            band,
            "confidence",
            0.0,
        )
    )


    # Explicit "band X" remains the strongest lexical evidence.
    if source == "explicit_band_pattern":
        return BandCandidateShadow(
            value=value,
            raw_value=raw_value,
            detector_source=source,
            detector_confidence=confidence,
            status=BandGroundingStatus.VALIDATED,
            reason="explicit_band_context",
        )


    # Any unfamiliar detector source remains unresolved in shadow.
    if source != "standalone_band_pattern":
        return BandCandidateShadow(
            value=value,
            raw_value=raw_value,
            detector_source=source,
            detector_confidence=confidence,
            status=BandGroundingStatus.UNRESOLVED,
            reason="unsupported_detector_source",
        )


    # Example:
    # "Waarom wordt AL5 als bandcode gezien?"
    #
    # The code is being DISCUSSED, not necessarily selected as
    # the business entity of the question.
    if _is_bandcode_meta_mention(question):
        return BandCandidateShadow(
            value=value,
            raw_value=raw_value,
            detector_source=source,
            detector_confidence=confidence,
            status=BandGroundingStatus.MENTION_ONLY,
            reason="bandcode_meta_mention",
        )


    # Example:
    # "Vergelijk MV1 en MV2."
    #
    # A standalone regex hit may be one member of a comparison
    # rather than the singular active band entity.
    if _is_comparison_member(question, value):
        return BandCandidateShadow(
            value=value,
            raw_value=raw_value,
            detector_source=source,
            detector_confidence=confidence,
            status=BandGroundingStatus.COMPARISON_MEMBER,
            reason="comparison_context",
        )


    # Example:
    # "Neem aan dat A999 bestaat ..."
    #
    # An explicit assumption is not grounding evidence.
    if _is_assumption_context(question):
        return BandCandidateShadow(
            value=value,
            raw_value=raw_value,
            detector_source=source,
            detector_confidence=confidence,
            status=BandGroundingStatus.UNRESOLVED,
            reason="assumption_is_not_grounding",
        )


    # Ambiguous natural-language prefixes remain candidates.
    # They are NOT suppressed in A2b.
    if _prefix(value) in _AMBIGUOUS_LANGUAGE_PREFIXES:
        return BandCandidateShadow(
            value=value,
            raw_value=raw_value,
            detector_source=source,
            detector_confidence=confidence,
            status=BandGroundingStatus.UNRESOLVED,
            reason="ambiguous_language_prefix_requires_grounding",
        )


    # A2b is shadow-only: preserve current legacy interpretation for
    # ordinary standalone cases until A2c activates real grounding.
    return BandCandidateShadow(
        value=value,
        raw_value=raw_value,
        detector_source=source,
        detector_confidence=confidence,
        status=BandGroundingStatus.VALIDATED,
        reason="legacy_standalone_shadow",
    )
