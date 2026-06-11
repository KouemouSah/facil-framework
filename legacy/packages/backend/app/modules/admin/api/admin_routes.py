"""
Admin API Endpoints - For database migrations and maintenance
RESTRICTED ACCESS - Requires admin authentication
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from loguru import logger
from typing import Dict, Any
import asyncpg

from app.modules.auth.middleware.auth_middleware import get_current_user
from app.modules.permissions.middleware.permission_middleware import permission_required
from app.database.connection import get_database as get_db
from app.core.secrets import validate_secrets_available
from app.config import get_settings

router = APIRouter(tags=["Admin - Diagnostics"])
security = HTTPBearer()


@router.post("/migrate/grandfather-users", response_model=Dict[str, Any])
async def migrate_grandfather_users(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
    _: None = Depends(permission_required("admin.run_migrations"))
):
    """
    Execute Migration 002: Grandfather existing users
    Sets email_verified=TRUE for users created before 2025-11-03

    ADMIN ONLY - Requires admin.run_migrations permission
    """
    try:
        user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")
        logger.info(f"Migration 002 requested by user {user_id}")

        # Execute UPDATE
        result = await db.execute("""
            UPDATE users
            SET email_verified = TRUE,
                updated_at = NOW()
            WHERE (email_verified IS NULL OR email_verified = FALSE)
              AND created_at < '2025-11-03 00:00:00+00'::timestamptz
        """)

        # Count grandfathered users
        count_result = await db.fetchval("""
            SELECT COUNT(*)
            FROM users
            WHERE email_verified = TRUE
              AND created_at < '2025-11-03 00:00:00+00'::timestamptz
        """)

        logger.success(f"Migration 002 completed: {count_result} users grandfathered")

        return {
            "success": True,
            "migration": "002_set_existing_users_email_verified",
            "users_grandfathered": count_result,
            "message": f"Successfully grandfathered {count_result} existing users"
        }

    except Exception as e:
        logger.error(f"Migration 002 failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Migration failed: {str(e)}"
        )


@router.get("/diagnostic/secrets", response_model=Dict[str, Any])
async def check_secrets_configuration(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: None = Depends(permission_required("admin.view_diagnostics"))
):
    """
    Diagnostic endpoint: Check secrets configuration status

    SECURITY NOTE: Does NOT expose secret values, only status
    ADMIN ONLY - Requires admin.view_diagnostics permission
    """
    try:
        user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")
        logger.info(f"Secrets diagnostic requested by user {user_id}")

        # Validate secrets availability
        secrets_status = validate_secrets_available()

        # Get SMTP configuration (without password)
        settings = get_settings()
        smtp_config = {
            "smtp_host": settings.SMTP_HOST,
            "smtp_port": settings.SMTP_PORT,
            "smtp_username": settings.SMTP_USERNAME,
            "smtp_from_email": settings.SMTP_FROM_EMAIL,
            "smtp_from_name": settings.SMTP_FROM_NAME,
            "smtp_use_tls": settings.SMTP_USE_TLS,
            "smtp_password_configured": bool(settings.SMTP_PASSWORD and len(settings.SMTP_PASSWORD) > 0),
            "smtp_password_length": len(settings.SMTP_PASSWORD) if settings.SMTP_PASSWORD else 0
        }

        return {
            "success": True,
            "secrets_status": secrets_status,
            "smtp_configuration": smtp_config,
            "message": "Secrets diagnostic completed successfully"
        }

    except Exception as e:
        logger.error(f"Secrets diagnostic failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Diagnostic failed: {str(e)}"
        )
