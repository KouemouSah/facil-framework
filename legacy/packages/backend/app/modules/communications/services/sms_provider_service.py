"""
SMS Provider Service for TaxasGE Backend
Handles SMS sending via Infobip API

Module: Communications
Provider: Infobip (y45e8g.api.infobip.com)
"""

import httpx
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from loguru import logger
from enum import Enum
from abc import ABC, abstractmethod


# =============================================================================
# ENUMS AND DATA CLASSES
# =============================================================================

class SmsProvider(str, Enum):
    """Available SMS providers"""
    INFOBIP = "infobip"
    MOCK = "mock"


class SmsDeliveryStatus(str, Enum):
    """SMS delivery status"""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    REJECTED = "rejected"


class SmsResult:
    """Result of an SMS send operation"""
    def __init__(
        self,
        success: bool,
        message_id: Optional[str] = None,
        status: SmsDeliveryStatus = SmsDeliveryStatus.PENDING,
        error: Optional[str] = None,
        provider_response: Optional[Dict] = None
    ):
        self.success = success
        self.message_id = message_id
        self.status = status
        self.error = error
        self.provider_response = provider_response
        self.sent_at = datetime.now(timezone.utc) if success else None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "message_id": self.message_id,
            "status": self.status.value,
            "error": self.error,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None
        }


class BulkSmsResult:
    """Result of a bulk SMS send operation"""
    def __init__(self, results: List[SmsResult]):
        self.results = results
        self.total = len(results)
        self.successful = sum(1 for r in results if r.success)
        self.failed = self.total - self.successful


# =============================================================================
# BASE SMS PROVIDER
# =============================================================================

class BaseSmsProvider(ABC):
    """Abstract base class for SMS providers"""

    @abstractmethod
    def send_sms(self, to: str, message: str, sender_id: Optional[str] = None) -> SmsResult:
        """Send a single SMS message"""
        pass

    @abstractmethod
    def send_bulk_sms(self, messages: List[Dict[str, str]], sender_id: Optional[str] = None) -> BulkSmsResult:
        """Send multiple SMS messages"""
        pass

    @abstractmethod
    def get_delivery_status(self, message_id: str) -> SmsDeliveryStatus:
        """Get delivery status for a message"""
        pass


# =============================================================================
# INFOBIP SMS PROVIDER
# =============================================================================

class InfobipSmsProvider(BaseSmsProvider):
    """
    Infobip SMS Provider Implementation

    API Documentation: https://www.infobip.com/docs/api/channels/sms
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "y45e8g.api.infobip.com",
        sender_id: str = "Facil"
    ):
        self.api_key = api_key
        self.base_url = f"https://{base_url}"
        self.sender_id = sender_id
        self._client: Optional[httpx.Client] = None

    def _get_client(self) -> httpx.Client:
        """Get or create HTTP client"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(
                base_url=self.base_url,
                timeout=30.0
            )
        return self._client

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication"""
        return {
            "Authorization": f"App {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number to E.164 format"""
        cleaned = ''.join(c for c in phone if c.isdigit() or c == '+')
        if cleaned.startswith('+'):
            cleaned = cleaned[1:]
        # Add Equatorial Guinea country code if missing
        if not cleaned.startswith('240') and len(cleaned) == 9:
            cleaned = '240' + cleaned
        return cleaned

    def send_sms(self, to: str, message: str, sender_id: Optional[str] = None) -> SmsResult:
        """
        Send a single SMS via Infobip

        Args:
            to: Recipient phone number
            message: SMS content (max 160 chars for single SMS)
            sender_id: Optional sender ID override

        Returns:
            SmsResult with success status and message ID
        """
        try:
            client = self._get_client()

            payload = {
                "messages": [
                    {
                        "destinations": [{"to": self._normalize_phone(to)}],
                        "from": sender_id or self.sender_id,
                        "text": message
                    }
                ]
            }

            response = client.post(
                "/sms/2/text/advanced",
                json=payload,
                headers=self._get_headers()
            )

            if response.status_code < 400:
                data = response.json()
                messages = data.get("messages", [])
                if messages:
                    msg = messages[0]
                    logger.info(f"SMS sent successfully to {to}", extra={"message_id": msg.get("messageId")})
                    return SmsResult(
                        success=True,
                        message_id=msg.get("messageId"),
                        status=self._map_status(msg.get("status", {}).get("groupName")),
                        provider_response=data
                    )

            logger.error(f"Infobip SMS failed: {response.text}")
            return SmsResult(
                success=False,
                error=response.text,
                status=SmsDeliveryStatus.FAILED
            )

        except httpx.TimeoutException:
            logger.error("Infobip SMS timeout")
            return SmsResult(success=False, error="Request timeout", status=SmsDeliveryStatus.FAILED)
        except Exception as e:
            logger.error(f"Infobip SMS error: {str(e)}")
            return SmsResult(success=False, error=str(e), status=SmsDeliveryStatus.FAILED)

    def send_bulk_sms(self, messages: List[Dict[str, str]], sender_id: Optional[str] = None) -> BulkSmsResult:
        """
        Send multiple SMS messages via Infobip

        Args:
            messages: List of {"to": phone, "text": message}
            sender_id: Optional sender ID override

        Returns:
            BulkSmsResult with individual results
        """
        try:
            client = self._get_client()

            destinations = [
                {
                    "destinations": [{"to": self._normalize_phone(msg["to"])}],
                    "from": sender_id or self.sender_id,
                    "text": msg["text"]
                }
                for msg in messages
            ]

            payload = {"messages": destinations}

            response = client.post(
                "/sms/2/text/advanced",
                json=payload,
                headers=self._get_headers()
            )

            results = []
            if response.status_code < 400:
                data = response.json()
                for msg in data.get("messages", []):
                    results.append(SmsResult(
                        success=True,
                        message_id=msg.get("messageId"),
                        status=self._map_status(msg.get("status", {}).get("groupName")),
                        provider_response=msg
                    ))
            else:
                for _ in messages:
                    results.append(SmsResult(
                        success=False,
                        error=response.text,
                        status=SmsDeliveryStatus.FAILED
                    ))

            return BulkSmsResult(results)

        except Exception as e:
            logger.error(f"Infobip bulk SMS error: {str(e)}")
            return BulkSmsResult([
                SmsResult(success=False, error=str(e), status=SmsDeliveryStatus.FAILED)
                for _ in messages
            ])

    def get_delivery_status(self, message_id: str) -> SmsDeliveryStatus:
        """Get delivery status for a message"""
        try:
            client = self._get_client()
            response = client.get(
                f"/sms/1/reports?messageId={message_id}",
                headers=self._get_headers()
            )

            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                if results:
                    return self._map_status(results[0].get("status", {}).get("groupName"))

            return SmsDeliveryStatus.PENDING

        except Exception as e:
            logger.error(f"Failed to get delivery status: {str(e)}")
            return SmsDeliveryStatus.PENDING

    def get_account_balance(self) -> Optional[Dict[str, Any]]:
        """Get Infobip account balance"""
        try:
            client = self._get_client()
            response = client.get(
                "/account/1/balance",
                headers=self._get_headers()
            )

            if response.status_code == 200:
                return response.json()
            return None

        except Exception as e:
            logger.error(f"Failed to get account balance: {str(e)}")
            return None

    def _map_status(self, group_name: Optional[str]) -> SmsDeliveryStatus:
        """Map Infobip status to internal status"""
        if not group_name:
            return SmsDeliveryStatus.PENDING

        status_map = {
            "PENDING": SmsDeliveryStatus.PENDING,
            "UNDELIVERABLE": SmsDeliveryStatus.FAILED,
            "DELIVERED": SmsDeliveryStatus.DELIVERED,
            "EXPIRED": SmsDeliveryStatus.FAILED,
            "REJECTED": SmsDeliveryStatus.REJECTED
        }
        return status_map.get(group_name.upper(), SmsDeliveryStatus.PENDING)

    def close(self):
        """Close HTTP client"""
        if self._client and not self._client.is_closed:
            self._client.close()


# =============================================================================
# MOCK SMS PROVIDER (for testing)
# =============================================================================

class MockSmsProvider(BaseSmsProvider):
    """Mock SMS provider for testing"""

    def __init__(self):
        self.sent_messages: List[Dict] = []

    def send_sms(self, to: str, message: str, sender_id: Optional[str] = None) -> SmsResult:
        msg_id = f"mock_{datetime.now(timezone.utc).timestamp()}"
        self.sent_messages.append({
            "to": to,
            "message": message,
            "sender_id": sender_id,
            "message_id": msg_id
        })
        logger.info(f"[MOCK] SMS sent to {to}: {message[:50]}...")
        return SmsResult(
            success=True,
            message_id=msg_id,
            status=SmsDeliveryStatus.DELIVERED
        )

    def send_bulk_sms(self, messages: List[Dict[str, str]], sender_id: Optional[str] = None) -> BulkSmsResult:
        results = [self.send_sms(msg["to"], msg["text"], sender_id) for msg in messages]
        return BulkSmsResult(results)

    def get_delivery_status(self, message_id: str) -> SmsDeliveryStatus:
        return SmsDeliveryStatus.DELIVERED


# =============================================================================
# SMS SERVICE (Main interface)
# =============================================================================

class SmsService:
    """
    Main SMS service for TaxasGE

    Usage:
        service = SmsService(provider="infobip", api_key="xxx")
        result = service.send_sms("+240222123456", "Your verification code is 123456")
    """

    def __init__(
        self,
        provider: str = "infobip",
        api_key: Optional[str] = None,
        base_url: str = "y45e8g.api.infobip.com",
        sender_id: str = "Facil"
    ):
        if provider == "infobip":
            if not api_key:
                raise ValueError("API key required for Infobip provider")
            self._provider = InfobipSmsProvider(api_key, base_url, sender_id)
        elif provider == "mock":
            self._provider = MockSmsProvider()
        else:
            raise ValueError(f"Unknown SMS provider: {provider}")

    def send_sms(self, to: str, message: str, sender_id: Optional[str] = None) -> SmsResult:
        """Send a single SMS"""
        return self._provider.send_sms(to, message, sender_id)

    def send_bulk_sms(self, messages: List[Dict[str, str]], sender_id: Optional[str] = None) -> BulkSmsResult:
        """Send multiple SMS messages"""
        return self._provider.send_bulk_sms(messages, sender_id)

    def get_delivery_status(self, message_id: str) -> SmsDeliveryStatus:
        """Get delivery status"""
        return self._provider.get_delivery_status(message_id)

    def get_balance(self) -> Optional[Dict[str, Any]]:
        """Get account balance (Infobip only)"""
        if isinstance(self._provider, InfobipSmsProvider):
            return self._provider.get_account_balance()
        return None

    def close(self):
        """Close provider connections"""
        if hasattr(self._provider, 'close'):
            self._provider.close()


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def get_sms_service(
    api_key: Optional[str] = None,
    provider: str = "infobip"
) -> SmsService:
    """
    Get SMS service instance

    Args:
        api_key: Infobip API key
        provider: Provider name (infobip or mock)

    Returns:
        Configured SmsService instance
    """
    return SmsService(
        provider=provider,
        api_key=api_key,
        base_url="y45e8g.api.infobip.com",
        sender_id="Facil"
    )
