#!/usr/bin/env python3
"""Read-only HTTP smoke tests for a locally running PROMATI API."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


FORBIDDEN = ("evidence_ids_used", "included_evidence_ids", "excluded_evidence_ids", "task_coverage_gate_cp10", "task_presenter_cp11", "/analysis/", "/product/", "latest_position_measurement:", "latest_blade_height:", "traceback (most recent call last)", "select * from")
CASES = (
    ("mv1_latest_compact", "Wat is de laatste inspectiedatum voor MV1?", "compact", "inspection"),
    ("maintenance_compact", "Wat heeft prioriteit qua onderhoud op B12?", "compact", "inspection"),
    ("product_compact", "Geef productinformatie over BB-U.", "compact", "product"),
    ("product_technical", "Geef productinformatie over BB-U en leg ook uit wat CEMA betekent.", "compact", "product"),
    ("unknown_band", "Wat is de laatste inspectiestatus van band Z999999?", "compact", "inspection"),
    ("negation", "Geef productinformatie over Belle Banne U, geen inspectieanalyse.", "compact", "product"),
    ("gsl_3mm_characterization", "Geef voor GSL de schrapers die nu op of rond de 3 mm grens zitten.", "debug", None),
    ("cp9_cp15_debug", "Geef productinformatie over BB-U en leg ook uit wat CEMA betekent.", "debug", "product"),
)


def request_json(url, *, payload=None, timeout=30):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(url, data=body, method="GET" if body is None else "POST", headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=timeout) as response:
        raw = response.read()
        return response.status, raw, json.loads(raw.decode("utf-8"))


def domain_intents(data):
    plan = data.get("query_plan") if isinstance(data.get("query_plan"), dict) else {}
    domains = data.get("domains") if isinstance(data.get("domains"), list) else plan.get("domains", [])
    tasks = data.get("tasks") if isinstance(data.get("tasks"), list) else plan.get("intent_tasks", [])
    intents = [str(item.get("intent")) for item in tasks if isinstance(item, dict) and item.get("intent")]
    return domains, intents


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--max-compact-bytes", type=int, default=12000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    reports = []
    try:
        for name, path in (("healthz", "/healthz"), ("openapi", "/openapi.json")):
            status, raw, data = request_json(base + path, timeout=args.timeout)
            reasons = []
            if status != 200: reasons.append(f"http_{status}")
            if name == "healthz" and data.get("status") != "ok": reasons.append("health_contract")
            if name == "openapi":
                operation = ((data.get("paths") or {}).get("/orchestrator/ask") or {}).get("post", {}).get("operationId")
                if operation != "promati_orchestrator_ask": reasons.append("operation_id_missing")
            reports.append({"case": name, "http": status, "contract": "pass" if not reasons else "fail", "bytes": len(raw), "reasons": reasons})
        for name, question, profile, expected_domain in CASES:
            started = time.perf_counter()
            status, raw, data = request_json(base + "/orchestrator/ask", payload={"vraag": question, "response_profile": profile, "include_trace": profile == "debug"}, timeout=args.timeout)
            reasons, warnings = [], []
            answer = str(data.get("answer") or "")
            domains, intents = domain_intents(data)
            if status != 200: reasons.append(f"http_{status}")
            if not data.get("trace_id"): reasons.append("trace_id_missing")
            if profile == "compact":
                folded = answer.casefold()
                leaked = [marker for marker in FORBIDDEN if marker.casefold() in folded]
                if leaked: reasons.append("forbidden_public_markers:" + ",".join(leaked))
                if len(raw) > args.max_compact_bytes: reasons.append("compact_response_too_large")
                if "evidence_pipeline" in data: reasons.append("debug_pipeline_in_compact")
            else:
                pipeline = data.get("evidence_pipeline")
                if name == "cp9_cp15_debug" and not isinstance(pipeline, dict): reasons.append("debug_pipeline_missing")
                if name == "cp9_cp15_debug" and isinstance(pipeline, dict):
                    text = repr(pipeline).casefold()
                    for cp in ("cp9", "cp10", "cp11", "cp12", "cp13", "cp15"):
                        if cp not in text: reasons.append(cp + "_missing")
            if expected_domain and expected_domain not in domains: warnings.append("data_or_routing_observation:expected_domain_not_visible")
            if name == "gsl_3mm_characterization": warnings.append("known_gap:desired maintenance_positions capability is not implemented")
            reports.append({"case": name, "http": status, "contract": "pass" if not reasons else "fail", "trace_id_present": bool(data.get("trace_id")), "domains": domains[:8], "intents": intents[:12], "bytes": len(raw), "duration_ms": round((time.perf_counter()-started)*1000), "reasons": reasons, "data_dependent_warnings": warnings})
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "environment_failure", "reason": type(exc).__name__}, indent=2))
        return 2
    summary = {"base_url": base, "privacy": "Answers and request payloads are not logged.", "passed": sum(r["contract"] == "pass" for r in reports), "failed": sum(r["contract"] == "fail" for r in reports), "cases": reports}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
