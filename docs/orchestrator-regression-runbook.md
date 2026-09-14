# PROMATI orchestrator regression baseline

This runbook is the repeatable gate for changes to the orchestrator. The deterministic layer uses synthetic configuration, blocks network calls, and does not require a live database. The runtime layer is read-only and reports contract failures separately from live-data observations.

## Canonical commands

Run from the repository root. Python 3.11 or newer and Docker are required; nothing is installed globally.

```powershell
python api/scripts/run_orchestrator_regression.py --label pre-change
python api/scripts/run_orchestrator_runtime_smokes.py --output artifacts/orchestrator-baseline/runtime-smoke.json
```

The regression runner builds `api/Dockerfile.test`, runs every test below `api/tests` except `tests/integration`, and writes a privacy-safe JSON report below `artifacts/orchestrator-baseline`. Reports contain commands, commit, counts and failure test names only—never questions, answers, tokens, entities, scopes or payloads.

## Result categories

- `code regression`: a previously passing deterministic test now fails.
- `environment`: Docker/build/API/health/timeout failure prevents a valid result.
- `live-data dependency`: the HTTP contract is intact, but a domain or data expectation is not visible; the smoke runner emits a warning, not a false green data assertion.
- `known baseline gap`: intentionally characterized current behavior with a machine-readable desired future contract. The GSL/3-mm case is registered this way.

Never weaken an assertion to hide a red result. Update a characterization only after reviewing and approving an intentional production behavior change.

Because this repository already contains explicit red baseline contracts, use failure-set comparison as the refactor gate:

```powershell
python api/scripts/run_orchestrator_regression.py --label candidate --compare-to artifacts/orchestrator-baseline/post-change-57fe45e.json
```

This exits zero when no new failure name appears, while still reporting unchanged and resolved baseline failures. Without `--compare-to`, pytest's raw nonzero status is preserved.

## Rebuild and verification cycle

Inspect first because Compose may point at another checkout and requires its existing `.env`.

```powershell
docker compose ps
docker inspect ai-platform-api-1 --format '{{.Image}}'
python api/scripts/run_orchestrator_regression.py --label pre-change
docker compose build api
docker compose up -d --no-deps --force-recreate api
```

Wait by polling health rather than sleeping blindly:

```powershell
1..30 | ForEach-Object {
  try { if ((Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/healthz -TimeoutSec 2).StatusCode -eq 200) { break } } catch {}
  Start-Sleep -Seconds 1
}
docker inspect ai-platform-api-1 --format '{{.Id}} {{.Image}} {{.Created}}'
python api/scripts/run_orchestrator_runtime_smokes.py --base-url http://127.0.0.1:8000 --timeout 30
python api/scripts/run_orchestrator_regression.py --label post-rebuild
```

If the saved Compose project lives in another checkout, run the rebuild from that checkout only after confirming that it contains the intended commit. Do not copy secrets into a test container. If Docker or required configuration is unavailable, record `not executed` and the reason; never simulate a pass.

## Coverage and interpretation

The suite locks query classification, negation, dimensions and band scope, planning/execution registration, legacy and typed outcomes, zero rows versus transport errors, evidence requirements, CP9–CP15 non-widening authority, public response bounds and forbidden markers, privacy, trace IDs, existing synthetic goldens, and the final public `run_orchestrator` facade.

The GSL query currently becomes a clarification for an unresolved false `DE3` band candidate and executes no action. `api/tests/fixtures/gsl_3mm_known_gap.json` separately records the desired future `analysis_maintenance_positions` route to `GET /analysis/maintenance/positions` with public `resultaat` detail rows. This task does not implement that production change.

Before using the suite as a refactor gate, compare the pre/post JSON reports. The acceptable delta is no new failures, with known gaps unchanged or intentionally closed. Existing explicit P4.14c red tests remain baseline failures and must not be mistaken for infrastructure failures.

## Pre-refactor stage-split gate

Before mechanically extracting any stage from `service.py`, run the Task 2B characterization modules for the facade wrapper chain, post-CP12 answer mutations, evidence-adapter wrapper chain, meta/maintenance routing and the existing maintenance endpoint. Future-only capability and projection contracts must remain machine-readable known gaps or strict xfails whose import occurs inside the test function. Treat any XPASS as a review-required contract change.

Then run the canonical failure-set comparison both before and after the candidate change. The gate is green only when `comparison.new_failures` is empty, no XPASS is unexplained, and `git diff -- api/app` is empty for a tests-only characterization change.

For the 3D2 initial-execution extraction, additionally run
`tests/orchestrator/test_initial_execution_boundary_characterization.py` both
before and after the edit and run
`tests/orchestrator/test_initial_execution_stage.py` afterward. The latter
locks the nine-field return contract, dependency order, object identity,
ordered observer collection, independent fail-open zones, authoritative
propagation, minimal imports, single core call site and the unchanged
CP4F -> CP4B -> CP3C -> core bindings.

For the 3E initial execution-observability extraction, also run
`tests/orchestrator/test_observability_stage_extraction.py`. It locks the
mapping/object attempts contract, integer-only result-count projection,
privacy, unchanged `len(results)` failure behavior, exact three-key mutation,
the single call after all 3D2 bindings and before evidence initialization, and
the leaf import surface.

For the 3F2 Phase-C-entry extraction, run
`tests/orchestrator/test_phase_c_entry_boundary_characterization.py` before
and after the edit and run `tests/orchestrator/test_phase_c_entry_stage.py`
afterward. These lock the exact lookup/gate/timestamp/normalization boundary,
exception propagation into the existing service fail-open `try`, tuple
identity, runtime dependency binding, retained coverage ownership and leaf
import surface.

For the 3G2 product-family coverage/recovery extraction, run
`tests/orchestrator/test_product_family_recovery_boundary_characterization.py`
and `tests/orchestrator/test_product_family_recovery_stage.py`. Together they
lock the single runtime-resolved service call inside the existing Phase-C
fail-open boundary, the three-field frozen return contract, the 35 previously
characterized low-level cases, exact partial count mutations, exception
propagation and the leaf import surface.

For the 3H2 task-evidence shadow/P4.6C extraction, run
`tests/orchestrator/test_task_evidence_p4_6c_boundary_characterization.py`
unchanged before and after the edit. Also run
`tests/orchestrator/test_task_evidence_stage.py` and
`tests/orchestrator/test_task_evidence_stage_service_integration.py` after the
edit. Together these lock the exact two-field frozen return contract, fresh
shadow fallback, independent `Exception` zones, `BaseException` propagation,
tuple coercion inside the authority zone, object identity and order, runtime
service dependency binding, and the rule that research receives shadow only.

For the 3I2 research-decision shadow/P4.6D1 extraction, run
`tests/orchestrator/test_task_research_decision_p4_6d1_boundary_characterization.py`
unchanged before and after the edit. Also run
`tests/orchestrator/test_task_research_decision_stage.py` and
`tests/orchestrator/test_task_research_decision_stage_service_integration.py`
afterward. These lock the exact two-field frozen return contract, fresh shadow
fallback, independent `Exception` zones, `BaseException` propagation, object
identity and order, runtime service dependency binding, and the unchanged
research-context inputs.
