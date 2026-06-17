"""keyset composite indexes (col, id) — scale 1M+ (P2)

Backs the keyset/cursor pagination added in `app.api.list_query.keyset_page`
(P1). Each list orders by `(sort_col, id)` and filters by the same tuple, so a
btree on exactly `(sort_col, id)` lets Postgres walk the index in order with no
residual sort step. The `id` tiebreaker MUST be inside the index — without it
every page would re-sort.

Indexed = the **default sort** of each admin list (see list_query whitelists):
  - account: `-created_at` -> (created_at, id)
  - organization / role / site: `code` -> (code, id)
Non-default sort columns (legal_name, name, email, display_name, status,
site_type) stay un-indexed: those lists fall back to a sort, an accepted cost
(the 1M+ concern is the *default* view). Add more composites later if a
secondary sort proves hot.

Plain btree indexes are **portable** (Postgres + SQLite, unlike the pg_trgm GIN
of 0012) — no dialect guard needed.

NOTE (production): `op.create_index` issues a plain `CREATE INDEX`, which takes a
write lock for the build. That is free here (pre-launch: empty/small tables). If
one of these is ever (re)built on an already-large live table, build it
out-of-band with `CREATE INDEX CONCURRENTLY` instead (cannot run inside Alembic's
transaction, Postgres-only).

Revision ID: 0014_keyset_composite_indexes
Revises: 0013_saved_view
Create Date: 2026-06-17
"""
from alembic import op

revision = "0014_keyset_composite_indexes"
down_revision = "0013_saved_view"
branch_labels = None
depends_on = None

# (index name, table, [columns]) — keyset (sort_col, id) for each default sort.
_INDEXES = (
    ("ix_account_created_at_id", "account", ["created_at", "id"]),
    ("ix_organization_code_id", "organization", ["code", "id"]),
    ("ix_role_code_id", "role", ["code", "id"]),
    ("ix_site_code_id", "site", ["code", "id"]),
)


def upgrade() -> None:
    for name, table, cols in _INDEXES:
        op.create_index(name, table, cols)


def downgrade() -> None:
    for name, table, _cols in _INDEXES:
        op.drop_index(name, table_name=table)
