import json
import urllib.request
from pathlib import Path


SOURCE_URL = "http://localhost:8000/openapi.json"

OUTPUT_FILE = Path(r"C:\ai-platform\api\app\openapi-gpt.json")

PUBLIC_SERVER = "https://uninveighing-nguyet-hilly.ngrok-free.dev"


GPT_PATHS = {
    "/analysis/assistant/ask",
    "/technical/assistant/ask",
    "/product/assistant/ask",
    "/rfq/assistant/ask",
    "/analysis/rfq/{rfq_id}/pdf-url/{language}",
    "/org/assistant/ask",
    "/diagnostics/assistant/ask",
    "/system/capabilities",
}

GENERIC_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {
            "type": "string"
        },
        "context_type": {
            "type": "string"
        },
        "write_actions_available": {
            "type": "boolean"
        }
    },
    "additionalProperties": True
}


RFQ_PDF_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string"
        },
        "rfq_id": {
            "type": "string"
        },
        "language": {
            "type": "string"
        },
        "pdf_id": {
            "type": "string"
        },
        "absolute_download_url": {
            "type": "string"
        }
    },
    "additionalProperties": True
}

def collect_refs(value, refs: set[str]) -> None:
    """
    Zoek recursief naar $ref-verwijzingen naar component schemas.
    """
    if isinstance(value, dict):
        ref = value.get("$ref")

        if isinstance(ref, str) and ref.startswith(
            "#/components/schemas/"
        ):
            refs.add(ref.split("/")[-1])

        for child in value.values():
            collect_refs(child, refs)

    elif isinstance(value, list):
        for child in value:
            collect_refs(child, refs)


def main() -> None:
    # -----------------------------------------------------
    # 1. Volledige FastAPI OpenAPI ophalen
    # -----------------------------------------------------

    with urllib.request.urlopen(SOURCE_URL) as response:
        source = json.load(response)

    # -----------------------------------------------------
    # 2. Alleen GPT-facing routes bewaren
    # -----------------------------------------------------

    paths = {}

    for path in GPT_PATHS:
        if path not in source.get("paths", {}):
            print(f"WAARSCHUWING: route ontbreekt: {path}")
            continue

        paths[path] = source["paths"][path]

    # -----------------------------------------------------
    # 3. GPT Action schema opschonen
    # -----------------------------------------------------

    for path, path_data in paths.items():
        for method, operation in path_data.items():
            if method.lower() not in {
                "get",
                "post",
                "put",
                "patch",
                "delete",
            }:
                continue

            if not isinstance(operation, dict):
                continue

            operation["x-openai-isConsequential"] = False

            # GPT Actions accepteert descriptions tot max. 300 tekens.
            description = operation.get("description")

            if isinstance(description, str) and len(description) > 280:
                operation["description"] = (
                    description[:277].rstrip() + "..."
                )

            # FastAPI 422-responses zijn voor GPT Actions niet nodig.
            responses = operation.get("responses", {})
            responses.pop("422", None)

            # GPT Actions wil bij object-responses expliciete properties.
            response_200 = responses.get("200")

            if isinstance(response_200, dict):
                content = response_200.setdefault(
                    "content", {}
                )

                json_content = content.setdefault(
                    "application/json", {}
                )

                if path == "/analysis/rfq/{rfq_id}/pdf-url/{language}":
                    json_content["schema"] = {
                        "$ref": "#/components/schemas/RfqPdfUrlResponse"
                    }
                else:
                    json_content["schema"] = {
                        "$ref": "#/components/schemas/GenericResponse"
                    }

    # -----------------------------------------------------
    # 4. Gebruikte schemas bepalen
    # -----------------------------------------------------

    required_schemas: set[str] = set()

    collect_refs(paths, required_schemas)

    source_schemas = (
        source.get("components", {})
        .get("schemas", {})
    )

    processed = set()

    while True:
        todo = required_schemas - processed

        if not todo:
            break

        for schema_name in todo:
            processed.add(schema_name)

            schema = source_schemas.get(schema_name)

            if schema:
                collect_refs(schema, required_schemas)

    schemas = {
        name: source_schemas[name]
        for name in sorted(required_schemas)
        if name in source_schemas
    }

    # -----------------------------------------------------
    # 5. GPT-vriendelijke response schemas toevoegen
    # -----------------------------------------------------

    schemas["GenericResponse"] = GENERIC_RESPONSE_SCHEMA
    schemas["RfqPdfUrlResponse"] = RFQ_PDF_RESPONSE_SCHEMA

    # Vrij generiek filters-object niet exposen aan GPT.
    diagnostics_schema = schemas.get(
        "DiagnosticsAskRequest",
        {},
    )

    diagnostics_properties = diagnostics_schema.get(
        "properties",
        {},
    )

    diagnostics_properties.pop("filters", None)

    # -----------------------------------------------------
    # 6. Compact GPT OpenAPI-document bouwen
    # -----------------------------------------------------

    result = {
        "openapi": source.get("openapi", "3.1.0"),
        "info": {
            "title": "PromatiGPT Hybrid Context API",
            "version": "3.1.0",
            "description": (
                "Compacte automatisch gegenereerde GPT-facing API. "
                "Backend routeert intern naar SQL, RAG, RFQ, "
                "producten, diagnostics en org-context."
            ),
        },
        "servers": [
            {
                "url": PUBLIC_SERVER,
            }
        ],
        "paths": paths,
        "components": {
            "schemas": schemas,
        },
    }

    # -----------------------------------------------------
    # 7. Bestand schrijven
    # -----------------------------------------------------

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_FILE.write_text(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(f"OK: {OUTPUT_FILE}")
    print(f"GPT-routes: {len(paths)}")
    print(f"Schemas: {len(schemas)}")

    diagnostics = schemas.get(
        "DiagnosticsAskRequest",
        {},
    )

    properties = diagnostics.get(
        "properties",
        {},
    )

    print(
        "DiagnosticsAskRequest:",
        ", ".join(properties.keys()),
    )
if __name__ == "__main__":
    main()