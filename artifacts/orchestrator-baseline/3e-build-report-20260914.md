# Opdracht 3E — build- en verificatierapport

- Startcommit: `eb871810a904ca45a4fe4b55bb492ee145330a38` (exact tip van
  `feature/monteur-flow`; worktree detached).
- Vereiste ancestor: `b6bb1b93cd4613efb096193cf0afe67882a3a0de` is ancestor van
  HEAD.
- Extractie: het bestaande blok voor `trace.attempts`,
  `execution_attempts`, `initial_specialist_calls` en
  `initial_raw_result_rows` is zonder gedragswijziging verplaatst naar
  `_record_initial_execution_observability(counts, trace, results)` in de
  observability-leaf. De service roept hetzelfde geïmporteerde function object
  exact eenmaal aan na alle negen 3D2-bindings en vóór `evidence_pipeline`.
- Regelreductie service: 31 regels verwijderd en 4 toegevoegd; netto 27 regels
  minder.
- Gerichte gate: 112 passed, 3 warnings. Selectie omvat 3A–3D2,
  orchestrator-observability/run-logging, wrapper/post-CP12/evidence en
  CP8/CP9/C8.
- Pre-gate: 901 passed, 56 failed, 5 errors, 18 skipped; gate exit 0.
- Post-gate: 909 passed, 56 failed, 5 errors, 18 skipped; gate exit 0.
- Baselinevergelijking tegen `post-change-57fe45e.json`: 61 ongewijzigde
  failure/error-namen, 0 nieuwe, 0 opgeloste en geen onverwachte XPASS.
- AST/diff/import: beide gewijzigde productiemodules parsen; `diff --check` is
  schoon; observability-stage blijft een leaf met alleen `__future__` en
  `typing`; helperidentiteit en facade-import zijn gecontroleerd; wrapperketen
  `CP4F -> CP4B -> CP3C -> core` is groen.
- Candidate: `promati-api-3e-candidate:20260914-0642`, image-ID
  `sha256:a77535028883efac3b6808a3eefc423eef35d18e93b8a674558ed4014eca2093`.
  Geen `/app/tests`, `.pyc` of `__pycache__` in de image vóór runtime-import.
- Actieve container vóór/na: ID
  `def8e0c72d29821aa363885d279f6299b7f31f1c85362ad1759f78f2014efc03`,
  image `sha256:1b4c8b31cb84b008dce82f18d544e98bd8108aa0740b00247cf206269eded9b5`;
  niet vervangen of herstart.
- Risico: beperkt tot import/call-indirection; bestaande `len(results)`- en
  attribute-accessexceptions blijven doorgegeven. Rollback is het terugzetten
  van de zeven bron/test/docwijzigingen en het verwijderen van de drie nieuwe
  privacy-safe rapportbestanden; er is geen runtime-rollback nodig.
- Er is niet gecommit, gepusht of gemerged.
