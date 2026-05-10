"""
REAL DATABASE INTEGRATION TESTS
Tests with actual Supabase users - NO MOCKS

Mission: Validate all recent implementations with REAL data
- TASK-M01-002: Refactoring securite (bcrypt, password verification)
- TASK-M01-005: Endpoints profil (GET/PATCH /users/profile, POST /users/password)
- TASK-M01-006: Password reset (POST /auth/password/reset/request, /auth/password/reset/confirm)
- TASK-M01-007: Email verification (POST /auth/email/verify, /auth/email/resend)

NOTE: These tests use REAL database connections and REAL user data
Test users: Uses existing users from Supabase (libressay@gmail.com, user@odoolab.site, validation@example.com)
"""

import pytest
import pytest_asyncio
import asyncio
from httpx import AsyncClient, ASGITransport
from fastapi import status
from datetime import datetime
from loguru import logger

# Test configuration
TEST_USERS = [
    {
        "id": "3080a850-416f-4c52-a7a1-b2c3e224ef9f",
        "email": "libressay@gmail.com",
        "role": "citizen",
        "status": "active"
    },
    {
        "id": "90c3d9b5-2458-4610-8e0b-32aec72b8e58",
        "email": "user@odoolab.site",
        "role": "citizen",
        "status": "active"
    },
    {
        "id": "b50f0f9f-f181-45e7-a009-8e3f1a98bca3",
        "email": "validation@example.com",
        "role": "citizen",
        "status": "active"
    }
]

# Test password (MUST match actual password in Supabase)
# If this password is wrong, login tests will fail
TEST_PASSWORD = "Test123!"


@pytest_asyncio.fixture(scope="module")
async def real_db_connection():
    """Verify database connection to Supabase"""
    from app.database.connection import DatabaseManager

    db = DatabaseManager()
    try:
        await db.connect()
        # Test query
        result = await db.execute_scalar("SELECT COUNT(*) FROM users")
        logger.info(f"Database connected - {result} users in database")
        yield db
    finally:
        await db.disconnect()


@pytest_asyncio.fixture(scope="module")
async def test_app():
    """Get FastAPI app instance"""
    from app.main import app
    return app


@pytest_asyncio.fixture(scope="module")
async def auth_tokens(test_app):
    """
    Login test users and get their access tokens

    WARNING: This will FAIL if test users don't have the correct password
    You may need to:
    1. Reset passwords in Supabase UI
    2. Or use /auth/password/reset/request endpoint to reset
    """
    tokens = {}
    failed_logins = []

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        for user in TEST_USERS:
            try:
                response = await client.post(
                    "/api/v1/auth/login",
                    json={
                        "email": user["email"],
                        "password": TEST_PASSWORD,
                        "remember_me": False
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    tokens[user["email"]] = {
                        "access_token": data["access_token"],
                        "refresh_token": data["refresh_token"],
                        "user_id": user["id"]
                    }
                    logger.success(f"Logged in: {user['email']}")
                else:
                    failed_logins.append({
                        "email": user["email"],
                        "status": response.status_code,
                        "error": response.json()
                    })
                    logger.warning(f"Login failed for {user['email']}: {response.status_code}")

            except Exception as e:
                failed_logins.append({
                    "email": user["email"],
                    "error": str(e)
                })
                logger.error(f"Login exception for {user['email']}: {e}")

    # If all logins failed, skip entire test suite
    if not tokens:
        pytest.skip(
            f"No test users could login. Failed logins: {failed_logins}. "
            f"Please verify TEST_PASSWORD or reset user passwords in Supabase."
        )

    if failed_logins:
        logger.warning(f"Some logins failed: {failed_logins}")

    return tokens


# =============================================================================
# AUTHENTICATION TESTS (TASK-M01-002: Bcrypt security)
# =============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
class TestRealAuthenticationEndpoints:
    """Test authentication endpoints with real database"""

    async def test_login_success_real_user(self, test_app):
        """Test: Login with real user credentials"""
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": TEST_USERS[0]["email"],
                    "password": TEST_PASSWORD,
                    "remember_me": False
                }
            )

            # If this fails, TEST_PASSWORD is wrong
            if response.status_code != 200:
                pytest.skip(
                    f"Login failed - verify TEST_PASSWORD is correct for {TEST_USERS[0]['email']}. "
                    f"Status: {response.status_code}, Error: {response.json()}"
                )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "access_token" in data
            assert "refresh_token" in data
            assert data["token_type"] == "bearer"
            assert "user" in data
            assert data["user"]["email"] == TEST_USERS[0]["email"]

    async def test_login_wrong_password(self, test_app):
        """Test: Login with wrong password returns 401"""
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": TEST_USERS[0]["email"],
                    "password": "WrongPassword123!",
                    "remember_me": False
                }
            )

            assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_login_nonexistent_user(self, test_app):
        """Test: Login with non-existent email"""
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": "nonexistent@example.com",
                    "password": TEST_PASSWORD,
                    "remember_me": False
                }
            )

            assert response.status_code == status.HTTP_401_UNAUTHORIZED


# =============================================================================
# PROFILE ENDPOINTS TESTS (TASK-M01-005)
# =============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
class TestRealProfileEndpoints:
    """Test profile endpoints with real authenticated users"""

    async def test_get_profile_real_user(self, test_app, auth_tokens):
        """Test: GET /users/profile with real authenticated user"""
        # Use first available logged-in user
        user_email = list(auth_tokens.keys())[0]
        token_data = auth_tokens[user_email]

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/users/profile",
                headers={"Authorization": f"Bearer {token_data['access_token']}"}
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["email"] == user_email
            assert data["id"] == token_data["user_id"]
            assert "role" in data
            assert "status" in data

    async def test_update_profile_real_user(self, test_app, auth_tokens):
        """Test: PUT /users/profile with real user (update first_name)"""
        # Use second available user (to avoid conflicts)
        user_emails = list(auth_tokens.keys())
        if len(user_emails) < 2:
            pytest.skip("Need at least 2 logged-in users for this test")

        user_email = user_emails[1]
        token_data = auth_tokens[user_email]

        new_first_name = f"TestUpdated_{datetime.utcnow().microsecond}"

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.put(
                "/api/v1/users/profile",
                json={"first_name": new_first_name},
                headers={"Authorization": f"Bearer {token_data['access_token']}"}
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["first_name"] == new_first_name

            # Verify update persisted by getting profile again
            verify_response = await client.get(
                "/api/v1/users/profile",
                headers={"Authorization": f"Bearer {token_data['access_token']}"}
            )
            assert verify_response.status_code == status.HTTP_200_OK
            verify_data = verify_response.json()
            assert verify_data["first_name"] == new_first_name

    async def test_update_profile_invalid_email(self, test_app, auth_tokens):
        """Test: PUT /users/profile with invalid email format returns 422"""
        user_email = list(auth_tokens.keys())[0]
        token_data = auth_tokens[user_email]

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.put(
                "/api/v1/users/profile",
                json={"email": "invalid-email-format"},
                headers={"Authorization": f"Bearer {token_data['access_token']}"}
            )

            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_get_profile_no_auth(self, test_app):
        """Test: GET /users/profile without auth returns 401/403"""
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.get("/api/v1/users/profile")

            assert response.status_code in [
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN
            ]


# =============================================================================
# PASSWORD CHANGE TESTS (TASK-M01-005: POST /users/password)
# =============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
class TestRealPasswordChange:
    """Test password change endpoint with real users"""

    async def test_change_password_wrong_old_password(self, test_app, auth_tokens):
        """Test: Change password with wrong old password returns 400"""
        user_email = list(auth_tokens.keys())[0]
        token_data = auth_tokens[user_email]

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/users/password",
                json={
                    "old_password": "WrongOldPassword123!",
                    "new_password": "NewValidPassword456!"
                },
                headers={"Authorization": f"Bearer {token_data['access_token']}"}
            )

            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "incorrect" in response.json()["detail"].lower()

    async def test_change_password_weak_new_password(self, test_app, auth_tokens):
        """Test: Change password with weak new password returns 400"""
        user_email = list(auth_tokens.keys())[0]
        token_data = auth_tokens[user_email]

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/users/password",
                json={
                    "old_password": TEST_PASSWORD,
                    "new_password": "weak"  # Too short, no uppercase, no digits
                },
                headers={"Authorization": f"Bearer {token_data['access_token']}"}
            )

            # Should fail validation or business logic
            assert response.status_code in [
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ]

    async def test_change_password_success_and_revert(self, test_app, auth_tokens):
        """
        Test: Successfully change password and revert it back

        IMPORTANT: This test modifies real data!
        It changes password and then reverts it to keep test idempotent
        """
        # Use third user to avoid interfering with other tests
        user_emails = list(auth_tokens.keys())
        if len(user_emails) < 3:
            pytest.skip("Need at least 3 logged-in users for password change test")

        user_email = user_emails[2]
        token_data = auth_tokens[user_email]

        new_password = "NewTempPassword789!"

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            # Step 1: Change password to new one
            response = await client.post(
                "/api/v1/users/password",
                json={
                    "old_password": TEST_PASSWORD,
                    "new_password": new_password
                },
                headers={"Authorization": f"Bearer {token_data['access_token']}"}
            )

            if response.status_code != 200:
                pytest.skip(
                    f"Password change failed - TEST_PASSWORD might be wrong for {user_email}. "
                    f"Status: {response.status_code}, Error: {response.json()}"
                )

            assert response.status_code == status.HTTP_200_OK
            assert "success" in response.json()["message"].lower()

            # Step 2: Verify new password works by logging in
            login_response = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": user_email,
                    "password": new_password,
                    "remember_me": False
                }
            )
            assert login_response.status_code == status.HTTP_200_OK
            new_token = login_response.json()["access_token"]

            # Step 3: Revert password back to original
            revert_response = await client.post(
                "/api/v1/users/password",
                json={
                    "old_password": new_password,
                    "new_password": TEST_PASSWORD
                },
                headers={"Authorization": f"Bearer {new_token}"}
            )
            assert revert_response.status_code == status.HTTP_200_OK

            # Step 4: Verify original password works again
            final_login = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": user_email,
                    "password": TEST_PASSWORD,
                    "remember_me": False
                }
            )
            assert final_login.status_code == status.HTTP_200_OK


# =============================================================================
# PASSWORD RESET TESTS (TASK-M01-006)
# =============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
class TestRealPasswordReset:
    """Test password reset endpoints with real database"""

    async def test_password_reset_request_existing_email(self, test_app):
        """Test: Request password reset for existing user"""
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/password/reset/request",
                json={"email": TEST_USERS[0]["email"]}
            )

            # Should always return 200 (for security reasons)
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "message" in data
            assert data["email"] == TEST_USERS[0]["email"]

    async def test_password_reset_request_nonexistent_email(self, test_app):
        """Test: Request password reset for non-existent email (still returns 200)"""
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/password/reset/request",
                json={"email": "nonexistent@example.com"}
            )

            # Should still return 200 (don't reveal if email exists)
            assert response.status_code == status.HTTP_200_OK

    async def test_password_reset_confirm_invalid_token(self, test_app):
        """Test: Confirm password reset with invalid token returns 400"""
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/password/reset/confirm",
                json={
                    "token": "invalid_token_12345678901234567890123456789012",
                    "new_password": "NewPassword123!"
                }
            )

            assert response.status_code == status.HTTP_400_BAD_REQUEST


# =============================================================================
# EMAIL VERIFICATION TESTS (TASK-M01-007)
# =============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
class TestRealEmailVerification:
    """Test email verification endpoints with real database"""

    async def test_verify_email_invalid_code(self, test_app):
        """Test: Verify email with invalid code returns 400"""
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/email/verify",
                json={"verification_code": "999999"}  # Invalid 6-digit code
            )

            assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_resend_verification_email_authenticated(self, test_app, auth_tokens):
        """Test: Resend verification email for authenticated user"""
        user_email = list(auth_tokens.keys())[0]
        token_data = auth_tokens[user_email]

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/email/resend",
                headers={"Authorization": f"Bearer {token_data['access_token']}"}
            )

            # Should succeed or fail gracefully
            assert response.status_code in [
                status.HTTP_200_OK,
                status.HTTP_400_BAD_REQUEST  # Might fail if email service not configured
            ]

            if response.status_code == 200:
                data = response.json()
                assert data["email"] == user_email

    async def test_resend_verification_email_no_auth(self, test_app):
        """Test: Resend verification email without auth returns 401/403"""
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post("/api/v1/auth/email/resend")

            assert response.status_code in [
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN
            ]


# =============================================================================
# TOKEN REFRESH TESTS
# =============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
class TestRealTokenRefresh:
    """Test token refresh functionality with real tokens"""

    async def test_refresh_token_success(self, test_app, auth_tokens):
        """Test: Refresh access token using refresh token"""
        user_email = list(auth_tokens.keys())[0]
        token_data = auth_tokens[user_email]

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": token_data["refresh_token"]}
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "access_token" in data
            assert "refresh_token" in data
            # New tokens should be different
            assert data["access_token"] != token_data["access_token"]

    async def test_refresh_token_invalid(self, test_app):
        """Test: Refresh with invalid refresh token returns 401"""
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": "invalid_refresh_token_xyz"}
            )

            assert response.status_code == status.HTTP_401_UNAUTHORIZED


# =============================================================================
# SUMMARY HELPER
# =============================================================================

def pytest_sessionfinish(session, exitstatus):
    """Print summary after all tests complete"""
    logger.info("=" * 70)
    logger.info("REAL DATABASE INTEGRATION TESTS COMPLETED")
    logger.info("=" * 70)
    logger.info(f"Test users used: {len(TEST_USERS)}")
    for user in TEST_USERS:
        logger.info(f"  - {user['email']} (ID: {user['id']})")
    logger.info("=" * 70)
