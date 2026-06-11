"""
Integration tests for 2FA login endpoints (TASK-M01-013)

Tests for 2FA-enabled login flow:
- POST /auth/login with 2FA enabled user
- POST /auth/login/2fa-verify

Coverage:
- Login flow returns temp_token when 2FA enabled
- Login flow returns normal tokens when 2FA disabled
- 2FA verify endpoint validates temp token and code
- Error handling (invalid temp token, invalid code, expired token)

NO MOCKS - Real database testing following system_instructions.md
"""

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from datetime import datetime, timedelta
import pyotp

from app.main import app
from app.modules.auth.services.jwt_service import get_jwt_service


# ==============================================================================
# Setup Guide for Real Database Testing
# ==============================================================================
"""
SETUP GUIDE: Real Supabase Test User with 2FA Enabled

Follow these steps to setup a test user with 2FA enabled in your Supabase database:

## Step 1: Create test user with 2FA enabled in Supabase

Execute this SQL query in your Supabase SQL Editor:

```sql
-- Create test user with 2FA ENABLED
INSERT INTO users (
    id,
    email,
    password_hash,
    first_name,
    last_name,
    role,
    status,
    two_factor_enabled,
    two_factor_secret,
    two_factor_backup_codes,
    two_factor_enabled_at,
    created_at,
    updated_at
) VALUES (
    'test_2fa_user_id_123456789',
    'test_2fa_user@example.com',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LdMxeCOgOCbOhq3i2',  -- Password: Test1234!
    'Test',
    'User2FA',
    'citizen',
    'active',
    TRUE,  -- 2FA ENABLED
    'JBSWY3DPEHPK3PXP',  -- TOTP secret (example - use pyotp.random_base32() for real)
    '["5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8", "7c222fb2927d828af22f592134e8932480637c0d6e5f8d4a9c51a0b6a0e3e8b6"]',  -- Hashed backup codes
    NOW(),
    NOW(),
    NOW()
)
ON CONFLICT (email) DO UPDATE SET
    password_hash = EXCLUDED.password_hash,
    two_factor_enabled = EXCLUDED.two_factor_enabled,
    two_factor_secret = EXCLUDED.two_factor_secret,
    two_factor_backup_codes = EXCLUDED.two_factor_backup_codes,
    two_factor_enabled_at = EXCLUDED.two_factor_enabled_at,
    updated_at = NOW();

-- Create test user WITHOUT 2FA (for comparison tests)
INSERT INTO users (
    id,
    email,
    password_hash,
    first_name,
    last_name,
    role,
    status,
    two_factor_enabled,
    created_at,
    updated_at
) VALUES (
    'test_no2fa_user_id_987654321',
    'test_no2fa_user@example.com',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LdMxeCOgOCbOhq3i2',  -- Password: Test1234!
    'Test',
    'UserNo2FA',
    'citizen',
    'active',
    FALSE,  -- 2FA DISABLED
    NOW(),
    NOW()
)
ON CONFLICT (email) DO UPDATE SET
    password_hash = EXCLUDED.password_hash,
    two_factor_enabled = EXCLUDED.two_factor_enabled,
    updated_at = NOW();
```

## Step 2: Generate valid TOTP code for testing

Use this Python code to generate a valid 6-digit TOTP code:

```python
import pyotp

# Use the same secret from the SQL query above
secret = "JBSWY3DPEHPK3PXP"
totp = pyotp.TOTP(secret)
current_code = totp.now()
print(f"Current TOTP code: {current_code}")
```

## Step 3: Test login flow manually with curl

### Step 3a: Login with 2FA enabled user (should return temp_token)
```bash
curl -X POST https://your-backend.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test_2fa_user@example.com",
    "password": "Test1234!",
    "remember_me": false
  }'

# Expected response:
# {
#   "requires_2fa": true,
#   "temp_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
#   "message": "2FA verification required. Please provide your 2FA code."
# }
```

### Step 3b: Verify 2FA with code (should return access/refresh tokens)
```bash
# First, generate current TOTP code with pyotp (see Step 2)
# Then use the temp_token from Step 3a

curl -X POST https://your-backend.com/api/v1/auth/login/2fa-verify \
  -H "Content-Type: application/json" \
  -d '{
    "temp_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
    "code": "123456"  # Replace with current TOTP code
  }'

# Expected response:
# {
#   "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
#   "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
#   "token_type": "bearer",
#   "expires_in": 3600,
#   "user": {...}
# }
```

### Step 3c: Login with NO 2FA user (should return tokens immediately)
```bash
curl -X POST https://your-backend.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test_no2fa_user@example.com",
    "password": "Test1234!",
    "remember_me": false
  }'

# Expected response (NO temp_token, direct access):
# {
#   "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
#   "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
#   "token_type": "bearer",
#   "expires_in": 3600,
#   "user": {...}
# }
```

## Step 4: Uncomment real database tests

After completing Steps 1-3, uncomment the tests marked with `@pytest.mark.skip` in this file
and update the test constants with your real test user credentials.

## Step 5: Run pytest

```bash
cd packages/backend
pytest tests/integration/test_auth_2fa_login_endpoints.py -v
```

Expected result: All tests should pass with real Supabase database.

"""

# ==============================================================================
# Test Constants (Update with your real test user data)
# ==============================================================================
TEST_2FA_USER_EMAIL = "test_2fa_user@taxasge.com"
TEST_2FA_USER_PASSWORD = "TestPass2FA123!"
TEST_2FA_USER_SECRET = "JBSWY3DPEHPK3PXP"  # TOTP secret from setup script

TEST_NO2FA_USER_EMAIL = "test_no2fa_user@taxasge.com"
TEST_NO2FA_USER_PASSWORD = "TestPassNo2FA456!"


# ==============================================================================
# Tests WITHOUT Database (Authentication/Validation Tests)
# ==============================================================================

class TestLoginEndpointValidation:
    """Tests for POST /auth/login endpoint validation (no DB required)"""

    def test_login_missing_email(self):
        """Test: POST /login fails with missing email"""
        client = TestClient(app)

        response = client.post(
            "/api/v1/auth/login",
            json={
                "password": "Test1234!",
                "remember_me": False,
            },
        )

        # Verify: 422 Unprocessable Entity (Pydantic validation)
        assert response.status_code == 422
        assert "detail" in response.json()

    def test_login_missing_password(self):
        """Test: POST /login fails with missing password"""
        client = TestClient(app)

        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "remember_me": False,
            },
        )

        # Verify: 422 Unprocessable Entity
        assert response.status_code == 422

    def test_login_invalid_email_format(self):
        """Test: POST /login fails with invalid email format"""
        client = TestClient(app)

        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "invalid-email-format",
                "password": "Test1234!",
                "remember_me": False,
            },
        )

        # Verify: 422 Unprocessable Entity (email validation)
        assert response.status_code == 422


class TestTwoFactorVerifyEndpointValidation:
    """Tests for POST /auth/login/2fa-verify endpoint validation (no DB required)"""

    def test_2fa_verify_missing_temp_token(self):
        """Test: POST /login/2fa-verify fails with missing temp_token"""
        client = TestClient(app)

        response = client.post(
            "/api/v1/auth/login/2fa-verify",
            json={
                "code": "123456",
            },
        )

        # Verify: 422 Unprocessable Entity
        assert response.status_code == 422

    def test_2fa_verify_missing_code(self):
        """Test: POST /login/2fa-verify fails with missing code"""
        client = TestClient(app)

        response = client.post(
            "/api/v1/auth/login/2fa-verify",
            json={
                "temp_token": "some_token",
            },
        )

        # Verify: 422 Unprocessable Entity
        assert response.status_code == 422

    def test_2fa_verify_invalid_temp_token(self):
        """Test: POST /login/2fa-verify fails with invalid JWT temp_token"""
        client = TestClient(app)

        response = client.post(
            "/api/v1/auth/login/2fa-verify",
            json={
                "temp_token": "invalid_jwt_token",
                "code": "123456",
            },
        )

        # Verify: 401 Unauthorized or 500 (JWT validation error)
        assert response.status_code in [401, 500]

    def test_2fa_verify_expired_temp_token(self):
        """Test: POST /login/2fa-verify fails with expired temp_token"""
        client = TestClient(app)

        # Generate expired temp token (expired 10 minutes ago)
        jwt_service = get_jwt_service()
        expired_token = jwt_service.create_access_token(
            subject="test_user_id",
            user_data={
                "email": "test@example.com",
                "role": "citizen",
                "type": "2fa_temp",
            },
            expires_delta=timedelta(minutes=-10),  # Already expired
        )

        response = client.post(
            "/api/v1/auth/login/2fa-verify",
            json={
                "temp_token": expired_token,
                "code": "123456",
            },
        )

        # Verify: 401 Unauthorized (expired token)
        assert response.status_code in [401, 500]


# ==============================================================================
# Tests WITH Real Database (E2E Tests)
# ==============================================================================

@pytest.mark.skip(
    reason="Requires real Supabase test user with 2FA enabled. "
    "Follow setup guide above, then uncomment this test."
)
class TestLoginWith2FAEnabledUser:
    """Integration tests for POST /auth/login with 2FA enabled user (real DB)"""

    def test_login_with_2fa_enabled_returns_temp_token(self):
        """Test: POST /login returns temp_token when user has 2FA enabled"""
        client = TestClient(app)

        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": TEST_2FA_USER_EMAIL,
                "password": TEST_2FA_USER_PASSWORD,
                "remember_me": False,
            },
        )

        # Verify: 200 OK
        assert response.status_code == 200

        # Verify: Response contains temp_token and requires_2fa flag
        data = response.json()
        assert data["requires_2fa"] is True
        assert "temp_token" in data
        assert "message" in data
        assert "2FA verification required" in data["message"]

        # Verify: Does NOT contain access_token (not logged in yet)
        assert "access_token" not in data
        assert "refresh_token" not in data
        assert "user" not in data

    def test_login_with_2fa_remember_me_preserved(self):
        """Test: POST /login preserves remember_me flag in temp_token"""
        client = TestClient(app)

        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": TEST_2FA_USER_EMAIL,
                "password": TEST_2FA_USER_PASSWORD,
                "remember_me": True,  # Should be preserved
            },
        )

        # Verify: 200 OK
        assert response.status_code == 200

        # Verify: temp_token contains remember_me=True
        data = response.json()
        temp_token = data["temp_token"]

        # Decode JWT to verify remember_me flag
        jwt_service = get_jwt_service()
        token_data = jwt_service.verify_access_token(temp_token)
        assert token_data is not None
        assert token_data.get("remember_me") is True


@pytest.mark.skip(
    reason="Requires real Supabase test user WITHOUT 2FA. "
    "Follow setup guide above, then uncomment this test."
)
class TestLoginWithout2FA:
    """Integration tests for POST /auth/login with 2FA disabled user (real DB)"""

    def test_login_without_2fa_returns_tokens_immediately(self):
        """Test: POST /login returns access/refresh tokens when 2FA disabled"""
        client = TestClient(app)

        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": TEST_NO2FA_USER_EMAIL,
                "password": TEST_NO2FA_USER_PASSWORD,
                "remember_me": False,
            },
        )

        # Verify: 200 OK
        assert response.status_code == 200

        # Verify: Response contains access/refresh tokens (standard login)
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert "token_type" in data
        assert "expires_in" in data
        assert "user" in data

        # Verify: Does NOT require 2FA
        assert "requires_2fa" not in data
        assert "temp_token" not in data


@pytest.mark.skip(
    reason="Requires real Supabase test user with 2FA enabled. "
    "Follow setup guide above, then uncomment this test."
)
class TestTwoFactorVerifyEndpoint:
    """Integration tests for POST /auth/login/2fa-verify endpoint (real DB)"""

    def test_2fa_verify_with_valid_totp_code(self):
        """Test: POST /login/2fa-verify succeeds with valid TOTP code"""
        client = TestClient(app)

        # Step 1: Login to get temp_token
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "email": TEST_2FA_USER_EMAIL,
                "password": TEST_2FA_USER_PASSWORD,
                "remember_me": False,
            },
        )
        assert login_response.status_code == 200
        temp_token = login_response.json()["temp_token"]

        # Step 2: Generate current TOTP code
        totp = pyotp.TOTP(TEST_2FA_USER_SECRET)
        current_code = totp.now()

        # Step 3: Verify 2FA with code
        verify_response = client.post(
            "/api/v1/auth/login/2fa-verify",
            json={
                "temp_token": temp_token,
                "code": current_code,
            },
        )

        # Verify: 200 OK
        assert verify_response.status_code == 200

        # Verify: Response contains access/refresh tokens
        data = verify_response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data
        assert "user" in data

        # Verify: User data is correct
        assert data["user"]["email"] == TEST_2FA_USER_EMAIL

    def test_2fa_verify_with_invalid_code(self):
        """Test: POST /login/2fa-verify fails with invalid TOTP code"""
        client = TestClient(app)

        # Step 1: Login to get temp_token
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "email": TEST_2FA_USER_EMAIL,
                "password": TEST_2FA_USER_PASSWORD,
                "remember_me": False,
            },
        )
        assert login_response.status_code == 200
        temp_token = login_response.json()["temp_token"]

        # Step 2: Try to verify with INVALID code
        verify_response = client.post(
            "/api/v1/auth/login/2fa-verify",
            json={
                "temp_token": temp_token,
                "code": "000000",  # Invalid code
            },
        )

        # Verify: 401 Unauthorized or 500 (invalid 2FA code)
        assert verify_response.status_code in [401, 500]

    def test_2fa_verify_with_wrong_token_type(self):
        """Test: POST /login/2fa-verify fails with non-2fa_temp token"""
        client = TestClient(app)

        # Generate a regular access token (NOT 2fa_temp)
        jwt_service = get_jwt_service()
        access_token = jwt_service.create_access_token(
            subject="test_user_id",
            user_data={
                "email": TEST_2FA_USER_EMAIL,
                "role": "citizen",
                "type": "access",  # Wrong type!
            },
        )

        # Generate valid TOTP code
        totp = pyotp.TOTP(TEST_2FA_USER_SECRET)
        current_code = totp.now()

        # Try to verify with wrong token type
        verify_response = client.post(
            "/api/v1/auth/login/2fa-verify",
            json={
                "temp_token": access_token,  # Wrong token type
                "code": current_code,
            },
        )

        # Verify: 401 Unauthorized or 500 (invalid token type)
        assert verify_response.status_code in [401, 500]


@pytest.mark.skip(
    reason="Requires real Supabase test users. "
    "Follow setup guide above, then uncomment this test."
)
class TestE2E2FALoginFlow:
    """End-to-End test for complete 2FA login flow (real DB)"""

    def test_complete_2fa_login_flow(self):
        """Test: Complete E2E flow - Login → 2FA verify → Authenticated"""
        client = TestClient(app)

        # ===== STEP 1: User enters email + password =====
        print("\n[STEP 1] User submits email + password")
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "email": TEST_2FA_USER_EMAIL,
                "password": TEST_2FA_USER_PASSWORD,
                "remember_me": True,
            },
        )

        assert login_response.status_code == 200
        login_data = login_response.json()

        # Verify: Backend asks for 2FA
        assert login_data["requires_2fa"] is True
        assert "temp_token" in login_data
        temp_token = login_data["temp_token"]
        print(f"[STEP 1] ✓ Backend returned temp_token (2FA required)")

        # ===== STEP 2: User opens authenticator app =====
        print("\n[STEP 2] User opens Google Authenticator / Authy")
        totp = pyotp.TOTP(TEST_2FA_USER_SECRET)
        current_code = totp.now()
        print(f"[STEP 2] ✓ User sees code: {current_code}")

        # ===== STEP 3: User enters 6-digit code =====
        print(f"\n[STEP 3] User submits code: {current_code}")
        verify_response = client.post(
            "/api/v1/auth/login/2fa-verify",
            json={
                "temp_token": temp_token,
                "code": current_code,
            },
        )

        assert verify_response.status_code == 200
        verify_data = verify_response.json()

        # Verify: Backend returns access/refresh tokens
        assert "access_token" in verify_data
        assert "refresh_token" in verify_data
        assert "user" in verify_data
        print(f"[STEP 3] ✓ Backend returned access/refresh tokens")

        # ===== STEP 4: User is authenticated =====
        print("\n[STEP 4] User makes authenticated request")
        access_token = verify_data["access_token"]

        # Try to access protected endpoint (e.g., GET /auth/me)
        me_response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert me_response.status_code == 200
        me_data = me_response.json()
        assert me_data["email"] == TEST_2FA_USER_EMAIL
        print(f"[STEP 4] ✓ User successfully authenticated: {me_data['email']}")

        print("\n[SUCCESS] Complete 2FA login flow: ✓ PASSED")
