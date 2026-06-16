"""create account (identity core)

Revision ID: 0004_create_account
Revises: 0003_org_location
Create Date: 2026-06-16
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_create_account"
down_revision = "0003_org_location"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "account",
        sa.Column("id", sa.String(length=36), primary_key=True),
        # NULL until issued (on_verified_document policy) — UNIQUE allows it.
        sa.Column("account_number", sa.String(length=40), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("organization_id", sa.String(length=36), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("subject_type", sa.String(length=20), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False,
                  server_default="pending_identity"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"],
                                ondelete="SET NULL"),
    )
    op.create_index("ix_account_number", "account", ["account_number"], unique=True)
    op.create_index("ix_account_email", "account", ["email"], unique=True)
    op.create_index("ix_account_organization_id", "account", ["organization_id"])


def downgrade() -> None:
    op.drop_table("account")
