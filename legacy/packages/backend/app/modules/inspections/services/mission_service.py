"""Mission Service — Business logic for field mission planning.

Pattern: Static methods, validation, IDOR checks, audit trail.
Uses InspectionService.resolve_inspector_context for auth context.
"""

import logging
from datetime import date, datetime, timezone
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from app.core.events.event_bus import EventBus
from app.core.events.event_types import EventType
from app.modules.inspections.repositories.mission_repository import (
    MissionRepository,
)
from app.modules.inspections.services.inspection_service import (
    InspectionService, _log_audit,
)

logger = logging.getLogger(__name__)

# Valid status transitions: from -> set of allowed to
VALID_TRANSITIONS = {
    "planned": {"in_progress", "cancelled"},
    "in_progress": {"completed", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}


class MissionService:
    """Business logic for field mission planning."""

    @staticmethod
    async def _resolve_zone_names(conn, zone_ids: Optional[List[UUID]]) -> str:
        """Resolve zone UUIDs to comma-separated names for notifications."""
        if not zone_ids:
            return ""
        rows = await conn.fetch(
            "SELECT name_es FROM commerce_zones WHERE id = ANY($1::uuid[])",
            zone_ids,
        )
        return ", ".join(r["name_es"] for r in rows)

    @staticmethod
    async def _get_supervisor_info(conn, user_id: UUID) -> Dict:
        """Get supervisor name and email for notifications."""
        row = await conn.fetchrow(
            "SELECT first_name, last_name, email, phone_number, preferred_language "
            "FROM users WHERE id = $1",
            user_id,
        )
        if not row:
            return {}
        return {
            "supervisor_name": f"{row['first_name']} {row['last_name']}".strip(),
            "user_email": row["email"],
            "user_phone": row["phone_number"],
            "preferred_language": row["preferred_language"] or "es",
        }

    # ============================================================
    # CREATE
    # ============================================================

    @staticmethod
    async def create_mission(conn, user_id: UUID, data: Dict) -> Dict:
        """Create a new field mission.

        Requires supervisor with manage_missions permission.
        """
        ctx = await InspectionService.resolve_inspector_context(conn, user_id)

        if not ctx["is_supervisor"]:
            raise ValueError("Only supervisors can create missions")

        # Verify manage_missions permission
        has_perm = await conn.fetchval("""
            SELECT EXISTS(
                SELECT 1 FROM role_permissions rp
                JOIN permissions p ON p.id = rp.permission_id
                JOIN users u ON u.role_id = rp.role_id
                WHERE u.id = $1 AND p.name = 'inspection.manage_missions'
            )
        """, user_id)
        if not has_perm:
            raise ValueError("Missing permission: inspection.manage_missions")

        # Auto-resolve entity_location_id from supervisor profile if not provided
        entity_location_id = data.get("entity_location_id")
        if not entity_location_id:
            entity_location_id = ctx.get("entity_location_id")
            if not entity_location_id:
                raise ValueError(
                    "entity_location_id not provided and could not be resolved from profile"
                )
            data["entity_location_id"] = entity_location_id

        # Validate entity_location_id belongs to supervisor's entity
        location = await conn.fetchrow("""
            SELECT id, entity_id FROM entity_locations
            WHERE id = $1
        """, data["entity_location_id"])

        if not location:
            raise ValueError(
                f"Entity location {data['entity_location_id']} not found"
            )
        if location["entity_id"] != ctx["entity_id"]:
            raise ValueError(
                "Entity location does not belong to your entity"
            )

        # Validate zone_ids exist in commerce_zones if provided
        zone_ids = data.get("zone_ids")
        if zone_ids:
            zone_count = await conn.fetchval("""
                SELECT COUNT(*) FROM commerce_zones
                WHERE id = ANY($1::uuid[])
            """, zone_ids)
            if zone_count != len(zone_ids):
                raise ValueError(
                    f"Some zone_ids are invalid: expected {len(zone_ids)} "
                    f"zones, found {zone_count}"
                )

        # Validate mission_date is today or in the future
        mission_date = data["mission_date"]
        if isinstance(mission_date, str):
            mission_date = date.fromisoformat(mission_date)
        if mission_date < date.today():
            raise ValueError(
                "Mission date cannot be in the past"
            )

        mission = await MissionRepository.create(conn, {
            "entity_id": ctx["entity_id"],
            "entity_location_id": data["entity_location_id"],
            "supervisor_id": user_id,
            "mission_date": mission_date,
            "title": data.get("title"),
            "notes": data.get("notes"),
            "zone_ids": zone_ids,
            "status": "planned",
        })

        await _log_audit(
            conn, user_id, "mission.created", "field_mission",
            str(mission["id"]), {
                "mission_date": str(mission_date),
                "title": data.get("title"),
            },
        )

        # Return enriched mission
        return await MissionRepository.get_by_id(conn, mission["id"])

    # ============================================================
    # READ
    # ============================================================

    @staticmethod
    async def get_mission(
        conn, user_id: UUID, mission_id: UUID,
    ) -> Dict:
        """Get a single mission with agents."""
        ctx = await InspectionService.resolve_inspector_context(conn, user_id)

        mission = await MissionRepository.get_by_id(conn, mission_id)
        if not mission:
            raise ValueError(f"Mission {mission_id} not found")

        # IDOR check
        if mission["entity_id"] != ctx["entity_id"]:
            raise ValueError("Cannot access missions from another entity")

        agents = await MissionRepository.get_mission_agents(conn, mission_id)
        mission["agents"] = agents

        return mission

    @staticmethod
    async def list_missions(
        conn, user_id: UUID, **filters,
    ) -> Tuple[List[Dict], int]:
        """List missions for the user's entity.

        Non-main-office supervisors only see their own location's missions.
        Main-office supervisors see all locations (read-only for other sites).
        """
        ctx = await InspectionService.resolve_inspector_context(conn, user_id)

        # City-scoped entities (AYUNTAMIENTO, CAMARA_COMERCIO): ALWAYS forced
        # to own location, even if is_main_office=True. These entities have
        # municipal jurisdiction — no cross-site visibility.
        CITY_SCOPED = {"AYUNTAMIENTO", "CAMARA_COMERCIO"}
        entity_code = ctx.get("entity_code", "")
        is_city_scoped = entity_code in CITY_SCOPED

        location_filter = filters.get("entity_location_id")
        if not location_filter:
            if is_city_scoped or not ctx.get("is_main_office", False):
                location_filter = ctx.get("entity_location_id")

        return await MissionRepository.list_by_entity(
            conn, ctx["entity_id"],
            entity_location_id=location_filter,
            date_from=filters.get("date_from"),
            date_to=filters.get("date_to"),
            status=filters.get("status"),
            page=filters.get("page", 1),
            page_size=filters.get("page_size", 20),
        )

    # ============================================================
    # UPDATE
    # ============================================================

    @staticmethod
    async def update_mission(
        conn, user_id: UUID, mission_id: UUID, data: Dict,
    ) -> Dict:
        """Update a mission (supervisor only)."""
        ctx = await InspectionService.resolve_inspector_context(conn, user_id)

        if not ctx["is_supervisor"]:
            raise ValueError("Only supervisors can update missions")

        mission = await MissionRepository.get_by_id(conn, mission_id)
        if not mission:
            raise ValueError(f"Mission {mission_id} not found")

        # IDOR check
        if mission["entity_id"] != ctx["entity_id"]:
            raise ValueError("Cannot update missions from another entity")

        # Validate status transitions
        new_status = data.get("status")
        if new_status:
            current_status = mission["status"]
            allowed = VALID_TRANSITIONS.get(current_status, set())
            if new_status not in allowed:
                raise ValueError(
                    f"Invalid status transition: '{current_status}' -> "
                    f"'{new_status}'. Allowed: {allowed or 'none'}"
                )

            # Set started_at when transitioning to in_progress
            if new_status == "in_progress":
                data["started_at"] = datetime.now(timezone.utc)

        updated = await MissionRepository.update(conn, mission_id, data)

        await _log_audit(
            conn, user_id, "mission.updated", "field_mission",
            str(mission_id), {
                "changes": list(data.keys()),
                "new_status": new_status,
            },
        )

        # Publish status change events
        if new_status in ("in_progress", "cancelled"):
            agents = await MissionRepository.get_mission_agents(conn, mission_id)
            zone_names = await MissionService._resolve_zone_names(
                conn, mission.get("zone_ids"),
            )
            event_type = (
                EventType.MISSION_STARTED if new_status == "in_progress"
                else EventType.MISSION_CANCELLED
            )
            for agent in agents:
                agent_row = await conn.fetchrow(
                    "SELECT first_name, last_name, email, phone_number, preferred_language "
                    "FROM users WHERE id = $1",
                    agent["agent_id"],
                )
                if agent_row:
                    EventBus.publish_nowait(event_type, {
                        "user_id": str(agent["agent_id"]),
                        "user_email": agent_row["email"],
                        "user_phone": agent_row["phone_number"],
                        "preferred_language": agent_row["preferred_language"] or "es",
                        "agent_name": f"{agent_row['first_name']} {agent_row['last_name']}".strip(),
                        "mission_id": str(mission_id),
                        "mission_date": str(mission["mission_date"]),
                        "mission_title": mission.get("title") or str(mission["mission_date"]),
                        "zone_names": zone_names,
                        "target_inspections": str(agent.get("target_inspections", 10)),
                        "agent_count": str(len(agents)),
                    })

        return updated

    # ============================================================
    # AGENTS
    # ============================================================

    @staticmethod
    async def assign_agents(
        conn, user_id: UUID, mission_id: UUID, agents: List[Dict],
    ) -> List[Dict]:
        """Assign agents to a mission."""
        ctx = await InspectionService.resolve_inspector_context(conn, user_id)

        if not ctx["is_supervisor"]:
            raise ValueError("Only supervisors can assign agents")

        mission = await MissionRepository.get_by_id(conn, mission_id)
        if not mission:
            raise ValueError(f"Mission {mission_id} not found")

        # IDOR check
        if mission["entity_id"] != ctx["entity_id"]:
            raise ValueError("Cannot assign agents to another entity's mission")

        # Validate mission is planned or in_progress
        if mission["status"] not in ("planned", "in_progress"):
            raise ValueError(
                f"Cannot assign agents to mission in status "
                f"'{mission['status']}'. Must be 'planned' or 'in_progress'."
            )

        # Validate agents belong to the same entity AND location
        agent_ids = [a["agent_id"] for a in agents]
        mission_location_id = mission["entity_location_id"]

        agent_locations = await conn.fetch("""
            SELECT user_id, entity_location_id, is_active
            FROM agent_profiles
            WHERE user_id = ANY($1::uuid[])
              AND entity_id = $2
        """, agent_ids, ctx["entity_id"])

        found_ids = {r["user_id"] for r in agent_locations}
        missing = [str(a) for a in agent_ids if a not in found_ids]
        if missing:
            raise ValueError(
                f"Agents not found in this entity: {', '.join(missing)}"
            )

        inactive = [str(r["user_id"]) for r in agent_locations if not r["is_active"]]
        if inactive:
            raise ValueError(
                f"Inactive agents cannot be assigned: {', '.join(inactive)}"
            )

        wrong_location = [
            str(r["user_id"]) for r in agent_locations
            if r["entity_location_id"] and r["entity_location_id"] != mission_location_id
        ]
        if wrong_location:
            raise ValueError(
                f"Cross-site assignment blocked: {len(wrong_location)} agent(s) "
                f"belong to a different location than this mission. "
                f"Agents: {', '.join(wrong_location)}"
            )

        # Check for scheduling conflicts (agent already on another mission same day)
        mission_date = mission["mission_date"]
        conflicts = await conn.fetch("""
            SELECT fma.agent_id, fm.title, fm.id AS conflict_mission_id
            FROM field_mission_agents fma
            JOIN field_missions fm ON fm.id = fma.mission_id
            WHERE fma.agent_id = ANY($1::uuid[])
              AND fm.mission_date = $2
              AND fm.status IN ('planned', 'in_progress')
              AND fm.id != $3
        """, agent_ids, mission_date, mission_id)

        if conflicts:
            conflict_names = [
                f"{c['agent_id']} (mission: {c['title'] or str(c['conflict_mission_id'])[:8]})"
                for c in conflicts
            ]
            raise ValueError(
                f"Scheduling conflict: {len(conflicts)} agent(s) already "
                f"assigned to another mission on {mission_date}: "
                + ", ".join(conflict_names)
            )

        # Check max agents from system_rules
        max_agents_rule = await conn.fetchval("""
            SELECT rule_value FROM system_rules
            WHERE rule_code = 'FIELD_MISSION_MAX_AGENTS' AND is_active = true
        """)
        max_agents = int(max_agents_rule) if max_agents_rule else 20

        current_count = mission["agents_count"]
        if current_count + len(agents) > max_agents:
            raise ValueError(
                f"Cannot assign {len(agents)} agents: would exceed max "
                f"of {max_agents} (currently {current_count})"
            )

        result = await MissionRepository.add_agents(conn, mission_id, agents)

        await _log_audit(
            conn, user_id, "mission.agents_assigned", "field_mission",
            str(mission_id), {
                "agent_ids": [str(a) for a in agent_ids],
                "count": len(agents),
            },
        )

        # Notify each assigned agent
        zone_names = await MissionService._resolve_zone_names(
            conn, mission.get("zone_ids"),
        )
        sup_info = await MissionService._get_supervisor_info(conn, user_id)
        for agent_data in agents:
            agent_row = await conn.fetchrow(
                "SELECT first_name, last_name, email, phone_number, preferred_language "
                "FROM users WHERE id = $1",
                agent_data["agent_id"],
            )
            if agent_row:
                EventBus.publish_nowait(EventType.MISSION_AGENT_ASSIGNED, {
                    "user_id": str(agent_data["agent_id"]),
                    "user_email": agent_row["email"],
                    "user_phone": agent_row["phone_number"],
                    "preferred_language": agent_row["preferred_language"] or "es",
                    "agent_name": f"{agent_row['first_name']} {agent_row['last_name']}".strip(),
                    "mission_id": str(mission_id),
                    "mission_date": str(mission["mission_date"]),
                    "mission_title": mission.get("title") or str(mission["mission_date"]),
                    "zone_names": zone_names,
                    "target_inspections": str(agent_data.get("target_inspections", 10)),
                    "supervisor_name": sup_info.get("supervisor_name", ""),
                })

        return result

    @staticmethod
    async def remove_agent(
        conn, user_id: UUID, mission_id: UUID, agent_id: UUID,
    ) -> bool:
        """Remove an agent from a planned mission."""
        ctx = await InspectionService.resolve_inspector_context(conn, user_id)

        if not ctx["is_supervisor"]:
            raise ValueError("Only supervisors can remove agents")

        mission = await MissionRepository.get_by_id(conn, mission_id)
        if not mission:
            raise ValueError(f"Mission {mission_id} not found")

        # IDOR check
        if mission["entity_id"] != ctx["entity_id"]:
            raise ValueError("Cannot modify another entity's mission")

        # Can only remove from planned missions
        if mission["status"] != "planned":
            raise ValueError(
                f"Cannot remove agents from mission in status "
                f"'{mission['status']}'. Must be 'planned'."
            )

        success = await MissionRepository.remove_agent(
            conn, mission_id, agent_id,
        )

        if success:
            await _log_audit(
                conn, user_id, "mission.agent_removed", "field_mission",
                str(mission_id), {"removed_agent_id": str(agent_id)},
            )

        return success

    # ============================================================
    # AGENT STATUS
    # ============================================================

    VALID_AGENT_TRANSITIONS = {
        "assigned": {"active", "absent"},
        "active": {"absent", "completed"},
        "absent": {"assigned"},
        "completed": set(),
    }

    @staticmethod
    async def update_agent_status(
        conn, user_id: UUID, mission_id: UUID, agent_id: UUID,
        new_status: str, reason: Optional[str] = None,
    ) -> Dict:
        """Update an agent's status within a mission (supervisor only)."""
        ctx = await InspectionService.resolve_inspector_context(conn, user_id)

        if not ctx["is_supervisor"]:
            raise ValueError("Only supervisors can update agent status")

        mission = await MissionRepository.get_by_id(conn, mission_id)
        if not mission:
            raise ValueError(f"Mission {mission_id} not found")

        if mission["entity_id"] != ctx["entity_id"]:
            raise ValueError("Cannot modify another entity's mission")

        if mission["status"] not in ("planned", "in_progress"):
            raise ValueError(
                f"Cannot update agents in mission status '{mission['status']}'"
            )

        # Fetch current agent status
        agent_row = await conn.fetchrow("""
            SELECT id, status, notes FROM field_mission_agents
            WHERE mission_id = $1 AND agent_id = $2
        """, mission_id, agent_id)

        if not agent_row:
            raise ValueError(f"Agent {agent_id} not found in mission {mission_id}")

        current = agent_row["status"]
        allowed = MissionService.VALID_AGENT_TRANSITIONS.get(current, set())
        if new_status not in allowed:
            raise ValueError(
                f"Invalid agent status transition: '{current}' -> '{new_status}'. "
                f"Allowed: {allowed or 'none'}"
            )

        updates = {"status": new_status}
        if new_status == "active":
            updates["started_at"] = datetime.now(timezone.utc)
        elif new_status == "absent" and reason:
            existing_notes = (agent_row["notes"] or "").strip()
            updates["notes"] = (
                f"{existing_notes}\n[Absent] {reason}".strip()
                if existing_notes
                else f"[Absent] {reason}"
            )[:2000]

        set_clauses = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(updates.keys()))
        values = list(updates.values())
        await conn.execute(
            f"UPDATE field_mission_agents SET {set_clauses} "
            f"WHERE id = $1",
            agent_row["id"], *values,
        )

        await _log_audit(
            conn, user_id, "mission.agent_status_changed", "field_mission",
            str(mission_id), {
                "agent_id": str(agent_id),
                "from": current,
                "to": new_status,
                "reason": reason,
            },
        )

        return {"agent_id": str(agent_id), "status": new_status}

    # ============================================================
    # PLANNING HELPERS
    # ============================================================

    @staticmethod
    async def suggest_zones(conn, user_id: UUID) -> List[Dict]:
        """Suggest zones for mission planning based on coverage gaps.

        Auto-scopes to supervisor's location for city-scoped entities
        (AYUNTAMIENTO, CAMARA_COMERCIO).
        """
        ctx = await InspectionService.resolve_inspector_context(conn, user_id)
        location_id = ctx.get("entity_location_id")
        return await MissionRepository.suggest_zones(
            conn, ctx["entity_id"],
            entity_location_id=location_id,
        )

    @staticmethod
    async def get_agents_availability(
        conn, user_id: UUID, mission_date: date,
        entity_location_id: Optional[UUID] = None,
    ) -> List[Dict]:
        """Get agent availability for a specific date.

        If entity_location_id is provided, filters agents to that location
        (prevents cross-site assignment).
        """
        ctx = await InspectionService.resolve_inspector_context(conn, user_id)
        return await MissionRepository.get_agents_availability(
            conn, ctx["entity_id"], mission_date,
            entity_location_id=entity_location_id,
        )

    # ============================================================
    # COMPLETE
    # ============================================================

    @staticmethod
    async def complete_mission(
        conn, user_id: UUID, mission_id: UUID,
        notes: Optional[str] = None,
    ) -> Dict:
        """Complete a mission (supervisor only, must be in_progress)."""
        ctx = await InspectionService.resolve_inspector_context(conn, user_id)

        if not ctx["is_supervisor"]:
            raise ValueError("Only supervisors can complete missions")

        mission = await MissionRepository.get_by_id(conn, mission_id)
        if not mission:
            raise ValueError(f"Mission {mission_id} not found")

        # IDOR check
        if mission["entity_id"] != ctx["entity_id"]:
            raise ValueError("Cannot complete another entity's mission")

        if mission["status"] != "in_progress":
            raise ValueError(
                f"Cannot complete mission in status '{mission['status']}'. "
                f"Must be 'in_progress'."
            )

        # Sync actual inspection counts before completing
        await MissionRepository.update_agent_actual_inspections(
            conn, mission_id,
        )

        # Append notes if provided
        if notes:
            existing_notes = (mission.get("notes") or "").strip()
            combined = (
                f"{existing_notes}\n[Completion] {notes}".strip()
                if existing_notes
                else f"[Completion] {notes}"
            )
            await MissionRepository.update(conn, mission_id, {
                "notes": combined[:2000],
            })

        completed = await MissionRepository.complete_mission(conn, mission_id)
        if not completed:
            raise ValueError(
                "Failed to complete mission: status may have changed"
            )

        await _log_audit(
            conn, user_id, "mission.completed", "field_mission",
            str(mission_id), {
                "agents_count": mission["agents_count"],
                "notes": notes,
            },
        )

        # Compute summary stats for notification
        agents = await MissionRepository.get_mission_agents(conn, mission_id)
        actual_total = sum(a.get("actual_inspections", 0) for a in agents)
        target_total = sum(a.get("target_inspections", 10) for a in agents)

        stats = await conn.fetchrow("""
            SELECT
                COUNT(*) FILTER (WHERE result = 'conforme') AS conforme,
                COUNT(*) FILTER (WHERE result = 'non_conforme') AS non_conforme,
                COALESCE(SUM(payment_amount) FILTER (WHERE payment_collected), 0) AS collected
            FROM field_inspections
            WHERE mission_id = $1
        """, mission_id)

        sup_info = await MissionService._get_supervisor_info(conn, user_id)
        zone_names = await MissionService._resolve_zone_names(
            conn, mission.get("zone_ids"),
        )

        EventBus.publish_nowait(EventType.MISSION_COMPLETED, {
            "user_id": str(user_id),
            "user_email": sup_info.get("user_email"),
            "preferred_language": sup_info.get("preferred_language", "es"),
            "supervisor_name": sup_info.get("supervisor_name", ""),
            "mission_id": str(mission_id),
            "mission_date": str(mission["mission_date"]),
            "mission_title": mission.get("title") or str(mission["mission_date"]),
            "actual_inspections": str(actual_total),
            "target_inspections": str(target_total),
            "agent_count": str(len(agents)),
            "conforme_count": str(stats["conforme"] if stats else 0),
            "non_conforme_count": str(stats["non_conforme"] if stats else 0),
            "collected_amount": str(stats["collected"] if stats else 0),
            "completion_notes": notes or "",
            "zone_names": zone_names,
        })

        return completed
