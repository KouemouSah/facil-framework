"""Permission catalog — core perms + per-module collection (D4.3).

A module declares its permissions in `app.modules.<name>.permissions:PERMISSIONS`
(a list of {"code": "resource.action", "description": ...}). `collect_permissions`
discovers every shipped module (regardless of MODULES_ENABLED — the catalog is
global, like the DB schema) and merges them with the core permissions. The
seeder upserts the result into the `permission` table.

Wildcards (`*`, `resource.*`) are NOT catalog entries; they only appear in role
grants and are matched at enforcement time.
"""

from __future__ import annotations

import importlib

from app.core.module_registry import DEFAULT_PACKAGE, discover

# Core (always-on) permissions — not owned by any business module.
CORE_PERMISSIONS: list[dict] = [
    {"code": "rbac.read", "module": "rbac",
     "description": "View roles, permissions and assignments"},
    {"code": "rbac.manage", "module": "rbac",
     "description": "Create/modify roles, grants and account assignments"},
    {"code": "account.read", "module": "identity",
     "description": "View accounts (agents and users)"},
    {"code": "account.manage", "module": "identity",
     "description": "Create accounts and change their status"},
    {"code": "branding.manage", "module": "core",
     "description": "Edit branding (names, colours, logos, locale)"},
    {"code": "settings.read", "module": "core",
     "description": "View config-store settings"},
    {"code": "settings.manage", "module": "core",
     "description": "Edit config-store settings"},
    {"code": "settings.manage_protected", "module": "core",
     "description": "Edit security-critical settings (auth.*, rbac, security.*)"},
    {"code": "provider.read", "module": "core",
     "description": "View provider registry (LLM/storage/email/…)"},
    {"code": "provider.manage", "module": "core",
     "description": "Edit providers and defaults"},
]


def collect_permissions(package: str = DEFAULT_PACKAGE) -> list[dict]:
    """Core permissions + every shipped module's declared permissions.

    De-duplicated by code (first declaration wins). A module without a
    `permissions` submodule simply contributes nothing.
    """
    seen: dict[str, dict] = {}
    for perm in CORE_PERMISSIONS:
        seen.setdefault(perm["code"], {"module": "core", "description": None, **perm})
    for name in discover(package):
        mod_name = f"{package}.{name}.permissions"
        try:
            mod = importlib.import_module(mod_name)
        except ModuleNotFoundError as e:
            if e.name == mod_name:
                continue  # module declares no permissions — fine
            raise
        for perm in getattr(mod, "PERMISSIONS", []):
            entry = {"module": name, "description": None, **perm}
            seen.setdefault(entry["code"], entry)
    return list(seen.values())
