from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.db import engine

from app.schemas import RAGQuery
from app.routers.rag import rag_query

from uuid import UUID

router = APIRouter(prefix="/analysis/context", tags=["gpt-context"])


def fetch_one(sql: str, params: dict[str, Any] | None = None):
    with engine.connect() as conn:
        row = conn.execute(text(sql), params or {}).mappings().first()
        return dict(row) if row else None


def fetch_all(sql: str, params: dict[str, Any] | None = None):
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params or {}).mappings().all()
        return [dict(r) for r in rows]


def calculate_engineering_completeness(specs: dict[str, Any] | None) -> dict[str, Any]:
    specs = specs or {}

    groups = {
        "geometry": [
            "diameter_mm",
            "outside_diameter_mm",
            "drum_width_mm",
            "total_length_mm",
            "shaft_diameter_mm",
        ],
        "materials": [
            "shaft_material",
            "shell_material",
            "rubber_material",
        ],
        "lagging": [
            "lagging_type",
            "rubber_thickness_mm",
            "rubber_hardness_shore_a",
            "vulcanizing_method",
        ],
        "bearing_set": [
            "bearing_housing",
            "bearing_type",
            "seal_type",
        ],
        "production": [
            "balancing_norm",
            "tolerance_class",
            "surface_roughness",
        ],
        "lubrication": [
            "grease_initial_fill_g",
            "grease_regreasing_g",
            "grease_type",
        ],
    }

    result = {}
    total_required = 0
    total_filled = 0
    missing_by_group = {}

    for group_name, fields in groups.items():
        filled = [field for field in fields if specs.get(field) not in (None, "", [], {})]
        missing = [field for field in fields if field not in filled]

        score = round((len(filled) / len(fields)) * 100, 1) if fields else 0

        result[group_name] = {
            "score": score,
            "filled": filled,
            "missing": missing,
        }

        missing_by_group[group_name] = missing
        total_required += len(fields)
        total_filled += len(filled)

    overall = round((total_filled / total_required) * 100, 1) if total_required else 0

    return {
        "overall_score": overall,
        "groups": result,
        "missing_by_group": missing_by_group,
    }


def build_rag_query(rfq: dict[str, Any], position: dict[str, Any], specs: dict[str, Any]) -> str:
    parts = [
        "technical pulley engineering standard",
        str(position.get("product_type") or ""),
        str(specs.get("drum_type") or ""),
        str(specs.get("bearing_housing") or ""),
        str(specs.get("bearing_type") or ""),
        str(specs.get("lagging_type") or ""),
        str(specs.get("rubber_material") or ""),
        str(specs.get("balancing_norm") or ""),
        str(specs.get("tolerance_class") or ""),
    ]

    return " ".join([p for p in parts if p and p != "None"]).strip()


def fetch_rag_context_safe(query: str) -> dict[str, Any]:
    try:
        body = RAGQuery(vraag=query, top_k=3, answer_mode="extractive")
        result = rag_query(body)

        return {
            "status": "ok",
            "provider": result.get("provider"),
            "embed_model": result.get("embed_model"),
            "context_hits": result.get("context_hits", []),
            "used_context": result.get("used_context", []),
        }

    except Exception as exc:
        return {
            "status": "error",
            "error": str(exc),
            "context_hits": [],
            "used_context": [],
        }


def build_engineering_review(
    specs: dict[str, Any],
    completeness: dict[str, Any],
    rag_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    specs = specs or {}
    groups = completeness.get("groups", {}) if completeness else {}

    missing = []
    for group in groups.values():
        missing.extend(group.get("missing", []))

    risks = []
    recommendations = []
    supplier_questions = []

    if "seal_type" in missing:
        risks.append("Bearing sealing is not specified.")
        recommendations.append("Confirm seal arrangement for the bearing housing.")
        supplier_questions.append("Please specify the seal type / sealing arrangement for the bearing housing.")

    if "balancing_norm" in missing:
        risks.append("Balancing norm is missing.")
        recommendations.append("Define balancing requirement, for example ISO 1940 / ISO 21940 class if applicable.")
        supplier_questions.append("Please confirm the required balancing norm and class.")

    if "surface_roughness" in missing:
        recommendations.append("Confirm surface roughness requirements for shaft seats and machined surfaces.")
        supplier_questions.append("Please confirm surface roughness requirements for machined surfaces.")

    if "tolerance_class" in missing:
        recommendations.append("Confirm general tolerance class or refer explicitly to drawing standard.")
        supplier_questions.append("Please confirm the general tolerance class.")

    if "grease_type" in missing:
        recommendations.append("Confirm grease type for initial fill and regreasing.")
        supplier_questions.append("Please specify the grease type used for initial fill and regreasing.")

    if specs.get("bearing_housing") and not specs.get("seal_type"):
        risks.append("Bearing housing is detected, but seal type is absent.")

    if specs.get("rubber_material") and not specs.get("rubber_hardness_shore_a"):
        risks.append("Rubber material is known, but hardness is missing.")

    if specs.get("shaft_diameter_mm") and specs.get("diameter_mm"):
        ratio = float(specs["shaft_diameter_mm"]) / float(specs["diameter_mm"])
        if ratio < 0.15:
            risks.append("Shaft diameter appears low compared with drum diameter.")
            recommendations.append("Check shaft calculation against belt pull, torque and fatigue.")

    review_status = "READY_FOR_SUPPLIER_RFQ"
    if completeness.get("overall_score", 0) < 85:
        review_status = "ENGINEERING_REVIEW_REQUIRED"
    if risks:
        review_status = "ENGINEERING_REVIEW_REQUIRED"

    return {
        "review_status": review_status,
        "overall_score": completeness.get("overall_score"),
        "missing_fields": sorted(set(missing)),
        "risks": sorted(set(risks)),
        "recommendations": sorted(set(recommendations)),
        "supplier_questions": sorted(set(supplier_questions)),
        "rag_status": (rag_context or {}).get("status"),
    }


@router.get("/rfq/{rfq_id}/positions/{position_id}")
def get_rfq_position_gpt_context(rfq_id: str, position_id: str):
    try:
        UUID(rfq_id)
        UUID(position_id)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail="RFQ or position not found"
        )
    rfq = fetch_one(
        """
        SELECT *
        FROM rfq.request
        WHERE rfq_id = :rfq_id
        """,
        {"rfq_id": rfq_id},
    )
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found")

    position = fetch_one(
        """
        SELECT *
        FROM rfq.position
        WHERE rfq_id = :rfq_id
          AND position_id = :position_id
        """,
        {
            "rfq_id": rfq_id,
            "position_id": position_id,
        },
    )

    if not position:
        raise HTTPException(status_code=404, detail="RFQ position not found")

    latest_specs = fetch_one(
        """
        SELECT *
        FROM rfq.position_extracted_specs
        WHERE rfq_id = :rfq_id
          AND position_id = :position_id
        ORDER BY created_at DESC
        LIMIT 1
        """,
        {
            "rfq_id": rfq_id,
            "position_id": position_id,
        },
    )

    documents = fetch_all(
        """
        SELECT
            pd.*,
            d.file_hash_sha256,
            d.stored_path AS document_stored_path,
            d.extracted_text AS document_extracted_text
        FROM rfq.position_document pd
        LEFT JOIN rfq.document d
          ON d.document_id = pd.document_id
         AND d.rfq_id = pd.rfq_id
        WHERE pd.rfq_id = :rfq_id
          AND pd.position_id = :position_id
        ORDER BY pd.created_at DESC
        """,
        {
            "rfq_id": rfq_id,
            "position_id": position_id,
        },
    )

    document_texts = fetch_all(
        """
        SELECT
            text_id,
            document_id,
            rfq_id,
            position_id,
            page_count,
            extraction_status,
            extraction_model,
            extracted_at,
            LEFT(extracted_text, 12000) AS extracted_text_preview
        FROM rfq.position_document_text
        WHERE rfq_id = :rfq_id
          AND position_id = :position_id
        ORDER BY extracted_at DESC
        """,
        {
            "rfq_id": rfq_id,
            "position_id": position_id,
        },
    )

    latest_document_text = document_texts[0] if document_texts else None
    document_history_count = len(document_texts)

    artifacts = fetch_all(
        """
        SELECT *
        FROM rfq.artifact
        WHERE rfq_id = :rfq_id
          AND (
            position_id = :position_id
            OR position_id IS NULL
          )
        ORDER BY created_at DESC
        """,
        {
            "rfq_id": rfq_id,
            "position_id": position_id,
        },
    )

    latest_fields = {}
    if latest_specs and latest_specs.get("extracted_fields"):
        latest_fields = latest_specs["extracted_fields"]
    elif position and position.get("extracted_specs"):
        latest_fields = position["extracted_specs"]

    engineering_completeness = calculate_engineering_completeness(latest_fields)

    rag_search_query = build_rag_query(rfq, position, latest_fields)
    rag_context = fetch_rag_context_safe(rag_search_query)

    engineering_review = build_engineering_review(
        specs=latest_fields,
        completeness=engineering_completeness,
        rag_context=rag_context,
    )

    return {
        "status": "ok",
        "context_type": "rfq_position",
        "rfq_id": rfq_id,
        "position_id": position_id,
        "rfq": rfq,
        "position": position,
        "latest_extracted_specs": latest_specs,
        "documents": documents,
        "latest_document_text": latest_document_text,
        "document_history_count": document_history_count,
        "document_texts": document_texts,
        "artifacts": artifacts,
        "engineering_completeness": engineering_completeness,
        "engineering_review": engineering_review,
        "rag_query": rag_search_query,
        "rag_context": rag_context,
        "write_actions_available": False,
    }


@router.get("/rfq/{rfq_id}/positions/{position_id}/engineering-review")
def get_rfq_position_engineering_review(rfq_id: str, position_id: str):
    context = get_rfq_position_gpt_context(rfq_id, position_id)

    latest_specs = context.get("latest_extracted_specs") or {}
    latest_fields = latest_specs.get("extracted_fields") or {}

    if not latest_fields:
        latest_fields = (context.get("position") or {}).get("extracted_specs") or {}

    review = build_engineering_review(
        specs=latest_fields,
        completeness=context.get("engineering_completeness") or {},
        rag_context=context.get("rag_context") or {},
    )

    return {
        "status": "ok",
        "context_type": "engineering_review",
        "rfq_id": rfq_id,
        "position_id": position_id,
        "review": review,
        "write_actions_available": False,
    }