"""create provider_settings registry table

Revision ID: 0002_create_provider_settings
Revises: 0001_create_settings
Create Date: 2026-06-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_create_provider_settings"
down_revision = "0001_create_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("capability", sa.String(length=20), nullable=False),
        sa.Column("provider_code", sa.String(length=50), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("secret_ref", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("rate_limit_per_minute", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retry_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("updated_by", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("capability", "provider_code", name="uq_provider_cap_code"),
    )
    op.create_index("ix_provider_settings_capability", "provider_settings", ["capability"])


def downgrade() -> None:
    op.drop_index("ix_provider_settings_capability", table_name="provider_settings")
    op.drop_table("provider_settings")
