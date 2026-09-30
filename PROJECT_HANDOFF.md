# PROJECT HANDOFF — orchestrator fase 4

## Actuele update — P3.2b capability_unsupported migratie voorbereid (niet toegepast)

- Op basis `06370ae1463cec380c39d76247434f466c7c6ef6` zijn uitsluitend minimale,
  reviewbare SQL-assets en gebruiksdocumentatie voorbereid voor
  `observability.orchestrator_runs.error_category`. De bestaande gevalideerde
  CHECK wordt uitsluitend uitgebreid met `capability_unsupported`; alle oude
  waarden en `NULL`-semantiek blijven behouden.
- De actuele database is alleen read-only geïnspecteerd: `promati`, nullable
  `text`-kolom, constraint `ck_orchestrator_runs_error_category` gevalideerd en
  nog op de oude P3.2-lijst. Er zijn alleen schemawaarden en geaggregeerde
  categorieaantallen gelezen. Geen schemawijziging, backup/export,
  livebusinesscall, commit, push of deployment is uitgevoerd.
- Apply vereist aparte expliciete GO en de preflight/backupcontrole uit
  `docs/orchestrator-error-category-capability-unsupported-migration.md`.
  Rollback is fail-closed: bestaande `capability_unsupported`-runrecords
  worden nooit verwijderd of herschreven en blokkeren een terugkeer naar de
  oude constraint. Dit herstelt niet automatisch de huidige persistentie.

## Werkboomstatus — blade-height-filtergrens (basis `5ba81073`, review vereist)

- Deze geïsoleerde werkboom bevat een niet-gecommitteerde, beperkte productieaansluiting van de bestaande pure meshoogteparser/-beslissing. Alleen een expliciete resultaatselectie met een door de bestaande resolver geleverde én intern coherente area/installatie-scope stopt vóór generieke planning, specialist- en researchcalls en retourneert top-level `status: "unsupported"` met de begrensde melding dat filteren voor die scope nog niet wordt ondersteund.
- Bestaande blockers en scopeclarificaties behouden voorrang; ongeldige predicate, ontbrekende of tegenstrijdige scope en multi-intent krijgen een begrijpelijke Nederlandse clarification. Onvolledige en niet-eindige predicates worden bewust aan de parser aangeboden; uitleg- en citaatvragen blijven legacy. De bestaande classifier herkent niet iedere combinatie van filter met slijtage-uitleg als multi-intent; de boundary behoudt die combinatie daarom lokaal via clarification, zonder een component uit te voeren.
- De parser/decision, backendcontract, endpoints en QueryPlan/schema zijn niet gewijzigd; interne parser/decisiondata wordt niet geserialiseerd. De bestaande publieke QueryPlan-clarificationvelden worden op boundary-antwoorden met de top-level clarification gesynchroniseerd.
- De bestaande interne health-taxonomie classificeert top-level of result-level `unsupported` als `capability_unsupported` met technische health `healthy`: dit is een herkenbare capability-uitkomst, geen succesvolle businessactie of infrastructuurfout. Clarification en aangetoonde result-/research-/evidencefouten houden voorrang; het bestaande privacyveilige `error_category`-veld maakt de uitkomst zichtbaar in runlogging en operability, zonder publiek veld of schemawijziging.
- Geen commit, push, deployment, Docker of databaseactie uitgevoerd. Coördinatorreview vereist vóór een volgende mijlpaal.

## Actuele status (4G2F-audit, 2026-09-27)

- Branch en geverifieerde basis: `feature/monteur-flow`, commit
  `da6211e131ffc012da973c653ce095ba5948d19c` (4G2E), schone checkout.
- Fase 3 is afgesloten. Fase 4 is op presenter-routingniveau afgesloten door
  deze read-only 4G2F-audit; dit is **geen** claim dat de bredere
  orchestrator-, endpoint- of capabilityroadmap voltooid is.
- 4G2E extraheerde de volledig gekarakteriseerde `band_deep_analysis`-presenter
  naar `api/app/orchestrator/asset_band_deep_analysis_answer_stage.py`.
  De commit bevat precies vijf files, met 1.313 toevoegingen en 900
  verwijderingen: de leaf, `service.py`, de characterizationtest en directe/
  service-integratietests.

## 4G2F-auditbevindingen

Geverifieerd op de actuele code, zonder productiecode te wijzigen:

- `service.py:1613-1939` (`_build_user_answer`) doet de asset-prescan,
  first-matchselectie, identiteitsheader en requested-information-normalisatie,
  en routeert daarna in exact deze volgorde onder de exacte
  `analysis_assistant`-selectie: `inspection_summary` (`:1720-1735`),
  `lifecycle` (`:1741-1757`), `maintenance_positions` (`:1764-1779`) en
  `band_deep_analysis` (`:1791-1807`). Iedere niet-`None` leaf-answer keert
  onmiddellijk terug; `None` valt door naar de volgende route.
- Iedere van die vier asset-stagecalls komt eenmaal voor binnen de bedoelde
  dispatchergrens. De deep-analysis-stagecall is eenmaal aanwezig op
  `service.py:1799`; zijn grote presenterlocals (`raw_positions`,
  `raw_forecasts`, forecastgroepen en lifecycle-facets) staan niet meer in de
  dispatcher maar uitsluitend in de leaf op
  `asset_band_deep_analysis_answer_stage.py:12-919`.
- De generieke assetfallback blijft bewust service-owned op
  `service.py:1703-1716` en `:1809-1817`: eerste geselecteerde asset,
  bestaande identiteitsheader, dan exact `message -> kort_resultaat ->
  header-only`. Dit behoudt de bestaande Python-truthiness en `str()`-conversie.
  Het is routingglue, geen volgende extractie- of characterizationmilestone.
- Na de assetroute blijft de non-assetresultaatloop service-owned; deze
  routeert diagnostics, scope, product, ORG en technical naar hun bestaande
  leaves en eindigt met het bestaande `None`-fallthrough op `:1937`.

Resterende onzekerheid: deze audit is statisch plus bestaand test-/regressiebewijs.
Hij bewijst geen nieuwe runtime-inhoud, endpointactualiteit of een volledige
groene regressiesuite. De vier top-level `run_orchestrator`-facadedefinities
blijven bewust buiten fase 4; hun wrappercontract is ongewijzigd en is een
bestaande baseline-eigenschap.

## Bewijs en bekende baseline

- 4G2E startcharacterization: 176 passed; kandidaatcharacterization: 198
  passed. De gerapporteerde relevante gerichte suite telt 631 gevallen.
- Canonieke deterministic suite met `--ignore=tests/integration`: start
  `3562 passed / 56 failed / 5 errors / 18 skipped`; kandidaat
  `3584 passed / 56 failed / 5 errors / 18 skipped`. JUnit telt subtests;
  de ruwe kandidaatuitvoer meldt `3474 passed` plus `110 subtests passed`.
  Vergelijking met zowel start als
  `artifacts/orchestrator-baseline/post-change-57fe45e.json` rapporteert nul
  nieuwe en nul opgeloste failure/error-namen. Dit is een nameset-gate, niet
  een groen-suite-claim.
- De zeven strict CP0-XPASSes (M3, M4, S2-S6) waren al baseline. De bekende
  56 failures en vijf errors, waaronder de vier-definitie-
  `run_orchestrator`-shape en omgevings-/historische contractgaten, zijn niet
  door 4G2E gewijzigd.
- Bronbewijzen zijn privacy-safe regressierapporten
  `C:\tmp\4g2e-start.json`, `C:\tmp\4g2e-candidate.json` en
  `C:\tmp\4g2e-candidate-rX.txt`.
- Door de gebruiker aangeleverd livebewijs in
  `C:\Users\john_\.codex\attachments\5dce8153-042a-49ed-9e38-3531ce5d9a70\Geplakte tekst.txt`
  toont een fast-forward, succesvolle API-build en startup, gevolgd door
  `/healthz` met `status: ok`. De eerste healthcheck direct na recreate faalde
  tijdelijk; de volgende poging herstelde. Dit is gebruikersaangeleverd
  deploymentbewijs, niet een door deze audit uitgevoerde deployment.

## Fasegrens en volgende milestone

Geen productiecode, tests, Docker, database of deployment wijzigen in deze
audit. Geen commit of push zonder afzonderlijke review-go.

De eerstvolgende, afzonderlijk te autoriseren milestone is uitsluitend
**endpointinventarisatie en actualiteit, inclusief de relatie met
orchestrator-capabilities**. Zij inventariseert read-only routers/endpoints,
planner/registry-drift en capabilitygaten (zoals maintenance positions); zij
start geen endpoint-, router-, multi-intent- of capabilityimplementatie.

## Impact

Deze auditdocumentatie wijzigt geen schema, API-contract, UI, runtime of
deployment. De bestaande 4G2E-refactor behield de publieke presentatiecontracten
via characterization en namesetvergelijking; dit document verandert daar niets
aan.

## Historisch archief — handoff vóór 4G2E (basis `756e8fe`)

De oorspronkelijke handoff is hieronder behouden voor architectuurbesluiten,
eerdere mijlpalen, omgevingsinformatie en operationele context. De actuele
status, het fallbackbesluit en de volgende milestone staan hierboven en
hebben voorrang op de oude status en planning in dit archief.

Uitspraken zoals "4G2E has not started", percentages, checkoutstatus,
versies en "Next steps" beschrijven uitsluitend de situatie vóór 4G2E.
De oude uitvoer-/commitstappen zijn geen nieuwe opdrachten of autorisatie.
Architectuurkeuzes en veiligheidsregels blijven relevante context waar ze
niet door actuele repository-instructies of de status hierboven zijn vervangen.
De oorspronkelijke hoofdcheckout en zijn handoff zijn niet gewijzigd.

### Historisch: Project overview

PROMATI AI Platform is an industrial inspection, maintenance-planning, product/RAG and RFQ platform. A FastAPI backend exposes database, diagnostics, product, inspection, planning and AI-orchestration APIs. PostgreSQL stores operational data, Qdrant supports vector retrieval, MinIO stores objects/photos, Keycloak provides identity, and React/Flutter clients consume the API.

The long-running refactor goal is to turn the large orchestrator service into a stable router over small, explicitly wired leaf stages without changing public behavior. Phase 3 extracted the main orchestration pipeline. Phase 4 is decomposing `_build_user_answer` presenter branches.

### Historisch: Current state

- Branch: `feature/monteur-flow`.
- HEAD at handoff creation: `756e8feed89d0133ed72aea0563eaeec256aa444` (`Characterize asset band deep analysis answer`).
- The Docker Compose stack and API health workflow are established; the last known user report said the prior production extraction was live.
- Phase 3 is complete and was closed with a full audit.
- Phase 4 is approximately 85–90% complete.
- The answer dispatcher now delegates multi-product, single-family product, diagnostics, analysis-scope, ORG, technical/CEMA, asset inspection summary, asset lifecycle and asset maintenance positions to leaf stages.
- `band_deep_analysis` is fully characterized but is still inline in `api/app/orchestrator/service.py`.
- The generic asset fallback remains service-owned and small.

The main checkout is intentionally very dirty: at inspection it contained 494 status entries (21 modified, 150 deleted, 323 untracked). These changes cover mobile/planner/validation/PDF/test-mode/cleanup work, backups and generated reports and predate this handoff. They are not part of the orchestrator handoff and must not be reset or swept into an orchestrator commit.

### Historisch: Current task

The next task is **4G2E**, a mechanical extraction of the characterized inline `band_deep_analysis` presenter from `_build_user_answer`.

Characterization is committed in:

- `api/tests/orchestrator/test_asset_band_deep_analysis_answer_characterization.py`

The test suite reports 176 cases and establishes that the whole approximately 894-line branch is the smallest behavior-preserving boundary. The recommended interface is:

```python
run_asset_band_deep_analysis_answer_stage(
    asset_result: dict[str, Any],
    asset_header_lines: tuple[str, ...],
    requested: set[str],
) -> AssetBandDeepAnalysisAnswerStageResult
```

The frozen result should contain only `answer: str | None`. No injected production dependencies are currently required.

### Historisch: Completed work

#### Historisch: Phase 3

Phase 3 extracted and wired the orchestration pipeline through single production callsites, including planning, execution, observability, serialization, Phase-C entry/research/evidence/synthesis, CP9–CP15, answer presentation, final response building and final observability. The compatibility facade remains `CP4F -> CP4B -> CP3C -> core`.

#### Historisch: Phase 4

Completed characterization/extraction pairs:

- 4A: top-level answer dispatch and multi-product delegation.
- 4B: single-family product answer.
- 4C: diagnostics answer.
- 4D: analysis-scope answer.
- 4E: ORG answer.
- 4F: technical/CEMA answer.
- 4G2B: asset inspection-summary answer.
- 4G2C: asset lifecycle answer.
- 4G2D: asset maintenance-positions answer.

Completed tests-only work:

- 4G1A asset routing.
- 4G1E band-deep-analysis characterization (`756e8fe`).

Important recent commits are visible with `git log`; the immediate sequence is `4c38374` (inspection extraction), `6dea111` (lifecycle extraction), `8cfc238` + `0a96c20` (maintenance extraction and whitespace fix), and `756e8fe` (deep-analysis characterization).

### Historisch: Work in progress

No orchestrator production change is currently uncommitted. 4G2E has not started.

The main checkout contains extensive unrelated unfinished work. Notable tracked modifications include `api/app/main.py`, inspection/planner/validation routers, Flutter application files, Compose override/configuration, mobile inspection documentation and root operational tools. Notable untracked work includes new routers/services, SQL scripts dated 2026-09-15/16, many D8–D16 reports/scripts, backups and check outputs. Review `git status --short` before doing anything; do not assume these files are disposable.

### Historisch: Architecture

- `api/app/main.py` creates the FastAPI app and registers product, scraper, machine, inspection, RAG, diagnostics, database-context, hybrid/orchestrator, mobile, validation, planner, user/history and administrative routers.
- `api/app/orchestrator/service.py` remains the orchestration router and compatibility facade. It currently has four intentional physical `run_orchestrator` definitions for the facade chain.
- `api/app/orchestrator/*_stage.py` modules are leaf boundaries. Dependencies are passed explicitly from `service.py`; leaf modules must not import the service.
- `api/app/routers/` exposes HTTP endpoints; `api/app/services/` owns reusable domain/data services.
- PostgreSQL is accessed through SQLAlchemy/psycopg2. Qdrant is the vector store; MinIO is object/photo storage; Keycloak provides identity; OpenAI and optional local model/technical-review services support AI operations.
- React/Vite is a web client. Flutter is the actively developed inspection/planning UI and talks to the FastAPI API.
- Docker Compose connects services on the `core` network. PostgreSQL and MinIO are published only on localhost by default; Qdrant is internal-only in the tracked compose file.

### Historisch: Important files

- `AGENTS.md`: durable rules for future Codex sessions.
- `api/app/main.py`: FastAPI composition and router registration.
- `api/app/orchestrator/service.py`: orchestrator core, answer dispatcher and compatibility facade.
- `api/app/orchestrator/asset_*_answer_stage.py`: extracted asset presenters.
- `api/tests/orchestrator/test_asset_*`: phase-4 characterization and integration contracts.
- `docs/orchestrator-architecture-and-cleanup-map.md`: detailed extraction map and architectural history.
- `docs/orchestrator-regression-runbook.md`: canonical nameset-based regression workflow.
- `api/scripts/run_orchestrator_regression.py`: builds/runs the deterministic pytest selection and writes privacy-safe JSON.
- `artifacts/orchestrator-baseline/post-change-57fe45e.json`: historical comparison baseline.
- `docker-compose.yml`, `.env.example`, `api/Dockerfile`, `api/Dockerfile.test`: runtime/test setup.
- `api/requirements.txt`, `api/requirements-test.txt`: Python dependencies.
- `frontend/package.json`: React commands and dependencies.
- `frontend_flutter/promati_inspection_app/pubspec.yaml`: Flutter/Dart dependencies.
- `docs/mobile_inspection_api_contract_v1.md`: mobile/planner API contract; note that the current checkout also contains uncommitted edits.
- `api/sql/` and `sql/`: schema scripts. There is no confirmed automatic migration ordering tool.

### Historisch: Technical decisions

- **Characterize, then extract.** Tests-only steps freeze current Python semantics before production movement. This avoids accidentally correcting legacy behavior during refactoring.
- **Mechanical leaf stages.** Each extraction moves one coherent block, uses a frozen minimal result, and preserves identity, ordering, truthiness, conversions, exception zones and fallthrough.
- **Runtime-resolved dependency injection.** Service callables are passed to leaves instead of imported, preserving monkeypatchability and preventing circular imports.
- **Nameset-based regression gate.** The suite has known historical red tests, so acceptance is zero new failure/error names, not raw pytest exit code alone.
- **One-stage deep-analysis extraction.** The 4G1E AST analysis found about 894 lines/1,805 nodes. Its facet block shares `positions`, formatting, answer state and return ownership. Splitting it now would require a new intermediate model and introduce semantic risk; move it as one mechanical stage first.
- **Keep routing in service.** Asset prescan, first-match behavior, header creation, selectors, route order and generic fallback remain in `_build_user_answer` while presenters move out.
- **Preserve legacy text exactly.** Some output contains mojibake separators. They are part of the characterized contract and must not be repaired during extraction.

### Historisch: Constraints / things not to change

- Do not reset, clean or bulk-stage the dirty main checkout.
- Do not combine the unrelated mobile/planner/PDF work with orchestrator commits.
- Do not rewrite `_build_user_answer` wholesale or “simplify” its selectors/fallthrough.
- Do not split deep-analysis before the one-stage mechanical move unless new evidence invalidates the 4G1E boundary.
- Do not change known failure/xfail contracts merely to make the raw suite green.
- Do not remove the multiple orchestrator facade definitions without a dedicated compatibility characterization.
- Do not alter database schema or apply SQL automatically without identifying ordering, backup and rollback requirements.
- Existing repository files contain unsafe local/example credential material. Never copy those values into new docs or commits; replace with environment-variable references when separately authorized.
- Never expose secrets from `.env`, Compose overrides, code defaults or runtime inspection.

### Historisch: Environment and setup

#### Historisch: Required tooling

- Docker Engine and Docker Compose. Inspected host versions were Docker 29.7.2 and Compose 5.5.1; these are observations, not strict minimums.
- Production API image uses Python 3.11. The host happened to have Python 3.14.7, but local pytest dependencies were not consistently installed; prefer Docker for reproducible tests.
- React container uses Node 20. The inspected host had Node 24/npm 11.
- Flutter container uses Ubuntu 22.04, Java 17, Flutter stable and Android platform/build-tools 35. The app requires Dart SDK `^3.12.2`.

#### Historisch: Initial setup

1. Clone/check out `feature/monteur-flow` into a clean worktree. Do not use the dirty main checkout for isolated orchestrator changes.
2. Copy `.env.example` to `.env` and provide local secret values outside Git.
3. Ensure the external Docker volumes named in `docker-compose.yml` exist (`ai-platform_pgdata`, `ai-platform_qdrantdata`, `ai-platform_minio`).
4. Start the stack:

```powershell
docker compose up -d
docker compose ps
Invoke-WebRequest -UseBasicParsing http://localhost:8000/healthz
```

API-only rebuild:

```powershell
docker compose build api
docker compose up -d --no-deps --force-recreate api
docker compose ps api
Invoke-WebRequest -UseBasicParsing http://localhost:8000/healthz
docker compose logs --tail 100 api
```

Python dependencies for a local environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r api\requirements.txt -r api\requirements-test.txt
```

Focused/full API tests:

```powershell
cd api
python -m pytest -q tests\orchestrator\<test_file>.py
python -m pytest -q tests --ignore=tests\integration
```

Canonical orchestrator regression:

```powershell
cd C:\ai-platform
python api\scripts\run_orchestrator_regression.py --label candidate --compare-to artifacts\orchestrator-baseline\post-change-57fe45e.json
```

React:

```powershell
cd frontend
npm ci
npm run dev
npm run lint
npm run build
```

Flutter:

```powershell
cd frontend_flutter\promati_inspection_app
flutter pub get
flutter analyze
flutter test
```

Alternatively, start the Flutter web container with `docker compose -f docker-compose.yml -f docker-compose.flutter.yml up --build flutter-dev`.

No repository-wide Python static typecheck is configured. Use compile/AST checks and tests; do not invent a mypy/ruff requirement.

#### Historisch: Environment variable names

Populate values privately. Relevant names observed in `.env.example`, Compose and application code include:

- Database: `DATABASE_URL`, `SQLALCHEMY_DATABASE_URL`, `PROMATI_DATABASE_URL`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST_PORT`.
- API/web: `API_HOST_PORT`, `FRONTEND_HOST_PORT`, `PUBLIC_API_URL`, `PUBLIC_WEB_URL`, `PROMATI_API_BASE_URL`, `CORS_ALLOWED_ORIGINS`.
- Keycloak: `KC_BASE`, `REALM_NAME`, `KEYCLOAK_ADMIN`, `KEYCLOAK_ADMIN_PASSWORD`, `KEYCLOAK_HOST_PORT`, `KEYCLOAK_AUDIENCE`, `KEYCLOAK_ISSUER`, `KEYCLOAK_JWKS_URL`.
- OpenAI/research: `OPENAI_API_KEY`, `OPENAI_CHAT_MODEL`, `OPENAI_EMBEDDING_MODEL`, `OPENAI_VISION_MODEL`, `USE_OPENAI_VISION`, `AI_RESEARCH_AGENT_ENABLED`, `AI_RESEARCH_PROVIDER`, `OPENAI_EMBED_BATCH_SIZE`.
- Qdrant: `QDRANT_URL`, `QDRANT_HOST_PORT`, `QDRANT_API_KEY`, `QDRANT_COLLECTION`, `QDRANT_UPSERT_BATCH_SIZE`.
- MinIO: `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `MINIO_BUCKET`, `MINIO_BUCKET_RFQ`, `MINIO_SECURE`, `MINIO_HOST_PORT`, `MINIO_CONSOLE_HOST_PORT`.
- Other services: `CLOUDFLARED_TOKEN`, `EDOCR2_URL`, `TECHREVIEW_URL`, `TECHREVIEW_HOST_PORT`, `TECHREVIEW_MODEL`, `TECHREVIEW_USE_PHI`, `OLLAMA_URL`.
- Operational paths/admin: `RFQ_PDF_DIR`, `RFQ_UPLOAD_DIR`, `PROMATI_CUSTOMER_REPORT_ROOT`, `ORG_ADMIN_USER`, `ORG_ADMIN_PASSWORD`.
- RAG behavior: `RAG_DEFAULT_MODE`, `RAG_RERANK_CANDIDATES`, `RAG_USE_MMR`.

### Historisch: Database / external services

- PostgreSQL 16 is the operational store. SQLAlchemy engines are created in `api/app/db.py`, `api/app/deps.py` and several routers/services.
- SQL changes live in both `api/sql/` and root `sql/`. Recent untracked scripts cover inspection users, planner tasks/revisions, validation workflows, week-planning import columns and live-test filtering. Determine applied state against the target database before running any script.
- Qdrant stores vector/RAG data and is internal to the Compose network in the tracked configuration.
- MinIO stores generated/object data including inspection photos/RFQ assets.
- Keycloak provides authentication/realm setup; the tracked init service is currently a placeholder.
- OpenAI models, optional Ollama/techreview and eDOCr2 support AI/OCR workflows.
- Cloudflare Tunnel can expose the API. Treat all public exposure and wildcard Keycloak settings as development-only until hardened.

### Historisch: Known issues

- Canonical orchestrator runs are not raw-green. Depending on the exact checkout/image selection, reports show 55 current failure/error names or the historical 61-name set including six retention tests. Acceptance requires comparing exact start and candidate namesets and explaining retention selection.
- Five expected XFAILs remain. Seven strict CP0 XPASS cases are historically reported as failures; do not treat them as new without nameset comparison.
- Five Phase-C8 setup errors reflect an old uniqueness assumption versus the intentional four-definition facade.
- Several evidence-adapter/P4.14c failures are historical baseline items.
- Candidate Docker builds have repeatedly missed cached apt/pip layers. BuildKit may still attempt registry metadata/auth resolution even with a networkless build request.
- The root/API READMEs are incomplete or stale and should not be treated as authoritative setup documentation.
- Plaintext credential defaults/overrides exist in pre-existing tracked or locally modified files. This handoff does not repeat them. They should be removed/rotated in a dedicated security task.
- No verified Alembic-style migration runner or authoritative migration order exists.
- The main checkout contains hundreds of unrelated modified/deleted/untracked files and generated backup material.

### Historisch: Uncommitted / unfinished changes

At handoff creation, only `AGENTS.md` and `PROJECT_HANDOFF.md` are new handoff changes made by this task. All other dirty items existed beforehand and must remain untouched.

Before committing these documents, run `git status --short` and stage only these two files. The many mobile/planner/validation/PDF/configuration/cleanup changes are unfinished or independently managed; their exact intent cannot be inferred safely from Git alone.

### Historisch: Next steps

1. **Review and commit the handoff documents.**
   - Files: `AGENTS.md`, `PROJECT_HANDOFF.md`.
   - Result: durable instructions and current-state transfer are present on `feature/monteur-flow` without unrelated files staged.
   - Verify: `git diff --check -- AGENTS.md PROJECT_HANDOFF.md`, inspect for secrets, then `git status --short`.

2. **Create an isolated worktree at `756e8fe`/latest `feature/monteur-flow` for 4G2E.**
   - Do not work in the dirty main checkout.
   - Verify start ancestry, clean status and baseline 4G1E test count (176 passes).

3. **Mechanically extract deep-analysis.**
   - New file: `api/app/orchestrator/asset_band_deep_analysis_answer_stage.py`.
   - Modify: `api/app/orchestrator/service.py` with one import, one call and direct non-`None` return.
   - Inputs/result exactly as stated in “Current task”. Copy header tuple to a fresh list. Move the whole characterized branch intact.
   - Keep prescan, header/display calls, requested normalization, selectors, prior asset stages and generic fallback in service.

4. **Add and mechanically update tests.**
   - New direct stage and service-integration tests under `api/tests/orchestrator/`.
   - Update only the AST/builtin monkeypatch boundaries in `test_asset_band_deep_analysis_answer_characterization.py` and demonstrably adjacent layout tests.
   - Desired result: all 176 characterization cases still pass; no behavior assertions are weakened.

5. **Run focused and full verification.**
   - Focus on 4G1A through 4G2E plus asset/replacement/routing/alignment tests.
   - Run the canonical nameset gate against both exact start revision and `post-change-57fe45e.json`.
   - Desired result: zero new failure/error names, no new unexpected XPASS, clean diff/syntax/import/callsite/privacy checks.

6. **Commit/push only after explicit review approval, then rebuild/live-check.**
   - Pull `feature/monteur-flow` in `C:\ai-platform`, rebuild/recreate only `api`, verify `/healthz` and logs.
   - Do not stage unrelated main-checkout changes.

7. **Decide the generic asset fallback.**
   - Inspect the small service-owned `message -> kort_resultaat -> header-only` path.
   - Either characterize/extract it as one small final presenter or explicitly document why it remains routing glue.

8. **Close Phase 4 with an audit.**
   - Verify `_build_user_answer` is chiefly routing over leaf stages, one callsite per stage, no duplicated presenter blocks, docs current, and full nameset unchanged.
   - Record intentionally service-owned logic and the next phase boundary.

### Historisch: Definition of done

4G2E is done only when:

- The whole characterized deep-analysis branch is in one dependency-free leaf with a frozen one-field result.
- The service retains the exact route order and generic fallback.
- 4G1E’s 176 cases and new direct/integration tests pass.
- Focused and canonical gates introduce zero new failure/error names and zero unexpected XPASS names.
- `git diff --check`, syntax/AST, import, unique-callsite, no-duplication and privacy checks pass.
- No test/cache/bytecode/JUnit/container artifacts remain.
- Runtime identity is unchanged during verification; after approved deployment, the rebuilt API passes `/healthz` and log inspection.
- Only reviewed files are committed and pushed after explicit authorization.

### Historisch: Context that is not obvious from the code

- Work was deliberately split into “1” characterization tasks and “2” mechanical extraction tasks. Continue that discipline.
- The user expects a separate Codex task/worktree for implementation; the coordinating session reviews evidence and alone performs commit/push after explicit GO.
- After every production-code push, provide the exact PowerShell pull/build/recreate/health/log commands. Tests-only pushes require only `git pull --ff-only`.
- The orchestrator baseline is intentionally evaluated by failure names, not by demanding a raw-green suite.
- Retention tests can appear as six resolved names or six historical failures depending on whether the current worktree SQL file is included. Always compare start and candidate using the same selection/image/mount.
- Budget was constrained at transfer time; avoid launching the large 4G2E task unless sufficient account budget is available.
- Existing user work in the main checkout is extensive and unrelated. A clean worktree is mandatory for orchestrator continuation.

### Historisch: HANDOFF SUMMARY

1. **Current branch:** `feature/monteur-flow`, HEAD `756e8feed89d0133ed72aea0563eaeec256aa444` at inspection time.
2. **Current Git status:** heavily dirty from pre-existing work (494 entries at inspection); this handoff adds only untracked `AGENTS.md` and `PROJECT_HANDOFF.md`.
3. **Main current task:** prepare and execute 4G2E, the single-stage mechanical extraction of `band_deep_analysis`.
4. **First concrete action:** review/commit only the two handoff files, then create a clean worktree from the latest `feature/monteur-flow` and rerun the 176-case 4G1E baseline.
5. **Read first:** `AGENTS.md`, this file, `docs/orchestrator-architecture-and-cleanup-map.md`, `docs/orchestrator-regression-runbook.md`, and `api/tests/orchestrator/test_asset_band_deep_analysis_answer_characterization.py`.
