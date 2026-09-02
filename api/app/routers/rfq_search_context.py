from fastapi import APIRouter, Query
from sqlalchemy import text, bindparam
from pydantic import BaseModel

import json
import urllib.request
import urllib.error

from app.db import engine
from app.config import settings
from app.services.rfq_pulley_knowledge import evaluate_pulley_knowledge

router = APIRouter(
    prefix="/analysis/context/rfq",
    tags=["rfq-context"],
)

class SupplierSelectionRequest(BaseModel):
    rfq_id: str
    position_id: str
    supplier_ids: list[str]

@router.get("/search")
def search_rfq_context(
    q: str = Query(..., min_length=2),
    limit: int = Query(default=25, ge=1, le=100),
):
    sql = """
    SELECT
        rfq_id,
        position_id,
        product_type,
        drawing_mark,
        drawing_description,
        file_name,
        bearing_type,
        bearing_housing,
        rubber_material
    FROM rfq.rfq_position_search_v1
    WHERE
          UPPER(COALESCE(product_type,'')) LIKE UPPER(:q)
       OR UPPER(COALESCE(drawing_mark,'')) LIKE UPPER(:q)
       OR UPPER(COALESCE(drawing_description,'')) LIKE UPPER(:q)
       OR UPPER(COALESCE(bearing_type,'')) LIKE UPPER(:q)
       OR UPPER(COALESCE(bearing_housing,'')) LIKE UPPER(:q)
       OR UPPER(COALESCE(rubber_material,'')) LIKE UPPER(:q)
       OR UPPER(COALESCE(extracted_text,'')) LIKE UPPER(:q)
    LIMIT :limit
    """

    with engine.begin() as conn:
        rows = conn.execute(
            text(sql),
            {
                "q": f"%{q}%",
                "limit": limit,
            },
        ).mappings().all()

    return {
        "status": "ok",
        "context_type": "rfq_search",
        "query": q,
        "results": [dict(r) for r in rows],
        "write_actions_available": False,
    }


@router.get("/supplier-recommendation")
def supplier_recommendation(
    q: str = "",
    product_type: str | None = None,
    bearing_type: str | None = None,
    rubber_material: str | None = None,
    limit: int = 10,
):
    sql = """
    SELECT
        s.supplier_id,
        s.supplier_name,
        s.categories,
        s.specialties,

        COALESCE(sq.total_score,0) AS qualification_score,

        COALESCE(ss.quality_score,0) +
        COALESCE(ss.delivery_score,0) +
        COALESCE(ss.documentation_score,0) +
        COALESCE(ss.response_score,0) AS performance_score,

        COALESCE(ss.rfq_count,0) AS rfq_count,
        COALESCE(ss.conversion_rate,0) AS conversion_rate,

        (
            COALESCE(sq.total_score,0)
            +
            COALESCE(ss.quality_score,0)
            +
            COALESCE(ss.delivery_score,0)
            +
            COALESCE(ss.documentation_score,0)
            +
            COALESCE(ss.response_score,0)
            +
            CASE
                WHEN :product_type IS NOT NULL
                 AND :product_type = ANY(s.categories)
                THEN 50 ELSE 0
            END
            +
            CASE
                WHEN :rubber_material IS NOT NULL
                 AND (
                    EXISTS (
                        SELECT 1 FROM unnest(s.specialties) sp
                        WHERE UPPER(sp) LIKE UPPER('%' || :rubber_material || '%')
                    )
                    OR EXISTS (
                        SELECT 1 FROM unnest(s.specialties) sp
                        WHERE UPPER(sp) LIKE '%RUBBER%'
                    )
                 )
                THEN 15 ELSE 0
            END
            +
            CASE
                WHEN :bearing_type IS NOT NULL
                 AND EXISTS (
                    SELECT 1 FROM unnest(s.specialties) sp
                    WHERE UPPER(sp) LIKE '%OEM%'
                       OR UPPER(sp) LIKE '%HEAVY%'
                       OR UPPER(sp) LIKE '%PREMIUM%'
                 )
                THEN 10 ELSE 0
            END
        ) AS recommendation_score

    FROM rfq.supplier s

    LEFT JOIN rfq.supplier_qualification sq
        ON sq.supplier_id = s.supplier_id
       AND sq.active = true

    LEFT JOIN rfq.supplier_score ss
        ON ss.supplier_id = s.supplier_id

    WHERE s.active = true
      AND (
            :product_type IS NULL
            OR :product_type = ANY(s.categories)
      )

    ORDER BY recommendation_score DESC

    LIMIT :limit
    """

    with engine.begin() as conn:
        rows = conn.execute(
            text(sql),
            {
                "q": q,
                "product_type": product_type.upper() if product_type else None,
                "bearing_type": bearing_type,
                "rubber_material": rubber_material,
                "limit": limit,
            },
        ).mappings().all()

    results = []
    for r in rows:
        row = dict(r)
        reasons = []

        if product_type and row.get("categories") and product_type.upper() in row["categories"]:
            reasons.append(f"Category match: {product_type.upper()}")

        if rubber_material:
            reasons.append(f"Rubber/material context: {rubber_material}")

        if bearing_type:
            reasons.append(f"Bearing/heavy-duty context: {bearing_type}")

        if row.get("qualification_score", 0) > 0:
            reasons.append(f"Qualification score: {row['qualification_score']}")

        if row.get("performance_score", 0) > 0:
            reasons.append(f"Performance score: {row['performance_score']}")

        row["reasons"] = reasons
        results.append(row)

    return {
        "status": "ok",
        "context_type": "rfq_supplier_recommendation",
        "query": q,
        "filters": {
            "product_type": product_type,
            "bearing_type": bearing_type,
            "rubber_material": rubber_material,
        },
        "recommended_suppliers": results,
        "write_actions_available": False,
    }


@router.get("/similar")
def similar_rfq_context(
    q: str = "",
    product_type: str | None = None,
    bearing_type: str | None = None,
    rubber_material: str | None = None,
    limit: int = 10,
):
    sql = """
    SELECT
        rfq_id,
        position_id,
        product_type,
        drawing_mark,
        drawing_description,
        file_name,
        bearing_type,
        bearing_housing,
        rubber_material,
        diameter_mm,
        drum_width_mm,
        shaft_diameter_mm,

        (
            CASE
                WHEN :product_type IS NOT NULL
                 AND UPPER(COALESCE(product_type,'')) = UPPER(:product_type)
                THEN 40 ELSE 0
            END
            +
            CASE
                WHEN :bearing_type IS NOT NULL
                 AND (
                    UPPER(COALESCE(bearing_type,'')) LIKE UPPER('%' || :bearing_type || '%')
                    OR UPPER(COALESCE(bearing_housing,'')) LIKE UPPER('%' || :bearing_type || '%')
                 )
                THEN 30 ELSE 0
            END
            +
            CASE
                WHEN :rubber_material IS NOT NULL
                 AND UPPER(COALESCE(rubber_material,'')) LIKE UPPER('%' || :rubber_material || '%')
                THEN 20 ELSE 0
            END
            +
            CASE
                WHEN :q <> ''
                 AND (
                    UPPER(COALESCE(drawing_mark,'')) LIKE UPPER('%' || :q || '%')
                    OR UPPER(COALESCE(drawing_description,'')) LIKE UPPER('%' || :q || '%')
                    OR UPPER(COALESCE(extracted_text,'')) LIKE UPPER('%' || :q || '%')
                    OR UPPER(COALESCE(file_name,'')) LIKE UPPER('%' || :q || '%')
                 )
                THEN 25 ELSE 0
            END
        ) AS similarity_score

    FROM rfq.rfq_position_search_v1

    WHERE
          (:q <> '' AND (
              UPPER(COALESCE(drawing_mark,'')) LIKE UPPER('%' || :q || '%')
              OR UPPER(COALESCE(drawing_description,'')) LIKE UPPER('%' || :q || '%')
              OR UPPER(COALESCE(extracted_text,'')) LIKE UPPER('%' || :q || '%')
              OR UPPER(COALESCE(file_name,'')) LIKE UPPER('%' || :q || '%')
          ))
       OR (:product_type IS NOT NULL AND UPPER(COALESCE(product_type,'')) = UPPER(:product_type))
       OR (:bearing_type IS NOT NULL AND (
              UPPER(COALESCE(bearing_type,'')) LIKE UPPER('%' || :bearing_type || '%')
              OR UPPER(COALESCE(bearing_housing,'')) LIKE UPPER('%' || :bearing_type || '%')
          ))
       OR (:rubber_material IS NOT NULL AND UPPER(COALESCE(rubber_material,'')) LIKE UPPER('%' || :rubber_material || '%'))

    ORDER BY similarity_score DESC
    LIMIT :limit
    """

    with engine.begin() as conn:
        rows = conn.execute(
            text(sql),
            {
                "q": q,
                "product_type": product_type,
                "bearing_type": bearing_type,
                "rubber_material": rubber_material,
                "limit": limit,
            },
        ).mappings().all()

    return {
        "status": "ok",
        "context_type": "rfq_similar",
        "query": q,
        "filters": {
            "product_type": product_type,
            "bearing_type": bearing_type,
            "rubber_material": rubber_material,
        },
        "similar_rfqs": [dict(r) for r in rows],
        "write_actions_available": False,
    }


@router.get("/supplier-package")
def supplier_package(
    q: str = "",
    product_type: str | None = None,
    bearing_type: str | None = None,
    rubber_material: str | None = None,
    limit: int = 10,
):
    supplier_sql = """
    SELECT
        s.supplier_id,
        s.supplier_name,
        s.categories,
        s.specialties,

        COALESCE(sq.total_score,0) AS qualification_score,

        COALESCE(ss.quality_score,0) +
        COALESCE(ss.delivery_score,0) +
        COALESCE(ss.documentation_score,0) +
        COALESCE(ss.response_score,0) AS performance_score,

        COALESCE(ss.rfq_count,0) AS rfq_count,
        COALESCE(ss.conversion_rate,0) AS conversion_rate,

        (
            COALESCE(sq.total_score,0)
            +
            COALESCE(ss.quality_score,0)
            +
            COALESCE(ss.delivery_score,0)
            +
            COALESCE(ss.documentation_score,0)
            +
            COALESCE(ss.response_score,0)
            +
            CASE
                WHEN :product_type IS NOT NULL
                 AND :product_type = ANY(s.categories)
                THEN 50 ELSE 0
            END
            +
            CASE
                WHEN :rubber_material IS NOT NULL
                 AND (
                    EXISTS (
                        SELECT 1 FROM unnest(s.specialties) sp
                        WHERE UPPER(sp) LIKE UPPER('%' || :rubber_material || '%')
                    )
                    OR EXISTS (
                        SELECT 1 FROM unnest(s.specialties) sp
                        WHERE UPPER(sp) LIKE '%RUBBER%'
                    )
                 )
                THEN 15 ELSE 0
            END
            +
            CASE
                WHEN :bearing_type IS NOT NULL
                 AND EXISTS (
                    SELECT 1 FROM unnest(s.specialties) sp
                    WHERE UPPER(sp) LIKE '%OEM%'
                       OR UPPER(sp) LIKE '%HEAVY%'
                       OR UPPER(sp) LIKE '%PREMIUM%'
                 )
                THEN 10 ELSE 0
            END
        ) AS recommendation_score

    FROM rfq.supplier s

    LEFT JOIN rfq.supplier_qualification sq
        ON sq.supplier_id = s.supplier_id
       AND sq.active = true

    LEFT JOIN rfq.supplier_score ss
        ON ss.supplier_id = s.supplier_id

    WHERE s.active = true
      AND (
            :product_type IS NULL
            OR :product_type = ANY(s.categories)
      )

    ORDER BY recommendation_score DESC
    LIMIT :limit
    """

    similar_sql = """
    SELECT
        rfq_id,
        position_id,
        product_type,
        drawing_mark,
        drawing_description,
        file_name,
        bearing_type,
        bearing_housing,
        rubber_material,
        diameter_mm,
        drum_width_mm,
        shaft_diameter_mm,

        (
            CASE
                WHEN :product_type IS NOT NULL
                 AND UPPER(COALESCE(product_type,'')) = UPPER(:product_type)
                THEN 40 ELSE 0
            END
            +
            CASE
                WHEN :bearing_type IS NOT NULL
                 AND (
                    UPPER(COALESCE(bearing_type,'')) LIKE UPPER('%' || :bearing_type || '%')
                    OR UPPER(COALESCE(bearing_housing,'')) LIKE UPPER('%' || :bearing_type || '%')
                 )
                THEN 30 ELSE 0
            END
            +
            CASE
                WHEN :rubber_material IS NOT NULL
                 AND UPPER(COALESCE(rubber_material,'')) LIKE UPPER('%' || :rubber_material || '%')
                THEN 20 ELSE 0
            END
            +
            CASE
                WHEN :q <> ''
                 AND (
                    UPPER(COALESCE(drawing_mark,'')) LIKE UPPER('%' || :q || '%')
                    OR UPPER(COALESCE(drawing_description,'')) LIKE UPPER('%' || :q || '%')
                    OR UPPER(COALESCE(extracted_text,'')) LIKE UPPER('%' || :q || '%')
                    OR UPPER(COALESCE(file_name,'')) LIKE UPPER('%' || :q || '%')
                 )
                THEN 25 ELSE 0
            END
        ) AS similarity_score

    FROM rfq.rfq_position_search_v1

    WHERE (
          (:q <> '' AND (
              UPPER(COALESCE(drawing_mark,'')) LIKE UPPER('%' || :q || '%')
              OR UPPER(COALESCE(drawing_description,'')) LIKE UPPER('%' || :q || '%')
              OR UPPER(COALESCE(extracted_text,'')) LIKE UPPER('%' || :q || '%')
              OR UPPER(COALESCE(file_name,'')) LIKE UPPER('%' || :q || '%')
          ))
       OR (:product_type IS NOT NULL
           AND UPPER(COALESCE(product_type,'')) = UPPER(:product_type))
       OR (:bearing_type IS NOT NULL AND (
              UPPER(COALESCE(bearing_type,'')) LIKE UPPER('%' || :bearing_type || '%')
              OR UPPER(COALESCE(bearing_housing,'')) LIKE UPPER('%' || :bearing_type || '%')
          ))
       OR (:rubber_material IS NOT NULL
           AND UPPER(COALESCE(rubber_material,'')) LIKE UPPER('%' || :rubber_material || '%'))
    )

       AND (
           (
               CASE
                   WHEN :product_type IS NOT NULL
                    AND UPPER(COALESCE(product_type,'')) = UPPER(:product_type)
                   THEN 40 ELSE 0
               END
               +
               CASE
                   WHEN :bearing_type IS NOT NULL
                    AND (
                       UPPER(COALESCE(bearing_type,'')) LIKE UPPER('%' || :bearing_type || '%')
                       OR UPPER(COALESCE(bearing_housing,'')) LIKE UPPER('%' || :bearing_type || '%')
                    )
                   THEN 30 ELSE 0
               END
               +
               CASE
                   WHEN :rubber_material IS NOT NULL
                    AND UPPER(COALESCE(rubber_material,'')) LIKE UPPER('%' || :rubber_material || '%')
                   THEN 20 ELSE 0
               END
           ) >= 60
       )
       ORDER BY similarity_score DESC
       LIMIT 5
       """

    params = {
        "q": q,
        "product_type": product_type.upper() if product_type else None,
        "bearing_type": bearing_type,
        "rubber_material": rubber_material,
        "limit": limit,
    }

    def risk_label(score: int) -> str:
        if score >= 5:
            return "HIGH"
        if score >= 2:
            return "MEDIUM"
        return "LOW"

    risk_sql = """
    SELECT
        balancing_norm,
        seal_type,
        grease_type,
        surface_roughness,
        tolerance_class
    FROM rfq.position_extracted_specs
    WHERE (:q = '' OR true)
    ORDER BY created_at DESC
    LIMIT 1
    """

    with engine.begin() as conn:
        suppliers = [dict(r) for r in conn.execute(text(supplier_sql), params).mappings().all()]
        similar_rfqs = [dict(r) for r in conn.execute(text(similar_sql), params).mappings().all()]
        risk_context = conn.execute(text(risk_sql), params).mappings().first()

    risk_context = dict(risk_context) if risk_context else {}

    enriched_suppliers = []

    for supplier in suppliers:
        reasons = []

        if product_type and supplier.get("categories") and product_type.upper() in supplier["categories"]:
            reasons.append(f"Geschikt voor categorie {product_type.upper()}")

        if rubber_material:
            reasons.append(f"Relevant voor rubber/material context: {rubber_material}")

        if bearing_type:
            reasons.append(f"Relevant voor heavy-duty/lagercontext: {bearing_type}")

        if supplier.get("qualification_score", 0) > 0:
            reasons.append(f"Kwalificatiescore: {supplier['qualification_score']}")

        if supplier.get("performance_score", 0) > 0:
            reasons.append(f"Prestatiescore: {supplier['performance_score']}")

        supplier["reasons"] = reasons
        enriched_suppliers.append(supplier)

    primary_suppliers = enriched_suppliers[:3]
    backup_suppliers = enriched_suppliers[3:6]

    technical_reasons = []
    recommended_actions = []

    if not risk_context.get("balancing_norm"):
        technical_reasons.append("Balanceernorm ontbreekt.")
        recommended_actions.append("Bevestig balanceernorm / balanceerklasse.")

    if not risk_context.get("seal_type"):
        technical_reasons.append("Seal type / afdichting ontbreekt.")
        recommended_actions.append("Bevestig afdichting van lagerhuis.")

    if not risk_context.get("tolerance_class"):
        technical_reasons.append("Tolerantieklasse ontbreekt.")
        recommended_actions.append("Bevestig algemene tolerantienorm of klasse.")

    risk_score = len(technical_reasons)

    risk_review = {
        "technical_risk": risk_label(risk_score),
        "overall_risk": risk_label(risk_score),
        "risk_score": risk_score,
        "technical_reasons": technical_reasons,
        "recommended_actions": recommended_actions,
    }

    return {
        "status": "ok",
        "context_type": "rfq_supplier_package",
        "query": q,
        "filters": {
            "product_type": product_type,
            "bearing_type": bearing_type,
            "rubber_material": rubber_material,
        },
        "primary_suppliers": primary_suppliers,
        "backup_suppliers": backup_suppliers,
        "similar_rfqs": similar_rfqs,

        "risk_review": risk_review,

        "recommendation_summary": [
            "Primary suppliers are the highest ranked suppliers for the RFQ context.",
            "Backup suppliers are suitable alternatives if primary suppliers are unavailable.",
            "Ranking uses supplier category, specialties, qualification score and performance score.",
        ],
        "write_actions_available": False,
    }


@router.get("/risk-review")
def rfq_risk_review(
    rfq_id: str | None = None,
    position_id: str | None = None,
    product_type: str | None = None,
    bearing_type: str | None = None,
    rubber_material: str | None = None,
):
    context_sql = """
    SELECT
        v.rfq_id,
        v.position_id,
        v.product_type,
        v.drawing_mark,
        v.bearing_type,
        v.bearing_housing,
        v.rubber_material,
        v.diameter_mm,
        v.drum_width_mm,
        v.shaft_diameter_mm,

        es.balancing_norm,
        es.seal_type,
        es.grease_type,
        es.surface_roughness,
        es.tolerance_class,
        es.missing_fields

    FROM rfq.rfq_position_search_v1 v

    LEFT JOIN LATERAL (
        SELECT *
        FROM rfq.position_extracted_specs es
        WHERE es.rfq_id = v.rfq_id
          AND es.position_id = v.position_id
        ORDER BY es.created_at DESC
        LIMIT 1
    ) es ON true

    WHERE
        (:rfq_id IS NULL OR v.rfq_id::text = :rfq_id)
        AND (:position_id IS NULL OR v.position_id::text = :position_id)
        AND (:product_type IS NULL OR UPPER(v.product_type) = UPPER(:product_type))
    LIMIT 1
    """

    supplier_sql = """
    SELECT COUNT(*)::int AS supplier_count
    FROM rfq.supplier
    WHERE active = true
      AND (
            :product_type IS NULL
            OR :product_type = ANY(categories)
      )
    """

    params = {
        "rfq_id": rfq_id,
        "position_id": position_id,
        "product_type": product_type.upper() if product_type else None,
        "bearing_type": bearing_type,
        "rubber_material": rubber_material,
    }

    with engine.begin() as conn:
        context = conn.execute(text(context_sql), params).mappings().first()
        supplier_count_row = conn.execute(text(supplier_sql), params).mappings().first()

    context = dict(context) if context else {}

    detected_product_type = product_type or context.get("product_type")
    detected_bearing_type = bearing_type or context.get("bearing_type") or context.get("bearing_housing")
    detected_rubber_material = rubber_material or context.get("rubber_material")

    supplier_count = supplier_count_row["supplier_count"] if supplier_count_row else 0

    technical_reasons = []
    commercial_reasons = []
    supplier_reasons = []
    recommended_actions = []

    if not detected_product_type:
        technical_reasons.append("Product type ontbreekt.")
        recommended_actions.append("Bevestig product type, bijvoorbeeld TROMMEL, ROL of SCRAPER.")

    if detected_product_type and detected_product_type.upper() == "TROMMEL":
        if not context.get("diameter_mm"):
            technical_reasons.append("Trommeldiameter ontbreekt.")
            recommended_actions.append("Bevestig trommeldiameter.")
        if not context.get("drum_width_mm"):
            technical_reasons.append("Trommelbreedte ontbreekt.")
            recommended_actions.append("Bevestig trommelbreedte.")
        if not context.get("shaft_diameter_mm"):
            technical_reasons.append("Asdiameter ontbreekt.")
            recommended_actions.append("Bevestig asdiameter.")
        if not detected_bearing_type:
            technical_reasons.append("Lager- of lagerhuistype ontbreekt.")
            recommended_actions.append("Bevestig lager/lagerhuis.")
        if not detected_rubber_material:
            technical_reasons.append("Rubbermateriaal ontbreekt.")
            recommended_actions.append("Bevestig rubbermateriaal en hardheid.")
        if not context.get("balancing_norm"):
            technical_reasons.append("Balanceernorm ontbreekt.")
            recommended_actions.append("Bevestig balanceernorm / balanceerklasse.")

        if not context.get("seal_type"):
            technical_reasons.append("Seal type / afdichting ontbreekt.")
            recommended_actions.append("Bevestig afdichting van lagerhuis.")

        if not context.get("tolerance_class"):
            technical_reasons.append("Tolerantieklasse ontbreekt.")
            recommended_actions.append("Bevestig algemene tolerantienorm of klasse.")

    if supplier_count == 0:
        supplier_reasons.append("Geen actieve leveranciers gevonden voor deze categorie.")
        recommended_actions.append("Voeg minimaal één actieve leverancier toe voor deze categorie.")
    elif supplier_count < 3:
        supplier_reasons.append(f"Beperkt aantal actieve leveranciers gevonden: {supplier_count}.")
        recommended_actions.append("Overweeg extra leveranciers als backup.")
    else:
        supplier_reasons.append(f"{supplier_count} actieve leveranciers beschikbaar voor deze categorie.")

    if detected_product_type and detected_product_type.upper() == "TROMMEL":
        commercial_reasons.append("Trommel-RFQ vereist meestal technische verificatie op tekening, lagers, rubber en balancing.")
        recommended_actions.append("Gebruik engineering review voordat de RFQ naar leveranciers gaat.")

    technical_risk_score = len(technical_reasons)
    supplier_risk_score = 0 if supplier_count >= 3 else 2 if supplier_count > 0 else 4
    commercial_risk_score = 1 if commercial_reasons else 0

    total_score = technical_risk_score + supplier_risk_score + commercial_risk_score

    def risk_label(score: int) -> str:
        if score >= 5:
            return "HIGH"
        if score >= 2:
            return "MEDIUM"
        return "LOW"

    return {
        "status": "ok",
        "context_type": "rfq_risk_review",
        "filters": {
            "rfq_id": rfq_id,
            "position_id": position_id,
            "product_type": detected_product_type,
            "bearing_type": detected_bearing_type,
            "rubber_material": detected_rubber_material,
        },
        "context": context,
        "risk": {
            "technical_risk": risk_label(technical_risk_score),
            "commercial_risk": risk_label(commercial_risk_score),
            "supplier_risk": risk_label(supplier_risk_score),
            "overall_risk": risk_label(total_score),
            "risk_score": total_score,
        },
        "reasons": {
            "technical": technical_reasons,
            "commercial": commercial_reasons,
            "supplier": supplier_reasons,
        },
        "recommended_actions": list(dict.fromkeys(recommended_actions)),
        "write_actions_available": False,
    }


@router.get("/{rfq_id}/positions/{position_id}/engineering-review-v2")
def get_rfq_position_engineering_review(
    rfq_id: str,
    position_id: str,
):
    """
    Technische RFQ-review per positie.
    Combineert extracted RFQ specs met de algemene technische kennisbank.
    Read-only endpoint voor GPT, frontend en later supplier-routing.
    """

    context_sql = """
    SELECT
        v.rfq_id,
        v.position_id,
        v.product_type,
        v.drawing_mark,
        v.drawing_description,
        v.file_name,

        v.bearing_type,
        v.bearing_housing,
        v.rubber_material,
        v.diameter_mm,
        v.drum_width_mm,
        v.shaft_diameter_mm,

        es.balancing_norm,
        es.seal_type,
        es.grease_type,
        es.surface_roughness,
        es.tolerance_class,
        es.confidence_score,
        es.missing_fields

    FROM rfq.rfq_position_search_v1 v

    LEFT JOIN LATERAL (
        SELECT *
        FROM rfq.position_extracted_specs es
        WHERE es.rfq_id = v.rfq_id
          AND es.position_id = v.position_id
        ORDER BY es.created_at DESC
        LIMIT 1
    ) es ON true

    WHERE v.rfq_id::text = :rfq_id
      AND v.position_id::text = :position_id

    LIMIT 1
    """

    with engine.begin() as conn:
        row = conn.execute(
            text(context_sql),
            {
                "rfq_id": rfq_id,
                "position_id": position_id,
            },
        ).mappings().first()

    if not row:
        return {
            "status": "not_found",
            "context_type": "rfq_engineering_review",
            "rfq_id": rfq_id,
            "position_id": position_id,
            "message": "Geen RFQ-positie gevonden.",
            "write_actions_available": False,
        }

    context = dict(row)

    product_type = (context.get("product_type") or "").upper()

    pulley_knowledge = evaluate_pulley_knowledge(
        specs={
            **context,
            "product_type": product_type,
        },
        missing_fields=context.get("missing_fields") or [],
    )

    if product_type in {"TROMMEL", "PULLEY", "DRUM"}:
        product_group = "pulley"
        topic_groups = [
            "rfq_norms_pulleys_idlers",
            "rfq_pulley_engineering",
            "rfq_premium_oem_selection",
            "rfq_fat_quality_requirements",
        ]
    elif product_type in {"ROL", "ROLLEN", "IDLER", "ROLLER"}:
        product_group = "idler"
        topic_groups = [
            "rfq_norms_pulleys_idlers",
            "rfq_idler_engineering",
            "rfq_premium_oem_selection",
            "rfq_fat_quality_requirements",
        ]
    else:
        product_group = "unknown"
        topic_groups = [
            "rfq_norms_pulleys_idlers",
            "rfq_premium_oem_selection",
            "rfq_fat_quality_requirements",
        ]

    missing_fields = []

    def missing(field: str, label: str):
        if not context.get(field):
            missing_fields.append({
                "field": field,
                "label": label,
            })

    if product_group == "pulley":
        missing("diameter_mm", "Trommeldiameter ontbreekt.")
        missing("drum_width_mm", "Mantellengte / trommelbreedte ontbreekt.")
        missing("shaft_diameter_mm", "Asdiameter ontbreekt.")
        missing("bearing_type", "Lagertype ontbreekt.")
        missing("bearing_housing", "Lagerhuis ontbreekt.")
        missing("rubber_material", "Rubbermateriaal / laggingmateriaal ontbreekt.")
        missing("balancing_norm", "Balanceernorm of balanceerklasse ontbreekt.")
        missing("seal_type", "Afdichting / sealtype ontbreekt.")
        missing("tolerance_class", "Tolerantieklasse ontbreekt.")

    elif product_group == "idler":
        missing("diameter_mm", "Roldiameter ontbreekt.")
        missing("shaft_diameter_mm", "Asdiameter ontbreekt.")
        missing("bearing_type", "Lagertype ontbreekt.")
        missing("seal_type", "Afdichting / sealconcept ontbreekt.")
        missing("tolerance_class", "Tolerantieklasse ontbreekt.")

    else:
        missing("product_type", "Producttype ontbreekt of is onbekend.")

    technical_risks = []
    fat_requirements = []
    documentation_requirements = []
    norm_requirements = []
    next_actions = []

    # Algemene risico’s vanuit ontbrekende data
    for item in missing_fields:
        next_actions.append(item["label"])

    # Productspecifieke basislogica
    if product_group == "pulley":
        if not context.get("balancing_norm"):
            technical_risks.append({
                "risk": "Balanceereis ontbreekt.",
                "severity": "MEDIUM",
                "reason": "Voor trommels is onduidelijk of statisch, dynamisch, G6.3 of G2.5 vereist is.",
            })
            norm_requirements.append("ISO 1940-1 / ISO 21940-11")
            fat_requirements.append("Balancing report met klasse, testsnelheid en restonbalans.")

        if not context.get("rubber_material"):
            technical_risks.append({
                "risk": "Lagging/rubber specificatie ontbreekt.",
                "severity": "MEDIUM",
                "reason": "Grip, slijtage en nat/droog gedrag zijn niet goed vergelijkbaar zonder compound, hardheid en dikte.",
            })
            fat_requirements.append("Laggingcontrole: type, dikte, hardheid, compound en adhesie waar nodig.")

        if not context.get("bearing_type"):
            norm_requirements.append("ISO 281")
            documentation_requirements.append("Lagerberekening L10/L10h bij premium of critical service.")

        documentation_requirements.extend([
            "Datasheet trommel",
            "Maatrapport met diameter, mantellengte, aszittingen en kritische passingen",
        ])

    elif product_group == "idler":
        if not context.get("bearing_type"):
            technical_risks.append({
                "risk": "Lagercode ontbreekt.",
                "severity": "MEDIUM",
                "reason": "Zonder lagercode is L10/L10h en supplier comparison niet toetsbaar.",
            })
            norm_requirements.append("ISO 281")

        if not context.get("seal_type"):
            technical_risks.append({
                "risk": "Sealconcept ontbreekt.",
                "severity": "MEDIUM",
                "reason": "Bij rollen/idlers bepaalt afdichting vaak de werkelijke levensduur in vuile of natte dienst.",
            })

        documentation_requirements.extend([
            "Datasheet idler/rol",
            "Lager- en afdichtingsspecificatie",
            "Maatbevestiging diameter, lengte, asmaat en framefit",
        ])

        fat_requirements.extend([
            "Vrije rotatiecontrole",
            "Seal/lageropbouw bevestigen",
        ])

    # Routeadvies
    risk_score = len(missing_fields) + len(technical_risks)

    premium_indicators = []

    if context.get("balancing_norm"):
        premium_indicators.append("Balanceereis aanwezig.")

    if context.get("rubber_material"):
        premium_indicators.append("Rubber/lagging context aanwezig.")

    if risk_score >= 5:
        recommended_route = "REVIEW"
        engineering_status = "ENGINEERING_REVIEW"
    elif product_group == "unknown":
        recommended_route = "REVIEW"
        engineering_status = "ENGINEERING_REVIEW"
    elif premium_indicators:
        recommended_route = "PREMIUM_REVIEW"
        engineering_status = "ENGINEERING_REVIEW"
    else:
        recommended_route = "OEM_OR_STANDARD_REVIEW"
        engineering_status = "ENGINEERING_REVIEW" if risk_score > 0 else "READY_FOR_RFQ"

    readiness_score = max(0, min(100, round(100 - risk_score * 10, 1)))

    ready_for_supplier_rfq = (
        engineering_status == "READY_FOR_RFQ"
        and len(missing_fields) == 0
        and len(technical_risks) == 0
    )

    # Algemene technische context ophalen uit kennisbank
    technical_context_sql = text("""
    SELECT
        item_type,
        source_code,
        topic_group,
        title,
        summary_nl,
        key_points_nl,
        structured_data
    FROM vw_gpt_technical_context
    WHERE source_code = 'PROMATI_RFQ_TECHNICAL_STANDARDS'
      AND topic_group IN :topic_groups
    ORDER BY
        CASE item_type
            WHEN 'fact' THEN 1
            WHEN 'table' THEN 2
            WHEN 'formula' THEN 3
            WHEN 'section' THEN 4
            ELSE 9
        END,
        topic_group,
        title
    LIMIT 25
    """).bindparams(bindparam("topic_groups", expanding=True))

    with engine.begin() as conn:
        tech_rows = conn.execute(
            technical_context_sql,
            {
                "topic_groups": topic_groups,
            },
        ).mappings().all()

    technical_context = [dict(r) for r in tech_rows]

    # Maak context.missing_fields leidend vanuit de actuele engineering-review,
    # niet vanuit de oude databasewaarde es.missing_fields.
    # Daardoor zijn context.missing_fields en top-level missing_fields altijd gelijk.
    if isinstance(context, dict):
        context["missing_fields"] = [
            item["field"]
            for item in missing_fields
            if item.get("field")
        ]

    return {
        "status": "ok",
        "context_type": "rfq_engineering_review",
        "rfq_id": rfq_id,
        "position_id": position_id,
        "product_group": product_group,
        "product_type": product_type,
        "engineering_status": engineering_status,
        "recommended_route": recommended_route,
        "readiness_score": readiness_score,
        "ready_for_supplier_rfq": ready_for_supplier_rfq,
        "context": context,
        "missing_fields": missing_fields,
        "technical_risks": technical_risks,
        "norm_requirements": list(dict.fromkeys(norm_requirements)),
        "fat_requirements": list(dict.fromkeys(fat_requirements)),
        "documentation_requirements": list(dict.fromkeys(documentation_requirements)),
        "next_actions": list(dict.fromkeys(next_actions)),
        "technical_context_used": technical_context,

        "pulley_knowledge": pulley_knowledge,
        "standard_suggestions": pulley_knowledge.get("standard_suggestions", []),
        "standard_supplier_questions": pulley_knowledge.get("supplier_questions", []),
        "standard_engineering_notes": pulley_knowledge.get("engineering_notes", []),

        "write_actions_available": False,
    }


@router.get("/{rfq_id}/positions/{position_id}/ocr-preview", include_in_schema=False)
def rfq_position_ocr_preview(
    rfq_id: str,
    position_id: str,
):
    """
    Interne test-route.
    Haalt het RFQ-document uit rfq.position_document,
    stuurt het naar ED OCR2 en geeft extracted specs terug.

    Schrijft nog niets naar de database.
    Staat niet in OpenAPI/GPT Actions door include_in_schema=False.
    """

    document_sql = """
    SELECT
        document_id,
        document_type,
        file_name,
        content_type,
        file_size,
        storage_path,
        uploaded_by,
        created_at
    FROM rfq.position_document
    WHERE rfq_id::text = :rfq_id
      AND position_id::text = :position_id
    ORDER BY
        CASE
            WHEN UPPER(COALESCE(document_type,'')) = 'DRAWING' THEN 1
            WHEN UPPER(COALESCE(content_type,'')) LIKE '%PDF%' THEN 2
            ELSE 9
        END,
        created_at DESC
    LIMIT 1
    """

    with engine.begin() as conn:
        document = conn.execute(
            text(document_sql),
            {
                "rfq_id": rfq_id,
                "position_id": position_id,
            },
        ).mappings().first()

    if not document:
        return {
            "status": "not_found",
            "context_type": "rfq_ocr_preview",
            "rfq_id": rfq_id,
            "position_id": position_id,
            "message": "Geen document gevonden voor deze RFQ-positie.",
            "write_actions_available": False,
        }

    document = dict(document)

    storage_path = document.get("storage_path")
    file_name = document.get("file_name")

    if not storage_path:
        return {
            "status": "error",
            "context_type": "rfq_ocr_preview",
            "rfq_id": rfq_id,
            "position_id": position_id,
            "message": "Document heeft geen storage_path.",
            "document": {
                "document_id": str(document.get("document_id")),
                "file_name": file_name,
                "document_type": document.get("document_type"),
            },
            "write_actions_available": False,
        }

    payload = {
        "bucket": "rfq-artifacts",
        "rfq_id": rfq_id,
        "position_id": position_id,
        "document_id": str(document.get("document_id")),
        "storage_path": storage_path,
        "file_name": file_name or storage_path.split("/")[-1],
    }

    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(
        f"{settings.EDOCR2_URL.rstrip('/')}/process",
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            body = response.read().decode("utf-8")
            ocr_result = json.loads(body)

    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="ignore")
        return {
            "status": "edocr2_error",
            "context_type": "rfq_ocr_preview",
            "rfq_id": rfq_id,
            "position_id": position_id,
            "http_status": exc.code,
            "error": error_body,
            "payload": payload,
            "write_actions_available": False,
        }

    except Exception as exc:
        return {
            "status": "edocr2_error",
            "context_type": "rfq_ocr_preview",
            "rfq_id": rfq_id,
            "position_id": position_id,
            "error": str(exc),
            "payload": payload,
            "write_actions_available": False,
        }

    return {
        "status": "ok",
        "context_type": "rfq_ocr_preview",
        "rfq_id": rfq_id,
        "position_id": position_id,
        "document": {
            "document_id": str(document.get("document_id")),
            "document_type": document.get("document_type"),
            "file_name": file_name,
            "content_type": document.get("content_type"),
            "file_size": document.get("file_size"),
            "storage_path": storage_path,
        },
        "edocr2": {
            "status": ocr_result.get("status"),
            "version": ocr_result.get("version"),
            "text_length": ocr_result.get("text_length"),
            "text_error": ocr_result.get("text_error"),
            "local_file_size": ocr_result.get("local_file_size"),
        },
        "extracted": ocr_result.get("extracted") or {},
        "text_excerpt": ocr_result.get("text_excerpt"),
        "write_actions_available": False,
    }


@router.post("/{rfq_id}/positions/{position_id}/ocr-merge", include_in_schema=False)
def rfq_position_ocr_merge(
    rfq_id: str,
    position_id: str,
):
    """
    Interne merge-route.
    Draait ED OCR2 op het RFQ-document en schrijft een nieuwe
    rfq.position_extracted_specs rij.

    Strategie:
    - behoud bestaande rijke extractievelden uit laatste specs-rij
    - vul/corrigeer kernvelden vanuit ED OCR2
    - herbereken missing_fields op basis van blocking engineering velden
    - geen GPT Action, want include_in_schema=False
    """

    preview = rfq_position_ocr_preview(
        rfq_id=rfq_id,
        position_id=position_id,
    )

    if preview.get("status") != "ok":
        return {
            "status": "error",
            "context_type": "rfq_ocr_merge",
            "rfq_id": rfq_id,
            "position_id": position_id,
            "message": "OCR preview failed; merge not executed.",
            "preview": preview,
            "write_actions_available": False,
        }

    document = preview.get("document") or {}
    edocr2 = preview.get("edocr2") or {}
    extracted = preview.get("extracted") or {}

    latest_sql = """
    SELECT *
    FROM rfq.position_extracted_specs
    WHERE rfq_id::text = :rfq_id
      AND position_id::text = :position_id
    ORDER BY created_at DESC
    LIMIT 1
    """

    with engine.begin() as conn:
        latest = conn.execute(
            text(latest_sql),
            {
                "rfq_id": rfq_id,
                "position_id": position_id,
            },
        ).mappings().first()

    latest = dict(latest) if latest else {}

    def pick(field: str):
        """
        ED OCR2 krijgt voorkeur als het veld gevuld is.
        Anders houden we de bestaande waarde uit de laatste specs-rij.
        """
        value = extracted.get(field)
        if value is not None and value != "":
            return value
        return latest.get(field)

    def keep(field: str):
        return latest.get(field)

    existing_extracted_fields = latest.get("extracted_fields") or {}
    if not isinstance(existing_extracted_fields, dict):
        existing_extracted_fields = {}

    merged_extracted_fields = dict(existing_extracted_fields)
    merged_extracted_fields.update({
        "edocr2_extracted": extracted,
        "edocr2_text_length": edocr2.get("text_length"),
        "edocr2_text_error": edocr2.get("text_error"),
        "edocr2_version": edocr2.get("version"),
    })

    # Kernvelden na merge
    merged_values = {
        "diameter_mm": pick("diameter_mm"),
        "drum_width_mm": pick("drum_width_mm"),
        "shaft_diameter_mm": pick("shaft_diameter_mm"),
        "bearing_type": pick("bearing_type"),
        "bearing_housing": pick("bearing_housing"),
        "rubber_material": pick("rubber_material"),

        # Engineering-blockers blijven behouden uit bestaande specs.
        # ED OCR2 vult deze nu nog niet betrouwbaar.
        "balancing_norm": keep("balancing_norm"),
        "seal_type": keep("seal_type"),
        "tolerance_class": keep("tolerance_class"),
        "surface_roughness": keep("surface_roughness"),
        "grease_type": keep("grease_type"),
    }

    required_blocking_fields = [
        "balancing_norm",
        "seal_type",
        "tolerance_class",
    ]

    missing_fields = [
        field
        for field in required_blocking_fields
        if not merged_values.get(field)
    ]

    warnings = latest.get("warnings") or []
    assumptions = latest.get("assumptions") or []
    supplier_scope_notes = latest.get("supplier_scope_notes") or []

    confidence_score = latest.get("confidence_score") or 0

    insert_sql = """
    INSERT INTO rfq.position_extracted_specs (
        rfq_id,
        position_id,
        source_document_id,
        extraction_method,
        extraction_model,

        diameter_mm,
        drum_width_mm,
        shaft_diameter_mm,
        bearing_type,
        bearing_housing,
        adapter_type,
        seal_type,
        balancing_norm,
        tolerance_class,
        surface_roughness,

        extracted_fields,
        missing_fields,
        warnings,
        assumptions,
        confidence_score,
        source_file_name,

        part_number,
        doc_number,
        drawing_description,
        shaft_end_diameter_mm,
        assembly_torque_nm,
        nominal_motor_torque_nm,
        belt_pull_force_kn,
        belt_speed_mps,
        rubber_thickness_mm,
        rubber_base_thickness_mm,
        rubber_profile_thickness_mm,
        drum_type,
        rotation_type,
        crowned,
        shaft_material,
        clamping_bushing_type,
        mass_kg,
        bearing_housing_type,
        supplier_scope_notes,
        grease_initial_fill_g,
        grease_regreasing_g,
        grease_type,
        rubber_material,
        rubber_hardness_shore_a,
        vulcanizing_method
    )
    VALUES (
        :rfq_id,
        :position_id,
        :source_document_id,
        :extraction_method,
        :extraction_model,

        :diameter_mm,
        :drum_width_mm,
        :shaft_diameter_mm,
        :bearing_type,
        :bearing_housing,
        :adapter_type,
        :seal_type,
        :balancing_norm,
        :tolerance_class,
        :surface_roughness,

        CAST(:extracted_fields AS jsonb),
        CAST(:missing_fields AS jsonb),
        CAST(:warnings AS jsonb),
        CAST(:assumptions AS jsonb),
        :confidence_score,
        :source_file_name,

        :part_number,
        :doc_number,
        :drawing_description,
        :shaft_end_diameter_mm,
        :assembly_torque_nm,
        :nominal_motor_torque_nm,
        :belt_pull_force_kn,
        :belt_speed_mps,
        :rubber_thickness_mm,
        :rubber_base_thickness_mm,
        :rubber_profile_thickness_mm,
        :drum_type,
        :rotation_type,
        :crowned,
        :shaft_material,
        :clamping_bushing_type,
        :mass_kg,
        :bearing_housing_type,
        CAST(:supplier_scope_notes AS jsonb),
        :grease_initial_fill_g,
        :grease_regreasing_g,
        :grease_type,
        :rubber_material,
        :rubber_hardness_shore_a,
        :vulcanizing_method
    )
    RETURNING
        spec_id,
        rfq_id,
        position_id,
        source_document_id,
        diameter_mm,
        drum_width_mm,
        shaft_diameter_mm,
        bearing_type,
        bearing_housing,
        rubber_material,
        balancing_norm,
        seal_type,
        tolerance_class,
        missing_fields,
        confidence_score,
        created_at
    """

    params = {
        "rfq_id": rfq_id,
        "position_id": position_id,
        "source_document_id": document.get("document_id"),
        "extraction_method": "edocr2_pdftotext_regex_merge",
        "extraction_model": edocr2.get("version") or "edocr2",

        "diameter_mm": merged_values.get("diameter_mm"),
        "drum_width_mm": merged_values.get("drum_width_mm"),
        "shaft_diameter_mm": merged_values.get("shaft_diameter_mm"),
        "bearing_type": merged_values.get("bearing_type"),
        "bearing_housing": merged_values.get("bearing_housing"),
        "adapter_type": keep("adapter_type"),
        "seal_type": merged_values.get("seal_type"),
        "balancing_norm": merged_values.get("balancing_norm"),
        "tolerance_class": merged_values.get("tolerance_class"),
        "surface_roughness": merged_values.get("surface_roughness"),

        "extracted_fields": json.dumps(merged_extracted_fields, default=str),
        "missing_fields": json.dumps(missing_fields, default=str),
        "warnings": json.dumps(warnings, default=str),
        "assumptions": json.dumps(assumptions, default=str),
        "confidence_score": confidence_score,
        "source_file_name": document.get("file_name"),

        "part_number": keep("part_number"),
        "doc_number": keep("doc_number"),
        "drawing_description": keep("drawing_description"),
        "shaft_end_diameter_mm": keep("shaft_end_diameter_mm"),
        "assembly_torque_nm": keep("assembly_torque_nm"),
        "nominal_motor_torque_nm": keep("nominal_motor_torque_nm"),
        "belt_pull_force_kn": keep("belt_pull_force_kn"),
        "belt_speed_mps": keep("belt_speed_mps"),
        "rubber_thickness_mm": keep("rubber_thickness_mm"),
        "rubber_base_thickness_mm": keep("rubber_base_thickness_mm"),
        "rubber_profile_thickness_mm": keep("rubber_profile_thickness_mm"),
        "drum_type": keep("drum_type"),
        "rotation_type": keep("rotation_type"),
        "crowned": keep("crowned"),
        "shaft_material": keep("shaft_material"),
        "clamping_bushing_type": keep("clamping_bushing_type"),
        "mass_kg": keep("mass_kg"),
        "bearing_housing_type": keep("bearing_housing_type"),
        "supplier_scope_notes": json.dumps(supplier_scope_notes, default=str),
        "grease_initial_fill_g": keep("grease_initial_fill_g"),
        "grease_regreasing_g": keep("grease_regreasing_g"),
        "grease_type": merged_values.get("grease_type"),
        "rubber_material": merged_values.get("rubber_material"),
        "rubber_hardness_shore_a": keep("rubber_hardness_shore_a"),
        "vulcanizing_method": keep("vulcanizing_method"),
    }

    with engine.begin() as conn:
        inserted = conn.execute(
            text(insert_sql),
            params,
        ).mappings().first()

    inserted = dict(inserted) if inserted else {}

    return {
        "status": "ok",
        "context_type": "rfq_ocr_merge",
        "rfq_id": rfq_id,
        "position_id": position_id,
        "document": document,
        "edocr2": edocr2,
        "ocr_extracted": extracted,
        "inserted_spec": inserted,
        "merge_policy": {
            "strategy": "insert_new_specs_row",
            "core_fields_from_edocr2_when_present": [
                "diameter_mm",
                "drum_width_mm",
                "shaft_diameter_mm",
                "bearing_type",
                "bearing_housing",
                "rubber_material",
            ],
            "blocking_missing_fields": required_blocking_fields,
            "preserved_from_previous_specs": True,
        },
        "write_actions_available": False,
    }


@router.post("/{rfq_id}/positions/{position_id}/technical-review-preview", include_in_schema=False)
def rfq_position_technical_review_preview(
    rfq_id: str,
    position_id: str,
):
    """
    Interne technische review-preview.
    Haalt actuele engineering-review op, zoekt technische context,
    roept techreview service aan en geeft voorstel terug.

    Schrijft nog niets naar database.
    Staat niet in OpenAPI/GPT Actions.
    """

    engineering = get_rfq_position_engineering_review(
        rfq_id=rfq_id,
        position_id=position_id,
    )

    if engineering.get("status") != "ok":
        return {
            "status": "error",
            "context_type": "rfq_technical_review_preview",
            "rfq_id": rfq_id,
            "position_id": position_id,
            "message": "Engineering review failed.",
            "engineering": engineering,
            "write_actions_available": False,
        }

    context = engineering.get("context") or {}

    known_specs = {
        "product_type": engineering.get("product_type"),
        "product_group": engineering.get("product_group"),
        "diameter_mm": context.get("diameter_mm"),
        "drum_width_mm": context.get("drum_width_mm"),
        "shaft_diameter_mm": context.get("shaft_diameter_mm"),
        "bearing_type": context.get("bearing_type"),
        "bearing_housing": context.get("bearing_housing"),
        "rubber_material": context.get("rubber_material"),
        "rubber_thickness_mm": context.get("rubber_thickness_mm"),
        "shaft_material": context.get("shaft_material"),
        "grease_initial_fill_g": context.get("grease_initial_fill_g"),
        "grease_regreasing_g": context.get("grease_regreasing_g"),
    }

    missing_fields = [
        item.get("field")
        for item in engineering.get("missing_fields") or []
        if item.get("field")
    ]

    pulley_knowledge = engineering.get("pulley_knowledge") or {}

    standard_suggestions = engineering.get("standard_suggestions") or []
    standard_supplier_questions = engineering.get("standard_supplier_questions") or []
    standard_engineering_notes = engineering.get("standard_engineering_notes") or []

    topic_groups = [
        "rfq_pulley_engineering",
        "rfq_fat_quality_requirements",
        "rfq_norms_pulleys_idlers",
        "rfq_premium_oem_selection",
    ]

    technical_context_sql = text("""
    SELECT
        item_type,
        source_code,
        topic_group,
        title,
        summary_nl,
        key_points_nl,
        structured_data
    FROM vw_gpt_technical_context
    WHERE source_code = 'PROMATI_RFQ_TECHNICAL_STANDARDS'
      AND topic_group IN :topic_groups
    ORDER BY
        CASE item_type
            WHEN 'fact' THEN 1
            WHEN 'table' THEN 2
            WHEN 'formula' THEN 3
            WHEN 'section' THEN 4
            ELSE 9
        END,
        topic_group,
        title
    LIMIT 20
    """).bindparams(bindparam("topic_groups", expanding=True))

    with engine.begin() as conn:
        tech_rows = conn.execute(
            technical_context_sql,
            {"topic_groups": topic_groups},
        ).mappings().all()

    technical_context = [dict(r) for r in tech_rows]

    payload = {
        "rfq_id": rfq_id,
        "position_id": position_id,
        "product_type": engineering.get("product_type"),
        "known_specs": known_specs,
        "missing_fields": missing_fields,

        # PROMATI normkennis / regelmotor
        "pulley_knowledge": pulley_knowledge,
        "standard_suggestions": standard_suggestions,
        "standard_supplier_questions": standard_supplier_questions,
        "standard_engineering_notes": standard_engineering_notes,

        # RAG / technische context uit database
        "technical_context": technical_context,
        "text_excerpt": None,
    }

    data = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")

    req = urllib.request.Request(
        f"{settings.TECHREVIEW_URL.rstrip('/')}/review",
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            body = response.read().decode("utf-8")
            techreview_result = json.loads(body)

    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="ignore")
        return {
            "status": "techreview_error",
            "context_type": "rfq_technical_review_preview",
            "rfq_id": rfq_id,
            "position_id": position_id,
            "http_status": exc.code,
            "error": error_body,
            "payload": payload,
            "write_actions_available": False,
        }

    except Exception as exc:
        return {
            "status": "techreview_error",
            "context_type": "rfq_technical_review_preview",
            "rfq_id": rfq_id,
            "position_id": position_id,
            "error": str(exc),
            "payload": payload,
            "write_actions_available": False,
        }

    return {
        "status": "ok",
        "context_type": "rfq_technical_review_preview",
        "rfq_id": rfq_id,
        "position_id": position_id,
        "known_specs": known_specs,
        "missing_fields": missing_fields,

        "pulley_knowledge": pulley_knowledge,
        "standard_suggestions": standard_suggestions,
        "standard_supplier_questions": standard_supplier_questions,
        "standard_engineering_notes": standard_engineering_notes,

        "technical_context_count": len(technical_context),
        "techreview": techreview_result,
        "write_actions_available": False,
    }


@router.post("/{rfq_id}/positions/{position_id}/technical-review-merge", include_in_schema=False)
def rfq_position_technical_review_merge(
    rfq_id: str,
    position_id: str,
):
    """
    Interne technische review-merge.

    Draait technical-review-preview en slaat het resultaat op in
    rfq.position_extracted_specs.extracted_fields["technical_review"].

    Belangrijk:
    - vult balancing_norm / seal_type / tolerance_class NIET automatisch
    - schrijft alleen proposal-only advies weg
    - blijft buiten OpenAPI/GPT Actions
    """

    preview = rfq_position_technical_review_preview(
        rfq_id=rfq_id,
        position_id=position_id,
    )

    if preview.get("status") != "ok":
        return {
            "status": "error",
            "context_type": "rfq_technical_review_merge",
            "rfq_id": rfq_id,
            "position_id": position_id,
            "message": "Technical review preview failed; merge not executed.",
            "preview": preview,
            "write_actions_available": False,
        }

    techreview = preview.get("techreview") or {}
    review = techreview.get("review") or {}

    if techreview.get("runtime") != "ollama" or techreview.get("model") == "stub-fallback":
        return {
            "status": "model_fallback_not_saved",
            "context_type": "rfq_technical_review_merge",
            "rfq_id": rfq_id,
            "position_id": position_id,
            "message": "TechReview viel terug naar fallback; resultaat is niet opgeslagen.",
            "techreview_model": techreview.get("model"),
            "techreview_runtime": techreview.get("runtime"),
            "engineering_notes": review.get("engineering_notes"),
            "write_actions_available": False,
        }

    latest_sql = """
    SELECT
        spec_id,
        extracted_fields
    FROM rfq.position_extracted_specs
    WHERE rfq_id::text = :rfq_id
      AND position_id::text = :position_id
    ORDER BY created_at DESC
    LIMIT 1
    """

    with engine.begin() as conn:
        latest = conn.execute(
            text(latest_sql),
            {
                "rfq_id": rfq_id,
                "position_id": position_id,
            },
        ).mappings().first()

    if not latest:
        return {
            "status": "not_found",
            "context_type": "rfq_technical_review_merge",
            "rfq_id": rfq_id,
            "position_id": position_id,
            "message": "Geen position_extracted_specs rij gevonden om technical_review aan toe te voegen.",
            "write_actions_available": False,
        }

    latest = dict(latest)

    technical_review_payload = {
        "source": "techreview_service",
        "service": techreview.get("service"),
        "version": techreview.get("version"),
        "model": techreview.get("model"),
        "runtime": techreview.get("runtime"),
        "rfq_id": rfq_id,
        "position_id": position_id,
        "known_specs": preview.get("known_specs"),
        "missing_fields": preview.get("missing_fields"),

        "pulley_knowledge": preview.get("pulley_knowledge"),
        "standard_suggestions": preview.get("standard_suggestions"),
        "standard_supplier_questions": preview.get("standard_supplier_questions"),
        "standard_engineering_notes": preview.get("standard_engineering_notes"),

        "technical_context_count": preview.get("technical_context_count"),
        "review": review,
        "rules": {
            "proposal_only": True,
            "may_auto_fill_engineering_fields": False,
            "locked_fields": [
                "balancing_norm",
                "seal_type",
                "tolerance_class",
            ],
        },
    }

    update_sql = """
    UPDATE rfq.position_extracted_specs
    SET extracted_fields =
        COALESCE(extracted_fields, '{}'::jsonb)
        || jsonb_build_object(
            'technical_review',
            CAST(:technical_review AS jsonb)
        )
    WHERE spec_id = :spec_id
    RETURNING
        spec_id,
        rfq_id,
        position_id,
        balancing_norm,
        seal_type,
        tolerance_class,
        missing_fields,
        extracted_fields,
        confidence_score,
        created_at
    """

    with engine.begin() as conn:
        updated = conn.execute(
            text(update_sql),
            {
                "spec_id": latest.get("spec_id"),
                "technical_review": json.dumps(
                    technical_review_payload,
                    ensure_ascii=False,
                    default=str,
                ),
            },
        ).mappings().first()

    updated = dict(updated) if updated else {}

    return {
        "status": "ok",
        "context_type": "rfq_technical_review_merge",
        "rfq_id": rfq_id,
        "position_id": position_id,
        "updated_spec_id": str(updated.get("spec_id")) if updated else None,
        "technical_assessment": review.get("technical_assessment"),
        "risk_level": review.get("risk_level"),
        "blocking_fields": review.get("blocking_fields"),
        "supplier_questions": review.get("supplier_questions"),
        "technical_proposals": review.get("technical_proposals"),
        "updated_spec": updated,
        "write_policy": {
            "updated_only_extracted_fields": True,
            "did_not_fill_locked_fields": [
                "balancing_norm",
                "seal_type",
                "tolerance_class",
            ],
        },
        "write_actions_available": False,
    }


@router.get("/readiness")
def rfq_readiness(
    rfq_id: str | None = None,
    position_id: str | None = None,
):
    sql = """
    SELECT
        v.rfq_id,
        v.position_id,
        v.product_type,
        v.drawing_mark,
        v.bearing_type,
        v.bearing_housing,
        v.rubber_material,
        v.diameter_mm,
        v.drum_width_mm,
        v.shaft_diameter_mm,

        es.balancing_norm,
        es.seal_type,
        es.grease_type,
        es.surface_roughness,
        es.tolerance_class,
        es.confidence_score

    FROM rfq.rfq_position_search_v1 v

    LEFT JOIN LATERAL (
        SELECT *
        FROM rfq.position_extracted_specs es
        WHERE es.rfq_id = v.rfq_id
          AND es.position_id = v.position_id
        ORDER BY es.created_at DESC
        LIMIT 1
    ) es ON true

    WHERE
        (:rfq_id IS NULL OR v.rfq_id::text = :rfq_id)
        AND (:position_id IS NULL OR v.position_id::text = :position_id)
    LIMIT 1
    """

    with engine.begin() as conn:
        row = conn.execute(
            text(sql),
            {
                "rfq_id": rfq_id,
                "position_id": position_id,
            },
        ).mappings().first()

    context = dict(row) if row else {}

    blocking_items = []
    warnings = []
    next_actions = []

    required_fields = {
        "product_type": "Producttype ontbreekt.",
        "diameter_mm": "Trommeldiameter ontbreekt.",
        "drum_width_mm": "Trommelbreedte ontbreekt.",
        "shaft_diameter_mm": "Asdiameter ontbreekt.",
        "bearing_type": "Lagertype ontbreekt.",
        "rubber_material": "Rubbermateriaal ontbreekt.",
        "balancing_norm": "Balanceernorm ontbreekt.",
        "seal_type": "Seal type / afdichting ontbreekt.",
        "tolerance_class": "Tolerantieklasse ontbreekt.",
    }

    for field, message in required_fields.items():
        if not context.get(field):
            blocking_items.append(field)
            next_actions.append(message)

    confidence = float(context.get("confidence_score") or 0)

    if confidence and confidence < 0.75:
        warnings.append("Extractiebetrouwbaarheid is lager dan 75%.")
        next_actions.append("Controleer tekening/OCR handmatig.")

    missing_count = len(blocking_items)

    readiness_score = max(0, 100 - (missing_count * 15))

    ready_for_supplier_rfq = missing_count == 0 and confidence >= 0.75
    ready_for_quotation = ready_for_supplier_rfq

    return {
        "status": "ok",
        "context_type": "rfq_readiness",
        "rfq_id": rfq_id,
        "position_id": position_id,
        "ready_for_supplier_rfq": ready_for_supplier_rfq,
        "ready_for_quotation": ready_for_quotation,
        "readiness_score": readiness_score,
        "blocking_items": blocking_items,
        "warnings": warnings,
        "next_actions": list(dict.fromkeys(next_actions)),
        "context": context,
        "write_actions_available": False,
    }


@router.get("/action-plan")
def rfq_action_plan(
    rfq_id: str | None = None,
    position_id: str | None = None,
):
    sql = """
    SELECT
        v.rfq_id,
        v.position_id,
        v.product_type,
        v.drawing_mark,
        v.bearing_type,
        v.bearing_housing,
        v.rubber_material,
        v.diameter_mm,
        v.drum_width_mm,
        v.shaft_diameter_mm,

        es.balancing_norm,
        es.seal_type,
        es.grease_type,
        es.surface_roughness,
        es.tolerance_class,
        es.confidence_score

    FROM rfq.rfq_position_search_v1 v

    LEFT JOIN LATERAL (
        SELECT *
        FROM rfq.position_extracted_specs es
        WHERE es.rfq_id = v.rfq_id
          AND es.position_id = v.position_id
        ORDER BY es.created_at DESC
        LIMIT 1
    ) es ON true

    WHERE
        (:rfq_id IS NULL OR v.rfq_id::text = :rfq_id)
        AND (:position_id IS NULL OR v.position_id::text = :position_id)
    LIMIT 1
    """

    supplier_sql = """
    SELECT COUNT(*)::int AS supplier_count
    FROM rfq.supplier
    WHERE active = true
      AND (
            :product_type IS NULL
            OR :product_type = ANY(categories)
      )
    """

    with engine.begin() as conn:
        row = conn.execute(
            text(sql),
            {
                "rfq_id": rfq_id,
                "position_id": position_id,
            },
        ).mappings().first()

    context = dict(row) if row else {}
    product_type = context.get("product_type")

    with engine.begin() as conn:
        supplier_row = conn.execute(
            text(supplier_sql),
            {"product_type": product_type},
        ).mappings().first()

    supplier_count = supplier_row["supplier_count"] if supplier_row else 0

    actions = []

    checks = {
        "balancing_norm": "Bevestig balanceernorm / balanceerklasse.",
        "seal_type": "Bevestig seal type / afdichting lagerhuis.",
        "tolerance_class": "Bevestig tolerantienorm of klasse.",
    }

    for field, action in checks.items():
        if not context.get(field):
            actions.append({
                "type": "ENGINEERING",
                "priority": "HIGH",
                "field": field,
                "action": action,
            })

    if supplier_count >= 3:
        actions.append({
            "type": "SUPPLIER_SELECTION",
            "priority": "MEDIUM",
            "action": "Selecteer primaire en backup leveranciers via supplier-package.",
        })
    else:
        actions.append({
            "type": "SUPPLIER_SELECTION",
            "priority": "HIGH",
            "action": "Voeg extra actieve leveranciers toe voor deze categorie.",
        })

    confidence = float(context.get("confidence_score") or 0)

    if confidence and confidence < 75:
        actions.append({
            "type": "DATA_QUALITY",
            "priority": "MEDIUM",
            "action": "Controleer OCR/extractie handmatig; confidence score is lager dan 75%.",
        })

    blocking_actions = [
        a for a in actions
        if a["type"] == "ENGINEERING" and a["priority"] == "HIGH"
    ]

    ready_for_supplier_rfq = len(blocking_actions) == 0

    if ready_for_supplier_rfq:
        phase = "SUPPLIER_SELECTION"
        overall_priority = "MEDIUM"
    else:
        phase = "ENGINEERING"
        overall_priority = "HIGH"

    return {
        "status": "ok",
        "context_type": "rfq_action_plan",
        "rfq_id": rfq_id,
        "position_id": position_id,
        "phase": phase,
        "priority": overall_priority,
        "ready_for_supplier_rfq": ready_for_supplier_rfq,
        "supplier_count": supplier_count,
        "actions": actions,
        "context": context,
        "write_actions_available": False,
    }


@router.get("/dashboard")
def rfq_dashboard(
    rfq_id: str,
    position_id: str,
):
    sql = """
    SELECT
        v.rfq_id,
        v.position_id,
        v.product_type,
        v.drawing_mark,
        v.bearing_type,
        v.bearing_housing,
        v.rubber_material,
        v.diameter_mm,
        v.drum_width_mm,
        v.shaft_diameter_mm,

        es.balancing_norm,
        es.seal_type,
        es.grease_type,
        es.surface_roughness,
        es.tolerance_class,
        es.confidence_score

    FROM rfq.rfq_position_search_v1 v

    LEFT JOIN LATERAL (
        SELECT *
        FROM rfq.position_extracted_specs es
        WHERE es.rfq_id = v.rfq_id
          AND es.position_id = v.position_id
        ORDER BY es.created_at DESC
        LIMIT 1
    ) es ON true

    WHERE v.rfq_id::text = :rfq_id
      AND v.position_id::text = :position_id
    LIMIT 1
    """

    with engine.begin() as conn:
        row = conn.execute(
            text(sql),
            {
                "rfq_id": rfq_id,
                "position_id": position_id,
            },
        ).mappings().first()

    context = dict(row) if row else {}

    required = {
        "balancing_norm": "Balanceernorm ontbreekt.",
        "seal_type": "Seal type / afdichting ontbreekt.",
        "tolerance_class": "Tolerantieklasse ontbreekt.",
    }

    blocking_items = []
    actions = []

    for field, message in required.items():
        if not context.get(field):
            blocking_items.append(field)
            actions.append({
                "type": "ENGINEERING",
                "priority": "HIGH",
                "field": field,
                "action": message,
            })

    confidence = float(context.get("confidence_score") or 0)

    if confidence < 75:
        actions.append({
            "type": "DATA_QUALITY",
            "priority": "MEDIUM",
            "action": "Controleer OCR/extractie handmatig; confidence score is lager dan 75%.",
        })

    readiness_score = max(0, 100 - (len(blocking_items) * 15))
    ready = len(blocking_items) == 0 and confidence >= 75

    if ready:
        phase = "SUPPLIER_SELECTION"
        priority = "MEDIUM"
        status = "READY_FOR_SUPPLIER_RFQ"
    else:
        phase = "ENGINEERING"
        priority = "HIGH"
        status = "ENGINEERING_REVIEW_REQUIRED"

    workflow = {
        "stages": [
            {
                "key": "ENGINEERING",
                "label": "Engineering",
                "active": phase == "ENGINEERING",
                "done": phase not in ["ENGINEERING"],
            },
            {
                "key": "SUPPLIER_SELECTION",
                "label": "Supplier Selection",
                "active": phase == "SUPPLIER_SELECTION",
                "done": phase in ["QUOTATIONS", "AWARD"],
            },
            {
                "key": "QUOTATIONS",
                "label": "Quotations",
                "active": phase == "QUOTATIONS",
                "done": phase == "AWARD",
            },
            {
                "key": "AWARD",
                "label": "Award",
                "active": phase == "AWARD",
                "done": False,
            },
        ],
        "current_stage": phase,
        "next_stage": "SUPPLIER_SELECTION" if phase == "ENGINEERING" else None,
        "completion": readiness_score,
    }

    return {
        "status": "ok",
        "context_type": "rfq_dashboard",
        "rfq_id": rfq_id,
        "position_id": position_id,
        "summary": {
            "status": status,
            "phase": phase,
            "priority": priority,
            "ready_for_supplier_rfq": ready,
            "readiness_score": readiness_score,
            "confidence_score": confidence,
        },
        "workflow": workflow,
        "context": context,
        "blocking_items": blocking_items,
        "actions": actions,
        "ui": {
            "style": "odoo_kanban",
            "primary_color": "#714B67",
            "status_color": "red" if not ready else "green",
        },
        "write_actions_available": False,
    }


@router.get("/supplier-selection")
def rfq_supplier_selection(
    rfq_id: str,
    position_id: str,
    limit: int = 6,
):
    context_sql = """
    SELECT
        product_type,
        bearing_type,
        bearing_housing,
        rubber_material
    FROM rfq.rfq_position_search_v1
    WHERE rfq_id::text = :rfq_id
      AND position_id::text = :position_id
    LIMIT 1
    """

    with engine.begin() as conn:
        context = conn.execute(
            text(context_sql),
            {
                "rfq_id": rfq_id,
                "position_id": position_id,
            },
        ).mappings().first()

    context = dict(context) if context else {}

    product_type = context.get("product_type")
    bearing_type = context.get("bearing_type") or context.get("bearing_housing")
    rubber_material = context.get("rubber_material")

    supplier_sql = """
    SELECT
        s.supplier_id,
        s.supplier_name,
        s.categories,
        s.specialties,

        COALESCE(sq.total_score,0) AS qualification_score,

        COALESCE(ss.quality_score,0) +
        COALESCE(ss.delivery_score,0) +
        COALESCE(ss.documentation_score,0) +
        COALESCE(ss.response_score,0) AS performance_score,

        COALESCE(ss.rfq_count,0) AS rfq_count,
        COALESCE(ss.conversion_rate,0) AS conversion_rate,

        (
            COALESCE(sq.total_score,0)
            +
            COALESCE(ss.quality_score,0)
            +
            COALESCE(ss.delivery_score,0)
            +
            COALESCE(ss.documentation_score,0)
            +
            COALESCE(ss.response_score,0)
            +
            CASE
                WHEN :product_type IS NOT NULL
                 AND :product_type = ANY(s.categories)
                THEN 50 ELSE 0
            END
            +
            CASE
                WHEN :rubber_material IS NOT NULL
                THEN 15 ELSE 0
            END
            +
            CASE
                WHEN :bearing_type IS NOT NULL
                 AND EXISTS (
                    SELECT 1 FROM unnest(s.specialties) sp
                    WHERE UPPER(sp) LIKE '%OEM%'
                       OR UPPER(sp) LIKE '%HEAVY%'
                       OR UPPER(sp) LIKE '%PREMIUM%'
                 )
                THEN 10 ELSE 0
            END
        ) AS selection_score

    FROM rfq.supplier s

    LEFT JOIN rfq.supplier_qualification sq
        ON sq.supplier_id = s.supplier_id
       AND sq.active = true

    LEFT JOIN rfq.supplier_score ss
        ON ss.supplier_id = s.supplier_id

    WHERE s.active = true
      AND (
            :product_type IS NULL
            OR :product_type = ANY(s.categories)
      )

    ORDER BY selection_score DESC
    LIMIT :limit
    """

    with engine.begin() as conn:
        rows = conn.execute(
            text(supplier_sql),
            {
                "product_type": product_type.upper() if product_type else None,
                "bearing_type": bearing_type,
                "rubber_material": rubber_material,
                "limit": limit,
            },
        ).mappings().all()

    suppliers = []
    for idx, row in enumerate(rows, start=1):
        supplier = dict(row)
        supplier["rank"] = idx
        supplier["selection_type"] = "PRIMARY" if idx <= 3 else "BACKUP"
        suppliers.append(supplier)

    return {
        "status": "ok",
        "context_type": "rfq_supplier_selection",
        "rfq_id": rfq_id,
        "position_id": position_id,
        "context": context,
        "recommended": suppliers,
        "primary_suppliers": [s for s in suppliers if s["selection_type"] == "PRIMARY"],
        "backup_suppliers": [s for s in suppliers if s["selection_type"] == "BACKUP"],
        "ready_for_write_action": False,
        "write_actions_available": False,
    }


@router.post("/supplier-selection/save")
def save_supplier_selection(
    request: SupplierSelectionRequest,
):
    with engine.begin() as conn:

        conn.execute(
            text("""
            UPDATE rfq.position_supplier_selection
            SET active = false
            WHERE rfq_id::text = :rfq_id
              AND position_id::text = :position_id
            """),
            {
                "rfq_id": request.rfq_id,
                "position_id": request.position_id,
            },
        )

        for rank_no, supplier_id in enumerate(
            request.supplier_ids,
            start=1,
        ):
            conn.execute(
                text("""
                INSERT INTO rfq.position_supplier_selection (
                    rfq_id,
                    position_id,
                    supplier_id,
                    selection_type,
                    rank_no,
                    selected_by
                )
                VALUES (
                    :rfq_id,
                    :position_id,
                    :supplier_id,
                    :selection_type,
                    :rank_no,
                    :selected_by
                )
                """),
                {
                    "rfq_id": request.rfq_id,
                    "position_id": request.position_id,
                    "supplier_id": supplier_id,
                    "selection_type":
                        "PRIMARY"
                        if rank_no <= 3
                        else "BACKUP",
                    "rank_no": rank_no,
                    "selected_by": "PROMATI",
                },
            )

    return {
        "status": "ok",
        "saved_suppliers": len(request.supplier_ids),
        "write_actions_available": False,
    }



@router.get("/selected-suppliers")
def get_selected_suppliers(
    rfq_id: str,
    position_id: str,
):
    sql = """
    SELECT
        sel.selection_id,
        sel.rfq_id,
        sel.position_id,
        sel.supplier_id,
        s.supplier_name,
        s.categories,
        s.specialties,
        sel.selection_type,
        sel.rank_no,
        sel.selected_by,
        sel.selected_at,
        sel.active
    FROM rfq.position_supplier_selection sel
    JOIN rfq.supplier s
        ON s.supplier_id = sel.supplier_id
    WHERE sel.rfq_id::text = :rfq_id
      AND sel.position_id::text = :position_id
      AND sel.active = true
    ORDER BY sel.rank_no ASC
    """

    with engine.begin() as conn:
        rows = conn.execute(
            text(sql),
            {
                "rfq_id": rfq_id,
                "position_id": position_id,
            },
        ).mappings().all()

    suppliers = [dict(r) for r in rows]

    return {
        "status": "ok",
        "context_type": "rfq_selected_suppliers",
        "rfq_id": rfq_id,
        "position_id": position_id,
        "selected_suppliers": suppliers,
        "primary_suppliers": [
            s for s in suppliers if s.get("selection_type") == "PRIMARY"
        ],
        "backup_suppliers": [
            s for s in suppliers if s.get("selection_type") == "BACKUP"
        ],
        "write_actions_available": False,
    }


@router.get("/rfq-package")
def rfq_package(
    rfq_id: str,
    position_id: str,
):
    context_sql = """
    SELECT
        v.rfq_id,
        v.position_id,
        v.product_type,
        v.drawing_mark,
        v.drawing_description,
        v.file_name,
        v.bearing_type,
        v.bearing_housing,
        v.rubber_material,
        v.diameter_mm,
        v.drum_width_mm,
        v.shaft_diameter_mm,

        es.balancing_norm,
        es.seal_type,
        es.grease_type,
        es.surface_roughness,
        es.tolerance_class,
        es.confidence_score

    FROM rfq.rfq_position_search_v1 v

    LEFT JOIN LATERAL (
        SELECT *
        FROM rfq.position_extracted_specs es
        WHERE es.rfq_id = v.rfq_id
          AND es.position_id = v.position_id
        ORDER BY es.created_at DESC
        LIMIT 1
    ) es ON true

    WHERE v.rfq_id::text = :rfq_id
      AND v.position_id::text = :position_id
    LIMIT 1
    """

    suppliers_sql = """
    SELECT
        sel.selection_id,
        sel.supplier_id,
        s.supplier_name,
        s.categories,
        s.specialties,
        sel.selection_type,
        sel.rank_no,
        sel.selected_by,
        sel.selected_at
    FROM rfq.position_supplier_selection sel
    JOIN rfq.supplier s
        ON s.supplier_id = sel.supplier_id
    WHERE sel.rfq_id::text = :rfq_id
      AND sel.position_id::text = :position_id
      AND sel.active = true
    ORDER BY sel.rank_no ASC
    """

    documents_sql = """
    SELECT
        document_id,
        document_type,
        file_name,
        content_type,
        file_size,
        storage_path,
        uploaded_by,
        created_at
    FROM rfq.position_document
    WHERE rfq_id::text = :rfq_id
      AND position_id::text = :position_id
    ORDER BY created_at DESC
    """

    with engine.begin() as conn:
        context = conn.execute(
            text(context_sql),
            {"rfq_id": rfq_id, "position_id": position_id},
        ).mappings().first()

        suppliers = conn.execute(
            text(suppliers_sql),
            {"rfq_id": rfq_id, "position_id": position_id},
        ).mappings().all()

        documents = conn.execute(
            text(documents_sql),
            {"rfq_id": rfq_id, "position_id": position_id},
        ).mappings().all()

    context = dict(context) if context else {}
    selected_suppliers = [dict(s) for s in suppliers]
    documents = [dict(d) for d in documents]

    missing_fields = []

    required_fields = {
        "balancing_norm": "Balanceernorm ontbreekt.",
        "seal_type": "Seal type / afdichting ontbreekt.",
        "tolerance_class": "Tolerantieklasse ontbreekt.",
    }

    for field, message in required_fields.items():
        if not context.get(field):
            missing_fields.append({
                "field": field,
                "message": message,
            })

    has_selected_suppliers = len(selected_suppliers) > 0
    has_documents = len(documents) > 0
    has_blocking_engineering = len(missing_fields) > 0

    ready_for_send = (
        has_selected_suppliers
        and has_documents
        and not has_blocking_engineering
    )

    return {
        "status": "ok",
        "context_type": "rfq_package",
        "rfq_id": rfq_id,
        "position_id": position_id,
        "ready_for_send": ready_for_send,
        "package_status": "READY" if ready_for_send else "NOT_READY",
        "context": context,
        "selected_suppliers": selected_suppliers,
        "documents": documents,
        "missing_fields": missing_fields,
        "checks": {
            "has_selected_suppliers": has_selected_suppliers,
            "has_documents": has_documents,
            "has_blocking_engineering": has_blocking_engineering,
        },
        "next_actions": [
            item["message"] for item in missing_fields
        ] + (
            [] if has_selected_suppliers else ["Selecteer minimaal één leverancier."]
        ) + (
            [] if has_documents else ["Voeg minimaal één tekening of technisch document toe."]
        ),
        "write_actions_available": False,
    }


@router.get("/status")
def rfq_status(
    rfq_id: str,
    position_id: str,
):
    package_sql = """
    SELECT
        v.rfq_id,
        v.position_id,
        v.product_type,
        v.drawing_mark,

        es.balancing_norm,
        es.seal_type,
        es.grease_type,
        es.surface_roughness,
        es.tolerance_class
    FROM rfq.rfq_position_search_v1 v
    LEFT JOIN LATERAL (
        SELECT *
        FROM rfq.position_extracted_specs es
        WHERE es.rfq_id = v.rfq_id
          AND es.position_id = v.position_id
        ORDER BY es.created_at DESC
        LIMIT 1
    ) es ON true
    WHERE v.rfq_id::text = :rfq_id
      AND v.position_id::text = :position_id
    LIMIT 1
    """

    supplier_sql = """
    SELECT COUNT(*)::int AS supplier_count
    FROM rfq.position_supplier_selection
    WHERE rfq_id::text = :rfq_id
      AND position_id::text = :position_id
      AND active = true
    """

    document_sql = """
    SELECT COUNT(*)::int AS document_count
    FROM rfq.position_document
    WHERE rfq_id::text = :rfq_id
      AND position_id::text = :position_id
    """

    with engine.begin() as conn:
        context = conn.execute(
            text(package_sql),
            {"rfq_id": rfq_id, "position_id": position_id},
        ).mappings().first()

        supplier_row = conn.execute(
            text(supplier_sql),
            {"rfq_id": rfq_id, "position_id": position_id},
        ).mappings().first()

        document_row = conn.execute(
            text(document_sql),
            {"rfq_id": rfq_id, "position_id": position_id},
        ).mappings().first()

    context = dict(context) if context else {}

    missing_fields = []

    required_fields = {
        "balancing_norm": "Balanceernorm ontbreekt.",
        "seal_type": "Seal type / afdichting ontbreekt.",
        "tolerance_class": "Tolerantieklasse ontbreekt.",
    }

    for field, message in required_fields.items():
        if not context.get(field):
            missing_fields.append({
                "field": field,
                "message": message,
            })

    supplier_count = supplier_row["supplier_count"] if supplier_row else 0
    document_count = document_row["document_count"] if document_row else 0
    blocking_count = len(missing_fields)

    if blocking_count > 0:
        status = "ENGINEERING_REVIEW"
        next_action = missing_fields[0]["message"]
    elif supplier_count == 0:
        status = "SUPPLIER_SELECTION_REQUIRED"
        next_action = "Selecteer minimaal één leverancier."
    elif document_count == 0:
        status = "DOCUMENTS_REQUIRED"
        next_action = "Voeg minimaal één tekening of technisch document toe."
    else:
        status = "READY_FOR_RFQ"
        next_action = "RFQ pakket kan worden vrijgegeven."

    ready_for_send = status == "READY_FOR_RFQ"

    return {
        "status": "ok",
        "context_type": "rfq_status",
        "rfq_id": rfq_id,
        "position_id": position_id,
        "rfq_workflow_status": status,
        "ready_for_send": ready_for_send,
        "supplier_count": supplier_count,
        "document_count": document_count,
        "blocking_items": blocking_count,
        "missing_fields": missing_fields,
        "next_action": next_action,
        "context": context,
        "write_actions_available": False,
    }


# Interne regressietest voor PROMATI pulley knowledge.
# Niet opnemen in OpenAPI/GPT Actions.
@router.get("/test-pulley-knowledge", include_in_schema=False)
def test_pulley_knowledge():
    from app.services.rfq_pulley_knowledge import evaluate_pulley_knowledge

    specs = {
        "product_type": "TROMMEL",
        "diameter_mm": 500,
        "drum_width_mm": 1400,
        "bearing_type": "CTL-301/140",
        "bearing_housing": "CTL-301/140",
        "rubber_material": "NBR",
    }

    missing_fields = [
        "shaft_diameter_mm",
        "balancing_norm",
        "seal_type",
        "tolerance_class",
    ]

    return {
        "status": "ok",
        "context_type": "test_pulley_knowledge",
        "specs": specs,
        "missing_fields": missing_fields,
        "pulley_knowledge": evaluate_pulley_knowledge(
            specs=specs,
            missing_fields=missing_fields,
        ),
        "write_actions_available": False,
    }