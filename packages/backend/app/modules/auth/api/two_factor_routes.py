"""
Two-Factor Authentication (2FA) API Endpoints for TaxasGE Backend.

TASK-M01-011: 2FA TOTP Implementation
Source: RAPPORT_MODULE_01_AUTHENTICATION.md lines 436-440

Endpoints:
- POST /2fa/enable - Start 2FA setup (generate secret + QR code)
- POST /2fa/verify - Verify 2FA setup with TOTP code
- POST /2fa/disable - Disable 2FA (requires password)
- GET /2fa/status - Get user's 2FA status
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from loguru import logger
from typing import Dict, Any

from app.modules.auth.services.two_factor_service import TwoFactorService, get_two_factor_service
from app.modules.auth.services.password_service import PasswordService
from app.repositories.user_repository import UserRepository
from app.modules.auth.models.two_factor_models import (
    TwoFactorEnableResponse,
    TwoFactorVerifyRequest,
    TwoFactorVerifyResponse,
    TwoFactorDisableRequest,
    TwoFactorDisableResponse,
    TwoFactorStatusResponse
)
from app.modules.auth.middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/2fa", tags=["Two-Factor Authentication"])
security = HTTPBearer()


@router.post("/enable", response_model=TwoFactorEnableResponse, status_code=200)
async def enable_two_factor(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: Dict[str, Any] = Depends(get_current_user),
    two_factor_service: TwoFactorService = Depends(get_two_factor_service)
):
    """
    Start 2FA setup process (Step 1).

    **Workflow:**
    1. Generate TOTP secret
    2. Generate QR code (user scans with Google Authenticator, Authy, etc.)
    3. Generate 10 backup codes
    4. Return data to user (NOT saved to DB yet)
    5. User calls /2fa/verify with code from authenticator app

    **Security:**
    - Requires authentication (Bearer token)
    - Secret NOT saved until verification step
    - Prevents enabling 2FA without confirming working setup

    **Response:**
    - `secret`: TOTP secret (save for verification step)
    - `qr_code_svg`: SVG QR code to display
    - `backup_codes`: 10 recovery codes (show once, user must save!)

    **Source:** TASK-M01-011
    """
    try:
        user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

        # Check if 2FA already enabled
        user_repo = UserRepository()
        user = await user_repo.get_by_id(user_id)

        if user and user.get('two_factor_enabled'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="2FA is already enabled for this account"
            )

        # Generate 2FA setup data
        setup_data = await two_factor_service.enable_2fa(user_id)

        logger.info(f"2FA setup initiated for user {user_id}")

        return TwoFactorEnableResponse(
            secret=setup_data['secret'],
            qr_code_svg=setup_data['qr_code'],
            backup_codes=setup_data['backup_codes']
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error enabling 2FA for user {current_user.get('sub')}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate 2FA setup"
        )


@router.post("/verify", response_model=TwoFactorVerifyResponse, status_code=200)
async def verify_two_factor_setup(
    request: TwoFactorVerifyRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: Dict[str, Any] = Depends(get_current_user),
    two_factor_service: TwoFactorService = Depends(get_two_factor_service)
):
    """
    Verify 2FA setup and enable 2FA (Step 2).

    **Workflow:**
    1. User scanned QR code from /2fa/enable
    2. User enters 6-digit code from authenticator app
    3. Backend verifies code against secret
    4. If valid: Save secret + backup codes to DB, enable 2FA
    5. If invalid: Return error, user must try again

    **Security:**
    - Requires authentication (Bearer token)
    - Code must match TOTP secret
    - Only enables 2FA after confirming working setup

    **Request:**
    - `secret`: TOTP secret from /2fa/enable response
    - `code`: 6-digit code from authenticator app
    - `backup_codes`: Backup codes from /2fa/enable response

    **Response:**
    - Success message
    - 2FA status (enabled: true)

    **Errors:**
    - 400: Invalid or expired code
    - 401: Unauthorized
    - 500: Internal error

    **Source:** TASK-M01-011
    """
    try:
        user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

        # Verify code and enable 2FA
        success = await two_factor_service.verify_and_enable_2fa(
            user_id=user_id,
            secret=request.secret,
            code=request.code,
            backup_codes=request.backup_codes
        )

        if not success:
            logger.warning(f"2FA verification failed for user {user_id}. "
                         f"This could be due to: invalid TOTP code OR database save failure. "
                         f"Check logs above for specific error.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to enable 2FA. This could be due to an invalid verification code or a system error. Please try again or contact support if the problem persists."
            )

        logger.info(f"✅ 2FA enabled successfully for user {user_id}")

        return TwoFactorVerifyResponse(
            message="2FA enabled successfully. Save your backup codes in a safe place.",
            two_factor_enabled=True
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected exception verifying 2FA setup for user {current_user.get('sub')}: {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"Stacktrace: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while setting up 2FA. Please try again later or contact support."
        )


@router.post("/disable", response_model=TwoFactorDisableResponse, status_code=200)
async def disable_two_factor(
    request: TwoFactorDisableRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: Dict[str, Any] = Depends(get_current_user),
    two_factor_service: TwoFactorService = Depends(get_two_factor_service)
):
    """
    Disable 2FA for user.

    **Security:**
    - Requires authentication (Bearer token)
    - Requires current password confirmation
    - Clears secret and backup codes from DB

    **Request:**
    - `password`: Current password for verification

    **Response:**
    - Success message
    - 2FA status (enabled: false)

    **Errors:**
    - 400: 2FA not enabled
    - 401: Unauthorized or incorrect password
    - 500: Internal error

    **Source:** TASK-M01-011
    """
    try:
        user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

        # Get user
        user_repo = UserRepository()
        user = await user_repo.get_by_id(user_id)

        if not user or not user.get('two_factor_enabled'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="2FA is not enabled for this account"
            )

        # Verify password
        user_with_password = await user_repo.find_by_email_with_password(user['email'])
        if not user_with_password:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed"
            )

        password_service = PasswordService()
        if not await password_service.verify_password(request.password, user_with_password['password_hash']):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect password"
            )

        # Disable 2FA
        await two_factor_service.disable_2fa(user_id)

        logger.info(f"2FA disabled for user {user_id}")

        return TwoFactorDisableResponse(
            message="2FA disabled successfully.",
            two_factor_enabled=False
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error disabling 2FA for user {current_user.get('sub')}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to disable 2FA"
        )


@router.get("/status", response_model=TwoFactorStatusResponse, status_code=200)
async def get_two_factor_status(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get user's current 2FA status.

    **Response:**
    - `two_factor_enabled`: Whether 2FA is enabled
    - `backup_codes_remaining`: Number of unused backup codes

    **Security:**
    - Requires authentication (Bearer token)
    - Returns only current user's status

    **Source:** TASK-M01-011
    """
    try:
        user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

        # Get user
        user_repo = UserRepository()
        user = await user_repo.get_by_id(user_id)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Count remaining backup codes
        backup_codes_remaining = None
        if user.get('two_factor_enabled') and user.get('two_factor_backup_codes'):
            import json
            backup_codes = user.get('two_factor_backup_codes')
            codes = json.loads(backup_codes) if isinstance(backup_codes, str) else backup_codes
            backup_codes_remaining = len(codes) if isinstance(codes, list) else 0

        return TwoFactorStatusResponse(
            two_factor_enabled=user.get('two_factor_enabled') or False,
            backup_codes_remaining=backup_codes_remaining
        )

    except Exception as e:
        logger.error(f"Error getting 2FA status for user {current_user.get('sub')}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get 2FA status"
        )
