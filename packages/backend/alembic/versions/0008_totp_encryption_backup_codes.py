"""totp: encrypt secret at rest (widen col) + backup codes

Revision ID: 0008_totp_enc_backup
Revises: 0007_create_session
Create Date: 2026-06-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

revision = "0008_totp_enc_backup"
down_revision = "0007_create_session"
branch_labels = None
depends_on = None

_JSON = JSONB().with_variant(JSON(), "sqlite")


def upgrade() -> None:
    # Encrypted (base64) TOTP secret is longer than the raw base32 secret.
    op.alter_column("credential", "totp_secret",
                    existing_type=sa.String(length=64), type_=sa.String(length=255),
                    existing_nullable=True)
    op.add_column("credential",
                  sa.Column("totp_backup_codes", _JSON, nullable=True))


def downgrade() -> None:
    op.drop_column("credential", "totp_backup_codes")
    op.alter_column("credential", "totp_secret",
                    existing_type=sa.String(length=255), type_=sa.String(length=64),
                    existing_nullable=True)
