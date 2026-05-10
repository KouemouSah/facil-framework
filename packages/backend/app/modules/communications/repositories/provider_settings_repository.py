"""
Communication Provider Settings Repository

Data access layer for communication provider configurations.
"""

import asyncpg
import json
from typing import Optional, List
from datetime import datetime, timezone
from uuid import UUID
from loguru import logger
from cryptography.fernet import Fernet
import base64
import os

from ..models.provider_settings import (
    CommunicationProviderType,
    ProviderSettingsCreate,
    ProviderSettingsUpdate,
    ProviderSettingsResponse
)


class ProviderSettingsRepository:
    """Repository for communication provider settings"""

    def __init__(self):
        # Get encryption key from environment or generate one
        self._encryption_key = self._get_encryption_key()

    def _get_encryption_key(self) -> bytes:
        """Get or create encryption key for API secrets"""
        key = os.environ.get("PROVIDER_ENCRYPTION_KEY")
        if key:
            return key.encode()
        # Fallback to a derived key (not ideal for production)
        secret = os.environ.get("JWT_SECRET_KEY", "default-secret-key")
        return base64.urlsafe_b64encode(secret[:32].ljust(32).encode())

    def _encrypt(self, value: str) -> str:
        """Encrypt a value"""
        if not value:
            return ""
        try:
            f = Fernet(self._encryption_key)
            return f.encrypt(value.encode()).decode()
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            # Return a placeholder if encryption fails
            return "ENCRYPTION_FAILED"

    def _decrypt(self, value: str) -> str:
        """Decrypt a value"""
        if not value or value in ("", "ENCRYPTION_FAILED", "ENCRYPTED_API_KEY_PLACEHOLDER"):
            return ""
        try:
            f = Fernet(self._encryption_key)
            return f.decrypt(value.encode()).decode()
        except Exception as e:
            logger.warning(f"Decryption failed: {e}")
            return ""

    async def create(
        self,
        db: asyncpg.Connection,
        data: ProviderSettingsCreate,
        created_by: Optional[UUID] = None
    ) -> ProviderSettingsResponse:
        """Create a new provider configuration"""
        query = """
            INSERT INTO communication_provider_settings (
                provider_type, provider_name, provider_code,
                api_base_url, api_key_encrypted, api_secret_encrypted,
                config, is_active, is_default,
                rate_limit_per_minute, retry_attempts, timeout_seconds,
                created_by, created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $14)
            RETURNING *
        """

        try:
            row = await db.fetchrow(
                query,
                data.provider_type.value,
                data.provider_name,
                data.provider_code,
                data.api_base_url,
                self._encrypt(data.api_key) if data.api_key else None,
                self._encrypt(data.api_secret) if data.api_secret else None,
                json.dumps(data.config),
                data.is_active,
                data.is_default,
                data.rate_limit_per_minute,
                data.retry_attempts,
                data.timeout_seconds,
                created_by,
                datetime.now(timezone.utc)
            )

            logger.info(f"Created provider settings: {data.provider_code}")
            return self._row_to_response(row)

        except asyncpg.UniqueViolationError:
            logger.warning(f"Provider code already exists: {data.provider_code}")
            raise

    async def find_by_id(
        self,
        db: asyncpg.Connection,
        provider_id: int
    ) -> Optional[ProviderSettingsResponse]:
        """Find provider by ID"""
        query = "SELECT * FROM communication_provider_settings WHERE id = $1"
        row = await db.fetchrow(query, provider_id)
        return self._row_to_response(row) if row else None

    async def find_by_code(
        self,
        db: asyncpg.Connection,
        provider_code: str
    ) -> Optional[ProviderSettingsResponse]:
        """Find provider by code"""
        query = "SELECT * FROM communication_provider_settings WHERE provider_code = $1"
        row = await db.fetchrow(query, provider_code)
        return self._row_to_response(row) if row else None

    async def find_default_by_type(
        self,
        db: asyncpg.Connection,
        provider_type: CommunicationProviderType
    ) -> Optional[ProviderSettingsResponse]:
        """Find default provider for a type"""
        query = """
            SELECT * FROM communication_provider_settings
            WHERE provider_type = $1 AND is_default = true AND is_active = true
            LIMIT 1
        """
        row = await db.fetchrow(query, provider_type.value)
        return self._row_to_response(row) if row else None

    async def find_all(
        self,
        db: asyncpg.Connection,
        provider_type: Optional[CommunicationProviderType] = None,
        is_active: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0
    ) -> tuple[List[ProviderSettingsResponse], int]:
        """List all provider configurations with filters"""
        where_clauses = []
        params = []
        param_counter = 1

        if provider_type:
            where_clauses.append(f"provider_type = ${param_counter}")
            params.append(provider_type.value)
            param_counter += 1

        if is_active is not None:
            where_clauses.append(f"is_active = ${param_counter}")
            params.append(is_active)
            param_counter += 1

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        # Count total
        count_query = f"SELECT COUNT(*) FROM communication_provider_settings {where_sql}"
        total = await db.fetchval(count_query, *params)

        # Fetch providers
        query = f"""
            SELECT * FROM communication_provider_settings
            {where_sql}
            ORDER BY provider_type, provider_name
            LIMIT ${param_counter} OFFSET ${param_counter + 1}
        """
        params.extend([limit, offset])

        rows = await db.fetch(query, *params)
        providers = [self._row_to_response(row) for row in rows]

        return providers, total

    async def update(
        self,
        db: asyncpg.Connection,
        provider_id: int,
        data: ProviderSettingsUpdate,
        updated_by: Optional[UUID] = None
    ) -> Optional[ProviderSettingsResponse]:
        """Update a provider configuration"""
        set_clauses = ["updated_at = $1", "updated_by = $2"]
        params = [datetime.now(timezone.utc), updated_by]
        param_counter = 3

        update_fields = data.model_dump(exclude_unset=True)

        for field, value in update_fields.items():
            if field == "api_key" and value is not None:
                set_clauses.append(f"api_key_encrypted = ${param_counter}")
                params.append(self._encrypt(value))
                param_counter += 1
            elif field == "api_secret" and value is not None:
                set_clauses.append(f"api_secret_encrypted = ${param_counter}")
                params.append(self._encrypt(value))
                param_counter += 1
            elif field == "config" and value is not None:
                set_clauses.append(f"config = ${param_counter}")
                params.append(json.dumps(value))
                param_counter += 1
            elif field not in ("api_key", "api_secret", "config"):
                set_clauses.append(f"{field} = ${param_counter}")
                params.append(value)
                param_counter += 1

        if len(set_clauses) == 2:
            return await self.find_by_id(db, provider_id)

        params.append(provider_id)

        query = f"""
            UPDATE communication_provider_settings
            SET {', '.join(set_clauses)}
            WHERE id = ${param_counter}
            RETURNING *
        """

        row = await db.fetchrow(query, *params)
        if row:
            logger.info(f"Updated provider settings: {provider_id}")
            return self._row_to_response(row)
        return None

    async def delete(
        self,
        db: asyncpg.Connection,
        provider_id: int
    ) -> bool:
        """Delete a provider configuration"""
        query = "DELETE FROM communication_provider_settings WHERE id = $1"
        result = await db.execute(query, provider_id)
        deleted = result.endswith("1")

        if deleted:
            logger.info(f"Deleted provider settings: {provider_id}")

        return deleted

    async def get_decrypted_api_key(
        self,
        db: asyncpg.Connection,
        provider_code: str
    ) -> Optional[str]:
        """Get decrypted API key for a provider"""
        query = "SELECT api_key_encrypted FROM communication_provider_settings WHERE provider_code = $1"
        encrypted = await db.fetchval(query, provider_code)
        return self._decrypt(encrypted) if encrypted else None

    async def get_decrypted_credentials(
        self,
        db: asyncpg.Connection,
        provider_code: str
    ) -> dict:
        """Get decrypted credentials for a provider"""
        query = """
            SELECT api_key_encrypted, api_secret_encrypted, api_base_url, config
            FROM communication_provider_settings
            WHERE provider_code = $1
        """
        row = await db.fetchrow(query, provider_code)
        if not row:
            return {}

        config = row["config"]
        if isinstance(config, str):
            config = json.loads(config)

        return {
            "api_key": self._decrypt(row["api_key_encrypted"]) if row["api_key_encrypted"] else None,
            "api_secret": self._decrypt(row["api_secret_encrypted"]) if row["api_secret_encrypted"] else None,
            "api_base_url": row["api_base_url"],
            "config": config
        }

    def _row_to_response(self, row: asyncpg.Record) -> ProviderSettingsResponse:
        """Convert database row to response model"""
        config = row["config"]
        if isinstance(config, str):
            config = json.loads(config)

        return ProviderSettingsResponse(
            id=row["id"],
            provider_type=CommunicationProviderType(row["provider_type"]),
            provider_name=row["provider_name"],
            provider_code=row["provider_code"],
            api_base_url=row["api_base_url"],
            has_api_key=bool(row["api_key_encrypted"]),
            has_api_secret=bool(row["api_secret_encrypted"]),
            config=config or {},
            is_active=row["is_active"],
            is_default=row["is_default"],
            rate_limit_per_minute=row["rate_limit_per_minute"],
            retry_attempts=row["retry_attempts"],
            timeout_seconds=row["timeout_seconds"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            created_by=row["created_by"],
            updated_by=row["updated_by"]
        )
