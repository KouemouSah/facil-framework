"""party + address pillar, and Company links on organization (ERP-grade F.3)

Creates the directory pillar (party / party_role) and the reusable address model
(FK to the reference country/country_region), and links organization (= Company)
to its parent (consolidation), its party (legal identity), its HQ address and its
currency. The text geo/currency columns on organization are kept (backfilled into
party/address by a later data migration), so this is non-destructive.

Revision ID: 0016_party_address_company_links
Revises: 0015_reference_master_data
Create Date: 2026-06-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0016_party_address_company_links"
down_revision = "0015_reference_master_data"
branch_labels = None
depends_on = None

_JSON = JSONB().with_variant(sa.JSON(), "sqlite")


def _audit() -> list:
    return [
        sa.Column("id", sa.String(length=36), primary_key=True),
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
        "party",
        sa.Column("party_type", sa.String(length=20), nullable=False, server_default="organization"),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("tax_id", sa.String(length=80), nullable=True),
        sa.Column("registration_number", sa.String(length=80), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("website", sa.String(length=255), nullable=True),
        sa.Column("custom_fields", _JSON, nullable=False, server_default="{}"),
        *_audit(),
    )

    op.create_table(
        "address",
        sa.Column("label", sa.String(length=120), nullable=True),
        sa.Column("line1", sa.Text(), nullable=True),
        sa.Column("line2", sa.Text(), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("postal_code", sa.String(length=20), nullable=True),
        sa.Column("country_id", sa.String(length=36),
                  sa.ForeignKey("country.id", ondelete="SET NULL"), nullable=True),
        sa.Column("country_region_id", sa.String(length=36),
                  sa.ForeignKey("country_region.id", ondelete="SET NULL"), nullable=True),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=True),
        *_audit(),
    )
    op.create_index("ix_address_country_id", "address", ["country_id"])

    op.create_table(
        "party_role",
        sa.Column("party_id", sa.String(length=36),
                  sa.ForeignKey("party.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False),
        *_audit(),
        sa.UniqueConstraint("party_id", "role", name="uq_party_role"),
    )
    op.create_index("ix_party_role_party_id", "party_role", ["party_id"])

    op.create_table(
        "party_address",
        sa.Column("party_id", sa.String(length=36),
                  sa.ForeignKey("party.id", ondelete="CASCADE"), nullable=False),
        sa.Column("address_id", sa.String(length=36),
                  sa.ForeignKey("address.id", ondelete="CASCADE"), nullable=False),
        sa.Column("address_type", sa.String(length=30), nullable=False, server_default="main"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_audit(),
        sa.UniqueConstraint("party_id", "address_id", "address_type", name="uq_party_address"),
    )
    op.create_index("ix_party_address_party_id", "party_address", ["party_id"])
    op.create_index("ix_party_address_address_id", "party_address", ["address_id"])

    # Company links on organization (non-destructive; text columns kept for backfill).
    op.add_column("organization", sa.Column(
        "parent_id", sa.String(length=36),
        sa.ForeignKey("organization.id", ondelete="SET NULL"), nullable=True))
    op.add_column("organization", sa.Column(
        "party_id", sa.String(length=36),
        sa.ForeignKey("party.id", ondelete="SET NULL"), nullable=True))
    op.add_column("organization", sa.Column(
        "hq_address_id", sa.String(length=36),
        sa.ForeignKey("address.id", ondelete="SET NULL"), nullable=True))
    op.add_column("organization", sa.Column(
        "currency_id", sa.String(length=36),
        sa.ForeignKey("currency.id", ondelete="SET NULL"), nullable=True))
    op.create_index("ix_organization_parent_id", "organization", ["parent_id"])


def downgrade() -> None:
    op.drop_index("ix_organization_parent_id", table_name="organization")
    for col in ("currency_id", "hq_address_id", "party_id", "parent_id"):
        op.drop_column("organization", col)
    op.drop_table("party_address")
    op.drop_table("party_role")
    op.drop_table("address")
    op.drop_table("party")
