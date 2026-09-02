from __future__ import annotations

import os
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

router = APIRouter(prefix="/scrapers", tags=["scrapers"])


# =========================================================
# DB
# =========================================================

def _get_engine() -> Engine:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL ontbreekt")
    return create_engine(db_url, pool_pre_ping=True)


ENGINE = _get_engine()


def _rows_to_dicts(result) -> list[dict[str, Any]]:
    cols = list(result.keys())
    return [dict(zip(cols, row)) for row in result.fetchall()]


def _table_exists(table_name: str) -> bool:
    sql = text("""
        select exists (
            select 1
            from information_schema.tables
            where table_schema = 'public'
              and table_name = :table_name
        )
    """)
    with ENGINE.begin() as conn:
        return bool(conn.execute(sql, {"table_name": table_name}).scalar())


def _get_columns(table_name: str) -> set[str]:
    sql = text("""
        select column_name
        from information_schema.columns
        where table_schema = 'public'
          and table_name = :table_name
    """)
    with ENGINE.begin() as conn:
        rows = conn.execute(sql, {"table_name": table_name}).fetchall()
    return {r[0] for r in rows}


# =========================================================
# API Models
# =========================================================

class RecommendationIn(BaseModel):
    slots: list[str] = Field(..., description="bijv ['primary'] of ['primary','secondary']")
    belt_speed: float = Field(..., ge=0)
    material: str = Field(..., description="dry | wet | sticky | dusty")
    critical: bool = False
    carryback_risk: Optional[str] = Field(default=None, description="low | medium | high")
    headroom: bool = True
    existing_cleaners: int = 0


# =========================================================
# Helpers
# =========================================================

def _normalize_slot(s: str) -> str:
    return (s or "").strip().lower()


def _normalize_material(s: str) -> str:
    return (s or "").strip().lower()


def _product_name(row: dict[str, Any]) -> str:
    brand = row.get("brand") or ""
    model = row.get("model") or ""
    return f"{brand} {model}".strip()


def _slot_allowed(row: dict[str, Any], slot: str) -> bool:
    allowed = row.get("allowed_slots") or []
    return slot in [str(x).lower() for x in allowed]


def _fetch_base_candidates(slot: str, belt_speed: float, headroom: bool) -> list[dict[str, Any]]:
    sql = text("""
        select
            product_id,
            brand,
            model,
            position_hint,
            bidirectional_ok,
            speed_max_mps,
            temp_max_c,
            space_compact,
            active,
            notes,
            allowed_slots
        from scraper_product
        where active = true
          and :slot = any(allowed_slots)
          and (speed_max_mps is null or speed_max_mps >= :belt_speed)
          and (:headroom = true or space_compact = true)
        order by brand, model
    """)

    with ENGINE.begin() as conn:
        rows = conn.execute(
            sql,
            {
                "slot": slot,
                "belt_speed": belt_speed,
                "headroom": headroom,
            },
        ).mappings().all()

    return [dict(r) for r in rows]


def _boost_from_sales(product: dict[str, Any]) -> float:
    """
    Probeert score te verhogen uit scraper_product_sales.
    Werkt alleen als tabel + bruikbare kolommen bestaan.
    """
    if not _table_exists("scraper_product_sales"):
        return 0.0

    cols = _get_columns("scraper_product_sales")
    if "product_id" not in cols:
        return 0.0

    # We proberen veelvoorkomende kolommen
    numeric_cols = [c for c in ["score", "priority", "weight", "rank"] if c in cols]

    if not numeric_cols:
        return 0.0

    chosen_col = numeric_cols[0]

    sql = text(f"""
        select {chosen_col}
        from scraper_product_sales
        where product_id = :product_id
        limit 1
    """)

    with ENGINE.begin() as conn:
        val = conn.execute(sql, {"product_id": product["product_id"]}).scalar()

    if val is None:
        return 0.0

    try:
        return float(val)
    except Exception:
        return 0.0


def _boost_from_capabilities(product: dict[str, Any], material: str, critical: bool, carryback_risk: Optional[str]) -> float:
    """
    Probeert scraper_capability te gebruiken.
    Zonder schema-garantie, dus alleen als kolommen herkenbaar zijn.
    """
    if not _table_exists("scraper_capability"):
        return 0.0

    cols = _get_columns("scraper_capability")
    if "product_id" not in cols:
        return 0.0

    score = 0.0

    # Verwachte simpele schema-varianten:
    # - capability / capability_key / key
    # - capability_value / value
    key_col = None
    for c in ["capability", "capability_key", "key", "name"]:
        if c in cols:
            key_col = c
            break

    val_col = None
    for c in ["capability_value", "value", "val"]:
        if c in cols:
            val_col = c
            break

    if not key_col:
        return 0.0

    sql = text(f"""
        select {key_col} as cap_key
               {"," + val_col + " as cap_val" if val_col else ""}
        from scraper_capability
        where product_id = :product_id
    """)

    with ENGINE.begin() as conn:
        rows = conn.execute(sql, {"product_id": product["product_id"]}).mappings().all()

    for r in rows:
        cap_key = str(r["cap_key"]).lower()

        cap_val = None
        if "cap_val" in r and r["cap_val"] is not None:
            cap_val = str(r["cap_val"]).lower()

        # eenvoudige interpretatie
        if material in ("wet", "sticky") and ("wet" in cap_key or "sticky" in cap_key):
            score += 10
        if material == "dry" and "dry" in cap_key:
            score += 6
        if material == "dusty" and "dust" in cap_key:
            score += 6
        if critical and "critical" in cap_key:
            score += 6
        if carryback_risk == "high" and ("carryback" in cap_key or "high" in (cap_val or "")):
            score += 8

    return score


def _boost_from_rule_actions(product: dict[str, Any], slot: str, material: str, critical: bool, carryback_risk: Optional[str]) -> float:
    """
    Probeert scraper_rule_action te gebruiken.
    Ook hier: veilig, alleen als bruikbare kolommen bestaan.
    """
    if not _table_exists("scraper_rule_action"):
        return 0.0

    cols = _get_columns("scraper_rule_action")
    if "product_id" not in cols:
        return 0.0

    score = 0.0

    condition_cols = [c for c in ["rule_name", "action", "condition_text", "note", "notes"] if c in cols]
    if not condition_cols:
        return 0.0

    chosen_col = condition_cols[0]

    sql = text(f"""
        select {chosen_col} as txt
        from scraper_rule_action
        where product_id = :product_id
    """)

    with ENGINE.begin() as conn:
        rows = conn.execute(sql, {"product_id": product["product_id"]}).mappings().all()

    for r in rows:
        txt = str(r["txt"] or "").lower()

        if slot in txt:
            score += 3
        if material in txt:
            score += 4
        if critical and "critical" in txt:
            score += 4
        if carryback_risk and carryback_risk in txt:
            score += 4

    return score


def _hard_business_filters(products: list[dict[str, Any]], slot: str) -> list[dict[str, Any]]:
    """
    Harde regels die nooit overtreden mogen worden.
    """
    out: list[dict[str, Any]] = []

    for p in products:
        model = str(p.get("model") or "").upper()

        # Verboden combinaties
        if slot == "primary" and model == "U":
            continue
        if slot == "secondary" and model == "H":
            continue
        if slot == "secondary" and model == "TPH":
            continue

        out.append(p)

    return out


def _base_score(
    product: dict[str, Any],
    slot: str,
    belt_speed: float,
    material: str,
    critical: bool,
    carryback_risk: Optional[str],
    headroom: bool,
    existing_cleaners: int,
) -> float:
    """
    Basisscore uit harde business-logica.
    """
    model = str(product.get("model") or "").upper()
    score = 0.0

    # Active / allowed slot is al gefilterd
    score += 20

    # snelheid
    if product.get("speed_max_mps") is None:
        score += 2
    else:
        try:
            margin = float(product["speed_max_mps"]) - belt_speed
            if margin >= 1.0:
                score += 4
            elif margin >= 0:
                score += 2
        except Exception:
            pass

    # ruimte
    if headroom:
        score += 2
    elif product.get("space_compact"):
        score += 8

    # slot-specifieke voorkeuren
    if slot == "primary":
        if model == "TPH":
            score += 14
        elif model == "TPL":
            score += 12
        elif model == "H":
            score += 10

        if material in ("wet", "sticky") or critical or carryback_risk == "high":
            if model == "TPH":
                score += 10
            if model == "TPL":
                score += 8
            if model == "H":
                score += 6

    elif slot == "secondary":
        if model == "U":
            score += 12
        elif model == "R":
            score += 10

        if material in ("wet", "sticky") or critical or carryback_risk in ("medium", "high"):
            if model == "U":
                score += 10
            if model == "R":
                score += 8

    elif slot == "tertiary":
        if model == "U_TERT":
            score += 20

    # bestaande reinigers
    if existing_cleaners >= 1 and slot in ("secondary", "tertiary"):
        score += 4

    # position hint kan klein beetje helpen
    pos = str(product.get("position_hint") or "").lower()
    if slot in pos:
        score += 3

    return score


def _score_product(
    product: dict[str, Any],
    slot: str,
    belt_speed: float,
    material: str,
    critical: bool,
    carryback_risk: Optional[str],
    headroom: bool,
    existing_cleaners: int,
) -> tuple[float, list[str]]:
    reasons: list[str] = []

    score = _base_score(
        product=product,
        slot=slot,
        belt_speed=belt_speed,
        material=material,
        critical=critical,
        carryback_risk=carryback_risk,
        headroom=headroom,
        existing_cleaners=existing_cleaners,
    )

    reasons.append("Voldoet aan allowed_slots.")
    reasons.append("Voldoet aan snelheid/ruimte-filter.")

    sales_boost = _boost_from_sales(product)
    if sales_boost:
        score += sales_boost
        reasons.append(f"Extra score uit scraper_product_sales (+{sales_boost:.1f}).")

    cap_boost = _boost_from_capabilities(product, material, critical, carryback_risk)
    if cap_boost:
        score += cap_boost
        reasons.append(f"Extra score uit scraper_capability (+{cap_boost:.1f}).")

    rule_boost = _boost_from_rule_actions(product, slot, material, critical, carryback_risk)
    if rule_boost:
        score += rule_boost
        reasons.append(f"Extra score uit scraper_rule_action (+{rule_boost:.1f}).")

    model = str(product.get("model") or "").upper()

    if slot == "primary" and model in ("TPH", "TPL", "H"):
        reasons.append("Model past logisch als primary.")
    if slot == "secondary" and model in ("U", "R"):
        reasons.append("Model past logisch als secondary.")
    if slot == "tertiary" and model == "U_TERT":
        reasons.append("Model past logisch als tertiary.")

    return score, reasons


def _select_best_for_slot(
    slot: str,
    belt_speed: float,
    material: str,
    critical: bool,
    carryback_risk: Optional[str],
    headroom: bool,
    existing_cleaners: int,
) -> dict[str, Any] | None:
    candidates = _fetch_base_candidates(slot, belt_speed, headroom)
    candidates = _hard_business_filters(candidates, slot)

    if not candidates:
        return None

    scored: list[tuple[float, dict[str, Any], list[str]]] = []
    for p in candidates:
        score, reasons = _score_product(
            product=p,
            slot=slot,
            belt_speed=belt_speed,
            material=material,
            critical=critical,
            carryback_risk=carryback_risk,
            headroom=headroom,
            existing_cleaners=existing_cleaners,
        )
        scored.append((score, p, reasons))

    scored.sort(key=lambda x: (x[0], x[1].get("brand") or "", x[1].get("model") or ""), reverse=True)

    best_score, best_product, reasons = scored[0]

    return {
        "product_id": best_product["product_id"],
        "brand": best_product["brand"],
        "model": best_product["model"],
        "name": _product_name(best_product),
        "allowed_slots": best_product["allowed_slots"],
        "position_hint": best_product["position_hint"],
        "speed_max_mps": float(best_product["speed_max_mps"]) if best_product["speed_max_mps"] is not None else None,
        "space_compact": best_product["space_compact"],
        "notes": best_product["notes"],
        "score": round(best_score, 2),
        "why": reasons,
    }


# =========================================================
# Endpoints
# =========================================================

@router.get("/catalog")
def scraper_catalog(slot: Optional[str] = None, active_only: bool = True):
    if slot:
        sql = text("""
            select
                product_id,
                brand,
                model,
                position_hint,
                bidirectional_ok,
                speed_max_mps,
                temp_max_c,
                space_compact,
                active,
                notes,
                allowed_slots
            from scraper_product
            where (:active_only = false or active = true)
              and :slot = any(allowed_slots)
            order by brand, model
        """)
        params = {"slot": slot.lower(), "active_only": active_only}
    else:
        sql = text("""
            select
                product_id,
                brand,
                model,
                position_hint,
                bidirectional_ok,
                speed_max_mps,
                temp_max_c,
                space_compact,
                active,
                notes,
                allowed_slots
            from scraper_product
            where (:active_only = false or active = true)
            order by brand, model
        """)
        params = {"active_only": active_only}

    with ENGINE.begin() as conn:
        rows = conn.execute(sql, params).mappings().all()

    return [dict(r) for r in rows]


@router.post("/recommendation")
def recommend_scrapers(payload: RecommendationIn):
    slots = [_normalize_slot(s) for s in payload.slots]
    material = _normalize_material(payload.material)
    carryback_risk = (payload.carryback_risk or "").lower() or None

    valid_slots = {"primary", "secondary", "tertiary"}
    if not slots or any(s not in valid_slots for s in slots):
        raise HTTPException(status_code=400, detail="Ongeldige slots opgegeven.")

    if material not in {"dry", "wet", "sticky", "dusty"}:
        raise HTTPException(status_code=400, detail="Ongeldig materiaal.")

    result = {
        "input": payload.model_dump(),
        "primary": None,
        "secondary": None,
        "tertiary": None,
    }

    if "primary" in slots:
        result["primary"] = _select_best_for_slot(
            slot="primary",
            belt_speed=payload.belt_speed,
            material=material,
            critical=payload.critical,
            carryback_risk=carryback_risk,
            headroom=payload.headroom,
            existing_cleaners=payload.existing_cleaners,
        )

    if "secondary" in slots:
        result["secondary"] = _select_best_for_slot(
            slot="secondary",
            belt_speed=payload.belt_speed,
            material=material,
            critical=payload.critical,
            carryback_risk=carryback_risk,
            headroom=payload.headroom,
            existing_cleaners=payload.existing_cleaners,
        )

    if "tertiary" in slots:
        result["tertiary"] = _select_best_for_slot(
            slot="tertiary",
            belt_speed=payload.belt_speed,
            material=material,
            critical=payload.critical,
            carryback_risk=carryback_risk,
            headroom=payload.headroom,
            existing_cleaners=payload.existing_cleaners,
        )

    return result