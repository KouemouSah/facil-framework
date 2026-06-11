# API exports
from .routes import router
from .agent_routes import router as agent_router
from .admin_routes import router as admin_router
from .appointment_routes import router as appointment_router
from .wizard_session_routes import router as wizard_session_router

__all__ = [
    "router",
    "agent_router",
    "admin_router",
    "appointment_router",
    "wizard_session_router",
]
