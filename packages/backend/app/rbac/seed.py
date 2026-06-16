"""RBAC seeding — permission catalog + per-profile global roles (D4.3).

Idempotent: re-running syncs the permission catalog and re-applies each profile
role's grants (so editing a seed YAML and re-seeding converges). Roles are global
(organization_id NULL, is_system) — operators ASSIGN them at a chosen scope.

Profiles map 1:1 to `deploy/scripts/profiles.py`. An unknown profile falls back
to `empty`. Invoked at boot (lifespan) and via the admin reseed endpoint.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from sqlalchemy.ext.asyncio import AsyncSession

from app.rbac import repository as repo
from app.rbac import service
from app.rbac.permissions import collect_permissions

SEEDS_DIR = Path(__file__).resolve().parent / "seeds"


async def sync_permissions(session: AsyncSession) -> int:
    """Upsert the full permission catalog (core + every module). Returns count."""
    perms = collect_permissions()
    for p in perms:
        await repo.upsert_permission(
            session, p["code"], p.get("module", "core"), p.get("description"))
    return len(perms)


def _load_profile(profile: str) -> dict:
    path = SEEDS_DIR / f"{profile}.yaml"
    if not path.exists():
        path = SEEDS_DIR / "empty.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


async def seed_roles(session: AsyncSession, profile: str = "empty") -> dict:
    """Sync permissions + upsert the profile's global roles (idempotent)."""
    perm_count = await sync_permissions(session)
    spec = _load_profile(profile)
    seeded: list[str] = []
    for r in spec.get("roles", []):
        code = r["code"]
        existing = await repo.get_role_by_code(session, code, None)  # global roles
        grants = r.get("grants", [])
        if existing is None:
            await service.create_role(
                session, code=code, name=r.get("name", code),
                description=r.get("description"), organization_id=None,
                is_system=r.get("is_system", True), grants=grants)
        else:
            existing.name = r.get("name", existing.name)
            existing.description = r.get("description", existing.description)
            existing.is_system = r.get("is_system", existing.is_system)
            await repo.set_role_codes(session, existing.id, grants)
        seeded.append(code)
    await session.flush()
    return {"profile": profile, "permissions": perm_count, "roles": seeded}
