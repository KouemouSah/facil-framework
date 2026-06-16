"""auth_token (reset/verif) + account.email_verified

Revision ID: 0009_auth_tokens
Revises: 0008_totp_enc_backup
Create Date: 2026-06-16
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_auth_tokens"
down_revision = "0008_totp_enc_backup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_token",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("purpose", sa.String(length=40), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_auth_token_account_id", "auth_token", ["account_id"])
    op.create_index("ix_auth_token_purpose", "auth_token", ["purpose"])
    op.create_index("ix_auth_token_token_hash", "auth_token", ["token_hash"])
    op.add_column("account", sa.Column("email_verified", sa.Boolean(),
                  nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("account", "email_verified")
    op.drop_table("auth_token")
