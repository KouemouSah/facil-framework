"""saved_view — per-user list-view presets (backlog ERP item 4)

Revision ID: 0013_saved_view
Revises: 0012_account_search_trgm
Create Date: 2026-06-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0013_saved_view"
down_revision = "0012_account_search_trgm"
branch_labels = None
depends_on = None

_JSON = JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "saved_view",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("resource", sa.String(length=60), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("config", _JSON, nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.UniqueConstraint("account_id", "resource", "name", name="uq_saved_view"),
    )
    op.create_index("ix_saved_view_account_id", "saved_view", ["account_id"])
    op.create_index("ix_saved_view_resource", "saved_view", ["resource"])


def downgrade() -> None:
    op.drop_table("saved_view")
