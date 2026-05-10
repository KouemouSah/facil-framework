"""
Gateway Service Base — Abstract contract for all bank API integrations.

Each bank (BANGE, Ecobank, BGFI, etc.) implements this interface.
The GatewayProcessor uses it to orchestrate payments generically.

Architecture:
    GatewayServiceBase (abstract)
    ├── BANGEGateway      → https://api.bange.gq
    ├── EcobankGateway    → https://developer.ecobank.com
    └── (future banks)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
from decimal import Decimal


# =============================================================================
# STANDARD DATACLASSES (gateway-agnostic)
# =============================================================================

@dataclass
class GatewayPaymentRequest:
    """
    Standard payment request sent to any bank gateway.
    Each gateway maps this to its bank-specific API format.
    """
    amount: Decimal
    currency: str                       # e.g., "XAF"
    reference: str                      # Our payment_reference (SR-...)
    description: str                    # Payment description
    callback_url: str                   # Our webhook endpoint URL
    return_url: str                     # Frontend redirect after payment
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GatewayPaymentResponse:
    """
    Standard response from bank gateway after payment initiation.
    """
    success: bool
    external_id: str = ""               # Bank's payment/transaction ID
    redirect_url: Optional[str] = None  # For redirect-based flows (user goes to bank page)
    status: str = "pending"             # Bank-specific status string
    expires_at: Optional[datetime] = None
    error: Optional[str] = None


@dataclass
class GatewayStatusResponse:
    """
    Standard response from bank gateway for payment status check.
    """
    external_id: str                    # Bank's payment/transaction ID
    status: str                         # e.g., "completed", "pending", "failed"
    paid: bool = False
    paid_at: Optional[datetime] = None
    amount: Optional[Decimal] = None
    currency: str = "XAF"
    error: Optional[str] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GatewayWebhookData:
    """
    Standard webhook data parsed from bank-specific notification.
    Used to create bank_transactions and auto-reconcile.
    """
    bank_code: str                      # e.g., "BANGE", "ECOBANK"
    bank_reference: str                 # Bank's transaction ID (UNIQUE with bank_code)
    merchant_reference: str             # Our payment_reference (for auto-reconciliation)
    status: str                         # "success", "failed", "pending"
    amount: Decimal
    currency: str = "XAF"
    transaction_date: Optional[datetime] = None
    account_number: Optional[str] = None
    account_holder_name: Optional[str] = None
    customer_phone: Optional[str] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# ABSTRACT BASE CLASS
# =============================================================================

class GatewayServiceBase(ABC):
    """
    Abstract base for all bank gateway API integrations.

    Each concrete gateway (BANGEGateway, EcobankGateway, etc.) implements
    this interface. The GatewayProcessor uses it polymorphically.

    Responsibilities:
    - API communication with the bank
    - Request/response format translation
    - Webhook signature validation
    - Webhook payload parsing

    NOT responsible for:
    - Creating service_payment records (GatewayProcessor does this)
    - Event publishing (GatewayProcessor does this)
    - Assignment outbox (GatewayProcessor does this)
    """

    # Subclasses MUST set these
    bank_code: str = ""                 # e.g., "BANGE", "ECOBANK"
    bank_name: str = ""                 # e.g., "Banco Nacional de Guinea Ecuatorial"

    @abstractmethod
    async def create_payment(
        self, request: GatewayPaymentRequest
    ) -> GatewayPaymentResponse:
        """
        Initiate payment with bank API.

        Args:
            request: Standard payment request

        Returns:
            GatewayPaymentResponse with redirect_url (if redirect flow)
            or confirmation (if inline flow)
        """
        ...

    @abstractmethod
    async def verify_payment(
        self, external_reference: str
    ) -> GatewayStatusResponse:
        """
        Check payment status with bank API.

        Args:
            external_reference: Bank's payment/transaction ID

        Returns:
            GatewayStatusResponse with current status
        """
        ...

    @abstractmethod
    def verify_webhook_signature(
        self, payload: bytes, signature: str
    ) -> bool:
        """
        Validate incoming webhook signature (bank-specific).

        Args:
            payload: Raw webhook body bytes
            signature: Signature from request headers

        Returns:
            True if signature is valid
        """
        ...

    @abstractmethod
    def parse_webhook_data(
        self, payload: Dict[str, Any]
    ) -> GatewayWebhookData:
        """
        Parse bank-specific webhook payload into standard format.

        Args:
            payload: Parsed JSON from webhook body

        Returns:
            GatewayWebhookData in standard format
        """
        ...

    @abstractmethod
    def get_supported_methods(self) -> List[str]:
        """
        Return payment method codes this gateway handles.

        Returns:
            List of PaymentMethod values (e.g., ["mobile_money", "card", "bank_transfer"])
        """
        ...

    def get_webhook_routing_code(self) -> str:
        """
        Return the code used for webhook URL routing.

        Default: same as bank_code. Override in subclasses where the
        registry key differs from bank_code (e.g., MPGS uses bank_code
        "ECOBANK" for bank_transactions but "ECOBANK_MPGS" for routing).

        Returns:
            Routing code for webhook URL path (e.g., "BANGE", "ECOBANK_MPGS")
        """
        return self.bank_code

    def get_webhook_signature_header(self) -> str:
        """
        Return the HTTP header name for webhook signatures.
        Override in subclass if bank uses a different header.

        Returns:
            Header name (e.g., "X-Bange-Signature", "X-Ecobank-Signature")
        """
        return f"X-{self.bank_code.capitalize()}-Signature"

    async def health_check(self) -> bool:
        """
        Optional health check for the bank API.
        Override in subclass for real health checks.

        Returns:
            True if API is reachable
        """
        return True

    async def cancel_payment(
        self, external_reference: str, reason: str = ""
    ) -> bool:
        """
        Optional: Cancel a pending payment with the bank.
        Override in subclass if bank supports cancellation.

        Returns:
            True if cancelled successfully
        """
        return False

    def map_status_to_internal(self, bank_status: str) -> str:
        """
        Map bank-specific status string to internal status.
        Override in subclass for bank-specific mappings.

        Default mapping covers common patterns.
        """
        status_map = {
            "pending": "pending",
            "processing": "processing",
            "completed": "completed",
            "paid": "completed",
            "success": "completed",
            "failed": "failed",
            "error": "failed",
            "cancelled": "cancelled",
            "expired": "failed",
            "refunded": "refunded",
        }
        return status_map.get(bank_status.lower(), "failed")
