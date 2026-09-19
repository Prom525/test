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

Voor de 3Y2 composition-shadow/public-canary-stage draait de pre-gate met 43
passes en precies één strict xfail (`awaiting_3y2_stage_extraction`). Na extractie
moeten alle 44 boundary-cases normaal slagen, zonder XPASS. Draai daarnaast de
leaf-stage- en service-integratietests en de aangrenzende composition-, P4.6F-,
CP9-, wrapper-, post-CP12-, Phase-C8- en evidence-adapterbundels.

Voor de 3Z2A P4.6F/CP9-authority-entry-extractie moet de bestaande 3Z1A-suite
vóór en na de wijziging exact 60 normale passes geven. Draai daarnaast
`test_p4_6f_cp9_authority_entry_stage.py` en
`test_p4_6f_cp9_authority_entry_stage_service_integration.py`. Deze borgen het
zesveldige frozen contract, de vijf runtime-resolved dependencies, de eenmalige
directe debugprofielbepaling, CP13-fallback, P4.6F fail-open, CP9-opslagvolgorde en de
servicegrens 3Y2 -> 3Z2A -> CP10.

Voor de 3Z2B CP10-authorityrollback-extractie moet de bestaande 3Z1B-suite
`test_cp10_authority_rollback_boundary_characterization.py` vóór en na de
wijziging exact 34 normale passes geven. Draai daarnaast
`test_cp10_authority_rollback_stage.py` en
`test_cp10_authority_rollback_stage_service_integration.py`. Deze borgen het
drieveldige frozen contract, de vijf positionele inputs, twee runtime-resolved
dependencies, exacte get/call/setitem-volgorde en de servicegrens
3Z2A -> 3Z2B -> CP11.

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

For the 3J2 research-context/call-guard shadow extraction, run
`tests/orchestrator/test_task_research_context_guard_boundary_characterization.py`
unchanged before and after the edit. Also run
`tests/orchestrator/test_task_research_context_stage.py` and
`tests/orchestrator/test_task_research_context_stage_service_integration.py`
afterward. These lock the frozen exact-two-field return contract, fresh and
separate list defaults, `list(results)` placement, object identity and order,
independent `Exception` zones, `BaseException` propagation, runtime service
dependency binding, the single stage callsite and the unchanged CP13 boundary.

For the 3K2 CP13 research-semantics extraction, run
`tests/orchestrator/test_cp13_research_semantics_boundary_characterization.py`
unchanged before and after the edit. Also run
`tests/orchestrator/test_cp13_research_semantics_stage.py` and
`tests/orchestrator/test_cp13_research_semantics_stage_service_integration.py`
afterward. These lock the frozen exact-one-field return contract, unchanged
success identity, fresh fail-closed fallback containers, `Exception`-only
handling, runtime service dependency binding, the single stage callsite and
the unchanged P4.6D2 boundary.

For the 3L2 P4.6D2 service-invocation extraction, run both unchanged 3L1 files:
`tests/orchestrator/test_p4_6d2_research_execution_boundary_characterization.py`
and `tests/orchestrator/test_p4_6d2_research_execution_characterization.py`.
Also run `tests/orchestrator/test_p4_6d2_research_execution_stage.py`,
`tests/orchestrator/test_p4_6d2_research_execution_stage_service_integration.py`
and `tests/test_cp14_task_research_authority_chain.py`. Together these lock the
frozen exact-two-field result, fresh observation and fallback lists, object
identity/order, `Exception`-only fail-open behavior, runtime service dependency
binding, the single stage callsite and the unchanged P4.6E1 boundary.

For the 3M2 P4.6E1 service-invocation extraction, run both unchanged 3M1 files:
`tests/orchestrator/test_p4_6e1_research_evidence_boundary_characterization.py`
and `tests/orchestrator/test_p4_6e1_research_evidence_characterization.py`.
Also run `tests/orchestrator/test_p4_6e1_research_evidence_stage.py`,
`tests/orchestrator/test_p4_6e1_research_evidence_stage_service_integration.py`
and `tests/test_cp14_task_research_authority_chain.py`. Together these lock the
frozen exact-two-field result, fresh unit and fallback lists, object
identity/order, `Exception`-only fail-open behavior, runtime service dependency
binding, the single stage callsite and the unchanged P4.6E2 boundary.

For the 3O2 P4.6E3 synthesis-coverage invocation extraction, run both
unchanged 3O1 files:
`tests/orchestrator/test_p4_6e3_synthesis_coverage_boundary_characterization.py`
and `tests/orchestrator/test_p4_6e3_synthesis_coverage_characterization.py`.
Also run `tests/orchestrator/test_p4_6e3_synthesis_coverage_stage.py`,
`tests/orchestrator/test_p4_6e3_synthesis_coverage_stage_service_integration.py`
and `tests/test_cp14_task_research_authority_chain.py`. Together these lock
the frozen exact-one-field result, tuple coercion inside the `Exception` zone,
success identity, runtime service dependency binding, the single stage
callsite and the unchanged following V8 boundary.

For the 3P2 V8 candidate research-execution canary extraction, run both
unchanged 3P1 files:
`tests/orchestrator/test_v8_research_execution_canary_boundary_characterization.py`
and `tests/orchestrator/test_v8_research_execution_canary_characterization.py`.
Also run `tests/orchestrator/test_v8_research_execution_canary_stage.py` and
`tests/orchestrator/test_v8_research_execution_canary_stage_service_integration.py`.
Together these lock the frozen exact-three-field result, fresh fallback and
observer lists, conversion placement, success and element identity,
`Exception`-only fail-open behavior, runtime service-helper binding, the
single stage callsite, and the unchanged following initial-assessment inputs.

For the 3Q2 initial Phase-C assessment/research-decision/CP13 legacy-gate
extraction, run
`tests/orchestrator/test_phase_c_assessment_research_gate_boundary_characterization.py`
unchanged before and after the edit. Also run
`tests/orchestrator/test_phase_c_assessment_gate_stage.py` and
`tests/orchestrator/test_phase_c_assessment_gate_stage_service_integration.py`.
Together these lock the frozen exact-two-field result, exact observability
labels and argument identity, unchanged success shapes, exception propagation,
runtime service dependency binding, one ordered stage callsite and the bounded
research call remaining in `service.py` with its fresh `list(results)` and
sender.

For the 3R2 bounded Phase-C research and immediate agent-metrics extraction,
run
`tests/orchestrator/test_phase_c_bounded_research_metrics_boundary_characterization.py`
unchanged before and after the edit. Also run
`tests/orchestrator/test_phase_c_bounded_research_stage.py` and
`tests/orchestrator/test_phase_c_bounded_research_stage_service_integration.py`.
Together these lock the frozen exact-one-field result, exact observability
boundary, fresh ordered results list, success identity, dict-only metric
updates, partial mutation behavior, exception propagation, runtime service
dependency binding, one ordered stage callsite and unchanged reconciliation.

For the 3S2 Phase-C reconciliation and immediate evidence-metric extraction,
run
`tests/orchestrator/test_phase_c_reconciliation_metrics_boundary_characterization.py`
unchanged before and after the edit. Also run
`tests/orchestrator/test_phase_c_reconciliation_stage.py` and
`tests/orchestrator/test_phase_c_reconciliation_stage_service_integration.py`.
Together these lock the frozen exact-one-field result, raw success identity,
exact observability arguments, list/tuple-only count replacement, partial
mutation behavior, exception propagation, runtime service dependency binding,
one ordered stage callsite and synthesis remaining in `service.py`.

For the 3T2 Phase-C grounded-synthesis extraction, run
`tests/orchestrator/test_phase_c_synthesis_boundary_characterization.py`
unchanged before and after the edit. Also run
`tests/orchestrator/test_phase_c_synthesis_stage.py` and
`tests/orchestrator/test_phase_c_synthesis_stage_service_integration.py`.
Together these lock the frozen exact-one-field result, raw synthesis identity,
the exact observability boundary, exception propagation and timing mutation,
runtime service dependency binding, one ordered stage callsite and the
unchanged pipeline handoff and outer Phase-C fail-open.

For the 3U2 Phase-C evidence-pipeline assembly extraction, keep
`tests/orchestrator/test_phase_c_evidence_pipeline_assembly_boundary_characterization.py`
byte-identical and run it together with
`tests/orchestrator/test_phase_c_evidence_pipeline_stage.py` and
`tests/orchestrator/test_phase_c_evidence_pipeline_stage_service_integration.py`.
Together these lock the frozen one-field result, exact ordered 25-key plain
mapping, single requirement-id read, raw runtime-serializer return identity,
runtime dependency binding, single ordered service callsite, outer `Exception`
fail-open, `BaseException` propagation and the unchanged following legacy
presentation boundary. The 3T2 integration test may only move its final ordering
boundary from the direct serializer call to the new 3U2 stage call.

For the 3V2 post-Phase-C clarification/status extraction, keep
`tests/orchestrator/test_post_phase_c_clarification_status_boundary_characterization.py`
byte-identical and run it with `tests/orchestrator/test_post_phase_c_status_stage.py`
and `tests/orchestrator/test_post_phase_c_status_stage_service_integration.py`.
Together these lock the frozen ordered two-field result, exact scan and
fallback semantics, runtime accepted-helper binding, one service callsite,
direct result bindings, exception propagation outside the Phase-C fail-open,
and the unchanged following bounded-research boundary.

For the 3W2 bounded-research-v1 extraction, keep
`tests/orchestrator/test_phase_c_bounded_research_v1_boundary_characterization.py`
byte-identical and run it with
`tests/orchestrator/test_phase_c_bounded_research_v1_stage.py` and
`tests/orchestrator/test_phase_c_bounded_research_v1_stage_service_integration.py`.
Together these lock the frozen ordered two-field result, fresh defaults, exact
gate and agent/legacy arguments, dict-only metadata parsing, counter coercion
and partial mutation, runtime binding of all five service dependencies, one
ordered service callsite, direct result bindings, and the unchanged
`_build_user_answer` boundary.

For the 3X2 answer-presentation extraction, keep
`tests/orchestrator/test_answer_presentation_boundary_characterization.py`
byte-identical and run it with
`tests/orchestrator/test_answer_presentation_stage.py` and
`tests/orchestrator/test_answer_presentation_stage_service_integration.py`.
Together these lock the frozen exact-one-field result, lazy
`requested_information` evaluation after the clock and inside the existing
`try`, exact research selection and string conversion, truthy-only mojibake
repair, timing mutation in `finally`, runtime binding of all four service
dependencies, one ordered stage callsite, direct answer binding and the
unchanged composition handoff and wrapper chain.
