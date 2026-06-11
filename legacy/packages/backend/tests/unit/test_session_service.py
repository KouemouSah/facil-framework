"""
Unit tests for SessionService (TASK-M01-008)
Tests for session management business logic

COVERAGE:
- get_active_sessions() - Business rules testing
- revoke_session() - Security checks and authorization
- revoke_all_sessions() - Batch operations
- Helper methods - Device/browser extraction
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.modules.auth.services.session_service import SessionService
from app.modules.auth.models.auth_models import SessionResponse, SessionStatus


@pytest.fixture
def mock_session_repo():
    """Fixture: Mock session repository"""
    return AsyncMock()


@pytest.fixture
def session_service(mock_session_repo):
    """Fixture: SessionService with mocked repository"""
    return SessionService(session_repo=mock_session_repo)


@pytest.fixture
def mock_sessions():
    """Fixture: Mock list of sessions"""
    user_id = str(uuid4())
    now = datetime.utcnow()

    return [
        SessionResponse(
            id=str(uuid4()),
            user_id=user_id,
            access_token="token_123",
            status=SessionStatus.active,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
            created_at=now - timedelta(hours=2),
            last_activity=now - timedelta(minutes=5),
            expires_at=now + timedelta(hours=1),
        ),
        SessionResponse(
            id=str(uuid4()),
            user_id=user_id,
            access_token="token_456",
            status=SessionStatus.active,
            ip_address="192.168.1.2",
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) Mobile/Safari",
            created_at=now - timedelta(days=1),
            last_activity=now - timedelta(hours=1),
            expires_at=now + timedelta(days=6),
        ),
        # Expired session (should be filtered out)
        SessionResponse(
            id=str(uuid4()),
            user_id=user_id,
            access_token="token_789",
            status=SessionStatus.active,
            ip_address="192.168.1.3",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/120.0",
            created_at=now - timedelta(days=2),
            last_activity=now - timedelta(days=2),
            expires_at=now - timedelta(hours=1),  # EXPIRED
        ),
    ]


class TestGetActiveSessions:
    """Unit tests for get_active_sessions() method"""

    @pytest.mark.asyncio
    async def test_get_active_sessions_filters_expired(
        self, session_service, mock_session_repo, mock_sessions
    ):
        """Test: Expired sessions are filtered out (Business Rule 1)"""
        user_id = mock_sessions[0].user_id
        mock_session_repo.find_user_sessions.return_value = mock_sessions

        result = await session_service.get_active_sessions(user_id=user_id)

        # Should return only 2 non-expired sessions (not 3)
        assert len(result) == 2
        assert all(session["expires_at"] > datetime.utcnow() for session in result)

    @pytest.mark.asyncio
    async def test_get_active_sessions_marks_current(
        self, session_service, mock_session_repo, mock_sessions
    ):
        """Test: Current session is marked correctly (Business Rule 2)"""
        user_id = mock_sessions[0].user_id
        current_token = "current_access_token_123"

        # Set one session as current
        mock_sessions[0].access_token = current_token
        mock_sessions[1].access_token = "other_token_456"
        mock_session_repo.find_user_sessions.return_value = mock_sessions[:2]  # Exclude expired

        result = await session_service.get_active_sessions(
            user_id=user_id,
            current_token=current_token
        )

        # First session should be marked as current
        assert result[0]["is_current"] is True
        assert result[1]["is_current"] is False

    @pytest.mark.asyncio
    async def test_get_active_sessions_enriches_metadata(
        self, session_service, mock_session_repo, mock_sessions
    ):
        """Test: Sessions are enriched with device/browser/location metadata"""
        user_id = mock_sessions[0].user_id
        mock_session_repo.find_user_sessions.return_value = mock_sessions[:2]  # Exclude expired

        result = await session_service.get_active_sessions(user_id=user_id)

        # Check enrichment fields exist
        for session in result:
            assert "device" in session
            assert "browser" in session
            assert "location" in session

        # Verify specific enrichments
        assert result[0]["device"] == "Desktop"
        assert result[0]["browser"] == "Chrome"
        assert result[1]["device"] == "Mobile"
        assert result[1]["browser"] == "Safari"

    @pytest.mark.asyncio
    async def test_get_active_sessions_empty_list(
        self, session_service, mock_session_repo
    ):
        """Test: Returns empty list when no active sessions"""
        user_id = str(uuid4())
        mock_session_repo.find_user_sessions.return_value = []

        result = await session_service.get_active_sessions(user_id=user_id)

        assert result == []
        assert isinstance(result, list)


class TestRevokeSession:
    """Unit tests for revoke_session() method"""

    @pytest.mark.asyncio
    async def test_revoke_session_success(
        self, session_service, mock_session_repo, mock_sessions
    ):
        """Test: Successfully revoke a session"""
        session = mock_sessions[0]
        user_id = session.user_id

        # Mock find_by_id and revoke_session
        session_dict = session.dict()
        session_dict["access_token"] = "token_123"
        mock_session = MagicMock(**session_dict)
        mock_session_repo.find_by_id.return_value = mock_session
        mock_session_repo.revoke_session.return_value = True

        result = await session_service.revoke_session(
            session_id=session.id,
            user_id=user_id
        )

        assert result is True
        mock_session_repo.revoke_session.assert_called_once_with(session.id)

    @pytest.mark.asyncio
    async def test_revoke_session_security_check(
        self, session_service, mock_session_repo, mock_sessions
    ):
        """Test: Security check - cannot revoke other user's session (Business Rule 1)"""
        session = mock_sessions[0]
        wrong_user_id = str(uuid4())  # Different user

        # Mock session belonging to different user
        session_dict = session.dict()
        session_dict["access_token"] = "token_123"
        mock_session = MagicMock(**session_dict)
        mock_session_repo.find_by_id.return_value = mock_session

        with pytest.raises(PermissionError) as exc_info:
            await session_service.revoke_session(
                session_id=session.id,
                user_id=wrong_user_id
            )

        assert "only revoke your own sessions" in str(exc_info.value).lower()
        mock_session_repo.revoke_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_revoke_session_not_found(
        self, session_service, mock_session_repo
    ):
        """Test: Raises ValueError when session not found"""
        session_id = str(uuid4())
        user_id = str(uuid4())

        mock_session_repo.find_by_id.return_value = None

        with pytest.raises(ValueError) as exc_info:
            await session_service.revoke_session(
                session_id=session_id,
                user_id=user_id
            )

        assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_revoke_session_idempotent(
        self, session_service, mock_session_repo, mock_sessions
    ):
        """Test: Revoking already revoked session is idempotent (Business Rule 2)"""
        session = mock_sessions[0]
        user_id = session.user_id

        # Mock already revoked session
        session_dict = session.dict()
        session_dict["access_token"] = "token_123"
        session_dict["status"] = SessionStatus.revoked
        mock_session = MagicMock(**session_dict)
        mock_session_repo.find_by_id.return_value = mock_session

        result = await session_service.revoke_session(
            session_id=session.id,
            user_id=user_id
        )

        # Should return True without calling revoke_session
        assert result is True
        mock_session_repo.revoke_session.assert_not_called()


class TestRevokeAllSessions:
    """Unit tests for revoke_all_sessions() method"""

    @pytest.mark.asyncio
    async def test_revoke_all_sessions_except_current(
        self, session_service, mock_session_repo, mock_sessions
    ):
        """Test: Revoke all sessions except current (Business Rule 1)"""
        user_id = mock_sessions[0].user_id
        current_token = "current_token_123"

        # Set access tokens
        mock_sessions[0].access_token = current_token  # Current
        mock_sessions[1].access_token = "other_token_456"

        mock_session_repo.find_user_sessions.return_value = mock_sessions[:2]
        mock_session_repo.revoke_session.return_value = True

        count = await session_service.revoke_all_sessions(
            user_id=user_id,
            except_current=True,
            current_token=current_token
        )

        # Should revoke only 1 session (not the current one)
        assert count == 1
        mock_session_repo.revoke_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_revoke_all_sessions_including_current(
        self, session_service, mock_session_repo, mock_sessions
    ):
        """Test: Revoke all sessions including current"""
        user_id = mock_sessions[0].user_id

        mock_session_repo.find_user_sessions.return_value = mock_sessions[:2]
        mock_session_repo.revoke_session.return_value = True

        count = await session_service.revoke_all_sessions(
            user_id=user_id,
            except_current=False
        )

        # Should revoke both sessions
        assert count == 2
        assert mock_session_repo.revoke_session.call_count == 2

    @pytest.mark.asyncio
    async def test_revoke_all_sessions_requires_token(
        self, session_service, mock_session_repo
    ):
        """Test: Raises ValueError if except_current=True but no current_token"""
        user_id = str(uuid4())

        with pytest.raises(ValueError) as exc_info:
            await session_service.revoke_all_sessions(
                user_id=user_id,
                except_current=True,
                current_token=None  # Missing token
            )

        assert "current_token required" in str(exc_info.value).lower()


class TestHelperMethods:
    """Unit tests for private helper methods"""

    def test_extract_device_desktop(self, session_service):
        """Test: Extract Desktop device type"""
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
        result = session_service._extract_device(user_agent)
        assert result == "Desktop"

    def test_extract_device_mobile(self, session_service):
        """Test: Extract Mobile device type"""
        user_agent = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) Mobile/Safari"
        result = session_service._extract_device(user_agent)
        assert result == "Mobile"

    def test_extract_device_tablet(self, session_service):
        """Test: Extract Tablet device type"""
        user_agent = "Mozilla/5.0 (iPad; CPU OS 16_0 like Mac OS X) AppleWebKit/605.1.15"
        result = session_service._extract_device(user_agent)
        assert result == "Tablet"

    def test_extract_device_unknown(self, session_service):
        """Test: Unknown device when user_agent is None"""
        result = session_service._extract_device(None)
        assert result == "Unknown"

    def test_extract_browser_chrome(self, session_service):
        """Test: Extract Chrome browser"""
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
        result = session_service._extract_browser(user_agent)
        assert result == "Chrome"

    def test_extract_browser_firefox(self, session_service):
        """Test: Extract Firefox browser"""
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0"
        result = session_service._extract_browser(user_agent)
        assert result == "Firefox"

    def test_extract_browser_safari(self, session_service):
        """Test: Extract Safari browser"""
        user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15"
        result = session_service._extract_browser(user_agent)
        assert result == "Safari"

    def test_extract_browser_edge(self, session_service):
        """Test: Extract Edge browser"""
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Edg/120.0.0.0"
        result = session_service._extract_browser(user_agent)
        assert result == "Edge"

    def test_get_location_placeholder(self, session_service):
        """Test: Location returns IP (placeholder for geolocation)"""
        ip_address = "192.168.1.1"
        result = session_service._get_location(ip_address)
        assert result == ip_address

    def test_get_location_none(self, session_service):
        """Test: Location returns Unknown when IP is None"""
        result = session_service._get_location(None)
        assert result == "Unknown"


class TestSessionStats:
    """Unit tests for get_session_stats() method"""

    @pytest.mark.asyncio
    async def test_get_session_stats(
        self, session_service, mock_session_repo
    ):
        """Test: Get session statistics for user"""
        user_id = str(uuid4())

        mock_stats = {
            "total_sessions": 5,
            "active_sessions": 2,
            "expired_sessions": 2,
            "revoked_sessions": 1,
        }
        mock_session_repo.get_session_stats.return_value = mock_stats

        result = await session_service.get_session_stats(user_id=user_id)

        assert result == mock_stats
        mock_session_repo.get_session_stats.assert_called_once_with(user_id=user_id)


class TestCleanupExpiredSessions:
    """Unit tests for cleanup_expired_sessions() method"""

    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions(
        self, session_service, mock_session_repo
    ):
        """Test: Cleanup expired sessions (admin/cron task)"""
        mock_session_repo.cleanup_expired_sessions.return_value = 5

        result = await session_service.cleanup_expired_sessions()

        assert result == 5
        mock_session_repo.cleanup_expired_sessions.assert_called_once()
