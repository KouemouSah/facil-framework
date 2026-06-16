"""create session (refresh-token rotation + revocation)

Revision ID: 0007_create_session
Revises: 0006_create_rbac
Create Date: 2026-06-16
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_create_session"
down_revision = "0006_create_rbac"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "session",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False,
                  server_default="active"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_session_account_id", "session", ["account_id"])
    op.create_index("ix_session_refresh_token_hash", "session",
                    ["refresh_token_hash"])


def downgrade() -> None:
    op.drop_table("session")
