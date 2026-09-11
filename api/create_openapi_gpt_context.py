import json
import urllib.request

SOURCE_URL = "http://localhost:8000/openapi.json"
OUTPUT_FILE = "app/openapi-gpt.json"

KEEP_PATHS = {
    "/analysis/context/system",

    # RFQ context
    "/analysis/context/rfq/{rfq_id}/positions/{position_id}",
    "/analysis/context/rfq/{rfq_id}/positions/{position_id}/engineering-review",
    "/analysis/context/rfq/search",
    "/analysis/context/rfq/supplier-recommendation",
    "/analysis/context/rfq/similar",
    "/analysis/context/rfq/supplier-package",
    "/analysis/context/rfq/risk-review",
    "/analysis/context/rfq/readiness",
    "/analysis/context/rfq/action-plan",
    "/analysis/context/rfq/dashboard",
    "/analysis/context/rfq/supplier-selection",
    "/analysis/context/rfq/supplier-selection/save",
    "/analysis/context/rfq/rfq-package",
    "/analysis/context/rfq/status",

    # PROMATI context
    "/analysis/context/line/{lijn_code}",
    "/analysis/context/belt/{band_code}",
    "/analysis/context/product/scrapers",

    # Database context
    "/analysis/context/database/catalog",
    "/analysis/context/database/table/{schema}/{table}",

    # Inspecties
    "/analysis/inspections/recent",

    # Diagnostics
    "/diagnostics/overview",
    "/diagnostics/modules",
}

with urllib.request.urlopen(SOURCE_URL) as r:
    spec = json.loads(r.read().decode("utf-8"))

new_spec = {
    "openapi": spec.get("openapi", "3.1.0"),
    "info": {
        "title": "Promati Context API",
        "version": "2.0.0",
    },
    "servers": [
        {"url": "https://uninveighing-nguyet-hilly.ngrok-free.dev"}
    ],
    "paths": {},
    "components": {
        "schemas": {
            "GenericObject": {
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
        }
    },
}

for path, path_item in spec.get("paths", {}).items():
    if path not in KEEP_PATHS:
        continue

    clean_item = {}

    for method, operation in path_item.items():
        if method.lower() != "get":
            continue

        operation["x-openai-isConsequential"] = False

        for status, response in operation.get("responses", {}).items():
            if status.startswith("2"):
                response["content"] = {
                    "application/json": {
                        "schema": {
                            "$ref": "#/components/schemas/GenericObject"
                        }
                    }
                }

        clean_item[method] = operation

    if clean_item:
        new_spec["paths"][path] = clean_item

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(new_spec, f, indent=2, ensure_ascii=False)

print(f"Wrote {OUTPUT_FILE}")
print(f"Paths: {len(new_spec['paths'])}")