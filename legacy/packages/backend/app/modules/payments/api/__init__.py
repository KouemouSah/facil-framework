"""Payment API routes"""

from app.modules.payments.api.payment_routes import router as payment_router
from app.modules.payments.api.verify_routes import router as verify_router

__all__ = ["payment_router", "verify_router"]
