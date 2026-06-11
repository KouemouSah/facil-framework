"""
Unit tests for User Models (TASK-M01-005 STEP 3)
Tests for password security and validation fixes

COVERAGE:
- PasswordChange model validation (STEP 1 fixes)
- UserUpdate model email/phone validation (STEP 2 fixes)
"""

import pytest
from pydantic import ValidationError
from app.modules.users.models.user import PasswordChange, UserUpdate


class TestPasswordChangeModel:
    """Unit tests for PasswordChange model (STEP 1 fixes)"""

    def test_password_change_valid(self):
        """Test: Valid password change data accepted"""
        pc = PasswordChange(
            old_password="OldPass123",
            new_password="NewPass456"
        )
        assert pc.old_password == "OldPass123"
        assert pc.new_password == "NewPass456"

    def test_password_change_same_passwords(self):
        """Test: New password cannot be same as old password"""
        with pytest.raises(ValidationError) as exc_info:
            PasswordChange(
                old_password="SamePass123",
                new_password="SamePass123"
            )
        error_msg = str(exc_info.value).lower()
        assert "different" in error_msg or "must be different" in error_msg

    def test_password_change_short_old_password(self):
        """Test: Old password must be at least 8 chars"""
        with pytest.raises(ValidationError) as exc_info:
            PasswordChange(
                old_password="Short1",
                new_password="ValidPass123"
            )
        # Verify it's a validation error about password length
        error_msg = str(exc_info.value)
        assert "old_password" in error_msg.lower() or "at least 8" in error_msg.lower()

    def test_password_change_short_new_password(self):
        """Test: New password must be at least 8 chars"""
        with pytest.raises(ValidationError) as exc_info:
            PasswordChange(
                old_password="ValidPass123",
                new_password="Short1"
            )
        # Verify it's a validation error about password length
        error_msg = str(exc_info.value)
        assert "new_password" in error_msg.lower() or "at least 8" in error_msg.lower()

    def test_password_change_too_long_password(self):
        """Test: Password cannot exceed 100 chars"""
        with pytest.raises(ValidationError) as exc_info:
            PasswordChange(
                old_password="ValidPass123",
                new_password="x" * 101
            )
        # Verify it's a validation error about password length
        error_msg = str(exc_info.value)
        assert "new_password" in error_msg.lower() or "100" in error_msg

    def test_password_change_empty_old_password(self):
        """Test: Old password cannot be empty"""
        with pytest.raises(ValidationError):
            PasswordChange(
                old_password="",
                new_password="ValidPass123"
            )

    def test_password_change_empty_new_password(self):
        """Test: New password cannot be empty"""
        with pytest.raises(ValidationError):
            PasswordChange(
                old_password="ValidPass123",
                new_password=""
            )


class TestUserUpdateModel:
    """Unit tests for UserUpdate model (STEP 2 fixes)"""

    def test_user_update_valid_email(self):
        """Test: Valid email format accepted"""
        user = UserUpdate(email="test@example.com")
        assert user.email == "test@example.com"

    def test_user_update_invalid_email_format(self):
        """Test: Invalid email format rejected"""
        with pytest.raises(ValidationError) as exc_info:
            UserUpdate(email="invalid-email")
        assert "email" in str(exc_info.value).lower()

    def test_user_update_invalid_email_no_domain(self):
        """Test: Email without domain rejected"""
        with pytest.raises(ValidationError) as exc_info:
            UserUpdate(email="user@")
        assert "email" in str(exc_info.value).lower()

    def test_user_update_valid_phone_e164(self):
        """Test: Valid E.164 phone accepted and formatted"""
        user = UserUpdate(phone="+240222123456")
        assert user.phone == "+240222123456"

    def test_user_update_valid_phone_e164_alternative_country(self):
        """Test: Valid E.164 phone with different country code"""
        user = UserUpdate(phone="+34912345678")
        assert user.phone == "+34912345678"

    def test_user_update_invalid_phone_missing_plus(self):
        """Test: Phone without + prefix rejected"""
        with pytest.raises(ValidationError) as exc_info:
            UserUpdate(phone="240222123456")
        error_msg = str(exc_info.value)
        assert "E.164" in error_msg or "phone" in error_msg.lower()

    def test_user_update_phone_with_dashes_autoformat(self):
        """Test: Phone with dashes is auto-formatted to E.164"""
        # phonenumbers library auto-strips dashes - this is CORRECT behavior
        user_update = UserUpdate(phone="+240-222-123-456")
        # Should be formatted to E.164 (no dashes)
        assert user_update.phone == "+240222123456"

    def test_user_update_invalid_phone_too_short(self):
        """Test: Phone number too short rejected"""
        with pytest.raises(ValidationError) as exc_info:
            UserUpdate(phone="+240")
        error_msg = str(exc_info.value)
        assert "phone" in error_msg.lower() or "E.164" in error_msg

    def test_user_update_phone_none_allowed(self):
        """Test: Phone can be None (optional field)"""
        user = UserUpdate(phone=None)
        assert user.phone is None

    def test_user_update_email_none_allowed(self):
        """Test: Email can be None (optional field in update)"""
        user = UserUpdate(email=None)
        assert user.email is None

    def test_user_update_multiple_fields(self):
        """Test: Multiple valid fields can be updated together"""
        user = UserUpdate(
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com",
            phone="+240222123456",
            city="Malabo"
        )
        assert user.first_name == "John"
        assert user.last_name == "Doe"
        assert user.email == "john.doe@example.com"
        assert user.phone == "+240222123456"
        assert user.city == "Malabo"

    def test_user_update_language_validation(self):
        """Test: Language must be valid (es/fr/en)"""
        # Valid languages
        user_es = UserUpdate(language="es")
        assert user_es.language == "es"

        user_fr = UserUpdate(language="fr")
        assert user_fr.language == "fr"

        user_en = UserUpdate(language="en")
        assert user_en.language == "en"

        # Invalid language
        with pytest.raises(ValidationError):
            UserUpdate(language="de")
