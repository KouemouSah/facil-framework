"""
Communications API Routes
"""

from fastapi import APIRouter
from app.modules.communications.api.communication_routes import router as communication_router
from app.modules.communications.api.email_templates_routes import router as email_templates_router
from app.modules.communications.api.push_templates_routes import router as push_templates_router
from app.modules.communications.api.webhook_routes import router as webhook_router
from app.modules.communications.api.sms_templates_routes import router as sms_templates_router
from app.modules.communications.api.ussd_routes import router as ussd_router
from app.modules.communications.api.notification_templates_routes import router as notification_templates_router
from app.modules.communications.api.provider_settings_routes import router as provider_settings_router

# Create main router that includes all sub-routers
router = APIRouter()
router.include_router(communication_router)
router.include_router(email_templates_router)
router.include_router(push_templates_router)
router.include_router(webhook_router)
router.include_router(sms_templates_router)
router.include_router(ussd_router)
router.include_router(notification_templates_router)
router.include_router(provider_settings_router)

__all__ = [
    "router",
    "email_templates_router",
    "push_templates_router",
    "sms_templates_router",
    "ussd_router",
    "notification_templates_router",
    "provider_settings_router"
]
