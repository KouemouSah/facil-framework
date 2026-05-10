"""Filter Preset Service — Business logic for supervisor filter presets."""

import logging
from typing import Dict, List
from uuid import UUID

from app.modules.inspections.repositories.filter_preset_repository import (
    FilterPresetRepository,
)

logger = logging.getLogger(__name__)


class FilterPresetService:
    """Business logic for supervisor filter presets (CRUD + IDOR checks)."""

    @staticmethod
    async def create_preset(conn, user_id: UUID, data: Dict) -> Dict:
        """Create a new filter preset.

        Validates preset_name is non-empty before delegating to repository.
        """
        preset_name = (data.get("preset_name") or "").strip()
        if not preset_name:
            raise ValueError("preset_name is required and cannot be empty")

        table_key = (data.get("table_key") or "").strip()
        if not table_key:
            raise ValueError("table_key is required and cannot be empty")

        # Normalize trimmed values back
        data["preset_name"] = preset_name
        data["table_key"] = table_key

        return await FilterPresetRepository.create(conn, user_id, data)

    @staticmethod
    async def list_presets(
        conn,
        user_id: UUID,
        table_key: str = None,
    ) -> List[Dict]:
        """List presets for a user, optionally filtered by table_key."""
        return await FilterPresetRepository.list_by_user(conn, user_id, table_key)

    @staticmethod
    async def update_preset(
        conn,
        user_id: UUID,
        preset_id: UUID,
        data: Dict,
    ) -> Dict:
        """Update a preset with IDOR protection.

        Verifies the preset belongs to the requesting user before updating.
        """
        preset = await FilterPresetRepository.get_by_id(conn, preset_id)
        if not preset:
            raise ValueError("Preset not found")

        # IDOR check: ensure the preset belongs to this user
        if preset["user_id"] != user_id:
            raise PermissionError("Cannot modify another user's preset")

        result = await FilterPresetRepository.update(conn, preset_id, data)
        if not result:
            raise ValueError("Preset not found after update")

        return result

    @staticmethod
    async def delete_preset(
        conn,
        user_id: UUID,
        preset_id: UUID,
    ) -> bool:
        """Delete a preset with IDOR protection.

        Verifies the preset belongs to the requesting user before deleting.
        """
        preset = await FilterPresetRepository.get_by_id(conn, preset_id)
        if not preset:
            raise ValueError("Preset not found")

        # IDOR check: ensure the preset belongs to this user
        if preset["user_id"] != user_id:
            raise PermissionError("Cannot delete another user's preset")

        return await FilterPresetRepository.delete(conn, preset_id, user_id=user_id)
