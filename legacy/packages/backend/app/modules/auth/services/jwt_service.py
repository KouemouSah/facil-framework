"""
JWT Service for TaxasGE Backend
Handles JWT token generation, validation, and refresh
"""

import jwt
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from loguru import logger

_DEFAULT_SECRET = "taxasge-jwt-secret-change-in-production"


class JWTService:
    """Service for JWT token operations"""

    def __init__(
        self,
        secret_key: Optional[str] = None,
        algorithm: str = "HS256",
        access_token_expire_minutes: int = 60,
        refresh_token_expire_days: int = 7,
    ):
        """
        Initialize JWT service

        Args:
            secret_key: Secret key for JWT encoding/decoding (from env if not provided)
            algorithm: JWT algorithm (default HS256)
            access_token_expire_minutes: Access token expiration in minutes
            refresh_token_expire_days: Refresh token expiration in days
        """
        self.secret_key = secret_key or os.getenv("JWT_SECRET_KEY", _DEFAULT_SECRET)

        environment = os.getenv("ENVIRONMENT", "development")
        if self.secret_key == _DEFAULT_SECRET:
            if environment in ("production", "staging"):
                raise RuntimeError(
                    "CRITICAL: JWT_SECRET_KEY is not configured! "
                    "Set JWT_SECRET_KEY environment variable before starting in production/staging."
                )
            logger.warning(
                "Using default JWT secret key! "
                "Set JWT_SECRET_KEY environment variable in production"
            )

        self.algorithm = algorithm
        self.access_token_expire_minutes = access_token_expire_minutes
        self.refresh_token_expire_days = refresh_token_expire_days

        logger.info(
            f"JWTService initialized: {algorithm}, "
            f"access={access_token_expire_minutes}min, "
            f"refresh={refresh_token_expire_days}days"
        )

    def create_access_token(
        self,
        subject: str,
        user_data: Optional[Dict[str, Any]] = None,
        expires_delta: Optional[timedelta] = None,
    ) -> str:
        """
        Create a JWT access token

        Args:
            subject: Token subject (usually user_id)
            user_data: Additional user data to include in token
            expires_delta: Custom expiration time (overrides default)

        Returns:
            str: Encoded JWT access token

        Raises:
            Exception: If token creation fails
        """
        try:
            # Calculate expiration
            if expires_delta:
                expire = datetime.now(timezone.utc) + expires_delta
            else:
                expire = datetime.now(timezone.utc) + timedelta(
                    minutes=self.access_token_expire_minutes
                )

            # Build token payload
            payload = {
                "sub": subject,
                "type": "access",
                "exp": expire,
                "iat": datetime.now(timezone.utc),
            }

            # Add user data if provided
            if user_data:
                payload.update(user_data)

            # Encode token
            token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

            logger.debug(f"Access token created for subject: {subject}")
            return token

        except Exception as e:
            logger.error(f"Error creating access token: {str(e)}")
            raise Exception(f"Failed to create access token: {str(e)}")

    def create_refresh_token(
        self,
        subject: str,
        expires_delta: Optional[timedelta] = None,
    ) -> str:
        """
        Create a JWT refresh token

        Args:
            subject: Token subject (usually user_id)
            expires_delta: Custom expiration time (overrides default)

        Returns:
            str: Encoded JWT refresh token

        Raises:
            Exception: If token creation fails
        """
        try:
            # Calculate expiration
            if expires_delta:
                expire = datetime.now(timezone.utc) + expires_delta
            else:
                expire = datetime.now(timezone.utc) + timedelta(
                    days=self.refresh_token_expire_days
                )

            # Build token payload
            payload = {
                "sub": subject,
                "type": "refresh",
                "exp": expire,
                "iat": datetime.now(timezone.utc),
            }

            # Encode token
            token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

            logger.debug(f"Refresh token created for subject: {subject}")
            return token

        except Exception as e:
            logger.error(f"Error creating refresh token: {str(e)}")
            raise Exception(f"Failed to create refresh token: {str(e)}")

    def decode_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Decode and validate a JWT token

        Args:
            token: JWT token to decode

        Returns:
            Optional[Dict]: Decoded token payload if valid, None otherwise
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )

            logger.debug(f"Token decoded successfully: type={payload.get('type')}")
            return payload

        except jwt.ExpiredSignatureError:
            logger.debug("Token has expired")
            return None

        except jwt.InvalidTokenError as e:
            logger.debug(f"Invalid token: {str(e)}")
            return None

        except Exception as e:
            logger.error(f"Error decoding token: {str(e)}")
            return None

    def verify_access_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify an access token

        Args:
            token: JWT access token

        Returns:
            Optional[Dict]: Token payload if valid access token, None otherwise
        """
        payload = self.decode_token(token)

        if payload is None:
            return None

        # Verify token type
        if payload.get("type") != "access":
            logger.warning("Token is not an access token")
            return None

        return payload

    def verify_refresh_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify a refresh token

        Args:
            token: JWT refresh token

        Returns:
            Optional[Dict]: Token payload if valid refresh token, None otherwise
        """
        payload = self.decode_token(token)

        if payload is None:
            return None

        # Verify token type
        if payload.get("type") != "refresh":
            logger.warning("Token is not a refresh token")
            return None

        return payload

    def get_token_subject(self, token: str) -> Optional[str]:
        """
        Extract subject from token without full validation

        Args:
            token: JWT token

        Returns:
            Optional[str]: Token subject if present, None otherwise
        """
        try:
            # Decode without verification (just to extract subject)
            payload = jwt.decode(
                token,
                options={"verify_signature": False}
            )

            return payload.get("sub")

        except Exception as e:
            logger.debug(f"Error extracting token subject: {str(e)}")
            return None

    def get_token_expiration(self, token: str) -> Optional[datetime]:
        """
        Get token expiration time

        Args:
            token: JWT token

        Returns:
            Optional[datetime]: Expiration time if present, None otherwise
        """
        payload = self.decode_token(token)

        if payload and "exp" in payload:
            return datetime.fromtimestamp(payload["exp"])

        return None

    def is_token_expired(self, token: str) -> bool:
        """
        Check if token is expired

        Args:
            token: JWT token

        Returns:
            bool: True if expired or invalid, False if still valid
        """
        expiration = self.get_token_expiration(token)

        if expiration is None:
            return True

        return datetime.now(timezone.utc) >= expiration

    def get_remaining_time(self, token: str) -> Optional[timedelta]:
        """
        Get remaining time before token expires

        Args:
            token: JWT token

        Returns:
            Optional[timedelta]: Remaining time if valid, None if expired/invalid
        """
        expiration = self.get_token_expiration(token)

        if expiration is None:
            return None

        remaining = expiration - datetime.now(timezone.utc)

        if remaining.total_seconds() <= 0:
            return None

        return remaining

    def create_token_pair(
        self,
        subject: str,
        user_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create both access and refresh tokens

        Args:
            subject: Token subject (usually user_id)
            user_data: Additional user data for access token

        Returns:
            Dict: Token pair with access_token, refresh_token, expires_in
        """
        access_token = self.create_access_token(subject, user_data)
        refresh_token = self.create_refresh_token(subject)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": self.access_token_expire_minutes * 60,  # in seconds
        }


# Singleton instance
_jwt_service_instance: Optional[JWTService] = None


def get_jwt_service(
    secret_key: Optional[str] = None,
    algorithm: str = "HS256",
    access_token_expire_minutes: int = 60,
    refresh_token_expire_days: int = 7,
) -> JWTService:
    """
    Get JWT service singleton instance

    Args:
        secret_key: Secret key (only used on first call)
        algorithm: JWT algorithm (only used on first call)
        access_token_expire_minutes: Access token expiration (only used on first call)
        refresh_token_expire_days: Refresh token expiration (only used on first call)

    Returns:
        JWTService: JWT service instance
    """
    global _jwt_service_instance

    if _jwt_service_instance is None:
        _jwt_service_instance = JWTService(
            secret_key=secret_key,
            algorithm=algorithm,
            access_token_expire_minutes=access_token_expire_minutes,
            refresh_token_expire_days=refresh_token_expire_days,
        )

    return _jwt_service_instance
