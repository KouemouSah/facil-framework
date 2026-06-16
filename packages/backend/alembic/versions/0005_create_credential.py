"""create credential (password + TOTP + lockout)

Revision ID: 0005_create_credential
Revises: 0004_create_account
Create Date: 2026-06-16
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_create_credential"
down_revision = "0004_create_account"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "credential",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("totp_secret", sa.String(length=64), nullable=True),
        sa.Column("totp_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_credential_account_id", "credential", ["account_id"],
                    unique=True)


def downgrade() -> None:
    op.drop_table("credential")
