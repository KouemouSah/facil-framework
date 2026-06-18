"""reference master data — currency / country / country_region (ERP-grade F.2)

Managed reference tables replacing the free-text country/region/currency on
organization & site. Composite (sort_col, id) indexes back the keyset lists
(same pattern as 0014). Portable btree + JSONB/JSON variant for the i18n column.

Revision ID: 0015_reference_master_data
Revises: 0014_keyset_composite_indexes
Create Date: 2026-06-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0015_reference_master_data"
down_revision = "0014_keyset_composite_indexes"
branch_labels = None
depends_on = None

_JSON = JSONB().with_variant(sa.JSON(), "sqlite")


def _audit_cols() -> list:
    """The UUIDAuditBase columns, replicated for create_table."""
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
        "currency",
        sa.Column("code", sa.String(length=3), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("name_i18n", _JSON, nullable=False, server_default="{}"),
        sa.Column("symbol", sa.String(length=8), nullable=True),
        sa.Column("decimal_places", sa.Integer(), nullable=False, server_default="2"),
        *_audit_cols(),
        sa.UniqueConstraint("code", name="uq_currency_code"),
    )
    op.create_index("ix_currency_code_id", "currency", ["code", "id"])

    op.create_table(
        "country",
        sa.Column("code", sa.String(length=2), nullable=False),
        sa.Column("alpha3", sa.String(length=3), nullable=True),
        sa.Column("numeric_code", sa.String(length=3), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("name_i18n", _JSON, nullable=False, server_default="{}"),
        sa.Column("phone_code", sa.String(length=8), nullable=True),
        sa.Column("default_currency_id", sa.String(length=36),
                  sa.ForeignKey("currency.id", ondelete="SET NULL"), nullable=True),
        *_audit_cols(),
        sa.UniqueConstraint("code", name="uq_country_code"),
    )
    op.create_index("ix_country_code_id", "country", ["code", "id"])
    op.create_index("ix_country_name_id", "country", ["name", "id"])

    op.create_table(
        "country_region",
        sa.Column("country_id", sa.String(length=36),
                  sa.ForeignKey("country.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(length=10), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("name_i18n", _JSON, nullable=False, server_default="{}"),
        sa.Column("region_type", sa.String(length=40), nullable=True),
        *_audit_cols(),
        sa.UniqueConstraint("country_id", "code", name="uq_country_region_code"),
    )
    op.create_index("ix_country_region_country_id", "country_region", ["country_id"])
    # Keyset list of regions, typically scoped to a country then ordered by name.
    op.create_index("ix_country_region_country_name_id", "country_region",
                    ["country_id", "name", "id"])


def downgrade() -> None:
    op.drop_table("country_region")
    op.drop_table("country")
    op.drop_table("currency")
