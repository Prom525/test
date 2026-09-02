from __future__ import annotations

import importlib

from fastapi import FastAPI
from app.config import settings

app = FastAPI(
    title="Promati AI Platform",
    version="10.0.1",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    servers=[{"url": settings.PUBLIC_API_URL.rstrip("/")}],
)

from fastapi.middleware.cors import CORSMiddleware

from app.routers.rfq_api import router as rfq_router

from pathlib import Path
from fastapi.responses import FileResponse, JSONResponse
import json
from app.routers.diagnostics_api import router as diagnostics_router
from app.routers import database_context
from app.routers import analysis_api_v10
from app.routers import diagnostics_api, scrapers, products, inspecties
from app.routers import promati_context
from app.routers import rfq_search_context
from app.routers import org_context
from app.routers import org_admin
from app.routers import hybrid_api
from app.routers import orchestrator_api

BASE_DIR = Path(__file__).resolve().parent

def _runtime_openapi(filename: str):
    path = BASE_DIR / filename
    data = json.loads(path.read_text(encoding="utf-8"))
    data["servers"] = [{"url": settings.PUBLIC_API_URL.rstrip("/")}]
    return JSONResponse(data)


@app.get("/openapi-gpt.json", include_in_schema=False)
def get_openapi_gpt():
    return _runtime_openapi("openapi-gpt.json")

def _optional_import(module_path: str):
    try:
        return importlib.import_module(module_path)
    except Exception:
        return None

def _include_router_if_present(
    app: FastAPI,
    module,
    prefix: str = "",
    tags: list[str] | None = None,
    attr: str = "router",
):
    if module is None:
        return
    router = getattr(module, attr, None)
    if router is None:
        return
    app.include_router(router, prefix=prefix, tags=tags or [])


@app.get("/healthz", tags=["health"])
def healthz():
    return {"status": "ok"}


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.routers import (  # noqa: E402
    berekeningen,
    calendar_line_mapping,
    inspecties,
    lijn_mapping,
    machines,
    products,
    rag,
    scrapers,
    gpt_context,
    technical,
    mobile_inspections,
    validation_inspections,
    planner_inspections,
)

@app.get("/openapi-org.json", include_in_schema=False)
def get_openapi_org():
    return _runtime_openapi("openapi-org.json")

app.include_router(products.router, tags=["products"])
app.include_router(scrapers.router, tags=["scrapers"])
app.include_router(machines.router, tags=["machines"])
app.include_router(inspecties.router, tags=["inspecties"])
app.include_router(rag.router, tags=["rag"])
app.include_router(berekeningen.router, tags=["berekeningen"])

# PROMATI_FILES_PRESIGN_DISABLED_V1
# Legacy unauthenticated MinIO presign-router bewust uitgeschakeld.
# Alleen opnieuw activeren met expliciete auth en een correcte public-presign endpoint.
app.include_router(calendar_line_mapping.router, tags=["calendar-line-mapping"])
app.include_router(lijn_mapping.router, tags=["lijn-mapping"])
app.include_router(gpt_context.router)
app.include_router(technical.router)
app.include_router(mobile_inspections.router)
app.include_router(validation_inspections.router)
app.include_router(planner_inspections.router)
app.include_router(rfq_router)
app.include_router(diagnostics_router)
app.include_router(database_context.router)
app.include_router(analysis_api_v10.router)
app.include_router(promati_context.router)
app.include_router(rfq_search_context.router)
app.include_router(org_context.router)
app.include_router(org_admin.router)
app.include_router(hybrid_api.router)
app.include_router(orchestrator_api.router)

chatdb_mod = _optional_import("app.routers.chatdb")
_include_router_if_present(app, chatdb_mod, tags=["chatdb"])

plugin_mod = _optional_import("app.routers.plugin")
_include_router_if_present(app, plugin_mod, tags=["plugin"])