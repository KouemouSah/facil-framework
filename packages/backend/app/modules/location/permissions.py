"""Permissions declared by the location module (collected by RBAC).

Uses the canonical verb taxonomy (app.rbac.verbs); `manage` is covered by the
`location.*` wildcard in role grants.
"""

from __future__ import annotations

from app.rbac import verbs as v

_R = "location"

PERMISSIONS: list[dict] = [
    {"code": v.perm(_R, v.READ), "description": "View sites and branches"},
    {"code": v.perm(_R, v.CREATE), "description": "Create sites"},
    {"code": v.perm(_R, v.UPDATE), "description": "Update sites"},
    {"code": v.perm(_R, v.DELETE), "description": "Delete sites"},
    {"code": v.perm(_R, v.EXPORT), "description": "Export site data"},
]
