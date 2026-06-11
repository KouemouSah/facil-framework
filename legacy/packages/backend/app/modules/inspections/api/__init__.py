from app.modules.inspections.api.inspection_routes import router
from app.modules.inspections.api.mission_routes import router as mission_router
from app.modules.inspections.api.analytics_routes import router as analytics_router
from app.modules.inspections.api.filter_export_routes import router as filter_export_router

__all__ = ["router", "mission_router", "analytics_router", "filter_export_router"]
