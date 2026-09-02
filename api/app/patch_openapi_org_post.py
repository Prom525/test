import json
from pathlib import Path

OPENAPI_FILE = Path("openapi-gpt.json")

with OPENAPI_FILE.open("r", encoding="utf-8") as f:
    spec = json.load(f)

# verwijder eventuele ngrok header-parameters
for path_item in spec.get("paths", {}).values():
    for operation in path_item.values():
        if isinstance(operation, dict):
            operation["parameters"] = [
                p for p in operation.get("parameters", [])
                if p.get("name") != "ngrok-skip-browser-warning"
            ]

paths = spec["paths"]

paths["/analysis/context/org/internal-help"] = {
    "post": {
        "tags": ["org-context"],
        "summary": "Internal Help And Routing",
        "operationId": "internal_help_analysis_context_org_internal_help_get",
        "description": "Gebruik dit endpoint voor interne hulpvragen. POST wordt gebruikt om ngrok browser-warning bij GET te vermijden.",
        "x-openai-isConsequential": False,
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "q": {
                                "type": "string",
                                "description": "Volledige originele gebruikersvraag."
                            },
                            "firma": {"type": "string"},
                            "locatie": {"type": "string"},
                            "afdeling": {"type": "string"}
                        },
                        "required": ["q"],
                        "additionalProperties": False
                    }
                }
            }
        },
        "responses": {
            "200": {
                "description": "Successful Response",
                "content": {
                    "application/json": {
                        "schema": {
                            "$ref": "#/components/schemas/GenericObject"
                        }
                    }
                }
            }
        }
    }
}

paths["/analysis/context/org/location-info"] = {
    "post": {
        "tags": ["org-context"],
        "summary": "Get Promati location information",
        "operationId": "location_info_analysis_context_org_location_info_get",
        "description": "Gebruik dit endpoint voor locatiegegevens. POST wordt gebruikt om ngrok browser-warning bij GET te vermijden.",
        "x-openai-isConsequential": False,
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "firma": {
                                "type": "string",
                                "default": "Promati"
                            },
                            "locatie": {"type": "string"},
                            "q": {
                                "type": "string",
                                "description": "Volledige originele gebruikersvraag."
                            }
                        },
                        "additionalProperties": False
                    }
                }
            }
        },
        "responses": {
            "200": {
                "description": "Successful Response",
                "content": {
                    "application/json": {
                        "schema": {
                            "$ref": "#/components/schemas/GenericObject"
                        }
                    }
                }
            }
        }
    }
}

with OPENAPI_FILE.open("w", encoding="utf-8") as f:
    json.dump(spec, f, ensure_ascii=False, indent=2)

print("OpenAPI aangepast: org internal-help en location-info gebruiken nu POST.")