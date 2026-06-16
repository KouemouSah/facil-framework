"""SQLAlchemy models for RBAC (D4.3).

- Role: a named bundle of permissions. organization_id NULL = global/system role
  available to every tenant; non-NULL = a role owned by a single organization.
  parent_id gives single-parent inheritance (a role inherits its ancestors' perms).
- Permission: the catalog of `resource.action` codes, declared per module.
- RolePermission: which permission CODES a role grants (the code string, so `*`
  and `resource.*` wildcards work without a catalog row).
- AccountRole: the SCOPED assignment — an account holds a role within a scope
  {organization_id?, org_unit_id?, site_id?} with an optional expiry. NULLs widen
  the scope (no org = global; no unit = whole org; no site = whole unit subtree).
"""

from __future__ import annotations

import datetime as _dt

from sqlalchemy import (Boolean, DateTime, ForeignKey, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import UUIDAuditBase


class Role(UUIDAuditBase):
    __tablename__ = "role"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_role_org_code"),
    )

    code: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # NULL = global/system role (available to all tenants).
    organization_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=True, index=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    parent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("role.id", ondelete="SET NULL"), nullable=True)

    def as_dict(self) -> dict:
        return {
            "id": self.id, "code": self.code, "name": self.name,
            "description": self.description, "organization_id": self.organization_id,
            "is_system": self.is_system, "parent_id": self.parent_id,
            "is_active": self.is_active,
        }


class Permission(UUIDAuditBase):
    __tablename__ = "permission"

    code: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    module: Mapped[str] = mapped_column(String(80), default="core", index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    def as_dict(self) -> dict:
        return {"id": self.id, "code": self.code, "module": self.module,
                "description": self.description}


class RolePermission(UUIDAuditBase):
    __tablename__ = "role_permission"
    __table_args__ = (
        UniqueConstraint("role_id", "permission_code", name="uq_role_perm"),
    )

    role_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("role.id", ondelete="CASCADE"), index=True)
    # Stored as the code string (supports `*` and `resource.*` wildcards).
    permission_code: Mapped[str] = mapped_column(String(120))


class AccountRole(UUIDAuditBase):
    __tablename__ = "account_role"
    __table_args__ = (
        UniqueConstraint("account_id", "role_id", "organization_id",
                         "org_unit_id", "site_id", name="uq_account_role_scope"),
    )

    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("account.id", ondelete="CASCADE"), index=True)
    role_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("role.id", ondelete="CASCADE"), index=True)

    # Scope — NULLs widen (no org = global, no unit = whole org, no site = subtree).
    organization_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=True, index=True)
    org_unit_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("org_unit.id", ondelete="CASCADE"), nullable=True)
    site_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("site.id", ondelete="CASCADE"), nullable=True)

    expires_at: Mapped[_dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)

    def as_dict(self) -> dict:
        return {
            "id": self.id, "account_id": self.account_id, "role_id": self.role_id,
            "organization_id": self.organization_id, "org_unit_id": self.org_unit_id,
            "site_id": self.site_id,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_active": self.is_active,
        }
