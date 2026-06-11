"""
Integration tests for Users Endpoints (TASK-M01-005 STEP 3)
Tests for password change and profile update endpoints

COVERAGE:
- POST /users/password endpoint (STEP 1 fixes)
- PUT /users/profile endpoint (STEP 2 fixes)
"""

import pytest
from fastapi import status
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime

from app.modules.users.models.user import UserResponse, UserRole, UserStatus
from app.services.password_service import PasswordService


@pytest.fixture
def mock_user():
    """Fixture: Mock authenticated user"""
    return UserResponse(
        id=str(uuid4()),
        email="test@example.com",
        role=UserRole.citizen,
        status=UserStatus.active,
        first_name="Test",
        last_name="User",
        phone="+240222123456",
        address="Test Address",
        city="Malabo",
        language="es",
        avatar_url=None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        last_login=None,
        citizen_profile=None,
        business_profile=None
    )


@pytest.fixture
def mock_auth_headers():
    """Fixture: Mock authorization headers"""
    return {"Authorization": "Bearer mock_token_12345"}


class TestChangePasswordEndpoint:
    """Integration tests for POST /users/password (STEP 1 fixes)"""

    @pytest.mark.asyncio
    async def test_change_password_wrong_old_password(self, mock_user, mock_auth_headers):
        """Test: Wrong old password returns 400"""
        from app.main import app

        # Mock dependencies
        with patch('app.api.v1.users.get_current_user', return_value=mock_user):
            password_service = PasswordService()
            correct_hash = password_service.hash_password("CorrectOld123")

            with patch('app.repositories.user_repository.UserRepository.get_password_hash',
                      new_callable=AsyncMock, return_value=correct_hash):
                with patch('app.repositories.user_repository.UserRepository.log_user_activity',
                          new_callable=AsyncMock, return_value=True):

                    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                        response = await client.post(
                            "/api/v1/users/password",
                            json={
                                "old_password": "WrongOld123",
                                "new_password": "ValidNew456"
                            },
                            headers=mock_auth_headers
                        )

                        assert response.status_code == status.HTTP_400_BAD_REQUEST
                        assert "incorrect" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_change_password_weak_new_password(self, mock_user, mock_auth_headers):
        """Test: Weak new password returns 400"""
        from app.main import app

        # Mock dependencies
        with patch('app.api.v1.users.get_current_user', return_value=mock_user):
            password_service = PasswordService()
            correct_hash = password_service.hash_password("ValidOld123")

            with patch('app.repositories.user_repository.UserRepository.get_password_hash',
                      new_callable=AsyncMock, return_value=correct_hash):
                with patch('app.repositories.user_repository.UserRepository.log_user_activity',
                          new_callable=AsyncMock, return_value=True):

                    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                        response = await client.post(
                            "/api/v1/users/password",
                            json={
                                "old_password": "ValidOld123",
                                "new_password": "weak"
                            },
                            headers=mock_auth_headers
                        )

                        # Should fail validation (422) or business logic (400)
                        assert response.status_code in [
                            status.HTTP_400_BAD_REQUEST,
                            status.HTTP_422_UNPROCESSABLE_ENTITY
                        ]

    @pytest.mark.asyncio
    async def test_change_password_same_passwords(self, mock_user, mock_auth_headers):
        """Test: Same old and new password returns 422"""
        from app.main import app

        # Mock dependencies
        with patch('app.api.v1.users.get_current_user', return_value=mock_user):
            with patch('app.repositories.user_repository.UserRepository.log_user_activity',
                      new_callable=AsyncMock, return_value=True):

                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    response = await client.post(
                        "/api/v1/users/password",
                        json={
                            "old_password": "SamePass123",
                            "new_password": "SamePass123"
                        },
                        headers=mock_auth_headers
                    )

                    # Should fail Pydantic validation
                    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_change_password_success(self, mock_user, mock_auth_headers):
        """Test: Valid password change succeeds (REAL DB TEST - requires auth)"""
        from app.main import app

        # This test requires a real authenticated user in the database
        # Skip if no valid auth token provided
        pytest.skip("Real DB test - requires valid auth token from test user. TODO: Setup test user in Supabase with known credentials")

    @pytest.mark.asyncio
    async def test_change_password_unauthenticated(self):
        """Test: Unauthenticated request returns 401"""
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/users/password",
                json={
                    "old_password": "ValidOld123",
                    "new_password": "ValidNew456"
                }
                # No auth headers
            )

            # Should fail authentication
            assert response.status_code in [
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN
            ]


class TestUpdateProfileEndpoint:
    """Integration tests for PUT /users/profile (STEP 2 fixes)"""

    @pytest.mark.asyncio
    async def test_update_profile_valid_email(self, mock_user, mock_auth_headers):
        """Test: Valid email update succeeds"""
        from app.main import app

        updated_user = mock_user.copy(update={"email": "newemail@example.com"})

        # Mock dependencies
        with patch('app.api.v1.users.get_current_user', return_value=mock_user):
            with patch('app.repositories.user_repository.UserRepository.find_by_email',
                      new_callable=AsyncMock, return_value=None):  # Email not in use
                with patch('app.repositories.user_repository.UserRepository.update',
                          new_callable=AsyncMock, return_value=updated_user):
                    with patch('app.repositories.user_repository.UserRepository.log_user_activity',
                              new_callable=AsyncMock, return_value=True):

                        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                            response = await client.put(
                                "/api/v1/users/profile",
                                json={"email": "newemail@example.com"},
                                headers=mock_auth_headers
                            )

                            assert response.status_code == status.HTTP_200_OK
                            assert response.json()["email"] == "newemail@example.com"

    @pytest.mark.asyncio
    async def test_update_profile_duplicate_email(self, mock_user, mock_auth_headers):
        """Test: Duplicate email returns 409 Conflict"""
        from app.main import app

        # Real DB test - requires valid auth token
        pytest.skip("Real DB test - requires valid auth token and existing email in database. TODO: Setup test data in Supabase")

    @pytest.mark.asyncio
    async def test_update_profile_invalid_email_format(self, mock_user, mock_auth_headers):
        """Test: Invalid email format returns 422"""
        from app.main import app

        # Mock dependencies
        with patch('app.api.v1.users.get_current_user', return_value=mock_user):
            with patch('app.repositories.user_repository.UserRepository.log_user_activity',
                      new_callable=AsyncMock, return_value=True):

                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    response = await client.put(
                        "/api/v1/users/profile",
                        json={"email": "invalid-email"},
                        headers=mock_auth_headers
                    )

                    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_update_profile_valid_phone_e164(self, mock_user, mock_auth_headers):
        """Test: Valid E.164 phone update succeeds"""
        from app.main import app

        updated_user = mock_user.copy(update={"phone": "+240222999888"})

        # Mock dependencies
        with patch('app.api.v1.users.get_current_user', return_value=mock_user):
            with patch('app.repositories.user_repository.UserRepository.update',
                      new_callable=AsyncMock, return_value=updated_user):
                with patch('app.repositories.user_repository.UserRepository.log_user_activity',
                          new_callable=AsyncMock, return_value=True):

                    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                        response = await client.put(
                            "/api/v1/users/profile",
                            json={"phone": "+240222999888"},
                            headers=mock_auth_headers
                        )

                        assert response.status_code == status.HTTP_200_OK
                        assert response.json()["phone"] == "+240222999888"

    @pytest.mark.asyncio
    async def test_update_profile_invalid_phone_format(self, mock_user, mock_auth_headers):
        """Test: Invalid phone format returns 422"""
        from app.main import app

        # Mock dependencies
        with patch('app.api.v1.users.get_current_user', return_value=mock_user):
            with patch('app.repositories.user_repository.UserRepository.log_user_activity',
                      new_callable=AsyncMock, return_value=True):

                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    response = await client.put(
                        "/api/v1/users/profile",
                        json={"phone": "0222123456"},  # Missing +
                        headers=mock_auth_headers
                    )

                    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
                    assert "E.164" in response.text or "phone" in response.text.lower()

    @pytest.mark.asyncio
    async def test_update_profile_phone_with_dashes(self, mock_user, mock_auth_headers):
        """Test: Phone with dashes is auto-formatted (REAL DB TEST)"""
        from app.main import app

        # Real DB test - requires valid auth token
        pytest.skip("Real DB test - requires valid auth token from test user. TODO: Setup test user in Supabase with known credentials")

    @pytest.mark.asyncio
    async def test_update_profile_multiple_fields(self, mock_user, mock_auth_headers):
        """Test: Multiple fields can be updated together"""
        from app.main import app

        updated_user = mock_user.copy(update={
            "first_name": "Updated",
            "last_name": "Name",
            "city": "Bata"
        })

        # Mock dependencies
        with patch('app.api.v1.users.get_current_user', return_value=mock_user):
            with patch('app.repositories.user_repository.UserRepository.update',
                      new_callable=AsyncMock, return_value=updated_user):
                with patch('app.repositories.user_repository.UserRepository.log_user_activity',
                          new_callable=AsyncMock, return_value=True):

                    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                        response = await client.put(
                            "/api/v1/users/profile",
                            json={
                                "first_name": "Updated",
                                "last_name": "Name",
                                "city": "Bata"
                            },
                            headers=mock_auth_headers
                        )

                        assert response.status_code == status.HTTP_200_OK
                        data = response.json()
                        assert data["first_name"] == "Updated"
                        assert data["last_name"] == "Name"
                        assert data["city"] == "Bata"

    @pytest.mark.asyncio
    async def test_update_profile_unauthenticated(self):
        """Test: Unauthenticated request returns 401/403"""
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.put(
                "/api/v1/users/profile",
                json={"email": "test@example.com"}
                # No auth headers
            )

            # Should fail authentication
            assert response.status_code in [
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN
            ]
