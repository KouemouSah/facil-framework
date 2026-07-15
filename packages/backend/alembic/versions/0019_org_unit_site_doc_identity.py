"""org_unit/site.document_identity — optional value-inheritance overrides.

Additive migration (spec §6 discipline — same shape as 0018): a single JSONB
column per table, NOT NULL, defaulted to `{}` so every existing row is valid
immediately, no backfill needed. Carries ONLY the narrow, optional override
set declared in `product_schemas.DOCUMENT_IDENTITY_OVERRIDE` (SP1 debt D1) —
`legal_name`/`short_code`/`logo_url`/`contact_line`/`footer_note` — resolved
against the parent `OrgUnit`/`Organization` chain by
`core.schema.issuer.resolve_issuer_identity`, never read raw.

`organization.document_identity` already exists (0003_org_location) and needs
no change here: SP1 debt D1 only adds the CHILD-entity override columns.

Revision ID: 0019_org_unit_site_doc_identity
Revises: 0018_field_definition
Create Date: 2026-07-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# NOTE: kept to <=32 chars — `alembic_version.version_num` is `varchar(32)`
# (see every other revision id in this directory); the original, more
# descriptive id overflowed it and 500'd `alembic upgrade` against real
# Postgres (SQLite silently truncates instead, so this only surfaces there).
revision = "0019_org_unit_site_doc_identity"
down_revision = "0018_field_definition"
branch_labels = None
depends_on = None

_JSON = sa.JSON().with_variant(
    sa.dialects.postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    for table in ("org_unit", "site"):
        op.add_column(table, sa.Column("document_identity", _JSON, nullable=False,
                                        server_default="{}"))


def downgrade() -> None:
    for table in ("org_unit", "site"):
        op.drop_column(table, "document_identity")
