#!/usr/bin/env python3
"""Build and run the deterministic orchestrator suite and write a safe summary."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
API = ROOT / "api"
DEFAULT_SELECTION = ["tests", "--ignore=tests/integration"]
IMAGE = "promati-orchestrator-regression:local"


def run(command, **kwargs):
    print("+", " ".join(map(str, command)), flush=True)
    return subprocess.run(command, check=False, text=True, **kwargs)


def git_sha():
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True)
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def parse_junit(path: Path):
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    totals = {key: sum(int(s.get(key, "0")) for s in suites) for key in ("tests", "failures", "errors", "skipped")}
    failed = []
    for case in root.iter("testcase"):
        if case.find("failure") is not None or case.find("error") is not None:
            failed.append(f"{case.get('classname')}::{case.get('name')}")
    return {
        "passed": totals["tests"] - totals["failures"] - totals["errors"] - totals["skipped"],
        "failed": totals["failures"], "errors": totals["errors"], "skipped": totals["skipped"],
        "failure_names": sorted(failed),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="manual")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--compare-to", type=Path, help="Existing safe JSON baseline; fail only on new failures")
    parser.add_argument("--no-build", action="store_true")
    args, extra = parser.parse_known_args()
    if shutil.which("docker") is None:
        print("Docker is required; no result was simulated.", file=sys.stderr)
        return 2
    if not args.no_build:
        built = run(["docker", "build", "-f", str(API / "Dockerfile.test"), "-t", IMAGE, str(API)])
        if built.returncode:
            return built.returncode
    output = args.output or ROOT / "artifacts" / "orchestrator-baseline" / f"{args.label}-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="promati-regression-") as tmp:
        tmp_path = Path(tmp)
        junit = tmp_path / "junit.xml"
        selection = extra or DEFAULT_SELECTION
        command = ["docker", "run", "--name", f"promati-regression-{os.getpid()}", IMAGE, "-q", "--disable-warnings", f"--junitxml=/tmp/junit.xml", *selection]
        result = run(command)
        container = f"promati-regression-{os.getpid()}"
        copied = run(["docker", "cp", f"{container}:/tmp/junit.xml", str(junit)], capture_output=True)
        run(["docker", "rm", container], capture_output=True)
        summary = parse_junit(junit) if copied.returncode == 0 and junit.exists() else {"passed": 0, "failed": 0, "errors": 1, "skipped": 0, "failure_names": ["runner::junit_unavailable"]}
    comparison = None
    final_exit = result.returncode
    if args.compare_to:
        baseline = json.loads(args.compare_to.read_text(encoding="utf-8"))
        before = set(baseline.get("result", {}).get("failure_names", []))
        after = set(summary.get("failure_names", []))
        comparison = {
            "baseline": str(args.compare_to),
            "new_failures": sorted(after - before),
            "resolved_failures": sorted(before - after),
            "unchanged_failure_count": len(before & after),
        }
        final_exit = 1 if comparison["new_failures"] else 0
    report = {
        "schema_version": "promati.orchestrator.regression-run.v1",
        "label": args.label,
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "commit_sha": git_sha(),
        "command": "python api/scripts/run_orchestrator_regression.py " + " ".join(sys.argv[1:]),
        "selection": selection,
        "result": summary,
        "pytest_exit_code": result.returncode,
        "gate_exit_code": final_exit,
        "comparison": comparison,
        "privacy": "No questions, answers, tokens, entities, scopes or payloads are stored.",
    }
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["result"], indent=2))
    print(f"Safe report: {output}")
    return final_exit


if __name__ == "__main__":
    raise SystemExit(main())
