"""Permissions declared by the organization module (collected by RBAC).

Units are part of the organization module, so they share these codes.
"""

from __future__ import annotations

PERMISSIONS: list[dict] = [
    {"code": "organization.read", "description": "View organizations and units"},
    {"code": "organization.write", "description": "Create/update organizations and units"},
    {"code": "organization.delete", "description": "Delete organizations and units"},
]
