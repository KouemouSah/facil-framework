"""account search trigram indexes (P1 — scale)

Accelerates the admin account search (`ILIKE '%q%'` on email / account_number /
display_name), whose leading wildcard cannot use a btree index → full scan at
millions of rows. pg_trgm GIN indexes make substring search index-backed.

PostgreSQL-only: guarded by the dialect so SQLite (tests / dev) is a no-op (it
has no pg_trgm; LIKE there just scans, which is fine at test scale).

Revision ID: 0012_account_search_trgm
Revises: 0011_federated_identity
Create Date: 2026-06-17
"""
from alembic import op

revision = "0012_account_search_trgm"
down_revision = "0011_federated_identity"
branch_labels = None
depends_on = None

_INDEXES = (
    ("ix_account_email_trgm", "email"),
    ("ix_account_number_trgm", "account_number"),
    ("ix_account_display_name_trgm", "display_name"),
)


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return  # pg_trgm is Postgres-only; nothing to do elsewhere
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    for name, col in _INDEXES:
        op.execute(
            f"CREATE INDEX IF NOT EXISTS {name} ON account "
            f"USING gin ({col} gin_trgm_ops)")


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for name, _ in _INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {name}")
