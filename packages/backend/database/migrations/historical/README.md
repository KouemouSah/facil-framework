# Historical Migrations Archive

This directory holds the **319 incremental migrations 010 → 336** that
were applied to the TaxasGE staging and production databases between
2025-11 and 2026-05-09.

## Why are they here and not in the parent `migrations/`?

All these migrations are **already applied** to staging and production.
Capturing them in the consolidated baseline (`database/baseline/000_baseline_2026_05_09.sql`)
made it unnecessary to keep them in the active migrations path:

  - The baseline reproduces the exact final schema in a single fast file.
  - For fresh DBs, `init_database.py` applies the baseline + seeds, then
    marks every historical migration as "applied via baseline" in
    `schema_migrations` (no replay).
  - For existing DBs (staging, prod), the legacy
    `deploy-backend-staging.yml` workflow uses
    `glob('*.sql')` (non-recursive) on the parent `migrations/`
    directory, which now returns zero files — a safe no-op since these
    migrations are already in the DB.

## Are these still needed?

For the running TaxasGE staging and production: **no functional need**
to replay them. They live here for:

  - **Audit / git history**: `git log` and `git blame` on any specific
    migration still work, useful when investigating an old schema decision.
  - **Disaster recovery**: if for some reason the baseline is lost or
    suspect, these incremental files can rebuild the schema by replaying
    them in order.
  - **Education**: future maintainers can read the chronology of how the
    schema evolved.

## When to add a new migration

**Do NOT add new migrations here.** Add them in the parent
`packages/backend/database/migrations/` directory (e.g. `337_my_change.sql`,
`338_another.sql`). Those will be picked up by both:

  - `deploy-backend-staging.yml` (legacy workflow) → applied to staging
    on the next push to `develop`.
  - `init_database.py` → applied on the next fresh-DB run after the
    baseline.

## When (if ever) to consolidate

A future periodic consolidation (e.g. annually):

  1. Generate a new baseline: `extract_full_schema.py`
  2. Move the migrations applied since the last baseline into this
     archive directory.
  3. Update `database/baseline/` symlink or filename.

This is **not** required for the system to keep working — it's purely a
hygiene step to avoid the historical pile growing unboundedly.

## Per-file status

Total: **319 SQL files** (315 numbered 010-336 + 4 legacy un-numbered).
See git log for per-file authorship and intent.
