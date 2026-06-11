"""
ENUM Repository - Data access layer for PostgreSQL ENUM types

Handles:
- Listing all values from ENUM types
- Adding new values to ENUM types
- Archiving values (renaming with _archived_ prefix)
- Checking if values are in use

Note: PostgreSQL ENUMs cannot have values deleted directly.
We use renaming to _archived_ prefix as soft-delete mechanism.
"""

from typing import List, Dict, Any, Optional
from loguru import logger
import asyncpg


# ENUMs that are modifiable from the UI
MODIFIABLE_ENUMS = [
    "user_role_enum",
    "declaration_status_enum",
    "payment_status_enum",
    "document_status_enum",
    "service_type_enum",
    "calculation_method_enum",
]

# Mapping of ENUM names to their usage in tables
ENUM_USAGE_MAP = {
    "user_role_enum": [("users", "role")],
    "declaration_status_enum": [("tax_declarations", "status")],
    "payment_status_enum": [("payments", "status")],
    "document_status_enum": [("uploaded_files", "status")],
    "service_type_enum": [("fiscal_services", "service_type")],
    "calculation_method_enum": [("fiscal_services", "calculation_method")],
}

ARCHIVED_PREFIX = "_archived_"


class EnumRepository:
    """Repository for PostgreSQL ENUM operations"""

    async def get_all_enum_types(
        self,
        conn: asyncpg.Connection,
    ) -> List[Dict[str, Any]]:
        """
        Get list of all modifiable ENUM types with their values

        Returns:
            List of dicts with enum_name and values
        """
        results = []

        for enum_name in MODIFIABLE_ENUMS:
            values = await self.get_enum_values(conn, enum_name)
            results.append({
                "enum_name": enum_name,
                "values": values,
                "active_values": [v for v in values if not v.startswith(ARCHIVED_PREFIX)],
                "archived_values": [v for v in values if v.startswith(ARCHIVED_PREFIX)],
            })

        return results

    async def get_enum_values(
        self,
        conn: asyncpg.Connection,
        enum_name: str,
    ) -> List[str]:
        """
        Get all values from a PostgreSQL ENUM type

        Args:
            conn: Database connection
            enum_name: Name of the ENUM type

        Returns:
            List of enum values
        """
        query = """
            SELECT enumlabel
            FROM pg_enum
            JOIN pg_type ON pg_enum.enumtypid = pg_type.oid
            WHERE pg_type.typname = $1
            ORDER BY pg_enum.enumsortorder
        """
        rows = await conn.fetch(query, enum_name)
        return [row["enumlabel"] for row in rows]

    async def get_active_enum_values(
        self,
        conn: asyncpg.Connection,
        enum_name: str,
    ) -> List[str]:
        """
        Get only active (non-archived) values from an ENUM type

        Args:
            conn: Database connection
            enum_name: Name of the ENUM type

        Returns:
            List of active enum values
        """
        all_values = await self.get_enum_values(conn, enum_name)
        return [v for v in all_values if not v.startswith(ARCHIVED_PREFIX)]

    async def enum_value_exists(
        self,
        conn: asyncpg.Connection,
        enum_name: str,
        value: str,
    ) -> bool:
        """
        Check if a value exists in an ENUM type

        Args:
            conn: Database connection
            enum_name: Name of the ENUM type
            value: Value to check

        Returns:
            True if value exists
        """
        values = await self.get_enum_values(conn, enum_name)
        return value in values

    async def add_enum_value(
        self,
        conn: asyncpg.Connection,
        enum_name: str,
        value: str,
    ) -> bool:
        """
        Add a new value to an ENUM type

        Args:
            conn: Database connection
            enum_name: Name of the ENUM type
            value: New value to add

        Returns:
            True if successful

        Raises:
            ValueError: If value already exists or enum is not modifiable
        """
        # Validate enum is modifiable
        if enum_name not in MODIFIABLE_ENUMS:
            raise ValueError(f"ENUM '{enum_name}' is not modifiable")

        # Check if value already exists
        if await self.enum_value_exists(conn, enum_name, value):
            raise ValueError(f"Value '{value}' already exists in {enum_name}")

        # Validate value format (snake_case, no special chars)
        if not value or not value.replace("_", "").isalnum():
            raise ValueError(f"Invalid value format: '{value}'. Use snake_case alphanumeric.")

        # Add the value - NOTE: ALTER TYPE ADD VALUE cannot run in transaction
        # We need to use COMMIT mode
        query = f"ALTER TYPE {enum_name} ADD VALUE '{value}'"

        try:
            await conn.execute(query)
            logger.info(f"Added value '{value}' to ENUM {enum_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to add enum value: {e}")
            raise

    async def archive_enum_value(
        self,
        conn: asyncpg.Connection,
        enum_name: str,
        value: str,
    ) -> bool:
        """
        Archive an ENUM value by renaming it with _archived_ prefix

        Args:
            conn: Database connection
            enum_name: Name of the ENUM type
            value: Value to archive

        Returns:
            True if successful

        Raises:
            ValueError: If value doesn't exist, is already archived, or is in use
        """
        # Validate enum is modifiable
        if enum_name not in MODIFIABLE_ENUMS:
            raise ValueError(f"ENUM '{enum_name}' is not modifiable")

        # Check if value exists
        if not await self.enum_value_exists(conn, enum_name, value):
            raise ValueError(f"Value '{value}' does not exist in {enum_name}")

        # Check if already archived
        if value.startswith(ARCHIVED_PREFIX):
            raise ValueError(f"Value '{value}' is already archived")

        # Check if value is in use
        usage_count = await self.get_value_usage_count(conn, enum_name, value)
        if usage_count > 0:
            raise ValueError(
                f"Cannot archive '{value}': it is used in {usage_count} record(s). "
                "Update or delete those records first."
            )

        # Rename to archived
        archived_value = f"{ARCHIVED_PREFIX}{value}"
        query = f"ALTER TYPE {enum_name} RENAME VALUE '{value}' TO '{archived_value}'"

        try:
            await conn.execute(query)
            logger.info(f"Archived value '{value}' in ENUM {enum_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to archive enum value: {e}")
            raise

    async def restore_enum_value(
        self,
        conn: asyncpg.Connection,
        enum_name: str,
        archived_value: str,
    ) -> bool:
        """
        Restore an archived ENUM value by removing _archived_ prefix

        Args:
            conn: Database connection
            enum_name: Name of the ENUM type
            archived_value: Archived value to restore (with _archived_ prefix)

        Returns:
            True if successful
        """
        # Validate
        if not archived_value.startswith(ARCHIVED_PREFIX):
            raise ValueError(f"Value '{archived_value}' is not archived")

        if not await self.enum_value_exists(conn, enum_name, archived_value):
            raise ValueError(f"Archived value '{archived_value}' does not exist")

        # Get original value
        original_value = archived_value[len(ARCHIVED_PREFIX):]

        # Check if original value already exists (conflict)
        if await self.enum_value_exists(conn, enum_name, original_value):
            raise ValueError(f"Cannot restore: value '{original_value}' already exists")

        # Rename back to original
        query = f"ALTER TYPE {enum_name} RENAME VALUE '{archived_value}' TO '{original_value}'"

        try:
            await conn.execute(query)
            logger.info(f"Restored value '{original_value}' in ENUM {enum_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to restore enum value: {e}")
            raise

    async def get_value_usage_count(
        self,
        conn: asyncpg.Connection,
        enum_name: str,
        value: str,
    ) -> int:
        """
        Count how many records use a specific ENUM value

        Args:
            conn: Database connection
            enum_name: Name of the ENUM type
            value: Value to check

        Returns:
            Number of records using this value
        """
        usages = ENUM_USAGE_MAP.get(enum_name, [])
        total_count = 0

        for table_name, column_name in usages:
            query = f"SELECT COUNT(*) FROM {table_name} WHERE {column_name} = $1"
            try:
                count = await conn.fetchval(query, value)
                total_count += count or 0
            except Exception as e:
                logger.warning(f"Could not check usage in {table_name}.{column_name}: {e}")

        return total_count

    async def get_enum_values_with_status(
        self,
        conn: asyncpg.Connection,
        enum_name: str,
    ) -> List[Dict[str, Any]]:
        """
        Get all ENUM values with their status (active/archived) and usage count

        Args:
            conn: Database connection
            enum_name: Name of the ENUM type

        Returns:
            List of dicts with value, is_archived, usage_count
        """
        values = await self.get_enum_values(conn, enum_name)
        results = []

        for value in values:
            is_archived = value.startswith(ARCHIVED_PREFIX)
            display_value = value[len(ARCHIVED_PREFIX):] if is_archived else value
            usage_count = await self.get_value_usage_count(conn, enum_name, value)

            results.append({
                "value": value,
                "display_value": display_value,
                "is_archived": is_archived,
                "usage_count": usage_count,
                "can_archive": not is_archived and usage_count == 0,
            })

        return results

    async def rename_enum_value(
        self,
        conn: asyncpg.Connection,
        enum_name: str,
        old_value: str,
        new_value: str,
    ) -> bool:
        """
        Rename an ENUM value

        Args:
            conn: Database connection
            enum_name: Name of the ENUM type
            old_value: Current value
            new_value: New value

        Returns:
            True if successful

        Note: This also updates all references in tables
        """
        # Validate enum is modifiable
        if enum_name not in MODIFIABLE_ENUMS:
            raise ValueError(f"ENUM '{enum_name}' is not modifiable")

        # Check if old value exists
        if not await self.enum_value_exists(conn, enum_name, old_value):
            raise ValueError(f"Value '{old_value}' does not exist in {enum_name}")

        # Check if new value already exists
        if await self.enum_value_exists(conn, enum_name, new_value):
            raise ValueError(f"Value '{new_value}' already exists in {enum_name}")

        # Validate new value format
        if not new_value or not new_value.replace("_", "").isalnum():
            raise ValueError(f"Invalid value format: '{new_value}'. Use snake_case alphanumeric.")

        # Rename the ENUM value
        query = f"ALTER TYPE {enum_name} RENAME VALUE '{old_value}' TO '{new_value}'"

        try:
            await conn.execute(query)
            logger.info(f"Renamed value '{old_value}' to '{new_value}' in ENUM {enum_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to rename enum value: {e}")
            raise
