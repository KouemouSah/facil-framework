"""field_definition table + custom_fields columns.

Additive migration, run at DEPLOY time — NOT runtime DDL triggered by a user.
That distinction is the whole safety of the design (spec §6): Odoo does
ALTER TABLE at runtime for custom fields, which in a single shared DB adds a
physical column visible to EVERY tenant, locks the table in production, and
makes migrations unmanageable. We emit no mutating DDL at all here; the only
DDL this feature will ever emit (a later task) is an additive, concurrent,
partial expression index.

Revision ID: 0018_field_definition
Revises: 0017_site_address_link
Create Date: 2026-07-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0018_field_definition"
down_revision = "0017_site_address_link"
branch_labels = None
depends_on = None

_JSON = sa.JSON().with_variant(
    sa.dialects.postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "field_definition",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36),
                  sa.ForeignKey("organization.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target", sa.String(length=60), nullable=False),
        sa.Column("key", sa.String(length=60), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False, server_default="string"),
        sa.Column("widget", sa.String(length=30), nullable=False, server_default="plain"),
        sa.Column("label_en", sa.Text(), nullable=False),
        sa.Column("label_fr", sa.Text(), nullable=False),
        sa.Column("label_es", sa.Text(), nullable=False),
        sa.Column("hint_en", sa.Text(), nullable=True),
        sa.Column("hint_fr", sa.Text(), nullable=True),
        sa.Column("hint_es", sa.Text(), nullable=True),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("default", _JSON, nullable=True),
        sa.Column("rules", _JSON, nullable=False, server_default="{}"),
        sa.Column("options", _JSON, nullable=False, server_default="[]"),
        sa.Column("relation_resource", sa.String(length=60), nullable=False, server_default=""),
        sa.Column("relation_filter", _JSON, nullable=False, server_default="{}"),
        sa.Column("group", sa.String(length=60), nullable=False, server_default=""),
        sa.Column("order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("col_span", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("indexed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("index_state", sa.String(length=10), nullable=False, server_default="none"),
        sa.Column("inherit_to_suborgs", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.UniqueConstraint("organization_id", "target", "key",
                             name="uq_field_definition_org_target_key"),
    )
    op.create_index("ix_field_definition_organization_id", "field_definition",
                     ["organization_id"])
    op.create_index("ix_field_definition_target", "field_definition", ["target"])

    for table in ("organization", "org_unit", "site"):
        op.add_column(table, sa.Column("custom_fields", _JSON, nullable=False,
                                        server_default="{}"))
    # party.custom_fields already exists (party/models.py:38) — nothing to add.


def downgrade() -> None:
    for table in ("organization", "org_unit", "site"):
        op.drop_column(table, "custom_fields")
    op.drop_index("ix_field_definition_target", table_name="field_definition")
    op.drop_index("ix_field_definition_organization_id", table_name="field_definition")
    op.drop_table("field_definition")
