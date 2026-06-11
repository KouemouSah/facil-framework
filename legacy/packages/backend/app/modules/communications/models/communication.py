"""
Communication Models - Types, status, and templates for communications

Used for email, SMS, push notifications, webhooks
"""

from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class CommunicationType(str, Enum):
    """Types of communications supported"""
    EMAIL = "email"
    SMS = "sms"  # Future
    PUSH = "push"  # Future
    WEBHOOK = "webhook"  # Future


class CommunicationStatus(str, Enum):
    """Status of a communication"""
    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    DELIVERED = "delivered"  # For SMS, Push
    READ = "read"  # For emails with tracking


class EmailTemplate(str, Enum):
    """Email template types"""
    VERIFICATION_CODE = "verification_code"
    PASSWORD_RESET = "password_reset"
    PASSWORD_RESET_CONFIRMATION = "password_reset_confirmation"
    TWO_FACTOR_CODE = "2fa_code"
    ACCOUNT_LOCKOUT = "account_lockout"
    WELCOME = "welcome"
    DECLARATION_SUBMITTED = "declaration_submitted"
    PAYMENT_CONFIRMATION = "payment_confirmation"


class CommunicationCreate(BaseModel):
    """Model for creating a communication record"""
    type: CommunicationType = Field(..., description="Type of communication")
    recipient: str = Field(..., description="Recipient (email, phone, device_token)")
    subject: Optional[str] = Field(None, description="Subject for email")
    content: str = Field(..., description="Message content")
    template: Optional[EmailTemplate] = Field(None, description="Template used")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")


class CommunicationResponse(BaseModel):
    """Model for communication response"""
    id: str
    type: CommunicationType
    recipient: str
    subject: Optional[str]
    status: CommunicationStatus
    template: Optional[EmailTemplate]
    sent_at: Optional[str]
    delivered_at: Optional[str]
    error_message: Optional[str]
    metadata: Dict[str, Any]

    class Config:
        from_attributes = True
