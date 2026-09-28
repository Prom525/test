"""Run the OpenAPI test only after Docker isolation attestation.

Build a unique api/Dockerfile.test image, then run this script from repository
root with --docker as the absolute docker executable path and --image as that
unique image. No volumes are created or used.
"""

from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
import uuid

_MARKER = "docker-inspect-v1"
_TESTS = ("tests/test_main_openapi_registration_isolated.py",)


def _run(command: list[str], capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=False, text=True, capture_output=capture)


def _attest(inspect: dict[str, object]) -> None:
    host, config, mounts = inspect["HostConfig"], inspect["Config"], inspect["Mounts"]
    failures = []
    if host.get("NetworkMode") != "none":
        failures.append("network mode")
    if host.get("ReadonlyRootfs") is not True:
        failures.append("read-only root")
    if mounts or host.get("Binds"):
        failures.append("mount or bind")
    if "/tmp" not in (host.get("Tmpfs") or {}):
        failures.append("/tmp tmpfs")
    if host.get("Privileged"):
        failures.append("privileged mode")
    if "no-new-privileges" not in (host.get("SecurityOpt") or []):
        failures.append("no-new-privileges")
    if set(host.get("CapDrop") or []) != {"ALL"}:
        failures.append("cap-drop ALL")
    if host.get("CapAdd"):
        failures.append("cap-add")
    if f"PROMATI_OPENAPI_ISOLATED_HARNESS={_MARKER}" not in (config.get("Env") or []):
        failures.append("harness marker")
    if failures:
        raise RuntimeError("Docker isolation attestation failed: " + ", ".join(failures))


def _assert_negative_attestation_controls(inspect: dict[str, object]) -> None:
    """Keep the attestation fail-closed for the isolation settings it promises."""
    for label, mutate in (
        ("network", lambda item: item["HostConfig"].__setitem__("NetworkMode", "bridge")),
        ("mount", lambda item: item.__setitem__("Mounts", [{"Type": "volume"}])),
        ("capability", lambda item: item["HostConfig"].__setitem__("CapAdd", ["NET_RAW"])),
    ):
        invalid = copy.deepcopy(inspect)
        mutate(invalid)
        try:
            _attest(invalid)
        except RuntimeError:
            continue
        raise RuntimeError(f"negative attestation control unexpectedly accepted {label}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--docker", required=True)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    name = f"promati-openapi-isolated-{uuid.uuid4().hex[:12]}"
    create = [
        args.docker, "create", "--name", name, "--network", "none", "--read-only",
        "--tmpfs", "/tmp:rw,nosuid,nodev,size=32m", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges", "--env", f"PROMATI_OPENAPI_ISOLATED_HARNESS={_MARKER}",
        args.image, "-q", "-s", "-p", "no:cacheprovider", *_TESTS,
    ]
    created = False
    try:
        if _run(create, capture=True).returncode:
            raise RuntimeError("Docker test container could not be created")
        created = True
        inspected = _run([args.docker, "inspect", name], capture=True)
        if inspected.returncode:
            raise RuntimeError("Docker test container could not be inspected")
        inspection = json.loads(inspected.stdout)[0]
        _attest(inspection)
        _assert_negative_attestation_controls(inspection)
        started = _run([args.docker, "start", "-a", name])
        if started.returncode:
            final_inspect = _run([args.docker, "inspect", name], capture=True)
            if final_inspect.returncode == 0:
                state_exit_code = json.loads(final_inspect.stdout)[0]["State"]["ExitCode"]
                if isinstance(state_exit_code, int) and state_exit_code != 0:
                    return state_exit_code
            return started.returncode
        return 0
    finally:
        if created:
            _run([args.docker, "rm", "-f", name])


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
