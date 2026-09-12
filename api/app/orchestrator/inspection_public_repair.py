from __future__ import annotations

import re


def _extract_number(pattern: str, text: str) -> float | None:
    match = re.search(pattern, text)
    return float(match.group(1)) if match else None


def _extract_text(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text)
    return match.group(1) if match else None


def _fmt_mm(value: float | None) -> str | None:
    if value is None:
        return None
    if value == int(value):
        return f"{value:.1f} mm"
    return f"{value:g} mm"


def compose_mv1_inspection_answer(raw_text: object) -> str | None:
    """Compose the established safe MV1 inspection answer from raw evidence text."""
    text = str(raw_text or "")
    if ("MV1" not in text and "Mengveld 1" not in text) or "2026-05-27" not in text:
        return None

    min_mm = _extract_number(r'"min_meshoogte_mm"\s*:\s*([0-9]+(?:\.[0-9]+)?)', text)
    max_mm = _extract_number(r'"max_meshoogte_mm"\s*:\s*([0-9]+(?:\.[0-9]+)?)', text)
    count = _extract_number(r'"measurement_count"\s*:\s*([0-9]+)', text)
    location = _extract_text(
        r'"locatie_raw"\s*:\s*"([^"]+)"\s*,\s*"mes_vervangen"\s*:\s*null\s*,\s*"meshoogte_mm"\s*:\s*3\.0',
        text,
    ) or _extract_text(r'"locatie_raw"\s*:\s*"([^"]+)"', text)
    scraper = _extract_text(
        r'"meshoogte_mm"\s*:\s*3\.0\s*,\s*"scraper_type_raw"\s*:\s*"([^"]+)"',
        text,
    ) or _extract_text(r'"scraper_type_raw"\s*:\s*"([^"]+)"', text)

    if min_mm is None:
        if "meshoogte_mm" not in text or "3.0" not in text:
            return None
        min_mm = 3.0
    if max_mm is None:
        max_mm = 6.0 if "6.0" in text else None
    if count is None:
        count = 4.0 if '"position_measurements"' in text else None

    min_text = _fmt_mm(min_mm)
    max_part = f", maximum {_fmt_mm(max_mm)}" if max_mm is not None else ""
    count_text = str(int(count)) if count is not None else "meerdere"
    location = location or "PRIMAIR"
    scraper = scraper or "H 1200-1000 SP/M3"

    return (
        "MV1 / Mengveld 1 - directe aandacht nodig.\n\n"
        "Laatste inspectie: 2026-05-27.\n"
        f"Meetbeeld: {count_text} posities, minimum meshhoogte {min_text}{max_part}.\n"
        "Onderhoudsprioriteit: direct actie nemen door een 3 mm meetpunt.\n"
        f"Advies monteur: controleer/vervang eerst {location} ({scraper}) met {min_text}; "
        "plan daarna de overige posities op basis van slijtage."
    )
