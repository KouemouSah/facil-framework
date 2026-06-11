"""
Two-Factor Authentication (2FA) Pydantic Models for TaxasGE Backend.

TASK-M01-011: 2FA TOTP Implementation
Source: RAPPORT_MODULE_01_AUTHENTICATION.md lines 436-440
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional


class TwoFactorEnableResponse(BaseModel):
    """
    Response model for POST /auth/2fa/enable endpoint.

    Contains TOTP secret, QR code, and backup codes for user to save.
    """
    secret: str = Field(..., description="TOTP secret (base32 encoded, 32 chars)")
    qr_code_svg: str = Field(..., description="SVG QR code for authenticator app")
    backup_codes: List[str] = Field(..., description="10 backup codes (show once!)")
    message: str = Field(
        default="2FA setup initiated. Scan QR code with authenticator app and verify with code.",
        description="Instruction message"
    )

    class Config:
        schema_extra = {
            "example": {
                "secret": "JBSWY3DPEHPK3PXP",
                "qr_code_svg": "<svg>...</svg>",
                "backup_codes": [
                    "1234-5678",
                    "9876-5432",
                    "1111-2222",
                    "3333-4444",
                    "5555-6666",
                    "7777-8888",
                    "9999-0000",
                    "1212-3434",
                    "5656-7878",
                    "9090-1212"
                ],
                "message": "2FA setup initiated. Scan QR code with authenticator app and verify with code."
            }
        }


class TwoFactorVerifyRequest(BaseModel):
    """
    Request model for POST /auth/2fa/verify endpoint.

    User provides TOTP code from authenticator app to confirm 2FA setup.
    """
    secret: str = Field(..., description="TOTP secret from enable response", min_length=32, max_length=32)
    code: str = Field(..., description="6-digit TOTP code from authenticator app", min_length=6, max_length=6)
    backup_codes: List[str] = Field(..., description="Backup codes from enable response (10 codes)")

    @validator('code')
    def validate_code_format(cls, v):
        """Validate TOTP code is 6 digits."""
        if not v.isdigit():
            raise ValueError("Code must be 6 digits")
        if len(v) != 6:
            raise ValueError("Code must be exactly 6 digits")
        return v

    @validator('backup_codes')
    def validate_backup_codes_count(cls, v):
        """Validate backup codes count."""
        if len(v) != 10:
            raise ValueError("Must provide exactly 10 backup codes")
        return v

    class Config:
        schema_extra = {
            "example": {
                "secret": "JBSWY3DPEHPK3PXP",
                "code": "123456",
                "backup_codes": [
                    "1234-5678",
                    "9876-5432",
                    "1111-2222",
                    "3333-4444",
                    "5555-6666",
                    "7777-8888",
                    "9999-0000",
                    "1212-3434",
                    "5656-7878",
                    "9090-1212"
                ]
            }
        }


class TwoFactorVerifyResponse(BaseModel):
    """Response model for POST /auth/2fa/verify endpoint."""
    message: str = Field(..., description="Success message")
    two_factor_enabled: bool = Field(default=True, description="2FA status")

    class Config:
        schema_extra = {
            "example": {
                "message": "2FA enabled successfully. Save your backup codes in a safe place.",
                "two_factor_enabled": True
            }
        }


class TwoFactorDisableRequest(BaseModel):
    """
    Request model for POST /auth/2fa/disable endpoint.

    Requires current password for security.
    """
    password: str = Field(..., description="Current password for verification", min_length=8)

    class Config:
        schema_extra = {
            "example": {
                "password": "MySecurePassword123!"
            }
        }


class TwoFactorDisableResponse(BaseModel):
    """Response model for POST /auth/2fa/disable endpoint."""
    message: str = Field(..., description="Success message")
    two_factor_enabled: bool = Field(default=False, description="2FA status")

    class Config:
        schema_extra = {
            "example": {
                "message": "2FA disabled successfully.",
                "two_factor_enabled": False
            }
        }


class TwoFactorLoginRequest(BaseModel):
    """
    Request model for 2FA login verification step.

    After login with email/password, user with 2FA enabled must provide TOTP code.
    """
    temp_token: str = Field(..., description="Temporary token from login response")
    code: str = Field(..., description="6-digit TOTP code OR 8-char backup code")

    @validator('code')
    def validate_code_format(cls, v):
        """Validate code is either 6 digits (TOTP) or 8 chars with dash (backup)."""
        # TOTP code: 6 digits
        if len(v) == 6 and v.isdigit():
            return v

        # Backup code: XXXX-XXXX (9 chars with dash)
        if len(v) == 9 and v[4] == '-' and v[:4].isdigit() and v[5:].isdigit():
            return v

        raise ValueError("Code must be 6-digit TOTP code or 8-digit backup code (format: XXXX-XXXX)")

    class Config:
        schema_extra = {
            "example": {
                "temp_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "code": "123456"
            }
        }


class TwoFactorStatusResponse(BaseModel):
    """
    Response model for GET /auth/2fa/status endpoint.

    Shows user's current 2FA status.
    """
    two_factor_enabled: bool = Field(..., description="Whether 2FA is enabled")
    backup_codes_remaining: Optional[int] = Field(None, description="Number of unused backup codes")

    class Config:
        schema_extra = {
            "example": {
                "two_factor_enabled": True,
                "backup_codes_remaining": 8
            }
        }
