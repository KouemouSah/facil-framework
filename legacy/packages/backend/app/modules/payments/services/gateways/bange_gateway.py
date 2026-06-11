"""
BANGE Gateway — Implements GatewayServiceBase for BANGE bank API.

Extracted from bange_service.py to comply with multi-gateway architecture.
API communication with https://api.bange.gq (BANGE payment gateway).

Authentication: Bearer token (API key)
Signature: HMAC-SHA256 on canonical request string
Webhook: HMAC-SHA256 with separate webhook_secret
"""

import httpx
import hashlib
import hmac
import json
from typing import Dict, List, Optional, Any
from decimal import Decimal
from datetime import datetime
from loguru import logger

from app.config import get_settings

from .base import (
    GatewayServiceBase,
    GatewayPaymentRequest,
    GatewayPaymentResponse,
    GatewayStatusResponse,
    GatewayWebhookData,
)


class BANGEGateway(GatewayServiceBase):
    """
    BANGE bank gateway integration.

    Handles API communication with BANGE payment gateway for:
    - Mobile Money (MTN, Orange)
    - Card payments
    - Bank transfers

    Credentials loaded from environment:
    - BANGE_API_URL: API base URL (default: https://api.bange.gq)
    - BANGE_MERCHANT_ID: Merchant identifier
    - BANGE_API_KEY: Bearer token for API auth + HMAC signing
    - BANGE_WEBHOOK_SECRET: HMAC secret for webhook signature validation
    """

    bank_code = "BANGE"
    bank_name = "Banco Nacional de Guinea Ecuatorial"

    def __init__(self):
        settings = get_settings()
        self.base_url = settings.BANGE_API_URL or "https://api.bange.gq"
        self.merchant_id = settings.BANGE_MERCHANT_ID
        self.api_key = settings.BANGE_API_KEY
        self.webhook_secret = settings.BANGE_WEBHOOK_SECRET
        self.timeout = 30

    async def create_payment(
        self, request: GatewayPaymentRequest
    ) -> GatewayPaymentResponse:
        """
        Initiate payment with BANGE API.

        POST {base_url}/payments
        - HMAC-SHA256 signature on canonical request
        - Bearer token auth
        - Returns payment URL for redirect flow
        """
        try:
            request_data = {
                "merchant_id": self.merchant_id,
                "amount": float(request.amount),
                "currency": request.currency,
                "description": request.description,
                "reference": request.reference,
                "callback_url": request.callback_url,
                "return_url": request.return_url,
                "customer": {
                    "email": request.customer_email,
                    "phone": request.customer_phone,
                },
                "metadata": request.metadata or {},
                "expires_in": 3600,  # 1 hour expiration
            }

            signature = self._generate_signature(request_data)
            request_data["signature"] = signature

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/payments",
                    json=request_data,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                )

                if response.status_code == 201:
                    data = response.json()
                    expires_at = None
                    if data.get("expires_at"):
                        expires_at = datetime.fromisoformat(data["expires_at"])

                    return GatewayPaymentResponse(
                        success=True,
                        external_id=data["payment_id"],
                        redirect_url=data["payment_url"],
                        status=data["status"],
                        expires_at=expires_at,
                    )
                else:
                    logger.error(
                        f"BANGE payment creation failed: "
                        f"{response.status_code} - {response.text}"
                    )
                    return GatewayPaymentResponse(
                        success=False,
                        error=f"BANGE API error: {response.status_code}",
                    )

        except Exception as e:
            logger.error(f"Error creating BANGE payment: {e}")
            return GatewayPaymentResponse(
                success=False,
                error=str(e),
            )

    async def verify_payment(
        self, external_reference: str
    ) -> GatewayStatusResponse:
        """
        Check payment status with BANGE API.

        GET {base_url}/payments/{payment_id}
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/payments/{external_reference}",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    bank_status = data.get("status", "unknown")
                    internal_status = self.map_status_to_internal(bank_status)

                    paid_at = None
                    if data.get("paid_at"):
                        paid_at = datetime.fromisoformat(data["paid_at"])

                    return GatewayStatusResponse(
                        external_id=external_reference,
                        status=internal_status,
                        paid=internal_status == "completed",
                        paid_at=paid_at,
                        amount=Decimal(str(data["amount"])) if data.get("amount") else None,
                        currency=data.get("currency", "XAF"),
                        raw_data=data,
                    )
                else:
                    logger.error(
                        f"BANGE payment verification failed: "
                        f"{response.status_code} - {response.text}"
                    )
                    return GatewayStatusResponse(
                        external_id=external_reference,
                        status="failed",
                        error=f"BANGE API error: {response.status_code}",
                    )

        except Exception as e:
            logger.error(f"Error verifying BANGE payment {external_reference}: {e}")
            return GatewayStatusResponse(
                external_id=external_reference,
                status="failed",
                error=str(e),
            )

    def verify_webhook_signature(
        self, payload: bytes, signature: str
    ) -> bool:
        """
        Validate BANGE webhook HMAC-SHA256 signature.

        Expected format: sha256={hex_digest}
        """
        try:
            if not self.webhook_secret:
                logger.warning("BANGE webhook secret not configured")
                return False

            expected_signature = hmac.new(
                self.webhook_secret.encode("utf-8"),
                payload,
                hashlib.sha256,
            ).hexdigest()

            return hmac.compare_digest(
                f"sha256={expected_signature}",
                signature,
            )

        except Exception as e:
            logger.error(f"Error verifying BANGE webhook signature: {e}")
            return False

    def parse_webhook_data(
        self, payload: Dict[str, Any]
    ) -> GatewayWebhookData:
        """
        Parse BANGE webhook payload into standard GatewayWebhookData.

        BANGE payload fields:
        - payment_id: Bank's transaction ID
        - reference: Our payment_reference (merchant_reference)
        - status: "completed", "failed", "cancelled"
        - amount, currency, paid_at
        - customer.email, customer.phone
        """
        transaction_date = None
        if payload.get("paid_at"):
            try:
                transaction_date = datetime.fromisoformat(payload["paid_at"])
            except (ValueError, TypeError):
                pass

        return GatewayWebhookData(
            bank_code=self.bank_code,
            bank_reference=payload.get("payment_id", ""),
            merchant_reference=payload.get("reference", ""),
            status=self._map_webhook_status(payload.get("status", "unknown")),
            amount=Decimal(str(payload.get("amount", 0))),
            currency=payload.get("currency", "XAF"),
            transaction_date=transaction_date,
            customer_phone=payload.get("customer", {}).get("phone"),
            raw_data=payload,
        )

    def get_supported_methods(self) -> List[str]:
        """BANGE supports Mobile Money, Card, and Bank Transfer."""
        return ["mobile_money", "card", "bank_transfer"]

    def get_webhook_signature_header(self) -> str:
        """BANGE uses X-Bange-Signature header."""
        return "X-Bange-Signature"

    async def health_check(self) -> bool:
        """Check BANGE API health status."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self.base_url}/health",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                    },
                )
                return response.status_code == 200

        except Exception as e:
            logger.error(f"BANGE health check failed: {e}")
            return False

    async def cancel_payment(
        self, external_reference: str, reason: str = ""
    ) -> bool:
        """Cancel a pending payment with BANGE."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/payments/{external_reference}/cancel",
                    json={"reason": reason or "Cancelled by user"},
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                )
                if response.status_code in [200, 204]:
                    logger.info(f"BANGE payment {external_reference} cancelled")
                    return True
                else:
                    logger.error(
                        f"BANGE cancellation failed: "
                        f"{response.status_code} - {response.text}"
                    )
                    return False

        except Exception as e:
            logger.error(f"Error cancelling BANGE payment {external_reference}: {e}")
            return False

    # === Private Helpers ===

    def _generate_signature(self, data: Dict[str, Any]) -> str:
        """Generate HMAC-SHA256 signature for BANGE API request."""
        try:
            canonical_string = self._create_canonical_string(data)
            signature = hmac.new(
                self.api_key.encode("utf-8"),
                canonical_string.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            return signature
        except Exception as e:
            logger.error(f"Error generating BANGE signature: {e}")
            return ""

    def _create_canonical_string(self, data: Dict[str, Any]) -> str:
        """Create canonical string from sorted request fields."""
        sorted_keys = sorted(data.keys())
        canonical_parts = []

        for key in sorted_keys:
            if key != "signature":
                value = data[key]
                if isinstance(value, dict):
                    value = json.dumps(value, sort_keys=True, separators=(",", ":"))
                canonical_parts.append(f"{key}={value}")

        return "&".join(canonical_parts)

    @staticmethod
    def _map_webhook_status(bange_status: str) -> str:
        """Map BANGE webhook status to standard: success/failed/pending."""
        mapping = {
            "completed": "success",
            "paid": "success",
            "success": "success",
            "failed": "failed",
            "error": "failed",
            "cancelled": "failed",
            "expired": "failed",
            "pending": "pending",
            "processing": "pending",
        }
        return mapping.get(bange_status.lower(), "failed")
