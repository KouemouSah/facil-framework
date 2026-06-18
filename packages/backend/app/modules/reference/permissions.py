"""Permissions declared by the reference module (collected by RBAC).

Reference master data is global (not org-scoped): reads are broadly granted,
writes are admin-level. `manage` is covered by the `reference.*` wildcard.
"""

from __future__ import annotations

from app.rbac import verbs as v

_R = "reference"

PERMISSIONS: list[dict] = [
    {"code": v.perm(_R, v.READ), "description": "View reference data (countries/currencies/regions)"},
    {"code": v.perm(_R, v.CREATE), "description": "Create reference data"},
    {"code": v.perm(_R, v.UPDATE), "description": "Update reference data"},
    {"code": v.perm(_R, v.DELETE), "description": "Delete reference data"},
]
