"""
Communication Provider Settings Service

Business logic for managing communication provider configurations.
"""

import asyncpg
from typing import Optional, List
from uuid import UUID
from datetime import datetime, timezone
from loguru import logger
from fastapi import HTTPException, status

from ..models.provider_settings import (
    CommunicationProviderType,
    ProviderSettingsCreate,
    ProviderSettingsUpdate,
    ProviderSettingsResponse,
    ProviderTestResponse
)
from ..repositories.provider_settings_repository import ProviderSettingsRepository
from .sms_provider_service import SmsService, get_sms_service


class ProviderSettingsService:
    """Service for managing communication provider settings"""

    def __init__(self):
        self.repository = ProviderSettingsRepository()

    async def create_provider(
        self,
        db: asyncpg.Connection,
        data: ProviderSettingsCreate,
        created_by: Optional[UUID] = None
    ) -> ProviderSettingsResponse:
        """Create a new provider configuration"""
        # Check if code already exists
        existing = await self.repository.find_by_code(db, data.provider_code)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Provider code already exists: {data.provider_code}"
            )

        # If setting as default, unset other defaults of same type
        if data.is_default:
            await self._unset_default_for_type(db, data.provider_type)

        return await self.repository.create(db, data, created_by)

    async def get_provider(
        self,
        db: asyncpg.Connection,
        provider_id: int
    ) -> ProviderSettingsResponse:
        """Get provider by ID"""
        provider = await self.repository.find_by_id(db, provider_id)
        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Provider not found: {provider_id}"
            )
        return provider

    async def get_provider_by_code(
        self,
        db: asyncpg.Connection,
        provider_code: str
    ) -> ProviderSettingsResponse:
        """Get provider by code"""
        provider = await self.repository.find_by_code(db, provider_code)
        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Provider not found: {provider_code}"
            )
        return provider

    async def get_default_provider(
        self,
        db: asyncpg.Connection,
        provider_type: CommunicationProviderType
    ) -> Optional[ProviderSettingsResponse]:
        """Get default provider for a type"""
        return await self.repository.find_default_by_type(db, provider_type)

    async def list_providers(
        self,
        db: asyncpg.Connection,
        provider_type: Optional[CommunicationProviderType] = None,
        is_active: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0
    ) -> tuple[List[ProviderSettingsResponse], int]:
        """List all providers with filters"""
        return await self.repository.find_all(
            db, provider_type, is_active, limit, offset
        )

    async def update_provider(
        self,
        db: asyncpg.Connection,
        provider_id: int,
        data: ProviderSettingsUpdate,
        updated_by: Optional[UUID] = None
    ) -> ProviderSettingsResponse:
        """Update a provider configuration"""
        # Check provider exists
        existing = await self.repository.find_by_id(db, provider_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Provider not found: {provider_id}"
            )

        # If setting as default, unset other defaults of same type
        if data.is_default is True:
            await self._unset_default_for_type(db, existing.provider_type)

        updated = await self.repository.update(db, provider_id, data, updated_by)
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update provider"
            )
        return updated

    async def delete_provider(
        self,
        db: asyncpg.Connection,
        provider_id: int
    ) -> bool:
        """Delete a provider configuration"""
        existing = await self.repository.find_by_id(db, provider_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Provider not found: {provider_id}"
            )

        return await self.repository.delete(db, provider_id)

    async def test_provider(
        self,
        db: asyncpg.Connection,
        provider_code: str,
        test_recipient: Optional[str] = None
    ) -> ProviderTestResponse:
        """Test a provider connection"""
        provider = await self.repository.find_by_code(db, provider_code)
        if not provider:
            return ProviderTestResponse(
                success=False,
                provider_code=provider_code,
                message=f"Provider not found: {provider_code}"
            )

        if not provider.is_active:
            return ProviderTestResponse(
                success=False,
                provider_code=provider_code,
                message="Provider is not active"
            )

        # Get decrypted credentials
        credentials = await self.repository.get_decrypted_credentials(db, provider_code)

        try:
            if provider.provider_type == CommunicationProviderType.SMS:
                return await self._test_sms_provider(provider, credentials, test_recipient)
            elif provider.provider_type == CommunicationProviderType.EMAIL:
                return await self._test_email_provider(provider, credentials, test_recipient)
            elif provider.provider_type == CommunicationProviderType.PUSH:
                return await self._test_push_provider(provider, credentials)
            elif provider.provider_type == CommunicationProviderType.WHATSAPP:
                return await self._test_whatsapp_provider(provider, credentials)
            else:
                return ProviderTestResponse(
                    success=False,
                    provider_code=provider_code,
                    message=f"Unknown provider type: {provider.provider_type}"
                )
        except Exception as e:
            logger.error(f"Provider test failed: {e}")
            return ProviderTestResponse(
                success=False,
                provider_code=provider_code,
                message=f"Test failed: {str(e)}"
            )

    async def _test_sms_provider(
        self,
        provider: ProviderSettingsResponse,
        credentials: dict,
        test_recipient: Optional[str]
    ) -> ProviderTestResponse:
        """Test SMS provider connection"""
        api_key = credentials.get("api_key")
        if not api_key:
            return ProviderTestResponse(
                success=False,
                provider_code=provider.provider_code,
                message="API key not configured"
            )

        try:
            # Create SMS service with provider credentials
            sms_service = get_sms_service(
                api_key=api_key,
                provider="infobip"
            )

            # Try to get account balance as a connection test
            balance = sms_service.get_balance()

            if balance:
                return ProviderTestResponse(
                    success=True,
                    provider_code=provider.provider_code,
                    message="SMS provider connection successful",
                    details={
                        "balance": balance,
                        "api_base_url": provider.api_base_url
                    }
                )
            else:
                return ProviderTestResponse(
                    success=True,
                    provider_code=provider.provider_code,
                    message="SMS provider connected (balance check not available)",
                    details={"api_base_url": provider.api_base_url}
                )
        except Exception as e:
            return ProviderTestResponse(
                success=False,
                provider_code=provider.provider_code,
                message=f"SMS provider test failed: {str(e)}"
            )

    async def _test_email_provider(
        self,
        provider: ProviderSettingsResponse,
        credentials: dict,
        test_recipient: Optional[str]
    ) -> ProviderTestResponse:
        """Test Email provider connection"""
        # For now, just check if API key is configured
        api_key = credentials.get("api_key")
        if not api_key:
            return ProviderTestResponse(
                success=False,
                provider_code=provider.provider_code,
                message="API key not configured"
            )

        return ProviderTestResponse(
            success=True,
            provider_code=provider.provider_code,
            message="Email provider configuration valid",
            details={"api_base_url": provider.api_base_url}
        )

    async def _test_push_provider(
        self,
        provider: ProviderSettingsResponse,
        credentials: dict
    ) -> ProviderTestResponse:
        """Test Push provider connection"""
        config = credentials.get("config", {})
        project_id = config.get("project_id")

        if not project_id:
            return ProviderTestResponse(
                success=False,
                provider_code=provider.provider_code,
                message="Firebase project ID not configured"
            )

        return ProviderTestResponse(
            success=True,
            provider_code=provider.provider_code,
            message="Push provider configuration valid",
            details={"project_id": project_id}
        )

    async def _test_whatsapp_provider(
        self,
        provider: ProviderSettingsResponse,
        credentials: dict
    ) -> ProviderTestResponse:
        """Test WhatsApp provider connection"""
        config = credentials.get("config", {})
        phone_number_id = config.get("phone_number_id")

        if not phone_number_id or phone_number_id == "PHONE_NUMBER_ID_PLACEHOLDER":
            return ProviderTestResponse(
                success=False,
                provider_code=provider.provider_code,
                message="WhatsApp phone number ID not configured"
            )

        return ProviderTestResponse(
            success=True,
            provider_code=provider.provider_code,
            message="WhatsApp provider configuration valid",
            details={"phone_number_id": phone_number_id}
        )

    async def _unset_default_for_type(
        self,
        db: asyncpg.Connection,
        provider_type: CommunicationProviderType
    ):
        """Unset default flag for all providers of a type"""
        query = """
            UPDATE communication_provider_settings
            SET is_default = false, updated_at = $1
            WHERE provider_type = $2 AND is_default = true
        """
        await db.execute(query, datetime.now(timezone.utc), provider_type.value)

    async def get_active_sms_credentials(
        self,
        db: asyncpg.Connection
    ) -> Optional[dict]:
        """Get active SMS provider credentials"""
        provider = await self.repository.find_default_by_type(
            db, CommunicationProviderType.SMS
        )
        if not provider:
            return None

        return await self.repository.get_decrypted_credentials(
            db, provider.provider_code
        )
