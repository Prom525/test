from fastapi import FastAPI
from pydantic import BaseModel
from typing import Any

import json
import os
import re
from typing import Any

import httpx
from fastapi import FastAPI
from pydantic import BaseModel
from json_repair import repair_json


app = FastAPI(title="PROMATI TechReview Service", version="0.2.0")


class TechReviewPayload(BaseModel):
    rfq_id: str | None = None
    position_id: str | None = None
    product_type: str | None = None
    known_specs: dict[str, Any] = {}
    missing_fields: list[str] = []
    technical_context: list[dict[str, Any]] = []
    text_excerpt: str | None = None


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "techreview",
        "version": "0.2.0",
        "model": os.getenv("TECHREVIEW_MODEL", "phi3:mini"),
        "runtime": "ollama" if os.getenv("TECHREVIEW_USE_PHI", "true").lower() == "true" else "stub",
    }


def context_summaries(technical_context: list[dict[str, Any]]) -> list[str]:
    summaries = []

    for item in technical_context or []:
        title = item.get("title")
        summary = item.get("summary_nl")
        topic_group = item.get("topic_group")
        key_points = item.get("key_points_nl")

        text = " - ".join(
            str(v)
            for v in [topic_group, title, summary, key_points]
            if v
        )

        if text:
            summaries.append(text)

    return summaries[:10]


def proposal_for_field(field: str, product_type: str | None, known_specs: dict[str, Any]) -> dict[str, Any]:
    if field == "balancing_norm":
        return {
            "field": field,
            "proposal": (
                "Vraag leverancier om de vereiste balanceerklasse te bevestigen. "
                "Voor trommels is een balanceerrapport aan te bevelen; gebruik geen aangenomen klasse zonder engineeringbevestiging."
            ),
            "risk_if_missing": (
                "Onbekende balanceereis kan leiden tot trillingen, lagerbelasting, kortere levensduur "
                "en slecht vergelijkbare leveranciersoffertes."
            ),
            "supplier_question": (
                "Bevestig de balanceerklasse/norm voor deze trommel en lever een balancing report mee."
            ),
            "may_auto_fill": False,
            "requires_engineering_confirmation": True,
            "confidence": "medium",
        }

    if field == "seal_type":
        bearing = known_specs.get("bearing_type") or known_specs.get("bearing_housing")

        return {
            "field": field,
            "proposal": (
                f"Bevestig het afdichtingsconcept voor lager/lagerhuis {bearing}."
                if bearing
                else "Bevestig het afdichtingsconcept voor het lagerhuis."
            ),
            "risk_if_missing": (
                "Zonder afdichtingstype is de geschiktheid voor stof, vocht en vervuiling niet goed te beoordelen."
            ),
            "supplier_question": (
                "Bevestig seal type / afdichtingsconcept van het lagerhuis en vermeld of dit geschikt is voor de bedrijfsomgeving."
            ),
            "may_auto_fill": False,
            "requires_engineering_confirmation": True,
            "confidence": "medium",
        }

    if field == "tolerance_class":
        return {
            "field": field,
            "proposal": (
                "Vraag leverancier om de toegepaste tolerantienorm of toleranties op kritische maten te bevestigen, "
                "met name aszittingen, lagerpassingen, trommeldiameter en mantellengte."
            ),
            "risk_if_missing": (
                "Onbekende toleranties kunnen leiden tot montageproblemen, verkeerde passingen of niet-vergelijkbare offertes."
            ),
            "supplier_question": (
                "Bevestig de toegepaste tolerantienorm/klasse en kritische toleranties voor as-, lager- en trommelmaten."
            ),
            "may_auto_fill": False,
            "requires_engineering_confirmation": True,
            "confidence": "medium",
        }

    return {
        "field": field,
        "proposal": "Laat dit veld technisch bevestigen voordat de RFQ wordt vrijgegeven.",
        "risk_if_missing": "Onvolledige technische specificatie.",
        "supplier_question": f"Bevestig {field}.",
        "may_auto_fill": False,
        "requires_engineering_confirmation": True,
        "confidence": "low",
    }


def stub_review(payload: TechReviewPayload, note: str | None = None) -> dict[str, Any]:
    product_type = payload.product_type
    known_specs = payload.known_specs or {}
    missing_fields = payload.missing_fields or []

    technical_proposals = {
        field: proposal_for_field(field, product_type, known_specs)
        for field in missing_fields
    }

    supplier_questions = [
        proposal["supplier_question"]
        for proposal in technical_proposals.values()
        if proposal.get("supplier_question")
    ]

    engineering_notes = []

    if note:
        engineering_notes.append(note)

    if known_specs.get("diameter_mm") and known_specs.get("drum_width_mm"):
        engineering_notes.append(
            f"Hoofdafmetingen herkend: Ø{known_specs.get('diameter_mm')} x {known_specs.get('drum_width_mm')} mm."
        )

    if known_specs.get("shaft_diameter_mm"):
        engineering_notes.append(
            f"Asdiameter herkend: {known_specs.get('shaft_diameter_mm')} mm."
        )

    if known_specs.get("bearing_type") or known_specs.get("bearing_housing"):
        engineering_notes.append(
            f"Lager/lagerhuis herkend: {known_specs.get('bearing_type') or known_specs.get('bearing_housing')}."
        )

    if known_specs.get("rubber_material"):
        engineering_notes.append(
            f"Rubbermateriaal herkend: {known_specs.get('rubber_material')}."
        )

    return {
        "technical_assessment": (
            "ENGINEERING_REVIEW_REQUIRED"
            if missing_fields
            else "READY_FOR_TECHNICAL_RELEASE"
        ),
        "risk_level": "MEDIUM" if missing_fields else "LOW",
        "do_not_send_to_supplier_yet": bool(missing_fields),
        "blocking_fields": missing_fields,
        "technical_proposals": technical_proposals,
        "supplier_questions": supplier_questions,
        "engineering_notes": engineering_notes,
        "context_used": context_summaries(payload.technical_context),
        "rules": {
            "proposal_only_fields": [
                "balancing_norm",
                "seal_type",
                "tolerance_class",
            ],
            "auto_fill_allowed": False,
        },
    }


def build_phi_prompt(payload: TechReviewPayload) -> str:
    compact_payload = {
        "role": "PROMATI technische RFQ-assistent",
        "instruction": (
            "Geef uitsluitend JSON. Geen markdown. Geen uitleg buiten JSON. "
            "Maak per ontbrekend veld een voorstel, risico en leveranciersvraag. "
            "Vul geen definitieve specificaties in."
        ),
        "output_shape": {
            "field_advice": {
                "balancing_norm": {
                    "proposal": "tekst",
                    "risk_if_missing": "tekst",
                    "supplier_question": "tekst",
                    "confidence": "low|medium|high"
                }
            },
            "engineering_notes": [
                "tekst"
            ],
            "context_used": [
                "korte bronverwijzing"
            ]
        },
        "locked_fields": [
            "balancing_norm",
            "seal_type",
            "tolerance_class"
        ],
        "product_type": payload.product_type,
        "known_specs": payload.known_specs,
        "missing_fields": payload.missing_fields,
        "technical_context": context_summaries(payload.technical_context)[:5],
    }

    return json.dumps(compact_payload, ensure_ascii=False, default=str)


def parse_model_json(raw_response: str) -> dict[str, Any]:
    text = (raw_response or "").strip()

    # Markdown fences verwijderen als het model die toch geeft.
    text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"^```\s*", "", text).strip()
    text = re.sub(r"\s*```$", "", text).strip()

    # Eerste normale parse.
    try:
        return json.loads(text)
    except Exception:
        pass

    # Probeer alleen het JSON-object uit de tekst te halen.
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        candidate = match.group(0).strip()

        try:
            return json.loads(candidate)
        except Exception:
            pass

        # Laat json-repair veelvoorkomende model-fouten herstellen:
        # ontbrekende komma's, trailing commas, quotes, enz.
        try:
            repaired = repair_json(candidate)
            return json.loads(repaired)
        except Exception:
            pass

    # Laatste poging op volledige tekst.
    try:
        repaired = repair_json(text)
        return json.loads(repaired)
    except Exception as exc:
        raise ValueError(f"Model gaf geen herstelbaar JSON terug: {exc}")


def normalize_review(review: dict[str, Any], payload: TechReviewPayload) -> dict[str, Any]:
    missing_fields = payload.missing_fields or []

    raw_proposals = review.get("technical_proposals") or review.get("technical-proposals") or {}

    canonical_proposals = {}

    for field in missing_fields:
        fallback = proposal_for_field(
            field,
            payload.product_type,
            payload.known_specs or {},
        )

        model_key_variants = [
            field,
            field.replace("_", "-"),
        ]

        model_proposal = {}
        for key in model_key_variants:
            if isinstance(raw_proposals, dict) and isinstance(raw_proposals.get(key), dict):
                model_proposal = raw_proposals.get(key) or {}
                break

        proposal_text = (
            model_proposal.get("proposal")
            or fallback.get("proposal")
        )

        risk_text = (
            model_proposal.get("risk_if_missing")
            or model_proposal.get("risk-if-missing")
            or fallback.get("risk_if_missing")
        )

        supplier_question = (
            model_proposal.get("supplier_question")
            or model_proposal.get("supplier-question")
            or fallback.get("supplier_question")
        )

        confidence = (
            model_proposal.get("confidence")
            or fallback.get("confidence")
            or "medium"
        )

        canonical_proposals[field] = {
            "field": field,
            "proposal": proposal_text,
            "risk_if_missing": risk_text,
            "supplier_question": supplier_question,
            "may_auto_fill": False,
            "requires_engineering_confirmation": True,
            "confidence": confidence,
        }

    supplier_questions = [
        proposal["supplier_question"]
        for proposal in canonical_proposals.values()
        if proposal.get("supplier_question")
    ]

    engineering_notes = (
        review.get("engineering_notes")
        or review.get("engineering-notes")
        or []
    )
    if not isinstance(engineering_notes, list):
        engineering_notes = []

    engineering_notes = [
        note
        for note in engineering_notes
        if str(note).strip().lower() not in ["tekst", "note", "engineering note"]
    ]

    known_specs = payload.known_specs or {}

    if known_specs.get("diameter_mm") and known_specs.get("drum_width_mm"):
        engineering_notes.append(
            f"Hoofdafmetingen herkend: Ø{known_specs.get('diameter_mm')} x {known_specs.get('drum_width_mm')} mm."
        )

    if known_specs.get("shaft_diameter_mm"):
        engineering_notes.append(
            f"Asdiameter herkend: {known_specs.get('shaft_diameter_mm')} mm."
        )

    if known_specs.get("bearing_type") or known_specs.get("bearing_housing"):
        engineering_notes.append(
            f"Lager/lagerhuis herkend: {known_specs.get('bearing_type') or known_specs.get('bearing_housing')}."
        )

    if known_specs.get("rubber_material"):
        engineering_notes.append(
            f"Rubbermateriaal herkend: {known_specs.get('rubber_material')}."
        )

    context_used = (
        review.get("context_used")
        or review.get("context-used")
        or context_summaries(payload.technical_context)
    )

    if not isinstance(context_used, list):
        context_used = context_summaries(payload.technical_context)

    context_used = [
        item
        for item in context_used
        if str(item).strip().lower() not in [
            "korte bronverwijzing",
            "bronverwijzing",
            "context",
        ]
    ]

    if not context_used:
        context_used = context_summaries(payload.technical_context)

    return {
        "technical_assessment": (
            "ENGINEERING_REVIEW_REQUIRED"
            if missing_fields
            else "READY_FOR_TECHNICAL_RELEASE"
        ),
        "risk_level": "MEDIUM" if missing_fields else "LOW",
        "do_not_send_to_supplier_yet": bool(missing_fields),
        "blocking_fields": missing_fields,
        "technical_proposals": canonical_proposals,
        "supplier_questions": supplier_questions,
        "engineering_notes": engineering_notes,
        "context_used": context_used,
        "rules": {
            "proposal_only_fields": [
                "balancing_norm",
                "seal_type",
                "tolerance_class",
            ],
            "auto_fill_allowed": False,
        },
    }


def call_phi3_review(payload: TechReviewPayload) -> dict[str, Any]:
    ollama_url = os.getenv("OLLAMA_URL")
    if not ollama_url:
        raise RuntimeError("OLLAMA_URL is not configured")
    model = os.getenv("TECHREVIEW_MODEL", "phi3:mini")

    last_error = None

    for attempt in [1, 2]:
        request_body = {
            "model": model,
            "prompt": build_phi_prompt(payload),
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.0,
                "num_predict": 500 if attempt == 1 else 350,
            },
        }

        try:
            with httpx.Client(timeout=180) as client:
                response = client.post(ollama_url, json=request_body)
                response.raise_for_status()
                data = response.json()

            raw_response = data.get("response") or "{}"
            review = parse_model_json(raw_response)
            normalized = normalize_review(review, payload)

            normalized.setdefault("model_runtime_notes", [])
            normalized["model_runtime_notes"].append(
                f"Phi-3 Mini JSON parse ok on attempt {attempt}."
            )

            return normalized

        except Exception as exc:
            last_error = exc

    raise ValueError(f"Phi-3 Mini gaf na retry geen geldig JSON terug: {last_error}")


@app.post("/review")
def review(payload: TechReviewPayload):
    use_phi = os.getenv("TECHREVIEW_USE_PHI", "true").lower() == "true"

    if use_phi:
        try:
            review_result = call_phi3_review(payload)
            return {
                "status": "ok",
                "service": "techreview",
                "version": "0.2.0",
                "model": os.getenv("TECHREVIEW_MODEL", "phi3:mini"),
                "runtime": "ollama",
                "rfq_id": payload.rfq_id,
                "position_id": payload.position_id,
                "review": review_result,
            }
        except Exception as exc:
            return {
                "status": "ok",
                "service": "techreview",
                "version": "0.2.0",
                "model": "stub-fallback",
                "runtime": "fallback",
                "rfq_id": payload.rfq_id,
                "position_id": payload.position_id,
                "review": stub_review(
                    payload,
                    note=f"Phi-3 Mini fallback actief: {exc}",
                ),
            }

    return {
        "status": "ok",
        "service": "techreview",
        "version": "0.2.0",
        "model": "stub",
        "runtime": "stub",
        "rfq_id": payload.rfq_id,
        "position_id": payload.position_id,
        "review": stub_review(payload),
    }