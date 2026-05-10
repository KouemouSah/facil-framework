"""
Session Service for TaxasGE Backend
Business logic for session management
TASK-M01-008: Sessions management implementation
"""

from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from loguru import logger

from app.modules.auth.repositories.session_repository import get_session_repository, SessionRepository
from app.modules.auth.models.auth_models import SessionResponse, SessionStatus


class SessionService:
    """
    Service for session management business logic

    **Source**: .github/docs-internal/Documentations/Backend/RAPPORT_MODULE_01_AUTHENTICATION.md
    **Architecture**: 3-tier (Routes → Services → Repositories)
    """

    def __init__(self, session_repo: Optional[SessionRepository] = None):
        """
        Initialize session service with repository

        Args:
            session_repo: Optional session repository (for testing/DI)
        """
        self.session_repo = session_repo or get_session_repository()
        logger.info("SessionService initialized")

    async def get_active_sessions(
        self,
        user_id: str,
        current_token: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all active sessions for a user with enriched information

        **Business Rules**:
        1. Return only non-expired sessions (expires_at > now)
        2. Mark current session (matching access_token)
        3. Verify user owns all returned sessions (security check)
        4. Order by created_at desc (most recent first)

        **Source**: RAPPORT_MODULE_01_AUTHENTICATION.md line 414-417

        Args:
            user_id: User ID to get sessions for
            current_token: Optional current access token to mark current session

        Returns:
            List[Dict]: List of active sessions with metadata

        Raises:
            Exception: If database query fails
        """
        try:
            # Get active sessions from repository
            sessions = await self.session_repo.find_user_sessions(
                user_id=user_id,
                active_only=True
            )

            # Filter out expired sessions (business rule 1)
            now = datetime.now(timezone.utc)
            active_sessions = []

            for session in sessions:
                # Check expiration
                if session.expires_at > now:
                    # Convert to enriched dict
                    session_dict = session.dict()

                    # Mark current session (business rule 2)
                    session_dict["is_current"] = (
                        current_token is not None and
                        session.access_token == current_token
                    )

                    # Add human-readable device info
                    session_dict["device"] = self._extract_device(session.user_agent)
                    session_dict["browser"] = self._extract_browser(session.user_agent)
                    session_dict["location"] = await self._get_location(session.ip_address)

                    active_sessions.append(session_dict)

            logger.info(f"Retrieved {len(active_sessions)} active sessions for user {user_id}")
            return active_sessions

        except Exception as e:
            logger.error(f"Error getting active sessions for user {user_id}: {str(e)}")
            raise Exception(f"Failed to retrieve sessions: {str(e)}")

    async def revoke_session(
        self,
        session_id: str,
        user_id: str
    ) -> bool:
        """
        Revoke a specific session

        **Business Rules**:
        1. Verify session belongs to user (security check)
        2. Revoke only if active (idempotent)
        3. Update revoked_at timestamp

        **Source**: RAPPORT_MODULE_01_AUTHENTICATION.md line 414-417

        Args:
            session_id: Session ID to revoke
            user_id: User ID making the request (for security check)

        Returns:
            bool: True if revoked successfully

        Raises:
            PermissionError: If session doesn't belong to user
            ValueError: If session not found
        """
        try:
            # Verify session exists and belongs to user (business rule 1)
            session = await self.session_repo.find_by_id(session_id)

            if not session:
                raise ValueError(f"Session {session_id} not found")

            if session.user_id != user_id:
                logger.warning(
                    f"User {user_id} attempted to revoke session {session_id} "
                    f"belonging to user {session.user_id}"
                )
                raise PermissionError("You can only revoke your own sessions")

            # Revoke only if active (business rule 2)
            if session.status != SessionStatus.active:
                logger.info(f"Session {session_id} already revoked/expired")
                return True  # Idempotent

            # Revoke session
            success = await self.session_repo.revoke_session(session_id)

            if success:
                logger.info(f"Session {session_id} revoked by user {user_id}")

            return success

        except (ValueError, PermissionError):
            raise
        except Exception as e:
            logger.error(f"Error revoking session {session_id}: {str(e)}")
            raise Exception(f"Failed to revoke session: {str(e)}")

    async def revoke_all_sessions(
        self,
        user_id: str,
        except_current: bool = True,
        current_token: Optional[str] = None
    ) -> int:
        """
        Revoke all sessions for a user (except optionally current)

        **Business Rules**:
        1. If except_current=True, keep current session active
        2. Revoke all other active sessions
        3. Return count of revoked sessions

        **Use case**: User clicks "Logout all devices" or password change

        **Source**: RAPPORT_MODULE_01_AUTHENTICATION.md line 414-417

        Args:
            user_id: User ID to revoke sessions for
            except_current: Keep current session active if True
            current_token: Current access token (required if except_current=True)

        Returns:
            int: Number of sessions revoked

        Raises:
            ValueError: If except_current=True but current_token not provided
        """
        try:
            if except_current and not current_token:
                raise ValueError("current_token required when except_current=True")

            # Get all active sessions
            sessions = await self.session_repo.find_user_sessions(
                user_id=user_id,
                active_only=True
            )

            revoked_count = 0

            for session in sessions:
                # Skip current session if requested (business rule 1)
                if except_current and session.access_token == current_token:
                    logger.debug(f"Keeping current session {session.id} active")
                    continue

                # Revoke session
                success = await self.session_repo.revoke_session(session.id)
                if success:
                    revoked_count += 1

            logger.info(
                f"Revoked {revoked_count} sessions for user {user_id} "
                f"(except_current={except_current})"
            )

            return revoked_count

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error revoking all sessions for user {user_id}: {str(e)}")
            raise Exception(f"Failed to revoke sessions: {str(e)}")

    async def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions (admin/cron task)

        **Business Rule**: Mark sessions as expired if expires_at < now

        **Use case**: Scheduled task to keep database clean

        Returns:
            int: Number of sessions cleaned up
        """
        try:
            count = await self.session_repo.cleanup_expired_sessions()
            logger.info(f"Cleaned up {count} expired sessions")
            return count

        except Exception as e:
            logger.error(f"Error cleaning up expired sessions: {str(e)}")
            return 0

    async def get_session_stats(self, user_id: str) -> Dict[str, Any]:
        """
        Get session statistics for a user

        Args:
            user_id: User ID

        Returns:
            Dict: Session statistics (total, active, expired, revoked)
        """
        try:
            stats = await self.session_repo.get_session_stats(user_id=user_id)
            logger.debug(f"Session stats for user {user_id}: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Error getting session stats: {str(e)}")
            return {
                "total_sessions": 0,
                "active_sessions": 0,
                "expired_sessions": 0,
                "revoked_sessions": 0,
            }

    # Private helper methods for enriching session data

    def _extract_device(self, user_agent: Optional[str]) -> str:
        """
        Extract device type from user agent string

        Args:
            user_agent: User agent string

        Returns:
            str: Device type (Mobile, Desktop, Tablet, Unknown)
        """
        if not user_agent:
            return "Unknown"

        user_agent_lower = user_agent.lower()

        if "mobile" in user_agent_lower or "android" in user_agent_lower or "iphone" in user_agent_lower:
            return "Mobile"
        elif "tablet" in user_agent_lower or "ipad" in user_agent_lower:
            return "Tablet"
        else:
            return "Desktop"

    def _extract_browser(self, user_agent: Optional[str]) -> str:
        """
        Extract browser name from user agent string

        Args:
            user_agent: User agent string

        Returns:
            str: Browser name (Chrome, Firefox, Safari, Edge, Unknown)
        """
        if not user_agent:
            return "Unknown"

        user_agent_lower = user_agent.lower()

        if "chrome" in user_agent_lower and "edg" not in user_agent_lower:
            return "Chrome"
        elif "firefox" in user_agent_lower:
            return "Firefox"
        elif "safari" in user_agent_lower and "chrome" not in user_agent_lower:
            return "Safari"
        elif "edg" in user_agent_lower:
            return "Edge"
        else:
            return "Unknown"

    async def _get_location(self, ip_address: Optional[str]) -> str:
        """
        Get location from IP address via ip-api.com (free, no key needed).
        Results cached in-memory for 1 hour to stay within rate limits (45 req/min).
        Falls back to raw IP on failure.
        """
        if not ip_address:
            return "Unknown"

        # Skip private/internal IPs (can't geolocate)
        private_prefixes = ("127.", "10.", "172.16.", "172.17.", "172.18.", "172.19.",
                            "172.20.", "172.21.", "172.22.", "172.23.", "172.24.",
                            "172.25.", "172.26.", "172.27.", "172.28.", "172.29.",
                            "172.30.", "172.31.", "192.168.", "169.254.", "::1", "fc", "fd")
        if any(ip_address.startswith(p) for p in private_prefixes):
            return f"Red interna ({ip_address})"

        # Check in-memory cache
        cache_key = f"geo:{ip_address}"
        try:
            from app.core.cache import get_cache
            cache = get_cache()
            cached = await cache.get(cache_key)
            if cached:
                return cached
        except Exception:
            pass

        # Query ip-api.com (free tier, no API key, HTTP only)
        try:
            import httpx
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"http://ip-api.com/json/{ip_address}?fields=city,country,status")
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("status") == "success":
                        location = f"{data.get('city', '')}, {data.get('country', '')}".strip(", ")
                        if location:
                            # Cache for 1 hour
                            try:
                                await cache.set(cache_key, location, ttl=3600)
                            except Exception:
                                pass
                            return location
        except Exception:
            pass  # Timeout or network error — use raw IP

        return ip_address


# Singleton instance
_session_service_instance: Optional[SessionService] = None


def get_session_service() -> SessionService:
    """
    Get session service singleton instance

    Returns:
        SessionService: Session service instance
    """
    global _session_service_instance

    if _session_service_instance is None:
        _session_service_instance = SessionService()

    return _session_service_instance
