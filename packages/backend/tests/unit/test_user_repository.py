"""
Unit tests for UserRepository (TASK-M01-005 STEP 3)
Tests for password hash retrieval methods

COVERAGE:
- get_password_hash() method (STEP 1 fixes)
"""

import pytest
from uuid import uuid4
from app.repositories.user_repository import UserRepository
from app.services.password_service import PasswordService


class TestUserRepositoryPasswordMethods:
    """Unit tests for UserRepository password methods (STEP 1)"""

    @pytest.mark.asyncio
    async def test_get_password_hash_nonexistent_user(self):
        """Test: Get password hash for nonexistent user raises ValueError"""
        repo = UserRepository()
        nonexistent_id = str(uuid4())

        with pytest.raises(ValueError) as exc_info:
            await repo.get_password_hash(nonexistent_id)

        error_msg = str(exc_info.value).lower()
        assert "not found" in error_msg or "user" in error_msg

    @pytest.mark.asyncio
    async def test_get_password_hash_invalid_uuid(self):
        """Test: Get password hash with invalid UUID raises error"""
        repo = UserRepository()

        with pytest.raises((ValueError, Exception)):
            await repo.get_password_hash("invalid-uuid")

    @pytest.mark.asyncio
    async def test_get_password_hash_empty_string(self):
        """Test: Get password hash with empty string raises error"""
        repo = UserRepository()

        with pytest.raises((ValueError, Exception)):
            await repo.get_password_hash("")

    # NOTE: Test for existing user requires database setup and is covered in integration tests
    # Integration test will verify:
    # - Password hash retrieval for existing user
    # - Hash format validation (bcrypt $2b$ prefix)
    # - Hash length validation
