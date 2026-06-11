"""Company API routes"""

from app.modules.companies.api.company_routes import router as company_router
from app.modules.companies.api.company_classification_routes import router as classification_router
from app.modules.companies.api.company_dashboard_routes import router as dashboard_router
from app.modules.companies.api.company_ministry_routes import router as ministry_router
from app.modules.companies.api.company_cron_routes import router as cron_router
from app.modules.companies.api.company_public_routes import router as public_router

# Include sub-routers under the company router
company_router.include_router(classification_router)
company_router.include_router(dashboard_router)
company_router.include_router(ministry_router)
company_router.include_router(cron_router)

__all__ = ["company_router", "public_router"]
