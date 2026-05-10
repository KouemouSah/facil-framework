"""
BANGE Payment Service — Backward-compatible wrapper.

Delegates all API communication to BANGEGateway (gateways/bange_gateway.py).
Kept for backward compatibility with existing imports:
    from app.modules.payments.services.bange_service import BANGEService, bange_service

New code should import BANGEGateway directly from:
    from app.modules.payments.services.gateways import BANGEGateway
"""

import httpx
from typing import Dict, List, Optional, Any
from decimal import Decimal
from datetime import datetime, timezone
from loguru import logger

from app.modules.payments.models.payment import (
    BANGEPaymentRequest, BANGEPaymentResponse, BANGEWebhookData,
    PaymentResponse, PaymentStatus
)
from app.modules.payments.services.gateways.bange_gateway import BANGEGateway
from app.modules.payments.services.gateways.base import (
    GatewayPaymentRequest,
)


class BANGEService:
    """
    BANGE Payment Gateway Service — backward-compatible wrapper.

    Delegates to BANGEGateway for actual API calls.
    Preserves the original interface (BANGEPaymentRequest/Response models)
    used by bange_processor.py.
    """

    def __init__(self):
        self._gateway = BANGEGateway()
        # Expose gateway properties for direct access
        self.base_url = self._gateway.base_url
        self.merchant_id = self._gateway.merchant_id
        self.api_key = self._gateway.api_key
        self.webhook_secret = self._gateway.webhook_secret

    @property
    def gateway(self) -> BANGEGateway:
        """Access the underlying BANGEGateway instance."""
        return self._gateway

    async def create_payment(
        self, payment_request: BANGEPaymentRequest
    ) -> Optional[BANGEPaymentResponse]:
        """
        Create payment with BANGE gateway.
        Converts BANGEPaymentRequest → GatewayPaymentRequest,
        calls gateway, converts GatewayPaymentResponse → BANGEPaymentResponse.
        """
        # Convert to gateway-agnostic request
        gw_request = GatewayPaymentRequest(
            amount=payment_request.amount,
            currency=payment_request.currency,
            reference=payment_request.reference,
            description=payment_request.description,
            callback_url=payment_request.callback_url or "",
            return_url=payment_request.return_url or "",
            customer_email=payment_request.customer_email,
            customer_phone=payment_request.customer_phone,
            metadata=payment_request.metadata or {},
        )

        gw_response = await self._gateway.create_payment(gw_request)

        if not gw_response.success:
            return None

        return BANGEPaymentResponse(
            payment_id=gw_response.external_id,
            payment_url=gw_response.redirect_url or "",
            reference=payment_request.reference,
            status=gw_response.status,
            amount=payment_request.amount,
            currency=payment_request.currency,
            expires_at=gw_response.expires_at,
            created_at=datetime.now(timezone.utc),
        )

    async def verify_payment(
        self, payment_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Verify payment status with BANGE.
        Returns raw dict for backward compat with bange_processor.py.
        """
        gw_status = await self._gateway.verify_payment(payment_id)

        if gw_status.error:
            return None

        return gw_status.raw_data or {
            "status": gw_status.status,
            "paid": gw_status.paid,
            "paid_at": gw_status.paid_at.isoformat() if gw_status.paid_at else None,
            "amount": float(gw_status.amount) if gw_status.amount else None,
            "currency": gw_status.currency,
        }

    async def cancel_payment(
        self, payment_id: str, reason: str = "Cancelled by user"
    ) -> bool:
        """Cancel payment with BANGE."""
        return await self._gateway.cancel_payment(payment_id, reason)

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify BANGE webhook signature."""
        return self._gateway.verify_webhook_signature(payload, signature)

    def parse_webhook_data(
        self, payload: Dict[str, Any]
    ) -> Optional[BANGEWebhookData]:
        """
        Parse BANGE webhook payload into BANGEWebhookData (legacy model).
        For new code, use gateway.parse_webhook_data() which returns GatewayWebhookData.
        """
        try:
            return BANGEWebhookData(
                payment_id=payload["payment_id"],
                reference=payload["reference"],
                status=payload["status"],
                amount=Decimal(str(payload["amount"])),
                currency=payload["currency"],
                customer_email=payload.get("customer", {}).get("email"),
                paid_at=datetime.fromisoformat(payload["paid_at"])
                if payload.get("paid_at") else None,
                metadata=payload.get("metadata", {}),
            )
        except Exception as e:
            logger.error(f"Error parsing BANGE webhook data: {e}")
            return None

    async def get_payment_methods(self) -> List[Dict[str, Any]]:
        """Get available payment methods from BANGE."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    f"{self.base_url}/payment-methods",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                if response.status_code == 200:
                    return response.json().get("payment_methods", [])
                return []
        except Exception as e:
            logger.error(f"Error getting BANGE payment methods: {e}")
            return []

    async def get_exchange_rates(self) -> Dict[str, Decimal]:
        """Get current exchange rates from BANGE."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    f"{self.base_url}/exchange-rates",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                if response.status_code == 200:
                    rates_data = response.json()
                    return {
                        currency: Decimal(str(rate))
                        for currency, rate in rates_data.get("rates", {}).items()
                    }
                return {}
        except Exception as e:
            logger.error(f"Error getting BANGE exchange rates: {e}")
            return {}

    def map_bange_status_to_internal(self, bange_status: str) -> PaymentStatus:
        """Map BANGE payment status to internal PaymentStatus enum."""
        status_mapping = {
            "pending": PaymentStatus.PENDING,
            "processing": PaymentStatus.PROCESSING,
            "completed": PaymentStatus.COMPLETED,
            "paid": PaymentStatus.COMPLETED,
            "success": PaymentStatus.COMPLETED,
            "failed": PaymentStatus.FAILED,
            "error": PaymentStatus.FAILED,
            "cancelled": PaymentStatus.CANCELLED,
            "expired": PaymentStatus.FAILED,
            "refunded": PaymentStatus.REFUNDED,
        }
        return status_mapping.get(bange_status.lower(), PaymentStatus.FAILED)

    async def health_check(self) -> bool:
        """Check BANGE API health."""
        return await self._gateway.health_check()


# Global BANGE service instance (backward compat)
bange_service = BANGEService()
