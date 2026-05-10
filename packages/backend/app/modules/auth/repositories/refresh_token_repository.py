"""
Refresh Token Repository for TaxasGE Backend
Handles refresh token data access and management using PostgreSQL direct

Module: Auth
Architecture: 3-tier (Routes → Services → Repositories)
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, List
from loguru import logger
import uuid
import hashlib
import asyncpg

from app.database.connection import db_manager
from app.modules.auth.models.auth_models import (
    RefreshToken,
    RefreshTokenCreate,
    RefreshTokenResponse,
)


class RefreshTokenRepository:
    """Repository for refresh token data access using PostgreSQL"""

    def __init__(self):
        """Initialize refresh token repository"""
        self.db_manager = db_manager
        self.table = "refresh_tokens"

    def _row_to_refresh_token(self, row) -> RefreshToken:
        """
        Convert asyncpg Record to RefreshToken model.
        Handles UUID conversion to strings.
        """
        data = dict(row) if hasattr(row, 'keys') else row
        # Convert UUID fields to strings
        if 'id' in data and data['id'] is not None:
            data['id'] = str(data['id'])
        if 'user_id' in data and data['user_id'] is not None:
            data['user_id'] = str(data['user_id'])
        if 'session_id' in data and data['session_id'] is not None:
            data['session_id'] = str(data['session_id'])
        return RefreshToken(**data)

    def _row_to_refresh_token_response(self, row) -> RefreshTokenResponse:
        """
        Convert asyncpg Record to RefreshTokenResponse model.
        Handles UUID conversion to strings.
        """
        data = dict(row) if hasattr(row, 'keys') else row
        # Convert UUID fields to strings
        if 'id' in data and data['id'] is not None:
            data['id'] = str(data['id'])
        if 'user_id' in data and data['user_id'] is not None:
            data['user_id'] = str(data['user_id'])
        if 'session_id' in data and data['session_id'] is not None:
            data['session_id'] = str(data['session_id'])
        return RefreshTokenResponse(**data)


    def _hash_token(self, token: str) -> str:
        """
        Hash a refresh token for secure storage

        Args:
            token: Plain text token

        Returns:
            str: Hashed token
        """
        return hashlib.sha256(token.encode()).hexdigest()

    async def create_token(
        self,
        token_data: RefreshTokenCreate,
        conn: Optional[asyncpg.Connection] = None
    ) -> RefreshToken:
        """
        Create a new refresh token

        Args:
            token_data: Refresh token creation data
            conn: Optional database connection (if None, uses db_manager)

        Returns:
            RefreshToken: Created refresh token

        Raises:
            Exception: If token creation fails
        """
        try:
            token_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)

            # Hash the token before storing
            hashed_token = self._hash_token(token_data.token)

            query = """
                INSERT INTO refresh_tokens (
                    id, token, user_id, session_id, is_revoked,
                    expires_at, created_at, revoked_at, last_used_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING *
            """

            if conn:
                result = await conn.fetchrow(
                    query,
                    token_id,
                    hashed_token,
                    token_data.user_id,
                    token_data.session_id,
                    False,
                    token_data.expires_at,
                    now,
                    None,
                    None
                )
            else:
                result = await self.db_manager.execute_single(
                    query,
                    token_id,
                    hashed_token,
                    token_data.user_id,
                    token_data.session_id,
                    False,
                    token_data.expires_at,
                    now,
                    None,
                    None
                )

            if not result:
                raise Exception("Failed to create refresh token")

            logger.info(f"✅ Refresh token created: {token_id} for user {token_data.user_id}")
            return self._row_to_refresh_token(result)

        except Exception as e:
            logger.error(f"❌ Error creating refresh token: {str(e)}")
            raise Exception(f"Failed to create refresh token: {str(e)}")

    async def find_by_token(
        self,
        token: str,
        conn: Optional[asyncpg.Connection] = None
    ) -> Optional[RefreshToken]:
        """
        Find refresh token by token value

        Args:
            token: Plain text token
            conn: Optional database connection (if None, uses db_manager)

        Returns:
            Optional[RefreshToken]: Token if found and valid, None otherwise
        """
        try:
            hashed_token = self._hash_token(token)

            query = """
                SELECT * FROM refresh_tokens
                WHERE token = $1 AND is_revoked = false
                LIMIT 1
            """

            if conn:
                result = await conn.fetchrow(query, hashed_token)
            else:
                result = await self.db_manager.execute_single(query, hashed_token)

            if result:
                token_data = dict(result)

                # Check if token is expired
                expires_at = token_data["expires_at"]
                if expires_at < datetime.now(timezone.utc):
                    logger.warning(f"⚠️ Refresh token expired: {token_data['id']}")
                    return None

                return self._row_to_refresh_token(token_data)

            return None

        except Exception as e:
            logger.error(f"❌ Error finding refresh token: {str(e)}")
            return None

    async def find_by_session(
        self,
        session_id: str,
        conn: Optional[asyncpg.Connection] = None
    ) -> Optional[RefreshToken]:
        """
        Find refresh token by session ID

        Args:
            session_id: Session ID
            conn: Optional database connection (if None, uses db_manager)

        Returns:
            Optional[RefreshToken]: Token if found, None otherwise
        """
        try:
            query = """
                SELECT * FROM refresh_tokens
                WHERE session_id = $1 AND is_revoked = false
                LIMIT 1
            """

            if conn:
                result = await conn.fetchrow(query, session_id)
            else:
                result = await self.db_manager.execute_single(query, session_id)

            if result:
                return self._row_to_refresh_token(result)

            return None

        except Exception as e:
            logger.error(f"❌ Error finding refresh token by session: {str(e)}")
            return None

    async def find_user_tokens(
        self,
        user_id: str,
        valid_only: bool = True,
        conn: Optional[asyncpg.Connection] = None
    ) -> List[RefreshTokenResponse]:
        """
        Find all refresh tokens for a user

        Args:
            user_id: User ID
            valid_only: Return only non-revoked tokens
            conn: Optional database connection (if None, uses db_manager)

        Returns:
            List[RefreshTokenResponse]: List of user refresh tokens
        """
        try:
            if valid_only:
                query = """
                    SELECT * FROM refresh_tokens
                    WHERE user_id = $1 AND is_revoked = false
                    ORDER BY created_at DESC
                    LIMIT 50
                """
            else:
                query = """
                    SELECT * FROM refresh_tokens
                    WHERE user_id = $1
                    ORDER BY created_at DESC
                    LIMIT 50
                """

            if conn:
                results = await conn.fetch(query, user_id)
            else:
                results = await self.db_manager.execute_query(query, user_id)

            if results:
                return [self._row_to_refresh_token_response(token) for token in results]

            return []

        except Exception as e:
            logger.error(f"❌ Error finding user refresh tokens: {str(e)}")
            return []

    async def update_last_used(
        self,
        token_id: str,
        conn: Optional[asyncpg.Connection] = None
    ) -> bool:
        """
        Update token last used timestamp

        Args:
            token_id: Token ID
            conn: Optional database connection (if None, uses db_manager)

        Returns:
            bool: True if updated successfully
        """
        try:
            query = """
                UPDATE refresh_tokens
                SET last_used_at = $1
                WHERE id = $2
            """

            now = datetime.now(timezone.utc)

            if conn:
                await conn.execute(query, now, token_id)
            else:
                await self.db_manager.execute_command(query, now, token_id)

            return True

        except Exception as e:
            logger.error(f"❌ Error updating token last used: {str(e)}")
            return False

    async def revoke_token(
        self,
        token_id: str,
        conn: Optional[asyncpg.Connection] = None
    ) -> bool:
        """
        Revoke a refresh token

        Args:
            token_id: Token ID
            conn: Optional database connection (if None, uses db_manager)

        Returns:
            bool: True if revoked successfully
        """
        try:
            now = datetime.now(timezone.utc)

            query = """
                UPDATE refresh_tokens
                SET is_revoked = true, revoked_at = $1
                WHERE id = $2
            """

            if conn:
                result = await conn.execute(query, now, token_id)
            else:
                result = await self.db_manager.execute_command(query, now, token_id)

            success = "UPDATE 1" in result
            if success:
                logger.info(f"✅ Refresh token revoked: {token_id}")

            return success

        except Exception as e:
            logger.error(f"❌ Error revoking refresh token: {str(e)}")
            return False

    async def revoke_by_token_value(
        self,
        token: str,
        conn: Optional[asyncpg.Connection] = None
    ) -> bool:
        """
        Revoke a refresh token by its value

        Args:
            token: Plain text token
            conn: Optional database connection (if None, uses db_manager)

        Returns:
            bool: True if revoked successfully
        """
        try:
            hashed_token = self._hash_token(token)
            now = datetime.now(timezone.utc)

            query = """
                UPDATE refresh_tokens
                SET is_revoked = true, revoked_at = $1
                WHERE token = $2
            """

            if conn:
                result = await conn.execute(query, now, hashed_token)
            else:
                result = await self.db_manager.execute_command(query, now, hashed_token)

            success = "UPDATE" in result
            if success:
                logger.info("✅ Refresh token revoked by value")

            return success

        except Exception as e:
            logger.error(f"❌ Error revoking refresh token by value: {str(e)}")
            return False

    async def revoke_by_session(
        self,
        session_id: str,
        conn: Optional[asyncpg.Connection] = None
    ) -> bool:
        """
        Revoke refresh token by session ID

        Args:
            session_id: Session ID
            conn: Optional database connection (if None, uses db_manager)

        Returns:
            bool: True if revoked successfully
        """
        try:
            now = datetime.now(timezone.utc)

            query = """
                UPDATE refresh_tokens
                SET is_revoked = true, revoked_at = $1
                WHERE session_id = $2
            """

            if conn:
                result = await conn.execute(query, now, session_id)
            else:
                result = await self.db_manager.execute_command(query, now, session_id)

            success = "UPDATE" in result
            if success:
                logger.info(f"✅ Refresh tokens revoked for session: {session_id}")

            return success

        except Exception as e:
            logger.error(f"❌ Error revoking tokens by session: {str(e)}")
            return False

    async def revoke_all_user_tokens(
        self,
        user_id: str,
        conn: Optional[asyncpg.Connection] = None
    ) -> int:
        """
        Revoke all refresh tokens for a user

        Args:
            user_id: User ID
            conn: Optional database connection (if None, uses db_manager)

        Returns:
            int: Number of tokens revoked
        """
        try:
            now = datetime.now(timezone.utc)

            query = """
                UPDATE refresh_tokens
                SET is_revoked = true, revoked_at = $1
                WHERE user_id = $2 AND is_revoked = false
            """

            if conn:
                result = await conn.execute(query, now, user_id)
            else:
                result = await self.db_manager.execute_command(query, now, user_id)

            # Extract count from result (e.g., "UPDATE 5")
            count = int(result.split()[-1]) if result and result.startswith("UPDATE") else 0

            logger.info(f"✅ Revoked {count} refresh tokens for user {user_id}")
            return count

        except Exception as e:
            logger.error(f"❌ Error revoking user refresh tokens: {str(e)}")
            return 0

    async def cleanup_expired_tokens(
        self,
        conn: Optional[asyncpg.Connection] = None
    ) -> int:
        """
        Clean up expired refresh tokens (mark as revoked)

        Args:
            conn: Optional database connection (if None, uses db_manager)

        Returns:
            int: Number of tokens cleaned up
        """
        try:
            now = datetime.now(timezone.utc)

            query = """
                UPDATE refresh_tokens
                SET is_revoked = true, revoked_at = $1
                WHERE expires_at < $1 AND is_revoked = false
            """

            if conn:
                result = await conn.execute(query, now)
            else:
                result = await self.db_manager.execute_command(query, now)

            count = int(result.split()[-1]) if result and result.startswith("UPDATE") else 0

            if count > 0:
                logger.info(f"✅ Cleaned up {count} expired refresh tokens")

            return count

        except Exception as e:
            logger.error(f"❌ Error cleaning up expired tokens: {str(e)}")
            return 0

    async def delete_old_tokens(
        self,
        days: int = 90,
        conn: Optional[asyncpg.Connection] = None
    ) -> int:
        """
        Delete old revoked refresh tokens

        Args:
            days: Delete tokens older than this many days
            conn: Optional database connection (if None, uses db_manager)

        Returns:
            int: Number of tokens deleted
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

            query = """
                DELETE FROM refresh_tokens
                WHERE is_revoked = true AND created_at < $1
            """

            if conn:
                result = await conn.execute(query, cutoff_date)
            else:
                result = await self.db_manager.execute_command(query, cutoff_date)

            count = int(result.split()[-1]) if result and result.startswith("DELETE") else 0

            if count > 0:
                logger.info(f"✅ Deleted {count} old refresh tokens")

            return count

        except Exception as e:
            logger.error(f"❌ Error deleting old tokens: {str(e)}")
            return 0
