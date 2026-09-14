# 3D2 initial execution extraction build report

- Start/HEAD: `312702d76b625f1c5d7d3cc27c75ee6b65e28f07`; required ancestor check passed.
- Baseline: `post-change-57fe45e.json` (803 passed, 56 failed, 5 errors, 17 skipped; 61 failure/error names).
- Final gate: `final-3d2-20260914T061126Z.json` (901 passed, 56 failed, 5 errors, 18 skipped; 61 unchanged names, 0 new, 0 resolved).
- XPASS: none observed (`pytest` progress contained no `X`).
- 3D1: unchanged; 9/9 passed before and after extraction.
- Final direct boundary/stage/wrapper gate: 25 passed.
- Privacy policy gate: 8 passed.
- Candidate tag: `promati-api:3d2-candidate-312702d-20260914`.
- Candidate image ID: `sha256:6d08ce092191a79af9d28c0edb212203c7345ac44fec5afe2d170cc39b07740c`.
- Candidate checks: service/stage import and callable core passed with synthetic required settings; no tests, `.pyc`, `.pyo`, or `__pycache__` present.
- Active API before/after: container `ea5a9896a2336741fc30f7823e3ab92902dea663dd2d1e6ddf492fb69face019`, image `sha256:e72699df1ff3f115090a27642bff45d0c9039f3ef4cb1e92696e02c7f73c13ba`; unchanged and not replaced.
- Static checks: `git diff --check`, AST parsing, minimal-import/source-shape tests and candidate circular-import/import check passed.
- Privacy: this report contains only revisions, test counts/nameset deltas and image/container identifiers; no questions, answers, tokens, entities, scopes, payloads or secrets.
