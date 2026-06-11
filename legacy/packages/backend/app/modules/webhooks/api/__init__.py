"""Webhook API routes"""

from app.modules.webhooks.api.webhook_routes import router as webhook_router

__all__ = ["webhook_router"]
