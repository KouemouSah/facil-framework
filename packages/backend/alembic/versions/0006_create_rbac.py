"""create RBAC tables (role, permission, role_permission, account_role)

Revision ID: 0006_create_rbac
Revises: 0005_create_credential
Create Date: 2026-06-16
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_create_rbac"
down_revision = "0005_create_credential"
branch_labels = None
depends_on = None


def _audit_cols() -> list:
    return [
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "role",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("organization_id", sa.String(length=36), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("parent_id", sa.String(length=36), nullable=True),
        *_audit_cols(),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"],
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["role.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("organization_id", "code", name="uq_role_org_code"),
    )
    op.create_index("ix_role_code", "role", ["code"])
    op.create_index("ix_role_organization_id", "role", ["organization_id"])

    op.create_table(
        "permission",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("code", sa.String(length=120), nullable=False),
        sa.Column("module", sa.String(length=80), nullable=False,
                  server_default="core"),
        sa.Column("description", sa.Text(), nullable=True),
        *_audit_cols(),
    )
    op.create_index("ix_permission_code", "permission", ["code"], unique=True)
    op.create_index("ix_permission_module", "permission", ["module"])

    op.create_table(
        "role_permission",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("role_id", sa.String(length=36), nullable=False),
        sa.Column("permission_code", sa.String(length=120), nullable=False),
        *_audit_cols(),
        sa.ForeignKeyConstraint(["role_id"], ["role.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("role_id", "permission_code", name="uq_role_perm"),
    )
    op.create_index("ix_role_permission_role_id", "role_permission", ["role_id"])

    op.create_table(
        "account_role",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("role_id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=True),
        sa.Column("org_unit_id", sa.String(length=36), nullable=True),
        sa.Column("site_id", sa.String(length=36), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_cols(),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["role.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"],
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_unit_id"], ["org_unit.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["site_id"], ["site.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("account_id", "role_id", "organization_id",
                            "org_unit_id", "site_id", name="uq_account_role_scope"),
    )
    op.create_index("ix_account_role_account_id", "account_role", ["account_id"])
    op.create_index("ix_account_role_role_id", "account_role", ["role_id"])
    op.create_index("ix_account_role_organization_id", "account_role",
                    ["organization_id"])


def downgrade() -> None:
    op.drop_table("account_role")
    op.drop_table("role_permission")
    op.drop_table("permission")
    op.drop_table("role")
