# Opdracht 3M2 — build- en verificatierapport

- Start-HEAD: `5c9814cc8df22f67390301dba2a4f974dac8ee2b`, detached checkout;
  vereiste 3M1-commit `d7004b69ddb0221c500575ce45c78af86ac89fe7` is ancestor.
- Extractie: uitsluitend de service-owned P4.6E1-aanroep, verse unitslijst en
  bestaande `Exception`-fail-open zijn verplaatst naar
  `p4_6e1_research_evidence_stage.py`. P4.6E2 blijft in `service.py`.
- Servicewijziging: oude E1-zone regels 7263-7280; nieuwe stagecall en bindings
  regels 7266-7288. De gehele servicewijziging is 22 toevoegingen en 17
  verwijderingen; de nieuwe leaf-stage heeft 42 regels.
- Directe gate: 73 passed voor de twee nieuwe 3M2-testmodules, beide 3M1-files
  en CP14. Aangrenzende gate: 296 passed en alleen de drie reeds bestaande ORG
  evidence-adapterfails.
- Canonieke copied-api gate: pre 1231 passed; post 1255 passed. Beide hebben 56
  failures, 5 errors en 18 skipped. Alle 61 failure/errornamen zijn identiek:
  0 nieuw, 0 opgelost.
- Volledige checkout netwerkloos/read-only gemount: post 1151 passed, 50
  failures, 5 errors, 13 skipped en 5 xfailed. Dit zijn de verwachte 55 actuele
  failure/errornamen; de zes retentionnamen uit de copied/historische set zijn
  apart gehouden. Er was geen XPASS.
- Beide 3M1-hashes bleven byte-identiek: boundary
  `11211E2A5728B1C6CFE8495BAAAD4908F069F81C3E4A19893E59CC269AC26EE1`;
  directe E1-characterization
  `A9FA1101E5DDFB90E494F9E8B02145211C22F791DF70CCE0938943F9B6E0FFD5`.
  CP14 bleef `2EC6FC40144D404A830B19AAF6DE47A9272505261763E1E5FE18064B4F7A626D`;
  `task_research_evidence.py` bleef
  `210129396475E6B0ACB832E9680B7F7E76797408CACFE649698D4364F8219F6A`.
- AST/imports: syntaxis groen, leaf-imports uitsluitend `dataclasses` en
  `typing`, exact één service-stagecallsite, productie-imports en callable
  facade groen met synthetische settings; wrapperketen CP4F -> CP4B -> CP3C ->
  core groen.
- Candidate: `promati-api:3m2-candidate`, image-ID
  `sha256:a5143d9cbf0c6a88f4cca547f9362ae260a3228adfdade3da2767cee4cc48639`.
  Geen tests, `.pyc`, `.pyo` of testcontainers aangetroffen.
- Actieve API voor/na: container-ID
  `16753297d0345ddb577d367120c3f14aef4a0cf8ffe85c730b8ae2058eba1b6f`,
  image `sha256:4a8f00745d1ee97ab5f7d8a2b2f80bfc191f156cc7f306358bb48106c350e252`,
  gestart `2026-09-15T06:50:53.30285717Z`; niet vervangen of herstart.
- Privacy: rapporten bevatten geen vragen, antwoorden, tokens, entiteiten,
  scopes, payloads of secrets. Geen live-smokes uitgevoerd.
- Niet gecommit, gepusht of gemerged.
