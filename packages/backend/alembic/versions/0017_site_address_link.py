"""site → reusable address link (ERP-grade F.3c)

Adds `address_id` on `site`, FK to the reusable `address` (party module). The
flat geo text columns on site are kept non-destructively during the transition
(backfilled into address by a later data migration), mirroring organization F.3.

Revision ID: 0017_site_address_link
Revises: 0016_party_address_company_links
Create Date: 2026-06-18
"""
from alembic import op
import sqlalchemy as sa

revision = "0017_site_address_link"
down_revision = "0016_party_address_company_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("site", sa.Column(
        "address_id", sa.String(length=36),
        sa.ForeignKey("address.id", ondelete="SET NULL"), nullable=True))
    op.create_index("ix_site_address_id", "site", ["address_id"])


def downgrade() -> None:
    op.drop_index("ix_site_address_id", table_name="site")
    op.drop_column("site", "address_id")
