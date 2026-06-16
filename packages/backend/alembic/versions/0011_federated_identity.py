"""federated_identity + account_role.source (D4.7)

Revision ID: 0011_federated_identity
Revises: 0010_auth_audit
Create Date: 2026-06-16
"""
from alembic import op
import sqlalchemy as sa

revision = "0011_federated_identity"
down_revision = "0010_auth_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "federated_identity",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("provider", "subject",
                            name="uq_federated_provider_subject"),
    )
    op.create_index("ix_federated_identity_account_id", "federated_identity",
                    ["account_id"])
    op.create_index("ix_federated_identity_provider", "federated_identity",
                    ["provider"])
    op.create_index("ix_federated_identity_subject", "federated_identity",
                    ["subject"])
    op.add_column("account_role", sa.Column("source", sa.String(length=10),
                  nullable=False, server_default="local"))


def downgrade() -> None:
    op.drop_column("account_role", "source")
    op.drop_table("federated_identity")
