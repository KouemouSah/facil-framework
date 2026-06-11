"""Agent Context Helpers — Resolve agent's ministry, zone, entity from profile.

Shared between dashboard, ministry, and other company routes.
Single source of truth for agent → ministry/zone resolution.
"""

from typing import Optional
from uuid import UUID

import asyncpg


def _uid(val) -> UUID:
    """Convert str to UUID if needed."""
    return UUID(val) if isinstance(val, str) else val


async def get_agent_ministry_id(db: asyncpg.Connection, user_id: str) -> Optional[int]:
    """Resolve agent's ministry_id from agent_profiles → entities."""
    return await db.fetchval(
        """SELECT e.ministry_id
           FROM agent_profiles ap
           JOIN entities e ON ap.entity_id = e.id
           WHERE ap.user_id = $1 AND ap.is_active = true
           LIMIT 1""",
        _uid(user_id),
    )


async def get_agent_zone_id(db: asyncpg.Connection, user_id: str) -> Optional[str]:
    """Resolve supervisor's zone_id from agent_profiles → entity_locations → cities."""
    row = await db.fetchrow(
        """SELECT DISTINCT c.zone_id
           FROM agent_profiles ap
           JOIN entity_locations el ON ap.entity_id = el.entity_id
           JOIN cities c ON el.city_id = c.id
           WHERE ap.user_id = $1 AND ap.is_active = true
             AND c.zone_id IS NOT NULL
           LIMIT 1""",
        _uid(user_id),
    )
    return str(row["zone_id"]) if row and row["zone_id"] else None


async def get_agent_entity_id(db: asyncpg.Connection, user_id: str) -> Optional[str]:
    """Resolve agent's entity_id from agent_profiles."""
    row = await db.fetchrow(
        "SELECT entity_id FROM agent_profiles WHERE user_id = $1 AND is_active = true",
        _uid(user_id),
    )
    return str(row["entity_id"]) if row and row["entity_id"] else None


async def get_agent_city_scope(db: asyncpg.Connection, user_id: str) -> Optional[UUID]:
    """Resolve agent's city scope from entity_location.

    Returns:
        None  — supervisor at main office → sees ALL cities (no filter)
        UUID  — all other agents → sees only this city_id

    Rule: only supervisors at main office get global visibility.
    Regular agents at main office are still restricted to their city.
    """
    row = await db.fetchrow(
        """SELECT el.city_id,
                  COALESCE(el.is_main_office, false) AS is_main_office,
                  COALESCE(ap.is_supervisor, false) AS is_supervisor
           FROM agent_profiles ap
           JOIN entity_locations el ON el.id = ap.entity_location_id
           WHERE ap.user_id = $1 AND ap.is_active = true
           LIMIT 1""",
        _uid(user_id),
    )
    if not row:
        return None  # No profile → will be caught by permission check
    # Only supervisors at main office get global scope
    has_global_scope = row["is_supervisor"] and row["is_main_office"]
    return None if has_global_scope else row["city_id"]
