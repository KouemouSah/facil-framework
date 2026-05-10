"""
Unit tests for AuthService 2FA login integration (TASK-M01-013)

Tests for 2FA login workflow:
- verify_2fa_login() method
- Login flow with 2FA enabled

Coverage:
- Temp token validation
- 2FA code verification (TOTP and backup)
- Session creation after 2FA verification
- Error handling (invalid temp token, invalid code, 2FA not enabled)
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import pyotp

from app.services.auth_service import AuthService
from app.modules.users.models.user import UserRole, UserStatus


@pytest.fixture
def auth_service():
    """Fixture: AuthService instance with mocked dependencies"""
    service = AuthService()
    service.user_repo = AsyncMock()
    service.jwt_service = MagicMock()
    service.password_service = MagicMock()
    return service


@pytest.fixture
def mock_user_2fa_enabled():
    """Fixture: Mock user with 2FA enabled"""
    user = MagicMock()
    user.id = "user_123"
    user.email = "test@example.com"
    user.role = UserRole.citizen
    user.status = UserStatus.active
    user.two_factor_enabled = True
    user.two_factor_secret = pyotp.random_base32()
    user.two_factor_backup_codes = []
    user.first_name = "Test"
    user.last_name = "User"
    user.phone = None
    user.address = None
    user.city = None
    user.language = "es"
    user.avatar_url = None
    user.created_at = datetime.utcnow()
    user.updated_at = datetime.utcnow()
    return user


@pytest.fixture
def mock_user_2fa_disabled():
    """Fixture: Mock user with 2FA disabled"""
    user = MagicMock()
    user.id = "user_456"
    user.email = "test2@example.com"
    user.role = UserRole.citizen
    user.status = UserStatus.active
    user.two_factor_enabled = False
    user.two_factor_secret = None
    user.two_factor_backup_codes = None
    user.first_name = "Test"
    user.last_name = "User2"
    user.phone = None
    user.address = None
    user.city = None
    user.language = "es"
    user.avatar_url = None
    user.created_at = datetime.utcnow()
    user.updated_at = datetime.utcnow()
    return user


class TestVerify2FALogin:
    """Unit tests for verify_2fa_login() method"""

    @pytest.mark.asyncio
    async def test_verify_2fa_login_valid_totp_code(self, auth_service, mock_user_2fa_enabled):
        """Test: verify_2fa_login() succeeds with valid TOTP code"""
        # Setup: Generate valid TOTP code
        totp = pyotp.TOTP(mock_user_2fa_enabled.two_factor_secret)
        valid_code = totp.now()

        # Setup: Mock temp token validation
        temp_token_data = {
            "sub": mock_user_2fa_enabled.id,
            "email": mock_user_2fa_enabled.email,
            "role": mock_user_2fa_enabled.role.value,
            "type": "2fa_temp",
            "remember_me": False,
            "ip_address": "192.168.1.1",
            "user_agent": "Mozilla/5.0",
        }
        auth_service.jwt_service.verify_access_token.return_value = temp_token_data

        # Setup: Mock user retrieval
        auth_service.user_repo.get_by_id.return_value = mock_user_2fa_enabled

        # Setup: Mock 2FA verification
        with patch("app.services.two_factor_service.get_two_factor_service") as mock_2fa_service:
            mock_2fa_service.return_value.verify_login_code = AsyncMock(return_value=True)

            # Setup: Mock session creation
            auth_service._create_session = AsyncMock(
                return_value={
                    "access_token": "access_token_123",
                    "refresh_token": "refresh_token_123",
                    "token_type": "bearer",
                    "expires_in": 3600,
                }
            )

            # Setup: Mock update last login
            auth_service.user_repo.update_last_login = AsyncMock()

            # Execute
            result = await auth_service.verify_2fa_login(
                temp_token="temp_token_123", code=valid_code
            )

            # Verify: Returns tokens and user data
            assert "access_token" in result
            assert "refresh_token" in result
            assert "user" in result
            assert result["access_token"] == "access_token_123"

            # Verify: User data is correct
            assert result["user"]["id"] == mock_user_2fa_enabled.id
            assert result["user"]["email"] == mock_user_2fa_enabled.email

            # Verify: Session was created
            auth_service._create_session.assert_called_once()

            # Verify: Last login was updated
            auth_service.user_repo.update_last_login.assert_called_once_with(
                mock_user_2fa_enabled.id
            )

    @pytest.mark.asyncio
    async def test_verify_2fa_login_invalid_temp_token(self, auth_service):
        """Test: verify_2fa_login() fails with invalid temp token"""
        # Setup: Invalid temp token
        auth_service.jwt_service.verify_access_token.return_value = None

        # Execute & Verify: Raises exception
        with pytest.raises(Exception, match="Invalid or expired temporary token"):
            await auth_service.verify_2fa_login(
                temp_token="invalid_token", code="123456"
            )

    @pytest.mark.asyncio
    async def test_verify_2fa_login_wrong_token_type(self, auth_service):
        """Test: verify_2fa_login() fails with wrong token type"""
        # Setup: Token with wrong type (not "2fa_temp")
        token_data = {
            "sub": "user_123",
            "email": "test@example.com",
            "role": "citizen",
            "type": "access",  # Wrong type!
        }
        auth_service.jwt_service.verify_access_token.return_value = token_data

        # Execute & Verify: Raises exception
        with pytest.raises(Exception, match="Invalid or expired temporary token"):
            await auth_service.verify_2fa_login(
                temp_token="temp_token_123", code="123456"
            )

    @pytest.mark.asyncio
    async def test_verify_2fa_login_2fa_not_enabled(
        self, auth_service, mock_user_2fa_disabled
    ):
        """Test: verify_2fa_login() fails if 2FA not enabled for user"""
        # Setup: Valid temp token
        temp_token_data = {
            "sub": mock_user_2fa_disabled.id,
            "email": mock_user_2fa_disabled.email,
            "role": mock_user_2fa_disabled.role.value,
            "type": "2fa_temp",
        }
        auth_service.jwt_service.verify_access_token.return_value = temp_token_data

        # Setup: User has 2FA disabled
        auth_service.user_repo.get_by_id.return_value = mock_user_2fa_disabled

        # Execute & Verify: Raises exception
        with pytest.raises(Exception, match="2FA is not enabled for this account"):
            await auth_service.verify_2fa_login(
                temp_token="temp_token_123", code="123456"
            )

    @pytest.mark.asyncio
    async def test_verify_2fa_login_invalid_2fa_code(
        self, auth_service, mock_user_2fa_enabled
    ):
        """Test: verify_2fa_login() fails with invalid 2FA code"""
        # Setup: Valid temp token
        temp_token_data = {
            "sub": mock_user_2fa_enabled.id,
            "email": mock_user_2fa_enabled.email,
            "role": mock_user_2fa_enabled.role.value,
            "type": "2fa_temp",
        }
        auth_service.jwt_service.verify_access_token.return_value = temp_token_data

        # Setup: User with 2FA enabled
        auth_service.user_repo.get_by_id.return_value = mock_user_2fa_enabled

        # Setup: Invalid 2FA code
        with patch("app.services.two_factor_service.get_two_factor_service") as mock_2fa_service:
            mock_2fa_service.return_value.verify_login_code = AsyncMock(
                return_value=False
            )

            # Execute & Verify: Raises exception
            with pytest.raises(Exception, match="Invalid or expired 2FA code"):
                await auth_service.verify_2fa_login(
                    temp_token="temp_token_123", code="000000"
                )

    @pytest.mark.asyncio
    async def test_verify_2fa_login_with_backup_code(
        self, auth_service, mock_user_2fa_enabled
    ):
        """Test: verify_2fa_login() succeeds with valid backup code"""
        # Setup: Valid temp token
        temp_token_data = {
            "sub": mock_user_2fa_enabled.id,
            "email": mock_user_2fa_enabled.email,
            "role": mock_user_2fa_enabled.role.value,
            "type": "2fa_temp",
            "remember_me": False,
        }
        auth_service.jwt_service.verify_access_token.return_value = temp_token_data

        # Setup: User with 2FA enabled
        auth_service.user_repo.get_by_id.return_value = mock_user_2fa_enabled

        # Setup: Valid backup code
        backup_code = "1234-5678"
        with patch("app.services.two_factor_service.get_two_factor_service") as mock_2fa_service:
            mock_2fa_service.return_value.verify_login_code = AsyncMock(
                return_value=True
            )

            # Setup: Mock session creation
            auth_service._create_session = AsyncMock(
                return_value={
                    "access_token": "access_token_123",
                    "refresh_token": "refresh_token_123",
                    "token_type": "bearer",
                    "expires_in": 3600,
                }
            )

            # Setup: Mock update last login
            auth_service.user_repo.update_last_login = AsyncMock()

            # Execute
            result = await auth_service.verify_2fa_login(
                temp_token="temp_token_123", code=backup_code
            )

            # Verify: Returns tokens
            assert "access_token" in result
            assert result["access_token"] == "access_token_123"

            # Verify: 2FA service was called with backup code
            mock_2fa_service.return_value.verify_login_code.assert_called_once_with(
                mock_user_2fa_enabled.id, backup_code
            )

    @pytest.mark.asyncio
    async def test_verify_2fa_login_remember_me_preserved(
        self, auth_service, mock_user_2fa_enabled
    ):
        """Test: verify_2fa_login() preserves remember_me flag from temp token"""
        # Setup: Valid temp token with remember_me=True
        temp_token_data = {
            "sub": mock_user_2fa_enabled.id,
            "email": mock_user_2fa_enabled.email,
            "role": mock_user_2fa_enabled.role.value,
            "type": "2fa_temp",
            "remember_me": True,  # Should be preserved
            "ip_address": "192.168.1.1",
            "user_agent": "Mozilla/5.0",
        }
        auth_service.jwt_service.verify_access_token.return_value = temp_token_data

        # Setup: User with 2FA enabled
        auth_service.user_repo.get_by_id.return_value = mock_user_2fa_enabled

        # Setup: Valid TOTP code
        totp = pyotp.TOTP(mock_user_2fa_enabled.two_factor_secret)
        valid_code = totp.now()

        with patch("app.services.two_factor_service.get_two_factor_service") as mock_2fa_service:
            mock_2fa_service.return_value.verify_login_code = AsyncMock(
                return_value=True
            )

            # Setup: Mock session creation
            auth_service._create_session = AsyncMock(
                return_value={
                    "access_token": "access_token_123",
                    "refresh_token": "refresh_token_123",
                    "token_type": "bearer",
                    "expires_in": 3600,
                }
            )

            # Setup: Mock update last login
            auth_service.user_repo.update_last_login = AsyncMock()

            # Execute
            await auth_service.verify_2fa_login(
                temp_token="temp_token_123", code=valid_code
            )

            # Verify: _create_session was called with remember_me=True
            call_args = auth_service._create_session.call_args
            assert call_args.kwargs["remember_me"] is True


class TestLoginWith2FA:
    """Unit tests for login() method with 2FA enabled users"""

    @pytest.mark.asyncio
    async def test_login_returns_temp_token_when_2fa_enabled(
        self, auth_service, mock_user_2fa_enabled
    ):
        """Test: login() returns temp_token when user has 2FA enabled"""
        # Setup: Mock user lookup with password
        user_data = {
            "id": mock_user_2fa_enabled.id,
            "email": mock_user_2fa_enabled.email,
            "password_hash": "$2b$12$hash",
            "role": mock_user_2fa_enabled.role.value,
            "status": mock_user_2fa_enabled.status.value,
        }
        auth_service.user_repo.find_by_email_with_password = AsyncMock(
            return_value=user_data
        )

        # Setup: Mock password verification
        auth_service.password_service.verify_password.return_value = True

        # Setup: Mock user retrieval (with 2FA enabled)
        auth_service.user_repo._map_to_model = MagicMock(
            return_value=mock_user_2fa_enabled
        )

        # Setup: Mock JWT token generation
        auth_service.jwt_service.create_access_token.return_value = (
            "temp_token_123_short_lived"
        )

        # Execute
        result = await auth_service.login(
            email="test@example.com",
            password="password123",
            remember_me=False,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
        )

        # Verify: Returns 2FA required response
        assert result["requires_2fa"] is True
        assert "temp_token" in result
        assert result["temp_token"] == "temp_token_123_short_lived"
        assert "message" in result

        # Verify: Temp token was created with correct params
        call_args = auth_service.jwt_service.create_access_token.call_args
        assert call_args.kwargs["subject"] == mock_user_2fa_enabled.id
        assert call_args.kwargs["user_data"]["type"] == "2fa_temp"
        assert call_args.kwargs["user_data"]["remember_me"] is False

        # Verify: Session was NOT created yet
        # (session creation happens after 2FA verification)

    @pytest.mark.asyncio
    async def test_login_returns_tokens_when_2fa_disabled(
        self, auth_service, mock_user_2fa_disabled
    ):
        """Test: login() returns access/refresh tokens when 2FA disabled"""
        # Setup: Mock user lookup with password
        user_data = {
            "id": mock_user_2fa_disabled.id,
            "email": mock_user_2fa_disabled.email,
            "password_hash": "$2b$12$hash",
            "role": mock_user_2fa_disabled.role.value,
            "status": mock_user_2fa_disabled.status.value,
        }
        auth_service.user_repo.find_by_email_with_password = AsyncMock(
            return_value=user_data
        )

        # Setup: Mock password verification
        auth_service.password_service.verify_password.return_value = True

        # Setup: Mock user retrieval (2FA disabled)
        auth_service.user_repo._map_to_model = MagicMock(
            return_value=mock_user_2fa_disabled
        )

        # Setup: Mock update last login
        auth_service.user_repo.update_last_login = AsyncMock()

        # Setup: Mock session creation
        auth_service._create_session = AsyncMock(
            return_value={
                "access_token": "access_token_123",
                "refresh_token": "refresh_token_123",
                "token_type": "bearer",
                "expires_in": 3600,
            }
        )

        # Execute
        result = await auth_service.login(
            email="test2@example.com",
            password="password123",
            remember_me=False,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
        )

        # Verify: Returns standard tokens (no 2FA required)
        assert "requires_2fa" not in result
        assert "access_token" in result
        assert "refresh_token" in result
        assert "user" in result

        # Verify: Session was created
        auth_service._create_session.assert_called_once()

        # Verify: Last login was updated
        auth_service.user_repo.update_last_login.assert_called_once()
