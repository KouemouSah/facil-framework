"""
Auth API routes for TaxasGE Backend
Exports routers for auth endpoints
"""

import traceback
import sys
from loguru import logger

# Track import errors for diagnostics
_auth_import_error = None
_two_factor_import_error = None

# Try to import auth_router with VERY detailed error logging
try:
    logger.warning("🔄 Starting auth_router import...")

    # Step-by-step imports to identify exactly where it fails
    try:
        logger.debug("  1. Importing auth_service...")
        from app.modules.auth.services.auth_service import get_auth_service
        logger.debug("  ✅ auth_service imported")
    except Exception as step_e:
        logger.error(f"  ❌ auth_service FAILED: {step_e}")
        raise

    try:
        logger.debug("  2. Importing session_service...")
        from app.modules.auth.services.session_service import get_session_service
        logger.debug("  ✅ session_service imported")
    except Exception as step_e:
        logger.error(f"  ❌ session_service FAILED: {step_e}")
        raise

    try:
        logger.debug("  3. Importing user models...")
        from app.modules.users.models.user import UserCreate, UserResponse
        logger.debug("  ✅ user models imported")
    except Exception as step_e:
        logger.error(f"  ❌ user models FAILED: {step_e}")
        raise

    try:
        logger.debug("  4. Importing auth_models...")
        from app.modules.auth.models.auth_models import TokenRefreshRequest
        logger.debug("  ✅ auth_models imported")
    except Exception as step_e:
        logger.error(f"  ❌ auth_models FAILED: {step_e}")
        raise

    # Now import the actual router
    logger.debug("  5. Importing auth_routes router...")
    from app.modules.auth.api.auth_routes import router as auth_router
    logger.warning("✅ auth_router imported successfully with all dependencies")

except Exception as e:
    _auth_import_error = str(e)
    _auth_import_traceback = traceback.format_exc()
    logger.error(f"❌ CRITICAL: Failed to import auth_router: {e}")
    logger.error(f"❌ Full Traceback:\n{_auth_import_traceback}")

    # Print to stderr as well (visible in Cloud Run logs)
    print(f"❌ CRITICAL AUTH IMPORT ERROR: {e}", file=sys.stderr)
    print(f"❌ Traceback:\n{_auth_import_traceback}", file=sys.stderr)

    # Create a dummy router with diagnostic endpoints
    from fastapi import APIRouter, HTTPException, status
    auth_router = APIRouter()

    @auth_router.get("/")
    async def auth_import_error():
        """Diagnostic endpoint - shows why auth module failed to load"""
        return {
            "error": "Auth module failed to load",
            "message": _auth_import_error,
            "hint": "Check Cloud Run logs for detailed traceback",
            "status": "CRITICAL - Authentication endpoints NOT available"
        }

    @auth_router.post("/login")
    async def login_error():
        """Return proper error instead of 404 when auth module fails"""
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Auth module failed to load",
                "message": _auth_import_error,
                "hint": "Check server logs for detailed traceback"
            }
        )

    @auth_router.post("/register")
    async def register_error():
        """Return proper error instead of 404 when auth module fails"""
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Auth module failed to load",
                "message": _auth_import_error,
                "hint": "Check server logs for detailed traceback"
            }
        )

# Try to import two_factor_router with detailed error logging
try:
    logger.debug("🔄 Starting two_factor_router import...")
    from app.modules.auth.api.two_factor_routes import router as two_factor_router
    logger.warning("✅ two_factor_router imported successfully")
except Exception as e:
    _two_factor_import_error = str(e)
    logger.error(f"❌ CRITICAL: Failed to import two_factor_router: {e}")
    logger.error(f"❌ Traceback:\n{traceback.format_exc()}")
    print(f"❌ CRITICAL 2FA IMPORT ERROR: {e}", file=sys.stderr)

    # Create a dummy router so the app doesn't crash
    from fastapi import APIRouter
    two_factor_router = APIRouter()

__all__ = [
    "auth_router",
    "two_factor_router",
]
