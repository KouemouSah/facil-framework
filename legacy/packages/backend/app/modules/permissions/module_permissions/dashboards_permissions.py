"""
Dashboards Module Permissions (Looker Studio embed + admin config)

⚠️ DO NOT CONFUSE with `dashboard_permissions.py` (singular) — that file
covers supervisor/agent dashboard views (live UI tiles). THIS file covers
the Looker Studio embeds + admin config introduced in plan E1 (2026-05-04).

Why this file exists
--------------------
Migrations 316 (dashboards.view_business) and 317 (dashboards.manage) seed
these permissions in the BD. Without an in-code registry mirror, the
auto-sync at app startup (cleanup_obsolete_permissions in
permission_registry.py) DELETES every permission it doesn't see in any
*_permissions.py file. That's exactly what wiped the rows between the
2026-05-02 and 2026-05-04 sessions (see project_looker_e1_2026_05_04.md).

By registering the same names here, the auto-sync now PRESERVES them at
every app boot. Migrations 316/317 keep their role as the BD seed for
fresh deployments where no app boot has occurred yet.

Naming
------
- module_name = "dashboards" (plural) — already inscribed in BD via migrations
  316/317. The plural is a deliberate exception (mirrors the namespace
  /api/v1/dashboards/*) and the validator in module_permissions/__init__.py
  emits a warning, not an error. Distinct from "dashboard" (singular,
  legacy supervisor module).
"""

MODULE_NAME = "dashboards"

# Format: (name, resource, action, description_es, is_critical)
PERMISSIONS = [
    # =========================================================================
    # LOOKER STUDIO EMBED ACCESS (read)
    # =========================================================================
    (
        "dashboards.view_business",
        "dashboards",
        "view_business",
        # Spanish description matches migration 316 wording
        "Ver dashboards de negocio (Recaudación, Agentes, Catálogo) embebidos desde Looker Studio",
        False,
    ),
    # =========================================================================
    # LOOKER STUDIO ADMIN CONFIG (write — E1 phase 1+2+3)
    # =========================================================================
    (
        "dashboards.manage",
        "dashboards",
        "manage",
        # Spanish description matches migration 317 wording
        "Gestionar la configuración de dashboards Looker Studio (report_id, page_id, estado)",
        True,  # is_critical: changes what every admin sees
    ),
]


# Default role-permission mapping — re-applied on every boot, so wipe is
# auto-healed. Mirrors the grants in migrations 316 + 317.
#
# - admin / super_admin: get everything via "*" wildcard (no need to list)
# - 19 agent_* roles: get view_business only (read-only access, mirroring
#   migration 316). They never get dashboards.manage.
# - citizen / business / accountant: no entry → no permission.
#
# Role codes are verified live in BD (Memory rule #11) — the canonical
# list is `SELECT code FROM roles WHERE code LIKE 'agent_%'` (19 rows
# at 2026-05-04). Keep this list in sync with migration 316.
_AGENT_ROLES_VIEW = [
    "dashboards.view_business",
]

ROLE_PERMISSIONS = {
    # Staff — wildcard grants both view_business and manage
    "admin": ["*"],
    "super_admin": ["*"],

    # Agent roles — read-only access to the Looker embeds
    "agent_ayuntamiento":      _AGENT_ROLES_VIEW,
    "agent_camara":            _AGENT_ROLES_VIEW,
    "agent_cnedoge_pasaporte": _AGENT_ROLES_VIEW,
    "agent_cnedoge_residencia": _AGENT_ROLES_VIEW,
    "agent_dgt":               _AGENT_ROLES_VIEW,
    "agent_extranjeria":       _AGENT_ROLES_VIEW,
    "agent_itv":               _AGENT_ROLES_VIEW,
    "agent_min_agricultura":   _AGENT_ROLES_VIEW,
    "agent_min_comercio":      _AGENT_ROLES_VIEW,
    "agent_min_electricidad":  _AGENT_ROLES_VIEW,
    "agent_min_hacienda":      _AGENT_ROLES_VIEW,
    "agent_min_informacion":   _AGENT_ROLES_VIEW,
    "agent_min_turismo":       _AGENT_ROLES_VIEW,
    "agent_minfp":             _AGENT_ROLES_VIEW,
    "agent_ofive":             _AGENT_ROLES_VIEW,
    "agent_oms_polyvalent":    _AGENT_ROLES_VIEW,
    "agent_onrc":              _AGENT_ROLES_VIEW,
    "agent_policia":           _AGENT_ROLES_VIEW,
    "agent_tesoro":            _AGENT_ROLES_VIEW,

    # Generic "agent" role: NO dashboard access by default. Only the
    # specific agent_* roles get view_business. This avoids accidentally
    # granting business KPI access to a future generic agent.
    "agent": [],
}
