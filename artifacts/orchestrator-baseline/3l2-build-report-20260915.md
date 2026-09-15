# Opdracht 3L2 — build- en verificatierapport

- Startcommit: `bb57cd95b68ddd3efb2ace6e1510ec23c5cbb053`, detached worktree;
  lokale `feature/monteur-flow` bevat dezelfde HEAD. Vereiste 3L1-commit
  `140ec4ffbb6aa4a6da5a793526b453d25b579a9a` is ancestor.
- Extractie: uitsluitend de service-owned P4.6D2-aanroep, verse observationslijst
  en bestaande `Exception`-fail-open zijn verplaatst naar
  `p4_6d2_research_execution_stage.py`. P4.6E1 blijft in `service.py`.
- Servicewijziging: oude D2-zone regels 7231-7253; nieuwe stagecall/bindings regels
  7234-7258 en ongewijzigde E1-marker op 7260. Netto 5 regels erbij (24/19).
- Gerichte gates: 76 passed voor 3L2 + beide 3L1-bestanden + CP14; 283 passed
  voor aangrenzende 3H-3K, eerdere stages, wrappers, post-CP12 en adapters.
- Canonieke copied-api gate: pre 1165 passed, 56 failed, 5 errors, 18 skipped;
  post 1189 passed, 56 failed, 5 errors, 18 skipped. Alle 61 gerapporteerde
  failure/errornamen zijn identiek, ook versus `post-change-57fe45e.json`.
- Volledige checkout read-only, netwerkloze gate: pre 1061 passed en post 1085
  passed; beide 50 failed, 5 errors, 13 skipped en 5 xfailed. Dit zijn 55 actuele
  failure/errornamen. De zes retentiontests zijn historisch resolved. De zeven
  strict-XPASS-namen zijn reeds bestaande CP0-namen; geen nieuwe XPASS.
- Characterization-hashes bleven byte-identiek:
  boundary `83FA2964633A8E164522972440C87446275D7B01F7FCD305DF5273FA543CFBDD`;
  executor `938F2C4A8F1F6AE965CFFC714744F2E1582C74A4B8C8367ADDE4A3DEACCBB76C`.
  Interne executorhash bleef
  `26938B9B30E5B4FFB8C663EA40DA4398D1B0ED51674A8F0E443F755EB64791F0`.
- Candidate: `ai-platform-api:3l2-candidate-bb57cd95`, image-ID
  `sha256:23f480d93c397da950ff58e16e487d445038d307a68b07daddd2fd85ccd0e790`.
  Imports en callable facade zijn groen met synthetische settings. Geen tests,
  `.pyc`, `.pyo` of `__pycache__` zijn in de image aangetroffen.
- Actieve API voor/na: container-ID
  `33d4d39da08dedd2368ec93bc1f3f2592d05e393e128f47d0d24f1b4de911b72`,
  image `sha256:f14a1ea8122e1cb6fbb8ee9aac138940ac236a0fd00a5fbbec812f81d2042e80`,
  gestart `2026-09-15T06:04:14.359641734Z`; niet vervangen of herstart.
- Privacy: rapporten bevatten geen vragen, antwoorden, tokens, entiteiten,
  scopes of payloads. Tijdelijke snapshots en containers zijn verwijderd.
- Niet gecommit, gepusht of gemerged; geen live-smokes uitgevoerd.
