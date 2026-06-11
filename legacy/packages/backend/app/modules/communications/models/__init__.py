"""
Communications Models
"""

from app.modules.communications.models.communication import (
    CommunicationType,
    CommunicationStatus,
    EmailTemplate,
)

from app.modules.communications.models.email_template import (
    TemplateVariable,
    EmailTemplateBase,
    EmailTemplateCreate,
    EmailTemplateUpdate,
    EmailTemplateResponse,
    EmailTemplatePreview,
    EmailTemplateListResponse,
)

from app.modules.communications.models.sms_template import (
    SmsTemplateCategory,
    SmsTemplateCreate,
    SmsTemplateUpdate,
    SmsTemplateResponse,
    SmsTemplateListResponse,
    SmsCharacterCount,
    SmsTemplateRenderRequest,
    SmsTemplateRenderResponse,
)

__all__ = [
    # Communication models
    "CommunicationType",
    "CommunicationStatus",
    "EmailTemplate",
    # Email Template models
    "TemplateVariable",
    "EmailTemplateBase",
    "EmailTemplateCreate",
    "EmailTemplateUpdate",
    "EmailTemplateResponse",
    "EmailTemplatePreview",
    "EmailTemplateListResponse",
    # SMS Template models
    "SmsTemplateCategory",
    "SmsTemplateCreate",
    "SmsTemplateUpdate",
    "SmsTemplateResponse",
    "SmsTemplateListResponse",
    "SmsCharacterCount",
    "SmsTemplateRenderRequest",
    "SmsTemplateRenderResponse",
]
