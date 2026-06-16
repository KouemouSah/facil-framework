"""Permissions declared by the location module (collected by RBAC)."""

from __future__ import annotations

PERMISSIONS: list[dict] = [
    {"code": "location.read", "description": "View sites and branches"},
    {"code": "location.write", "description": "Create/update sites"},
    {"code": "location.delete", "description": "Delete sites"},
]
