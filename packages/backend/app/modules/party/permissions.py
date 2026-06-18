"""Permissions declared by the party module (collected by RBAC).

Covers the whole directory family (party, party_role, address, party_address).
Global admin for V1 (the directory is not tenant-scoped yet — scope is a later
phase); `manage` is covered by the `party.*` wildcard.
"""

from __future__ import annotations

from app.rbac import verbs as v

_R = "party"

PERMISSIONS: list[dict] = [
    {"code": v.perm(_R, v.READ), "description": "View parties, roles and addresses"},
    {"code": v.perm(_R, v.CREATE), "description": "Create parties/roles/addresses"},
    {"code": v.perm(_R, v.UPDATE), "description": "Update parties/roles/addresses"},
    {"code": v.perm(_R, v.DELETE), "description": "Delete parties/roles/addresses"},
]
