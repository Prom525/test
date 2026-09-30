# P3.2b capability-unsupported database migration

## Scope and status

This is a prepared, unexecuted PostgreSQL migration for the existing
`observability.orchestrator_runs.error_category` CHECK constraint. It adds
only `capability_unsupported`, retaining every P3.2 category and the existing
`NULL` semantics. It does not change tables, columns, indexes, triggers,
functions, run records, application code, or API contracts.

The prepared assets are based on repository commit
`06370ae1463cec380c39d76247434f466c7c6ef6`. They are not a claim that
current persistence has been repaired: no database was changed by this work.

## Assets

| File | Purpose |
| --- | --- |
| `api/sql/2026_09_29_p3_2b_error_category_capability_unsupported_check.sql` | Read-only schema and aggregate-count preflight/postflight. |
| `api/sql/2026_09_29_p3_2b_error_category_capability_unsupported_apply.sql` | Transactional, guarded apply. |
| `api/sql/2026_09_29_p3_2b_error_category_capability_unsupported_rollback.sql` | Transactional, guarded fail-closed rollback. |

The apply script accepts only the exact validated P3.2 baseline or the exact
already-installed P3.2b target. The latter is its sole no-op case. Any missing,
renamed, unvalidated, different, or widened constraint is rejected. The
rollback accepts only the exact P3.2b target and is deliberately not a no-op
when the legacy state is already present.

The sole mutable database object is constraint
`observability.ck_orchestrator_runs_error_category` on table
`observability.orchestrator_runs`. Explicitly out of scope are every table
column (including `error_category`), all run-record data, indexes, triggers,
functions, schemas, and other constraints.

## Required operator procedure

Production application requires separate explicit approval. Before that
approval, do not run the apply script against any existing database.

1. Record the target identity and take/verify the organization-approved backup
   before the change window. The backup scope must include schema
   `observability`, the definition and data of
   `observability.orchestrator_runs`, and dependent table metadata (its
   constraints, indexes, triggers, and referenced functions). Retain the backup
   job/snapshot identifier, completion time, and restore-verification evidence.
   This repository does not create or export a backup.
2. With approved secrets supplied only through the operator environment, run
   the read-only check. It may print database/schema metadata, constraint
   metadata, and aggregate category counts only:

   ```powershell
   psql -X -v ON_ERROR_STOP=1 -f api/sql/2026_09_29_p3_2b_error_category_capability_unsupported_check.sql
   ```

   Proceed only if the single metadata row reports `migration_state = BASELINE`.
   Save the privacy-safe output with the change evidence. `DRIFT_OR_MISSING`
   is a stop condition, not an invitation to edit the script or force-install.
3. Run the guarded apply once:

   ```powershell
   psql -X -v ON_ERROR_STOP=1 -f api/sql/2026_09_29_p3_2b_error_category_capability_unsupported_apply.sql
   ```

4. Repeat the read-only check and require `migration_state = TARGET`. Inspect
   the application health and only privacy-safe persistence-error metrics/logs;
   do not generate live business requests merely to test this constraint.

The scripts set a five-second lock timeout and a 15-second statement timeout.
They take `ACCESS EXCLUSIVE` on `observability.orchestrator_runs` while
replacing the CHECK, so they temporarily block reads and writes to that table.
If a lock cannot be obtained or validation cannot finish within those bounds,
the transaction aborts without a partial schema change. Schedule a short,
low-traffic window and monitor blocked sessions before retrying.

## Rollback boundary

The rollback never deletes or rewrites append-only run records. It first proves
the exact P3.2b target and then refuses if even one
`capability_unsupported` record exists. That refusal preserves historical data
and leaves the target constraint untouched.

Consequently, an application rollback to a version that still emits
`capability_unsupported` is not automatically safe with the legacy database
constraint. Before a database rollback, operators need a traffic/application
plan that prevents new values, confirms the guarded count is zero, and accepts
that existing capability records prohibit this rollback until a separately
approved data-retention strategy exists. If those conditions are met, use:

```powershell
psql -X -v ON_ERROR_STOP=1 -f api/sql/2026_09_29_p3_2b_error_category_capability_unsupported_rollback.sql
```

Then rerun the read-only check and require `migration_state = BASELINE`.

## Prepared-asset validation

The three scripts were exercised against a temporary PostgreSQL 16 container
with only synthetic schema and rows. The checks covered P3.2 baseline-to-target
apply, exact-target apply no-op, acceptance of the new value, rollback refusal
with preservation of one synthetic capability record, successful rollback after
that synthetic row was removed, legacy rejection of the new value, and apply
rejection of a deliberately drifted CHECK. No existing database, Compose
service, volume, or application request was changed for that validation.
