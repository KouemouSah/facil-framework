"""auth_audit — append-only log of auth events

Revision ID: 0010_auth_audit
Revises: 0009_auth_tokens
Create Date: 2026-06-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

revision = "0010_auth_audit"
down_revision = "0009_auth_tokens"
branch_labels = None
depends_on = None

_JSON = JSONB().with_variant(JSON(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "auth_audit",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("account_id", sa.String(length=36), nullable=True),
        sa.Column("action", sa.String(length=60), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("detail", _JSON, nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
    )
    op.create_index("ix_auth_audit_account_id", "auth_audit", ["account_id"])
    op.create_index("ix_auth_audit_action", "auth_audit", ["action"])


def downgrade() -> None:
    op.drop_table("auth_audit")
