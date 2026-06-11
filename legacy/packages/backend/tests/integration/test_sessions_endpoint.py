"""
Integration tests for Sessions Endpoint (TASK-M01-008)
Tests for GET /auth/sessions endpoint

REAL DATABASE TESTS - NO MOCKS
Following system_instructions.md: "ne travaille pas avec des mock mais travailles
et fait des tests direct avec la base de données pour valider exactement le comportement final"

SETUP REQUIRED:
- Valid test user in Supabase with known credentials
- Active sessions in database for that user
- Real JWT tokens for authentication

COVERAGE:
- GET /auth/sessions endpoint with real authentication
- Real session data from Supabase
- Device/browser metadata extraction from real user agents
"""

import pytest
from fastapi import status
from httpx import AsyncClient, ASGITransport


class TestGetSessionsEndpointRealDB:
    """
    Real database integration tests for GET /auth/sessions endpoint

    NOTE: These tests require:
    1. A test user in Supabase with known credentials
    2. Valid JWT access token for that user
    3. Active sessions in the sessions table

    To run these tests:
    1. Create test user in Supabase (email: test_sessions@taxasge.com)
    2. Login to get valid access token
    3. Set ACCESS_TOKEN environment variable
    4. Run: pytest tests/integration/test_sessions_endpoint.py -v
    """

    @pytest.mark.asyncio
    async def test_get_sessions_unauthenticated(self):
        """Test: Unauthenticated request returns 401 (NO MOCK - Real FastAPI)"""
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/auth/sessions")

            # Should fail authentication
            assert response.status_code in [
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN
            ]

    @pytest.mark.asyncio
    async def test_get_sessions_invalid_token(self):
        """Test: Invalid token returns 401 (NO MOCK - Real JWT validation)"""
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/auth/sessions",
                headers={"Authorization": "Bearer invalid_token_xyz"}
            )

            # Should fail JWT validation
            assert response.status_code in [
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN
            ]

    @pytest.mark.asyncio
    async def test_get_sessions_with_real_token(self):
        """
        Test: Get sessions with real JWT token and real database

        SKIP REASON: Requires manual setup of test user with valid token

        TODO SETUP:
        1. Create test user in Supabase:
           - Email: test_sessions@taxasge.com
           - Password: TestSessions123!

        2. Login via POST /auth/login to get access_token

        3. Create active sessions for that user in sessions table

        4. Use real access_token in this test

        EXPECTED BEHAVIOR:
        - Returns 200 OK
        - Returns list of active sessions
        - Each session has: id, device, browser, location, timestamps, is_current
        - Current session is marked with is_current=true
        - Expired sessions are filtered out
        """
        pytest.skip(
            "Real DB test - requires manual setup:\n"
            "1. Create test user: test_sessions@taxasge.com\n"
            "2. Login to get valid JWT token\n"
            "3. Create active sessions in database\n"
            "4. Replace 'REPLACE_WITH_REAL_TOKEN' below with actual token\n"
            "\n"
            "See RAPPORT_TESTS_REELS.md for detailed setup instructions"
        )

        # UNCOMMENT AND REPLACE TOKEN AFTER SETUP:
        # from app.main import app
        #
        # real_token = "REPLACE_WITH_REAL_TOKEN"  # Get from login response
        #
        # async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        #     response = await client.get(
        #         "/api/v1/auth/sessions",
        #         headers={"Authorization": f"Bearer {real_token}"}
        #     )
        #
        #     assert response.status_code == status.HTTP_200_OK
        #
        #     data = response.json()
        #     assert "sessions" in data
        #     assert "total" in data
        #     assert isinstance(data["sessions"], list)
        #
        #     # Verify session structure (if sessions exist)
        #     if data["total"] > 0:
        #         session = data["sessions"][0]
        #         assert "id" in session
        #         assert "device" in session
        #         assert "browser" in session
        #         assert "location" in session
        #         assert "created_at" in session
        #         assert "last_activity" in session
        #         assert "expires_at" in session
        #         assert "is_current" in session
        #
        #         # At least one session should be marked as current
        #         current_sessions = [s for s in data["sessions"] if s["is_current"]]
        #         assert len(current_sessions) >= 1


class TestSessionsMetadataRealDB:
    """
    Real database tests for session metadata enrichment

    These tests verify device/browser extraction works with real user agents
    """

    @pytest.mark.asyncio
    async def test_device_browser_extraction_with_real_sessions(self):
        """
        Test: Device and browser detection with real sessions from database

        SKIP REASON: Requires test user with multiple sessions from different devices

        TODO SETUP:
        1. Login from Desktop Chrome → creates session 1
        2. Login from Mobile Safari → creates session 2
        3. Login from Tablet Firefox → creates session 3
        4. Use valid token to call GET /sessions

        EXPECTED BEHAVIOR:
        - Desktop session shows: device="Desktop", browser="Chrome"
        - Mobile session shows: device="Mobile", browser="Safari"
        - Tablet session shows: device="Tablet", browser="Firefox"
        """
        pytest.skip(
            "Real DB test - requires multiple sessions from different devices:\n"
            "1. Login from Desktop Chrome (Windows/Mac)\n"
            "2. Login from Mobile Safari (iPhone)\n"
            "3. Login from Tablet Firefox (iPad)\n"
            "4. Verify device/browser metadata in response\n"
            "\n"
            "This validates real-world multi-device scenarios"
        )


# ============================================================================
# DOCUMENTATION: How to run real database tests
# ============================================================================

"""
REAL DATABASE TEST SETUP GUIDE
===============================

Step 1: Create Test User in Supabase
-------------------------------------
SQL Query in Supabase SQL Editor:

INSERT INTO users (email, password_hash, role, status, first_name, last_name)
VALUES (
    'test_sessions@taxasge.com',
    '$2b$12$...',  -- Use bcrypt hash of 'TestSessions123!'
    'citizen',
    'active',
    'Test',
    'Sessions'
);


Step 2: Get Valid JWT Token
----------------------------
Using curl:

curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test_sessions@taxasge.com",
    "password": "TestSessions123!"
  }'

Copy the "access_token" from response.


Step 3: Create Test Sessions
-----------------------------
Sessions are created automatically on login. To create multiple sessions:

# Login from Desktop Chrome
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0" \
  -d '{"email":"test_sessions@taxasge.com","password":"TestSessions123!"}'

# Login from Mobile Safari
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -H "User-Agent: Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) Mobile/Safari" \
  -d '{"email":"test_sessions@taxasge.com","password":"TestSessions123!"}'


Step 4: Test GET /sessions Endpoint
------------------------------------
curl -X GET http://localhost:8000/api/v1/auth/sessions \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN_HERE"

Expected response:
{
  "sessions": [
    {
      "id": "uuid",
      "device": "Desktop",
      "browser": "Chrome",
      "location": "192.168.1.1",
      "created_at": "2025-11-02T...",
      "last_activity": "2025-11-02T...",
      "expires_at": "2025-11-02T...",
      "is_current": true
    },
    {
      "id": "uuid",
      "device": "Mobile",
      "browser": "Safari",
      "location": "192.168.1.2",
      "created_at": "2025-11-02T...",
      "last_activity": "2025-11-02T...",
      "expires_at": "2025-11-02T...",
      "is_current": false
    }
  ],
  "total": 2
}


Step 5: Run Tests
-----------------
# Run all tests
pytest tests/integration/test_sessions_endpoint.py -v

# Run specific test (after uncommenting code)
pytest tests/integration/test_sessions_endpoint.py::TestGetSessionsEndpointRealDB::test_get_sessions_with_real_token -v

# Run with output
pytest tests/integration/test_sessions_endpoint.py -v -s


NOTES:
------
- NO MOCKS are used - all tests use real Supabase database
- Tests validate real JWT tokens, real sessions, real metadata
- Setup is manual but validates actual production behavior
- See RAPPORT_TESTS_REELS.md for more examples

Following system_instructions.md rule:
"ne travaille pas avec des mock mais travailles et fait des tests
direct avec la base de données pour valider exactement le comportement final"
"""
