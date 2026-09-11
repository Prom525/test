import base64
import json
import os
from pathlib import Path

import fitz
from openai import OpenAI


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_VISION_MODEL = os.getenv("OPENAI_VISION_MODEL", "gpt-4.1")

USE_OPENAI_VISION = (
    os.getenv("USE_OPENAI_VISION", "false").lower() == "true"
)

client = OpenAI(api_key=OPENAI_API_KEY)

def render_pdf_first_page_to_png(pdf_path: str | Path, output_dir: str | Path) -> Path:
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(pdf_path))
    page = doc[0]

    zoom = 2.5
    matrix = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=matrix, alpha=False)

    output_path = output_dir / f"{pdf_path.stem}_page1.png"
    pix.save(str(output_path))

    return output_path


def image_to_base64(image_path: str | Path) -> str:
    image_path = Path(image_path)
    return base64.b64encode(image_path.read_bytes()).decode("utf-8")


def vision_review_pulley_drawing(
    image_path: str | Path,
    extracted_specs: dict,
    extracted_text: str = "",
) -> dict:
    if not USE_OPENAI_VISION:
        return {
            "status": "disabled",
            "reason": "Vision AI tijdelijk uitgeschakeld",
            "warnings": [],
            "suggested_specs": {},
            "field_confidence": {},
            "missing_fields": [],
            "conflicts": [],
        }

    if not OPENAI_API_KEY:
        return {
            "status": "skipped",
            "reason": "OPENAI_API_KEY ontbreekt",
            "warnings": [],
            "suggested_specs": {},
            "field_confidence": {},
            "missing_fields": [],
            "conflicts": [],
        }

    image_b64 = image_to_base64(image_path)

    prompt = f"""
Je bent een technische tekeninglezer voor transportband-trommels.

Controleer de aangeleverde tekening visueel en vergelijk met de reeds geëxtraheerde data.

Let specifiek op:
- trommeltype
- trommeldiameter DE
- mantellengte / drum width / L
- asdiameters D1/D2/D4
- totale aslengte LA
- L1, L2, M, N
- lagerhuizen
- lagers
- klembussen/adapters
- afdichtingen
- FRB-ringen
- rubberbekleding / lagging
- materiaal
- TIR
- balancering
- normen zoals ISO 2768 en ISO 1940

Belangrijk:
- ISO 2768 is een norm, geen maatvoering.
- Geef alleen waarden terug die visueel of tekstueel aannemelijk zijn.
- Als iets onzeker is: zet confidence lager.
- Geef output als strikt JSON.

Bestaande extracted_specs:
{json.dumps(extracted_specs, ensure_ascii=False)}

OCR tekst preview:
{extracted_text[:4000]}
"""

    response = client.responses.create(
        model=OPENAI_VISION_MODEL,
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": prompt,
                    },
                    {
                        "type": "input_image",
                        "image_url": f"data:image/png;base64,{image_b64}",
                    },
                ],
            }
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "pulley_vision_review",
                "schema": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string"},
                        "drawing_type": {"type": "string"},
                        "suggested_specs": {"type": "object"},
                        "field_confidence": {"type": "object"},
                        "warnings": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "missing_fields": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "conflicts": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "field": {"type": "string"},
                                    "current_value": {},
                                    "suggested_value": {},
                                    "reason": {"type": "string"},
                                },
                                "required": ["field", "reason"],
                            },
                        },
                        "summary": {"type": "string"},
                    },
                    "required": [
                        "status",
                        "drawing_type",
                        "suggested_specs",
                        "field_confidence",
                        "warnings",
                        "missing_fields",
                        "conflicts",
                        "summary",
                    ],
                    "additionalProperties": True,
                },
            }
        },
    )

    return json.loads(response.output_text)