"""Permissions declared by the organization module (collected by RBAC).

Units are part of the organization module, so they share these codes. Uses the
canonical verb taxonomy (app.rbac.verbs); `manage` is covered by the
`organization.*` wildcard in role grants.
"""

from __future__ import annotations

from app.rbac import verbs as v

_R = "organization"

PERMISSIONS: list[dict] = [
    {"code": v.perm(_R, v.READ), "description": "View organizations and units"},
    {"code": v.perm(_R, v.CREATE), "description": "Create organizations and units"},
    {"code": v.perm(_R, v.UPDATE), "description": "Update organizations and units"},
    {"code": v.perm(_R, v.DELETE), "description": "Delete organizations and units"},
    {"code": v.perm(_R, v.EXPORT), "description": "Export organization data"},
]
