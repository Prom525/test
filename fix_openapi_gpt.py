import json
from pathlib import Path

path = Path(r"C:\ai-platform\openapi-gpt.json")

data = json.loads(path.read_text(encoding="utf-8-sig"))

# 1. Assistant ask operation fixen
ask = data["paths"]["/analysis/assistant/ask"]["post"]
ask["operationId"] = "analysis_assistant_ask"
ask["summary"] = "Assistant Ask"
ask["description"] = (
    "Primaire vrije-vraag ingang voor inspecties, banden, actuele bandstatus, "
    "schrapers, meshoogtes, lifecycle, forecast en onderhoud. Gebruik dit voor "
    "vragen zoals: wat zit er nu op band R5 van MV1?"
)

# 2. Technical/context schema fixen en generiek alle 200 object schemas zonder properties fixen
default_schema = {
    "type": "object",
    "properties": {
        "status": {"type": "string"},
        "context_type": {"type": "string"},
        "result": {
            "type": "object",
            "additionalProperties": True
        }
    },
    "additionalProperties": True
}

for path_name, path_obj in data.get("paths", {}).items():
    for method_name, method_obj in path_obj.items():
        if method_name.lower() not in {"get", "post", "put", "patch", "delete"}:
            continue

        responses = method_obj.get("responses", {})
        resp_200 = responses.get("200")
        if not resp_200:
            continue

        content = resp_200.setdefault("content", {})
        app_json = content.setdefault("application/json", {})
        schema = app_json.setdefault("schema", {})

        # Als schema object is zonder properties: properties toevoegen
        if schema.get("type") == "object" and "properties" not in schema:
            schema["properties"] = default_schema["properties"]
            schema["additionalProperties"] = True

        # Als schema leeg is: volledig default schema zetten
        if not schema:
            app_json["schema"] = default_schema

# 3. Component AssistantAskRequest eventueel verkorten/netjes houden
components = data.setdefault("components", {}).setdefault("schemas", {})
components["AssistantAskRequest"] = {
    "type": "object",
    "properties": {
        "vraag": {
            "type": "string",
            "description": "Vrije gebruikersvraag, bijvoorbeeld: wat zit er nu op band R5 van MV1?"
        },
        "lijn_code": {"type": "string", "nullable": True},
        "date_from": {"type": "string", "nullable": True},
        "date_to": {"type": "string", "nullable": True},
        "band_code": {"type": "string", "nullable": True},
        "scraper_type": {"type": "string", "nullable": True},
        "zijde": {"type": "string", "nullable": True},
        "limit": {
            "type": "integer",
            "default": 20,
            "minimum": 1,
            "maximum": 50
        }
    },
    "required": ["vraag"],
    "additionalProperties": True
}

path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

print("OK geschreven:", path)
print("Aantal paths:", len(data["paths"]))
print("operationId:", data["paths"]["/analysis/assistant/ask"]["post"]["operationId"])
print("description length:", len(data["paths"]["/analysis/assistant/ask"]["post"]["description"]))
