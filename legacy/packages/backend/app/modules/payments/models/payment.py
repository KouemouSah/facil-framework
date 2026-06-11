"""
Payment Models - BANGE Mobile Payment Integration

Table: payments (polymorphe - tax_declarations XOR fiscal_services)
Aligned with DATABASE_SCHEMA_REFERENCE.md
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from decimal import Decimal
from enum import Enum


class PaymentType(str, Enum):
    """Type de paiement — matches DB payment_type_enum"""
    FULL = "full"                        # Paiement complet
    PARTIAL = "partial"                  # Paiement partiel
    INSTALLMENT = "installment"          # Acompte (échéancier)
    COMPLEMENTARY = "complementary"      # Paiement complémentaire


class PaymentStatus(str, Enum):
    """Status de paiement"""
    PENDING = "pending"          # En attente
    PROCESSING = "processing"    # En traitement BANGE
    COMPLETED = "completed"      # Complété
    FAILED = "failed"            # Échoué
    CANCELLED = "cancelled"      # Annulé
    REFUNDED = "refunded"        # Remboursé


class PaymentMethod(str, Enum):
    """Méthode de paiement — matches DB payment_method_enum"""
    BANK_TRANSFER = "bank_transfer"  # Virement bancaire
    CARD = "card"                    # Carte bancaire
    MOBILE_MONEY = "mobile_money"    # Mobile money (BANGE)
    CASH = "cash"                    # Espèces
    CHECK = "check"                  # Chèque


class PaymentBase(BaseModel):
    """Base payment model - Polymorphe"""

    user_id: str = Field(..., description="User UUID")

    # Polymorphic: tax_declaration_id XOR fiscal_service_id
    tax_declaration_id: Optional[str] = Field(None, description="FK tax_declarations (XOR fiscal_service_id)")
    fiscal_service_id: Optional[int] = Field(None, description="FK fiscal_services (XOR tax_declaration_id)")

    # Payment plan (optional)
    payment_plan_id: Optional[str] = Field(None, description="FK payment_plans (si paiement partiel)")
    installment_id: Optional[str] = Field(None, description="FK payment_installments (si acompte)")

    # Amounts
    base_amount: Decimal = Field(..., ge=0, description="Montant de base")
    penalties: Decimal = Field(default=Decimal("0"), ge=0, description="Pénalités")
    interest: Decimal = Field(default=Decimal("0"), ge=0, description="Intérêts")
    currency: str = Field(default="XAF", description="Devise")

    # Payment details
    payment_type: PaymentType = Field(default=PaymentType.FULL)
    payment_method: PaymentMethod = Field(..., description="Méthode de paiement")

    # BANGE integration
    bank_reference: Optional[str] = Field(None, description="Référence bancaire (unique)")

    # Idempotency (prevent double-click duplicates)
    idempotency_key: str = Field(..., description="Clé d'idempotence client (unique)")

    @validator('tax_declaration_id', 'fiscal_service_id')
    def validate_polymorphic(cls, v, values):
        """Ensure XOR: exactly one of tax_declaration_id or fiscal_service_id"""
        tax_id = values.get('tax_declaration_id')
        fiscal_id = values.get('fiscal_service_id')

        if tax_id and fiscal_id:
            raise ValueError("Cannot set both tax_declaration_id and fiscal_service_id")
        if not tax_id and not fiscal_id:
            raise ValueError("Must set either tax_declaration_id or fiscal_service_id")

        return v


class PaymentCreate(PaymentBase):
    """Create payment"""
    pass


class PaymentUpdate(BaseModel):
    """Update payment"""
    status: Optional[PaymentStatus] = None
    bank_reference: Optional[str] = None
    paid_at: Optional[datetime] = None


class PaymentResponse(PaymentBase):
    """Payment response"""
    id: str

    # Calculated amount (GENERATED in DB or calculated)
    amount: Decimal = Field(..., description="Total amount (base + penalties + interest)")

    # Status
    status: PaymentStatus

    # BANGE transaction
    bank_transaction_id: Optional[str] = Field(None, description="FK bank_transactions")

    # Timestamps
    created_at: datetime
    updated_at: datetime
    paid_at: Optional[datetime] = None

    # Related data (populated by joins)
    declaration_type: Optional[str] = Field(None, description="Type déclaration (si tax_declaration)")
    fiscal_service_name: Optional[str] = Field(None, description="Nom service (si fiscal_service)")
    user_email: Optional[str] = None


class PaymentListResponse(BaseModel):
    """List of payments"""
    payments: List[PaymentResponse]
    total: int
    page: int
    page_size: int


# ========== PAYMENT PLANS ==========

class PaymentPlanCreate(BaseModel):
    """Create payment plan (échéancier)"""
    payment_id: str = Field(..., description="FK payments")
    number_of_installments: int = Field(..., ge=2, le=12, description="Nombre d'acomptes (2-12)")
    installment_frequency: str = Field(default="monthly", description="Fréquence: monthly, bi_monthly, quarterly")
    first_installment_date: date = Field(..., description="Date 1er acompte")


class InstallmentResponse(BaseModel):
    """Payment installment"""
    id: str
    payment_plan_id: str
    installment_number: int = Field(..., description="Numéro acompte (1, 2, 3...)")
    amount: Decimal = Field(..., ge=0)
    due_date: date
    status: PaymentStatus
    paid_at: Optional[datetime] = None
    created_at: datetime


class PaymentPlanResponse(BaseModel):
    """Payment plan with installments"""
    id: str
    payment_id: str
    total_amount: Decimal
    number_of_installments: int
    installment_frequency: str
    status: str  # active, completed, cancelled
    created_at: datetime

    installments: List[InstallmentResponse] = []


# ========== BANGE INTEGRATION MODELS ==========

class BANGEPaymentRequest(BaseModel):
    """BANGE payment request model for gateway integration"""
    amount: Decimal = Field(..., ge=0, description="Payment amount")
    currency: str = Field(default="XAF", description="Payment currency (XAF, EUR, USD)")
    description: str = Field(..., max_length=500, description="Payment description")
    reference: str = Field(..., description="Unique payment reference")
    customer_email: Optional[str] = Field(None, description="Customer email")
    customer_phone: Optional[str] = Field(None, description="Customer phone")
    callback_url: Optional[str] = Field(None, description="Payment callback URL")
    return_url: Optional[str] = Field(None, description="Return URL after payment")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class BANGEPaymentResponse(BaseModel):
    """BANGE payment response model from gateway"""
    payment_id: str = Field(..., description="BANGE payment ID")
    payment_url: str = Field(..., description="Payment URL for redirection")
    reference: str = Field(..., description="Payment reference")
    status: str = Field(..., description="Payment status")
    amount: Decimal = Field(..., description="Payment amount")
    currency: str = Field(..., description="Payment currency")
    expires_at: Optional[datetime] = Field(None, description="Payment expiration time")
    created_at: datetime = Field(..., description="Payment creation time")


class BANGEWebhookData(BaseModel):
    """BANGE webhook notification data"""
    payment_id: str = Field(..., description="BANGE payment ID")
    reference: str = Field(..., description="Payment reference")
    status: str = Field(..., description="Payment status: completed, failed, cancelled")
    amount: Decimal = Field(..., description="Payment amount")
    currency: str = Field(..., description="Payment currency")
    paid_at: Optional[datetime] = Field(None, description="Payment completion timestamp")
    transaction_id: Optional[str] = Field(None, description="Bank transaction ID")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    signature: str = Field(..., description="HMAC signature for verification")


# ========== SEARCH AND FILTERING ==========

class PaymentSearchFilter(BaseModel):
    """Model for payment search and filtering"""
    user_id: Optional[str] = Field(None, description="Filter by user UUID")
    tax_declaration_id: Optional[str] = Field(None, description="Filter by declaration UUID")
    fiscal_service_id: Optional[int] = Field(None, description="Filter by fiscal service ID")
    payment_type: Optional[PaymentType] = Field(None, description="Filter by payment type")
    payment_method: Optional[PaymentMethod] = Field(None, description="Filter by payment method")
    status: Optional[PaymentStatus] = Field(None, description="Filter by status")
    min_amount: Optional[Decimal] = Field(None, ge=0, description="Minimum amount filter")
    max_amount: Optional[Decimal] = Field(None, ge=0, description="Maximum amount filter")
    currency: Optional[str] = Field(None, description="Filter by currency (XAF, EUR, USD)")
    created_after: Optional[datetime] = Field(None, description="Created after date")
    created_before: Optional[datetime] = Field(None, description="Created before date")
    reference_search: Optional[str] = Field(None, description="Search by bank reference")
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Page size")


# ========== STATISTICS ==========

class PaymentStats(BaseModel):
    """Model for payment statistics and metrics"""
    # Count metrics
    total_payments: int = Field(..., description="Total number of payments")
    successful_payments: int = Field(..., description="Number of completed payments")
    failed_payments: int = Field(..., description="Number of failed payments")
    pending_payments: int = Field(..., description="Number of pending payments")

    # Amount metrics
    total_amount: Decimal = Field(..., description="Total payment amount (all)")
    successful_amount: Decimal = Field(..., description="Total successful amount")
    pending_amount: Decimal = Field(..., description="Total pending amount")
    average_amount: Decimal = Field(..., description="Average payment amount")

    # By payment method
    payments_by_method: Dict[str, int] = Field(..., description="Payments count by method")
    amount_by_method: Dict[str, Decimal] = Field(..., description="Amount by payment method")

    # By payment type (full, partial, installment)
    payments_by_type: Dict[str, int] = Field(..., description="Payments count by type")
    amount_by_type: Dict[str, Decimal] = Field(..., description="Amount by payment type")

    # Time-based metrics
    payments_today: int = Field(..., description="Payments today")
    payments_this_week: int = Field(..., description="Payments this week")
    payments_this_month: int = Field(..., description="Payments this month")

    # Success rate
    success_rate: float = Field(..., ge=0, le=100, description="Payment success rate percentage")

    # Daily and monthly trends
    daily_trend: List[Dict[str, Any]] = Field(default_factory=list, description="Daily payment trends")
    monthly_revenue: List[Dict[str, Any]] = Field(default_factory=list, description="Monthly revenue trends")
