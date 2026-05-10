"""
Legacy Refresh Token Repository - Backwards Compatibility

Re-exports from app.modules.auth.repositories.refresh_token_repository
"""

from app.modules.auth.repositories.refresh_token_repository import RefreshTokenRepository

__all__ = ["RefreshTokenRepository"]
