from __future__ import annotations

import json
import re
from typing import Any


TASK_CONCISE_COMPOSER_CONTRACT_VERSION = (
    "promati.orchestrator.task_concise_composer.cp12.v1"
)
MAX_PUBLIC_ANSWER_BYTES = 1_900
MAX_PUBLIC_LINES = 18
MAX_PUBLIC_BULLETS = 10

_RAW_MARKERS = (
    "latest_position_measurement:",
    "latest_blade_height:",
    "evidence_ids_used",
    "included_evidence_ids",
    "excluded_evidence_ids",
    "task_coverage_gate_cp10",
    "task_presenter_cp11",
)
_SAFE_FAILURE = (
    "De beschikbare gegevens konden niet veilig en beknopt tot een publiek "
    "antwoord worden samengevat. Probeer de vraag specifieker te stellen."
)


def _bytes(value: str) -> int:
    return len(value.encode("utf-8"))


def _contains_machine_payload(value: str) -> bool:
    folded = value.casefold()
    if any(marker in folded for marker in _RAW_MARKERS):
        return True
    if re.search(r"```\s*(?:json)?\s*[\[{]", value, re.IGNORECASE):
        return True
    for line in value.splitlines():
        candidate = line.strip()
        if len(candidate) < 80 or candidate[:1] not in "[{":
            continue
        try:
            if isinstance(json.loads(candidate), (dict, list)):
                return True
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
    return False


def _safe_candidate(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text or _contains_machine_payload(text):
        return None
    if _bytes(text) > MAX_PUBLIC_ANSWER_BYTES:
        return None
    return text


def _deduplicate_and_bound(value: str) -> str | None:
    lines: list[str] = []
    seen: set[str] = set()
    bullets = 0
    for raw_line in value.splitlines():
        line = raw_line.strip()
        if not line:
            if lines and lines[-1]:
                lines.append("")
            continue
        key = re.sub(r"\s+", " ", line).casefold()
        if key in seen:
            continue
        seen.add(key)
        if line.startswith(("- ", "* ", "• ")):
            bullets += 1
            if bullets > MAX_PUBLIC_BULLETS:
                continue
            line = "- " + line[2:].strip()
        lines.append(line)
        if len(lines) > MAX_PUBLIC_LINES:
            return None
    answer = "\n".join(lines).strip()
    return _safe_candidate(answer)


def compose_concise_public_answer(
    answer: Any,
    safe_fallback: Any,
    *,
    response_profile: str = "compact",
    task_coverage_gate_cp10: dict[str, Any] | None = None,
    task_presenter_cp11: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Bound public prose without granting or widening CP10/CP11 authority."""
    gate = task_coverage_gate_cp10 or {}
    presenter = task_presenter_cp11 or {}
    blocked = gate.get("blocked") is True or presenter.get("authoritative") is False
    authoritative = (
        not blocked
        and gate.get("authoritative") is True
        and presenter.get("authoritative") is True
        and presenter.get("public_answer_replaced") is True
    )
    original = str(answer or "").strip()
    composed = _deduplicate_and_bound(original) if original else None
    reason = "answer_normalized"

    if blocked:
        # CP12 formats a blocked legacy answer but can never turn it into an
        # authoritative replacement.
        authoritative = False
        reason = str(gate.get("reason") or presenter.get("reason") or "authority_blocked")
    if composed is None:
        composed = _safe_candidate(safe_fallback) or _SAFE_FAILURE
        reason = "unsafe_or_oversized_answer_fell_back"
        authoritative = False

    status = {
        "contract_version": TASK_CONCISE_COMPOSER_CONTRACT_VERSION,
        "evaluated": True,
        "response_profile": response_profile,
        "authoritative": authoritative,
        "public_answer_replaced": authoritative,
        "reason": reason,
        "input_bytes": _bytes(original),
        "output_bytes": _bytes(composed),
    }
    return composed, status


__all__ = [
    "MAX_PUBLIC_ANSWER_BYTES",
    "TASK_CONCISE_COMPOSER_CONTRACT_VERSION",
    "compose_concise_public_answer",
]
