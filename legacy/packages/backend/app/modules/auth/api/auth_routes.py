"""
= TaxasGE Authentication & Authorization API
JWT-based authentication with role-based access control (RBAC)
Updated to use AuthService, PasswordService, and JWTService
"""

from fastapi import APIRouter, HTTPException, Depends, status, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, EmailStr, validator, model_validator
from typing import Optional, Dict, Any, List, Union
from datetime import datetime
from enum import Enum
from loguru import logger
from app.config import get_settings
from app.core.errors import TranslatedException, ErrorCode

from app.core.cache import check_rate_limit
from app.core.events import EventBus, EventType
from app.modules.auth.services.auth_service import get_auth_service
from app.modules.auth.services.session_service import get_session_service
from app.modules.users.models.user import (
    UserCreate,
    UserResponse,
    UserProfile,
    CitizenProfile,
    BusinessProfile,
    UserRole,
    UserStatus,
)
from app.modules.auth.models.auth_models import (
    TokenRefreshRequest,
    LogoutRequest,
    TokenRefreshResponse,
    LogoutResponse,
)

# Create router
router = APIRouter()
security = HTTPBearer()


def _set_refresh_cookie(response: JSONResponse, refresh_token: str, max_age: int = 30 * 24 * 3600) -> None:
    """Set refresh_token as HttpOnly Secure cookie on the response."""
    settings = get_settings()
    is_prod = settings.ENVIRONMENT not in ("development", "test")
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=is_prod,  # HTTPS only in prod/staging
        samesite="strict",
        path="/api/v1/auth",  # Only sent to auth endpoints
        max_age=max_age,
    )


def _set_access_cookie(response: JSONResponse, access_token: str, max_age: int = 35 * 60) -> None:
    """Set access_token as HttpOnly Secure cookie for middleware JWT verification.
    Path=/ so middleware on all routes can read it. 35min aligned with JWT lifetime + grace."""
    settings = get_settings()
    is_prod = settings.ENVIRONMENT not in ("development", "test")
    response.set_cookie(
        key="taxasge_auth_token",
        value=access_token,
        httponly=True,
        secure=is_prod,
        samesite="strict",
        path="/",
        max_age=max_age,
    )


def _clear_refresh_cookie(response: JSONResponse) -> None:
    """Clear refresh_token cookie from the response."""
    settings = get_settings()
    is_prod = settings.ENVIRONMENT not in ("development", "test")
    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        secure=is_prod,
        samesite="strict",
        path="/api/v1/auth",
    )
    response.delete_cookie(
        key="taxasge_auth_token",
        httponly=True,
        secure=is_prod,
        samesite="strict",
        path="/",
    )


# Request/Response Models
class LoginRequest(BaseModel):
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=6, description="User password")
    remember_me: bool = Field(False, description="Extended session duration")


class RegisterRequest(BaseModel):
    """
    Registration request model (Step 2 of two-step registration)

    IMPORTANT: Aligned with schema_taxage.sql users table (lines 1044-1078)
    All fields map to REAL database columns only.
    """
    email: EmailStr = Field(..., description="User email address")
    verification_code: str = Field(
        ...,
        min_length=6,
        max_length=6,
        pattern="^\\d{6}$",
        description="6-digit verification code sent to email"
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=100,
        description="Password (min 8 chars, must contain: uppercase, lowercase, digit, special char)"
    )
    first_name: str = Field(..., min_length=2, max_length=50, description="First name")
    last_name: str = Field(..., min_length=2, max_length=50, description="Last name")
    phone: str = Field(
        ...,
        pattern="^(222|555|551|333)\\d{6}$",
        description="Phone number (9 digits: 222/555/551/333 + 6 digits). Example: 222123456"
    )
    role: UserRole = Field(default=UserRole.citizen, description="User role (citizen or business)")

    # Optional: Basic contact info (exist in users table)
    address: Optional[str] = Field(None, max_length=200, description="User address")
    city: Optional[str] = Field(None, max_length=100, description="City")
    preferred_language: Optional[str] = Field(
        None,
        pattern="^(es|fr|en)$",
        description="Preferred language (es/fr/en). If not provided, uses Accept-Language header"
    )

    # Phase 10/B — Legal acceptance (mobile only, citizen/business/accountant only).
    # Both fields are Optional at the schema level so the existing web sign-up
    # flow keeps working unchanged. The service layer enforces:
    # if role IN (citizen, business, accountant) AND versions are provided
    # (mobile case), they must match settings.LEGAL_*_VERSION exactly,
    # otherwise 400 outdated_legal_versions. admin/agent/funcionario are
    # exempt entirely. See migration 331 + .claude/plans/MOBILE_PHASE_10_B_LEGAL_DETAILED.md.
    terms_version_accepted: Optional[str] = Field(
        None,
        min_length=1,
        max_length=16,
        description="Version of Terms of Service the user is accepting (mobile-only field)"
    )
    privacy_version_accepted: Optional[str] = Field(
        None,
        min_length=1,
        max_length=16,
        description="Version of Privacy Policy the user is accepting (mobile-only field)"
    )

    @model_validator(mode='after')
    def validate_password_strength(self):
        """Validate password contains: uppercase, lowercase, digit, special character"""
        password = self.password
        if not any(c.isupper() for c in password):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in password):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in password):
            raise ValueError("Password must contain at least one digit")
        if not any(not c.isalnum() for c in password):
            raise ValueError("Password must contain at least one special character")
        return self


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: Dict[str, Any]


class RequestVerificationRequest(BaseModel):
    """Request to send verification code to email"""
    email: EmailStr = Field(..., description="Email address to verify")


class RequestVerificationResponse(BaseModel):
    """Response after requesting verification code"""
    message: str = Field(..., description="Success message")
    email: str = Field(..., description="Email where code was sent")
    expires_in: int = Field(..., description="Code validity duration in seconds")


class PasswordResetRequestRequest(BaseModel):
    email: EmailStr = Field(..., description="User email address")


class PasswordResetRequestResponse(BaseModel):
    message: str
    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    token: str = Field(..., min_length=32, max_length=64, description="Password reset token")
    new_password: str = Field(..., min_length=8, description="New password (min 8 characters)")


class PasswordResetConfirmResponse(BaseModel):
    message: str


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(..., min_length=6, description="Current password")


class PasswordChangeResponse(BaseModel):
    message: str
    email: str


class PasswordChangeVerifyRequest(BaseModel):
    email: str = Field(..., description="User email")
    verification_code: str = Field(..., min_length=6, max_length=6, description="6-digit verification code")
    new_password: str = Field(..., min_length=8, description="New password (min 8 characters)")

    @model_validator(mode='after')
    def validate_password_strength(self):
        """Validate new password contains: uppercase, lowercase, digit, special character"""
        password = self.new_password
        if not any(c.isupper() for c in password):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in password):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in password):
            raise ValueError("Password must contain at least one digit")
        if not any(not c.isalnum() for c in password):
            raise ValueError("Password must contain at least one special character")
        return self


class PasswordChangeVerifyResponse(BaseModel):
    message: str


class EmailVerifyRequest(BaseModel):
    verification_code: str = Field(..., min_length=6, max_length=6, description="6-digit verification code")


class EmailVerifyResponse(BaseModel):
    message: str


class EmailResendRequest(BaseModel):
    pass  # No body needed, use current_user from token


class EmailResendResponse(BaseModel):
    message: str
    email: EmailStr


class TwoFactorLoginResponse(BaseModel):
    """Response when 2FA is required after login"""

    requires_2fa: bool = Field(True, description="Indicates 2FA verification is required")
    temp_token: str = Field(..., description="Temporary token for 2FA verification (5 min validity)")
    message: str = Field(
        default="2FA verification required. Please provide your 2FA code.",
        description="User-facing message",
    )


class TwoFactorVerifyRequest(BaseModel):
    """Request to verify 2FA code and complete login"""

    temp_token: str = Field(..., description="Temporary token from login response")
    code: str = Field(..., description="6-digit TOTP code or 8-char backup code (XXXX-XXXX)")

    class Config:
        schema_extra = {
            "example": {"temp_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...", "code": "123456"}
        }


# Dependency to get client info from request
def get_client_info(request: Request) -> tuple[Optional[str], Optional[str]]:
    """Extract client IP and user agent from request"""
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return ip_address, user_agent


# Dependency to get current user from token
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Dict[str, Any]:
    """
    Validate access token and return current user data

    Args:
        credentials: Bearer token from Authorization header

    Returns:
        Dict: Current user data from token

    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        auth_service = get_auth_service()
        token_data = await auth_service.validate_access_token(credentials.credentials)

        if not token_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired access token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return token_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


# API Endpoints
@router.get("/")
async def get_auth_info():
    """Get authentication API information"""
    return {
        "message": "TaxasGE Authentication API",
        "version": "2.4.0",  # TASK-M01-013: 2FA login integration added
        "endpoints": {
            "register": "POST /register - Register new user",
            "login": "POST /login - User login (returns temp_token if 2FA enabled)",
            "login_2fa_verify": "POST /login/2fa-verify - Verify 2FA code and complete login",
            "refresh": "POST /refresh - Refresh access token",
            "logout": "POST /logout - Logout user",
            "profile": "GET /profile - Get current user profile",
            "password_reset_request": "POST /password/reset/request - Request password reset email",
            "password_reset_confirm": "POST /password/reset/confirm - Confirm password reset with token",
            "email_verify": "POST /email/verify - Verify email with 6-digit code",
            "email_resend": "POST /email/resend - Resend email verification code",
            "sessions": "GET /sessions - Get active sessions for current user",
        },
        "security": {
            "token_type": "JWT Bearer",
            "access_token_duration": "60 minutes",
            "refresh_token_duration": "7 days",
            "password_hashing": "bcrypt (12 rounds)",
            "password_reset_token_validity": "1 hour",
            "email_verification_code_validity": "15 minutes",
        },
    }


@router.post(
    "/request-verification-code",
    response_model=RequestVerificationResponse,
    status_code=status.HTTP_200_OK,
)
async def request_verification_code(request: RequestVerificationRequest, req: Request):
    """
    Step 1 of 2-step registration: Send verification code to email

    Flow:
    1. Validate email syntax and DNS
    2. Check if email already registered
    3. Generate 6-digit code
    4. Store in pending_registrations
    5. Send email with code
    6. Return success

    Args:
        request: Email to verify
        req: FastAPI request object

    Returns:
        RequestVerificationResponse: Success message with expiration time

    Raises:
        HTTPException 400: Invalid email or already registered
        HTTPException 429: Rate limit exceeded
        HTTPException 500: Failed to send email
    """
    try:
        # Rate limit: 3 requests per 5 minutes per email
        is_allowed, remaining = await check_rate_limit(
            identifier=request.email.lower(),
            endpoint="/auth/request-verification-code",
            max_requests=3,
            window_seconds=300,
        )
        if not is_allowed:
            raise TranslatedException(ErrorCode.TOO_MANY_ATTEMPTS)
        from app.utils.email_validator import EmailValidator
        from app.repositories.pending_registration_repository import PendingRegistrationRepository
        from app.modules.communications.services.email_service import EmailService
        from app.config import get_settings
        from app.repositories.user_repository import UserRepository
        import secrets

        settings = get_settings()

        # 1. Validate email (syntax + DNS)
        is_valid, error_msg = EmailValidator.validate_email(request.email)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email invalide"
            )

        # 2. Check if email already registered
        # SECURITY: Return same success response to prevent email enumeration
        user_repo = UserRepository()
        existing = await user_repo.find_by_email(request.email, use_supabase=False)
        if existing:
            logger.info(f"Verification code requested for already registered email: {request.email}")
            return RequestVerificationResponse(
                message="Code de vérification envoyé à votre email",
                email=request.email,
                expires_in=900
            )

        # 3. Generate 6-digit code (cryptographically secure)
        code = ''.join([str(secrets.randbelow(10)) for _ in range(6)])

        # 4. Store in pending_registrations (replaces existing if any)
        pending_repo = PendingRegistrationRepository()
        await pending_repo.create(request.email, code, expires_in_minutes=15)

        # 5. Send email
        email_service = EmailService(
            smtp_host=settings.SMTP_HOST,
            smtp_port=settings.SMTP_PORT,
            smtp_username=settings.SMTP_USERNAME,
            smtp_password=settings.SMTP_PASSWORD,
            smtp_use_tls=settings.SMTP_USE_TLS,
            smtp_from_email=settings.SMTP_FROM_EMAIL,
            smtp_from_name=settings.SMTP_FROM_NAME,
        )

        email_sent = email_service.send_verification_code(
            to_email=request.email,
            verification_code=code,
            user_name=request.email.split('@')[0]  # Temporary name until full registration
        )

        if not email_sent:
            # Clean up pending registration if email failed
            await pending_repo.delete_by_email(request.email)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Impossible d'envoyer l'email de vérification"
            )

        # 6. Return success
        logger.info(f"Verification code sent to {request.email}")
        return RequestVerificationResponse(
            message="Code de vérification envoyé à votre email",
            email=request.email,
            expires_in=900  # 15 minutes
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in request_verification_code: {str(e)}")
        raise TranslatedException(ErrorCode.SERVER_ERROR)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    req: Request,
):
    """
    Step 2 of 2-step registration: Verify code and create user

    Flow:
    1. Verify code in pending_registrations
    2. Check not expired and attempts < 5
    3. Create user with email_verified=True
    4. Delete from pending_registrations
    5. Generate JWT tokens
    6. Return TokenResponse

    Args:
        request: Registration data with verification code
        req: FastAPI request object

    Returns:
        TokenResponse: Access/refresh tokens and user data

    Raises:
        HTTPException 400: Invalid/expired code or registration fails
        HTTPException 429: Rate limit exceeded
    """
    try:
        # Rate limit: 5 attempts per 15 minutes per IP
        ip_address = req.client.host if req.client else "unknown"
        is_allowed, remaining = await check_rate_limit(
            identifier=ip_address,
            endpoint="/auth/register",
            max_requests=5,
            window_seconds=900,
        )
        if not is_allowed:
            raise TranslatedException(ErrorCode.TOO_MANY_ATTEMPTS)

        from app.repositories.pending_registration_repository import PendingRegistrationRepository

        # STEP 1: Verify email verification code
        pending_repo = PendingRegistrationRepository()
        is_valid = await pending_repo.verify_code(request.email, request.verification_code)

        if not is_valid:
            raise TranslatedException(ErrorCode.INVALID_VERIFICATION)

        # Get client info
        ip_address, user_agent = get_client_info(req)

        # Determine preferred language
        # Priority: 1. Request field, 2. Accept-Language header, 3. Default "es"
        preferred_lang = request.preferred_language
        if not preferred_lang:
            # Extract from Accept-Language header
            accept_lang = req.headers.get("Accept-Language", "")
            # Parse Accept-Language: "es-ES,es;q=0.9,en;q=0.8" -> "es"
            if accept_lang:
                lang_code = accept_lang.split(",")[0].split("-")[0].lower()
                if lang_code in ("es", "fr", "en"):
                    preferred_lang = lang_code
        if not preferred_lang:
            preferred_lang = "es"  # Default to Spanish

        # Create UserProfile with ONLY fields that exist in users table
        # NOTE: Extended profiles (citizen/business specific) will be in MODULE_03
        user_profile = UserProfile(
            first_name=request.first_name,
            last_name=request.last_name,
            phone=request.phone,
            address=request.address,
            city=request.city,
            language=preferred_lang,  # Use detected or default language
        )

        # Create UserCreate model (NO citizen_profile/business_profile for now)
        user_data = UserCreate(
            email=request.email,
            password=request.password,
            role=request.role,
            profile=user_profile,
            email_verified=True,  # Already verified via two-step registration
        )

        # STEP 2: Register user via AuthService
        # Note: Email is already verified, so user will be created with email_verified=True
        auth_service = get_auth_service()
        result = await auth_service.register(
            user_data=user_data,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # STEP 2.5: Phase 10/B — persist legal acceptance for mobile sign-up.
        # Public-onboarding roles (citizen/business/accountant) on mobile send
        # `terms_version_accepted` + `privacy_version_accepted`. We validate
        # exact match against settings (force-update mobile if stale) and
        # persist on the freshly created users row. Web sign-up sends None →
        # no validation, NULL stays in BD (alignment with V1 web scope).
        # admin/agent/funcionario are exempt regardless.
        # See migration 331 + .claude/plans/MOBILE_PHASE_10_B_LEGAL_DETAILED.md
        if (
            request.role in ("citizen", "business", "accountant")
            and request.terms_version_accepted is not None
            and request.privacy_version_accepted is not None
        ):
            from app.config import settings as _settings
            from app.database.connection import get_db_pool
            from datetime import datetime, timezone

            if request.terms_version_accepted != _settings.LEGAL_TERMS_VERSION:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "outdated_terms_version",
                        "expected": _settings.LEGAL_TERMS_VERSION,
                        "received": request.terms_version_accepted,
                    },
                )
            if request.privacy_version_accepted != _settings.LEGAL_PRIVACY_VERSION:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "outdated_privacy_version",
                        "expected": _settings.LEGAL_PRIVACY_VERSION,
                        "received": request.privacy_version_accepted,
                    },
                )

            new_user_id = result.get("user", {}).get("id")
            if new_user_id:
                _now = datetime.now(timezone.utc)
                _pool = await get_db_pool()
                async with _pool.acquire() as _conn:
                    await _conn.execute(
                        """
                        UPDATE users
                        SET terms_accepted_at   = $1,
                            terms_version       = $2,
                            privacy_accepted_at = $3,
                            privacy_version     = $4,
                            updated_at          = $5
                        WHERE id = $6
                        """,
                        _now,
                        request.terms_version_accepted,
                        _now,
                        request.privacy_version_accepted,
                        _now,
                        new_user_id,
                    )
                logger.info(
                    f"Legal acceptance persisted for new user {new_user_id} "
                    f"(terms={request.terms_version_accepted}, "
                    f"privacy={request.privacy_version_accepted})"
                )

        # STEP 3: Delete pending registration (cleanup)
        await pending_repo.delete_by_email(request.email)

        # STEP 4: Publish USER_REGISTERED event for welcome notification
        try:
            EventBus.publish_nowait(
                EventType.USER_REGISTERED,
                {
                    "user_id": result.get("user", {}).get("id"),
                    "user_email": request.email,
                    "user_name": f"{request.first_name} {request.last_name}",
                    "user_phone": request.phone,
                    "preferred_language": preferred_lang,
                    "role": request.role,
                    "timestamp": datetime.now().isoformat(),
                }
            )
        except Exception:
            pass  # Non-blocking

        logger.info(f"User registered successfully with verified email: {request.email}")
        return TokenResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration failed. Please try again.",
        )


@router.post("/login", response_model=Union[TokenResponse, TwoFactorLoginResponse])
async def login(
    request: LoginRequest,
    req: Request,
):
    """
    Login user and create session

    **Workflow**:
    1. Validate email and password
    2. Check if user has 2FA enabled:
       - If 2FA enabled: Return temp_token + requires_2fa=true
       - If 2FA disabled: Return access/refresh tokens immediately
    3. If 2FA required, client calls /login/2fa-verify with code

    Args:
        request: Login credentials
        req: FastAPI request object

    Returns:
        Union[TokenResponse, TwoFactorLoginResponse]:
            - TokenResponse: If 2FA disabled (access/refresh tokens + user data)
            - TwoFactorLoginResponse: If 2FA enabled (temp_token + requires_2fa flag)

    Raises:
        HTTPException: If login fails

    Source: TASK-M01-013 (Login 2FA Integration)
    """
    try:
        # Rate limit: 10 attempts per 15 minutes per IP
        ip_address_rl = req.client.host if req.client else "unknown"
        is_allowed, remaining = await check_rate_limit(
            identifier=ip_address_rl,
            endpoint="/auth/login",
            max_requests=10,
            window_seconds=900,
        )
        if not is_allowed:
            raise TranslatedException(ErrorCode.TOO_MANY_ATTEMPTS)

        # Get client info
        ip_address, user_agent = get_client_info(req)

        # Login via AuthService
        auth_service = get_auth_service()
        result = await auth_service.login(
            email=request.email,
            password=request.password,
            remember_me=request.remember_me,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # Check if 2FA is required
        if result.get("requires_2fa"):
            logger.info(f"User logged in, 2FA verification required: {request.email}")
            return TwoFactorLoginResponse(**result)

        logger.info(f"User logged in successfully: {request.email}")
        # Set tokens as HttpOnly cookies + return in body (backward compatible)
        token_resp = TokenResponse(**result)
        response = JSONResponse(content=token_resp.model_dump(mode="json"))
        _set_refresh_cookie(response, result["refresh_token"])
        _set_access_cookie(response, result["access_token"])
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise TranslatedException(ErrorCode.INVALID_CREDENTIALS)


@router.post("/login/2fa-verify", response_model=TokenResponse)
async def verify_2fa_login(
    request: TwoFactorVerifyRequest,
    req: Request = None,
):
    """
    Verify 2FA code and complete login process

    **Workflow**:
    1. User calls /login with email + password
    2. If user has 2FA enabled, receives temp_token + requires_2fa=true
    3. User provides 2FA code (from authenticator app or backup code)
    4. This endpoint verifies code and returns real access/refresh tokens

    Args:
        request: Temp token + 2FA code (TOTP or backup)

    Returns:
        TokenResponse: Access/refresh tokens and user data

    Raises:
        HTTPException: If 2FA verification fails

    **Security**:
    - Temp token is short-lived (5 minutes)
    - Invalid code = authentication failure
    - Backup codes are one-time use
    - Rate limited: 5 attempts per 5 minutes per IP

    Source: TASK-M01-013 (Login 2FA Integration)
    """
    # Rate limit: 5 attempts per 5 minutes per IP (brute-force 6-digit codes)
    if req:
        ip = req.client.host if req.client else "unknown"
        is_allowed, remaining = await check_rate_limit(
            identifier=ip, endpoint="/auth/login/2fa-verify", max_requests=5, window_seconds=300
        )
        if not is_allowed:
            raise TranslatedException(ErrorCode.TOO_MANY_ATTEMPTS)

    try:
        # Verify 2FA code via AuthService
        auth_service = get_auth_service()
        result = await auth_service.verify_2fa_login(
            temp_token=request.temp_token,
            code=request.code,
        )

        logger.info("2FA login verification successful")
        # Set tokens as HttpOnly cookies + return in body (backward compatible)
        token_resp = TokenResponse(**result)
        response = JSONResponse(content=token_resp.model_dump(mode="json"))
        _set_refresh_cookie(response, result["refresh_token"])
        _set_access_cookie(response, result["access_token"])
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"2FA login verification error: {str(e)}")
        raise TranslatedException(ErrorCode.INVALID_VERIFICATION)


@router.post("/refresh")
async def refresh_token(
    request: TokenRefreshRequest,
    req: Request,
):
    """
    Refresh access token using refresh token.
    Reads refresh_token from HttpOnly cookie first, falls back to request body.

    Args:
        request: Refresh token request (body fallback)
        req: FastAPI request object

    Returns:
        TokenRefreshResponse: New access/refresh tokens (+ Set-Cookie)

    Raises:
        HTTPException: If refresh fails
    """
    try:
        # Prefer HttpOnly cookie, fallback to body (backward compatible)
        refresh_tok = req.cookies.get("refresh_token") or request.refresh_token
        if not refresh_tok:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No refresh token provided",
            )

        # Get client info
        ip_address, user_agent = get_client_info(req)

        # Refresh tokens via AuthService
        auth_service = get_auth_service()
        result = await auth_service.refresh_tokens(
            refresh_token=refresh_tok,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        logger.info("Tokens refreshed successfully")
        # Set new tokens as HttpOnly cookies
        resp_data = TokenRefreshResponse(**result) if isinstance(result, dict) else result
        response = JSONResponse(content=resp_data.model_dump(mode="json") if hasattr(resp_data, 'model_dump') else result)
        new_refresh = result.get("refresh_token") if isinstance(result, dict) else getattr(result, "refresh_token", None)
        new_access = result.get("access_token") if isinstance(result, dict) else getattr(result, "access_token", None)
        if new_refresh:
            _set_refresh_cookie(response, new_refresh)
        if new_access:
            _set_access_cookie(response, new_access)
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}")
        raise TranslatedException(ErrorCode.TOKEN_EXPIRED)


@router.post("/logout")
async def logout(
    request: LogoutRequest,
    req: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Logout user (revoke tokens and session).
    Reads refresh_token from HttpOnly cookie first, falls back to request body.
    Clears the refresh_token cookie on response.

    Args:
        request: Logout request (optional refresh token, all_sessions flag)
        req: FastAPI request object
        current_user: Current authenticated user

    Returns:
        LogoutResponse: Logout status

    Raises:
        HTTPException: If logout fails
    """
    try:
        # Prefer HttpOnly cookie, fallback to body
        refresh_tok = req.cookies.get("refresh_token") or request.refresh_token

        # Logout via AuthService
        auth_service = get_auth_service()
        result = await auth_service.logout(
            refresh_token=refresh_tok,
            all_sessions=request.all_sessions,
        )

        logger.info(f"User logged out: {current_user.get('email')}")
        # Clear the refresh_token cookie
        resp_data = result if isinstance(result, dict) else result.model_dump(mode="json") if hasattr(result, 'model_dump') else {"message": "Logged out", "sessions_revoked": 0}
        response = JSONResponse(content=resp_data)
        _clear_refresh_cookie(response)
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        raise TranslatedException(ErrorCode.BAD_REQUEST)


@router.get("/profile", response_model=UserResponse)
async def get_profile(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Get current user profile

    Args:
        current_user: Current authenticated user

    Returns:
        UserResponse: User profile data

    Raises:
        HTTPException: If profile fetch fails
    """
    try:
        # Get user from database
        from app.repositories.user_repository import UserRepository

        user_repo = UserRepository()
        user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")
        user = await user_repo.get_by_id(user_id)

        if not user:
            raise TranslatedException(ErrorCode.USER_NOT_FOUND)

        # Return user response
        return UserResponse(
            id=user.get("id"),
            email=user.get("email"),
            role=user.get("role"),
            status=user.get("status"),
            first_name=user.get("first_name"),
            last_name=user.get("last_name"),
            phone_number=user.get("phone_number"),
            address=user.get("address"),
            city=user.get("city"),
            preferred_language=user.get("preferred_language", "es"),
            avatar_url=user.get("avatar_url"),
            created_at=user.get("created_at"),
            updated_at=user.get("updated_at"),
            last_login=user.get("last_login"),
            email_verified=user.get("email_verified", False),
            two_factor_enabled=user.get("two_factor_enabled", False),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Profile fetch error: {str(e)}")
        raise TranslatedException(ErrorCode.SERVER_ERROR)


# =============================================================================
# PASSWORD RESET ENDPOINTS (MODULE_02)
# =============================================================================

@router.post("/password/reset/request", response_model=PasswordResetRequestResponse)
async def request_password_reset(request: PasswordResetRequestRequest):
    """
    Request password reset - Send reset email with token

    **Public endpoint** (no authentication required)

    Args:
        request: Email address

    Returns:
        PasswordResetRequestResponse: Confirmation message

    Raises:
        HTTPException: If email sending fails

    Business Rules:
        - For security, always returns success (even if email doesn't exist)
        - Token valid for 1 hour
        - Email sent with reset link containing token

    Source: .github/docs-internal/Documentations/Backend/API_REFERENCE.md
    """
    try:
        # Rate limit: 3 requests per hour per email
        is_allowed, remaining = await check_rate_limit(
            identifier=request.email.lower(),
            endpoint="/auth/password-reset-request",
            max_requests=3,
            window_seconds=3600,
        )
        if not is_allowed:
            # Still return success for security (don't reveal rate limiting vs no-email)
            return PasswordResetRequestResponse(
                message="If your email exists in our system, you will receive a password reset link shortly.",
                email=request.email
            )

        # Request password reset via AuthService
        auth_service = get_auth_service()
        email_sent = await auth_service.request_password_reset(email=request.email)

        # Log the result for debugging (but don't expose to user)
        if not email_sent:
            logger.error(f"Password reset email failed to send to {request.email}, but returning success for security")

        # Always return success (don't reveal if email exists or if email failed)
        return PasswordResetRequestResponse(
            message="If your email exists in our system, you will receive a password reset link shortly.",
            email=request.email
        )

    except Exception as e:
        logger.error(f"Password reset request error: {str(e)}")
        # For security: Still return success to avoid revealing internal errors
        # But log the full error for debugging
        return PasswordResetRequestResponse(
            message="If your email exists in our system, you will receive a password reset link shortly.",
            email=request.email
        )


@router.post("/password/reset/confirm", response_model=PasswordResetConfirmResponse)
async def confirm_password_reset(request: PasswordResetConfirmRequest, req: Request = None):
    """
    Confirm password reset - Validate token and update password

    **Public endpoint** (no authentication required)

    Args:
        request: Reset token and new password

    Returns:
        PasswordResetConfirmResponse: Confirmation message

    Raises:
        HTTPException: If token invalid/expired or password update fails

    Business Rules:
        - Token must be valid and not expired (1 hour validity)
        - New password must meet strength requirements (min 8 chars)
        - Token cleared after successful reset
        - Confirmation email sent
        - Rate limited: 5 per 15 min per IP

    Source: .github/docs-internal/Documentations/Backend/API_REFERENCE.md
    """
    # Rate limit: 5 per 15 min per IP (prevent token brute-force)
    if req:
        ip = req.client.host if req.client else "unknown"
        is_allowed, remaining = await check_rate_limit(
            identifier=ip, endpoint="/auth/password/reset/confirm", max_requests=5, window_seconds=900
        )
        if not is_allowed:
            raise TranslatedException(ErrorCode.TOO_MANY_ATTEMPTS)

    try:
        # Confirm password reset via AuthService
        auth_service = get_auth_service()
        success = await auth_service.confirm_password_reset(
            reset_token=request.token,
            new_password=request.new_password
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password reset failed",
            )

        return PasswordResetConfirmResponse(
            message="Password reset successful. You can now login with your new password."
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password reset confirm error: {str(e)}")
        raise TranslatedException(ErrorCode.INVALID_VERIFICATION)


# =============================================================================
# PASSWORD CHANGE ENDPOINT (AUTHENTICATED USERS)
# =============================================================================

@router.post("/password/change", response_model=PasswordChangeResponse)
async def change_password(
    request: PasswordChangeRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Request password change - Validates current password and sends verification code

    **Requires authentication** (Bearer token)

    Args:
        request: Current password only
        credentials: Bearer token from Authorization header
        current_user: Current authenticated user from token

    Returns:
        PasswordChangeResponse: Success message and email

    Raises:
        HTTPException: If current password incorrect

    Workflow (SIMPLIFIED):
        1. Validate current password
        2. Generate 6-digit verification code
        3. Store code in pending_registrations (NO password hash stored!)
        4. Send verification code to email
        5. User calls /password/change/verify with code + new password
    """
    # Rate limit: 5 per 15 min per user (prevent password brute-force)
    user_id_rl = current_user.get("sub") or current_user.get("id") or "unknown"
    is_allowed, remaining = await check_rate_limit(
        identifier=str(user_id_rl), endpoint="/auth/password/change", max_requests=5, window_seconds=900
    )
    if not is_allowed:
        raise TranslatedException(ErrorCode.TOO_MANY_ATTEMPTS)

    try:
        # Get user from database
        from app.repositories.user_repository import UserRepository
        user_repo = UserRepository()
        user_id = current_user.get("sub") or current_user.get("id")
        user = await user_repo.get_by_id(user_id)

        if not user:
            raise TranslatedException(ErrorCode.USER_NOT_FOUND)

        # Verify current password
        from app.modules.auth.services.password_service import PasswordService
        password_service = PasswordService()
        is_valid = await password_service.verify_password(
            password=request.current_password,
            hashed_password=user.get("password_hash")
        )

        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )

        # Generate verification code
        import secrets
        verification_code = ''.join([str(secrets.randbelow(10)) for _ in range(6)])

        # Store ONLY the verification code (no password hash!)
        from app.repositories.pending_registration_repository import PendingRegistrationRepository
        pending_repo = PendingRegistrationRepository()
        await pending_repo.create(
            email=user.get("email"),
            verification_code=verification_code,
            expires_in_minutes=10
        )

        # Send verification email
        from app.modules.communications.services.email_service import EmailService
        from app.config import get_settings
        settings = get_settings()

        email_service = EmailService(
            smtp_host=settings.SMTP_HOST,
            smtp_port=settings.SMTP_PORT,
            smtp_username=settings.SMTP_USERNAME,
            smtp_password=settings.SMTP_PASSWORD,
            smtp_use_tls=settings.SMTP_USE_TLS,
            smtp_from_email=settings.SMTP_FROM_EMAIL,
            smtp_from_name=settings.SMTP_FROM_NAME
        )

        email_service.send_verification_code(
            to_email=user.get("email"),
            verification_code=verification_code,
            user_name=user.get("first_name")
        )

        logger.info(f"Password change verification code sent to {user.get('email')}")

        return PasswordChangeResponse(
            message="Verification code sent to your email. Please enter the code and your new password to complete the change.",
            email=user.get("email")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password change error: {str(e)}")
        raise TranslatedException(ErrorCode.SERVER_ERROR)


@router.post("/password/change/verify", response_model=PasswordChangeVerifyResponse)
async def verify_password_change(request: PasswordChangeVerifyRequest, req: Request = None):
    """
    Verify password change with code and apply new password (SIMPLIFIED APPROACH)

    **Public endpoint** (no authentication required - code validates identity)

    Args:
        request: Email, verification code (6 digits), and new password

    Returns:
        PasswordChangeVerifyResponse: Confirmation message

    Raises:
        HTTPException: If code invalid/expired or password update fails

    Business Rules:
        - Code must be valid and not expired (10 minutes validity)
        - New password validated for strength (upper, lower, digit, special)
        - New password hash applied to user account immediately
        - Code cleared after successful verification
        - Rate limited: 5 per 5 min per IP (6-digit code brute-force protection)

    Source: SECURITY_SETTINGS_README.md lines 88-95
    """
    # Rate limit: 5 per 5 min per IP (brute-force 6-digit codes = 1M possibilities)
    if req:
        ip = req.client.host if req.client else "unknown"
        is_allowed, remaining = await check_rate_limit(
            identifier=ip, endpoint="/auth/password/change/verify", max_requests=5, window_seconds=300
        )
        if not is_allowed:
            raise TranslatedException(ErrorCode.TOO_MANY_ATTEMPTS)

    try:
        # Get pending registration by email
        from app.repositories.pending_registration_repository import PendingRegistrationRepository
        pending_repo = PendingRegistrationRepository()

        # Verify code using existing method (handles expiration, attempts, etc.)
        is_valid = await pending_repo.verify_code(request.email, request.verification_code)

        if not is_valid:
            raise TranslatedException(ErrorCode.INVALID_VERIFICATION)

        # Get user by email (use find_by_email_with_password to get Dict, not UserResponse)
        from app.repositories.user_repository import UserRepository
        user_repo = UserRepository()
        user = await user_repo.find_by_email_with_password(request.email)

        if not user:
            # Clean up pending record even if user not found
            await pending_repo.delete_by_email(request.email)
            raise TranslatedException(ErrorCode.USER_NOT_FOUND)

        # Hash the new password
        from app.modules.auth.services.password_service import PasswordService
        password_service = PasswordService()
        new_password_hash = await password_service.hash_password(request.new_password)

        # Update user password in database
        success = await user_repo.update_password(user.get("id") if isinstance(user, dict) else user["id"], new_password_hash)

        if not success:
            raise TranslatedException(ErrorCode.SERVER_ERROR)

        # Delete pending record
        await pending_repo.delete_by_email(request.email)

        logger.info(f"Password changed successfully for user {request.email}")

        return PasswordChangeVerifyResponse(
            message="Password changed successfully. You can now login with your new password."
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password change verification error: {str(e)}")
        raise TranslatedException(ErrorCode.SERVER_ERROR)


# =============================================================================
# EMAIL VERIFICATION ENDPOINTS (MODULE_02)
# =============================================================================

@router.post("/email/verify", response_model=EmailVerifyResponse)
async def verify_email(request: EmailVerifyRequest, req: Request = None):
    """
    Verify email address with 6-digit code

    **Public endpoint** (no authentication required)

    Args:
        request: Email verification code (6 digits)

    Returns:
        EmailVerifyResponse: Confirmation message

    Raises:
        HTTPException: If code invalid/expired or verification fails

    Business Rules:
        - Code must be valid and not expired (15 minutes validity)
        - Email marked as verified in database
        - Code cleared after successful verification
        - Rate limited: 5 per 5 min per IP

    Source: .github/docs-internal/Documentations/Backend/API_REFERENCE.md
    """
    # Rate limit: 5 per 5 min per IP (brute-force 6-digit codes)
    if req:
        ip = req.client.host if req.client else "unknown"
        is_allowed, remaining = await check_rate_limit(
            identifier=ip, endpoint="/auth/email/verify", max_requests=5, window_seconds=300
        )
        if not is_allowed:
            raise TranslatedException(ErrorCode.TOO_MANY_ATTEMPTS)

    try:
        # Verify email via AuthService
        auth_service = get_auth_service()
        success = await auth_service.verify_email_code(
            verification_code=request.verification_code
        )

        if not success:
            raise TranslatedException(ErrorCode.INVALID_VERIFICATION)

        return EmailVerifyResponse(
            message="Email verified successfully."
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Email verification error: {str(e)}")
        raise TranslatedException(ErrorCode.INVALID_VERIFICATION)


@router.post("/email/resend", response_model=EmailResendResponse)
async def resend_verification_email(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Resend email verification code

    **Authenticated endpoint** (requires valid access token)

    Args:
        current_user: Current authenticated user

    Returns:
        EmailResendResponse: Confirmation message with email

    Raises:
        HTTPException: If email sending fails

    Business Rules:
        - User must be authenticated
        - New 6-digit code generated
        - Code valid for 15 minutes
        - Email sent with verification code

    Source: .github/docs-internal/Documentations/Backend/API_REFERENCE.md
    """
    try:
        user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")
        email = current_user.email if hasattr(current_user, 'email') else current_user.get("email")

        # Get existing verification code from pending_registrations
        from app.repositories.pending_registration_repository import PendingRegistrationRepository
        pending_repo = PendingRegistrationRepository()
        pending_record = await pending_repo.find_by_email(email)

        if not pending_record:
            # No pending verification code - generate a new one
            import secrets
            verification_code = ''.join([str(secrets.randbelow(10)) for _ in range(6)])
            await pending_repo.create(email, verification_code, expires_in_minutes=15)
        else:
            # Use existing code
            verification_code = pending_record.get("verification_code")

        # Resend verification email
        from app.modules.communications.services.email_service import EmailService
        from app.config import get_settings
        settings = get_settings()

        email_service = EmailService(
            smtp_host=settings.SMTP_HOST,
            smtp_port=settings.SMTP_PORT,
            smtp_username=settings.SMTP_USERNAME,
            smtp_password=settings.SMTP_PASSWORD,
            smtp_use_tls=settings.SMTP_USE_TLS,
            smtp_from_email=settings.SMTP_FROM_EMAIL,
            smtp_from_name=settings.SMTP_FROM_NAME
        )

        # Get user info for personalization
        from app.repositories.user_repository import UserRepository
        user_repo = UserRepository()
        user = await user_repo.get_by_id(user_id)

        success = email_service.send_verification_code(
            to_email=email,
            verification_code=verification_code,
            user_name=user.get("first_name") if user else email.split('@')[0]
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to send verification email",
            )

        return EmailResendResponse(
            message="Verification code sent successfully.",
            email=email
        )

    except Exception as e:
        logger.error(f"Email resend error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to resend verification email",
        )


# === TASK-M01-008: Sessions Management ===

class SessionInfoResponse(BaseModel):
    """Model for session information response"""
    id: str = Field(..., description="Session ID")
    device: str = Field(..., description="Device type (Desktop/Mobile/Tablet)")
    browser: str = Field(..., description="Browser name")
    location: str = Field(..., description="Location (IP address or City, Country)")
    ip_address: Optional[str] = Field(None, description="IP address")
    created_at: datetime = Field(..., description="Session creation time")
    last_activity: datetime = Field(..., description="Last activity time")
    expires_at: datetime = Field(..., description="Session expiration time")
    is_current: bool = Field(..., description="True if this is the current session")


class SessionsListResponse(BaseModel):
    """Model for sessions list response"""
    sessions: List[SessionInfoResponse] = Field(..., description="List of active sessions")
    total: int = Field(..., description="Total number of active sessions")


@router.get("/sessions", response_model=SessionsListResponse)
async def get_sessions(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Get all active sessions for the current user

    **Authenticated endpoint** (requires valid access token)

    Args:
        credentials: Bearer token from Authorization header
        current_user: Current authenticated user

    Returns:
        SessionsListResponse: List of active sessions with metadata

    Raises:
        HTTPException: If retrieval fails

    Business Rules:
        - Only return non-expired sessions (expires_at > now)
        - Mark current session (matching access_token)
        - Verify user owns all returned sessions (security check)
        - Enrich with device, browser, location metadata
        - Order by created_at desc (most recent first)

    Source: .github/docs-internal/Documentations/Backend/RAPPORT_MODULE_01_AUTHENTICATION.md line 414-417
    """
    try:
        user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")
        access_token = credentials.credentials

        # Get active sessions via SessionService
        session_service = get_session_service()
        sessions_data = await session_service.get_active_sessions(
            user_id=user_id,
            current_token=access_token
        )

        # Convert to response models
        sessions_list = [
            SessionInfoResponse(
                id=session["id"],
                device=session["device"],
                browser=session["browser"],
                location=session["location"],
                ip_address=session.get("ip_address"),
                created_at=session["created_at"],
                last_activity=session["last_activity"],
                expires_at=session["expires_at"],
                is_current=session["is_current"]
            )
            for session in sessions_data
        ]

        logger.info(f"Retrieved {len(sessions_list)} active sessions for user {user_id}")

        return SessionsListResponse(
            sessions=sessions_list,
            total=len(sessions_list)
        )

    except Exception as e:
        logger.error(f"Get sessions error: {str(e)}")
        raise TranslatedException(ErrorCode.SERVER_ERROR)


# =============================================================================
# CRON CLEANUP ENDPOINT (1.8 — Auth Security Hardening)
# =============================================================================

@router.post("/cron/auth-cleanup", status_code=200)
async def cron_auth_cleanup(req: Request):
    """
    Cron endpoint to clean up expired auth data.
    Called by Cloud Scheduler daily.

    Security: Validates X-Cron-Secret header or Cloud Scheduler OIDC token.

    Cleans:
    - Expired sessions (> 7 days past expiry)
    - Expired refresh tokens (> 7 days past expiry)
    - Expired pending registrations
    """
    # Verify cron secret — ALWAYS required (User-Agent is spoofable)
    settings = get_settings()
    cron_secret = getattr(settings, 'CRON_SECRET', None) or settings.JWT_SECRET_KEY
    request_secret = req.headers.get("X-Cron-Secret", "")

    if not request_secret or request_secret != cron_secret:
        logger.warning(f"[AuthCleanup] Unauthorized cron attempt from {req.client.host if req.client else 'unknown'}")
        raise TranslatedException(ErrorCode.FORBIDDEN)

    from app.database.connection import db_manager

    results = {}

    try:
        # 1. Delete expired sessions older than 7 days
        result = await db_manager.execute_command(
            "DELETE FROM sessions WHERE expires_at < NOW() - INTERVAL '7 days'"
        )
        results["sessions_deleted"] = int(result.split()[-1]) if result and result.startswith("DELETE") else 0

        # 2. Delete expired refresh tokens older than 7 days
        result = await db_manager.execute_command(
            "DELETE FROM refresh_tokens WHERE expires_at < NOW() - INTERVAL '7 days'"
        )
        results["refresh_tokens_deleted"] = int(result.split()[-1]) if result and result.startswith("DELETE") else 0

        # 3. Delete expired pending registrations
        result = await db_manager.execute_command(
            "DELETE FROM pending_registrations WHERE expires_at < NOW()"
        )
        results["pending_registrations_deleted"] = int(result.split()[-1]) if result and result.startswith("DELETE") else 0

        total = sum(results.values())
        if total > 0:
            logger.info(f"[AuthCleanup] Cleaned {total} expired records: {results}")

        return {"status": "ok", **results}

    except Exception as e:
        logger.error(f"[AuthCleanup] Error: {e}")
        return {"status": "error", "error": "Internal cleanup error", **results}
