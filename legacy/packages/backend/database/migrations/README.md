# Database Migrations — TaxasGE Backend

> **Last update**: 2026-05-10 — Phase H test (move 319 historical migrations
> to `historical/` subdirectory, see commit history).

This directory contains the **active migrations** path (anything new goes
here) plus a `historical/` subdirectory holding the 319 already-applied
migrations from 010 → 336.

## Layout

```
migrations/
├── README.md                      # this file
├── historical/                    # 319 migrations 010-336 (already applied)
│   ├── README.md
│   ├── 010_*.sql ... 336_*.sql
│   └── (4 unnumbered legacy SQLs)
├── 040_secrets_to_configure.md    # documentation note (legacy companion)
├── 189_encrypt_totp_secrets.py    # one-off helper script (legacy)
└── 337_my_next_migration.sql      # → put any new migration here
```

The non-recursive `glob('*.sql')` used by `deploy-backend-staging.yml`
and `init_database.py` only scans the **root** of `migrations/` — the
historical/ subdirectory is intentionally invisible to them. This is the
mechanism that lets us keep the 319 historical migrations in git for
audit while skipping their replay (already applied in staging + captured
in `database/baseline/000_baseline_2026_05_09.sql`).

The migration system is in transition between two patterns. Both work
side-by-side until Phase G validation completes.

---

## Two patterns coexist (transition period)

### Pattern 1 — Legacy "replay-all" (still active in `deploy-backend-staging.yml`)

The historical workflow reads every `*.sql` file in this directory at each
deploy and re-applies them, swallowing `'already exists'`/`'duplicate'`
errors silently.

- **Pros**: simple, no tracking infrastructure required.
- **Cons**: slow (322+ statements parsed per deploy), no auditability, no
  checksum, no concurrency control, DML migrations re-execute side effects.

This pattern remains the **default** for the staging deploy until Phase G
validates Pattern 2.

### Pattern 2 — `init_database.py` orchestrator (Phase A)

A new script `packages/backend/scripts/deploy/init_database.py` introduces
a tracking table (`schema_migrations`), SHA-256 checksums, and a Postgres
`pg_advisory_lock` — see the script's docstring for full details.

Triggered manually via the `DB Migrate (Auto Mode)` workflow
(`.github/workflows/db-migrate-auto.yml`):

1. GitHub UI → **Actions** → "DB Migrate (Auto Mode)" → **Run workflow**
2. Choose mode (`hybrid` recommended — see below) and target (staging only
   for now)
3. Inspect the workflow logs and verify `SELECT COUNT(*) FROM
   schema_migrations` post-run

---

## Modes (init_database.py `--mode=...`)

| Mode             | Use case                                                |
|------------------|---------------------------------------------------------|
| `hybrid`         | Default. Skip applied migrations, fall back to legacy   |
|                  | "already exists" swallow on first apply. Safe rollout.  |
| `auto`           | Same as hybrid in Phase A. In Phase D will detect       |
|                  | empty DB and apply baseline.                            |
| `strict`         | Error on any unexpected SQL exception. No fallback.     |
|                  | Use after Phase G validation.                           |
| `legacy-compat`  | Replay every file, swallow errors everywhere.           |
|                  | Equivalent to the historical workflow. Rollback path.   |
| `migrations-only`| Apply only `database/migrations/`. Skip seeds.          |
| `seeds-only`     | Apply only `database/seeds/` (Phase C target).          |

---

## Naming convention

```
NNN_short_description.sql
```

- `NNN` = three-digit version (zero-padded, lexicographically sortable).
  The next available number is **337**.
- Description = snake_case, max ~60 characters.
- One file = one logical change. Don't bundle unrelated DDL.
- Always idempotent: `CREATE TABLE IF NOT EXISTS`, `DROP CONSTRAINT IF
  EXISTS`, `ON CONFLICT DO NOTHING/UPDATE` for inserts.
- Wrap in `BEGIN; ... COMMIT;` to make the file atomic.

---

## Adding a new migration

```bash
# 1. Find next number — include historical/ in the search
ls database/migrations/ database/migrations/historical/ | grep -E '^[0-9]' | sort | tail -3
# → highest is currently 336

# 2. Create the file IN THE ROOT of migrations/ (NOT in historical/)
NEXT=337
$EDITOR database/migrations/${NEXT}_my_change.sql

# 3. Test locally against a copy of the DB (DO NOT touch staging directly)
psql $DATABASE_URL_LOCAL -f database/migrations/${NEXT}_my_change.sql

# 4. Run the unit tests
cd packages/backend && pytest tests/test_init_database.py -v

# 5. Commit + push to develop
# The legacy deploy-backend-staging.yml will apply it on next deploy.
# Optionally trigger DB Migrate (Auto Mode) to populate schema_migrations.
```

**Do NOT create new files in `historical/`** — that directory is for
already-applied migrations only. New migrations belong in the root of
`migrations/` so the workflows pick them up.

---

## Tables in this directory's scope

The `schema_migrations` table (created by `336_create_schema_migrations.sql`)
tracks which migrations have been applied. See its inline comment for the
full column reference, or run `\d+ schema_migrations` in psql.

---

## Future structure (post Phase D)

```
database/
├── baseline/                      # Phase D target
│   └── 000_baseline_2026_XX_XX.sql
├── migrations/                    # incremental DDL (this directory)
│   ├── 336_create_schema_migrations.sql
│   └── 337+_*.sql
├── seeds/                         # Phase C target — idempotent DML
│   ├── 001_categories.sql
│   ├── 002_roles.sql
│   └── …
└── tools/                         # admin one-shots
    └── looker_studio_url_generator.py
```

---

## References

- Plan: `.claude/plans/MIGRATIONS_BASELINE_REFACTOR_PLAN.md` (local only)
- Orchestrator: `packages/backend/scripts/deploy/init_database.py`
- Workflow auto: `.github/workflows/db-migrate-auto.yml`
- Workflow legacy (untouched): `.github/workflows/deploy-backend-staging.yml`
- Memory: `memory/project_repo_cleanup_2026_05_09.md`
