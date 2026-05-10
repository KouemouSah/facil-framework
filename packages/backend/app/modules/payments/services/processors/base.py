"""
Payment Processor Base - Abstract Base Class.

Defines the interface that all payment processors must implement.
Uses Strategy pattern for handling different payment methods.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime
from decimal import Decimal
from enum import Enum
import asyncpg

from app.modules.payments.models.payment import PaymentMethod, PaymentStatus


class ProcessorType(str, Enum):
    """Type of payment processor."""
    GATEWAY_API = "gateway_api"        # Any bank gateway (BANGE, Ecobank, etc.)
    BANGE_API = "gateway_api"          # Backward compat alias → same as GATEWAY_API
    MANUAL_VALIDATION = "manual"       # Requires agent validation


@dataclass
class PaymentInitResult:
    """
    Result of payment initiation.

    Attributes:
        success: Whether initiation was successful
        payment_id: Internal payment ID (UUID)
        external_reference: External reference (e.g., BANGE transaction ID)
        redirect_url: URL to redirect user for payment (for BANGE)
        status: Initial payment status
        requires_action: Whether user action is required
        action_type: Type of action required (redirect, wait_confirmation, etc.)
        message_es: Message in Spanish for the user
        expires_at: When the payment request expires
        error: Error message if not successful
        metadata: Additional metadata
    """
    success: bool
    payment_id: str
    external_reference: Optional[str] = None
    redirect_url: Optional[str] = None
    status: PaymentStatus = PaymentStatus.PENDING
    requires_action: bool = False
    action_type: Optional[str] = None  # "redirect", "wait_confirmation", "agent_validation"
    message_es: Optional[str] = None
    expires_at: Optional[datetime] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PaymentStatusResult:
    """
    Result of payment status check.

    Attributes:
        payment_id: Internal payment ID
        status: Current payment status
        paid: Whether payment has been completed
        paid_at: When payment was completed
        amount: Payment amount
        currency: Payment currency
        receipt_number: Receipt number if generated
        receipt_url: URL to download receipt
        validated_by: Agent who validated (for manual payments)
        error: Error message if check failed
    """
    payment_id: str
    status: PaymentStatus
    paid: bool = False
    paid_at: Optional[datetime] = None
    amount: Optional[Decimal] = None
    currency: str = "XAF"
    receipt_number: Optional[str] = None
    receipt_url: Optional[str] = None
    receipt_pdf_bytes: Optional[bytes] = None
    validated_by: Optional[str] = None
    error: Optional[str] = None


@dataclass
class PaymentContext:
    """
    Context for payment processing.

    Contains all information needed to process a payment.
    """
    # Identifiers
    service_request_id: str
    user_id: str

    # Payment details
    amount: Decimal
    currency: str = "XAF"
    payment_method: PaymentMethod = PaymentMethod.MOBILE_MONEY

    # Tariff breakdown (from workflow.get_tariff_breakdown())
    # Stored as calculation_details in service_payments
    tariff_breakdown: Optional[Dict[str, Any]] = None

    # User contact info (for notifications)
    user_email: Optional[str] = None
    user_phone: Optional[str] = None
    user_name: Optional[str] = None

    # Request details
    workflow_code: Optional[str] = None
    service_name: Optional[str] = None
    reference_number: Optional[str] = None

    # Additional data
    metadata: Dict[str, Any] = field(default_factory=dict)

    # For idempotency
    idempotency_key: Optional[str] = None

    # Optional client-supplied return URL for the payment gateway redirect.
    # Used by mobile clients to deep-link back into the app after BANGE checkout.
    # Validated upstream against the MOBILE_DEEP_LINK_SCHEMES whitelist + FRONTEND_URL origin.
    return_url: Optional[str] = None

    def get_total_amount(self) -> Decimal:
        """Get total amount from tariff_breakdown if available, else amount."""
        if self.tariff_breakdown:
            return Decimal(str(self.tariff_breakdown.get("total_amount", self.amount)))
        return self.amount


class PaymentProcessorBase(ABC):
    """
    Abstract base class for payment processors.

    All payment processors must implement:
    - initiate(): Start a payment
    - check_status(): Check payment status
    - get_supported_methods(): Return supported payment methods

    Optional methods:
    - cancel(): Cancel a pending payment
    - refund(): Refund a completed payment
    """

    processor_type: ProcessorType

    @abstractmethod
    async def initiate(
        self,
        db: asyncpg.Connection,
        context: PaymentContext
    ) -> PaymentInitResult:
        """
        Initiate a payment.

        Args:
            db: Database connection
            context: Payment context with all required information

        Returns:
            PaymentInitResult with payment details and next steps
        """
        pass

    @abstractmethod
    async def check_status(
        self,
        db: asyncpg.Connection,
        payment_id: str
    ) -> PaymentStatusResult:
        """
        Check payment status.

        Args:
            db: Database connection
            payment_id: Internal payment ID

        Returns:
            PaymentStatusResult with current status
        """
        pass

    @abstractmethod
    def get_supported_methods(self) -> list[PaymentMethod]:
        """
        Get list of payment methods supported by this processor.

        Returns:
            List of PaymentMethod values
        """
        pass

    async def cancel(
        self,
        db: asyncpg.Connection,
        payment_id: str,
        reason: Optional[str] = None
    ) -> bool:
        """
        Cancel a pending payment.

        Default implementation returns False (not supported).
        Override in subclass if cancellation is supported.

        Args:
            db: Database connection
            payment_id: Internal payment ID
            reason: Cancellation reason

        Returns:
            True if cancelled successfully
        """
        return False

    async def refund(
        self,
        db: asyncpg.Connection,
        payment_id: str,
        amount: Optional[Decimal] = None,
        reason: Optional[str] = None
    ) -> bool:
        """
        Refund a completed payment.

        Default implementation returns False (not supported).
        Override in subclass if refund is supported.

        Args:
            db: Database connection
            payment_id: Internal payment ID
            amount: Amount to refund (None = full refund)
            reason: Refund reason

        Returns:
            True if refund initiated successfully
        """
        return False

    def can_process(self, method: PaymentMethod) -> bool:
        """
        Check if this processor can handle a specific payment method.

        Args:
            method: Payment method to check

        Returns:
            True if this processor supports the method
        """
        return method in self.get_supported_methods()
