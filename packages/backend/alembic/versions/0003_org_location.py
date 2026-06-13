"""create organization + org_unit + site (base modules)

Revision ID: 0003_org_location
Revises: 0002_create_provider_settings
Create Date: 2026-06-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_org_location"
down_revision = "0002_create_provider_settings"
branch_labels = None
depends_on = None


def _audit_cols() -> list:
    return [
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "organization",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("legal_name", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("website", sa.String(length=255), nullable=True),
        sa.Column("address_line1", sa.Text(), nullable=True),
        sa.Column("address_line2", sa.Text(), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("region", sa.String(length=120), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=True),
        sa.Column("postal_code", sa.String(length=20), nullable=True),
        sa.Column("tax_id", sa.String(length=80), nullable=True),
        sa.Column("registration_number", sa.String(length=80), nullable=True),
        sa.Column("default_locale", sa.String(length=5), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("document_identity", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("settings", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        *_audit_cols(),
    )
    op.create_index("ix_organization_code", "organization", ["code"], unique=True)

    op.create_table(
        "org_unit",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("parent_id", sa.String(length=36), nullable=True),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("unit_type", sa.String(length=40), nullable=False,
                  server_default="department"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("path", sa.String(length=1024), nullable=False, server_default=""),
        sa.Column("depth", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("external_ref", sa.String(length=80), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        *_audit_cols(),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"],
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["org_unit.id"]),
        sa.UniqueConstraint("organization_id", "code", name="uq_org_unit_org_code"),
    )
    op.create_index("ix_org_unit_organization_id", "org_unit", ["organization_id"])
    op.create_index("ix_org_unit_path", "org_unit", ["path"])

    op.create_table(
        "site",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("org_unit_id", sa.String(length=36), nullable=True),
        sa.Column("parent_site_id", sa.String(length=36), nullable=True),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("site_type", sa.String(length=40), nullable=False,
                  server_default="branch"),
        sa.Column("address_line1", sa.Text(), nullable=True),
        sa.Column("address_line2", sa.Text(), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("region", sa.String(length=120), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=True),
        sa.Column("postal_code", sa.String(length=20), nullable=True),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("operating_hours", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        *_audit_cols(),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"],
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_unit_id"], ["org_unit.id"]),
        sa.ForeignKeyConstraint(["parent_site_id"], ["site.id"]),
        sa.UniqueConstraint("organization_id", "code", name="uq_site_org_code"),
    )
    op.create_index("ix_site_organization_id", "site", ["organization_id"])
    op.create_index("ix_site_org_unit_id", "site", ["org_unit_id"])
    op.create_index("ix_site_parent_site_id", "site", ["parent_site_id"])


def downgrade() -> None:
    op.drop_table("site")
    op.drop_table("org_unit")
    op.drop_index("ix_organization_code", table_name="organization")
    op.drop_table("organization")
