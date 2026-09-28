"""Docker-attested test of the real app.main registration/OpenAPI boundary.

The outer test does not import app and skips before probing unless the dedicated
runner attested Docker isolation. The inner process uses only synthetic
configuration, imports real app.main, then calls real app.openapi(). The only
mocks are import-time MetaData.create_all, Qdrant's compatibility thread, and
the known import-time MinIO bucket-existence check; bucket creation is forbidden.
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch


_HARNESS_MARKER = "docker-inspect-v1"
_EXCLUDED = {
    ("GET", "/openapi-gpt.json", "get_openapi_gpt"),
    ("GET", "/openapi-org.json", "get_openapi_org"),
    ("GET", "/analysis/context/rfq/{rfq_id}/positions/{position_id}/ocr-preview", "rfq_position_ocr_preview"),
    ("POST", "/analysis/context/rfq/{rfq_id}/positions/{position_id}/ocr-merge", "rfq_position_ocr_merge"),
    ("POST", "/analysis/context/rfq/{rfq_id}/positions/{position_id}/technical-review-preview", "rfq_position_technical_review_preview"),
    ("POST", "/analysis/context/rfq/{rfq_id}/positions/{position_id}/technical-review-merge", "rfq_position_technical_review_merge"),
    ("GET", "/analysis/context/rfq/test-pulley-knowledge", "test_pulley_knowledge"),
}

_PROBE = r'''
import inspect, json, re, socket, traceback, warnings
from collections import Counter, defaultdict
from contextlib import contextmanager
from unittest.mock import patch
from minio import Minio
import psycopg2
import pytest
from fastapi import FastAPI, Query
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient
from sqlalchemy.engine import Engine
from sqlalchemy.sql.schema import MetaData
from starlette.routing import Match

ddl_calls, qdrant_checks = [], []
network_attempts, database_attempts = [], []
minio_bucket_checks, minio_make_bucket_attempts = [], []
def _record_and_raise(attempts, detail):
    attempts.append(detail)
    raise AssertionError(detail)
def no_ddl(self, bind=None, *args, **kwargs):
    ddl_calls.append({"bind_type": type(bind).__name__})
def deny_network(*args, **kwargs):
    _record_and_raise(network_attempts, " > ".join(frame.name for frame in traceback.extract_stack(limit=20)))
def deny_database(*args, **kwargs):
    _record_and_raise(database_attempts, "database-connect")
def no_qdrant_init(self, *args, **kwargs):
    qdrant_checks.append("constructor-compatibility-thread")
def synthetic_bucket_exists(self, bucket_name, *args, **kwargs):
    minio_bucket_checks.append(bucket_name)
    return True
def deny_make_bucket(self, *args, **kwargs):
    _record_and_raise(minio_make_bucket_attempts, "make-bucket")
class RouteUniquenessResult:
    def __init__(self):
        self.total = self.passed = self.failed = self.skipped = 0
    def pytest_runtest_logreport(self, report):
        if report.when != "call":
            return
        self.total += 1
        if report.passed:
            self.passed += 1
        elif report.skipped:
            self.skipped += 1
        else:
            self.failed += 1

with (
    patch.object(MetaData, "create_all", no_ddl),
    patch.object(socket.socket, "connect", deny_network),
    patch.object(socket, "create_connection", deny_network),
    patch.object(psycopg2, "connect", deny_database),
    patch.object(Engine, "connect", deny_database),
    patch.object(QdrantClient, "__init__", no_qdrant_init),
    patch.object(Minio, "bucket_exists", synthetic_bucket_exists),
    patch.object(Minio, "make_bucket", deny_make_bucket),
):
    from app.main import app
    wrappers, api_routes = len(app.routes), []
    for top in app.routes:
        source = getattr(top, "original_router", None)
        api_routes.extend(route for route in (source.routes if source else [top]) if isinstance(route, APIRoute))
    registrations, schema_registrations, excluded = defaultdict(list), defaultdict(list), []
    for route in api_routes:
        for method in sorted(route.methods or ()):
            registrations[(method, route.path)].append(route)
            # path is a live registration key; path_format is an OpenAPI key.
            schema_registrations[(method, route.path_format)].append(route)
            if not route.include_in_schema:
                excluded.append((method, route.path, route.name))
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        schema = app.openapi()
    route_uniqueness = RouteUniquenessResult()
    route_uniqueness_exit_code = int(pytest.main(
        ["-q", "tests/test_route_uniqueness.py"], plugins=[route_uniqueness]
    ))
    assert route_uniqueness_exit_code == 0, route_uniqueness_exit_code
    assert route_uniqueness.total == route_uniqueness.passed == 5
    assert route_uniqueness.failed == route_uniqueness.skipped == 0

operations = {
    (method.upper(), path): operation
    for path, item in schema["paths"].items() for method, operation in item.items()
    if method.lower() in {"get", "post", "put", "patch", "delete", "options", "head", "trace"}
}
for key, routes in schema_registrations.items():
    visible = [route for route in routes if route.include_in_schema]
    if not visible:
        assert key not in operations, key
    else:
        assert operations[key]["operationId"] == visible[-1].unique_id, key
schema_ids = [operation["operationId"] for operation in operations.values()]
assert len(schema_ids) == len(set(schema_ids)), schema_ids
duplicates = {key: routes for key, routes in registrations.items() if len(routes) > 1}
id_groups = defaultdict(list)
for key, routes in registrations.items():
    for route in routes:
        if route.include_in_schema:
            id_groups[route.unique_id].append(key)
id_collisions = {identifier: keys for identifier, keys in id_groups.items() if len(keys) > 1}
warning_ids = [
    message.split("Duplicate Operation ID ", 1)[1].split(" for function ", 1)[0]
    for message in (str(item.message) for item in captured)
    if message.startswith("Duplicate Operation ID ")
]

expected_assistants = {
    "/product/assistant/ask": ("app.routers.hybrid_api", "product_assistant_ask"),
    "/analysis/assistant/ask": ("app.routers.analysis_api_v10", "analysis_assistant_ask"),
    "/technical/assistant/ask": ("app.routers.hybrid_api", "technical_assistant_ask"),
    "/rfq/assistant/ask": ("app.routers.hybrid_api", "rfq_assistant_ask"),
    "/org/assistant/ask": ("app.routers.hybrid_api", "org_assistant_ask"),
    "/diagnostics/assistant/ask": ("app.routers.hybrid_api", "diagnostics_assistant_ask"),
}
for path, expected in expected_assistants.items():
    routes = registrations[("POST", path)]
    assert len(routes) == 1
    assert (routes[0].endpoint.__module__, routes[0].endpoint.__name__) == expected

rfq_expectations = {
    ("DELETE", "/analysis/rfq/{rfq_id}/positions/{position_id}"): 3,
    ("GET", "/analysis/rfq/{rfq_id}/positions/{position_id}/datasheet/pdf"): 2,
}
for key, count in rfq_expectations.items():
    routes = registrations[key]
    assert len(routes) == count
    assert all(route.endpoint.__module__ == "app.routers.rfq_api" for route in routes)
    lines = [inspect.getsourcelines(route.endpoint)[1] for route in routes]
    assert lines == sorted(lines)
    scope = {"type": "http", "method": key[0], "path": re.sub(r"\{[^}]+\}", "route-check", key[1]), "root_path": "", "scheme": "http", "headers": []}
    matched = [route for route in routes if route.matches(scope)[0] is Match.FULL]
    assert matched and matched[0] is routes[0]

# The real DELETE duplicates differ: only the first has deleted_by. Last wins.
delete_key = ("DELETE", "/analysis/rfq/{rfq_id}/positions/{position_id}")
delete_routes = schema_registrations[delete_key]
schema_parameters = [item["name"] for item in operations[delete_key].get("parameters", [])]
last_parameters = [item.name for item in (*delete_routes[-1].dependant.path_params, *delete_routes[-1].dependant.query_params)]
first_parameters = [item.name for item in (*delete_routes[0].dependant.path_params, *delete_routes[0].dependant.query_params)]
assert schema_parameters == last_parameters
try:
    assert schema_parameters == first_parameters
except AssertionError:
    first_delete_metadata_rejected = True
else:
    raise AssertionError("first DELETE metadata unexpectedly matched schema")

# Exercise the real first registered RFQ endpoint in-process.  This remains
# inside the Docker-attested process: TestClient uses ASGI transport, not a
# listening socket, and the domain helpers are replaced before every request.
rfq_module = __import__("app.routers.rfq_api", fromlist=["delete_rfq_position"])
first_delete_route, last_delete_route = delete_routes[0], delete_routes[-1]
assert first_delete_route.endpoint is not rfq_module.delete_rfq_position
assert last_delete_route.endpoint is rfq_module.delete_rfq_position
assert first_delete_route.endpoint.__module__ == rfq_module.__name__

rfq_path = "/analysis/rfq/rfq-synthetic/positions/position-synthetic"
rfq_position = {
    "position_id": "position-synthetic",
    "pos_nr": 17,
    "product_type": "synthetic-product",
}

def compact_sql(statement):
    return " ".join(statement.split()).upper()

LOOKUP_SQL = "SELECT * FROM RFQ.POSITION WHERE RFQ_ID = :RFQ_ID AND POSITION_ID = :POSITION_ID"
DELETE_SQL = "DELETE FROM RFQ.POSITION WHERE RFQ_ID = :RFQ_ID AND POSITION_ID = :POSITION_ID RETURNING POSITION_ID"
AUDIT_SQL = (
    "INSERT INTO RFQ.DECISION_LOG ( RFQ_ID, STEP, USER_OVERRIDE, APPROVED_BY, APPROVED_AT ) "
    "VALUES ( :RFQ_ID, 'POSITION_DELETED', CAST(:USER_OVERRIDE AS JSONB), :APPROVED_BY, NOW() ) "
    "RETURNING DECISION_ID"
)
EXPECTED_POSITION_PARAMS = {"rfq_id": "rfq-synthetic", "position_id": "position-synthetic"}

def sql_kind(statement, parameters):
    normalized = compact_sql(statement)
    values = dict(parameters)
    if normalized == LOOKUP_SQL and values == EXPECTED_POSITION_PARAMS:
        return "lookup"
    if normalized == DELETE_SQL and values == EXPECTED_POSITION_PARAMS:
        return "delete"
    if normalized == AUDIT_SQL and set(values) == {"rfq_id", "user_override", "approved_by"}:
        return "audit"
    return None

# Keep these mutations in memory: each must be rejected by the same fail-closed
# predicate used by the database doubles below.
assert sql_kind(LOOKUP_SQL.replace("RFQ.POSITION", "RFQ.REQUEST"), EXPECTED_POSITION_PARAMS) is None
assert sql_kind(LOOKUP_SQL.replace("RFQ_ID = :RFQ_ID AND ", ""), EXPECTED_POSITION_PARAMS) is None
assert sql_kind(DELETE_SQL.replace(" AND POSITION_ID = :POSITION_ID", ""), EXPECTED_POSITION_PARAMS) is None
assert sql_kind(AUDIT_SQL.replace("POSITION_DELETED", "POSITION_CREATED"), {
    "rfq_id": "rfq-synthetic", "user_override": "{}", "approved_by": "synthetic",
}) is None

@contextmanager
def rfq_request_guards():
    with (
        patch.object(socket.socket, "connect", deny_network),
        patch.object(socket, "create_connection", deny_network),
        patch.object(psycopg2, "connect", deny_database),
        patch.object(Engine, "connect", deny_database),
        patch.object(Minio, "make_bucket", deny_make_bucket),
    ):
        yield

def exercise_rfq_delete(*, deleted_by=None, missing=False, failing_helper=None):
    calls = []
    unexpected_sql = []
    def fail_closed(statement, parameters):
        kind = sql_kind(statement, parameters)
        if kind is None:
            unexpected_sql.append({"statement": compact_sql(statement), "parameters": dict(parameters)})
            raise AssertionError("unexpected RFQ DELETE SQL")
        return kind
    def lookup(statement, parameters):
        assert fail_closed(statement, parameters) == "lookup"
        calls.append(("lookup", statement, dict(parameters)))
        if failing_helper == "lookup":
            raise RuntimeError("synthetic lookup failure")
        return None if missing else dict(rfq_position)
    def write(statement, parameters):
        call = fail_closed(statement, parameters)
        assert call in {"delete", "audit"}
        calls.append((call, statement, dict(parameters)))
        if failing_helper == call:
            raise RuntimeError(f"synthetic {call} failure")
        # Current behavior deliberately ignores this DELETE RETURNING result.
        return None if call == "delete" else {"decision_id": "synthetic-decision"}
    def workflow(rfq_id):
        calls.append(("workflow", rfq_id))
        if failing_helper == "workflow":
            raise RuntimeError("synthetic workflow failure")
    request_kwargs = {} if deleted_by is None else {"params": {"deleted_by": deleted_by}}
    with (
        patch.object(rfq_module, "fetch_one", lookup),
        patch.object(rfq_module, "execute_one", write),
        patch.object(rfq_module, "update_rfq_workflow_status", workflow),
        rfq_request_guards(),
    ):
        client = TestClient(app, raise_server_exceptions=False)
        try:
            response = client.delete(rfq_path, **request_kwargs)
        finally:
            client.close()
    assert not unexpected_sql, unexpected_sql
    return response, calls

success_actors = []
for actor in (None, "explicit-actor", ""):
    response, calls = exercise_rfq_delete(deleted_by=actor)
    expected_actor = "DEV_TEST" if actor is None else actor
    assert response.status_code == 200, response.text
    assert response.json() == {
        "status": "ok",
        "rfq_id": "rfq-synthetic",
        "deleted_position_id": "position-synthetic",
        "write_actions_available": True,
    }
    assert [call[0] for call in calls] == ["lookup", "delete", "audit", "workflow"]
    lookup, deletion, audit, workflow = calls
    assert lookup[2] == {"rfq_id": "rfq-synthetic", "position_id": "position-synthetic"}
    assert deletion[2] == lookup[2]
    assert compact_sql(lookup[1]) == LOOKUP_SQL
    assert compact_sql(deletion[1]) == DELETE_SQL
    assert compact_sql(audit[1]) == AUDIT_SQL
    assert audit[2]["rfq_id"] == "rfq-synthetic"
    assert audit[2]["approved_by"] == expected_actor
    assert json.loads(audit[2]["user_override"]) == {
        "position_id": "position-synthetic",
        "pos_nr": 17,
        "product_type": "synthetic-product",
        "reason": "Testfase positie verwijderd",
    }
    assert workflow == ("workflow", "rfq-synthetic")
    success_actors.append(expected_actor)

response, calls = exercise_rfq_delete(missing=True)
assert response.status_code == 404
assert response.json() == {"detail": "RFQ position not found"}
assert [call[0] for call in calls] == ["lookup"]

failure_sequences = {}
for helper, expected_calls in (
    ("lookup", ["lookup"]),
    ("delete", ["lookup", "delete"]),
    ("audit", ["lookup", "delete", "audit"]),
    ("workflow", ["lookup", "delete", "audit", "workflow"]),
):
    response, calls = exercise_rfq_delete(failing_helper=helper)
    assert response.status_code == 500, response.text
    assert response.text == "Internal Server Error"
    assert [call[0] for call in calls] == expected_calls
    failure_sequences[helper] = expected_calls

invalid_path_calls = []
def unexpected_domain_call(*args, **kwargs):
    invalid_path_calls.append((args, kwargs))
    raise AssertionError("invalid path invoked RFQ domain helper")
with (
    patch.object(rfq_module, "fetch_one", unexpected_domain_call),
    patch.object(rfq_module, "execute_one", unexpected_domain_call),
    patch.object(rfq_module, "update_rfq_workflow_status", unexpected_domain_call),
    rfq_request_guards(),
):
    client = TestClient(app, raise_server_exceptions=False)
    try:
        missing_path_response = client.delete(
            "/analysis/rfq/rfq-synthetic/positions/position-synthetic/unexpected"
        )
    finally:
        client.close()
assert missing_path_response.status_code == 404
assert invalid_path_calls == []
rfq_delete_contract = {
    "first_handler_differs_from_module_symbol": first_delete_route.endpoint is not rfq_module.delete_rfq_position,
    "openapi_metadata_uses_last_handler": schema_parameters == last_parameters,
    "first_handler_metadata_rejected_by_openapi": first_delete_metadata_rejected,
    "success_actors": success_actors,
    "missing_position_status": 404,
    "failure_sequences": failure_sequences,
    "delete_return_ignored": True,
}

# Independent, in-memory marker proof after untouched real schema baseline.
app.openapi_schema = None
marker_app = FastAPI()
def marker_first(marker: str = Query(default="first")):
    return {"marker": marker}
def marker_last(marker: str, final_marker: int = Query(default=7)):
    return {"marker": marker, "final_marker": final_marker}
marker_app.add_api_route("/last-metadata-wins", marker_first, methods=["GET"], summary="FIRST", operation_id="marker_first")
marker_app.add_api_route("/last-metadata-wins", marker_last, methods=["GET"], summary="LAST", operation_id="marker_last")
marker_routes = [route for route in marker_app.routes if isinstance(route, APIRoute) and route.path == "/last-metadata-wins"]
marker_operation = marker_app.openapi()["paths"]["/last-metadata-wins"]["get"]
def assert_marker_metadata(route):
    assert marker_operation["operationId"] == route.unique_id
    assert marker_operation["summary"] == route.summary
    assert [item["name"] for item in marker_operation["parameters"]] == [
        item.name for item in (*route.dependant.path_params, *route.dependant.query_params)
    ]
assert_marker_metadata(marker_routes[-1])
try:
    assert_marker_metadata(marker_routes[0])
except AssertionError:
    marker_first_metadata_rejected = True
else:
    raise AssertionError("marker probe did not reject first metadata")

d14c = "/planner/mobile-download/inspection-plans/{plan_id}/second-monteur"
assert not any(path == d14c for _, path in registrations)
# These are deliberate, post-baseline guard probes.  They exercise the active
# patches and are kept separate from the import/route-check attempt lists.
unexpected_network_attempts = list(network_attempts)
unexpected_database_attempts = list(database_attempts)
unexpected_make_bucket_attempts = list(minio_make_bucket_attempts)
assert not unexpected_network_attempts
assert not unexpected_database_attempts
assert not unexpected_make_bucket_attempts
probe_starts = {
    "network": len(network_attempts), "database": len(database_attempts),
    "make_bucket": len(minio_make_bucket_attempts),
}
with (
    patch.object(MetaData, "create_all", no_ddl),
    patch.object(socket.socket, "connect", deny_network),
    patch.object(socket, "create_connection", deny_network),
    patch.object(psycopg2, "connect", deny_database),
    patch.object(Engine, "connect", deny_database),
    patch.object(QdrantClient, "__init__", no_qdrant_init),
    patch.object(Minio, "bucket_exists", synthetic_bucket_exists),
    patch.object(Minio, "make_bucket", deny_make_bucket),
):
    for boundary, operation in (
        ("socket.connect", lambda: socket.socket().connect(("127.0.0.1", 1))),
        ("socket.create_connection", lambda: socket.create_connection(("127.0.0.1", 1))),
        ("psycopg2.connect", lambda: psycopg2.connect("dbname=synthetic")),
        ("Engine.connect", lambda: __import__("sqlalchemy").create_engine("sqlite://").connect()),
        ("Minio.make_bucket", lambda: Minio("127.0.0.1:1").make_bucket("synthetic-probe")),
    ):
        try:
            operation()
        except AssertionError:
            pass
        else:
            raise AssertionError(f"guard probe unexpectedly allowed {boundary}")
guard_probe_attempts = {
    "network": network_attempts[probe_starts["network"]:],
    "database": database_attempts[probe_starts["database"]:],
    "make_bucket": minio_make_bucket_attempts[probe_starts["make_bucket"]:],
}
assert len(guard_probe_attempts["network"]) == 2
assert guard_probe_attempts["database"] == ["database-connect", "database-connect"]
assert guard_probe_attempts["make_bucket"] == ["make-bucket"]
print("MAIN_OPENAPI_PROBE=" + json.dumps({
    "top_level_route_wrappers": wrappers,
    "api_route_registrations": sum(map(len, registrations.values())),
    "unique_method_paths": len(registrations),
    "schema_paths": len(schema["paths"]), "schema_operations": len(operations),
    "schema_excluded_method_paths": sorted(excluded),
    "duplicate_method_path_counts": {f"{method} {path}": len(routes) for (method, path), routes in duplicates.items()},
    "operation_id_collision_counts": {identifier: len(keys) for identifier, keys in id_collisions.items()},
    "warning_operation_id_counts": dict(Counter(warning_ids)),
    "schema_operation_ids_unique": len(schema_ids) == len(set(schema_ids)),
    "ddl_calls_blocked": ddl_calls, "qdrant_compatibility_checks_blocked": qdrant_checks,
    "network_attempts": unexpected_network_attempts, "database_attempts": unexpected_database_attempts,
    "minio_bucket_checks": minio_bucket_checks,
    "minio_make_bucket_attempts": unexpected_make_bucket_attempts,
    "route_uniqueness": {
        "total": route_uniqueness.total, "passed": route_uniqueness.passed,
        "failed": route_uniqueness.failed, "skipped": route_uniqueness.skipped,
        "exit_code": route_uniqueness_exit_code,
    },
    "guard_probe_counts": {key: len(value) for key, value in guard_probe_attempts.items()},
    "first_delete_metadata_rejected": first_delete_metadata_rejected,
    "rfq_delete_contract": rfq_delete_contract,
    "marker_first_metadata_rejected": marker_first_metadata_rejected,
}, sort_keys=True))
'''


def _assert_container_runtime() -> None:
    """Defence in depth for the runner's Docker-inspection attestation."""
    if os.environ.get("PROMATI_OPENAPI_ISOLATED_HARNESS") != _HARNESS_MARKER:
        raise unittest.SkipTest("requires isolated runner; app is not imported on host")
    if os.name != "posix" or set(os.listdir("/sys/class/net")) != {"lo"}:
        raise AssertionError("Docker network-none isolation required")
    root = next(
        (line.split() for line in Path("/proc/self/mountinfo").read_text().splitlines() if line.split()[4] == "/"),
        None,
    )
    if root is None or "ro" not in root[5].split(","):
        raise AssertionError("Docker read-only root required")
    if any(path.exists() for path in (Path(".env"), Path("../.env"))):
        raise AssertionError("test image must not contain an environment file")


def _synthetic_probe_environment() -> dict[str, str]:
    """Return the complete non-secret environment; do not inherit host values."""
    return {
        "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1",
        "PUBLIC_API_URL": "http://public.invalid", "PUBLIC_WEB_URL": "http://web.invalid",
        "PROMATI_API_BASE_URL": "http://api.invalid", "CORS_ALLOWED_ORIGINS": "",
        "DATABASE_URL": "postgresql+psycopg2://synthetic:synthetic@127.0.0.1:1/synthetic",
        "MINIO_ENDPOINT": "127.0.0.1:1", "MINIO_ACCESS_KEY": "synthetic",
        "MINIO_SECRET_KEY": "synthetic", "MINIO_BUCKET": "synthetic-files",
        "MINIO_BUCKET_RFQ": "synthetic-rfq-artifacts", "QDRANT_URL": "http://127.0.0.1:1",
        "QDRANT_API_KEY": "", "EDOCR2_URL": "http://127.0.0.1:1",
        "TECHREVIEW_URL": "http://127.0.0.1:1",
        "KEYCLOAK_ISSUER": "http://issuer.invalid/realms/synthetic",
        "KEYCLOAK_JWKS_URL": "http://127.0.0.1:1/jwks",
        "ORG_ADMIN_USER": "synthetic", "ORG_ADMIN_PASSWORD": "synthetic",
        "RFQ_PDF_DIR": "/tmp/rfq-pdf", "RFQ_UPLOAD_DIR": "/tmp/rfq-upload",
        "OPENAI_API_KEY": "",
    }


class MainOpenApiRegistrationIsolatedTests(unittest.TestCase):
    def test_host_entrypoint_skips_before_app_import(self) -> None:
        """A fresh host probe skips without importing or replacing app.main."""
        module_path = Path(__file__).resolve()
        host_probe = r'''
import importlib.util, json, os, sys, types
module_path = sys.argv[1]
sentinel = types.ModuleType("app.main")
sentinel.provenance = "preloaded-host-sentinel"
sys.modules["app.main"] = sentinel
spec = importlib.util.spec_from_file_location("isolated_openapi_host_probe", module_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
try:
    module._assert_container_runtime()
except module.unittest.SkipTest:
    skipped = True
else:
    skipped = False
print(json.dumps({
    "skipped": skipped,
    "sentinel_preserved": sys.modules.get("app.main") is sentinel,
    "sentinel_provenance": getattr(sys.modules.get("app.main"), "provenance", None),
}))
'''
        completed = subprocess.run(
            [sys.executable, "-c", host_probe, str(module_path)], check=False,
            capture_output=True, text=True, env={**os.environ, "PROMATI_OPENAPI_ISOLATED_HARNESS": ""}, timeout=20,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result, {
            "skipped": True, "sentinel_preserved": True,
            "sentinel_provenance": "preloaded-host-sentinel",
        })

    def test_real_main_import_and_openapi_registration(self) -> None:
        _assert_container_runtime()
        completed = subprocess.run(
            [sys.executable, "-c", _PROBE], check=False, capture_output=True, text=True,
            env=_synthetic_probe_environment(), cwd=Path.cwd(), timeout=60,
        )
        self.assertEqual(
            completed.returncode,
            0,
            "isolated OpenAPI probe failed\nstdout:\n"
            + completed.stdout
            + "\nstderr:\n"
            + completed.stderr,
        )
        marker = next((line for line in completed.stdout.splitlines() if line.startswith("MAIN_OPENAPI_PROBE=")), None)
        self.assertIsNotNone(marker, "isolated OpenAPI probe did not emit a summary")
        summary = json.loads(marker.removeprefix("MAIN_OPENAPI_PROBE="))
        self.assertEqual(summary["api_route_registrations"], 282)
        self.assertEqual(summary["unique_method_paths"], 279)
        self.assertEqual(summary["schema_paths"], 264)
        self.assertEqual(summary["schema_operations"], 272)
        self.assertEqual({tuple(item) for item in summary["schema_excluded_method_paths"]}, _EXCLUDED)
        self.assertEqual(summary["duplicate_method_path_counts"], {
            "DELETE /analysis/rfq/{rfq_id}/positions/{position_id}": 3,
            "GET /analysis/rfq/{rfq_id}/positions/{position_id}/datasheet/pdf": 2,
        })
        self.assertEqual(summary["operation_id_collision_counts"], {
            "delete_rfq_position_analysis_rfq__rfq_id__positions__position_id__delete": 3,
            "get_rfq_position_datasheet_pdf_analysis_rfq__rfq_id__positions__position_id__datasheet_pdf_get": 2,
        })
        self.assertEqual(summary["warning_operation_id_counts"], {
            "delete_rfq_position_analysis_rfq__rfq_id__positions__position_id__delete": 2,
            "get_rfq_position_datasheet_pdf_analysis_rfq__rfq_id__positions__position_id__datasheet_pdf_get": 1,
        })
        self.assertTrue(summary["schema_operation_ids_unique"])
        self.assertEqual(summary["ddl_calls_blocked"], [{"bind_type": "Engine"}])
        self.assertEqual(summary["qdrant_compatibility_checks_blocked"], ["constructor-compatibility-thread"])
        self.assertEqual(summary["network_attempts"], [])
        self.assertEqual(summary["database_attempts"], [])
        self.assertEqual(summary["minio_bucket_checks"], ["synthetic-files"])
        self.assertEqual(summary["minio_make_bucket_attempts"], [])
        self.assertEqual(summary["route_uniqueness"], {
            "total": 5, "passed": 5, "failed": 0, "skipped": 0, "exit_code": 0,
        })
        self.assertEqual(summary["guard_probe_counts"], {
            "network": 2, "database": 2, "make_bucket": 1,
        })
        self.assertTrue(summary["first_delete_metadata_rejected"])
        self.assertEqual(summary["rfq_delete_contract"], {
            "first_handler_differs_from_module_symbol": True,
            "openapi_metadata_uses_last_handler": True,
            "first_handler_metadata_rejected_by_openapi": True,
            "success_actors": ["DEV_TEST", "explicit-actor", ""],
            "missing_position_status": 404,
            "failure_sequences": {
                "lookup": ["lookup"],
                "delete": ["lookup", "delete"],
                "audit": ["lookup", "delete", "audit"],
                "workflow": ["lookup", "delete", "audit", "workflow"],
            },
            "delete_return_ignored": True,
        })
        self.assertTrue(summary["marker_first_metadata_rejected"])
        print(json.dumps(summary, sort_keys=True))

    def test_runner_propagates_nonzero_probe_exit(self) -> None:
        """A failed container probe preserves its inspected nonzero exit code."""
        runner_path = Path(__file__).parents[1] / "scripts" / "run_main_openapi_registration_isolated.py"
        if not runner_path.is_file():
            self.skipTest("runner source is intentionally excluded from the minimal test image")
        spec = importlib.util.spec_from_file_location("isolated_openapi_runner", runner_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        inspection = {
            "HostConfig": {
                "NetworkMode": "none", "ReadonlyRootfs": True, "Binds": None,
                "Tmpfs": {"/tmp": "rw"}, "Privileged": False,
                "SecurityOpt": ["no-new-privileges"], "CapDrop": ["ALL"], "CapAdd": None,
            },
            "Config": {"Env": [f"PROMATI_OPENAPI_ISOLATED_HARNESS={_HARNESS_MARKER}"]},
            "Mounts": [], "State": {"ExitCode": 23},
        }

        def fake_run(command: list[str], capture: bool = False) -> subprocess.CompletedProcess[str]:
            action = command[1]
            if action == "inspect":
                return subprocess.CompletedProcess(command, 0, stdout=json.dumps([inspection]))
            if action == "start":
                return subprocess.CompletedProcess(command, 23)
            if action in {"create", "rm"}:
                return subprocess.CompletedProcess(command, 0)
            self.fail(f"unexpected Docker action: {action}")

        with patch.object(runner, "_run", side_effect=fake_run), patch.object(
            sys, "argv", ["runner", "--docker", "docker", "--image", "image"]
        ):
            self.assertEqual(runner.main(), 23)
