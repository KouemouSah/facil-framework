"""
Ecobank Gateway — Implements GatewayServiceBase for Ecobank Unified API.

Integration with https://developer.ecobank.com (sandbox)
Production: https://ecobank.com/corporateapi (requires Go Live approval)

Authentication: OAuth2 client_credentials → Bearer token (auto-refresh)
Signature: HMAC-SHA256 for webhook validation
Collections API: Receiving payments from customers

Environment variables:
    ECOBANK_API_URL          → Base URL (default: https://developer.ecobank.com)
    ECOBANK_CLIENT_ID        → Client ID (from Ecobank developer portal)
    ECOBANK_CLIENT_SECRET    → Client Secret (from Ecobank developer portal)
    ECOBANK_WEBHOOK_SECRET   → HMAC secret for webhook signature validation

Security features:
    - Token auto-refresh with safety margin (5 min before expiry)
    - Thread-safe token caching (asyncio Lock)
    - HMAC-SHA256 constant-time signature comparison
    - Request timeout (30s default)
    - Exponential backoff retry on transient errors (503, 429, timeout)
    - Structured logging with correlation IDs
"""

import httpx
import hashlib
import hmac
import asyncio
from typing import Dict, List, Optional, Any
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from loguru import logger

from app.config import get_settings

from .base import (
    GatewayServiceBase,
    GatewayPaymentRequest,
    GatewayPaymentResponse,
    GatewayStatusResponse,
    GatewayWebhookData,
)


# Transient HTTP status codes that warrant retry
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

# Maximum retries for transient failures
_MAX_RETRIES = 3

# Base delay for exponential backoff (seconds)
_BASE_RETRY_DELAY = 1.0


class EcobankGateway(GatewayServiceBase):
    """
    Ecobank Unified API gateway integration.

    Handles Collections (receiving payments) via Ecobank's Corporate API.
    Supports: Mobile Money, Card, Bank Transfer.

    Token lifecycle:
        1. First API call → fetch token from /corporateapi/user/token
        2. Token cached with TTL (refreshed 5 min before expiry)
        3. Thread-safe via asyncio.Lock

    Payment flow:
        1. create_payment() → POST /corporateapi/merchant/payment
        2. Bank returns redirect URL for customer payment page
        3. Customer completes payment on Ecobank page
        4. Ecobank sends webhook → parse_webhook_data()
        5. verify_payment() → GET /corporateapi/merchant/payment/{id}
    """

    bank_code = "ECOBANK"
    bank_name = "Ecobank Guinée Équatoriale"

    def __init__(self):
        settings = get_settings()
        self.base_url = (
            settings.ECOBANK_API_URL or "https://developer.ecobank.com"
        )
        self.client_id = settings.ECOBANK_CLIENT_ID or ""
        self.client_secret = settings.ECOBANK_CLIENT_SECRET or ""
        self.webhook_secret = settings.ECOBANK_WEBHOOK_SECRET or ""
        self.timeout = 30

        # Token management (thread-safe)
        self._token: Optional[str] = None
        self._token_expires: Optional[datetime] = None
        self._token_lock = asyncio.Lock()

        # Persistent HTTP client (connection pooling)
        self._client: Optional[httpx.AsyncClient] = None

    # =========================================================================
    # HTTP CLIENT (persistent, connection-pooled)
    # =========================================================================

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create persistent httpx client with connection pooling."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                limits=httpx.Limits(
                    max_connections=20, max_keepalive_connections=10
                ),
            )
        return self._client

    # =========================================================================
    # TOKEN MANAGEMENT (OAuth2 client_credentials)
    # =========================================================================

    async def _get_token(self) -> str:
        """
        Get a valid Bearer token, auto-refreshing if expired.

        Uses asyncio.Lock to prevent concurrent token refresh requests.
        Refreshes 5 minutes before actual expiry to avoid edge cases.

        Returns:
            Valid Bearer token string

        Raises:
            RuntimeError: If token generation fails after retries
        """
        async with self._token_lock:
            # Check if current token is still valid (with 5-min safety margin)
            if (
                self._token
                and self._token_expires
                and datetime.now(timezone.utc) < self._token_expires - timedelta(minutes=5)
            ):
                return self._token

            # Fetch new token
            correlation_id = str(uuid4())[:8]
            logger.info(
                f"[ECOBANK:{correlation_id}] Refreshing OAuth2 token"
            )

            token_data = await self._fetch_token(correlation_id)
            self._token = token_data["token"]
            # Default 1 hour TTL if not specified
            ttl_seconds = token_data.get("expires_in", 3600)
            self._token_expires = (
                datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
            )

            logger.info(
                f"[ECOBANK:{correlation_id}] Token refreshed, "
                f"expires in {ttl_seconds}s"
            )
            return self._token

    async def _fetch_token(self, correlation_id: str) -> Dict[str, Any]:
        """
        Call Ecobank token endpoint with retry on transient errors.

        POST /corporateapi/user/token
        Body: {"userId": "...", "password": "..."}

        Returns:
            Dict with "token" and optionally "expires_in"

        Raises:
            RuntimeError: If all retries exhausted
        """
        url = f"{self.base_url}/corporateapi/user/token"

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                client = await self._get_client()
                response = await client.post(
                    url,
                    json={
                        "userId": self.client_id,
                        "password": self.client_secret,
                    },
                    headers={"Content-Type": "application/json"},
                )

                if response.status_code == 200:
                    data = response.json()
                    token = data.get("token") or data.get("access_token")
                    if not token:
                        raise RuntimeError(
                            f"[ECOBANK:{correlation_id}] "
                            f"Token response missing 'token' field: "
                            f"{list(data.keys())}"
                        )
                    return {
                        "token": token,
                        "expires_in": data.get(
                            "expires_in", data.get("expiresIn", 3600)
                        ),
                    }

                if response.status_code in _RETRYABLE_STATUS_CODES:
                    delay = _BASE_RETRY_DELAY * (2 ** (attempt - 1))
                    logger.warning(
                        f"[ECOBANK:{correlation_id}] Token request "
                        f"failed ({response.status_code}), "
                        f"retry {attempt}/{_MAX_RETRIES} in {delay}s"
                    )
                    await asyncio.sleep(delay)
                    continue

                raise RuntimeError(
                    f"[ECOBANK:{correlation_id}] Token request failed: "
                    f"{response.status_code} - {response.text[:200]}"
                )

            except httpx.TimeoutException:
                if attempt < _MAX_RETRIES:
                    delay = _BASE_RETRY_DELAY * (2 ** (attempt - 1))
                    logger.warning(
                        f"[ECOBANK:{correlation_id}] Token request "
                        f"timeout, retry {attempt}/{_MAX_RETRIES} in {delay}s"
                    )
                    await asyncio.sleep(delay)
                else:
                    raise RuntimeError(
                        f"[ECOBANK:{correlation_id}] "
                        f"Token request timeout after {_MAX_RETRIES} retries"
                    )

        raise RuntimeError(
            f"[ECOBANK:{correlation_id}] "
            f"Token request failed after {_MAX_RETRIES} retries"
        )

    # =========================================================================
    # GATEWAY API METHODS
    # =========================================================================

    async def create_payment(
        self, request: GatewayPaymentRequest
    ) -> GatewayPaymentResponse:
        """
        Initiate payment via Ecobank Collections API.

        POST /corporateapi/merchant/payment
        Auth: Bearer token
        Body: Payment details mapped to Ecobank format

        Returns GatewayPaymentResponse with redirect URL for customer.
        """
        correlation_id = str(uuid4())[:8]

        try:
            token = await self._get_token()

            # Map to Ecobank request format
            ecobank_payload = {
                "paymentDetails": {
                    "requestId": request.reference,
                    "productCode": "ENP",  # Ecobank Payment
                    "amount": str(request.amount),
                    "currency": request.currency,
                    "locale": "es",
                    "orderInfo": request.description[:100],
                    "returnUrl": request.return_url,
                    "callbackUrl": request.callback_url,
                },
                "merchantDetails": {
                    "accessCode": self.client_id,
                },
                "customerDetails": {
                    "email": request.customer_email or "",
                    "phone": request.customer_phone or "",
                },
                "metadata": request.metadata or {},
            }

            response = await self._api_request(
                method="POST",
                path="/corporateapi/merchant/payment",
                token=token,
                json_data=ecobank_payload,
                correlation_id=correlation_id,
            )

            if response and response.get("response_code") in ("00", "0", "000"):
                content = response.get("response_content", {})
                return GatewayPaymentResponse(
                    success=True,
                    external_id=content.get(
                        "transactionId",
                        content.get("paymentId", request.reference),
                    ),
                    redirect_url=content.get(
                        "paymentUrl",
                        content.get("redirectUrl"),
                    ),
                    status="pending",
                    expires_at=(
                        datetime.now(timezone.utc) + timedelta(hours=1)
                    ),
                )
            else:
                error_msg = (
                    response.get("response_message", "Unknown error")
                    if response
                    else "No response from Ecobank API"
                )
                logger.error(
                    f"[ECOBANK:{correlation_id}] Payment creation failed: "
                    f"{error_msg}"
                )
                return GatewayPaymentResponse(
                    success=False,
                    error=f"Ecobank error: {error_msg}",
                )

        except Exception as e:
            logger.error(
                f"[ECOBANK:{correlation_id}] create_payment error: {e}"
            )
            return GatewayPaymentResponse(
                success=False,
                error=str(e),
            )

    async def verify_payment(
        self, external_reference: str
    ) -> GatewayStatusResponse:
        """
        Check payment status with Ecobank API.

        POST /corporateapi/merchant/payment/status
        Body: {"requestId": "..."}
        """
        correlation_id = str(uuid4())[:8]

        try:
            token = await self._get_token()

            response = await self._api_request(
                method="POST",
                path="/corporateapi/merchant/payment/status",
                token=token,
                json_data={"requestId": external_reference},
                correlation_id=correlation_id,
            )

            if response:
                content = response.get("response_content", {})
                bank_status = content.get("status", "unknown")
                internal_status = self.map_status_to_internal(bank_status)

                paid_at = None
                if content.get("transactionDate"):
                    try:
                        paid_at = datetime.fromisoformat(
                            content["transactionDate"]
                        )
                    except (ValueError, TypeError):
                        pass

                return GatewayStatusResponse(
                    external_id=external_reference,
                    status=internal_status,
                    paid=internal_status == "completed",
                    paid_at=paid_at,
                    amount=(
                        Decimal(str(content["amount"]))
                        if content.get("amount")
                        else None
                    ),
                    currency=content.get("currency", "XAF"),
                    raw_data=response,
                )
            else:
                return GatewayStatusResponse(
                    external_id=external_reference,
                    status="failed",
                    error="No response from Ecobank API",
                )

        except Exception as e:
            logger.error(
                f"[ECOBANK:{correlation_id}] verify_payment error: {e}"
            )
            return GatewayStatusResponse(
                external_id=external_reference,
                status="failed",
                error=str(e),
            )

    def verify_webhook_signature(
        self, payload: bytes, signature: str
    ) -> bool:
        """
        Validate Ecobank webhook HMAC-SHA256 signature.

        Expected header: X-Ecobank-Signature: sha256={hex_digest}
        """
        try:
            if not self.webhook_secret:
                logger.warning("Ecobank webhook secret not configured")
                return False

            expected = hmac.new(
                self.webhook_secret.encode("utf-8"),
                payload,
                hashlib.sha256,
            ).hexdigest()

            # Support both formats: raw hex or sha256= prefixed
            signature_clean = signature
            if signature.startswith("sha256="):
                signature_clean = signature[7:]

            return hmac.compare_digest(expected, signature_clean)

        except Exception as e:
            logger.error(f"Error verifying Ecobank webhook signature: {e}")
            return False

    def parse_webhook_data(
        self, payload: Dict[str, Any]
    ) -> GatewayWebhookData:
        """
        Parse Ecobank webhook notification into standard format.

        Ecobank webhook payload structure:
        {
            "transactionId": "...",
            "requestId": "...",          ← our payment_reference
            "status": "SUCCESS|FAILED",
            "amount": "...",
            "currency": "XAF",
            "transactionDate": "...",
            "customerPhone": "...",
            ...
        }
        """
        transaction_date = None
        if payload.get("transactionDate"):
            try:
                transaction_date = datetime.fromisoformat(
                    payload["transactionDate"]
                )
            except (ValueError, TypeError):
                pass

        return GatewayWebhookData(
            bank_code=self.bank_code,
            bank_reference=payload.get(
                "transactionId", payload.get("paymentId", "")
            ),
            merchant_reference=payload.get(
                "requestId", payload.get("merchantRef", "")
            ),
            status=self._map_webhook_status(
                payload.get("status", "unknown")
            ),
            amount=Decimal(str(payload.get("amount", 0))),
            currency=payload.get("currency", "XAF"),
            transaction_date=transaction_date,
            account_number=payload.get("accountNumber"),
            account_holder_name=payload.get("accountName"),
            customer_phone=payload.get("customerPhone"),
            raw_data=payload,
        )

    def get_supported_methods(self) -> List[str]:
        """Ecobank supports Mobile Money, Card, and Bank Transfer."""
        return ["mobile_money", "card", "bank_transfer"]

    def get_webhook_signature_header(self) -> str:
        """Ecobank webhook signature header name."""
        return "X-Ecobank-Signature"

    async def health_check(self) -> bool:
        """
        Check Ecobank API health by attempting token generation.

        If we can get a valid token, the API is reachable.
        """
        try:
            token = await self._get_token()
            return bool(token)
        except Exception as e:
            logger.error(f"Ecobank health check failed: {e}")
            return False

    async def cancel_payment(
        self, external_reference: str, reason: str = ""
    ) -> bool:
        """
        Cancel payment with Ecobank.

        Note: Not all payment types support cancellation.
        """
        correlation_id = str(uuid4())[:8]
        try:
            token = await self._get_token()
            response = await self._api_request(
                method="POST",
                path="/corporateapi/merchant/payment/cancel",
                token=token,
                json_data={
                    "requestId": external_reference,
                    "reason": reason or "Cancelled by merchant",
                },
                correlation_id=correlation_id,
            )
            if response and response.get("response_code") in (
                "00", "0", "000"
            ):
                logger.info(
                    f"[ECOBANK:{correlation_id}] Payment "
                    f"{external_reference} cancelled"
                )
                return True
            return False
        except Exception as e:
            logger.error(
                f"[ECOBANK:{correlation_id}] cancel_payment error: {e}"
            )
            return False

    def map_status_to_internal(self, bank_status: str) -> str:
        """Map Ecobank status strings to internal status."""
        status_map = {
            # Ecobank success statuses
            "success": "completed",
            "successful": "completed",
            "completed": "completed",
            "paid": "completed",
            "approved": "completed",
            # Ecobank pending statuses
            "pending": "pending",
            "processing": "processing",
            "initiated": "pending",
            "awaiting_payment": "pending",
            # Ecobank failure statuses
            "failed": "failed",
            "declined": "failed",
            "rejected": "failed",
            "error": "failed",
            "expired": "failed",
            "timeout": "failed",
            # Ecobank cancellation
            "cancelled": "cancelled",
            "reversed": "refunded",
            "refunded": "refunded",
        }
        return status_map.get(bank_status.lower(), "failed")

    # =========================================================================
    # PRIVATE HELPERS
    # =========================================================================

    async def _api_request(
        self,
        method: str,
        path: str,
        token: str,
        json_data: Optional[Dict] = None,
        correlation_id: str = "",
    ) -> Optional[Dict[str, Any]]:
        """
        Make an authenticated API request to Ecobank with retry logic.

        Retries on: 429 (rate limit), 500-504 (server errors), timeouts.
        Uses exponential backoff: 1s, 2s, 4s.

        Args:
            method: HTTP method (GET, POST)
            path: API path (e.g., /corporateapi/merchant/payment)
            token: Bearer token
            json_data: Request body (for POST)
            correlation_id: For structured logging

        Returns:
            Parsed JSON response or None on failure
        """
        url = f"{self.base_url}{path}"
        # Origin header is MANDATORY for all Ecobank API requests
        settings = get_settings()
        origin = settings.API_BASE_URL or "https://api.taxasge.com"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Origin": origin,
            "X-Correlation-Id": correlation_id,
        }

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                client = await self._get_client()
                if method.upper() == "POST":
                    response = await client.post(
                        url, json=json_data, headers=headers
                    )
                else:
                    response = await client.get(url, headers=headers)

                if response.status_code in (200, 201):
                    return response.json()

                # Token expired → refresh and retry
                if response.status_code == 401:
                    logger.warning(
                        f"[ECOBANK:{correlation_id}] 401 Unauthorized, "
                        f"refreshing token (attempt {attempt})"
                    )
                    # Force token refresh
                    self._token = None
                    self._token_expires = None
                    token = await self._get_token()
                    headers["Authorization"] = f"Bearer {token}"
                    continue

                # Retryable errors
                if response.status_code in _RETRYABLE_STATUS_CODES:
                    delay = _BASE_RETRY_DELAY * (2 ** (attempt - 1))
                    logger.warning(
                        f"[ECOBANK:{correlation_id}] {method} {path} "
                        f"failed ({response.status_code}), "
                        f"retry {attempt}/{_MAX_RETRIES} in {delay}s"
                    )
                    await asyncio.sleep(delay)
                    continue

                # Non-retryable error
                logger.error(
                    f"[ECOBANK:{correlation_id}] {method} {path} "
                    f"failed: {response.status_code} - "
                    f"{response.text[:300]}"
                )
                # Try to parse error response
                try:
                    return response.json()
                except Exception:
                    return None

            except httpx.TimeoutException:
                if attempt < _MAX_RETRIES:
                    delay = _BASE_RETRY_DELAY * (2 ** (attempt - 1))
                    logger.warning(
                        f"[ECOBANK:{correlation_id}] {method} {path} "
                        f"timeout, retry {attempt}/{_MAX_RETRIES} in {delay}s"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"[ECOBANK:{correlation_id}] {method} {path} "
                        f"timeout after {_MAX_RETRIES} retries"
                    )
                    return None

            except httpx.ConnectError as e:
                logger.error(
                    f"[ECOBANK:{correlation_id}] Connection error: {e}"
                )
                if attempt < _MAX_RETRIES:
                    delay = _BASE_RETRY_DELAY * (2 ** (attempt - 1))
                    await asyncio.sleep(delay)
                else:
                    return None

        logger.error(
            f"[ECOBANK:{correlation_id}] {method} {path} "
            f"failed after {_MAX_RETRIES} retries"
        )
        return None

    @staticmethod
    def _map_webhook_status(ecobank_status: str) -> str:
        """Map Ecobank webhook status to standard: success/failed/pending."""
        mapping = {
            "success": "success",
            "successful": "success",
            "completed": "success",
            "paid": "success",
            "approved": "success",
            "failed": "failed",
            "declined": "failed",
            "rejected": "failed",
            "error": "failed",
            "expired": "failed",
            "cancelled": "failed",
            "pending": "pending",
            "processing": "pending",
            "initiated": "pending",
        }
        return mapping.get(ecobank_status.lower(), "failed")
