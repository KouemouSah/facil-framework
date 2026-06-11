"""
Integration tests for Two-Factor Authentication endpoints (TASK-M01-012)

Tests for 2FA API endpoints with real database.

Coverage:
- POST /auth/2fa/enable
- POST /auth/2fa/verify
- POST /auth/2fa/disable
- GET /auth/2fa/status

Following system_instructions.md: "ne travaille pas avec des mock"
"""

import pytest
import pyotp
from httpx import AsyncClient, ASGITransport
from app.main import app

# Test user credentials (must exist in Supabase)
TEST_USER_EMAIL = "test2fa@taxasge.com"
TEST_USER_PASSWORD = "Test2FA@Password123!"

# Global variables to store data between test steps
VALID_JWT_TOKEN = None
TOTP_SECRET = None
BACKUP_CODES = None


@pytest.fixture
async def client():
    """Fixture: AsyncClient for FastAPI app"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestTwoFactorEnableEndpoint:
    """Integration tests for POST /auth/2fa/enable"""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires real Supabase user and valid JWT token. See setup guide below.")
    async def test_enable_2fa_success(self, client):
        """
        Test: POST /auth/2fa/enable returns secret, QR code, and backup codes

        **Prerequisites:**
        1. Test user must exist in Supabase
        2. Test user must have 2FA DISABLED
        3. Valid JWT token required

        **Setup Guide:**

        # Step 1: Create test user (run in Supabase SQL editor)
        INSERT INTO users (email, password_hash, role, status, first_name, last_name, two_factor_enabled)
        VALUES (
            'test2fa@taxasge.com',
            '$2b$12$HASH_HERE',  -- Use bcrypt hash of 'Test2FA@Password123!'
            'citizen',
            'active',
            'Test',
            '2FA',
            FALSE
        )
        ON CONFLICT (email) DO UPDATE SET two_factor_enabled = FALSE;

        # Step 2: Get JWT token
        curl -X POST http://localhost:8000/api/v1/auth/login \
             -H "Content-Type: application/json" \
             -d '{"email": "test2fa@taxasge.com", "password": "Test2FA@Password123!"}'

        # Step 3: Copy access_token from response

        # Step 4: Update VALID_JWT_TOKEN in this file

        # Step 5: Uncomment test and run:
        pytest tests/integration/test_two_factor_endpoints.py::TestTwoFactorEnableEndpoint::test_enable_2fa_success -v
        """
        global VALID_JWT_TOKEN, TOTP_SECRET, BACKUP_CODES

        # REPLACE WITH YOUR VALID JWT TOKEN FROM STEP 2
        VALID_JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.YOUR_TOKEN_HERE"

        headers = {"Authorization": f"Bearer {VALID_JWT_TOKEN}"}

        response = await client.post("/api/v1/auth/2fa/enable", headers=headers)

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "secret" in data
        assert "qr_code_svg" in data
        assert "backup_codes" in data
        assert "message" in data

        # Verify secret format (base32, 32 chars)
        assert len(data["secret"]) == 32
        assert all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567' for c in data["secret"])

        # Verify QR code is SVG
        assert isinstance(data["qr_code_svg"], str)
        assert "svg" in data["qr_code_svg"].lower()

        # Verify backup codes (10 codes, format XXXX-XXXX)
        assert len(data["backup_codes"]) == 10
        for code in data["backup_codes"]:
            assert len(code) == 9
            assert code[4] == '-'
            assert code[:4].isdigit()
            assert code[5:].isdigit()

        # Store for next tests
        TOTP_SECRET = data["secret"]
        BACKUP_CODES = data["backup_codes"]

    @pytest.mark.asyncio
    async def test_enable_2fa_unauthenticated(self, client):
        """Test: POST /auth/2fa/enable returns 401 without token"""
        response = await client.post("/api/v1/auth/2fa/enable")

        assert response.status_code == 403  # FastAPI HTTPBearer returns 403

    @pytest.mark.asyncio
    async def test_enable_2fa_invalid_token(self, client):
        """Test: POST /auth/2fa/enable returns 401 with invalid token"""
        headers = {"Authorization": "Bearer invalid_token_12345"}

        response = await client.post("/api/v1/auth/2fa/enable", headers=headers)

        assert response.status_code == 401

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires test user with 2FA already enabled")
    async def test_enable_2fa_already_enabled(self, client):
        """
        Test: POST /auth/2fa/enable returns 400 if 2FA already enabled

        **Setup:**
        1. Enable 2FA for test user first
        2. Run this test
        3. Should return 400 "2FA is already enabled for this account"
        """
        global VALID_JWT_TOKEN

        headers = {"Authorization": f"Bearer {VALID_JWT_TOKEN}"}

        response = await client.post("/api/v1/auth/2fa/enable", headers=headers)

        assert response.status_code == 400
        assert "already enabled" in response.json()["detail"].lower()


class TestTwoFactorVerifyEndpoint:
    """Integration tests for POST /auth/2fa/verify"""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires TOTP_SECRET and BACKUP_CODES from enable test")
    async def test_verify_2fa_valid_code(self, client):
        """
        Test: POST /auth/2fa/verify succeeds with valid TOTP code

        **Prerequisites:**
        1. Run test_enable_2fa_success first to get TOTP_SECRET
        2. Generate valid TOTP code
        3. Verify and enable 2FA
        """
        global VALID_JWT_TOKEN, TOTP_SECRET, BACKUP_CODES

        # Generate valid TOTP code
        totp = pyotp.TOTP(TOTP_SECRET)
        valid_code = totp.now()

        headers = {"Authorization": f"Bearer {VALID_JWT_TOKEN}"}
        payload = {
            "secret": TOTP_SECRET,
            "code": valid_code,
            "backup_codes": BACKUP_CODES
        }

        response = await client.post("/api/v1/auth/2fa/verify", headers=headers, json=payload)

        assert response.status_code == 200
        data = response.json()

        assert "message" in data
        assert data["two_factor_enabled"] is True
        assert "successfully" in data["message"].lower()

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires TOTP_SECRET from enable test")
    async def test_verify_2fa_invalid_code(self, client):
        """Test: POST /auth/2fa/verify fails with invalid code"""
        global VALID_JWT_TOKEN, TOTP_SECRET, BACKUP_CODES

        headers = {"Authorization": f"Bearer {VALID_JWT_TOKEN}"}
        payload = {
            "secret": TOTP_SECRET,
            "code": "000000",  # Invalid code
            "backup_codes": BACKUP_CODES
        }

        response = await client.post("/api/v1/auth/2fa/verify", headers=headers, json=payload)

        assert response.status_code == 400
        assert "invalid" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_verify_2fa_unauthenticated(self, client):
        """Test: POST /auth/2fa/verify returns 403 without token"""
        payload = {
            "secret": "JBSWY3DPEHPK3PXP",
            "code": "123456",
            "backup_codes": ["1234-5678"] * 10
        }

        response = await client.post("/api/v1/auth/2fa/verify", json=payload)

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_verify_2fa_invalid_request_format(self, client):
        """Test: POST /auth/2fa/verify validates request format"""
        global VALID_JWT_TOKEN

        if not VALID_JWT_TOKEN:
            pytest.skip("No valid JWT token available")

        headers = {"Authorization": f"Bearer {VALID_JWT_TOKEN}"}

        # Test 1: Code too short
        payload = {
            "secret": "JBSWY3DPEHPK3PXP",
            "code": "12345",  # Only 5 digits
            "backup_codes": ["1234-5678"] * 10
        }
        response = await client.post("/api/v1/auth/2fa/verify", headers=headers, json=payload)
        assert response.status_code == 422  # Pydantic validation error

        # Test 2: Non-numeric code
        payload["code"] = "abc123"
        response = await client.post("/api/v1/auth/2fa/verify", headers=headers, json=payload)
        assert response.status_code == 422

        # Test 3: Wrong backup codes count
        payload["code"] = "123456"
        payload["backup_codes"] = ["1234-5678"]  # Only 1 instead of 10
        response = await client.post("/api/v1/auth/2fa/verify", headers=headers, json=payload)
        assert response.status_code == 422


class TestTwoFactorDisableEndpoint:
    """Integration tests for POST /auth/2fa/disable"""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires test user with 2FA enabled and valid password")
    async def test_disable_2fa_success(self, client):
        """
        Test: POST /auth/2fa/disable succeeds with correct password

        **Prerequisites:**
        1. Test user must have 2FA enabled
        2. Valid JWT token
        3. Correct password
        """
        global VALID_JWT_TOKEN

        headers = {"Authorization": f"Bearer {VALID_JWT_TOKEN}"}
        payload = {"password": TEST_USER_PASSWORD}

        response = await client.post("/api/v1/auth/2fa/disable", headers=headers, json=payload)

        assert response.status_code == 200
        data = response.json()

        assert "message" in data
        assert data["two_factor_enabled"] is False
        assert "disabled successfully" in data["message"].lower()

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires test user with 2FA enabled")
    async def test_disable_2fa_wrong_password(self, client):
        """Test: POST /auth/2fa/disable fails with wrong password"""
        global VALID_JWT_TOKEN

        headers = {"Authorization": f"Bearer {VALID_JWT_TOKEN}"}
        payload = {"password": "WrongPassword123!"}

        response = await client.post("/api/v1/auth/2fa/disable", headers=headers, json=payload)

        assert response.status_code == 401
        assert "incorrect password" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_disable_2fa_unauthenticated(self, client):
        """Test: POST /auth/2fa/disable returns 403 without token"""
        payload = {"password": "SomePassword123!"}

        response = await client.post("/api/v1/auth/2fa/disable", json=payload)

        assert response.status_code == 403

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires test user with 2FA disabled")
    async def test_disable_2fa_not_enabled(self, client):
        """Test: POST /auth/2fa/disable returns 400 if 2FA not enabled"""
        global VALID_JWT_TOKEN

        headers = {"Authorization": f"Bearer {VALID_JWT_TOKEN}"}
        payload = {"password": TEST_USER_PASSWORD}

        response = await client.post("/api/v1/auth/2fa/disable", headers=headers, json=payload)

        assert response.status_code == 400
        assert "not enabled" in response.json()["detail"].lower()


class TestTwoFactorStatusEndpoint:
    """Integration tests for GET /auth/2fa/status"""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires valid JWT token")
    async def test_get_2fa_status_enabled(self, client):
        """
        Test: GET /auth/2fa/status returns correct status when 2FA enabled

        **Prerequisites:**
        1. Test user with 2FA enabled
        2. Valid JWT token
        """
        global VALID_JWT_TOKEN

        headers = {"Authorization": f"Bearer {VALID_JWT_TOKEN}"}

        response = await client.get("/api/v1/auth/2fa/status", headers=headers)

        assert response.status_code == 200
        data = response.json()

        assert "two_factor_enabled" in data
        assert "two_factor_enabled_at" in data
        assert "backup_codes_remaining" in data

        if data["two_factor_enabled"]:
            assert data["two_factor_enabled_at"] is not None
            assert data["backup_codes_remaining"] is not None
            assert 0 <= data["backup_codes_remaining"] <= 10

    @pytest.mark.asyncio
    async def test_get_2fa_status_unauthenticated(self, client):
        """Test: GET /auth/2fa/status returns 403 without token"""
        response = await client.get("/api/v1/auth/2fa/status")

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_2fa_status_invalid_token(self, client):
        """Test: GET /auth/2fa/status returns 401 with invalid token"""
        headers = {"Authorization": "Bearer invalid_token_12345"}

        response = await client.get("/api/v1/auth/2fa/status", headers=headers)

        assert response.status_code == 401


class TestTwoFactorWorkflowE2E:
    """End-to-end workflow tests for 2FA"""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires real Supabase user. See complete setup guide.")
    async def test_complete_2fa_workflow(self, client):
        """
        Test: Complete 2FA workflow from enable to disable

        **Workflow:**
        1. Check status (should be disabled)
        2. Enable 2FA (get secret + QR + backup codes)
        3. Verify setup (with valid TOTP code)
        4. Check status (should be enabled)
        5. Disable 2FA (with password)
        6. Check status (should be disabled again)

        **Setup Guide:**

        # Step 1: Create fresh test user in Supabase
        INSERT INTO users (email, password_hash, role, status, first_name, last_name, two_factor_enabled)
        VALUES (
            'test2fa@taxasge.com',
            '$2b$12$YOUR_BCRYPT_HASH',  -- Hash of 'Test2FA@Password123!'
            'citizen',
            'active',
            'Test',
            '2FA',
            FALSE
        )
        ON CONFLICT (email) DO UPDATE SET
            two_factor_enabled = FALSE,
            two_factor_secret = NULL,
            two_factor_backup_codes = NULL,
            two_factor_enabled_at = NULL;

        # Step 2: Login to get JWT token
        curl -X POST http://localhost:8000/api/v1/auth/login \
             -H "Content-Type: application/json" \
             -d '{"email": "test2fa@taxasge.com", "password": "Test2FA@Password123!"}'

        # Step 3: Update VALID_JWT_TOKEN in test code

        # Step 4: Run test
        pytest tests/integration/test_two_factor_endpoints.py::TestTwoFactorWorkflowE2E::test_complete_2fa_workflow -v -s
        """
        global VALID_JWT_TOKEN

        # REPLACE WITH YOUR VALID JWT TOKEN
        VALID_JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.YOUR_TOKEN_HERE"

        headers = {"Authorization": f"Bearer {VALID_JWT_TOKEN}"}

        # Step 1: Check initial status (should be disabled)
        response = await client.get("/api/v1/auth/2fa/status", headers=headers)
        assert response.status_code == 200
        status_data = response.json()
        assert status_data["two_factor_enabled"] is False

        # Step 2: Enable 2FA
        response = await client.post("/api/v1/auth/2fa/enable", headers=headers)
        assert response.status_code == 200
        enable_data = response.json()

        secret = enable_data["secret"]
        backup_codes = enable_data["backup_codes"]

        # Step 3: Generate valid TOTP code
        totp = pyotp.TOTP(secret)
        valid_code = totp.now()

        # Step 4: Verify and enable 2FA
        verify_payload = {
            "secret": secret,
            "code": valid_code,
            "backup_codes": backup_codes
        }
        response = await client.post("/api/v1/auth/2fa/verify", headers=headers, json=verify_payload)
        assert response.status_code == 200
        verify_data = response.json()
        assert verify_data["two_factor_enabled"] is True

        # Step 5: Check status (should be enabled now)
        response = await client.get("/api/v1/auth/2fa/status", headers=headers)
        assert response.status_code == 200
        status_data = response.json()
        assert status_data["two_factor_enabled"] is True
        assert status_data["backup_codes_remaining"] == 10

        # Step 6: Disable 2FA
        disable_payload = {"password": TEST_USER_PASSWORD}
        response = await client.post("/api/v1/auth/2fa/disable", headers=headers, json=disable_payload)
        assert response.status_code == 200
        disable_data = response.json()
        assert disable_data["two_factor_enabled"] is False

        # Step 7: Check final status (should be disabled)
        response = await client.get("/api/v1/auth/2fa/status", headers=headers)
        assert response.status_code == 200
        status_data = response.json()
        assert status_data["two_factor_enabled"] is False
        assert status_data["backup_codes_remaining"] is None


# ============================================================================
# SETUP GUIDE FOR RUNNING INTEGRATION TESTS
# ============================================================================
"""
These tests require a real Supabase user and valid JWT token.
Follow this guide to set up and run the tests:

## Prerequisites

1. Supabase project running
2. Backend API running on http://localhost:8000
3. 2FA migration script executed (add_2fa_fields.sql)

## Step-by-Step Setup

### 1. Create Test User

Run this SQL in Supabase SQL Editor:

```sql
-- Generate bcrypt hash for password
-- In Python: from passlib.hash import bcrypt; print(bcrypt.hash("Test2FA@Password123!"))

INSERT INTO users (
    email,
    password_hash,
    role,
    status,
    first_name,
    last_name,
    two_factor_enabled,
    email_verified,
    phone,
    address,
    city,
    language
)
VALUES (
    'test2fa@taxasge.com',
    '$2b$12$YOUR_BCRYPT_HASH_HERE',  -- Replace with actual hash
    'citizen',
    'active',
    'Test',
    '2FA',
    FALSE,
    TRUE,
    '+240222000000',
    'Test Address',
    'Malabo',
    'es'
)
ON CONFLICT (email) DO UPDATE SET
    two_factor_enabled = FALSE,
    two_factor_secret = NULL,
    two_factor_backup_codes = NULL,
    two_factor_enabled_at = NULL;
```

### 2. Generate Bcrypt Hash

```python
# In Python terminal or script
from passlib.hash import bcrypt
password_hash = bcrypt.hash("Test2FA@Password123!")
print(password_hash)
# Copy output and replace in SQL above
```

### 3. Get JWT Token

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
     -H "Content-Type: application/json" \
     -d '{
       "email": "test2fa@taxasge.com",
       "password": "Test2FA@Password123!"
     }'
```

Copy the `access_token` from response.

### 4. Update Test Code

In this file, update `VALID_JWT_TOKEN` with your token:

```python
VALID_JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.YOUR_ACTUAL_TOKEN_HERE"
```

### 5. Run Tests

```bash
# Run all 2FA integration tests
pytest tests/integration/test_two_factor_endpoints.py -v

# Run specific test
pytest tests/integration/test_two_factor_endpoints.py::TestTwoFactorEnableEndpoint::test_enable_2fa_success -v

# Run E2E workflow test
pytest tests/integration/test_two_factor_endpoints.py::TestTwoFactorWorkflowE2E::test_complete_2fa_workflow -v -s
```

### 6. Uncomment Tests

Once you have a valid JWT token, uncomment the `@pytest.mark.skip` decorators
for the tests you want to run.

## Test Coverage Summary

- **POST /auth/2fa/enable**: 4 tests (success, unauthenticated, invalid token, already enabled)
- **POST /auth/2fa/verify**: 4 tests (valid code, invalid code, unauthenticated, invalid format)
- **POST /auth/2fa/disable**: 4 tests (success, wrong password, unauthenticated, not enabled)
- **GET /auth/2fa/status**: 3 tests (enabled, unauthenticated, invalid token)
- **E2E Workflow**: 1 test (complete enable → verify → disable flow)

**Total**: 16 integration tests

## Troubleshooting

**Issue**: 401 Unauthorized
- Check JWT token is valid (not expired)
- Verify token is correctly formatted in Authorization header

**Issue**: 404 Not Found
- Ensure backend is running on http://localhost:8000
- Verify 2FA router is loaded (check backend logs)

**Issue**: 500 Internal Server Error
- Check Supabase connection
- Verify 2FA migration script was executed
- Check backend logs for detailed error

**Issue**: Test user not found
- Verify user was created in Supabase
- Check email matches TEST_USER_EMAIL constant
"""
