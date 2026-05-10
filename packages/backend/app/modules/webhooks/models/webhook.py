"""
Webhook Models - Multi-Gateway Bank Integration

Tables: bank_configurations, bank_transactions
Aligned with DATABASE_SCHEMA_REFERENCE.md
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from enum import Enum
import json


class BankCode(str, Enum):
    """Codes des banques en Guinée"""
    BANGE = "BANGE"          # Banque Centrale (Mobile Money)
    BGFI = "BGFI"            # BGFI Bank Guinea
    CCEIBANK = "CCEIBANK"    # CCEI Bank Guinea
    SGBGE = "SGBGE"          # Société Générale de Banques en Guinée
    ECOBANK = "ECOBANK"      # Ecobank Guinea


class TransactionStatus(str, Enum):
    """Status de transaction bancaire"""
    UNRECONCILED = "unreconciled"  # Pas encore réconciliée
    RECONCILED = "reconciled"      # Réconciliée avec payment_id
    DISPUTED = "disputed"          # En litige


# ========== BANK CONFIGURATIONS ==========

class BankConfigurationBase(BaseModel):
    """Base bank configuration"""
    bank_code: BankCode
    bank_name: str = Field(..., description="Nom de la banque")
    api_endpoint: Optional[str] = Field(None, description="URL API banque")
    api_version: Optional[str] = Field(None, description="Version API")
    treasury_account_number: str = Field(..., description="N° compte Trésor Public")
    is_active: bool = Field(default=True, description="Activer/désactiver banque")
    supports_webhooks: bool = Field(default=False, description="Support webhooks callbacks")
    supports_direct_integration: bool = Field(default=False, description="Support API directe")


class BankConfigurationCreate(BankConfigurationBase):
    """Create bank configuration (admin only)"""
    api_key_encrypted: Optional[str] = Field(None, description="Clé API chiffrée")
    webhook_secret: Optional[str] = Field(None, description="Secret HMAC webhooks")
    gateway_type: Optional[str] = Field(None, description="Type gateway: bange, ecobank, null")
    supported_payment_methods: Optional[List[str]] = Field(default=[], description="Méthodes supportées")
    is_primary: bool = Field(default=False, description="Gateway principal pour ses méthodes")


class BankConfigurationUpdate(BaseModel):
    """Update bank configuration"""
    bank_name: Optional[str] = None
    api_endpoint: Optional[str] = None
    api_version: Optional[str] = None
    api_key_encrypted: Optional[str] = None
    webhook_secret: Optional[str] = None
    treasury_account_number: Optional[str] = None
    is_active: Optional[bool] = None
    supports_webhooks: Optional[bool] = None
    supports_direct_integration: Optional[bool] = None
    gateway_type: Optional[str] = None
    supported_payment_methods: Optional[List[str]] = None
    is_primary: Optional[bool] = None


class BankConfigurationResponse(BankConfigurationBase):
    """Bank configuration response (sans secrets)"""
    id: int
    gateway_type: Optional[str] = None
    supported_payment_methods: Optional[List[str]] = None
    is_primary: bool = False
    created_at: datetime
    updated_at: datetime

    @field_validator("supported_payment_methods", mode="before")
    @classmethod
    def parse_jsonb_methods(cls, v):
        """asyncpg returns JSONB as raw JSON string — parse to list"""
        if isinstance(v, str):
            return json.loads(v)
        return v

    # Ne pas exposer les secrets via API
    # api_key_encrypted et webhook_secret sont exclus


# ========== BANK TRANSACTIONS ==========

class BankTransactionBase(BaseModel):
    """Base bank transaction"""
    bank_code: BankCode = Field(..., description="Code banque")
    bank_reference: str = Field(..., description="Référence unique banque")
    bank_transaction_date: datetime = Field(..., description="Date transaction banque")
    amount: Decimal = Field(..., ge=0, description="Montant")
    currency: str = Field(default="XAF", description="Devise")
    account_number: Optional[str] = Field(None, description="N° compte")
    account_holder_name: Optional[str] = Field(None, description="Nom titulaire")


class BankTransactionCreate(BankTransactionBase):
    """Create bank transaction (from webhook)"""
    raw_data: Dict[str, Any] = Field(..., description="Payload JSON complet (audit)")


class BankTransactionResponse(BankTransactionBase):
    """Bank transaction response"""
    id: str

    # Reconciliation
    service_payment_id: Optional[str] = Field(None, description="FK service_payments (si réconciliée)")
    status: TransactionStatus
    reconciled_at: Optional[datetime] = Field(None, description="Date réconciliation")
    reconciled_by: Optional[str] = Field(None, description="UUID user qui a réconcilié")

    # Raw data
    raw_data: Optional[Dict[str, Any]] = Field(None, description="Payload original")

    # Timestamps
    created_at: datetime

    # Related data (populated by joins)
    payment_reference: Optional[str] = Field(None, description="Référence payment lié")
    user_email: Optional[str] = Field(None, description="Email user du payment")


class BankTransactionListResponse(BaseModel):
    """List of bank transactions"""
    transactions: List[BankTransactionResponse]
    total: int
    page: int
    page_size: int


# ========== RECONCILIATION ==========

class ReconcileRequest(BaseModel):
    """Manual reconciliation request"""
    bank_transaction_id: str = Field(..., description="ID transaction bancaire")
    service_payment_id: str = Field(..., description="ID service_payment à réconcilier")


# ========== BANGE WEBHOOK PAYLOAD ==========

class BangeWebhookPayload(BaseModel):
    """
    BANGE webhook payload structure

    À adapter selon la vraie structure BANGE API
    """
    event_type: str = Field(..., description="Type événement: payment.success, payment.failed")
    bank_reference: str = Field(..., description="Référence unique BANGE")
    transaction_date: str = Field(..., description="Date ISO 8601")
    amount: Decimal = Field(..., ge=0)
    currency: str = Field(default="XAF")
    account_number: Optional[str] = None
    account_holder: Optional[str] = None
    status: str = Field(..., description="success, failed, pending")

    # Metadata
    merchant_reference: Optional[str] = Field(None, description="Notre référence (payment.bank_reference)")
    customer_phone: Optional[str] = None

    # HMAC signature (dans headers HTTP, pas body)
    # signature: str = Field(..., description="HMAC-SHA256 signature")
