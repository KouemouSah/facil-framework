"""
Session Repository for TaxasGE Backend
Handles session data access and management using PostgreSQL direct
"""

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from loguru import logger
import uuid
import asyncpg

from app.database.connection import db_manager
from app.modules.auth.models.auth_models import (
    Session,
    SessionCreate,
    SessionResponse,
    SessionStatus,
)


class SessionRepository:
    """Repository for session data access using PostgreSQL"""

    def __init__(self):
        """Initialize session repository"""
        self.db_manager = db_manager
        self.table = "sessions"

    @staticmethod
    def _hash_token(token: str) -> str:
        """Hash a token with SHA256 for secure storage (same pattern as refresh tokens)"""
        return hashlib.sha256(token.encode()).hexdigest()

    def _row_to_session(self, row: asyncpg.Record) -> Session:
        """
        Convert asyncpg Record to Session model.
        Handles UUID and IPv4Address conversion to strings.
        """
        data = dict(row)
        # Convert UUID fields to strings
        if 'id' in data and data['id'] is not None:
            data['id'] = str(data['id'])
        if 'user_id' in data and data['user_id'] is not None:
            data['user_id'] = str(data['user_id'])
        # Convert IPv4Address to string
        if 'ip_address' in data and data['ip_address'] is not None:
            data['ip_address'] = str(data['ip_address'])
        return Session(**data)

    def _row_to_session_response(self, row: asyncpg.Record) -> SessionResponse:
        """
        Convert asyncpg Record to SessionResponse model.
        Handles UUID and IPv4Address conversion to strings.
        """
        data = dict(row)
        # Convert UUID fields to strings
        if 'id' in data and data['id'] is not None:
            data['id'] = str(data['id'])
        if 'user_id' in data and data['user_id'] is not None:
            data['user_id'] = str(data['user_id'])
        # Convert IPv4Address to string
        if 'ip_address' in data and data['ip_address'] is not None:
            data['ip_address'] = str(data['ip_address'])
        return SessionResponse(**data)


    async def create_session(
        self,
        session_data: SessionCreate,
        conn: Optional[asyncpg.Connection] = None
    ) -> Session:
        """
        Create a new session

        Args:
            session_data: Session creation data
            conn: Optional database connection (if None, uses db_manager)

        Returns:
            Session: Created session

        Raises:
            Exception: If session creation fails
        """
        try:
            session_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)

            # Hash tokens before storage (never store plaintext tokens in DB)
            hashed_access = self._hash_token(session_data.access_token) if session_data.access_token else None
            hashed_refresh = self._hash_token(session_data.refresh_token) if session_data.refresh_token else None

            query = """
                INSERT INTO sessions (
                    id, user_id, access_token, refresh_token, status,
                    ip_address, user_agent, device_info, expires_at,
                    created_at, last_activity, revoked_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                RETURNING *
            """

            if conn:
                result = await conn.fetchrow(
                    query,
                    session_id,
                    session_data.user_id,
                    hashed_access,
                    hashed_refresh,
                    SessionStatus.active.value,
                    session_data.ip_address,
                    session_data.user_agent,
                    session_data.device_info,
                    session_data.expires_at,
                    now,
                    now,
                    None
                )
            else:
                result = await self.db_manager.execute_single(
                    query,
                    session_id,
                    session_data.user_id,
                    hashed_access,
                    hashed_refresh,
                    SessionStatus.active.value,
                    session_data.ip_address,
                    session_data.user_agent,
                    session_data.device_info,
                    session_data.expires_at,
                    now,
                    now,
                    None
                )

            if not result:
                raise Exception("Failed to create session")

            logger.info(f"✅ Session created: {session_id} for user {session_data.user_id}")
            return self._row_to_session(result)

        except Exception as e:
            logger.error(f"❌ Error creating session: {str(e)}")
            raise Exception(f"Failed to create session: {str(e)}")

    async def find_by_id(
        self,
        session_id: str,
        conn: Optional[asyncpg.Connection] = None
    ) -> Optional[Session]:
        """
        Find session by ID

        Args:
            session_id: Session ID
            conn: Optional database connection (if None, uses db_manager)

        Returns:
            Optional[Session]: Session if found, None otherwise
        """
        try:
            query = "SELECT * FROM sessions WHERE id = $1 LIMIT 1"

            if conn:
                result = await conn.fetchrow(query, session_id)
            else:
                result = await self.db_manager.execute_single(query, session_id)

            if result:
                return self._row_to_session(result)

            return None

        except Exception as e:
            logger.error(f"❌ Error finding session by ID: {str(e)}")
            return None

    async def find_by_access_token(
        self,
        access_token: str,
        conn: Optional[asyncpg.Connection] = None
    ) -> Optional[Session]:
        """
        Find session by access token

        Args:
            access_token: Access token
            conn: Optional database connection (if None, uses db_manager)

        Returns:
            Optional[Session]: Session if found, None otherwise
        """
        try:
            # Hash the token to match stored hash
            hashed_token = self._hash_token(access_token)

            query = """
                SELECT * FROM sessions
                WHERE access_token = $1 AND status = $2
                LIMIT 1
            """

            if conn:
                result = await conn.fetchrow(query, hashed_token, SessionStatus.active.value)
            else:
                result = await self.db_manager.execute_single(query, hashed_token, SessionStatus.active.value)

            if result:
                return self._row_to_session(result)

            # Transition: try raw token lookup for pre-migration sessions
            # When found, rehash in-place so next lookup uses hash directly
            if conn:
                result = await conn.fetchrow(query, access_token, SessionStatus.active.value)
            else:
                result = await self.db_manager.execute_single(query, access_token, SessionStatus.active.value)

            if result:
                # Rehash the legacy plaintext token in-place
                try:
                    rehash_query = "UPDATE sessions SET access_token = $1 WHERE id = $2"
                    if conn:
                        await conn.execute(rehash_query, hashed_token, result['id'])
                    else:
                        await self.db_manager.execute_command(rehash_query, hashed_token, str(result['id']))
                    logger.info(f"Rehashed legacy access_token for session {result['id']}")
                except Exception as rehash_err:
                    logger.warning(f"Failed to rehash legacy session token: {rehash_err}")
                return self._row_to_session(result)

            return None

        except Exception as e:
            logger.error(f"❌ Error finding session by access token: {str(e)}")
            return None

    async def find_by_refresh_token(
        self,
        refresh_token: str,
        conn: Optional[asyncpg.Connection] = None
    ) -> Optional[Session]:
        """
        Find session by refresh token

        Args:
            refresh_token: Refresh token
            conn: Optional database connection (if None, uses db_manager)

        Returns:
            Optional[Session]: Session if found, None otherwise
        """
        try:
            # Hash the token to match stored hash
            hashed_token = self._hash_token(refresh_token)

            query = """
                SELECT * FROM sessions
                WHERE refresh_token = $1 AND status = $2
                LIMIT 1
            """

            if conn:
                result = await conn.fetchrow(query, hashed_token, SessionStatus.active.value)
            else:
                result = await self.db_manager.execute_single(query, hashed_token, SessionStatus.active.value)

            if result:
                return self._row_to_session(result)

            # Transition: try raw token lookup for pre-migration sessions
            if conn:
                result = await conn.fetchrow(query, refresh_token, SessionStatus.active.value)
            else:
                result = await self.db_manager.execute_single(query, refresh_token, SessionStatus.active.value)

            if result:
                # Rehash the legacy plaintext token in-place
                try:
                    rehash_query = "UPDATE sessions SET refresh_token = $1 WHERE id = $2"
                    if conn:
                        await conn.execute(rehash_query, hashed_token, result['id'])
                    else:
                        await self.db_manager.execute_command(rehash_query, hashed_token, str(result['id']))
                    logger.info(f"Rehashed legacy refresh_token for session {result['id']}")
                except Exception as rehash_err:
                    logger.warning(f"Failed to rehash legacy session token: {rehash_err}")
                return self._row_to_session(result)

            return None

        except Exception as e:
            logger.error(f"❌ Error finding session by refresh token: {str(e)}")
            return None

    async def find_user_sessions(
        self,
        user_id: str,
        active_only: bool = True,
        conn: Optional[asyncpg.Connection] = None
    ) -> List[SessionResponse]:
        """
        Find all sessions for a user

        Args:
            user_id: User ID
            active_only: Return only active sessions
            conn: Optional database connection (if None, uses db_manager)

        Returns:
            List[SessionResponse]: List of user sessions
        """
        try:
            if active_only:
                query = """
                    SELECT * FROM sessions
                    WHERE user_id = $1 AND status = $2
                    ORDER BY created_at DESC
                    LIMIT 50
                """
                if conn:
                    results = await conn.fetch(query, user_id, SessionStatus.active.value)
                else:
                    results = await self.db_manager.execute_query(query, user_id, SessionStatus.active.value)
            else:
                query = """
                    SELECT * FROM sessions
                    WHERE user_id = $1
                    ORDER BY created_at DESC
                    LIMIT 50
                """
                if conn:
                    results = await conn.fetch(query, user_id)
                else:
                    results = await self.db_manager.execute_query(query, user_id)

            if results:
                return [self._row_to_session_response(session) for session in results]

            return []

        except Exception as e:
            logger.error(f"❌ Error finding user sessions: {str(e)}")
            return []

    async def update_last_activity(
        self,
        session_id: str,
        conn: Optional[asyncpg.Connection] = None
    ) -> bool:
        """
        Update session last activity timestamp

        Args:
            session_id: Session ID
            conn: Optional database connection (if None, uses db_manager)

        Returns:
            bool: True if updated successfully
        """
        try:
            query = """
                UPDATE sessions
                SET last_activity = $1
                WHERE id = $2
            """

            now = datetime.now(timezone.utc)

            if conn:
                await conn.execute(query, now, session_id)
            else:
                await self.db_manager.execute_command(query, now, session_id)

            return True

        except Exception as e:
            logger.error(f"❌ Error updating session activity: {str(e)}")
            return False

    async def revoke_session(
        self,
        session_id: str,
        conn: Optional[asyncpg.Connection] = None
    ) -> bool:
        """
        Revoke a session

        Args:
            session_id: Session ID
            conn: Optional database connection (if None, uses db_manager)

        Returns:
            bool: True if revoked successfully
        """
        try:
            now = datetime.now(timezone.utc)

            query = """
                UPDATE sessions
                SET status = $1, revoked_at = $2
                WHERE id = $3
            """

            if conn:
                result = await conn.execute(query, SessionStatus.revoked.value, now, session_id)
            else:
                result = await self.db_manager.execute_command(query, SessionStatus.revoked.value, now, session_id)

            success = "UPDATE" in result
            if success:
                logger.info(f"✅ Session revoked: {session_id}")

            return success

        except Exception as e:
            logger.error(f"❌ Error revoking session: {str(e)}")
            return False

    async def revoke_all_user_sessions(
        self,
        user_id: str,
        conn: Optional[asyncpg.Connection] = None
    ) -> int:
        """
        Revoke all active sessions for a user

        Args:
            user_id: User ID
            conn: Optional database connection (if None, uses db_manager)

        Returns:
            int: Number of sessions revoked
        """
        try:
            now = datetime.now(timezone.utc)

            query = """
                UPDATE sessions
                SET status = $1, revoked_at = $2
                WHERE user_id = $3 AND status = $4
            """

            if conn:
                result = await conn.execute(
                    query,
                    SessionStatus.revoked.value,
                    now,
                    user_id,
                    SessionStatus.active.value
                )
            else:
                result = await self.db_manager.execute_command(
                    query,
                    SessionStatus.revoked.value,
                    now,
                    user_id,
                    SessionStatus.active.value
                )

            count = int(result.split()[-1]) if result and result.startswith("UPDATE") else 0

            logger.info(f"✅ Revoked {count} sessions for user {user_id}")
            return count

        except Exception as e:
            logger.error(f"❌ Error revoking user sessions: {str(e)}")
            return 0

    async def cleanup_expired_sessions(
        self,
        conn: Optional[asyncpg.Connection] = None
    ) -> int:
        """
        Clean up expired sessions (mark as expired)

        Args:
            conn: Optional database connection (if None, uses db_manager)

        Returns:
            int: Number of sessions cleaned up
        """
        try:
            now = datetime.now(timezone.utc)

            query = """
                UPDATE sessions
                SET status = $1
                WHERE expires_at < $2 AND status = $3
            """

            if conn:
                result = await conn.execute(
                    query,
                    SessionStatus.expired.value,
                    now,
                    SessionStatus.active.value
                )
            else:
                result = await self.db_manager.execute_command(
                    query,
                    SessionStatus.expired.value,
                    now,
                    SessionStatus.active.value
                )

            count = int(result.split()[-1]) if result and result.startswith("UPDATE") else 0

            if count > 0:
                logger.info(f"✅ Cleaned up {count} expired sessions")

            return count

        except Exception as e:
            logger.error(f"❌ Error cleaning up expired sessions: {str(e)}")
            return 0

    async def delete_old_sessions(
        self,
        days: int = 30,
        conn: Optional[asyncpg.Connection] = None
    ) -> int:
        """
        Delete old revoked/expired sessions

        Args:
            days: Delete sessions older than this many days
            conn: Optional database connection (if None, uses db_manager)

        Returns:
            int: Number of sessions deleted
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

            query = """
                DELETE FROM sessions
                WHERE status IN ($1, $2) AND created_at < $3
            """

            if conn:
                result = await conn.execute(
                    query,
                    SessionStatus.expired.value,
                    SessionStatus.revoked.value,
                    cutoff_date
                )
            else:
                result = await self.db_manager.execute_command(
                    query,
                    SessionStatus.expired.value,
                    SessionStatus.revoked.value,
                    cutoff_date
                )

            count = int(result.split()[-1]) if result and result.startswith("DELETE") else 0

            if count > 0:
                logger.info(f"✅ Deleted {count} old sessions")

            return count

        except Exception as e:
            logger.error(f"❌ Error deleting old sessions: {str(e)}")
            return 0

    async def get_session_stats(
        self,
        user_id: Optional[str] = None,
        conn: Optional[asyncpg.Connection] = None
    ) -> Dict[str, Any]:
        """
        Get session statistics

        Args:
            user_id: Optional user ID to filter stats
            conn: Optional database connection (if None, uses db_manager)

        Returns:
            Dict: Session statistics
        """
        try:
            if user_id:
                query = """
                    SELECT
                        COUNT(*) as total_sessions,
                        COUNT(*) FILTER (WHERE status = $1) as active_sessions,
                        COUNT(*) FILTER (WHERE status = $2) as expired_sessions,
                        COUNT(*) FILTER (WHERE status = $3) as revoked_sessions
                    FROM sessions
                    WHERE user_id = $4
                """
                if conn:
                    result = await conn.fetchrow(
                        query,
                        SessionStatus.active.value,
                        SessionStatus.expired.value,
                        SessionStatus.revoked.value,
                        user_id
                    )
                else:
                    result = await self.db_manager.execute_single(
                        query,
                        SessionStatus.active.value,
                        SessionStatus.expired.value,
                        SessionStatus.revoked.value,
                        user_id
                    )
            else:
                query = """
                    SELECT
                        COUNT(*) as total_sessions,
                        COUNT(*) FILTER (WHERE status = $1) as active_sessions,
                        COUNT(*) FILTER (WHERE status = $2) as expired_sessions,
                        COUNT(*) FILTER (WHERE status = $3) as revoked_sessions
                    FROM sessions
                """
                if conn:
                    result = await conn.fetchrow(
                        query,
                        SessionStatus.active.value,
                        SessionStatus.expired.value,
                        SessionStatus.revoked.value
                    )
                else:
                    result = await self.db_manager.execute_single(
                        query,
                        SessionStatus.active.value,
                        SessionStatus.expired.value,
                        SessionStatus.revoked.value
                    )

            if result:
                return {
                    "total_sessions": result["total_sessions"] or 0,
                    "active_sessions": result["active_sessions"] or 0,
                    "expired_sessions": result["expired_sessions"] or 0,
                    "revoked_sessions": result["revoked_sessions"] or 0,
                }

            return {
                "total_sessions": 0,
                "active_sessions": 0,
                "expired_sessions": 0,
                "revoked_sessions": 0,
            }

        except Exception as e:
            logger.error(f"❌ Error getting session stats: {str(e)}")
            return {
                "total_sessions": 0,
                "active_sessions": 0,
                "expired_sessions": 0,
                "revoked_sessions": 0,
            }


# Singleton instance
_session_repository_instance: Optional[SessionRepository] = None


def get_session_repository() -> SessionRepository:
    """
    Get session repository singleton instance

    Returns:
        SessionRepository: Session repository instance
    """
    global _session_repository_instance

    if _session_repository_instance is None:
        _session_repository_instance = SessionRepository()

    return _session_repository_instance
