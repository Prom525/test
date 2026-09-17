# PROMATI orchestrator architectuur- en cleanupkaart

## Besluit

### Gerealiseerde research-context shadow-/call-guard shadowgrens (opdracht 3J2)

De bestaande research-context- en research-call-guard-shadowzones staan nu
mechanisch in `api/app/orchestrator/task_research_context_stage.py`. De frozen
`TaskResearchContextStageResult` retourneert exact de twee onbewerkte
resultaatobjecten. Iedere stageaanroep begint met twee afzonderlijke verse
`[]`-defaults. `list(results)` en de contextcall blijven samen in de eerste
`Exception`-zone; de guardcall blijft in de onafhankelijke tweede zone en
ontvangt exact het contexts-resultaatobject, inclusief de fallbacklijst.
`BaseException` blijft overal propageren.

De core roept de stage exact eenmaal aan na de 3I2-resultaatbinding en bindt
beide velden vóór de ongewijzigde CP13-call. Beide servicecallables worden per
core-aanroep runtime-resolved doorgegeven. CP13 ontvangt nog steeds uitsluitend
`plan`, `task_execution_shadow` en `task_research_authority_p4_6d1`; CP13,
P4.6D2 en alle downstreamlogica en wrappers blijven in `service.py`.

### Gerealiseerde research-decision shadow-/P4.6D1-authoritygrens (opdracht 3I2)

De bestaande research-decision shadow en P4.6D1-authoritycall staan nu
mechanisch in `api/app/orchestrator/task_research_decision_stage.py`. De frozen
`TaskResearchDecisionStageResult` retourneert exact de twee onbewerkte
resultaatobjecten. De onafhankelijke fail-open-zones blijven gelijk: iedere
stageaanroep begint met een verse shadow-`[]`, authority begint met `None`, en
alleen `Exception` wordt gevangen zodat `BaseException` propageert.

De core roept de stage exact eenmaal aan na de 3H2-resultaatbinding en bindt
beide velden vóór de bestaande research-contextzone. Beide servicecallables
worden per orchestrator-aanroep runtime-resolved doorgegeven. De contextfunctie
ontvangt ongewijzigd dezelfde planidentiteit, `list(results)` en uitsluitend
het decisions-shadowobject; P4.6D1-authority, CP13, researchuitvoering,
evidenceverwerking, responsebouw en de wrapperketen zijn niet verplaatst.

### Gerealiseerde task-evidence shadow-/P4.6C-authoritygrens (opdracht 3H2)

De exact in 3H1 gekarakteriseerde task-evidencegrens staat nu in
`api/app/orchestrator/task_evidence_stage.py`. De frozen
`TaskEvidenceStageResult` retourneert uitsluitend het onbewerkte
`task_evidence_assessments_shadow`-object en het onbewerkte
`task_evidence_authority_p4_6c`-object. De stage houdt de twee bestaande,
onafhankelijke `Exception`-fail-open-zones intact: een verse shadow-`[]` per
aanroep en een authoritydefault van `None`. Tuplecoercie blijft binnen de
authorityzone en `BaseException` propageert.

De service roept de stage eenmaal aan direct na product-family recovery en
bindt beide velden vóór de bestaande researchdecision. De twee dependencies
worden per orchestrator-aanroep runtime-resolved doorgegeven, zodat de
bestaande servicemonkeypatchpunten effectief blijven. De researchdecision
ontvangt nog steeds uitsluitend het shadowresultaat; P4.6C-authority,
research/CP13, evidenceverwerking, responsebouw en de wrapperketen blijven op
hun bestaande plaats.

### Gerealiseerde product-family coverage/recoverygrens (opdracht 3G2)

De exact in 3G1 gekarakteriseerde product-family coverage/recoverygrens staat
nu in `api/app/orchestrator/product_family_recovery_stage.py`. De frozen
`ProductFamilyRecoveryResult` retourneert uitsluitend
`product_family_coverage`, `product_family_recovery` en
`working_evidence_items`. De service roept de stage eenmaal aan binnen de
bestaande brede Phase-C-`try`, direct na de 3F2-entry en vóór task-evidence,
en levert alle vier runtime-resolved dependencies expliciet aan. De stage is
een leaf en vangt geen exceptions af; de bestaande service-fallback blijft dus
de enige fail-open grens.

De 35 parametrische 3G1-low-level contractgevallen zijn zonder versoepeling
verplaatst naar directe tests in
`api/tests/orchestrator/test_product_family_recovery_stage.py`:

| Oude 3G1-assertiongroep | Nieuwe directe testlocatie |
| --- | --- |
| Verse defaultmetadata, exact eerste coveragecall, identity en no-recovery return | `test_no_recovery_exact_call_return_contract_and_fresh_default`; `test_default_dict_and_lists_are_fresh_between_calls` |
| Letterlijke tuplecoercie voor zeven shapes | `test_missing_codes_use_literal_tuple_coercion` |
| Truthy applicable-gate voor vier falsey waarden | `test_recovery_requires_truthy_applicable` |
| Exact één recoverycall, sender/append-observer, raw ongebruikt, metadatareplacement | `test_exact_recovery_call_metadata_replacement_counter_raw_unused_and_max_one` |
| Zes counterconversies en behoud beginwaarde | `test_counter_uses_supplied_nonnegative_conversion_and_start_value` |
| Ordered typed normalization, gedeelde timestamp en tuplecompositie | `test_ordered_typed_normalization_timestamp_tuple_composition_and_raw_unused` |
| Zero-evidence tuple-identity | `test_zero_recovered_evidence_preserves_tuple_identity` |
| Tweede coveragecall en vervanging eerste resultaat | `test_second_coverage_exact_objects_and_replaces_first` |
| Zeven failurepunten met exacte partiële countmutatie en propagatie | `test_failure_matrix_propagates_and_preserves_partial_count` |
| Drie malformed coveragevormen | `test_malformed_coverage_shape_propagates_without_recovery` |
| Niet-iterable missing codes | `test_noniterable_missing_codes_propagates_before_applicable_lookup` |
| `None` recoverymetadata vóór countmutatie | `test_none_metadata_propagates_before_counter_mutation` |

De voormalige service-frame-local assertions op
`missing_product_families`, `recovery_typed_results`,
`recovered_evidence_items` en het raw recoveryresultaat staan daarmee bij de
stage die deze locals nu bezit. De resterende 3G1-service-integratietests in
`test_product_family_recovery_boundary_characterization.py` bewijzen exact één
stagecall, runtime dependencylookup, binding vóór task-evidence, één initiële
execution en de bestaande outer fail-open/fallback inclusief partiële count.
De 3F2-structuurtest is alleen mechanisch aangepast: zijn eerdere assertion dat
de coveragecall in `service.py` stond, wijst nu naar de 3G2-stagecall na de
3F2-resultaatbinding.

### Gerealiseerde Phase-C-entrygrens (opdracht 3F2)

Requirementlookup, de bestaande clarificationgate, de ene UTC-timestamp en de
initiële typed-evidencenormalisatie staan nu in
`api/app/orchestrator/phase_c_entry_stage.py`. De frozen
`PhaseCEntryResult` retourneert requirementset, timestamp en de initial/working
tuples; beide evidencevelden verwijzen bij terugkeer naar exact dezelfde tuple.
Alle dependencies worden per core-aanroep vanuit `service.py` aangeleverd.
De bestaande brede Phase-C-`try`, product-family coverage/recovery en alle
latere Phase-C- en authoritylogica blijven in `service.py`.

### Gerealiseerde initiële execution-observabilitygrens (opdracht 3E)

De drie bestaande initiële execution-metrics worden nu mechanisch vastgelegd
door `_record_initial_execution_observability` in
`api/app/orchestrator/observability_stage.py`. De core roept dezelfde helper
exact eenmaal aan nadat alle negen 3D2-resultaten lokaal zijn gebonden en vóór
initialisatie van de evidencepipeline. Mapping-/objecttoegang, attempts-shape,
integerconversie, `len(results)` en exceptionsemantiek zijn ongewijzigd.

### Gerealiseerde initiële planningsgrens (opdracht 3C)

De bestaande keten understanding, routing sanity, research requirement en
execution planning wordt nu mechanisch gecoördineerd door
`initial_planning_stage.py`. Vraagselectie/-trim en serialisatie van
`conversation_context` blijven in `service.py`. Alle vier bewerkingsfuncties
en `_observability_call` worden bij iedere core-aanroep expliciet vanuit
`service.py` aangeleverd. Daardoor blijven de bestaande service-level
monkeypatchpunten runtime-effectief. De timinglabels en volgorde zijn
ongewijzigd; routing sanity krijgt bewust geen eigen timinglabel. De stage is
een leaf met alleen typing-imports en bevat geen uitvoering, evidence,
research, response- of repairlogica.

### Gerealiseerde pure serialisatiegrens (opdracht 3B)

De pure JSON-serialisatiehelpers `_model_to_dict` en
`_evidence_pipeline_to_dict` staan nu in `serialization_stage.py`.
`service.py` importeert en bindt exact dezelfde function objects, zodat
bestaande interne aanroepen en import-/monkeypatchcontracten behouden blijven.
De compacte publieke projectiehelper
`_compact_evidence_pipeline_for_public_response` blijft bewust in
`service.py`: die bevat publiek projectiebeleid en is geen pure serialisatie.
De nieuwe module is een leaf met uitsluitend minimale stdlib- en type-imports.

### Gerealiseerde eerste observabilitygrens (opdracht 3A)

De pure primitive access/clamping, timing- en countmap-initialisatie en de twee
integer-only task/public-composition metricsrecorders staan nu in
`api/app/orchestrator/observability_stage.py`. `service.py` importeert dezelfde
symbolen, zodat bestaande imports en monkeypatchpunten behouden blijven. De
clock-, elapsed- en timingwrapperhelpers blijven bewust in `service.py`, omdat
de characterizationtests `service._observability_now` patchen; verplaatsing zou
dat compatibiliteitscontract wijzigen. Pipeline-, answer-, evidence- en
authoritylogica is niet verplaatst.

Opdracht 3 kan nog niet veilig als brede stage-split starten. Een eerste, mechanische extractie kan wel beginnen nadat de zeven minimale characterizationtests in dit document groen of als expliciete baseline-rood zijn vastgezet. De reden is concreet: de feitelijk geëxporteerde `run_orchestrator` is de vierde definitie in `service.py`; drie post-authority wrappers en de compacte HTTP-response-shaper kunnen het antwoord wijzigen nadat CP12 heeft gedraaid. Zij zijn productiecode, maar vallen niet onder de CP9-CP12-authorityketen.

Deze analyse is read-only voor `api/app`. Zij is gebaseerd op commit `f39ab8b27ad745e14bcc271eca749ee9b9e24676`, die exact de tip is van `codex/orchestrator-baseline-regression`. De analyse-worktree is detached op die commit omdat dezelfde branch al in een andere worktree is uitgecheckt. De pre-gate gaf 803 passed, 56 failed, 5 errors en 17 skipped. De 61 failure/error-namen zijn gelijk aan `post-change-57fe45e.json`; er zijn nul nieuwe failures.

De bestaande API op localhost:8000 is niet gerebuild of vervangen. Alle tien read-only runtime-smokes voldeden aan de HTTP- en publieke contractchecks. De live GSL/3-mm-debugcase bleef een known gap: het domain was `inspection`, maar de zichtbare intent-task was `product_lookup` en er was geen expliciete maintenance-positions capabilityroute. Dit is een runtime-observatie, geen bewijs dat de actieve container uit deze worktree of commit is gebouwd.

## Publieke flow

`POST /orchestrator/ask` in `api/app/routers/orchestrator_api.py` accepteert `models_cp1.OrchestratorAskRequest`. De router maakt een UUID `trace_id`, roept de op importtijd gebonden `service.run_orchestrator` aan, voegt de trace-id toe, plant fail-open persistence via een FastAPI-background task en projecteert daarna `compact` of `debug` met `shape_orchestrator_response`.

Bij een niet-afgevangen exception bouwt de router een privacy-safe exceptionresponse voor synchrone logging, voegt de trace-id toe, roept `persist_orchestrator_run` aan en werpt dezelfde exception opnieuw op. Het bestaande HTTP-foutgedrag blijft dus authoritative; de taxonomie verandert de HTTP-response niet.

Compact bevat alleen `status`, `answer`, `response_profile`, maximaal acht domains, maximaal twaalf compacte tasks, result coverage, trace/request-id, eventuele clarification en een task-execution-samenvatting. Debug retourneert de volledige service-response. `include_trace` beïnvloedt de serviceprojectie van trace/results/evidence, maar `response_profile` bepaalt uiteindelijk de HTTP-shape.

Run logging bewaart status, query class, primary domain, intent, domeinnamen, booleans, aantallen, timings, health en responsegrootte. Vraag, antwoord, entities, scopewaarden, trace en specialistpayloads worden niet opgenomen. Recordbouw en database-insert zijn fail-open.

## Werkelijk geëxporteerde facade

Python bindt top-level namen sequentieel. De vier definities zijn:

1. `service.py:7336`: volledige pipeline.
2. `service.py:9061`: CP3C single-intent `inspection_latest` repair over `_p4_15cp3c_previous_run_orchestrator`.
3. `service.py:9400`: CP4B multi-intent inspection/maintenance repair over `_p4_15cp4b_previous_run_orchestrator`.
4. `service.py:9567`: CP4F raw-text repair over `_p4_15cp4f_previous_run_orchestrator`.

De import `from app.orchestrator.service import run_orchestrator` exporteert definitie 4. De opgeslagen references vormen een vaste wrapperketen: `CP4F -> CP4B -> CP3C -> core`. Een verplaatsing die één assignment overslaat, verandert productiegedrag.

De initiële executiongrens van de core is mechanisch ondergebracht in
`app/orchestrator/initial_execution_stage.py`. De core levert per aanroep alle
productieafhankelijkheden expliciet aan, zodat service-level monkeypatches hun
runtimebinding behouden. `InitialExecutionStageResult` geeft de negen bestaande
waarden terug; attempts/counts en de evidenceketen blijven in `service.py` en
starten pas nadat die waarden onder hun bestaande lokale namen zijn gebonden.
De stage bezit uitsluitend requirement-attach, P4.6A-shadow, P4.6B-canary, de
enige authoritative legacy execution, CP8-shadow en CP9-canary.

## Feitelijke pipelinevolgorde

1. Requestselectie kiest `payload.q`, anders `payload.vraag`, en stript whitespace.
2. `understand_query` normaliseert de vraag, classificeert querytype, detecteert domains, negaties, entities, scope, intent en shadow `IntentTask`-objecten.
3. `apply_routing_sanity` herstelt lokaal vooral system-meta/ORG false positives.
4. `assess_research_requirement` bepaalt planbrede complexiteit en researchbehoefte.
5. `build_execution_plan` muteert `plan.execution_steps`; blockers en clarification leveren nul stappen.
6. Evidence-requirement-id's worden shadow aan intent-tasks gekoppeld.
7. Task-planner shadow vergelijkt taskplannen met het legacy plan. Fouten zijn fail-open.
8. De default-off task-execution canary kan dezelfde allowlisted execution observerend uitvoeren. Resultaten worden niet authoritative.
9. `execute_plan` voert het legacy plan uit. Alle calls zijn POST naar zes assistant-endpoints. Legacy acceptance is ieder resultaat waarvan status niet `error`, `failed` of `failure` is.
10. Typed `ExecutionResult`-observaties worden via een observer verzameld. Fouten in typed derivation zijn fail-open en veranderen legacy execution niet.
11. CP8 `task_execution_shadow` en CP9 planner-canary observeren uitvoering/planning; interne fouten leveren `None`.
12. Als een requirement set bestaat en er geen clarification/blockerende specialiststatus is, start Phase C: typed evidence normaliseren, product-family recovery, task-evidence shadow/canary, assessment, evidence-research gate, begrensde follow-up execution, normalisatie, reassessment, reconciliation en grounded synthesis.
13. De task-lagen P4.6C tot P4.6E3 bouwen conditioneel authoritative task-evidence, task-research, research-execution, research-evidence, grounded-synthesis en coveragecontracten. Flags bepalen activatie; afwezigheid of interne fouten behouden de legacy path.
14. CP13 bepaalt task-scoped researchsemantiek en begrenst legacy generic research. CP14 is de begrensde execution/researchlaag die alleen toegestane actions en pinned params mag gebruiken.
15. Planbrede legacy research draait na deterministische specialists wanneer `research_required` waar is, status ok is en geen clarification geldt. Het researchantwoord overschrijft de legacy presenter wanneer researchstatus `ok` is en `answer` aanwezig is.
16. `_build_user_answer` presenteert anders rechtstreeks uit legacy specialistresults. Daarna repareert `repair_mojibake_text` tekst.
17. Multi-intent composition shadow observeert; een oudere, default-off smalle public-composition canary kan alleen een product+CEMA-shape vervangen.
18. P4.6F maakt een default-off composition candidate. CP9 trekt authority in wanneer required execution niet bewezen is. CP10 vereist volledige grounded task coverage. CP11 presenteert alleen requested, relevante, covered task-units. CP12 begrenst prose en kan authority niet verlenen.
19. CP15 is uitsluitend release-observatie en muteert het antwoord niet.
20. Response build projecteert results en evidence pipeline, zet `question` opnieuw in de interne/debugresponse en voegt observability toe.
21. CP3C, CP4B en CP4F draaien na de core return en kunnen `answer`, plus aanwezige `final_answer`/`antwoord`-aliases, wijzigen.
22. De router voegt trace-id toe. Compact shaping kan raw MV1-output opnieuw repareren en roept CP12-composer nogmaals aan zonder CP10/CP11-statuscontracten.

## Authoritykaart

De machineleesbare uitwerking staat in `artifacts/orchestrator-analysis/component-authority-inventory.json`. De doorslaggevende indeling is:

| Laag | Productie-authority | Failgedrag | Antwoordmutatie |
| --- | --- | --- | --- |
| Understanding, routing sanity, legacy planner | Execution scope en stappen | Blockers/clarification sluiten execution; lokale sanity is deterministisch | Nee |
| Legacy executor | Feitelijke specialistcalls | Transportfout wordt error-result; typed observer fail-open | Nee |
| Typed execution shadow | Observatie, nog niet execution-authority | Fail-open | Nee |
| Phase-C assessment, reconciliation, synthesis | Evidence-authority voor intents met requirement set | Meestal fail-closed binnen Phase C; buiten pipeline blijft legacy beschikbaar | Nee |
| `_build_user_answer` en planresearch | Legacy public-answer authority | Fail-open naar beschikbare resultpresentatie | Ja |
| P4.6C-E3 taskcanaries | Conditioneel evidence/synthesis-authoritative wanneer flags en contracten groen zijn | Fail-open naar legacy path; geen eigen public authority | Nee |
| CP9/CP10 | Intrekken van conditionele public authority | Fail-closed en herstel legacy answer | Ja, door herstel |
| CP11 | Conditionele public-answer authority | Fail-closed naar legacy answer | Ja |
| CP12 | Response safety, geen nieuwe authority | Fail-closed/safe candidate en kan authority intrekken | Ja |
| CP15 | Observability only | Fail-closed release status | Nee |
| CP3C/CP4B/CP4F | Post-authority compatibilityrepair | Fail-open naar vorige response | Ja |
| Compact response shaping | Publieke HTTP-response shaping | Raw MV1 fail-closed naar veilige melding; composer begrenst | Ja |

### Wat werkelijk authoritative is

De legacy planner en executor bepalen altijd de echte eerste specialistcalls. Typed execution is observerend. De legacy presenter of planresearch bepaalt standaard het antwoord. Alleen wanneer de relevante canaryflags actief zijn en CP8-CP12 alle groen zijn, wordt task-gebaseerde composition/presentation conditioneel authoritative. CP9 en CP10 mogen die authority alleen intrekken. CP11 selecteert de publieke grounded claims. CP12 begrenst de geselecteerde tekst en mag geen authority toevoegen.

### Wat na CP12 nog antwoorden kan wijzigen

CP3C wijzigt single-intent MV1 `inspection_latest`; CP4B wijzigt raw/long multi-intent MV1 inspection plus maintenance; CP4F parseert raw tekst voor dezelfde MV1 golden cases. Daarna kan `_repair_raw_mv1_inspection_answer` in `response_shaping.py` opnieuw wijzigen. `compact_orchestrator_response` roept bovendien `compose_concise_public_answer` een tweede keer aan. Geen van deze vier paden consumeert het volledige CP9-CP12-authoritycontract.

### Repairs die de authorityketen omzeilen

Alle drie servicewrappers en de compact-boundary repair omzeilen de authorityketen in structurele zin: zij draaien na CP12 en beslissen op response/evidence/raw-text-shape. CP3C eist wel sufficient accepted inspection evidence; CP4B zoekt evidence- en prioritysignalen; CP4F gebruikt stringmarkers en vaste MV1-waarden, waaronder `2026-05-27`. Dat maakt ze bounded compatibilitycode, maar geen CP9-CP12-governed authority.

## Serviceverantwoordelijkheden en mutaties

`service.py` telt 9.569 regels en bevat observabilityhelpers, serialisatie, legacy presenters, evidencepipeline-integratie, task-shadows/canaries, researchguards, uitvoering, CP9-CP15, responsebouw en drie repairs. `_build_user_answer` alleen beslaat regels 1862-4718 en bevat domeinpresentatie voor product, inspection/latest/lifecycle/maintenance/replacement, technical, RFQ, ORG en diagnostics.

Belangrijke `answer`-mutaties zijn: legacy presenter; planresearch override; mojibake repair; oudere public-composition canary; P4.6F candidate; CP9- en CP10-herstel naar `legacy_answer_before_public_composition_canary`; CP11 presenter; CP12 composer; CP3C replacement; CP4B setter; CP4F setter; compact-boundary MV1 repair; tweede CP12-call. `final_answer` en `antwoord` bestaan niet in de core response, maar CP4B/CP4F houden ze synchroon wanneer een legacy/nested response ze al bevat.

De MV1-specifieke markers zijn `MV1`, `Mengveld 1`, `2026-05-27`, `43 actuele geregistreerde schraperposities`, `latest_blade_height`, `latest_position_measurement`, `DIRECT_ACTIE_3MM_OVERDUE` en `status_3mm`. CP4F bevat een volledig vaste single-latest tekst met datum, vier posities en 3,0-6,0 mm. `inspection_public_repair.py` is eveneens MV1-specifiek.

Brede `except Exception`-paden zijn doelbewust talrijk. Observers, canaries, metrics en logging zijn fail-open. CP11/CP12-authorityfouten zijn fail-closed naar legacy/safe output. Transport vangt iedere exception en maakt een error-result. De top-level HTTP-router logt een exception en re-raiset. Characterization moet dus zowel output als de precieze fallbackrichting vastleggen.

## Planner, executor en registry

De domain-to-actionmapping is product -> `product_assistant`, inspection -> `analysis_assistant`, technical -> `technical_assistant`, RFQ -> `rfq_assistant`, ORG -> `org_assistant`, diagnostics -> `diagnostics_assistant`. Diagnostics is exclusief wanneer primary. Multi-product fan-out maakt één productstep per expliciete familie. `IntentTask` stuurt de echte executionsteps niet; het legacy domainplan doet dat.

Alle actions mappen in `executor.ACTION_ENDPOINTS` naar POST-assistant endpoints. De planner zet geen endpoint of HTTP-method op `ExecutionStep`; de executorregistry bepaalt het pad en `default_sender` gebruikt altijd POST. De specialist registry dupliceert action-to-endpoint en veldcontracten voor typed derivation/researchguards. Dit is een driftpunt.

De planner stuurt voor inspection aanvullende scopevelden, maar `specialist_registry.planner_fields` noemt alleen `vraag` en `mode`. De velden worden wel geaccepteerd, maar de registry beschrijft de feitelijke planneroutput dus onvolledig. Diagnostics planner bouwt `objects`, `lijn_code` en `band_code` conditioneel, terwijl die evenmin allemaal in `planner_fields` staan. De analysis-mode gap uit oudere tests is deels opgelost: `mode` staat nu in accepted inputs, maar de execution blijft een generieke assistant-call en kiest geen expliciete capability.

Legacy acceptance accepteert alle statussen behalve drie errorstrings. Typed semantic outcomes worden uit specialiststatusmaps afgeleid, maar `has_service_accepted_execution` houdt completed non-error outcomes en ontbrekende typed derivation compatibility-breed accepted. RFQ heeft alleen `error -> ERROR`, overige waarden -> `UNKNOWN`; ORG en diagnostics hebben dynamische/onbekende statuscontracten. Evidence assessment en CP10 dragen daardoor de inhoudelijke blokkering.

## Evidenceketen en dubbele definities

De globale requirementcatalog bevat intentsets, waarna een late P4.15Q-wrapper `get_requirement_set` opnieuw definieert en requirementsets uitlijnt. De geëxporteerde functie is de tweede definitie. `evidence_adapters.py` definieert `normalize_execution_result_evidence` tien keer; iedere wrapper bewaart een previous reference en voegt aliases/importbridges toe. De laatste CP3-wrapper is de export. `task_evidence.py` definieert `_select_task_evidence` tweemaal; de late definitie vervangt de oorspronkelijke selectie voor replacement-context.

Normalisatie converteert typed specialistresultaten naar evidence-items voor technical, product knowledge/price-stock/articles, inspection latest/lifecycle/maintenance/replacement, RFQ, ORG en diagnostics. Late adapters voegen position-, asset-, technical-selection-, product-record-, article-, replacement- en lifecyclealiases toe. Assessment toetst requirementtype, bron, grounding, freshness, quality, directness en entityscope. Research gate bepaalt of ontbrekende requirements bounded follow-up toelaten. Reconciliation dedupliceert en ordent. Grounded synthesis maakt alleen claims uit claimable reconciled evidence.

CP10 combineert CP8 required-execution met P4.6E3 taskcoverage. CP11 vereist requested/required relevante units met renderbare claims. CP12 detecteert machinepayloads en begrenst bytes, regels en bullets. De volledige intent/action/endpoint/status/requirement/adapter/presenter/testmatrix staat hieronder.

| Intent/task | Planner action | Endpoint | Statuscontract | Requirement | Adapter | Presenter | Belangrijkste tests |
| --- | --- | --- | --- | --- | --- | --- | --- |
| product_lookup/product_fit/article_lookup | product_assistant | POST `/product/assistant/ask` | `ok` SUCCESS | PRODUCT_RECORD/ARTICLE/PRICE_STOCK per catalog | product knowledge, price-stock, article plus late product aliases | legacy product + CP11 | p4_5_product_evidence, phase_c adapters/catalog, product goldens |
| inspection_latest/inspection_observation | analysis_assistant | POST `/analysis/assistant/ask` | missing/resolved SUCCESS; explicit negative states | resolved asset, latest event/measurement | resultaat/latest adapters plus CP3 alias | legacy inspection, CP11, CP3C/CP4F | inspection_latest phase-C/presentation, user_answer |
| inspection_trend/performance_history | analysis_assistant | POST `/analysis/assistant/ask` | analysis map | lifecycle measurement/event | lifecycle plus late lifecycle aliases | legacy trend + CP11 | inspection_trend phase-C/presentation |
| maintenance_priority | analysis_assistant | POST `/analysis/assistant/ask` | analysis map | measurement/status/forecast/asset | maintenance-priority adapter | legacy maintenance, CP11, CP4B/CP4F | maintenance_priority phase-C, P4.14c |
| replacement_advice | analysis_assistant | POST `/analysis/assistant/ask` | analysis map | replacement history/current measurement/forecast | replacement adapter plus aliases | legacy replacement + CP11 | replacement_advice phase-C |
| technical_lookup/theory_guidance | technical_assistant | POST `/technical/assistant/ask` | ok SUCCESS, redirect REDIRECT | TECHNICAL_RECORD | technical structured plus selection bridge | legacy technical + CP11 | task research/grounded synthesis, regression goldens |
| person_role_lookup | org_assistant | POST `/org/assistant/ask` | unknown/delegated | CURRENT_PERSON_ROLE | ORG adapter | legacy ORG + CP11 | phase_c adapters/catalog |
| rfq_status/readiness | rfq_assistant | POST `/rfq/assistant/ask` | error ERROR, overige UNKNOWN | RFQ_STATUS | RFQ adapter | legacy RFQ + CP11 | phase_c catalog, routing goldens |
| diagnostics_health | diagnostics_assistant | POST `/diagnostics/assistant/ask` | dynamic UNKNOWN | DIAGNOSTIC_FINDING | diagnostics adapter | legacy diagnostics + CP11 | diagnostics routing, phase_c catalog |
| maintenance_position_list (gewenst, nog niet actief) | geen | geen; gewenste GET `/analysis/maintenance/positions` | niet geregistreerd | geen hard end-to-end contract | geen dedicated row adapter | geen dedicated listprojector | `gsl_3mm_known_gap`, benodigde characterization |

## Endpointinventaris en capabilitywaarde

`api/app/main.py` includeert `analysis_api_v10`, products, rag, technical, RFQ, diagnostics, ORG en hybrid. Analysis v5-v9 worden niet geïncludeerd. De machineleesbare inventaris staat in `endpoint-inventory.json`.

De hoogste informatiewinst met het laagste risico komt van bestaande GET-routes met bounded parameters en duidelijke rowsets:

1. `/analysis/maintenance/positions`: sluit direct aan op onderhoudslijsten, leest `vw_mes_maintenance_positions_latest`, ondersteunt lijn/band/limit en retourneert `resultaat`.
2. `/analysis/mes/latest`: actuele toestand; voorkomt misbruik van lifecycle als current state.
3. `/analysis/mes/lifecycle`: historische context, afzonderlijk houden van current state.
4. `/analysis/mes/forecast-3mm`: alleen gebruiken wanneer voldoende meetpunten en typed status dit toelaten.
5. `/analysis/replacement/advice`: bruikbaar nadat bron- en eventrequirements hard zijn.
6. Product family/config GETs en `/technical/context`: informatief en read-only, maar de bestaande assistantwrappers leveren al veel dekking.
7. ORG/diagnostics/RFQ-read GETs: pas later, wegens zwakkere statuscontracten en grotere datascope.

De veilige stage-splitvolgorde is: capabilitycatalog als data-only shadow; plannerselectie shadow; typed GET-transport achter default-off canary; row-normalisatie shadow; CP10 characterization; CP11 projector; compact listbounds; pas daarna conditionele authority. De GSL/DE3-parserfix, statusactivatie en capability-implementatie horen niet in dezelfde refactorcommit.

## Cleanupinventaris

`cleanup-candidates.json` bevat ieder aangetroffen backup/oud-bestand, oude analysis-router, parsefout, dubbel top-level symbool en Docker-contextprobleem. Geen item is verwijderd.

Na verificatie waarschijnlijk veilig te verwijderen zijn timestamped `.bak`-snapshots, `main.oud`, `ai-plugin.old2`, `backupopenapi-gpt.txt`, `inspecties.old2` en de backup-template. Voorwaarden: geen import/stringreference, geen deployment-volume of handmatig herstelproces dat erop leunt, en een schone Docker build plus gelijk failure-set.

`analysis_api_v5`, v7, v8 en v9 zijn niet geïncludeerde historische routers en kunnen eerst in quarantine. v6 bevat een syntaxfout en is aantoonbaar niet importeerbaar; retain/quarantine totdat is bevestigd dat geen script of externe loader hem gebruikt. `service.py`, `evidence_adapters.py`, `evidence_requirement_catalog.py`, `task_evidence.py` en `rfq_api.py` bevatten overschreven namen die niet veilig los te verwijderen zijn: late wrappers bewaren references naar eerdere definities of FastAPI-decorators kunnen eerdere function objects al geregistreerd hebben.

De Docker testcontext is de hele map `api` omdat `.dockerignore` effectief leeg/afwezig is. Daardoor gaan backups, oude routers, templates en overige niet-testbestanden mee in de buildcontext. Verklein de context pas na een afzonderlijke build-context characterization; wijzig Dockerfiles en cleanup niet tegelijk met de stage-split.

## Vergelijking met de drie analyses

| Bronbevinding | Status in huidige code | Bewijs |
| --- | --- | --- |
| `service.py` is de grootste risicoknoop | Nog actueel | 9.569 regels; pipeline, presentatie en repairs in één module |
| Legacy MV1-repairs zitten in public path | Nog actueel | CP3C, CP4B, CP4F en response-shaping repair |
| Shadow/canary en beperkte authority zijn moeilijk te onderscheiden | Deels opgelost | Contractvelden en CP9-CP15 bestaan, maar flags/wrappers blijven verspreid |
| Execution acceptance is breed fail-open | Nog actueel | legacy `_is_accepted`; typed acceptance compatibilitybreed |
| RFQ/statuscontract ongelijk | Nog actueel | RFQ overige status UNKNOWN; ORG/diagnostics dynamisch |
| CP12 kan inhoud verliezen | Nog actueel | machine/size guards en safe fallback; bovendien dubbele compact-call |
| CP11 hangt van claimrendering af | Nog actueel | structured payload zonder renderbare velden wordt niet gepresenteerd |
| Entity grounding is shadow-only | Nog actueel | `band_candidate_shadow` muteert plan niet; GSL/DE3 gap blijft rood |
| Queryclassificatie is smal | Deels opgelost | system-meta/diagnostics verbeterd, auditvragen blijven ambigu |
| Presentatiebeleid is verspreid | Nog actueel | `_build_user_answer`, CP11, CP12 en vier repairs |
| Iedere intent heeft requirements nodig | Deels opgelost | catalog uitgebreid en laat uitgelijnd; exacte catalogtests zijn baseline-rood |
| Release/runtime discipline | Deels opgelost | runbook en scripts bestaan; actieve runtime kan nog een andere checkout/image zijn |
| GSL rond 3 mm moet maintenance positions gebruiken | Nog niet opgelost | fixture verwacht capability; huidige plan clarificeert op false DE3 en voert niets uit |

## Tests en baseline-rood

Source-shape-tests lezen AST/tekst en bewaken imports, unieke definities of callorder. Voorbeeld: `test_phase_c8_evidence_pipeline_integration` vereist precies één `run_orchestrator` en levert vijf baseline-errors juist omdat er vier zijn. Behavior-tests voeren functies/routes met synthetische senders en fixtures uit. Beide zijn nodig: source-shape vangt wrapper/volgordedrift, behavior vangt semantische regressie.

De 61 baseline-items bestrijken forecast DB-contract, inspection/maintenance/replacement adapters en presenters, P4.14c composition, asset resolution, CP0 snapshots/known gaps, retention, user answer, product evidence, registry, ORG evidence, requirementcatalog en de vijf unieke-runner errors. Ze zijn geen toestemming om nieuwe failures toe te voegen.

### Minimale characterization vóór opdracht 3

1. Een import-bindingtest die bewijst dat public `run_orchestrator` exact `CP4F(CP4B(CP3C(core)))` uitvoert en iedere wrapper éénmaal aanroept.
2. Een answer-mutationmatrix voor legacy presenter, researchoverride, CP9 restore, CP10 restore, CP11 replace, CP12 bound, CP3C, CP4B, CP4F en compact-boundary repair.
3. Een post-CP12 invarianttest die per repair vastlegt welke CP-status nodig is, plus een expliciete baseline voor de huidige bypass.
4. Compact/debug end-to-end golden tests voor single MV1 latest, multi-intent MV1 maintenance, product+CEMA, RFQ-missing en diagnostics.
5. Failure-injectiontests voor iedere brede `except`: observer/canary fail-open, CP11 fail-closed, CP12 safe fallback, logging fail-open en transport error-result.
6. Registry/planner consistencytest voor action, endpoint, method, required/accepted/planner/research fields en semantic statusmap.
7. Evidence-wrapper ordertest voor de tien adapterdefinities en de late requirement/task-evidence wrappers; vergelijk evidence-id/aliasset en publieke claims vóór/na extractie.

Aanvullend vóór capabilityactivatie, maar niet vereist voor een puur mechanische eerste extractie: GSL/DE3 query-shape characterization, maintenance `resultaat` rowcontract, authoritative zero rows, thresholdprojectie en een detail-list compact-bound test.

## Beslisadvies voor opdracht 3

Start opdracht 3 alleen als een beperkte, gedragloze extractie met één stage per wijziging. Begin met observabilityhelpers en pure serialisatiehelpers; verplaats daarna planner/execution orchestration; laat `_build_user_answer`, CP9-CP12 en alle post-authority repairs aanvankelijk op hun plaats. Maak geen capability-, GSL/DE3-, typed-status- of cleanupwijziging in dezelfde reeks. Na iedere extractie: source-shape characterization, behaviorgoldens, Docker failure-set vergelijking en controle dat de wrapperketen en compacte boundary identiek blijven.

3K2 extraheert uitsluitend de CP13-call en zijn bestaande fail-closed fallback
naar `cp13_research_semantics_stage.py`. De core geeft de service-local callable
runtime door en bindt het ene resultaatveld vóór de ongewijzigde P4.6D2-call;
P4.6D2 en alle latere authority-, evidence- en presentatiepaden blijven in
`service.py`.

3L2 extraheert uitsluitend de service-owned P4.6D2-aanroep, de verse interne
observationslijst en de bestaande `Exception`-fail-open naar
`p4_6d2_research_execution_stage.py`. De core geeft de service-local D2-callable
per aanroep runtime door en bindt authority plus observations vóór de
ongewijzigde P4.6E1-zone. De interne D2-executor, P4.6E1 en alle latere paden
blijven op hun bestaande plaats.

3M2 extraheert uitsluitend de service-owned P4.6E1-aanroep, de verse interne
evidence-unitslijst en de bestaande `Exception`-fail-open naar
`p4_6e1_research_evidence_stage.py`. De core geeft de service-local E1-callable
per aanroep runtime door en bindt authority plus units vóór de ongewijzigde
P4.6E2-call. De E1-builder, P4.6E2 en alle latere paden blijven op hun bestaande
plaats.

3O2 verplaatst uitsluitend de service-owned P4.6E3 synthesis-coverage
invocation naar `p4_6e3_synthesis_coverage_stage.py`; tuplecoercie en de
`Exception`-fail-open blijven samen, terwijl de opvolgende V8-canary volledig
in `service.py` blijft.

3P2 extraheert uitsluitend de service-owned V8 candidate research execution
canary-aanroep naar `v8_research_execution_canary_stage.py`. De drie verse
shadowlijsten, conversies, observers en gezamenlijke `Exception`-fail-open
blijven één mechanische zone; de interne V8-helper blijft in `service.py` en
wordt per core-aanroep runtime doorgegeven. De opvolgende initial assessment
en alle authority-, reconciliation-, synthesis- en responsepaden blijven in
`service.py`.

3Q2 extraheert uitsluitend de initiële Phase-C evidence-assessment, de
research-decision en de CP13 legacy-gate naar
`phase_c_assessment_gate_stage.py`. De stage laat successobjecten ongeconverteerd,
voegt geen exceptionafhandeling toe en ontvangt alle vier service-callables per
core-aanroep runtime-resolved. Bounded research, inclusief observability,
`list(results)` en sender, en alle latere Phase-C-paden blijven in `service.py`.

3R2 extraheert uitsluitend de service-owned bounded Phase-C research-aanroep
en de direct opvolgende agent-metricsverwerking naar
`phase_c_bounded_research_stage.py`. De stage behoudt de verse `list(results)`,
objectidentiteit, `+=`/`=`-mutaties en exceptionpropagatie en ontvangt alle vier
service-callables per core-aanroep runtime-resolved. Reconciliation en alle
latere Phase-C-paden blijven in `service.py`.

3S2 extraheert uitsluitend de service-owned reconciliation-aanroep en de direct
opvolgende reconciled-evidence-metric naar
`phase_c_reconciliation_stage.py`. De stage behoudt de ongeconverteerde
reconciliation-identiteit, het exacte observabilitylabel en de list/tuple-only
countvervanging en ontvangt de reconcile- en observability-callables per
core-aanroep runtime-resolved. Synthesis en de outer Phase-C-fail-open blijven
in `service.py`.

3T2 extraheert uitsluitend de service-owned grounded-synthesisaanroep naar
`phase_c_synthesis_stage.py`. De stage behoudt het ongeconverteerde
synthesisobject, het exacte observabilitylabel, timingmutaties en volledige
exceptionpropagatie en ontvangt de synthesizer en observability-callable per
core-aanroep runtime-resolved. Pipeline-assembly en de outer Phase-C-fail-open
blijven in `service.py`.

3U2 extraheert uitsluitend de Phase-C evidence-pipeline-assembly naar
`phase_c_evidence_pipeline_stage.py`. De leaf stage bouwt de gewone geordende
25-key mapping, leest `requirement_set.requirement_set_id` eenmaal en roept de
runtime-resolved serializer eenmaal aan. Het ruwe serializerresultaat blijft
object-identiek; de bestaande outer Phase-C `Exception`-fail-open en alle
latere specialist-, legacy-, compositie- en responsepaden blijven in
`service.py`.

3V2 extraheert uitsluitend de clarification- en statusselectie direct na de
outer Phase-C `except` naar `post_phase_c_status_stage.py`. De frozen result
bevat alleen `status` en `clarification`; de stage ontvangt `plan`, `results`,
`typed_execution_results` en de service-local accepted-executionhelper runtime.
De researchdefault en volledige bounded-researchgate blijven in `service.py`.

3W2 extraheert uitsluitend de direct opvolgende bounded-research-v1-default,
gate, agent/legacykeuze, `plan_research`-observability en counteraggregatie naar
`phase_c_bounded_research_v1_stage.py`. De frozen result bevat in volgorde alleen
`research` en `plan_research_agent`; alle vijf service-callables worden per
core-aanroep runtime-resolved doorgegeven. `_build_user_answer`, presentatie en
alle responsemutaties blijven ongewijzigd in `service.py`.

3X2 extraheert uitsluitend de legacy antwoordselectie en mojibakepresentatie
naar `answer_presentation_stage.py`. De frozen result bevat alleen `answer`.
`results`, een lazy accessor voor `plan.requested_information`, `research` en
`timings` gaan expliciet naar de stage; clock, answerbuilder, repair en elapsed
worden per core-aanroep runtime-resolved doorgegeven. De accessor bewaart de
3X1-volgorde: de clock loopt vóór de `try`, terwijl de property pas binnen de
`try` als builder-keyword wordt gelezen. Composition, evidence-mutaties,
responsebouw en wrappers blijven in `service.py`.
