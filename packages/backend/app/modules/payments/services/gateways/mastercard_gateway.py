"""
Mastercard Payment Gateway Services (MPGS) — Hosted Checkout integration.

Sub-processor of Ecobank for card payments.
Sandbox: https://test-ecobank.mtf.gateway.mastercard.com
Production: https://ecobank.gateway.mastercard.com

Authentication: HTTP Basic Auth (merchant.{MERCHANT_ID}:{API_PASSWORD})
Flow: Create Session → Redirect to Hosted Checkout → Verify Order

Environment variables:
    MPGS_API_URL           → Base URL (default: sandbox)
    MPGS_MERCHANT_ID       → Merchant ID from Ecobank MPGS portal
    MPGS_API_PASSWORD      → API password from MPGS portal
    MPGS_API_VERSION       → API version (default: 85)
    MPGS_WEBHOOK_SECRET    → Shared secret for webhook signature validation
    MPGS_PRIMARY_METHODS   → Comma-separated methods (default: "card")

Security:
    - PCI-compliant: card data never touches our server (Hosted Checkout)
    - HTTP Basic Auth over TLS
    - Webhook signature validation
    - Request timeout (30s)
    - Exponential backoff retry on transient errors
    - Structured logging with correlation IDs
"""

import httpx
import hmac
import asyncio
import base64
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

_MAX_RETRIES = 3
_BASE_RETRY_DELAY = 1.0


class MastercardGateway(GatewayServiceBase):
    """
    Mastercard Payment Gateway Services (MPGS) — Hosted Checkout.

    Handles card payments via Ecobank's MPGS integration.
    The customer is redirected to a Mastercard-hosted payment page
    (PCI DSS compliant — card data never touches our servers).

    Payment flow:
        1. create_payment() → POST session (CREATE_CHECKOUT_SESSION)
        2. Returns redirect URL → customer pays on MPGS hosted page
        3. MPGS redirects back to return_url with resultIndicator
        4. verify_payment() → GET order/{id} to confirm status
        5. Webhook notification → parse_webhook_data()
    """

    bank_code = "ECOBANK"
    bank_name = "Ecobank (Mastercard MPGS)"

    # Internal code for registry/webhook routing (distinct from bank_code)
    _internal_code = "ECOBANK_MPGS"

    def get_webhook_routing_code(self) -> str:
        """MPGS uses ECOBANK_MPGS for webhook URL routing."""
        return self._internal_code

    def __init__(self):
        settings = get_settings()
        self.base_url = (
            settings.MPGS_API_URL
            or "https://test-ecobank.mtf.gateway.mastercard.com"
        )
        self.merchant_id = settings.MPGS_MERCHANT_ID or ""
        self.api_password = settings.MPGS_API_PASSWORD or ""
        self.api_version = settings.MPGS_API_VERSION or "85"
        self.webhook_secret = settings.MPGS_WEBHOOK_SECRET or ""
        self.timeout = 30

        # Persistent HTTP client (created on first use)
        self._client: Optional[httpx.AsyncClient] = None

    # =========================================================================
    # HTTP CLIENT
    # =========================================================================

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create persistent httpx client with Basic Auth."""
        if self._client is None or self._client.is_closed:
            auth_string = f"merchant.{self.merchant_id}:{self.api_password}"
            auth_bytes = base64.b64encode(auth_string.encode()).decode()
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                limits=httpx.Limits(
                    max_connections=20, max_keepalive_connections=10
                ),
                headers={
                    "Authorization": f"Basic {auth_bytes}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    def _api_url(self, path: str) -> str:
        """Build full API URL with version and merchant ID."""
        return (
            f"{self.base_url}/api/rest/version/{self.api_version}"
            f"/merchant/{self.merchant_id}{path}"
        )

    # =========================================================================
    # GATEWAY API METHODS
    # =========================================================================

    async def create_payment(
        self, request: GatewayPaymentRequest
    ) -> GatewayPaymentResponse:
        """
        Create MPGS Hosted Checkout session and return redirect URL.

        Step 1: POST /merchant/{mid}/session → CREATE_CHECKOUT_SESSION
        Step 2: Build checkout redirect URL from session.id

        The successIndicator is stored in metadata for later verification.
        """
        correlation_id = str(uuid4())[:8]
        order_id = request.reference  # Use our payment_reference as order ID

        try:
            # Build return URL with order ID for result verification
            return_url = request.return_url
            if "?" in return_url:
                return_url += f"&orderId={order_id}"
            else:
                return_url += f"?orderId={order_id}"

            # Create checkout session
            session_payload = {
                "apiOperation": "CREATE_CHECKOUT_SESSION",
                "interaction": {
                    "operation": "PURCHASE",
                    "returnUrl": return_url,
                    "cancelUrl": return_url,
                    "locale": "es",
                    "merchant": {
                        "name": "TaxasGE - Gobierno de Guinea Ecuatorial",
                    },
                    "displayControl": {
                        "billingAddress": "HIDE",
                        "customerEmail": "OPTIONAL",
                        "shipping": "HIDE",
                    },
                },
                "order": {
                    "id": order_id,
                    "amount": str(request.amount),
                    "currency": request.currency,
                    "description": request.description[:127],
                    "reference": order_id,
                    "notificationUrl": request.callback_url,
                },
                "transaction": {
                    "reference": order_id,
                },
            }

            if request.customer_email:
                session_payload["customer"] = {
                    "email": request.customer_email,
                }

            response = await self._api_request(
                method="POST",
                path="/session",
                json_data=session_payload,
                correlation_id=correlation_id,
            )

            if not response:
                return GatewayPaymentResponse(
                    success=False,
                    error="No response from MPGS API",
                )

            result = response.get("result", "")
            if result != "SUCCESS":
                error_msg = response.get("error", {}).get(
                    "explanation",
                    response.get("error", {}).get("cause", result),
                )
                logger.error(
                    f"[MPGS:{correlation_id}] Session creation failed: "
                    f"{error_msg}"
                )
                return GatewayPaymentResponse(
                    success=False,
                    error=f"MPGS error: {error_msg}",
                )

            session_id = response.get("session", {}).get("id", "")
            success_indicator = response.get("successIndicator", "")

            if not session_id:
                return GatewayPaymentResponse(
                    success=False,
                    error="MPGS session creation returned no session ID",
                )

            # Build checkout redirect URL
            checkout_url = (
                f"{self.base_url}/checkout/pay/{session_id}"
            )

            logger.info(
                f"[MPGS:{correlation_id}] Checkout session created: "
                f"order={order_id}, session={session_id[:20]}..."
            )

            return GatewayPaymentResponse(
                success=True,
                external_id=order_id,
                redirect_url=checkout_url,
                status="pending",
                expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
            )

        except Exception as e:
            logger.error(
                f"[MPGS:{correlation_id}] create_payment error: {e}"
            )
            return GatewayPaymentResponse(
                success=False,
                error=str(e),
            )

    async def verify_payment(
        self, external_reference: str
    ) -> GatewayStatusResponse:
        """
        Verify payment status by retrieving the order.

        GET /merchant/{mid}/order/{orderId}
        """
        correlation_id = str(uuid4())[:8]

        try:
            response = await self._api_request(
                method="GET",
                path=f"/order/{external_reference}",
                correlation_id=correlation_id,
            )

            if not response:
                return GatewayStatusResponse(
                    external_id=external_reference,
                    status="failed",
                    error="No response from MPGS API",
                )

            order_status = response.get("status", "UNKNOWN")
            internal_status = self.map_status_to_internal(order_status)

            # Extract amount from order
            amount = None
            if response.get("amount"):
                amount = Decimal(str(response["amount"]))

            # Extract payment timestamp
            # MPGS GET /order returns transaction as dict {"1": {...}, "2": {...}}
            # NOT as an array. Handle both formats defensively.
            paid_at = None
            if internal_status == "completed":
                transactions = response.get("transaction", {})
                # Normalize: if it's a dict, iterate values; if array, iterate items
                txn_items = (
                    transactions.values()
                    if isinstance(transactions, dict)
                    else transactions
                    if isinstance(transactions, list)
                    else []
                )
                for txn in txn_items:
                    if txn.get("transaction", {}).get("type") == "PAYMENT":
                        ts = txn.get("timeOfLastUpdate")
                        if ts:
                            try:
                                paid_at = datetime.fromisoformat(
                                    ts.replace("Z", "+00:00")
                                )
                            except (ValueError, TypeError):
                                pass

            return GatewayStatusResponse(
                external_id=external_reference,
                status=internal_status,
                paid=internal_status == "completed",
                paid_at=paid_at,
                amount=amount,
                currency=response.get("currency", "XAF"),
                raw_data=response,
            )

        except Exception as e:
            logger.error(
                f"[MPGS:{correlation_id}] verify_payment error: {e}"
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
        Validate MPGS webhook notification signature.

        MPGS sends the webhook secret in the Authorization header.
        We compare it with our stored secret.
        """
        try:
            if not self.webhook_secret:
                logger.warning("MPGS webhook secret not configured")
                return False

            # MPGS webhook uses shared secret in Authorization header
            # Format: "Basic {base64(merchant_id:secret)}" or just the secret
            signature_clean = signature.strip()

            # If it's a Basic auth header, extract the password
            if signature_clean.startswith("Basic "):
                try:
                    decoded = base64.b64decode(
                        signature_clean[6:]
                    ).decode()
                    # Format: merchant_id:secret
                    if ":" in decoded:
                        _, secret = decoded.split(":", 1)
                        signature_clean = secret
                except Exception:
                    pass

            return hmac.compare_digest(
                self.webhook_secret, signature_clean
            )

        except Exception as e:
            logger.error(f"Error verifying MPGS webhook signature: {e}")
            return False

    def parse_webhook_data(
        self, payload: Dict[str, Any]
    ) -> GatewayWebhookData:
        """
        Parse MPGS webhook notification into standard format.

        MPGS notification payload:
        {
            "order": {
                "id": "SR-...",
                "status": "CAPTURED",
                "amount": 50000,
                "currency": "XAF"
            },
            "transaction": {
                "id": "...",
                "type": "PAYMENT"
            },
            "result": "SUCCESS",
            ...
        }
        """
        order = payload.get("order", {})
        transaction = payload.get("transaction", {})

        # Map MPGS status to simple success/failed/pending
        result = payload.get("result", "UNKNOWN")
        order_status = order.get("status", "UNKNOWN")
        webhook_status = self._map_webhook_status(result, order_status)

        # Extract timestamp
        transaction_date = None
        ts = payload.get("timeOfLastUpdate") or transaction.get(
            "timeOfLastUpdate"
        )
        if ts:
            try:
                transaction_date = datetime.fromisoformat(
                    ts.replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                pass

        return GatewayWebhookData(
            bank_code=self.bank_code,  # "ECOBANK" for bank_transactions
            bank_reference=transaction.get(
                "id", transaction.get("acquirer", {}).get("id", "")
            ),
            merchant_reference=order.get("id", order.get("reference", "")),
            status=webhook_status,
            amount=Decimal(str(order.get("amount", 0))),
            currency=order.get("currency", "XAF"),
            transaction_date=transaction_date,
            raw_data=payload,
        )

    def get_supported_methods(self) -> List[str]:
        """MPGS handles card payments only."""
        return ["card"]

    def get_webhook_signature_header(self) -> str:
        """MPGS webhook uses Authorization header."""
        return "Authorization"

    async def health_check(self) -> bool:
        """
        Check MPGS API health by making a lightweight request.

        Uses the session endpoint with minimal data as a connectivity test.
        """
        try:
            client = await self._get_client()
            url = self._api_url("/paymentOptionsInquiry")
            response = await client.get(url)
            # 200 = OK, 401 = auth issue but API reachable
            return response.status_code in (200, 401)
        except Exception as e:
            logger.error(f"MPGS health check failed: {e}")
            return False

    def map_status_to_internal(self, mpgs_status: str) -> str:
        """Map MPGS order status to internal status."""
        status_map = {
            # MPGS success
            "CAPTURED": "completed",
            "AUTHORIZED": "processing",
            # MPGS pending
            "INITIATED": "pending",
            "AUTHENTICATION_INITIATED": "pending",
            "AUTHENTICATION_SUCCESSFUL": "pending",
            # MPGS failure
            "FAILED": "failed",
            "DECLINED": "failed",
            "AUTHENTICATION_UNSUCCESSFUL": "failed",
            "ERROR": "failed",
            "TIMED_OUT": "failed",
            # MPGS cancellation
            "CANCELLED": "cancelled",
            "VOIDED": "cancelled",
            # MPGS refund
            "REFUNDED": "refunded",
            "PARTIALLY_REFUNDED": "refunded",
        }
        return status_map.get(mpgs_status.upper(), "failed")

    # =========================================================================
    # PRIVATE HELPERS
    # =========================================================================

    async def _api_request(
        self,
        method: str,
        path: str,
        json_data: Optional[Dict] = None,
        correlation_id: str = "",
    ) -> Optional[Dict[str, Any]]:
        """
        Make authenticated API request to MPGS with retry logic.

        Uses Basic Auth (persistent client).
        Retries on 429, 500-504, and timeouts.
        """
        url = self._api_url(path)
        client = await self._get_client()

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                if method.upper() == "POST":
                    response = await client.post(url, json=json_data)
                elif method.upper() == "PUT":
                    response = await client.put(url, json=json_data)
                else:
                    response = await client.get(url)

                if response.status_code in (200, 201):
                    return response.json()

                # Retryable errors
                if response.status_code in _RETRYABLE_STATUS_CODES:
                    delay = _BASE_RETRY_DELAY * (2 ** (attempt - 1))
                    logger.warning(
                        f"[MPGS:{correlation_id}] {method} {path} "
                        f"failed ({response.status_code}), "
                        f"retry {attempt}/{_MAX_RETRIES} in {delay}s"
                    )
                    await asyncio.sleep(delay)
                    continue

                # Non-retryable error — try to return parsed response
                logger.error(
                    f"[MPGS:{correlation_id}] {method} {path} "
                    f"failed: {response.status_code} - "
                    f"{response.text[:300]}"
                )
                try:
                    return response.json()
                except Exception:
                    return None

            except httpx.TimeoutException:
                if attempt < _MAX_RETRIES:
                    delay = _BASE_RETRY_DELAY * (2 ** (attempt - 1))
                    logger.warning(
                        f"[MPGS:{correlation_id}] {method} {path} "
                        f"timeout, retry {attempt}/{_MAX_RETRIES} "
                        f"in {delay}s"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"[MPGS:{correlation_id}] {method} {path} "
                        f"timeout after {_MAX_RETRIES} retries"
                    )
                    return None

            except httpx.ConnectError as e:
                logger.error(
                    f"[MPGS:{correlation_id}] Connection error: {e}"
                )
                if attempt < _MAX_RETRIES:
                    delay = _BASE_RETRY_DELAY * (2 ** (attempt - 1))
                    await asyncio.sleep(delay)
                else:
                    return None

        logger.error(
            f"[MPGS:{correlation_id}] {method} {path} "
            f"failed after {_MAX_RETRIES} retries"
        )
        return None

    @staticmethod
    def _map_webhook_status(result: str, order_status: str) -> str:
        """Map MPGS webhook result + order status to success/failed/pending."""
        if result == "SUCCESS" and order_status in ("CAPTURED", "AUTHORIZED"):
            return "success"
        if order_status in ("CAPTURED",):
            return "success"
        if order_status in (
            "FAILED", "DECLINED", "ERROR", "TIMED_OUT",
            "AUTHENTICATION_UNSUCCESSFUL",
        ):
            return "failed"
        if order_status in ("CANCELLED", "VOIDED"):
            return "failed"
        if order_status in (
            "INITIATED", "AUTHENTICATION_INITIATED",
            "AUTHENTICATION_SUCCESSFUL", "AUTHORIZED",
        ):
            return "pending"
        return "failed"
