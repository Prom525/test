# Opdracht 3O2 — verificatierapport

- Start: branch `codex/orchestrator-p46e3-coverage-characterization`, HEAD
  `febd56637ddcd1b346dc524d1b9eeee01a252b89`, schoon; de vereiste commit is
  ancestor (en gelijk aan HEAD).
- Extractie: uitsluitend de service-owned P4.6E3 synthesis-coverage invocation,
  inclusief `tuple(working_evidence_items)` en de bestaande `Exception`-fail-open,
  is verplaatst naar `p4_6e3_synthesis_coverage_stage.py`.
- Resultaatcontract: frozen dataclass met exact één veld,
  `task_grounded_synthesis_coverage_authority_p4_6e3`. Succeswaarden blijven
  object-identiek; `Exception` geeft exact `None`; `BaseException` propageert.
- Service: 18 regels toegevoegd en 12 verwijderd (netto +6, inclusief de
  drie-regelige import). Er is exact één stagecall en één resultaatbinding.
  De V8-zone bleef inhoudelijk identiek: SHA-256
  `9EBF5FEFC2088805184A67F264E7EFA903D496881CC46BFFA4BAD02AEBA76278`.
- Gerichte 3O2-gate: 67 passed voor beide ongewijzigde 3O1-modules, beide
  nieuwe 3O2-modules en CP14.
- Brede aangrenzende gate: 491 passed; alleen de drie bekende ORG
  evidence-adapterfails en vijf bekende layout-brosse Phase-C8-errors.
- Canonieke volledige startgate: 1349 passed, 56 failed, 5 errors, 18 skipped,
  inclusief 5 xfailed; geen XPASS.
- Canonieke volledige kandidaatgate: 1362 passed, 56 failed, 5 errors,
  18 skipped, inclusief 5 xfailed; geen XPASS. De 13 extra passes zijn de
  nieuwe tests. Tegen start en `post-change-57fe45e.json`: 0 nieuwe, 0
  opgeloste en 61 ongewijzigde failure/errornamen.
- Ongewijzigde SHA-256-hashes: 3O1 boundary
  `0503ADAED2DA0BE67BAB8AC3F318237A334EA3800C46BB75928A7EE7E5A197F1`;
  3O1 direct
  `8B9368D09AFF9A5FA93B9CF53A7AA6F564F720DEA21061B05B9B91CFA8FA86AE`;
  interne E3-module
  `0D8F8D3D0AA9FB55FC6C1C7F9D977932D95CDE71C4213BC0FA90B25CD06B9EB7`.
  Nieuwe leaf-stage SHA-256:
  `D4C45186A8A45E61779D7FA30E29868F61A8467B5781D3DAC3C9654FB4FE4A7A`.
- Candidate: `promati-api:3o2-candidate`, image-ID
  `sha256:f1ab6b015c0c37623a910f964b017d4e8dde3a83e6b456c4eb329822b3a2d705`.
  Imports, callable facade en wrapperketen zijn groen; tests, `.pyc`, `.pyo`
  en `__pycache__` ontbreken.
- Actieve API vóór/na: container-ID
  `01ec4dc7b24a34574d00e0df26171c798a29f400e7ffba8379c6497fcd7e3fda`,
  image
  `sha256:adc839994e2f38b034f103b21605e059c773fcd851506d00c0995a17cbe894ce`,
  gestart `2026-09-15T11:55:50.608088567Z`; niet herstart of vervangen.
- Resterend risico: de bestaande brede baseline bevat 61 bekende
  failure/errornamen en vijf xfails; de extractie verandert die set niet.
  Mechanische rollback is het verwijderen van de leaf-stage en twee nieuwe
  tests, het terugplaatsen van de oorspronkelijke E3-zone in `service.py` en
  het verwijderen van de twee documentatie-aanvullingen en 3O2-rapporten.
- Privacy: rapporten bevatten geen vragen, antwoorden, tokens, entiteiten,
  scopes, payloads of secrets. Geen live-smokes uitgevoerd.
- Niets gecommit, gepusht, gemerged of geactiveerd.
