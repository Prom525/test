from __future__ import annotations

import os
import re
from typing import Optional, Literal, Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

router = APIRouter(prefix="/analysis", tags=["analysis"])

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:5432/promati",
)

engine: Engine = create_engine(DATABASE_URL, pool_pre_ping=True)

KNOWN_LIJN_CODES = {
    "GSL",
    "MV1",
    "MV2",
    "KOFA1",
    "KOFA2",
    "EO1",
    "PEFA",
    "SIFA",
    "HOO6",
    "HOO7",
    "KOLEN2",
}

BAND_CODE_PATTERN = re.compile(r"\b([A-Z]{1,3}\s?[0-9]{1,4})\b", re.IGNORECASE)
SCRAPER_PATTERN = re.compile(
    r"\b(UI|TPH|TPL|RI|RV|AF|H|U|TSN|P|R)\s*[0-9]{0,4}(?:[-/][0-9]{2,4})?(?:\s+[A-Z0-9/]+)*\b",
    re.IGNORECASE,
)

SIGNAL_TERMS = [
    "band",
    "loopt scheef",
    "scheefloop",
    "scheef",
    "trommel",
    "splice",
    "vervuil",
    "mors",
    "morsgoot",
    "nat materiaal",
    "nat",
    "materiaalopbouw",
    "uithouder",
    "druk",
    "lager",
    "frame",
    "steun",
    "hoog",
    "niet zichtbaar",
    "niet toegankelijk",
    "geen steiger",
    "mes",
    "vervang",
    "cassette",
    "hosch",
]


def fetch_all(sql: str, params: dict) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
    return [dict(r) for r in rows]


def fetch_one(sql: str, params: dict) -> Optional[dict]:
    with engine.connect() as conn:
        row = conn.execute(text(sql), params).mappings().first()
    return dict(row) if row else None


class AssistantAskRequest(BaseModel):
    vraag: str
    lijn_code: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    band_code: Optional[str] = None
    scraper_type: Optional[str] = None
    limit: int = 20


def normalize_code(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return re.sub(r"\s+", "", value).upper()


def normalize_scraper_type(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return re.sub(r"\s+", " ", value.strip()).upper()


def extract_band_code(vraag: str) -> Optional[str]:
    matches = BAND_CODE_PATTERN.findall(vraag or "")
    if not matches:
        return None

    cleaned = []
    for m in matches:
        code = normalize_code(m)
        if code in KNOWN_LIJN_CODES:
            continue
        cleaned.append(code)

    return cleaned[0] if cleaned else None


def extract_lijn_code(vraag: str, explicit_lijn_code: Optional[str]) -> Optional[str]:
    if explicit_lijn_code:
        return normalize_code(explicit_lijn_code)

    vraag_up = (vraag or "").upper()
    for code in sorted(KNOWN_LIJN_CODES, key=len, reverse=True):
        if code in vraag_up:
            return code
    return None


def extract_scraper_type(vraag: str, explicit_scraper_type: Optional[str] = None) -> Optional[str]:
    if explicit_scraper_type:
        return normalize_scraper_type(explicit_scraper_type)

    m = SCRAPER_PATTERN.search(vraag or "")
    if not m:
        return None
    return normalize_scraper_type(m.group(0))


def build_date_filters(
    date_from: Optional[str],
    date_to: Optional[str],
    column: str,
) -> tuple[list[str], dict]:
    conditions: list[str] = []
    params: dict[str, Any] = {}

    if date_from:
        conditions.append(f"{column} >= :date_from")
        params["date_from"] = date_from

    if date_to:
        conditions.append(f"{column} <= :date_to")
        params["date_to"] = date_to

    return conditions, params


def detect_intent(
    vraag: str,
    band_code: Optional[str],
    lijn_code: Optional[str],
    scraper_type: Optional[str],
) -> str:
    q = (vraag or "").lower()

    if any(w in q for w in ["word", "doc", "docx", "config", "configuratie", "welke schrapers", "scrapers in word"]):
        return "word_config"

    if any(w in q for w in ["onderhoudslijst", "actielijst", "meest dringend", "prioriteit", "onderhoudsplanning"]):
        return "maintenance_positions"

    if any(w in q for w in ["forecast", "3 mm", "3mm", "wanneer vervangen", "dagen tot", "levensduur", "binnen 30 dagen", "binnen 60 dagen"]):
        return "forecast"

    if any(w in q for w in ["vervanglijst", "overdue", "binnen_2_weken", "binnen 2 weken", "binnen 1 maand", "wat moet vervangen"]):
        return "replacement"

    if any(w in q for w in ["laatste meshoogte", "actuele meshoogte", "laatste stand"]):
        return "latest_mes"

    if any(w in q for w in ["lifecycle", "slijtage", "meshoogteverloop", "historie", "tijdlijn", "trend"]):
        if band_code:
            return "band_lifecycle"
        if scraper_type:
            return "scraper_lifecycle"
        return "lifecycle"

    if band_code:
        return "band"

    if scraper_type:
        return "scraper"

    if lijn_code:
        return "location"

    if any(w in q for w in ["dataset", "overzicht", "hoeveel", "samenvatting", "summary", "totaal"]):
        return "dataset"

    return "dataset"


def first_non_empty(rows: list[dict], key: str) -> Optional[Any]:
    for row in rows:
        value = row.get(key)
        if value not in (None, "", []):
            return value
    return None


def collect_signal_comments_from_lifecycle(
    lijn_code: Optional[str],
    band_code: Optional[str],
    scraper_type: Optional[str],
    limit: int,
) -> list[dict]:
    conditions = ["1=1"]
    params: dict[str, Any] = {"limit": limit}

    if lijn_code:
        conditions.append("lijn_code = :lijn_code")
        params["lijn_code"] = lijn_code

    if band_code:
        conditions.append("band_norm = :band_code")
        params["band_code"] = band_code

    if scraper_type:
        conditions.append("scraper_type_norm = :scraper_type")
        params["scraper_type"] = scraper_type

    signal_sql = " OR ".join([f"LOWER(COALESCE(commentaar, '')) LIKE '%{term}%'" for term in SIGNAL_TERMS])
    conditions.append(f"({signal_sql})")

    where_sql = " AND ".join(conditions)

    sql = f"""
        SELECT
            inspected_on,
            lijn_code,
            band_norm,
            scraper_type_norm,
            position_hint,
            meshoogte_mm,
            replace_event,
            cycle_id,
            commentaar
        FROM vw_mes_lifecycle_cycles_clean
        WHERE {where_sql}
        ORDER BY inspected_on DESC NULLS LAST
        LIMIT :limit
    """
    return fetch_all(sql, params)


def evaluate_unusual_slijtage(
    lifecycle_rows: list[dict],
    forecast_rows: list[dict],
    comment_rows: list[dict],
) -> tuple[bool, list[str], list[str]]:
    reasons: list[str] = []
    hypotheses: list[str] = []

    mes_values = [r.get("meshoogte_mm") for r in lifecycle_rows if r.get("meshoogte_mm") is not None]
    replace_count = sum(1 for r in lifecycle_rows if r.get("replace_event"))
    low_forecast = [r for r in forecast_rows if r.get("status_3mm") in ("NU VERVANGEN", "BINNEN 30 DAGEN")]

    if len(mes_values) >= 3 and min(mes_values) <= 3:
        reasons.append("lage meshoogte in lifecycle")
    if replace_count >= 2:
        reasons.append("meerdere vervangevents")
    if len(low_forecast) >= 2:
        reasons.append("meerdere urgente forecast-posities")

    all_comments = " || ".join([(r.get("commentaar") or "").lower() for r in comment_rows])

    if "scheef" in all_comments:
        reasons.append("herhaalde signalen van scheefloop")
        hypotheses.append("mogelijk bandloop of afstelling")
    if "vervuil" in all_comments or "mors" in all_comments:
        reasons.append("herhaalde signalen van vervuiling of mors")
        hypotheses.append("mogelijk vervuiling of carryback")
    if "trommel" in all_comments or "splice" in all_comments or "band" in all_comments:
        reasons.append("band/trommel/splice-signalen in opmerkingen")
        hypotheses.append("mogelijk band- of trommelconditie")
    if "nat" in all_comments or "materiaalopbouw" in all_comments:
        reasons.append("proces- of materiaalsignalen in opmerkingen")
        hypotheses.append("mogelijk proces- of materiaalbelasting")
    if "niet zichtbaar" in all_comments or "niet toegankelijk" in all_comments or "steiger" in all_comments:
        hypotheses.append("mogelijk beperkte inspectiekwaliteit of bereikbaarheid")

    unusual = len(reasons) > 0
    return unusual, list(dict.fromkeys(reasons)), list(dict.fromkeys(hypotheses))


def summarize_dataset_question(
    lijn_code: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
) -> dict:
    conditions = ["1=1"]
    params: dict[str, Any] = {}

    if lijn_code:
        conditions.append("lijn_code = :lijn_code")
        params["lijn_code"] = lijn_code

    date_conditions, date_params = build_date_filters(date_from, date_to, "effective_date")
    conditions.extend(date_conditions)
    params.update(date_params)

    where_sql = " AND ".join(conditions)

    sql = f"""
        SELECT
            COUNT(*) AS n_rows,
            COUNT(*) FILTER (WHERE record_type = 'POSITION') AS n_positions,
            COUNT(*) FILTER (WHERE record_type = 'OBSERVATION') AS n_observations,
            COUNT(*) FILTER (WHERE mes_num IS NOT NULL) AS n_mesmetingen,
            COUNT(*) FILTER (WHERE vervangen = TRUE) AS n_vervang_rows,
            COUNT(*) FILTER (WHERE opmerking_raw IS NOT NULL) AS n_opmerkingen,
            COUNT(DISTINCT lijn_code) AS n_lijnen,
            COUNT(DISTINCT band_locatie_norm) FILTER (WHERE band_locatie_norm IS NOT NULL) AS n_bandcodes,
            MIN(effective_date) AS eerste_datum,
            MAX(effective_date) AS laatste_datum
        FROM vw_inspection_full_dataset_v1
        WHERE {where_sql}
    """
    summary = fetch_one(sql, params)

    return {
        "intent": "dataset",
        "entities": {"lijn_code": lijn_code},
        "kort_resultaat": (
            f"Dataset bevat {summary['n_rows']} regels van {summary['eerste_datum']} tot {summary['laatste_datum']}."
            if summary else "Ik vind geen dataset-samenvatting."
        ),
        "resultaat": summary,
        "suggested_followups": [
            "Geef forecast bij 3 mm",
            "Maak een onderhoudslijst per fysieke positie",
            "Analyseer een band",
        ],
    }


def get_word_band_config(
    band_code: Optional[str] = None,
    lijn_code: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    conditions = ["1=1"]
    params: dict[str, Any] = {"limit": limit}

    if band_code:
        conditions.append("band_code = :band_code")
        params["band_code"] = band_code

    if lijn_code:
        conditions.append("lijn_code = :lijn_code")
        params["lijn_code"] = lijn_code

    where_sql = " AND ".join(conditions)

    sql = f"""
        SELECT
            band_code,
            last_doc_date,
            lijn_code,
            scraper_raw_list,
            scraper_function_list,
            scraper_brand_list,
            n_primary,
            n_secondary,
            n_tertiary,
            laatste_meting_datum,
            scraper_type_norm,
            position_hint,
            meshoogte_mm,
            commentaar
        FROM vw_band_config_plus_condition_v1
        WHERE {where_sql}
        ORDER BY band_code, laatste_meting_datum DESC NULLS LAST, position_hint
        LIMIT :limit
    """
    return fetch_all(sql, params)


def get_word_scraper_rows(
    band_code: Optional[str] = None,
    lijn_code: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    conditions = ["1=1"]
    params: dict[str, Any] = {"limit": limit}

    if band_code:
        conditions.append("band_code = :band_code")
        params["band_code"] = band_code

    if lijn_code:
        conditions.append("line_hint = :lijn_code")
        params["lijn_code"] = lijn_code

    where_sql = " AND ".join(conditions)

    sql = f"""
        SELECT
            doc_key,
            source_name,
            doc_date,
            line_hint,
            matched_inspection_key,
            match_status,
            band_code,
            scraper_raw,
            scraper_model,
            scraper_family_raw,
            scraper_function,
            scraper_brand,
            position_hint,
            direction_hint,
            scraper_status_from_doc,
            remark
        FROM vw_word_scraper_config_v1
        WHERE {where_sql}
        ORDER BY doc_date DESC NULLS LAST, band_code, scraper_raw
        LIMIT :limit
    """
    return fetch_all(sql, params)


def summarize_word_config_question(
    band_code: Optional[str],
    lijn_code: Optional[str],
    limit: int,
) -> dict:
    summary_rows = get_word_band_config(
        band_code=band_code,
        lijn_code=lijn_code,
        limit=limit,
    )
    detail_rows = get_word_scraper_rows(
        band_code=band_code,
        lijn_code=lijn_code,
        limit=limit,
    )

    if not summary_rows and not detail_rows:
        return {
            "intent": "word_config",
            "entities": {"band_code": band_code, "lijn_code": lijn_code},
            "kort_resultaat": "Geen Word-configuratie gevonden.",
            "resultaat": [],
            "scraper_rows": [],
        }

    if band_code:
        kort_resultaat = (
            f"Word-configuratie gevonden voor band {band_code}: "
            f"{len(summary_rows)} samenvattingsregels en {len(detail_rows)} scraperregels."
        )
    elif lijn_code:
        kort_resultaat = (
            f"Word-configuratie gevonden voor lijn {lijn_code}: "
            f"{len(summary_rows)} samenvattingsregels en {len(detail_rows)} scraperregels."
        )
    else:
        kort_resultaat = (
            f"Word-configuratie gevonden: {len(summary_rows)} samenvattingsregels en "
            f"{len(detail_rows)} scraperregels."
        )

    return {
        "intent": "word_config",
        "entities": {"band_code": band_code, "lijn_code": lijn_code},
        "kort_resultaat": kort_resultaat,
        "resultaat": summary_rows,
        "scraper_rows": detail_rows,
    }


def summarize_band_question(
    band_code: str,
    lijn_code: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
) -> dict:
    conditions = ["band_code = :band_code"]
    params: dict[str, Any] = {"band_code": band_code}

    if lijn_code:
        conditions.append("lijn_code = :lijn_code")
        params["lijn_code"] = lijn_code

    date_conditions, date_params = build_date_filters(date_from, date_to, "effective_date")
    conditions.extend(date_conditions)
    params.update(date_params)

    where_sql = " AND ".join(conditions)

    summary = fetch_one(
        f"""
        SELECT *
        FROM vw_band_performance_v1
        WHERE {where_sql}
        """,
        params,
    )

    trend = fetch_all(
        f"""
        SELECT *
        FROM vw_band_signal_trend_v1
        WHERE {where_sql}
        ORDER BY effective_date DESC
        LIMIT 20
        """,
        params,
    )

    recent_rows = fetch_all(
        """
        SELECT
            inspection_key,
            lijn_code,
            effective_date,
            source_file,
            sheet,
            row_nr,
            scraper_type_effective_norm,
            mes_num,
            vervangen,
            reinigen,
            demontage,
            montage,
            afstellen,
            hosch_flag,
            opmerking_raw
        FROM vw_inspection_full_dataset_v1
        WHERE band_locatie_norm = :band_code
          AND (:lijn_code IS NULL OR lijn_code = :lijn_code)
          AND (:date_from IS NULL OR effective_date >= :date_from)
          AND (:date_to IS NULL OR effective_date <= :date_to)
        ORDER BY effective_date DESC, row_nr
        LIMIT 20
        """,
        {
            "band_code": band_code,
            "lijn_code": lijn_code,
            "date_from": date_from,
            "date_to": date_to,
        },
    )

    word_config = get_word_band_config(band_code=band_code, lijn_code=lijn_code, limit=50)
    word_scrapers = get_word_scraper_rows(band_code=band_code, lijn_code=lijn_code, limit=50)

    if not summary and not word_config and not word_scrapers:
        return {
            "intent": "band",
            "entities": {"band_code": band_code, "lijn_code": lijn_code},
            "kort_resultaat": f"Ik vind geen data voor band {band_code}.",
            "resultaat": None,
            "trend_patronen": [],
            "relevante_opmerkingen": [],
            "vervangingen": [],
            "ongewone_slijtage": None,
            "mogelijke_oorzaak": [],
            "actieadvies": [],
            "word_config": [],
            "word_scrapers": [],
        }

    signal_parts = []
    if summary and summary.get("n_vervuiling"):
        signal_parts.append(f"vervuiling {summary['n_vervuiling']}")
    if summary and summary.get("n_mors"):
        signal_parts.append(f"mors {summary['n_mors']}")
    if summary and summary.get("n_scheefloop"):
        signal_parts.append(f"scheefloop {summary['n_scheefloop']}")

    if summary:
        kort_resultaat = (
            f"Band {band_code} heeft {summary['n_rows']} regels tussen {summary['eerste_datum']} en {summary['laatste_datum']}. "
            f"Mesmetingen: {summary['n_mesmetingen']}, gemiddelde {summary['avg_mes_num']}. "
            f"Vervangingen: {summary['n_vervangen']}."
        )
    else:
        kort_resultaat = (
            f"Band {band_code}: geen performance-samenvatting in vw_band_performance_v1, "
            f"maar wel Word-configuratie beschikbaar."
        )

    trend_patronen = []
    if trend:
        latest_avg = first_non_empty(trend, "avg_mes_num")
        trend_patronen.append(f"{len(trend)} tijdpunten beschikbaar.")
        if latest_avg is not None:
            trend_patronen.append(f"Recente gemiddelde meshoogte: {latest_avg}.")
        if signal_parts:
            trend_patronen.append("Signalen in historie: " + ", ".join(signal_parts) + ".")

    if word_config:
        cfg = word_config[0]
        trend_patronen.append(
            "Word-configuratie: "
            f"primary={cfg.get('n_primary', 0)}, "
            f"secondary={cfg.get('n_secondary', 0)}, "
            f"tertiary={cfg.get('n_tertiary', 0)}."
        )
        if cfg.get("scraper_raw_list"):
            trend_patronen.append(f"Word-scrapers: {cfg['scraper_raw_list']}.")
        if cfg.get("scraper_brand_list") and cfg["scraper_brand_list"] != "UNKNOWN":
            trend_patronen.append(f"Merken in Word: {cfg['scraper_brand_list']}.")

    opmerkingen = [r for r in recent_rows if (r.get("opmerking_raw") or "").strip()][:10]
    vervangingen = [r for r in recent_rows if r.get("vervangen") is True][:10]

    mogelijke_oorzaak = []
    recent_comments = " || ".join([(r.get("opmerking_raw") or "").lower() for r in opmerkingen])
    if "scheef" in recent_comments:
        mogelijke_oorzaak.append("mogelijk bandloop of afstelling")
    if "vervuil" in recent_comments or "mors" in recent_comments:
        mogelijke_oorzaak.append("mogelijk vervuiling of carryback")
    if "trommel" in recent_comments or "band" in recent_comments:
        mogelijke_oorzaak.append("mogelijk band- of trommelconditie")

    actieadvies = []
    if summary and summary.get("n_vervangen", 0) > 0:
        actieadvies.append("controleer vervangmomenten en vergelijk met mestrend")
    if summary and summary.get("n_scheefloop", 0) > 0:
        actieadvies.append("controleer bandloop en afstelling")
    if summary and (summary.get("n_vervuiling", 0) > 0 or summary.get("n_mors", 0) > 0):
        actieadvies.append("controleer vervuiling, carryback en procesbelasting")
    if word_config and word_config[0].get("n_primary", 0) == 0:
        actieadvies.append("geen primaire schraper zichtbaar in Word-configuratie; controleer configuratie")

    return {
        "intent": "band",
        "entities": {"band_code": band_code, "lijn_code": lijn_code},
        "kort_resultaat": kort_resultaat,
        "resultaat": summary,
        "trend_patronen": trend_patronen,
        "relevante_opmerkingen": opmerkingen,
        "vervangingen": vervangingen,
        "ongewone_slijtage": None,
        "mogelijke_oorzaak": list(dict.fromkeys(mogelijke_oorzaak)),
        "actieadvies": list(dict.fromkeys(actieadvies)),
        "trend_data": trend,
        "recent_rows": recent_rows,
        "word_config": word_config,
        "word_scrapers": word_scrapers,
    }


def summarize_location_question(
    lijn_code: str,
    date_from: Optional[str],
    date_to: Optional[str],
) -> dict:
    summary = fetch_one(
        """
        SELECT *
        FROM vw_location_performance_v1
        WHERE lijn_code = :lijn_code
        """,
        {"lijn_code": lijn_code},
    )

    bands = fetch_all(
        """
        SELECT *
        FROM vw_band_performance_v1
        WHERE lijn_code = :lijn_code
        ORDER BY n_rows DESC, band_code
        LIMIT 20
        """,
        {"lijn_code": lijn_code},
    )

    word_config = get_word_band_config(band_code=None, lijn_code=lijn_code, limit=100)

    if not summary and not word_config:
        return {
            "intent": "location",
            "entities": {"lijn_code": lijn_code},
            "kort_resultaat": f"Ik vind geen locatie-data voor {lijn_code}.",
            "resultaat": None,
            "trend_patronen": [],
            "relevante_opmerkingen": [],
            "vervangingen": [],
            "ongewone_slijtage": None,
            "mogelijke_oorzaak": [],
            "actieadvies": [],
        }

    trend_patronen = []
    if summary:
        trend_patronen = [
            f"Locatie {lijn_code} heeft {summary['n_banden']} banden en {summary['n_scraper_types']} scrapertypes.",
            f"Mesmetingen: {summary['n_mesmetingen']} met gemiddeld {summary['avg_mes_num']}.",
        ]

        signal_parts = []
        if summary.get("n_vervangen"):
            signal_parts.append(f"vervanging {summary['n_vervangen']}")
        if summary.get("n_vervuiling"):
            signal_parts.append(f"vervuiling {summary['n_vervuiling']}")
        if summary.get("n_scheefloop"):
            signal_parts.append(f"scheefloop {summary['n_scheefloop']}")
        if summary.get("n_mors"):
            signal_parts.append(f"mors {summary['n_mors']}")
        if signal_parts:
            trend_patronen.append("Belangrijkste signalen: " + ", ".join(signal_parts) + ".")

    if word_config:
        bands_with_primary = len({r["band_code"] for r in word_config if (r.get("n_primary") or 0) > 0})
        trend_patronen.append(
            f"Word-configuratie beschikbaar voor {len({r['band_code'] for r in word_config})} banden; {bands_with_primary} met primaire schraper zichtbaar."
        )

    actieadvies = []
    if summary and summary.get("n_vervuiling", 0) > 0:
        actieadvies.append("focus op banden met vervuilingssignalen")
    if summary and summary.get("n_scheefloop", 0) > 0:
        actieadvies.append("controleer lijnen met scheefloop en bandloop")
    if summary and summary.get("n_vervangen", 0) > 0:
        actieadvies.append("vergelijk vervanggedrag per band voor prioritering")
    if word_config:
        actieadvies.append("vergelijk Word-configuratie met actuele mesdata per band")

    return {
        "intent": "location",
        "entities": {"lijn_code": lijn_code},
        "kort_resultaat": (
            f"Locatie {lijn_code} heeft {summary['n_rows']} regels tussen {summary['eerste_datum']} en {summary['laatste_datum']}."
            if summary else f"Word-configuratie beschikbaar voor locatie {lijn_code}."
        ),
        "resultaat": summary,
        "trend_patronen": trend_patronen,
        "relevante_opmerkingen": [],
        "vervangingen": [],
        "ongewone_slijtage": None,
        "mogelijke_oorzaak": [],
        "actieadvies": list(dict.fromkeys(actieadvies)),
        "bands": bands,
        "word_config": word_config,
    }


def summarize_scraper_question(
    scraper_type: str,
    lijn_code: Optional[str],
) -> dict:
    conditions = ["scraper_type = :scraper_type"]
    params: dict[str, Any] = {"scraper_type": scraper_type}

    if lijn_code:
        conditions.append("lijn_code = :lijn_code")
        params["lijn_code"] = lijn_code

    where_sql = " AND ".join(conditions)

    rows = fetch_all(
        f"""
        SELECT *
        FROM vw_scraper_performance_v1
        WHERE {where_sql}
        ORDER BY lijn_code
        LIMIT 20
        """,
        params,
    )

    if not rows:
        return {
            "intent": "scraper",
            "entities": {"scraper_type": scraper_type, "lijn_code": lijn_code},
            "kort_resultaat": f"Ik vind geen performance-data voor scrapertype {scraper_type}.",
            "resultaat": None,
            "trend_patronen": [],
            "relevante_opmerkingen": [],
            "vervangingen": [],
            "ongewone_slijtage": None,
            "mogelijke_oorzaak": [],
            "actieadvies": [],
        }

    total_rows = sum(r.get("n_rows", 0) or 0 for r in rows)
    total_bands = sum(r.get("n_banden", 0) or 0 for r in rows)

    return {
        "intent": "scraper",
        "entities": {"scraper_type": scraper_type, "lijn_code": lijn_code},
        "kort_resultaat": f"Scrapertype {scraper_type} komt {total_rows} keer voor over {total_bands} bandkoppelingen.",
        "resultaat": rows[0],
        "trend_patronen": [f"{len(rows)} locatie-selecties gevonden."],
        "relevante_opmerkingen": [],
        "vervangingen": [],
        "ongewone_slijtage": None,
        "mogelijke_oorzaak": [],
        "actieadvies": ["vergelijk scrapertype per lijn en band voor referentieanalyse"],
        "rows": rows,
    }


def latest_meshoogte(
    lijn_code: Optional[str],
    band_code: Optional[str],
    scraper_type: Optional[str],
    limit: int,
) -> dict:
    conditions = ["1=1"]
    params: dict[str, Any] = {"limit": limit}

    if lijn_code:
        conditions.append("lijn_code = :lijn_code")
        params["lijn_code"] = lijn_code

    if band_code:
        conditions.append("band_norm = :band_code")
        params["band_code"] = band_code

    if scraper_type:
        conditions.append("scraper_type_norm = :scraper_type")
        params["scraper_type"] = scraper_type

    where_sql = " AND ".join(conditions)

    sql = f"""
        SELECT
            laatste_meting_datum,
            lijn_code,
            band_norm,
            scraper_family,
            scraper_type_norm,
            position_hint,
            meshoogte_mm,
            commentaar
        FROM vw_meshoogte_latest_per_scraper_clean
        WHERE {where_sql}
        ORDER BY laatste_meting_datum DESC NULLS LAST, lijn_code, band_norm, position_hint
        LIMIT :limit
    """
    rows = fetch_all(sql, params)

    return {
        "intent": "latest_mes",
        "kort_resultaat": f"{len(rows)} laatste meshoogte-regels gevonden." if rows else "Geen laatste meshoogtes gevonden.",
        "resultaat": rows[:20],
    }


def lifecycle_analysis(
    lijn_code: Optional[str],
    band_code: Optional[str],
    scraper_type: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
    limit: int,
) -> dict:
    conditions = ["1=1"]
    params: dict[str, Any] = {"limit": limit}

    if lijn_code:
        conditions.append("lijn_code = :lijn_code")
        params["lijn_code"] = lijn_code

    if band_code:
        conditions.append("band_norm = :band_code")
        params["band_code"] = band_code

    if scraper_type:
        conditions.append("scraper_type_norm = :scraper_type")
        params["scraper_type"] = scraper_type

    date_conditions, date_params = build_date_filters(date_from, date_to, "inspected_on")
    conditions.extend(date_conditions)
    params.update(date_params)

    where_sql = " AND ".join(conditions)

    sql = f"""
        SELECT
            inspected_on,
            lijn_code,
            band_norm,
            scraper_type_norm,
            position_hint,
            meshoogte_mm,
            replace_event,
            cycle_id,
            commentaar
        FROM vw_mes_lifecycle_cycles_clean
        WHERE {where_sql}
        ORDER BY inspected_on DESC NULLS LAST, lijn_code, band_norm, position_hint
        LIMIT :limit
    """
    rows = fetch_all(sql, params)

    replace_events = sum(1 for r in rows if r.get("replace_event"))
    mes_values = [r.get("meshoogte_mm") for r in rows if r.get("meshoogte_mm") is not None]

    trend_patronen = [f"{len(rows)} lifecycle-regels gevonden."]
    if mes_values:
        trend_patronen.append(f"Meshoogte varieert van {min(mes_values)} tot {max(mes_values)}.")
    if replace_events:
        trend_patronen.append(f"{replace_events} vervangevents gedetecteerd.")

    return {
        "intent": "lifecycle",
        "kort_resultaat": f"{len(rows)} lifecycle-regels gevonden." if rows else "Geen lifecycle-data gevonden.",
        "trend_patronen": trend_patronen,
        "resultaat": rows,
    }


def forecast_3mm(
    lijn_code: Optional[str],
    band_code: Optional[str],
    scraper_type: Optional[str],
    limit: int,
) -> dict:
    conditions = ["meetpunten >= 3"]
    params: dict[str, Any] = {"limit": limit}

    if lijn_code:
        conditions.append("lijn_code = :lijn_code")
        params["lijn_code"] = lijn_code

    if band_code:
        conditions.append("band_norm = :band_code")
        params["band_code"] = band_code

    if scraper_type:
        conditions.append("scraper_type_norm = :scraper_type")
        params["scraper_type"] = scraper_type

    where_sql = " AND ".join(conditions)

    sql = f"""
        SELECT
            lijn_code,
            band_norm,
            scraper_type_norm,
            position_hint,
            cycle_start,
            cycle_end,
            meetpunten,
            start_meshoogte_mm,
            eind_meshoogte_mm,
            slijtage_mm_per_dag,
            geschatte_dagen_tot_3mm,
            geschatte_vervangdatum_bij_3mm,
            status_3mm
        FROM vw_mes_cycle_analysis_clean
        WHERE {where_sql}
        ORDER BY
            CASE status_3mm
                WHEN 'NU VERVANGEN' THEN 1
                WHEN 'BINNEN 30 DAGEN' THEN 2
                WHEN 'BINNEN 60 DAGEN' THEN 3
                ELSE 4
            END,
            geschatte_vervangdatum_bij_3mm ASC NULLS LAST
        LIMIT :limit
    """
    rows = fetch_all(sql, params)

    urgent = [r for r in rows if r.get("status_3mm") in ("NU VERVANGEN", "BINNEN 30 DAGEN")]
    action = []
    if urgent:
        action.append(f"{len(urgent)} posities hebben urgente vervangstatus.")
    else:
        action.append("Geen directe urgente 3 mm-posities in selectie.")

    return {
        "intent": "forecast",
        "kort_resultaat": f"{len(rows)} forecast-regels gevonden.",
        "trend_patronen": action,
        "resultaat": rows,
    }


def maintenance_positions(
    lijn_code: Optional[str],
    band_code: Optional[str],
    limit: int,
) -> dict:
    conditions = ["cycle_end >= DATE '2024-01-01'"]
    params: dict[str, Any] = {"limit": limit}

    if lijn_code:
        conditions.append("lijn_code = :lijn_code")
        params["lijn_code"] = lijn_code

    if band_code:
        conditions.append("band_norm = :band_code")
        params["band_code"] = band_code

    where_sql = " AND ".join(conditions)

    sql = f"""
        SELECT
            lijn_code,
            band_norm,
            position_hint,
            scraper_types,
            cycle_start,
            cycle_end,
            meetpunten,
            avg_meshoogte_mm,
            start_meshoogte_mm,
            eind_meshoogte_mm,
            slijtage_mm_per_dag,
            geschatte_dagen_tot_3mm,
            geschatte_vervangdatum_bij_3mm,
            status_3mm,
            prioriteit
        FROM vw_mes_maintenance_positions_latest
        WHERE {where_sql}
        ORDER BY prioriteit, geschatte_vervangdatum_bij_3mm NULLS LAST, lijn_code, band_norm
        LIMIT :limit
    """
    rows = fetch_all(sql, params)

    p1 = sum(1 for r in rows if r.get("prioriteit") == 1)
    p2 = sum(1 for r in rows if r.get("prioriteit") == 2)

    return {
        "intent": "maintenance_positions",
        "kort_resultaat": f"{len(rows)} onderhoudsposities gevonden.",
        "trend_patronen": [f"Prioriteit 1: {p1}", f"Prioriteit 2: {p2}"],
        "resultaat": rows,
    }


def maintenance_planning(limit: int) -> dict:
    sql = """
        SELECT
            lijn_code,
            COUNT(*) AS n_posities,
            COUNT(*) FILTER (WHERE prioriteit = 1) AS nu_vervangen,
            COUNT(*) FILTER (WHERE prioriteit = 2) AS binnen_30_dagen,
            COUNT(*) FILTER (WHERE prioriteit = 3) AS binnen_60_dagen,
            COUNT(*) FILTER (WHERE prioriteit = 4) AS ok
        FROM vw_mes_maintenance_positions_latest
        WHERE cycle_end >= DATE '2024-01-01'
        GROUP BY lijn_code
        ORDER BY nu_vervangen DESC, binnen_30_dagen DESC, binnen_60_dagen DESC, lijn_code
        LIMIT :limit
    """
    rows = fetch_all(sql, {"limit": limit})

    return {
        "intent": "maintenance_planning",
        "kort_resultaat": f"{len(rows)} lijnen in onderhoudsplanning.",
        "resultaat": rows,
    }


def replacement_advice(
    lijn_code: Optional[str],
    limit: int,
) -> dict:
    conditions = ["status IN ('OVERDUE','BINNEN_2_WEKEN','BINNEN_1_MAAND')"]
    params: dict[str, Any] = {"limit": limit}

    if lijn_code:
        conditions.append("lijn_code = :lijn_code")
        params["lijn_code"] = lijn_code

    where_sql = " AND ".join(conditions)

    sql = f"""
        SELECT
            lijn_code,
            band_norm,
            scraper_family,
            scraper_type_norm,
            next_due_date,
            days_to_due,
            typical_mes_qty,
            status
        FROM vw_all_replacement_advice
        WHERE {where_sql}
        ORDER BY
            CASE status
                WHEN 'OVERDUE' THEN 1
                WHEN 'BINNEN_2_WEKEN' THEN 2
                WHEN 'BINNEN_1_MAAND' THEN 3
                ELSE 4
            END,
            next_due_date ASC NULLS LAST
        LIMIT :limit
    """
    rows = fetch_all(sql, params)

    return {
        "intent": "replacement",
        "kort_resultaat": f"{len(rows)} vervangadviezen gevonden.",
        "resultaat": rows,
    }


def band_deep_analysis(
    band_code: str,
    lijn_code: Optional[str],
    limit: int,
) -> dict:
    latest = latest_meshoogte(
        lijn_code=lijn_code,
        band_code=band_code,
        scraper_type=None,
        limit=limit,
    )
    lifecycle = lifecycle_analysis(
        lijn_code=lijn_code,
        band_code=band_code,
        scraper_type=None,
        date_from=None,
        date_to=None,
        limit=limit,
    )
    forecast = forecast_3mm(
        lijn_code=lijn_code,
        band_code=band_code,
        scraper_type=None,
        limit=limit,
    )
    comments = collect_signal_comments_from_lifecycle(
        lijn_code=lijn_code,
        band_code=band_code,
        scraper_type=None,
        limit=limit,
    )
    word_config = get_word_band_config(
        band_code=band_code,
        lijn_code=lijn_code,
        limit=limit,
    )
    word_scrapers = get_word_scraper_rows(
        band_code=band_code,
        lijn_code=lijn_code,
        limit=limit,
    )

    unusual, reasons, hypotheses = evaluate_unusual_slijtage(
        lifecycle_rows=lifecycle.get("resultaat", []),
        forecast_rows=forecast.get("resultaat", []),
        comment_rows=comments,
    )

    vervangingen = [r for r in lifecycle.get("resultaat", []) if r.get("replace_event")][:10]

    trend_patronen = []
    if latest.get("resultaat"):
        trend_patronen.append(f"{len(latest['resultaat'])} laatste meshoogte-posities beschikbaar.")
    if lifecycle.get("resultaat"):
        trend_patronen.extend(lifecycle.get("trend_patronen", []))
    if forecast.get("resultaat"):
        trend_patronen.extend(forecast.get("trend_patronen", []))
    if word_config:
        cfg = word_config[0]
        trend_patronen.append(
            f"Word-configuratie: primary={cfg.get('n_primary', 0)}, secondary={cfg.get('n_secondary', 0)}, tertiary={cfg.get('n_tertiary', 0)}."
        )
        if cfg.get("scraper_raw_list"):
            trend_patronen.append(f"Word-scrapers: {cfg['scraper_raw_list']}.")

    actieadvies = []
    if unusual:
        actieadvies.append("controleer afwijkende slijtagepatronen per fysieke positie")
    if any("scheef" in (r.get("commentaar") or "").lower() for r in comments):
        actieadvies.append("controleer bandloop, uitlijning en afstelling")
    if any(("vervuil" in (r.get("commentaar") or "").lower()) or ("mors" in (r.get("commentaar") or "").lower()) for r in comments):
        actieadvies.append("controleer carryback, vervuiling en materiaalopbouw")
    if word_config and word_config[0].get("n_primary", 0) == 0:
        actieadvies.append("geen primaire schraper zichtbaar in Word-configuratie; controleer configuratie")
    if not actieadvies and forecast.get("resultaat"):
        actieadvies.append("monitor forecast en prioriteer op status_3mm")

    return {
        "intent": "band_deep_analysis",
        "entities": {"band_code": band_code, "lijn_code": lijn_code},
        "kort_resultaat": (
            f"Analyse voor band {band_code}: "
            f"{len(latest.get('resultaat', []))} laatste meshoogte-posities, "
            f"{len(lifecycle.get('resultaat', []))} lifecycle-regels, "
            f"{len(forecast.get('resultaat', []))} forecast-regels, "
            f"{len(word_scrapers)} Word-scraperregels."
        ),
        "trend_patronen": trend_patronen[:12],
        "relevante_opmerkingen": comments[:10],
        "vervangingen": vervangingen,
        "ongewone_slijtage": {"ja_nee": unusual, "waarom": reasons},
        "mogelijke_oorzaak": hypotheses,
        "actieadvies": list(dict.fromkeys(actieadvies)),
        "laatste_meshoogte": latest.get("resultaat", []),
        "lifecycle": lifecycle.get("resultaat", []),
        "forecast_3mm": forecast.get("resultaat", []),
        "word_config": word_config,
        "word_scrapers": word_scrapers,
    }


@router.get("/health")
def analysis_health() -> dict:
    try:
        row = fetch_one("SELECT 1 AS ok", {})
        return {"status": "ok", "db": row}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/dataset/summary")
def get_dataset_summary(
    lijn_code: Optional[str] = Query(default=None),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
):
    return summarize_dataset_question(
        lijn_code=normalize_code(lijn_code),
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/dataset/full")
def get_full_dataset(
    lijn_code: Optional[str] = Query(default=None),
    band_code: Optional[str] = Query(default=None),
    scraper_type: Optional[str] = Query(default=None),
    record_type: Optional[Literal["POSITION", "OBSERVATION"]] = Query(default=None),
    data_quality_flag: Optional[str] = Query(default=None),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    limit: int = Query(default=500, ge=1, le=10000),
):
    conditions = ["1=1"]
    params: dict[str, Any] = {"limit": limit}

    if lijn_code:
        conditions.append("lijn_code = :lijn_code")
        params["lijn_code"] = normalize_code(lijn_code)

    if band_code:
        conditions.append("band_locatie_norm = :band_code")
        params["band_code"] = normalize_code(band_code)

    if scraper_type:
        conditions.append("scraper_type_effective_norm = :scraper_type")
        params["scraper_type"] = normalize_scraper_type(scraper_type)

    if record_type:
        conditions.append("record_type = :record_type")
        params["record_type"] = record_type

    if data_quality_flag:
        conditions.append("data_quality_flag = :data_quality_flag")
        params["data_quality_flag"] = data_quality_flag

    if date_from:
        conditions.append("effective_date >= :date_from")
        params["date_from"] = date_from

    if date_to:
        conditions.append("effective_date <= :date_to")
        params["date_to"] = date_to

    where_sql = " AND ".join(conditions)

    sql = f"""
        SELECT
            inspection_key,
            lijn_code,
            effective_date,
            source_file,
            sheet,
            row_nr,
            record_type,
            data_quality_flag,
            band_locatie_norm,
            locatie_effective,
            scraper_type_effective_norm,
            scraper_family,
            scraper_material,
            mes_num,
            mes_code,
            mes_interpretatie,
            demontage,
            reinigen,
            vervangen,
            montage,
            afstellen,
            hosch_flag,
            opmerking_raw,
            record_role,
            parse_confidence
        FROM vw_inspection_full_dataset_v1
        WHERE {where_sql}
        ORDER BY effective_date DESC, lijn_code, inspection_key, row_nr
        LIMIT :limit
    """
    return fetch_all(sql, params)


@router.get("/word/config")
def get_word_config_endpoint(
    lijn_code: Optional[str] = Query(default=None),
    band_code: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
):
    return summarize_word_config_question(
        band_code=normalize_code(band_code),
        lijn_code=normalize_code(lijn_code),
        limit=limit,
    )


@router.get("/band/{band_code}/word-config")
def get_band_word_config_endpoint(
    band_code: str,
    lijn_code: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
):
    return summarize_word_config_question(
        band_code=normalize_code(band_code),
        lijn_code=normalize_code(lijn_code),
        limit=limit,
    )


@router.get("/band/{band_code}/performance-v1")
def get_band_performance_v1(
    band_code: str,
    lijn_code: Optional[str] = Query(default=None),
):
    return summarize_band_question(
        band_code=normalize_code(band_code),
        lijn_code=normalize_code(lijn_code),
        date_from=None,
        date_to=None,
    )


@router.get("/band/{band_code}/analysis-v7")
def get_band_analysis_v7(
    band_code: str,
    lijn_code: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
):
    return band_deep_analysis(
        band_code=normalize_code(band_code),
        lijn_code=normalize_code(lijn_code),
        limit=limit,
    )


@router.get("/location/{locatie_code}/performance-v1")
def get_location_performance_v1(
    locatie_code: str,
):
    return summarize_location_question(
        lijn_code=normalize_code(locatie_code),
        date_from=None,
        date_to=None,
    )


@router.get("/scraper/{scraper_type}/performance-v1")
def get_scraper_performance_v1(
    scraper_type: str,
    lijn_code: Optional[str] = Query(default=None),
):
    return summarize_scraper_question(
        scraper_type=normalize_scraper_type(scraper_type),
        lijn_code=normalize_code(lijn_code),
    )


@router.get("/mes/latest")
def get_meshoogte_latest(
    lijn_code: Optional[str] = Query(default=None),
    band_code: Optional[str] = Query(default=None),
    scraper_type: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
):
    return latest_meshoogte(
        lijn_code=normalize_code(lijn_code),
        band_code=normalize_code(band_code),
        scraper_type=extract_scraper_type("", scraper_type),
        limit=limit,
    )


@router.get("/mes/lifecycle")
def get_mes_lifecycle(
    lijn_code: Optional[str] = Query(default=None),
    band_code: Optional[str] = Query(default=None),
    scraper_type: Optional[str] = Query(default=None),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=500),
):
    return lifecycle_analysis(
        lijn_code=normalize_code(lijn_code),
        band_code=normalize_code(band_code),
        scraper_type=extract_scraper_type("", scraper_type),
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )


@router.get("/mes/forecast-3mm")
def get_mes_forecast_3mm(
    lijn_code: Optional[str] = Query(default=None),
    band_code: Optional[str] = Query(default=None),
    scraper_type: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
):
    return forecast_3mm(
        lijn_code=normalize_code(lijn_code),
        band_code=normalize_code(band_code),
        scraper_type=extract_scraper_type("", scraper_type),
        limit=limit,
    )


@router.get("/replacement/advice")
def get_replacement_advice(
    lijn_code: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
):
    return replacement_advice(
        lijn_code=normalize_code(lijn_code),
        limit=limit,
    )


@router.get("/maintenance/positions")
def get_maintenance_positions(
    lijn_code: Optional[str] = Query(default=None),
    band_code: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
):
    return maintenance_positions(
        lijn_code=normalize_code(lijn_code),
        band_code=normalize_code(band_code),
        limit=limit,
    )


@router.get("/maintenance/planning")
def get_maintenance_planning(
    limit: int = Query(default=20, ge=1, le=200),
):
    return maintenance_planning(limit=limit)


@router.post("/assistant/ask")
def analysis_assistant_ask(payload: AssistantAskRequest):
    vraag = (payload.vraag or "").strip()
    if not vraag:
        raise HTTPException(status_code=400, detail="vraag is verplicht")

    lijn_code = extract_lijn_code(vraag, payload.lijn_code)
    band_code = normalize_code(payload.band_code) if payload.band_code else extract_band_code(vraag)
    scraper_type = extract_scraper_type(vraag, payload.scraper_type)
    intent = detect_intent(vraag, band_code, lijn_code, scraper_type)
    limit = max(1, min(payload.limit, 50))

    if intent == "word_config":
        return summarize_word_config_question(
            band_code=band_code,
            lijn_code=lijn_code,
            limit=limit,
        )

    if intent == "maintenance_positions":
        return maintenance_positions(
            lijn_code=lijn_code,
            band_code=band_code,
            limit=limit,
        )

    if intent == "forecast":
        return forecast_3mm(
            lijn_code=lijn_code,
            band_code=band_code,
            scraper_type=scraper_type,
            limit=limit,
        )

    if intent == "replacement":
        return replacement_advice(
            lijn_code=lijn_code,
            limit=limit,
        )

    if intent == "latest_mes":
        return latest_meshoogte(
            lijn_code=lijn_code,
            band_code=band_code,
            scraper_type=scraper_type,
            limit=limit,
        )

    if intent in {"lifecycle", "band_lifecycle", "scraper_lifecycle"}:
        return lifecycle_analysis(
            lijn_code=lijn_code,
            band_code=band_code,
            scraper_type=scraper_type,
            date_from=payload.date_from,
            date_to=payload.date_to,
            limit=limit,
        )

    if intent == "band" and band_code:
        return band_deep_analysis(
            band_code=band_code,
            lijn_code=lijn_code,
            limit=limit,
        )

    if intent == "scraper" and scraper_type:
        return summarize_scraper_question(
            scraper_type=scraper_type,
            lijn_code=lijn_code,
        )

    if intent == "location" and lijn_code:
        return summarize_location_question(
            lijn_code=lijn_code,
            date_from=payload.date_from,
            date_to=payload.date_to,
        )

    return summarize_dataset_question(
        lijn_code=lijn_code,
        date_from=payload.date_from,
        date_to=payload.date_to,
    )
