import json
from pathlib import Path

OPENAPI_FILE = Path("openapi-gpt.json")

NGROK_HEADER = {
    "name": "ngrok-skip-browser-warning",
    "in": "header",
    "required": True,
    "schema": {
        "type": "string",
        "enum": ["true"],
        "default": "true"
    },
    "description": "Verplicht voor ngrok free tunnel zodat de browser-warning wordt overgeslagen."
}

with OPENAPI_FILE.open("r", encoding="utf-8") as f:
    spec = json.load(f)

changed = 0

for path, path_item in spec.get("paths", {}).items():
    for method, operation in path_item.items():
        if method.lower() not in ["get"]:
            continue

        parameters = operation.setdefault("parameters", [])

        already_exists = any(
            p.get("name") == "ngrok-skip-browser-warning"
            and p.get("in") == "header"
            for p in parameters
        )

        if not already_exists:
            parameters.insert(0, NGROK_HEADER.copy())
            changed += 1
            print(f"Header toegevoegd aan GET {path}")

with OPENAPI_FILE.open("w", encoding="utf-8") as f:
    json.dump(spec, f, ensure_ascii=False, indent=2)

print(f"Klaar. Aantal aangepaste GET-actions: {changed}")