"""
Auth models for TaxasGE Backend
Pydantic models for authentication requests and responses
"""

from app.modules.auth.models.auth_models import (
    TokenType,
    SessionStatus,
    Session,
    SessionCreate,
    SessionResponse,
    RefreshToken,
    RefreshTokenCreate,
    RefreshTokenResponse,
    TokenRefreshRequest,
    TokenRefreshResponse,
    LogoutRequest,
    LogoutResponse,
)

from app.modules.auth.models.two_factor_models import (
    TwoFactorEnableResponse,
    TwoFactorVerifyRequest,
    TwoFactorVerifyResponse,
    TwoFactorDisableRequest,
    TwoFactorDisableResponse,
    TwoFactorLoginRequest,
    TwoFactorStatusResponse,
)

__all__ = [
    # auth_models
    "TokenType",
    "SessionStatus",
    "Session",
    "SessionCreate",
    "SessionResponse",
    "RefreshToken",
    "RefreshTokenCreate",
    "RefreshTokenResponse",
    "TokenRefreshRequest",
    "TokenRefreshResponse",
    "LogoutRequest",
    "LogoutResponse",
    # two_factor_models
    "TwoFactorEnableResponse",
    "TwoFactorVerifyRequest",
    "TwoFactorVerifyResponse",
    "TwoFactorDisableRequest",
    "TwoFactorDisableResponse",
    "TwoFactorLoginRequest",
    "TwoFactorStatusResponse",
]
