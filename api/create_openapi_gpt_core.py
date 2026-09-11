import json
import urllib.request

SOURCE_URL = "http://localhost:8000/openapi.json"
OUTPUT_FILE = "app/openapi-gpt.json"

KEEP_PATHS = {
    "/diagnostics/health",
    "/diagnostics/modules",
    "/diagnostics/overview",
    "/diagnostics/database/summary",
    "/diagnostics/database/tables",
    "/diagnostics/database/views",
    "/diagnostics/database/domain/inspections/core",
    "/diagnostics/database/domain/rfq/core",
    "/diagnostics/database/domain/crm/core",
    "/analysis/context/database/catalog",
    "/analysis/context/database/table/{schema}/{table}",

    "/analysis/context/rfq/{rfq_id}/positions/{position_id}",
    "/analysis/context/rfq/{rfq_id}/positions/{position_id}/engineering-review",
    "/analysis/rfq/list",
    "/analysis/rfq/{rfq_id}",
    "/analysis/rfq/{rfq_id}/positions",
    "/analysis/rfq/{rfq_id}/positions/{position_id}/technical-review",
    "/analysis/rfq/{rfq_id}/positions/{position_id}/documents/status",
    "/analysis/rfq/{rfq_id}/positions/{position_id}/documents",
    "/analysis/rfq/{rfq_id}/positions/{position_id}/datasheet",
    "/analysis/rfq/{rfq_id}/positions/{position_id}/datasheet/pdf-url",
    "/analysis/rfq/{rfq_id}/artifacts",
    "/analysis/rfq/{rfq_id}/pdf/list",
    "/analysis/rfq/{rfq_id}/timeline",
    "/analysis/rfq/{rfq_id}/supplier-routing",
    "/analysis/rfq/{rfq_id}/supplier-comparison",
    "/analysis/rfq/{rfq_id}/supplier-rfqs",
    "/analysis/rfq/suppliers",
    "/analysis/rfq/suppliers/kpi",

    "/inspecties",
    "/inspecties/stats/per-jaar",
    "/inspecties/stats/per-maand",
    "/inspecties/stats/top-lijnen",
    "/analysis/location/{locatie_code}/performance-v1",
    "/analysis/band/{band_code}/performance-v1",
    "/analysis/band/{band_code}/analysis-v7",
    "/analysis/band/{band_code}/diagnose",
    "/analysis/inspection-summary",
    "/analysis/inspection/latest-v2",
    "/analysis/dataset/summary",
    "/analysis/dataset/full",
    "/analysis/lijnen/{lijn_code}/bands",
    "/analysis/banden/scraper-status",
    "/analysis/banden/{band_code}/scrapers",
    "/analysis/word/config",
    "/analysis/band/{band_code}/word-config",

    "/analysis/maintenance/planning",
    "/analysis/maintenance/positions",
    "/analysis/replacement/advice",
    "/analysis/mes/latest",
    "/analysis/mes/lifecycle",
    "/analysis/mes/forecast-3mm",
    "/analysis/scraper/{scraper_type}/performance-v1",
    "/analysis/monteurs/performance",
    "/analysis/monteurs/{monteur}/findings",
    "/analysis/monteurs/{monteur}/top-problemen",

    "/products",
    "/products/slots",
    "/products/{product_id}",
    "/products/by-model/{model}",
    "/scrapers/catalog",
}

BLOCK_METHODS = {"post", "put", "patch", "delete"}

with urllib.request.urlopen(SOURCE_URL) as r:
    spec = json.loads(r.read().decode("utf-8"))

new_spec = {
    "openapi": spec.get("openapi", "3.1.0"),
    "info": {
        "title": "Promati GPT Core API",
        "version": "1.0.0",
    },
    "servers": [
        {"url": "https://uninveighing-nguyet-hilly.ngrok-free.dev"}
    ],
    "paths": {},
    "components": spec.get("components", {}),
}

for path, path_item in spec.get("paths", {}).items():
    if path not in KEEP_PATHS:
        continue

    clean_item = {}

    for method, operation in path_item.items():
        if method.lower() in BLOCK_METHODS:
            continue

        if isinstance(operation, dict):
            operation["x-openai-isConsequential"] = False

        clean_item[method] = operation

    if clean_item:
        new_spec["paths"][path] = clean_item

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(new_spec, f, indent=2, ensure_ascii=False)

print(f"Wrote {OUTPUT_FILE}")
print(f"Paths: {len(new_spec['paths'])}")