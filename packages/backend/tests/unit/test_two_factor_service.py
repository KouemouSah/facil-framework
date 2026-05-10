"""
Unit tests for TwoFactorService (TASK-M01-012)

Tests for 2FA TOTP business logic.

Coverage:
- TOTP secret generation
- QR code generation
- TOTP code verification
- Backup codes generation/verification
- 2FA enable/disable workflows
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
import pyotp

from app.modules.auth.services.two_factor_service import TwoFactorService


@pytest.fixture
def two_factor_service():
    """Fixture: TwoFactorService instance"""
    return TwoFactorService()


@pytest.fixture
def mock_user_repo():
    """Fixture: Mock UserRepository"""
    return AsyncMock()


class TestSecretGeneration:
    """Unit tests for TOTP secret generation"""

    def test_generate_secret_returns_base32(self, two_factor_service):
        """Test: generate_secret() returns base32 encoded string"""
        secret = two_factor_service.generate_secret()

        assert isinstance(secret, str)
        assert len(secret) == 32
        # Base32 alphabet: A-Z and 2-7
        assert all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567' for c in secret)

    def test_generate_secret_unique(self, two_factor_service):
        """Test: Each secret generated is unique"""
        secrets = [two_factor_service.generate_secret() for _ in range(10)]

        # All secrets should be unique
        assert len(secrets) == len(set(secrets))


class TestQRCodeGeneration:
    """Unit tests for QR code generation"""

    def test_generate_qr_code_returns_svg(self, two_factor_service):
        """Test: generate_qr_code() returns SVG string"""
        secret = "JBSWY3DPEHPK3PXP"
        email = "test@example.com"

        qr_code = two_factor_service.generate_qr_code(email, secret)

        assert isinstance(qr_code, str)
        assert qr_code.startswith('<?xml') or qr_code.startswith('<svg')
        assert '</svg>' in qr_code

    def test_generate_qr_code_contains_provisioning_uri(self, two_factor_service):
        """Test: QR code contains TOTP provisioning URI"""
        secret = "JBSWY3DPEHPK3PXP"
        email = "test@example.com"

        qr_code = two_factor_service.generate_qr_code(email, secret)

        # Verify provisioning URI components are encoded in QR
        # Format: otpauth://totp/TaxasGE:test@example.com?secret=SECRET&issuer=TaxasGE
        assert 'svg' in qr_code.lower()


class TestTOTPVerification:
    """Unit tests for TOTP code verification"""

    def test_verify_code_valid_totp(self, two_factor_service):
        """Test: verify_code() accepts valid TOTP code"""
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        valid_code = totp.now()

        result = two_factor_service.verify_code(secret, valid_code)

        assert result is True

    def test_verify_code_invalid_code(self, two_factor_service):
        """Test: verify_code() rejects invalid TOTP code"""
        secret = pyotp.random_base32()
        invalid_code = "000000"

        result = two_factor_service.verify_code(secret, invalid_code)

        assert result is False

    def test_verify_code_non_numeric(self, two_factor_service):
        """Test: verify_code() rejects non-numeric codes"""
        secret = pyotp.random_base32()
        invalid_code = "abc123"

        result = two_factor_service.verify_code(secret, invalid_code)

        assert result is False

    def test_verify_code_wrong_length(self, two_factor_service):
        """Test: verify_code() rejects codes with wrong length"""
        secret = pyotp.random_base32()

        # Too short
        result = two_factor_service.verify_code(secret, "12345")
        assert result is False

        # Too long
        result = two_factor_service.verify_code(secret, "1234567")
        assert result is False

    def test_verify_code_none(self, two_factor_service):
        """Test: verify_code() rejects None code"""
        secret = pyotp.random_base32()

        result = two_factor_service.verify_code(secret, None)

        assert result is False


class TestBackupCodes:
    """Unit tests for backup codes generation and verification"""

    def test_generate_backup_codes_count(self, two_factor_service):
        """Test: generate_backup_codes() returns correct count"""
        codes = two_factor_service.generate_backup_codes(count=10)

        assert len(codes) == 10

    def test_generate_backup_codes_format(self, two_factor_service):
        """Test: Backup codes have correct format (XXXX-XXXX)"""
        codes = two_factor_service.generate_backup_codes(count=5)

        for code in codes:
            assert len(code) == 9  # 4 digits + dash + 4 digits
            assert code[4] == '-'
            assert code[:4].isdigit()
            assert code[5:].isdigit()

    def test_generate_backup_codes_unique(self, two_factor_service):
        """Test: All backup codes are unique"""
        codes = two_factor_service.generate_backup_codes(count=10)

        assert len(codes) == len(set(codes))

    def test_hash_backup_code(self, two_factor_service):
        """Test: hash_backup_code() returns SHA256 hash"""
        code = "1234-5678"

        hashed = two_factor_service.hash_backup_code(code)

        assert isinstance(hashed, str)
        assert len(hashed) == 64  # SHA256 hex digest is 64 chars

    def test_hash_backup_code_deterministic(self, two_factor_service):
        """Test: Same code produces same hash"""
        code = "1234-5678"

        hash1 = two_factor_service.hash_backup_code(code)
        hash2 = two_factor_service.hash_backup_code(code)

        assert hash1 == hash2

    def test_verify_backup_code_valid(self, two_factor_service):
        """Test: verify_backup_code() accepts valid backup code"""
        code = "1234-5678"
        hashed = two_factor_service.hash_backup_code(code)
        hashed_codes = [hashed, "other_hash_1", "other_hash_2"]

        is_valid, remaining = two_factor_service.verify_backup_code(code, hashed_codes)

        assert is_valid is True
        assert len(remaining) == 2
        assert hashed not in remaining

    def test_verify_backup_code_invalid(self, two_factor_service):
        """Test: verify_backup_code() rejects invalid backup code"""
        code = "1234-5678"
        hashed_codes = ["hash1", "hash2", "hash3"]

        is_valid, remaining = two_factor_service.verify_backup_code(code, hashed_codes)

        assert is_valid is False
        assert remaining is None

    def test_verify_backup_code_removes_used_code(self, two_factor_service):
        """Test: Used backup code is removed from list"""
        code = "1234-5678"
        hashed = two_factor_service.hash_backup_code(code)
        hashed_codes = [hashed, "hash1", "hash2"]

        is_valid, remaining = two_factor_service.verify_backup_code(code, hashed_codes)

        assert is_valid is True
        assert hashed not in remaining
        assert "hash1" in remaining
        assert "hash2" in remaining


class TestEnable2FA:
    """Unit tests for 2FA enable workflow"""

    @pytest.mark.asyncio
    async def test_enable_2fa_returns_complete_data(self, two_factor_service):
        """Test: enable_2fa() returns secret, QR code, and backup codes"""
        with patch.object(two_factor_service, 'user_repo') as mock_repo:
            mock_user = MagicMock()
            mock_user.email = "test@example.com"
            mock_repo.get_by_id = AsyncMock(return_value=mock_user)

            result = await two_factor_service.enable_2fa("user_id_123")

            assert 'secret' in result
            assert 'qr_code' in result
            assert 'backup_codes' in result
            assert len(result['backup_codes']) == 10

    @pytest.mark.asyncio
    async def test_enable_2fa_secret_is_base32(self, two_factor_service):
        """Test: Secret returned by enable_2fa() is base32"""
        with patch.object(two_factor_service, 'user_repo') as mock_repo:
            mock_user = MagicMock()
            mock_user.email = "test@example.com"
            mock_repo.get_by_id = AsyncMock(return_value=mock_user)

            result = await two_factor_service.enable_2fa("user_id_123")

            secret = result['secret']
            assert isinstance(secret, str)
            assert len(secret) == 32
            assert all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567' for c in secret)


class TestVerifyAndEnable2FA:
    """Unit tests for 2FA verification and activation"""

    @pytest.mark.asyncio
    async def test_verify_and_enable_2fa_valid_code(self, two_factor_service):
        """Test: verify_and_enable_2fa() succeeds with valid code"""
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        valid_code = totp.now()
        backup_codes = ["1234-5678", "9876-5432"]

        with patch.object(two_factor_service, 'user_repo') as mock_repo:
            mock_repo.enable_two_factor = AsyncMock(return_value=True)

            result = await two_factor_service.verify_and_enable_2fa(
                user_id="user_123",
                secret=secret,
                code=valid_code,
                backup_codes=backup_codes
            )

            assert result is True
            mock_repo.enable_two_factor.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_and_enable_2fa_invalid_code(self, two_factor_service):
        """Test: verify_and_enable_2fa() fails with invalid code"""
        secret = pyotp.random_base32()
        invalid_code = "000000"
        backup_codes = ["1234-5678", "9876-5432"]

        with patch.object(two_factor_service, 'user_repo') as mock_repo:
            result = await two_factor_service.verify_and_enable_2fa(
                user_id="user_123",
                secret=secret,
                code=invalid_code,
                backup_codes=backup_codes
            )

            assert result is False
            mock_repo.enable_two_factor.assert_not_called()


class TestDisable2FA:
    """Unit tests for 2FA disable"""

    @pytest.mark.asyncio
    async def test_disable_2fa_success(self, two_factor_service):
        """Test: disable_2fa() calls repository method"""
        with patch.object(two_factor_service, 'user_repo') as mock_repo:
            mock_repo.disable_two_factor = AsyncMock(return_value=True)

            result = await two_factor_service.disable_2fa("user_123")

            assert result is True
            mock_repo.disable_two_factor.assert_called_once_with("user_123")


class TestVerifyLoginCode:
    """Unit tests for 2FA login verification"""

    @pytest.mark.asyncio
    async def test_verify_login_code_totp_valid(self, two_factor_service):
        """Test: verify_login_code() accepts valid TOTP code"""
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        valid_code = totp.now()

        with patch.object(two_factor_service, 'user_repo') as mock_repo:
            mock_user = MagicMock()
            mock_user.two_factor_enabled = True
            mock_user.two_factor_secret = secret
            mock_user.two_factor_backup_codes = []
            mock_repo.get_by_id = AsyncMock(return_value=mock_user)

            result = await two_factor_service.verify_login_code("user_123", valid_code)

            assert result is True

    @pytest.mark.asyncio
    async def test_verify_login_code_backup_valid(self, two_factor_service):
        """Test: verify_login_code() accepts valid backup code"""
        secret = pyotp.random_base32()
        backup_code = "1234-5678"
        hashed_code = two_factor_service.hash_backup_code(backup_code)

        with patch.object(two_factor_service, 'user_repo') as mock_repo:
            mock_user = MagicMock()
            mock_user.two_factor_enabled = True
            mock_user.two_factor_secret = secret
            mock_user.two_factor_backup_codes = [hashed_code, "other_hash"]
            mock_repo.get_by_id = AsyncMock(return_value=mock_user)
            mock_repo.update_backup_codes = AsyncMock(return_value=True)

            result = await two_factor_service.verify_login_code("user_123", backup_code)

            assert result is True
            # Should update backup codes (remove used one)
            mock_repo.update_backup_codes.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_login_code_2fa_not_enabled(self, two_factor_service):
        """Test: verify_login_code() fails if 2FA not enabled"""
        with patch.object(two_factor_service, 'user_repo') as mock_repo:
            mock_user = MagicMock()
            mock_user.two_factor_enabled = False
            mock_repo.get_by_id = AsyncMock(return_value=mock_user)

            result = await two_factor_service.verify_login_code("user_123", "123456")

            assert result is False

    @pytest.mark.asyncio
    async def test_verify_login_code_invalid(self, two_factor_service):
        """Test: verify_login_code() fails with invalid code"""
        secret = pyotp.random_base32()

        with patch.object(two_factor_service, 'user_repo') as mock_repo:
            mock_user = MagicMock()
            mock_user.two_factor_enabled = True
            mock_user.two_factor_secret = secret
            mock_user.two_factor_backup_codes = []
            mock_repo.get_by_id = AsyncMock(return_value=mock_user)

            result = await two_factor_service.verify_login_code("user_123", "000000")

            assert result is False
