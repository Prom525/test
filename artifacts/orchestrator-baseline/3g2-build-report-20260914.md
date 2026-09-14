# Opdracht 3G2 — build- en verificatierapport

- Startcommit: `cfb16c0ca8c8bde4d3b5f4f99cc43fe05156073c`, exact
  de tip van `feature/monteur-flow`; de worktree is detached op die commit.
- Vereiste ancestor: `de084fe75db53d7d9ec35534ddc1ae32be8fee06` is
  ancestor van HEAD.
- Extractie: het bestaande blok vanaf de eerste product-family coveragecall
  tot direct vóór task-evidence is verplaatst naar
  `product_family_recovery_stage.py`. De frozen return bevat exact coverage,
  recoverymetadata en working evidence. De service levert alle runtime
  dependencies aan en bindt de drie velden vóór task-evidence.
- Regelreductie service: 86 regels verwijderd en 30 toegevoegd; netto 56
  regels minder. De nieuwe leaf-stage bevat 96 regels.
- 3G1-migratie: alle 35 parametrische low-level cases staan als directe
  stagetests; de service-integratie bevat drie tests voor runtime lookup,
  één stagecall/order/bindings en outer fail-open met partiële countstate.
  De volledige assertiongroepmapping staat in de architectuurkaart.
- Gerichte gate: 189 passed. Selectie omvat 3A–3G2, product-family en
  price/stock, Phase-C8 behavior/hardening, observability, serialization,
  evidence-adapter, wrappers en post-CP12.
- Pre-gate: 978 passed, 56 failed, 5 errors, 18 skipped, waarvan 5 xfailed.
- Finale post-gate: 982 passed, 56 failed, 5 errors, 18 skipped, waarvan 5
  xfailed. Tegen de feitelijke startcommitnameset: 0 nieuwe en 0 opgeloste
  failure/errornamen.
- Legacyvergelijking tegen `post-change-57fe45e.json`: 61 ongewijzigde namen,
  0 nieuwe en 0 opgeloste. De zes retentionnamen en de zeven CP0 strict-XPASS-
  namen staan zowel in legacy, pre als post en zijn dus expliciet geen 3G2-
  regressies of 3G2-resolutions.
- AST/import/circular/privacy: leaf-importoppervlak is alleen `dataclasses` en
  `typing`; service- en stage-import met synthetische settings is groen;
  facade en wrapperketen zijn groen; privacy-safe runner- en buildartifacts
  bevatten geen vragen, antwoorden, tokens, entities, scopes of payloads.
- Candidate: `promati-api:3g2-candidate-cfb16c0-20260914-1320`, image-ID
  `sha256:a92ae963da55b083abd556c3e238a8d6107922c234e19882bf856c5db7429ebd`.
  Geen `/app/tests`, `.pyc`, `.pyo` of `__pycache__` in de image.
- Actieve container vóór/na: ID
  `f734251c700be9751fbed88cdfed103340ae0079aec0b978a7951fda5cb6bf98`,
  image `sha256:98131b91ef25a9626c6d309d26a12e5fb2fa6706ef8894a0a857af56242ee62b`;
  niet vervangen of herstart.
- Risico: beperkt tot de nieuwe import/call-indirection. Alle gekarakteriseerde
  shape-, normalization- en second-coverageexceptions blijven propageren naar
  dezelfde outer Phase-C-fallback. Rollback is het terugzetten van de
  bron/test/docwijzigingen; runtime-rollback is niet nodig.
- Er is niet gecommit, gepusht of gemerged.
