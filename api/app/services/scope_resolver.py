from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


# PROMATI_GENERALIZED_SCOPE_RESOLVER_V13_1
#
# Doel:
# - natuurlijke gebied/installatiebenamingen herkennen;
# - alleen scopes accepteren die door PROMATI-data zijn bevestigd;
# - area en installation expliciet uit elkaar houden;
# - geen vrije tekst zoals "op" als lijncode accepteren;
# - nog GEEN routering of writes uitvoeren.
#
# Bronnen:
# 1. vw_gpt_band_asset_context:
#    canonical area/installatie + namen
# 2. sb_calendar_line_to_lijn:
#    gecontroleerde natuurlijke lijnnamen
#
# line_alias_map wordt bewust NIET als installation-alias gebruikt.
# Die tabel bevat legacy/group mappings zoals SINTER -> GSL en
# GROTE_KADE -> GSL. Dat is nuttig voor historische lijnnormalisatie,
# maar zou een installation-scope te vroeg terugbrengen tot area GSL.


@dataclass(frozen=True)
class ScopeCandidate:
    scope_type: str
    canonical_code: str
    canonical_name: str | None
    area_code: str | None
    installation_code: str | None
    matched_alias: str
    source: str
    confidence: float


_CACHE_TTL_SECONDS = 300
_catalog_cache: dict[str, Any] | None = None
_catalog_cache_at: float = 0.0
_engine: Engine | None = None


def _get_engine() -> Engine:
    global _engine

    if _engine is not None:
        return _engine

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL ontbreekt")

    _engine = create_engine(
        db_url,
        pool_pre_ping=True,
    )
    return _engine


def _normalize_text(value: Any) -> str:
    text_value = str(value or "").casefold()
    text_value = text_value.replace("_", " ")
    text_value = text_value.replace("-", " ")
    text_value = re.sub(r"[^a-z0-9\s]", " ", text_value)
    text_value = re.sub(r"\s+", " ", text_value).strip()
    return text_value


def _contains_alias(question_norm: str, alias_norm: str) -> bool:
    if not alias_norm:
        return False

    pattern = (
        r"(?<![a-z0-9])"
        + re.escape(alias_norm)
        + r"(?![a-z0-9])"
    )
    return re.search(pattern, question_norm) is not None


def _add_alias(
    aliases: dict[str, list[dict[str, Any]]],
    alias: Any,
    target: dict[str, Any],
) -> None:
    alias_norm = _normalize_text(alias)
    if not alias_norm or len(alias_norm) < 2:
        return

    bucket = aliases.setdefault(alias_norm, [])

    signature = (
        target.get("scope_type"),
        target.get("canonical_code"),
        target.get("area_code"),
        target.get("installation_code"),
        target.get("source"),
    )

    existing = {
        (
            item.get("scope_type"),
            item.get("canonical_code"),
            item.get("area_code"),
            item.get("installation_code"),
            item.get("source"),
        )
        for item in bucket
    }

    if signature not in existing:
        bucket.append(dict(target))


def _build_catalog() -> dict[str, Any]:
    engine = _get_engine()

    aliases: dict[str, list[dict[str, Any]]] = {}
    installations: dict[str, dict[str, Any]] = {}
    areas: dict[str, dict[str, Any]] = {}

    with engine.connect() as conn:
        asset_rows = conn.execute(
            text(
                """
                SELECT
                    area_code,
                    area_name,
                    installation_code,
                    installation_name,
                    process_area,
                    COUNT(DISTINCT band_code_norm) AS n_bands
                FROM public.vw_gpt_band_asset_context
                WHERE
                    area_code IS NOT NULL
                    OR installation_code IS NOT NULL
                GROUP BY
                    area_code,
                    area_name,
                    installation_code,
                    installation_name,
                    process_area
                """
            )
        ).mappings().all()

        for row in asset_rows:
            area_code = (
                str(row.get("area_code")).strip().upper()
                if row.get("area_code")
                else None
            )
            area_name = (
                str(row.get("area_name")).strip()
                if row.get("area_name")
                else None
            )
            installation_code = (
                str(row.get("installation_code")).strip().upper()
                if row.get("installation_code")
                else None
            )
            installation_name = (
                str(row.get("installation_name")).strip()
                if row.get("installation_name")
                else None
            )
            process_area = (
                str(row.get("process_area")).strip()
                if row.get("process_area")
                else None
            )

            if area_code:
                area_target = {
                    "scope_type": "area",
                    "canonical_code": area_code,
                    "canonical_name": area_name or area_code,
                    "area_code": area_code,
                    "installation_code": None,
                    "source": "vw_gpt_band_asset_context.area",
                    "confidence": 0.99,
                }
                areas[area_code] = area_target

                _add_alias(aliases, area_code, area_target)
                _add_alias(aliases, area_name, area_target)

            if installation_code:
                installation_target = {
                    "scope_type": "installation",
                    "canonical_code": installation_code,
                    "canonical_name": (
                        installation_name
                        or installation_code
                    ),
                    "area_code": area_code,
                    "installation_code": installation_code,
                    "source": (
                        "vw_gpt_band_asset_context.installation"
                    ),
                    "confidence": 1.0,
                    "process_area": process_area,
                    "n_bands": int(row.get("n_bands") or 0),
                }

                installations[installation_code] = (
                    installation_target
                )

                _add_alias(
                    aliases,
                    installation_code,
                    installation_target,
                )
                _add_alias(
                    aliases,
                    installation_name,
                    installation_target,
                )

        # Natuurlijke kalendernamen toevoegen, maar uitsluitend
        # wanneer het doel al als canonical installation of area
        # in vw_gpt_band_asset_context bestaat.
        calendar_rows = conn.execute(
            text(
                """
                SELECT DISTINCT
                    line_name,
                    lijn_code
                FROM public.sb_calendar_line_to_lijn
                WHERE
                    line_name IS NOT NULL
                    AND lijn_code IS NOT NULL
                """
            )
        ).mappings().all()

        for row in calendar_rows:
            line_name = str(row.get("line_name") or "").strip()
            target_code = str(
                row.get("lijn_code") or ""
            ).strip().upper()

            target = installations.get(target_code)
            if target is None:
                target = areas.get(target_code)

            if target is None:
                # Bijvoorbeeld kalendercodes die nog niet in de
                # canonical asset-context voorkomen: niet gokken.
                continue

            calendar_target = dict(target)
            calendar_target["source"] = (
                "sb_calendar_line_to_lijn"
            )
            calendar_target["confidence"] = 0.98

            _add_alias(
                aliases,
                line_name,
                calendar_target,
            )

            # Veilige generieke afleiding:
            # "Afgraaflijn MV1" -> basisalias "afgraaflijn".
            # Wanneer meerdere targets dezelfde basis krijgen,
            # wordt die alias later automatisch ambiguous.
            line_norm = _normalize_text(line_name)
            code_norm = _normalize_text(target_code)

            if (
                code_norm
                and line_norm.endswith(" " + code_norm)
            ):
                base_alias = line_norm[
                    : -(len(code_norm) + 1)
                ].strip()
                _add_alias(
                    aliases,
                    base_alias,
                    calendar_target,
                )

            # "Kolenopslag 2" -> "kolenopslag".
            # Alleen numerieke eindtokens verwijderen.
            numeric_base = re.sub(
                r"\s+\d+$",
                "",
                line_norm,
            ).strip()

            if (
                numeric_base
                and numeric_base != line_norm
            ):
                _add_alias(
                    aliases,
                    numeric_base,
                    calendar_target,
                )

    return {
        "aliases": aliases,
        "installations": installations,
        "areas": areas,
    }


def get_scope_catalog(
    force_refresh: bool = False,
) -> dict[str, Any]:
    global _catalog_cache
    global _catalog_cache_at

    now = time.monotonic()

    if (
        not force_refresh
        and _catalog_cache is not None
        and (now - _catalog_cache_at) < _CACHE_TTL_SECONDS
    ):
        return _catalog_cache

    catalog = _build_catalog()
    _catalog_cache = catalog
    _catalog_cache_at = now
    return catalog


def _candidate_from_target(
    alias: str,
    target: dict[str, Any],
) -> ScopeCandidate:
    return ScopeCandidate(
        scope_type=str(target["scope_type"]),
        canonical_code=str(target["canonical_code"]),
        canonical_name=target.get("canonical_name"),
        area_code=target.get("area_code"),
        installation_code=target.get(
            "installation_code"
        ),
        matched_alias=alias,
        source=str(target["source"]),
        confidence=float(target["confidence"]),
    )


def resolve_scope(
    question: str,
) -> dict[str, Any]:
    """
    Resolveert een PROMATI area/installatie uit natuurlijke taal.

    Resultaatstatus:
    - resolved
    - ambiguous
    - not_found
    - unavailable

    Geen vrije tekst wordt als canonical code teruggegeven:
    iedere match moet uit de PROMATI-catalogus komen.
    """
    question_norm = _normalize_text(question)

    if not question_norm:
        return {
            "status": "not_found",
            "scope": None,
            "candidates": [],
        }

    try:
        catalog = get_scope_catalog()
    except Exception as exc:
        return {
            "status": "unavailable",
            "scope": None,
            "candidates": [],
            "error_type": type(exc).__name__,
        }

    aliases = catalog["aliases"]

    matching_aliases = [
        alias
        for alias in aliases
        if _contains_alias(
            question_norm,
            alias,
        )
    ]

    if not matching_aliases:
        return {
            "status": "not_found",
            "scope": None,
            "candidates": [],
        }

    # Langste/meer specifieke natuurlijke naam eerst.
    max_tokens = max(
        len(alias.split())
        for alias in matching_aliases
    )
    token_filtered = [
        alias
        for alias in matching_aliases
        if len(alias.split()) == max_tokens
    ]

    max_chars = max(
        len(alias)
        for alias in token_filtered
    )
    best_aliases = [
        alias
        for alias in token_filtered
        if len(alias) == max_chars
    ]

    candidates_by_key: dict[
        tuple[str, str],
        ScopeCandidate,
    ] = {}

    for alias in best_aliases:
        for target in aliases[alias]:
            candidate = _candidate_from_target(
                alias,
                target,
            )

            key = (
                candidate.scope_type,
                candidate.canonical_code,
            )

            previous = candidates_by_key.get(key)

            if (
                previous is None
                or candidate.confidence
                > previous.confidence
            ):
                candidates_by_key[key] = candidate

    candidates = list(
        candidates_by_key.values()
    )

    # Wanneer dezelfde canonical code zowel area als installation
    # is (bv. HOO6/HOO7), is installation de meest concrete scope.
    codes = {
        candidate.canonical_code
        for candidate in candidates
    }

    if len(codes) == 1:
        installation_candidates = [
            candidate
            for candidate in candidates
            if candidate.scope_type == "installation"
        ]

        if installation_candidates:
            candidates = installation_candidates

    if len(candidates) == 1:
        candidate = candidates[0]

        return {
            "status": "resolved",
            "scope": {
                "scope_type": candidate.scope_type,
                "canonical_code": (
                    candidate.canonical_code
                ),
                "canonical_name": (
                    candidate.canonical_name
                ),
                "area_code": candidate.area_code,
                "installation_code": (
                    candidate.installation_code
                ),
                "matched_alias": (
                    candidate.matched_alias
                ),
                "source": candidate.source,
                "confidence": candidate.confidence,
            },
            "candidates": [],
        }

    return {
        "status": "ambiguous",
        "scope": None,
        "candidates": [
            {
                "scope_type": c.scope_type,
                "canonical_code": c.canonical_code,
                "canonical_name": c.canonical_name,
                "area_code": c.area_code,
                "installation_code": (
                    c.installation_code
                ),
                "matched_alias": c.matched_alias,
                "source": c.source,
                "confidence": c.confidence,
            }
            for c in sorted(
                candidates,
                key=lambda item: (
                    item.scope_type,
                    item.canonical_code,
                ),
            )
        ],
    }



# PROMATI_SCOPE_CONTEXT_ROLES_V13_1
def _scope_dict_from_candidate(
    candidate: ScopeCandidate,
) -> dict[str, Any]:
    return {
        "scope_type": candidate.scope_type,
        "canonical_code": candidate.canonical_code,
        "canonical_name": candidate.canonical_name,
        "area_code": candidate.area_code,
        "installation_code": candidate.installation_code,
        "matched_alias": candidate.matched_alias,
        "source": candidate.source,
        "confidence": candidate.confidence,
    }


def _scope_mention_role(
    question_norm: str,
    start: int,
    end: int,
    *,
    comparison_mode: bool,
) -> str:
    prefix = question_norm[
        max(0, start - 90):start
    ]
    suffix = question_norm[
        end:min(len(question_norm), end + 110)
    ]

    if re.search(
        r"(?:"
        r"\bniet\s+(?:op|bij|van|voor)\s+(?:de\s+|het\s+)?"
        r"|\bzonder\s+(?:de\s+|het\s+)?"
        r"|\bbehalve\s+(?:de\s+|het\s+)?"
        r"|\buitgezonderd\s+(?:de\s+|het\s+)?"
        r")$",
        prefix,
    ):
        return "excluded"

    if re.match(
        r"^\s*(?:"
        r"noem\s+ik\s+alleen\s+ter\s+vergelijking"
        r"|alleen\s+ter\s+vergelijking"
        r"|slechts\s+ter\s+vergelijking"
        r"|is\s+alleen\s+ter\s+vergelijking"
        r")\b",
        suffix,
    ):
        return "mentioned"

    if comparison_mode:
        return "comparison"

    if re.search(
        r"\b(?:op|bij|voor|van)\s+(?:de\s+|het\s+)?$",
        prefix,
    ):
        return "active"

    return "unspecified"


def resolve_scope_context(
    question: str,
) -> dict[str, Any]:
    """
    Resolveert alle canonical scopevermeldingen en kent rollen toe:
    active, excluded, comparison en mentioned.

    Single-scope gedrag en bestaande ambiguous aliases blijven
    backwards compatible met resolve_scope().
    """

    question_norm = _normalize_text(question)

    empty_roles = {
        "active": [],
        "excluded": [],
        "comparison": [],
        "mentioned": [],
    }

    if not question_norm:
        return {
            "status": "not_found",
            "scope": None,
            "candidates": [],
            "roles": empty_roles,
            "mode": "single",
        }

    try:
        catalog = get_scope_catalog()
    except Exception as exc:
        return {
            "status": "unavailable",
            "scope": None,
            "candidates": [],
            "roles": empty_roles,
            "mode": "single",
            "error_type": type(exc).__name__,
        }

    raw_matches: list[tuple[int, int, str]] = []

    for alias in catalog["aliases"]:
        if not alias:
            continue

        pattern = (
            r"(?<![a-z0-9])"
            + re.escape(alias)
            + r"(?![a-z0-9])"
        )

        for match in re.finditer(pattern, question_norm):
            raw_matches.append(
                (match.start(), match.end(), alias)
            )

    if not raw_matches:
        return {
            "status": "not_found",
            "scope": None,
            "candidates": [],
            "roles": empty_roles,
            "mode": "single",
        }

    selected_matches: list[tuple[int, int, str]] = []

    for item in sorted(
        raw_matches,
        key=lambda value: (
            -(value[1] - value[0]),
            value[0],
            value[2],
        ),
    ):
        start, end, _ = item

        overlaps = any(
            not (
                end <= chosen_start
                or start >= chosen_end
            )
            for chosen_start, chosen_end, _ in selected_matches
        )

        if not overlaps:
            selected_matches.append(item)

    selected_matches.sort(key=lambda value: value[0])

    comparison_mode = bool(
        re.search(
            r"\b(?:vergelijk|versus|vs|tegenover)\b",
            question_norm,
        )
    )

    mentions: list[dict[str, Any]] = []

    for start, end, alias in selected_matches:
        candidates = [
            _candidate_from_target(alias, target)
            for target in catalog["aliases"].get(alias, [])
        ]

        codes = {
            item.canonical_code
            for item in candidates
        }

        if len(codes) == 1:
            installations = [
                item
                for item in candidates
                if item.scope_type == "installation"
            ]

            if installations:
                candidates = installations

        role = _scope_mention_role(
            question_norm,
            start,
            end,
            comparison_mode=comparison_mode,
        )

        mentions.append(
            {
                "start": start,
                "end": end,
                "alias": alias,
                "role": role,
                "candidates": [
                    _scope_dict_from_candidate(candidate)
                    for candidate in candidates
                ],
            }
        )

    roles: dict[str, list[dict[str, Any]]] = {
        "active": [],
        "excluded": [],
        "comparison": [],
        "mentioned": [],
    }

    for mention in mentions:
        candidates = mention["candidates"]

        if len(candidates) != 1:
            continue

        candidate = dict(candidates[0])
        role = str(mention["role"])

        candidate["role"] = role
        candidate["mention_start"] = mention["start"]
        candidate["mention_end"] = mention["end"]

        if role in roles:
            roles[role].append(candidate)

    if comparison_mode:
        unique_comparison: dict[
            tuple[str, str],
            dict[str, Any],
        ] = {}

        for mention in mentions:
            if mention["role"] in {"excluded", "mentioned"}:
                continue

            if len(mention["candidates"]) != 1:
                continue

            candidate = dict(mention["candidates"][0])
            key = (
                str(candidate.get("scope_type")),
                str(candidate.get("canonical_code")),
            )
            unique_comparison[key] = candidate

        roles["comparison"] = list(unique_comparison.values())

        if len(roles["comparison"]) >= 2:
            return {
                "status": "comparison",
                "scope": None,
                "candidates": [],
                "roles": roles,
                "mentions": mentions,
                "mode": "comparison",
            }

    if roles["active"]:
        unique_active: dict[
            tuple[str, str],
            dict[str, Any],
        ] = {}

        for candidate in roles["active"]:
            key = (
                str(candidate.get("scope_type")),
                str(candidate.get("canonical_code")),
            )
            unique_active[key] = candidate

        active_values = list(unique_active.values())

        if len(active_values) == 1:
            active = dict(active_values[0])
            active.pop("role", None)
            active.pop("mention_start", None)
            active.pop("mention_end", None)

            return {
                "status": "resolved",
                "scope": active,
                "candidates": [],
                "roles": roles,
                "mentions": mentions,
                "mode": "context_roles",
            }

        return {
            "status": "ambiguous",
            "scope": None,
            "candidates": active_values,
            "roles": roles,
            "mentions": mentions,
            "mode": "context_roles",
        }

    neutral_mentions = [
        mention
        for mention in mentions
        if mention["role"] == "unspecified"
    ]

    if len(neutral_mentions) == 1:
        candidates = neutral_mentions[0]["candidates"]

        if len(candidates) == 1:
            return {
                "status": "resolved",
                "scope": dict(candidates[0]),
                "candidates": [],
                "roles": roles,
                "mentions": mentions,
                "mode": "context_roles",
            }

        if len(candidates) > 1:
            return {
                "status": "ambiguous",
                "scope": None,
                "candidates": candidates,
                "roles": roles,
                "mentions": mentions,
                "mode": "context_roles",
            }

    if len(neutral_mentions) > 1:
        unique_candidates: dict[
            tuple[str, str],
            dict[str, Any],
        ] = {}

        for mention in neutral_mentions:
            for candidate in mention["candidates"]:
                key = (
                    str(candidate.get("scope_type")),
                    str(candidate.get("canonical_code")),
                )
                unique_candidates[key] = candidate

        return {
            "status": "ambiguous",
            "scope": None,
            "candidates": list(unique_candidates.values()),
            "roles": roles,
            "mentions": mentions,
            "mode": "context_roles",
        }

    return {
        "status": "not_found",
        "scope": None,
        "candidates": [],
        "roles": roles,
        "mentions": mentions,
        "mode": "context_roles",
    }

def validate_scope_code(
    value: str,
) -> dict[str, Any]:
    """
    Valideert een reeds voorgestelde area/installatiecode
    tegen dezelfde canonical catalogus.

    Handig voor latere planner-follow-up validatie.
    """
    normalized = _normalize_text(value)

    if not normalized:
        return {
            "valid": False,
            "scope": None,
        }

    try:
        catalog = get_scope_catalog()
    except Exception as exc:
        return {
            "valid": False,
            "scope": None,
            "error_type": type(exc).__name__,
        }

    target_code = re.sub(
        r"\s+",
        "_",
        normalized,
    ).upper()

    installation = catalog[
        "installations"
    ].get(target_code)

    if installation is not None:
        return {
            "valid": True,
            "scope": {
                "scope_type": "installation",
                "canonical_code": target_code,
                "canonical_name": installation.get(
                    "canonical_name"
                ),
                "area_code": installation.get(
                    "area_code"
                ),
                "installation_code": target_code,
                "source": (
                    "canonical_scope_validation"
                ),
                "confidence": 1.0,
            },
        }

    area = catalog["areas"].get(target_code)

    if area is not None:
        return {
            "valid": True,
            "scope": {
                "scope_type": "area",
                "canonical_code": target_code,
                "canonical_name": area.get(
                    "canonical_name"
                ),
                "area_code": target_code,
                "installation_code": None,
                "source": (
                    "canonical_scope_validation"
                ),
                "confidence": 1.0,
            },
        }

    return {
        "valid": False,
        "scope": None,
    }