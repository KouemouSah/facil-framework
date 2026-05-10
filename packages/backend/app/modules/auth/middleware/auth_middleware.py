"""
Authentication Core - JWT-based authentication for TaxasGE Backend
Provides get_current_user dependency for route protection
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from loguru import logger

from app.modules.users.models.user import UserResponse

# Security schemes
security = HTTPBearer()
security_optional = HTTPBearer(auto_error=False)

# Lazy-loaded singleton for UserRepository to avoid import-time errors
_user_repository = None


def get_user_repository():
    """Get UserRepository singleton (lazy-loaded)"""
    global _user_repository
    if _user_repository is None:
        from app.repositories.user_repository import UserRepository
        _user_repository = UserRepository()
        logger.debug("UserRepository initialized (lazy)")
    return _user_repository


def get_auth_service():
    """Get AuthService singleton (lazy-loaded)"""
    from app.modules.auth.services.auth_service import get_auth_service as _get_auth_service
    return _get_auth_service()


async def _check_funcionario_status(matricula: str) -> dict:
    """
    Check funcionario matricula status against verified_identifiers table.

    This is called for every authenticated request where user has matricula_funcionario.
    Uses the VerificationService to check if the matricula is still active.

    Args:
        matricula: The funcionario's matricula

    Returns:
        Dict with funcionario status fields
    """
    from app.database.connection import db_manager
    from app.modules.verified_identifiers.services.verification_service import VerificationService
    from app.modules.verified_identifiers.services.crypto_service import get_crypto_service

    async with db_manager.get_connection() as db:
        crypto = get_crypto_service()
        verification_service = VerificationService(pool=db, crypto=crypto)
        return await verification_service.check_funcionario_status(matricula)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> UserResponse:
    """
    Dependency to get current authenticated user from JWT token

    This replaces the mock authentication - uses real JWT validation

    Args:
        credentials: Bearer token from Authorization header

    Returns:
        UserResponse: Current authenticated user

    Raises:
        HTTPException 401: If token is invalid or user not found
        HTTPException 403: If user account is suspended
    """
    try:
        # Validate access token and get user data (lazy-loaded)
        auth_service = get_auth_service()
        token_data = await auth_service.validate_access_token(credentials.credentials)

        if not token_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired access token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Get user_id from token (JWT uses "sub" for subject/user_id)
        user_id = token_data.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload: missing user ID",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Fetch full user from database (lazy-loaded repository)
        user_repository = get_user_repository()
        user = await user_repository.find_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Check if user is suspended
        if user.status == "suspended":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account suspended. Contact administrator."
            )

        # Check if user is active
        if user.status != "active":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Account status: {user.status}. Please verify your email or contact support."
            )

        # Enrich with funcionario_status if user is a verified funcionario
        # Cached for 5 minutes to avoid DB query on every authenticated request
        if user.matricula_funcionario and user.funcionario_verified_at:
            try:
                from app.core.cache import get_cache
                cache = get_cache()
                cache_key = f"func:status:{user.matricula_funcionario}"
                cached_status = await cache.get(cache_key)
                if cached_status is not None:
                    user.funcionario_status = cached_status
                else:
                    funcionario_status = await _check_funcionario_status(user.matricula_funcionario)
                    user.funcionario_status = funcionario_status
                    await cache.set(cache_key, funcionario_status, ttl=300)  # 5 min
            except Exception as e:
                logger.warning(f"Failed to check funcionario status: {e}")
                # Don't block access on failure - just log

        return user

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Authentication error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_active_user(
    current_user: UserResponse = Depends(get_current_user),
) -> UserResponse:
    """
    Dependency to get current active user (not suspended)

    Args:
        current_user: Current authenticated user

    Returns:
        UserResponse: Current active user

    Raises:
        HTTPException 403: If user is not active
    """
    if current_user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User account is {current_user.status}"
        )
    return current_user


async def get_current_admin_user(
    current_user: UserResponse = Depends(get_current_user),
) -> UserResponse:
    """
    Dependency to require admin role

    **IMPORTANT:** Admins have FULL ACCESS to ALL modules automatically.
    See .github/docs-internal/ADMIN_PERMISSIONS.md for details.

    Args:
        current_user: Current authenticated user

    Returns:
        UserResponse: Current admin user

    Raises:
        HTTPException 403: If user is not an admin
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


def require_admin(
    current_user: UserResponse = Depends(get_current_user),
) -> UserResponse:
    """
    Alias for get_current_admin_user (for backward compatibility)

    Admins have FULL ACCESS to ALL modules automatically.

    Args:
        current_user: Current authenticated user

    Returns:
        UserResponse: Current admin user

    Raises:
        HTTPException 403: If user is not an admin
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


def is_admin(user: UserResponse) -> bool:
    """
    Helper function to check if a user is admin

    Args:
        user: User object

    Returns:
        True if user is admin
    """
    return user.role == "admin"


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_optional),
) -> Optional[UserResponse]:
    """
    Dependency to optionally get current user from JWT token.

    Returns None if no token provided (allows anonymous access).
    Validates token if provided and returns user.

    Use this for endpoints that work for both authenticated and anonymous users,
    like chatbot where authenticated users get personalized responses.

    Args:
        credentials: Optional Bearer token from Authorization header

    Returns:
        UserResponse if authenticated, None if anonymous

    Raises:
        HTTPException 401: If token is provided but invalid
    """
    if credentials is None:
        return None

    try:
        # Validate access token and get user data (lazy-loaded)
        auth_service = get_auth_service()
        token_data = await auth_service.validate_access_token(credentials.credentials)

        if not token_data:
            # Invalid token - return None for optional auth
            logger.warning("Invalid token provided for optional auth endpoint")
            return None

        # Get user_id from token (JWT uses "sub" for subject/user_id)
        user_id = token_data.get("sub")
        if not user_id:
            return None

        # Fetch full user from database (lazy-loaded repository)
        user_repository = get_user_repository()
        user = await user_repository.find_by_id(user_id)
        if not user:
            return None

        # Check if user is active (but don't block - just return None)
        if user.status != "active":
            logger.warning(f"Non-active user {user_id} accessing optional auth endpoint")
            return None

        return user

    except Exception as e:
        logger.warning(f"Optional auth validation failed: {e}")
        return None
