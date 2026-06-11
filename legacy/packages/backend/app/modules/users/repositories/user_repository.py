"""
User repository for TaxasGE Backend
Handles user data persistence with PostgreSQL and Supabase
"""

import json
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone
from loguru import logger

from app.repositories.base import BaseRepository
from app.modules.users.models import (
    UserResponse, UserCreate, UserUpdate, UserSearchFilter,
    UserStats, UserActivity, UserNotificationPreferences,
    UserRole, UserStatus
)


class UserRepository(BaseRepository[UserResponse]):
    """Repository for user management operations"""

    def __init__(self):
        super().__init__("users")

    async def find_by_id(self, id: str, conn=None) -> Optional[UserResponse]:
        """
        Find user by ID with RBAC role code from roles table.
        Overrides base find_by_id to LEFT JOIN roles for role_code.
        """
        try:
            query = """
                SELECT u.*, r.code as role_code
                FROM users u
                LEFT JOIN roles r ON r.id = u.role_id
                WHERE u.id = $1
            """
            if conn:
                result = await conn.fetchrow(query, id)
            else:
                result = await self.db_manager.execute_single(query, id)

            if result:
                return self._map_to_model(dict(result))
        except Exception as e:
            logger.error(f"Error finding user by ID {id}: {e}")
        return None

    def _map_to_model(self, data: Dict[str, Any]) -> UserResponse:
        """Map database row to UserResponse model"""
        import json

        # Parse JSONB fields that come as strings from asyncpg
        backup_codes = data.get("two_factor_backup_codes")
        if backup_codes and isinstance(backup_codes, str):
            try:
                backup_codes = json.loads(backup_codes)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse two_factor_backup_codes for user {data.get('id')}")
                backup_codes = None

        return UserResponse(
            id=str(data["id"]),  # Convert UUID to string
            email=data["email"],
            role=UserRole(data["role"]),
            status=UserStatus(data["status"]),
            first_name=data["first_name"],
            last_name=data["last_name"],
            phone_number=data.get("phone_number"),  # DB column: phone_number
            address=data.get("address"),
            city=data.get("city"),
            preferred_language=data.get("preferred_language", "es"),  # DB column: preferred_language
            avatar_url=data.get("avatar_url"),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            last_login=data.get("last_login"),
            email_verified=data.get("email_verified", False),
            two_factor_enabled=data.get("two_factor_enabled", False),
            two_factor_secret=data.get("two_factor_secret"),
            two_factor_backup_codes=backup_codes,  # Now properly parsed as list
            citizen_profile=data.get("citizen_profile"),
            business_profile=data.get("business_profile"),
            # Funcionario fields
            matricula_funcionario=data.get("matricula_funcionario"),
            funcionario_verified_at=data.get("funcionario_verified_at"),
            funcionario_verified_by=str(data["funcionario_verified_by"]) if data.get("funcionario_verified_by") else None,
            # funcionario_status will be enriched by auth middleware
            # RBAC role code from LEFT JOIN roles (available when fetched via find_by_id)
            role_code=data.get("role_code"),
        )

    def _map_from_model(self, model: UserResponse) -> Dict[str, Any]:
        """Map UserResponse model to database row"""
        return {
            "id": model.id,
            "email": model.email,
            "role": model.role.value,
            "status": model.status.value,
            "first_name": model.first_name,
            "last_name": model.last_name,
            "phone_number": model.phone_number,
            "address": model.address,
            "city": model.city,
            "preferred_language": model.preferred_language,
            "avatar_url": model.avatar_url,
            "created_at": model.created_at,
            "updated_at": model.updated_at,
            "last_login": model.last_login,
            "citizen_profile": model.citizen_profile.model_dump() if model.citizen_profile else None,
            "business_profile": model.business_profile.model_dump() if model.business_profile else None
        }

    async def find_all(
        self,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        conn = None,
        use_supabase: bool = True
    ) -> List[UserResponse]:
        """
        Find all users with optional filtering.
        Overrides base to handle 'search' filter with ILIKE on name/email.

        Args:
            filters: Dictionary of filters. Special 'search' key does ILIKE on first_name, last_name, email.
            order_by: ORDER BY clause
            limit: Maximum results
            offset: Results to skip

        Returns:
            List[UserResponse]: List of matching users
        """
        try:
            query_parts = [f"SELECT * FROM {self.table_name}"]
            conditions = []
            params = []
            param_count = 0

            if filters:
                # Copy to avoid mutating original
                filters = filters.copy()

                # Handle 'search' filter specially with ILIKE on multiple columns
                search_term = filters.pop('search', None)
                if search_term:
                    param_count += 1
                    search_condition = f"""(
                        first_name ILIKE ${param_count}
                        OR last_name ILIKE ${param_count}
                        OR email ILIKE ${param_count}
                    )"""
                    conditions.append(search_condition)
                    params.append(f"%{search_term}%")

                # Handle 'roles' filter (multiple roles via ANY)
                roles_list = filters.pop('roles', None)
                if roles_list and isinstance(roles_list, list):
                    param_count += 1
                    conditions.append(f"role::text = ANY(${param_count}::text[])")
                    params.append(roles_list)

                # Handle remaining filters as exact match
                for key, value in filters.items():
                    param_count += 1
                    conditions.append(f"{key} = ${param_count}")
                    params.append(value)

            if conditions:
                query_parts.append(f"WHERE {' AND '.join(conditions)}")

            if order_by:
                query_parts.append(f"ORDER BY {order_by}")

            if limit:
                param_count += 1
                query_parts.append(f"LIMIT ${param_count}")
                params.append(limit)

            if offset:
                param_count += 1
                query_parts.append(f"OFFSET ${param_count}")
                params.append(offset)

            query = " ".join(query_parts)

            if conn:
                results = await conn.fetch(query, *params)
            else:
                results = await self.db_manager.execute_query(query, *params)

            return [self._map_to_model(dict(row)) for row in results]

        except Exception as e:
            logger.error(f"❌ Error finding all users: {e}")
            return []

    async def count(
        self,
        filters: Optional[Dict[str, Any]] = None,
        conn = None,
        use_supabase: bool = True
    ) -> int:
        """
        Count users with optional filtering.
        Overrides base to handle 'search' filter with ILIKE on name/email.

        Args:
            filters: Dictionary of filters. Special 'search' key does ILIKE on first_name, last_name, email.

        Returns:
            int: Number of matching users
        """
        try:
            query_parts = [f"SELECT COUNT(*) FROM {self.table_name}"]
            conditions = []
            params = []
            param_count = 0

            if filters:
                # Copy filters to avoid modifying original
                filters = filters.copy()

                # Handle 'search' filter specially with ILIKE on multiple columns
                search_term = filters.pop('search', None)
                if search_term:
                    param_count += 1
                    search_condition = f"""(
                        first_name ILIKE ${param_count}
                        OR last_name ILIKE ${param_count}
                        OR email ILIKE ${param_count}
                    )"""
                    conditions.append(search_condition)
                    params.append(f"%{search_term}%")

                # Handle 'roles' filter (multiple roles via ANY)
                roles_list = filters.pop('roles', None)
                if roles_list and isinstance(roles_list, list):
                    param_count += 1
                    conditions.append(f"role::text = ANY(${param_count}::text[])")
                    params.append(roles_list)

                # Handle remaining filters as exact match
                for key, value in filters.items():
                    param_count += 1
                    conditions.append(f"{key} = ${param_count}")
                    params.append(value)

            if conditions:
                query_parts.append(f"WHERE {' AND '.join(conditions)}")

            query = " ".join(query_parts)

            if conn:
                result = await conn.fetchval(query, *params)
            else:
                result = await self.db_manager.execute_scalar(query, *params)

            return result or 0

        except Exception as e:
            logger.error(f"❌ Error counting users: {e}")
            return 0

    async def find_by_email(self, email: str, use_supabase: bool = False) -> Optional[UserResponse]:
        """
        Find user by email address.

        Args:
            email: User email address
            use_supabase: Deprecated parameter, kept for backward compatibility.
                         Always uses PostgreSQL directly.

        Returns:
            Optional[UserResponse]: User if found, None otherwise
        """
        try:
            # Always use direct PostgreSQL (use_supabase parameter ignored)
            query = f"SELECT * FROM {self.table_name} WHERE email = $1"
            result = await self.db_manager.execute_single(query, email)
            if result:
                return self._map_to_model(dict(result))

        except Exception as e:
            logger.error(f"❌ Error finding user by email {email}: {e}")

        return None

    async def get_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user by ID and return raw data including sensitive fields
        Used for internal operations (2FA, password change, etc.)

        Args:
            user_id: User UUID

        Returns:
            Optional[Dict]: Raw user data, or None if not found
        """
        try:
            query = f"SELECT * FROM {self.table_name} WHERE id = $1"
            result = await self.db_manager.execute_single(query, user_id)

            if result:
                return dict(result)

        except Exception as e:
            logger.error(f"❌ Error finding user by ID {user_id}: {e}")

        return None

    async def find_by_email_with_password(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Find user by email and return raw data including password_hash
        Used for authentication purposes only

        IMPORTANT: Always uses direct PostgreSQL query (not Supabase REST API)
        because Supabase RLS policies may hide password_hash column for security.

        Args:
            email: User email address

        Returns:
            Optional[Dict]: Raw user data with password_hash, or None if not found
        """
        try:
            # Always use direct PostgreSQL for password_hash retrieval
            # Supabase REST API may hide password_hash due to RLS policies
            query = f"SELECT * FROM {self.table_name} WHERE email = $1"
            result = await self.db_manager.execute_single(query, email)
            if result:
                return dict(result)

        except Exception as e:
            logger.error(f"❌ Error finding user by email with password {email}: {e}")

        return None

    async def create_user(self, user_data: UserCreate, password_hash: str) -> Optional[UserResponse]:
        """Create new user with password hash"""
        try:
            from uuid import uuid4
            from datetime import datetime, timezone

            # Generate ID and timestamps
            user_id = str(uuid4())
            now = datetime.now(timezone.utc)

            # Prepare data for insertion (using REAL Supabase columns)
            data = {
                "id": user_id,
                "email": user_data.email,
                "password_hash": password_hash,
                "first_name": user_data.profile.first_name,
                "last_name": user_data.profile.last_name,
                # full_name is a GENERATED column in Supabase, don't insert
                "phone_number": user_data.profile.phone_number,  # Use actual field name, not alias
                "address": user_data.profile.address,  # Profile field
                "city": user_data.profile.city,  # Profile field
                "avatar_url": user_data.profile.avatar_url,  # Profile field
                "role": user_data.role.value,
                "status": UserStatus.active.value,
                "preferred_language": user_data.profile.preferred_language if user_data.profile.preferred_language else "es",  # Use actual field name
                "email_verified": getattr(user_data, 'email_verified', False),  # CRITICAL: Email verification status
                # created_at, updated_at have DB defaults, no need to insert
            }

            # Insert user directly using db_manager
            columns = list(data.keys())
            placeholders = [f"${i+1}" for i in range(len(columns))]
            values = list(data.values())

            query = f"""
                INSERT INTO {self.table_name} ({', '.join(columns)})
                VALUES ({', '.join(placeholders)})
                RETURNING *
            """

            result = await self.db_manager.execute_single(query, *values)
            if result:
                return self._map_to_model(dict(result))

            return None

        except Exception as e:
            logger.error(f"❌ Error creating user: {e}")
            return None

    async def get_password_hash(self, user_id: str) -> str:
        """
        Get password hash for user (for verification during password change).

        Args:
            user_id: User ID

        Returns:
            str: Password hash

        Raises:
            ValueError: If user not found

        Source: UC-USER-010
        """
        try:
            # Always use direct PostgreSQL for password_hash retrieval
            # Supabase REST API may hide password_hash due to RLS policies
            query = """
                SELECT password_hash
                FROM users
                WHERE id = $1
            """
            result = await self.db_manager.execute_single(query, user_id)

            if not result:
                raise ValueError(f"User {user_id} not found")

            return result['password_hash']

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"❌ Error getting password hash for user {user_id}: {e}")
            raise ValueError(f"Error retrieving user password")

    async def update_password(self, user_id: str, password_hash: str) -> bool:
        """
        Update user password hash

        IMPORTANT: Always uses PostgreSQL directly (not Supabase) to bypass RLS
        because password updates can happen from public endpoints (password reset)
        or from authenticated users changing their own password.
        """
        try:
            updates = {
                "password_hash": password_hash,
                "updated_at": datetime.now(timezone.utc)
            }

            # Always use direct PostgreSQL to bypass Supabase RLS restrictions
            query = """
                UPDATE users
                SET password_hash = $1, updated_at = $2
                WHERE id = $3
            """
            result = await self.db_manager.execute_command(
                query, password_hash, updates["updated_at"], user_id
            )
            return "UPDATE 1" in result

        except Exception as e:
            logger.error(f"❌ Error updating password for user {user_id}: {e}")
            return False

    async def update_last_login(self, user_id: str) -> bool:
        """Update user's last login timestamp"""
        try:
            now = datetime.now(timezone.utc)
            updates = {
                "last_login": now,
                "updated_at": now
            }

            return await self.update(user_id, updates) is not None

        except Exception as e:
            logger.error(f"❌ Error updating last login for user {user_id}: {e}")
            return False

    async def search_users(self, search_filter: UserSearchFilter) -> List[UserResponse]:
        """Search users with advanced filtering"""
        try:
            filters = {}

            # Build filters
            if search_filter.role:
                filters["role"] = search_filter.role.value
            if search_filter.status:
                filters["status"] = search_filter.status.value
            if search_filter.country:
                filters["country"] = search_filter.country
            if search_filter.city:
                filters["city"] = search_filter.city
            if search_filter.language:
                filters["language"] = search_filter.language

            # Text search
            if search_filter.search_query:
                search_columns = ["first_name", "last_name", "email"]
                return await self.search(
                    search_filter.search_query,
                    search_columns,
                    filters
                )

            # Email filter (partial match)
            if search_filter.email:
                # Use PostgreSQL ILIKE
                query_parts = [f"SELECT * FROM {self.table_name}"]
                conditions = ["email ILIKE $1"]
                params = [f"%{search_filter.email}%"]
                param_count = 1

                for key, value in filters.items():
                    param_count += 1
                    conditions.append(f"{key} = ${param_count}")
                    params.append(value)

                query_parts.append(f"WHERE {' AND '.join(conditions)}")
                query = " ".join(query_parts)

                results = await self.db_manager.execute_query(query, *params)
                return [self._map_to_model(dict(row)) for row in results]

            # Standard filtering
            return await self.find_all(filters=filters)

        except Exception as e:
            logger.error(f"❌ Error searching users: {e}")
            return []

    async def get_user_stats(self) -> UserStats:
        """Get user statistics"""
        try:
            total_users = await self.count()
            active_users = await self.count({"status": UserStatus.active.value})

            # New users this month
            start_of_month = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            new_users_query = """
                SELECT COUNT(*) FROM users
                WHERE created_at >= $1
            """
            new_users_this_month = await self.db_manager.execute_scalar(
                new_users_query, start_of_month
            ) or 0

            # Users by role
            role_stats_query = """
                SELECT role, COUNT(*) as count
                FROM users
                GROUP BY role
            """
            role_results = await self.db_manager.execute_query(role_stats_query)
            users_by_role = {row["role"]: row["count"] for row in role_results}

            # Users by status
            status_stats_query = """
                SELECT status, COUNT(*) as count
                FROM users
                GROUP BY status
            """
            status_results = await self.db_manager.execute_query(status_stats_query)
            users_by_status = {row["status"]: row["count"] for row in status_results}

            # Users by city
            city_stats_query = """
                SELECT COALESCE(city, 'Non spécifié') as city, COUNT(*) as count
                FROM users
                GROUP BY city
                ORDER BY count DESC
                LIMIT 10
            """
            city_results = await self.db_manager.execute_query(city_stats_query)
            users_by_city = {row["city"]: row["count"] for row in city_results}

            return UserStats(
                total_users=total_users,
                active_users=active_users,
                new_users_this_month=new_users_this_month,
                users_by_role=users_by_role,
                users_by_status=users_by_status,
                users_by_city=users_by_city
            )

        except Exception as e:
            logger.error(f"❌ Error getting user stats: {e}")
            return UserStats(
                total_users=0,
                active_users=0,
                new_users_this_month=0,
                users_by_role={},
                users_by_status={},
                users_by_city={}
            )

    async def log_user_activity(self, activity: UserActivity) -> bool:
        """Log user activity to audit_logs table

        Maps UserActivity fields to audit_logs schema:
        - resource → entity_type (e.g., 'login', 'profile', 'declaration')
        - user_id as entity_id for user-centric activities
        - metadata → new_values (jsonb)
        """
        try:
            # Parse resource to get entity_type (default to 'user_activity')
            entity_type = activity.resource or "user_activity"
            entity_id = activity.user_id

            # Prepare metadata as JSONB
            metadata_json = json.dumps(activity.metadata) if activity.metadata else None

            query = """
                INSERT INTO audit_logs
                (user_id, entity_type, entity_id, action, new_values, ip_address, user_agent, created_at)
                VALUES ($1, $2, $3, $4, $5::jsonb, $6::inet, $7, $8)
            """
            result = await self.db_manager.execute_command(
                query,
                activity.user_id,
                entity_type,
                entity_id,
                activity.action,
                metadata_json,
                activity.ip_address,
                activity.user_agent,
                activity.timestamp
            )
            return "INSERT" in result

        except Exception as e:
            logger.error(f"❌ Error logging user activity to audit_logs: {e}")
            return False

    async def get_user_activities(
        self,
        user_id: str,
        limit: int = 50
    ) -> List[UserActivity]:
        """Get user activity history from audit_logs table

        Maps audit_logs fields back to UserActivity model:
        - entity_type → resource
        - new_values → metadata
        - created_at → timestamp
        """
        try:
            query = """
                SELECT user_id, action, entity_type as resource,
                       ip_address::text, user_agent, new_values as metadata, created_at as timestamp
                FROM audit_logs
                WHERE user_id = $1
                ORDER BY created_at DESC
                LIMIT $2
            """
            results = await self.db_manager.execute_query(query, user_id, limit)
            return [
                UserActivity(
                    user_id=str(row["user_id"]),
                    action=row["action"],
                    resource=row.get("resource"),
                    ip_address=row.get("ip_address"),
                    user_agent=row.get("user_agent"),
                    metadata=row.get("metadata"),
                    timestamp=row["timestamp"]
                )
                for row in results
            ]

        except Exception as e:
            logger.error(f"❌ Error getting user activities for {user_id}: {e}")
            return []

    # =========================================================================
    # PASSWORD RESET METHODS (MODULE_02)
    # =========================================================================

    async def update_password_reset_token(
        self,
        user_id: str,
        reset_token: str,
        expires_at: datetime
    ) -> bool:
        """
        Update user's password reset token and expiration

        Args:
            user_id: User UUID
            reset_token: Password reset token (32 chars random)
            expires_at: Token expiration timestamp (1 hour)

        Returns:
            bool: True if update successful, False otherwise

        Source: migrations/module_02/001_add_auth_advanced_columns.sql
        """
        try:
            now = datetime.now(timezone.utc)
            query = """
                UPDATE users
                SET password_reset_token = $1,
                    password_reset_expires_at = $2,
                    updated_at = $3
                WHERE id = $4
            """
            result = await self.db_manager.execute_command(
                query, reset_token, expires_at, now, user_id
            )
            success = "UPDATE 1" in result
            if success:
                logger.info(f"✅ Password reset token set for user {user_id}")
            return success

        except Exception as e:
            logger.error(f"❌ Error setting password reset token for user {user_id}: {e}")
            return False

    async def find_by_reset_token(self, reset_token: str) -> Optional[Dict[str, Any]]:
        """
        Find user by password reset token (with expiration check)

        Args:
            reset_token: Password reset token

        Returns:
            Optional[Dict]: User data if token valid and not expired, None otherwise

        Source: migrations/module_02/001_add_auth_advanced_columns.sql
        """
        try:
            now = datetime.now(timezone.utc)
            query = """
                SELECT *
                FROM users
                WHERE password_reset_token = $1
                AND password_reset_expires_at > $2
            """
            result = await self.db_manager.execute_single(query, reset_token, now)
            if result:
                logger.info(f"✅ Valid password reset token found")
                return dict(result)
            else:
                logger.warning(f"⚠️ Password reset token not found or expired")
                return None

        except Exception as e:
            logger.error(f"❌ Error finding user by reset token: {e}")
            return None

    async def clear_password_reset_token(self, user_id: str) -> bool:
        """
        Clear password reset token after successful password reset

        Args:
            user_id: User UUID

        Returns:
            bool: True if cleared successfully, False otherwise

        Source: migrations/module_02/001_add_auth_advanced_columns.sql
        """
        try:
            now = datetime.now(timezone.utc)
            query = """
                UPDATE users
                SET password_reset_token = NULL,
                    password_reset_expires_at = NULL,
                    updated_at = $1
                WHERE id = $2
            """
            result = await self.db_manager.execute_command(query, now, user_id)
            success = "UPDATE 1" in result
            if success:
                logger.info(f"✅ Password reset token cleared for user {user_id}")
            return success

        except Exception as e:
            logger.error(f"❌ Error clearing password reset token for user {user_id}: {e}")
            return False

    # =========================================================================
    # EMAIL VERIFICATION METHODS (MODULE_02)
    # =========================================================================

    async def update_email_verification_code(
        self,
        user_id: str,
        verification_code: str,
        expires_at: datetime
    ) -> bool:
        """
        Update user's email verification code and expiration

        Args:
            user_id: User UUID
            verification_code: 6-digit verification code
            expires_at: Code expiration timestamp (15 minutes)

        Returns:
            bool: True if update successful, False otherwise

        Source: migrations/module_02/001_add_auth_advanced_columns.sql
        """
        try:
            now = datetime.now(timezone.utc)
            query = """
                UPDATE users
                SET email_verification_code = $1,
                    email_verification_expires_at = $2,
                    updated_at = $3
                WHERE id = $4
            """
            result = await self.db_manager.execute_command(
                query, verification_code, expires_at, now, user_id
            )
            success = "UPDATE 1" in result
            if success:
                logger.info(f"✅ Email verification code set for user {user_id}")
            return success

        except Exception as e:
            logger.error(f"❌ Error setting email verification code for user {user_id}: {e}")
            return False

    async def find_by_verification_code(self, verification_code: str) -> Optional[Dict[str, Any]]:
        """
        Find user by email verification code (with expiration check)

        Args:
            verification_code: 6-digit verification code

        Returns:
            Optional[Dict]: User data if code valid and not expired, None otherwise

        Source: migrations/module_02/001_add_auth_advanced_columns.sql
        """
        try:
            now = datetime.now(timezone.utc)
            query = """
                SELECT *
                FROM users
                WHERE email_verification_code = $1
                AND email_verification_expires_at > $2
            """
            result = await self.db_manager.execute_single(query, verification_code, now)
            if result:
                logger.info(f"✅ Valid email verification code found")
                return dict(result)
            else:
                logger.warning(f"⚠️ Email verification code not found or expired")
                return None

        except Exception as e:
            logger.error(f"❌ Error finding user by verification code: {e}")
            return None

    async def mark_email_verified(self, user_id: str) -> bool:
        """
        Mark user's email as verified and clear verification code

        Args:
            user_id: User UUID

        Returns:
            bool: True if marked successfully, False otherwise

        Source: migrations/module_02/001_add_auth_advanced_columns.sql
        """
        try:
            now = datetime.now(timezone.utc)
            query = """
                UPDATE users
                SET email_verified = TRUE,
                    email_verification_code = NULL,
                    email_verification_expires_at = NULL,
                    updated_at = $1
                WHERE id = $2
            """
            result = await self.db_manager.execute_command(query, now, user_id)
            success = "UPDATE 1" in result
            if success:
                logger.info(f"✅ Email marked as verified for user {user_id}")
            return success

        except Exception as e:
            logger.error(f"❌ Error marking email as verified for user {user_id}: {e}")
            return False

    # =========================================================================
    # TWO-FACTOR AUTHENTICATION METHODS (TASK-M01-011)
    # =========================================================================

    async def enable_two_factor(
        self,
        user_id: str,
        secret: str,
        backup_codes: List[str]
    ) -> bool:
        """
        Enable 2FA for user and save TOTP secret + backup codes.

        Args:
            user_id: User UUID
            secret: TOTP secret (base32 encoded, 32 chars)
            backup_codes: List of hashed backup codes

        Returns:
            bool: True if enabled successfully, False otherwise

        Source: TASK-M01-011
        Database: users.two_factor_enabled, two_factor_secret, two_factor_backup_codes
        """
        try:
            import json
            now = datetime.now(timezone.utc)
            query = """
                UPDATE users
                SET two_factor_enabled = TRUE,
                    two_factor_secret = $1,
                    two_factor_backup_codes = $2,
                    updated_at = $3
                WHERE id = $4
            """

            logger.info(f"Enabling 2FA for user {user_id}")
            result = await self.db_manager.execute_command(
                query, secret, json.dumps(backup_codes), now, user_id
            )

            success = "UPDATE 1" in result
            if success:
                logger.info(f"✅ 2FA enabled successfully for user {user_id}")
            else:
                logger.error(f"❌ 2FA enable failed: UPDATE affected 0 rows for user {user_id}. "
                           f"Possible causes: user not found, RLS blocking update, or database permissions issue. "
                           f"Query result: {result}")
            return success

        except Exception as e:
            logger.error(f"❌ Exception while enabling 2FA for user {user_id}: {str(e)}")
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"Stacktrace: {traceback.format_exc()}")
            return False

    async def disable_two_factor(self, user_id: str) -> bool:
        """
        Disable 2FA for user and clear secret + backup codes.

        Args:
            user_id: User UUID

        Returns:
            bool: True if disabled successfully, False otherwise

        Source: TASK-M01-011
        """
        try:
            now = datetime.now(timezone.utc)
            query = """
                UPDATE users
                SET two_factor_enabled = FALSE,
                    two_factor_secret = NULL,
                    two_factor_backup_codes = NULL,
                    updated_at = $1
                WHERE id = $2
            """

            logger.info(f"Disabling 2FA for user {user_id}")
            result = await self.db_manager.execute_command(query, now, user_id)

            success = "UPDATE 1" in result
            if success:
                logger.info(f"✅ 2FA disabled successfully for user {user_id}")
            else:
                logger.error(f"❌ 2FA disable failed: UPDATE affected 0 rows for user {user_id}. "
                           f"Possible causes: user not found, RLS blocking update, or database permissions issue. "
                           f"Query result: {result}")
            return success

        except Exception as e:
            logger.error(f"❌ Exception while disabling 2FA for user {user_id}: {str(e)}")
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"Stacktrace: {traceback.format_exc()}")
            return False

    async def update_backup_codes(
        self,
        user_id: str,
        backup_codes: List[str]
    ) -> bool:
        """
        Update user's 2FA backup codes (after one is used).

        Args:
            user_id: User UUID
            backup_codes: Updated list of hashed backup codes

        Returns:
            bool: True if updated successfully, False otherwise

        Source: TASK-M01-011
        """
        try:
            import json
            now = datetime.now(timezone.utc)
            query = """
                UPDATE users
                SET two_factor_backup_codes = $1,
                    updated_at = $2
                WHERE id = $3
            """
            result = await self.db_manager.execute_command(
                query, json.dumps(backup_codes), now, user_id
            )
            success = "UPDATE 1" in result
            if success:
                logger.info(f"✅ Backup codes updated for user {user_id}")
            return success

        except Exception as e:
            logger.error(f"❌ Error updating backup codes for user {user_id}: {e}")
            return False

    # =========================================================================
    # LOGIN LOCKOUT METHODS (Account Security - Brute Force Protection)
    # =========================================================================

    async def increment_failed_login(
        self,
        user_id: str,
        ip_address: str
    ) -> Dict[str, Any]:
        """
        Increment failed login attempts for user.
        Locks account if attempts reach 5.

        Args:
            user_id: User UUID
            ip_address: Client IP address

        Returns:
            Dict with: failed_attempts (int), locked_until (datetime or None), was_locked (bool)

        Source: Account lockout feature (brute force protection)
        """
        try:
            # Get current user data to check IP
            query_get = """
                SELECT failed_login_attempts, last_failed_ip, locked_until
                FROM users
                WHERE id = $1
            """
            user_data = await self.db_manager.execute_single(query_get, user_id)

            if not user_data:
                logger.warning(f"User {user_id} not found for lockout increment")
                return {"failed_attempts": 0, "locked_until": None, "was_locked": False}

            current_attempts = user_data.get("failed_login_attempts", 0) or 0
            last_ip = user_data.get("last_failed_ip")

            # Reset counter if IP changed (different device/location)
            if last_ip and last_ip != ip_address:
                new_attempts = 1
                logger.info(f"IP changed for user {user_id}, resetting attempts to 1")
            else:
                new_attempts = current_attempts + 1

            # Check if we need to lock the account (exponential backoff)
            locked_until = None
            was_locked = False

            if new_attempts >= 5:
                # Exponential backoff: 1min, 5min, 15min, 1h, 24h
                lockout_minutes_map = {
                    5: 1,      # 5 attempts → 1 minute
                    6: 5,      # 6 attempts → 5 minutes
                    7: 15,     # 7 attempts → 15 minutes
                    8: 60,     # 8 attempts → 1 hour
                }
                # 9+ attempts → 24 hours
                lockout_minutes = lockout_minutes_map.get(new_attempts, 1440)
                locked_until = datetime.now(timezone.utc) + timedelta(minutes=lockout_minutes)
                was_locked = True
                logger.warning(f"🔒 Account locked for user {user_id} for {lockout_minutes}min (attempt #{new_attempts})")

            # Update database
            now = datetime.now(timezone.utc)
            if locked_until:
                query_update = """
                    UPDATE users
                    SET failed_login_attempts = $1,
                        last_failed_ip = $2,
                        locked_until = $3,
                        updated_at = $4
                    WHERE id = $5
                """
                await self.db_manager.execute_command(
                    query_update, new_attempts, ip_address, locked_until, now, user_id
                )
            else:
                query_update = """
                    UPDATE users
                    SET failed_login_attempts = $1,
                        last_failed_ip = $2,
                        updated_at = $3
                    WHERE id = $4
                """
                await self.db_manager.execute_command(
                    query_update, new_attempts, ip_address, now, user_id
                )

            return {
                "failed_attempts": new_attempts,
                "locked_until": locked_until,
                "was_locked": was_locked
            }

        except Exception as e:
            logger.error(f"❌ Error incrementing failed login for user {user_id}: {e}")
            return {"failed_attempts": 0, "locked_until": None, "was_locked": False}

    async def reset_failed_login(self, user_id: str) -> bool:
        """
        Reset failed login attempts and unlock account.
        Called on successful login.

        Args:
            user_id: User UUID

        Returns:
            bool: True if reset successfully, False otherwise

        Source: Account lockout feature (brute force protection)
        """
        try:
            now = datetime.now(timezone.utc)
            query = """
                UPDATE users
                SET failed_login_attempts = 0,
                    last_failed_ip = NULL,
                    locked_until = NULL,
                    updated_at = $1
                WHERE id = $2
            """
            result = await self.db_manager.execute_command(query, now, user_id)
            success = "UPDATE 1" in result
            if success:
                logger.info(f"✅ Failed login attempts reset for user {user_id}")
            return success

        except Exception as e:
            logger.error(f"❌ Error resetting failed login for user {user_id}: {e}")
            return False

    async def check_account_lockout(self, user_id: str) -> Optional[datetime]:
        """
        Check if account is currently locked.

        Args:
            user_id: User UUID

        Returns:
            Optional[datetime]: locked_until timestamp if locked, None if not locked

        Source: Account lockout feature (brute force protection)
        """
        try:
            query = """
                SELECT locked_until
                FROM users
                WHERE id = $1
            """
            result = await self.db_manager.execute_single(query, user_id)

            if not result:
                return None

            locked_until = result.get("locked_until")

            if not locked_until:
                return None

            # Check if lock has expired
            if datetime.now(timezone.utc) >= locked_until:
                # Auto-unlock (lock expired)
                await self.reset_failed_login(user_id)
                logger.info(f"🔓 Auto-unlocked expired lock for user {user_id}")
                return None

            # Still locked
            return locked_until

        except Exception as e:
            logger.error(f"❌ Error checking account lockout for user {user_id}: {e}")
            return None

    async def delete_user(self, user_id: str) -> bool:
        """
        Delete user by ID (used for rollback when email verification fails).

        Args:
            user_id: User UUID

        Returns:
            bool: True if deleted successfully, False otherwise

        Source: Email verification rollback (BLOCKING registration)
        """
        try:
            query = """
                DELETE FROM users
                WHERE id = $1
            """
            result = await self.db_manager.execute_command(query, user_id)
            success = "DELETE 1" in result
            if success:
                logger.info(f"✅ User {user_id} deleted (rollback)")
            return success

        except Exception as e:
            logger.error(f"❌ Error deleting user {user_id}: {e}")
            return False



# Global user repository instance
user_repository = UserRepository()