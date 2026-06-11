"""create settings config-store table

Revision ID: 0001_create_settings
Revises:
Create Date: 2026-06-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_create_settings"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=200), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("value_type", sa.String(length=20), nullable=False,
                  server_default="string"),
        sa.Column("scope", sa.String(length=50), nullable=False,
                  server_default="global"),
        sa.Column("secret_ref", sa.String(length=200), nullable=False,
                  server_default=""),
        sa.Column("name_es", sa.Text(), nullable=True),
        sa.Column("name_fr", sa.Text(), nullable=True),
        sa.Column("name_en", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False,
                  server_default=sa.true()),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_until", sa.Date(), nullable=True),
        sa.Column("updated_by", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_settings_key", "settings", ["key"], unique=True)
    op.create_index("ix_settings_scope", "settings", ["scope"])


def downgrade() -> None:
    op.drop_index("ix_settings_scope", table_name="settings")
    op.drop_index("ix_settings_key", table_name="settings")
    op.drop_table("settings")
