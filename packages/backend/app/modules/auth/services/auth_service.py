"""
Authentication Service for TaxasGE Backend
Orchestrates authentication operations using repositories and services
"""

import asyncio
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Tuple
from loguru import logger


def _safe_create_task(coro):
    """Create an asyncio task with error logging (fire-and-forget safe)."""
    task = asyncio.create_task(coro)
    task.add_done_callback(
        lambda t: logger.error(f"Background task failed: {t.exception()}") if not t.cancelled() and t.exception() else None
    )
    return task

from app.repositories.user_repository import UserRepository
from app.modules.auth.repositories.session_repository import SessionRepository
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.modules.auth.services.password_service import get_password_service
from app.modules.auth.services.jwt_service import get_jwt_service
from app.modules.communications.services.email_service import EmailService
from app.modules.users.models.user import UserCreate, UserResponse, UserRole, UserStatus
from app.modules.auth.models.auth_models import (
    SessionCreate,
    RefreshTokenCreate,
    TokenRefreshResponse,
    LogoutResponse,
)
from app.modules.permissions.repositories.user_permission_repository import UserPermissionRepository
from app.database.connection import db_manager


class AuthService:
    """Service for authentication operations"""

    def __init__(self):
        """Initialize auth service with repositories and services"""
        self.user_repo = UserRepository()
        self.session_repo = SessionRepository()
        self.token_repo = RefreshTokenRepository()
        self.password_service = get_password_service()
        self.jwt_service = get_jwt_service()

        logger.info("AuthService initialized")

    async def _audit_auth_event(
        self,
        action: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log auth event to audit_logs table (fire-and-forget, never blocks auth flow)."""
        try:
            import json
            query = """
                INSERT INTO audit_logs (
                    user_id, entity_type, entity_id, action,
                    new_values, ip_address, user_agent, created_at
                ) VALUES ($1, 'auth', COALESCE($2, 'system'), $3, $4, $5, $6, NOW())
            """
            await db_manager.execute_command(
                query,
                user_id,
                user_id or "system",
                action,
                json.dumps(details) if details else None,
                ip_address,
                user_agent,
            )
        except Exception as e:
            logger.warning(f"Failed to log auth audit event {action}: {e}")

    async def register(
        self,
        user_data: UserCreate,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Register a new user

        Args:
            user_data: User registration data
            ip_address: Client IP address
            user_agent: Client user agent

        Returns:
            Dict: Registration response with user data and tokens

        Raises:
            Exception: If registration fails
        """
        try:
            # Check if user already exists
            # IMPORTANT: use_supabase=False to bypass RLS policies and use direct PostgreSQL
            existing_user = await self.user_repo.find_by_email(user_data.email, use_supabase=False)
            if existing_user:
                raise Exception(
                    f"Un compte existe déjà avec l'adresse email {user_data.email}. "
                    "Utilisez 'Mot de passe oublié' pour récupérer votre accès."
                )

            # Validate password strength
            password_check = self.password_service.check_password_strength(user_data.password)
            if not password_check["valid"]:
                raise Exception(
                    f"Password is too weak: {', '.join(password_check['issues'])}"
                )

            # Hash password (async — runs bcrypt in thread executor)
            hashed_password = await self.password_service.hash_password(user_data.password)

            # Create user with UserCreate object
            user = await self.user_repo.create_user(
                user_data=user_data,
                password_hash=hashed_password
            )

            if not user:
                raise Exception("Failed to create user")

            logger.info(f"[REGISTRATION_STEP_3] Utilisateur créé avec succès: {user.email} (ID: {user.id})")

            # NOTE: Email verification is now done BEFORE user creation in two-step registration flow
            # User is created with email_verified=True by default
            logger.info(f"[REGISTRATION_STEP_4] Email déjà vérifié via le code de vérification")

            # Create tokens and session
            tokens = await self._create_session(
                user_id=user.id,
                email=user.email,
                role=user.role,
                ip_address=ip_address,
                user_agent=user_agent,
            )

            # Prepare user response
            user_response = UserResponse(
                id=user.id,
                email=user.email,
                role=user.role,
                status=user.status,
                first_name=user.first_name,
                last_name=user.last_name,
                phone_number=user.phone_number,
                address=user.address,
                city=user.city,
                preferred_language=user.preferred_language,
                avatar_url=user.avatar_url,
                created_at=user.created_at,
                updated_at=user.updated_at,
                last_login=user.last_login,
                email_verified=user.email_verified,  # Important: include verification status
            )

            # Audit: REGISTER
            _safe_create_task(self._audit_auth_event(
                action="REGISTER",
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
                details={"email": user.email, "role": user.role.value if hasattr(user.role, 'value') else user.role},
            ))

            return {
                **tokens,
                "user": user_response.dict(),
            }

        except Exception as e:
            logger.error(f"Registration failed: {str(e)}")
            raise

    async def login(
        self,
        email: str,
        password: str,
        remember_me: bool = False,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Login user

        Args:
            email: User email
            password: User password
            remember_me: Extended session duration
            ip_address: Client IP address
            user_agent: Client user agent

        Returns:
            Dict: Login response with user data and tokens

        Raises:
            Exception: If login fails
        """
        try:
            # Find user by email WITH password hash (for authentication)
            user_data = await self.user_repo.find_by_email_with_password(email)
            if not user_data:
                raise Exception("Invalid email or password")

            user_id = user_data.get("id")

            # LOCKOUT CHECK: Verify account is not locked BEFORE password verification
            locked_until = await self.user_repo.check_account_lockout(user_id)
            if locked_until:
                remaining_seconds = (locked_until - datetime.now(timezone.utc)).total_seconds()
                # Ensure at least 1 minute is shown (round up)
                remaining_minutes = max(1, int((remaining_seconds + 59) / 60))
                raise Exception(f"Account locked. Try again in {remaining_minutes} minute{'s' if remaining_minutes != 1 else ''}.")

            # Verify password
            if not await self.password_service.verify_password(password, user_data["password_hash"]):
                logger.warning(f"Failed login attempt for {email} from IP {ip_address}")

                # LOCKOUT: Increment failed attempts (may lock account)
                lockout_result = await self.user_repo.increment_failed_login(
                    user_id=user_id,
                    ip_address=ip_address or "unknown"
                )

                # If account was just locked, send notification email
                if lockout_result.get("was_locked"):
                    # Send account lockout notification email
                    from app.config import get_settings
                    settings = get_settings()

                    email_service = EmailService(
                        smtp_host=settings.SMTP_HOST,
                        smtp_port=settings.SMTP_PORT,
                        smtp_username=settings.SMTP_USERNAME,
                        smtp_password=settings.SMTP_PASSWORD,
                        smtp_use_tls=settings.SMTP_USE_TLS,
                        smtp_from_email=settings.SMTP_FROM_EMAIL,
                        smtp_from_name=settings.SMTP_FROM_NAME
                    )

                    # Send lockout notification
                    email_service.send_account_lockout_notification(
                        to_email=email,
                        user_name=user_data.get("first_name", "User"),
                        locked_until=lockout_result["locked_until"]
                    )

                    logger.info(f"Account lockout email sent to {email}")

                # Audit: LOGIN_FAILURE
                _safe_create_task(self._audit_auth_event(
                    action="LOGIN_FAILURE",
                    user_id=user_id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    details={"email": email, "attempts": lockout_result.get("failed_attempts", 0)},
                ))

                raise Exception("Invalid email or password")

            # Map user data to UserResponse model (excluding password_hash)
            user = self.user_repo._map_to_model(user_data)
            # Keep role_id from raw data for RBAC role code resolution
            user_role_id = user_data.get("role_id")

            # Check user status
            if user.status == UserStatus.suspended:
                raise Exception("Account is suspended")
            elif user.status == UserStatus.deactivated or user.status == UserStatus.inactive:
                raise Exception("Account is deactivated")
            elif user.status == UserStatus.pending_verification:
                raise Exception("Email verification required. Please check your email.")
            elif user.status != UserStatus.active:
                raise Exception("Account is not active")

            logger.info(f"User logged in: {user.email} (ID: {user.id})")

            # Check if 2FA is enabled for this user
            if user.two_factor_enabled:
                logger.info(f"2FA required for user {user.email}")

                # Generate temporary token for 2FA verification (short-lived: 5 minutes)
                temp_token_user_data = {
                    "email": user.email,
                    "role": user.role.value,
                    "type": "2fa_temp",
                    "remember_me": remember_me,
                    "ip_address": ip_address,
                    "user_agent": user_agent,
                }
                temp_token = self.jwt_service.create_access_token(
                    subject=user.id,
                    user_data=temp_token_user_data,
                    expires_delta=timedelta(minutes=5),  # Short-lived temp token
                )

                # Return temp token and 2FA requirement flag
                return {
                    "requires_2fa": True,
                    "temp_token": temp_token,
                    "message": "2FA verification required. Please provide your 2FA code.",
                }

            # Standard login flow (no 2FA)
            # LOCKOUT: Reset failed login attempts on successful login
            await self.user_repo.reset_failed_login(user.id)

            # Update last login
            await self.user_repo.update_last_login(user.id)

            # Create tokens and session (with extended expiry if remember_me)
            tokens = await self._create_session(
                user_id=user.id,
                email=user.email,
                role=user.role,
                ip_address=ip_address,
                user_agent=user_agent,
                remember_me=remember_me,
            )

            # Fetch user permissions + RBAC role code (from role + user-specific grants)
            user_permissions = []
            role_code = None
            try:
                async with db_manager.get_connection() as db:
                    perm_repo = UserPermissionRepository(db)
                    user_permissions = await perm_repo.get_all_permission_names(user.id)
                    logger.debug(f"Loaded {len(user_permissions)} permissions for user {user.email}")

                    # Cache warming: pre-populate Redis permissions cache at login
                    # Eliminates cold-start latency on first authenticated request
                    try:
                        from app.core.cache import get_permissions_cache, CacheKeys
                        cache = get_permissions_cache()
                        cache_key = CacheKeys.user_permissions(user.id)
                        await cache.set(cache_key, user_permissions, ttl=600)  # 10 min
                        logger.debug(f"Warmed permissions cache for {user.email} ({len(user_permissions)} perms)")
                    except Exception as cache_err:
                        logger.warning(f"Cache warming failed for {user.email}: {cache_err}")

                    # Resolve RBAC role code from users.role_id → roles.code
                    if user_role_id:
                        row = await db.fetchrow(
                            "SELECT code FROM roles WHERE id = $1", user_role_id
                        )
                        if row:
                            role_code = row["code"]
                            logger.debug(f"Resolved RBAC role code for {user.email}: {role_code}")
            except Exception as perm_error:
                logger.warning(f"Failed to load permissions for user {user.email}: {perm_error}")
                # Continue without permissions - user will have role-based access

            # Prepare user response
            user_response = UserResponse(
                id=user.id,
                email=user.email,
                role=user.role,
                status=user.status,
                first_name=user.first_name,
                last_name=user.last_name,
                phone_number=user.phone_number,
                address=user.address,
                city=user.city,
                preferred_language=user.preferred_language,
                avatar_url=user.avatar_url,
                created_at=user.created_at,
                updated_at=user.updated_at,
                last_login=datetime.now(timezone.utc),
                email_verified=user.email_verified,
                two_factor_enabled=user.two_factor_enabled,
                role_code=role_code,
                permissions=user_permissions,
            )

            # Audit: LOGIN_SUCCESS
            _safe_create_task(self._audit_auth_event(
                action="LOGIN_SUCCESS",
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
                details={"email": user.email, "role": user.role.value if hasattr(user.role, 'value') else user.role},
            ))

            return {
                **tokens,
                "user": user_response.dict(),
            }

        except Exception as e:
            logger.error(f"Login failed: {str(e)}")
            raise

    async def refresh_tokens(
        self,
        refresh_token: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> TokenRefreshResponse:
        """
        Refresh access token using refresh token

        Args:
            refresh_token: Refresh token
            ip_address: Client IP address
            user_agent: Client user agent

        Returns:
            TokenRefreshResponse: New token pair

        Raises:
            Exception: If refresh fails
        """
        try:
            # Verify refresh token (JWT)
            payload = self.jwt_service.verify_refresh_token(refresh_token)
            if not payload:
                raise Exception("Invalid or expired refresh token")

            user_id = payload.get("sub")

            # Find refresh token in database
            token_record = await self.token_repo.find_by_token(refresh_token)
            if not token_record:
                raise Exception("Refresh token not found or revoked")

            # Find associated session
            session = await self.session_repo.find_by_id(token_record.session_id)
            if not session or session.status != "active":
                raise Exception("Session is not active")

            # Get user data
            user = await self.user_repo.find_by_id(user_id)
            if not user:
                raise Exception("User not found")

            # Check user status
            if user.status != UserStatus.active:
                raise Exception("User account is not active")

            # Update token last used
            await self.token_repo.update_last_used(token_record.id)

            # Create new token pair
            new_tokens = self.jwt_service.create_token_pair(
                subject=user_id,
                user_data={
                    "email": user.email,
                    "role": user.role.value,
                },
            )

            # Update session with new tokens
            now = datetime.now(timezone.utc)
            new_expires_at = now + timedelta(days=7)

            # Wrap revoke + create in a transaction to prevent user lockout
            # if a crash occurs between revoking the old session and creating the new one.
            async with db_manager.get_connection() as conn:
                async with conn.transaction():
                    # Revoke old session and tokens
                    await self.session_repo.revoke_session(session.id, conn=conn)
                    await self.token_repo.revoke_by_session(session.id, conn=conn)

                    # Create new session with new tokens
                    session_data = SessionCreate(
                        user_id=user_id,
                        access_token=new_tokens["access_token"],
                        refresh_token=new_tokens["refresh_token"],
                        ip_address=ip_address or session.ip_address,
                        user_agent=user_agent or session.user_agent,
                        device_info=session.device_info,
                        expires_at=new_expires_at,
                    )

                    new_session = await self.session_repo.create_session(session_data, conn=conn)

                    # Create new refresh token record
                    token_data = RefreshTokenCreate(
                        token=new_tokens["refresh_token"],
                        user_id=user_id,
                        session_id=new_session.id,
                        expires_at=new_expires_at,
                    )

                    await self.token_repo.create_token(token_data, conn=conn)

            logger.info(f"Tokens refreshed for user: {user_id}")

            # Include minimal user data so frontend can update role_code
            user_data_for_response = {
                "id": user.id,
                "email": user.email,
                "role": user.role.value if hasattr(user.role, 'value') else user.role,
                "role_code": user.role_code,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "status": user.status.value if hasattr(user.status, 'value') else user.status,
            }

            return TokenRefreshResponse(
                access_token=new_tokens["access_token"],
                refresh_token=new_tokens["refresh_token"],
                token_type="bearer",
                expires_in=new_tokens["expires_in"],
                user=user_data_for_response,
            )

        except Exception as e:
            logger.error(f"Token refresh failed: {str(e)}")
            raise

    async def logout(
        self,
        refresh_token: Optional[str] = None,
        access_token: Optional[str] = None,
        all_sessions: bool = False,
    ) -> LogoutResponse:
        """
        Logout user (revoke tokens and session)

        Args:
            refresh_token: Refresh token to revoke
            access_token: Access token to identify session
            all_sessions: Revoke all user sessions

        Returns:
            LogoutResponse: Logout status

        Raises:
            Exception: If logout fails
        """
        try:
            sessions_revoked = 0

            # Get user_id from token
            user_id = None
            if refresh_token:
                payload = self.jwt_service.decode_token(refresh_token)
                if payload:
                    user_id = payload.get("sub")
            elif access_token:
                payload = self.jwt_service.decode_token(access_token)
                if payload:
                    user_id = payload.get("sub")

            if not user_id:
                raise Exception("Invalid token")

            if all_sessions:
                # Revoke all user sessions
                sessions_revoked = await self.session_repo.revoke_all_user_sessions(user_id)
                await self.token_repo.revoke_all_user_tokens(user_id)
                logger.info(f"All sessions revoked for user: {user_id}")

            else:
                # Revoke specific session
                if refresh_token:
                    token_record = await self.token_repo.find_by_token(refresh_token)
                    if token_record:
                        await self.session_repo.revoke_session(token_record.session_id)
                        await self.token_repo.revoke_by_session(token_record.session_id)
                        sessions_revoked = 1

                elif access_token:
                    session = await self.session_repo.find_by_access_token(access_token)
                    if session:
                        await self.session_repo.revoke_session(session.id)
                        await self.token_repo.revoke_by_session(session.id)
                        sessions_revoked = 1

                logger.info(f"Session revoked for user: {user_id}")

            # Cache revocation in Redis (so validate_access_token skips DB)
            await self._cache_token_revocation(access_token)

            # Audit: LOGOUT
            _safe_create_task(self._audit_auth_event(
                action="LOGOUT",
                user_id=user_id,
                details={"all_sessions": all_sessions, "sessions_revoked": sessions_revoked},
            ))

            return LogoutResponse(
                message="Logout successful",
                sessions_revoked=sessions_revoked,
            )

        except Exception as e:
            logger.error(f"Logout failed: {str(e)}")
            raise

    async def _cache_token_revocation(self, token: Optional[str]) -> None:
        """Cache token revocation in Redis with TTL matching token remaining lifetime."""
        if not token:
            return
        try:
            from app.core.cache import get_cache
            cache = get_cache()
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            # Get remaining TTL from JWT exp claim
            remaining = self.jwt_service.get_remaining_time(token)
            ttl = int(remaining.total_seconds()) + 60 if remaining else 3600  # +60s safety margin
            await cache.set(f"revoked:{token_hash}", "1", ttl=ttl)
        except Exception as e:
            logger.warning(f"Failed to cache token revocation in Redis: {e}")

    async def validate_access_token(self, access_token: str) -> Optional[Dict[str, Any]]:
        """
        Validate access token and return user data.

        Optimized hot path (0 DB queries for non-revoked tokens):
        1. JWT verify (CPU only)
        2. Redis revocation check (O(1) Redis GET)
        3. Batched activity update (Redis, flushed to DB periodically)

        Args:
            access_token: JWT access token

        Returns:
            Optional[Dict]: User data if valid, None otherwise
        """
        try:
            # Step 1: Verify JWT signature + expiration (CPU only, 0 DB queries)
            payload = self.jwt_service.verify_access_token(access_token)
            if not payload:
                return None

            # Step 2: Check Redis revocation cache (O(1) — no DB query)
            token_hash = hashlib.sha256(access_token.encode()).hexdigest()
            try:
                from app.core.cache import get_cache
                cache = get_cache()
                is_revoked = await cache.get(f"revoked:{token_hash}")
                if is_revoked:
                    logger.warning("Token is revoked (Redis cache hit)")
                    return None
            except Exception as e:
                # Redis down: fall back to DB check (graceful degradation)
                logger.warning(f"Redis revocation check failed, falling back to DB: {e}")
                session = await self.session_repo.find_by_access_token(access_token)
                if not session or session.status != "active":
                    logger.warning("Session not found or not active (DB fallback)")
                    return None

            # Step 3: Idle timeout check + batched activity update
            user_id = payload.get("sub")
            role = payload.get("role", "citizen")
            if user_id:
                try:
                    activity_key = f"activity:{user_id}"
                    last_seen = await cache.get(activity_key)

                    # Idle timeout: agents 24h, citizens 2h
                    is_agent = role in ("admin", "supervisor", "dgi_agent", "ministry_agent") or "agent_" in str(role)
                    idle_ttl = 86400 if is_agent else 7200  # 24h vs 2h

                    if last_seen:
                        # User is active — refresh the TTL
                        await cache.set(activity_key, "1", ttl=idle_ttl)
                    else:
                        # No activity marker — could be first request or idle timeout
                        # Check JWT iat: if token was issued recently, allow (first request)
                        iat = payload.get("iat")
                        if iat:
                            token_age = (datetime.now(timezone.utc) - datetime.utcfromtimestamp(iat)).total_seconds()
                            if token_age > idle_ttl:
                                logger.warning(f"Session idle timeout for user {user_id} (age={token_age:.0f}s, limit={idle_ttl}s)")
                                return None

                        # Set activity marker + flush to DB (debounced)
                        await cache.set(activity_key, "1", ttl=idle_ttl)
                        # Flush last_activity to DB every 5min (check sub-key)
                        db_flush_key = f"activity_db:{user_id}"
                        needs_db_flush = not await cache.get(db_flush_key)
                        if needs_db_flush:
                            session = await self.session_repo.find_by_access_token(access_token)
                            if session:
                                await self.session_repo.update_last_activity(session.id)
                            await cache.set(db_flush_key, "1", ttl=300)  # 5min debounce
                except Exception:
                    pass  # Activity tracking is best-effort

            return payload

        except Exception as e:
            logger.error(f"Token validation failed: {str(e)}")
            return None

    async def _create_session(
        self,
        user_id: str,
        email: str,
        role: UserRole,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        remember_me: bool = False,
    ) -> Dict[str, Any]:
        """
        Internal method to create session and tokens

        Args:
            user_id: User ID
            email: User email
            role: User role
            ip_address: Client IP
            user_agent: Client user agent
            remember_me: Extended session

        Returns:
            Dict: Token data
        """
        # Create token pair
        tokens = self.jwt_service.create_token_pair(
            subject=user_id,
            user_data={
                "email": email,
                "role": role.value if isinstance(role, UserRole) else role,
            },
        )

        # Calculate session expiration
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=30 if remember_me else 7
        )

        # Create session
        session_data = SessionCreate(
            user_id=user_id,
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            ip_address=ip_address,
            user_agent=user_agent,
            device_info=None,
            expires_at=expires_at,
        )

        session = await self.session_repo.create_session(session_data)

        # Create refresh token record
        token_data = RefreshTokenCreate(
            token=tokens["refresh_token"],
            user_id=user_id,
            session_id=session.id,
            expires_at=expires_at,
        )

        await self.token_repo.create_token(token_data)

        return tokens

    # =========================================================================
    # PASSWORD RESET METHODS (MODULE_02)
    # =========================================================================

    async def request_password_reset(self, email: str) -> bool:
        """
        Request password reset - Generate token and send email

        Args:
            email: User email address

        Returns:
            bool: True if email sent successfully, False otherwise

        Raises:
            Exception: If user not found or email sending fails

        Business Rules:
            1. User must exist and be active
            2. Token valid for 1 hour
            3. Token is 32 characters random string
            4. Email sent with reset link

        Source: .github/docs-internal/Documentations/Backend/API_REFERENCE.md
        """
        try:
            logger.info(f"🔍 [PASSWORD_RESET] Starting password reset request for: {email}")

            # Find user by email (IMPORTANT: use_supabase=False to bypass RLS on public endpoint)
            user = await self.user_repo.find_by_email(email, use_supabase=False)
            logger.debug(f"🔍 [PASSWORD_RESET] User lookup result - Found: {user is not None}, Type: {type(user).__name__ if user else 'None'}")

            if not user:
                # For security, don't reveal if email exists
                logger.warning(f"⚠️ [PASSWORD_RESET] Password reset requested for non-existent email: {email}")
                return True  # Pretend success to avoid email enumeration

            # Check user status
            user_status = user.get("status") if isinstance(user, dict) else user.status
            logger.debug(f"🔍 [PASSWORD_RESET] User status: {user_status}")

            if user_status != "active":  # UserStatus.active is "active"
                logger.warning(f"⚠️ [PASSWORD_RESET] Password reset requested for inactive user: {email} (status={user_status})")
                return True  # Pretend success to avoid status enumeration

            # Generate reset token (32 chars random)
            import secrets
            reset_token = secrets.token_urlsafe(32)
            logger.debug(f"🔍 [PASSWORD_RESET] Generated reset token (length={len(reset_token)})")

            # Set expiration (1 hour from now)
            expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

            # Hash token before storing in DB (never store plaintext tokens)
            hashed_reset_token = hashlib.sha256(reset_token.encode()).hexdigest()

            # Save hashed token to database
            user_id = user.get("id") if isinstance(user, dict) else user.id
            logger.debug(f"🔍 [PASSWORD_RESET] Saving hashed token to DB for user_id: {user_id}")

            success = await self.user_repo.update_password_reset_token(
                user_id=user_id,
                reset_token=hashed_reset_token,
                expires_at=expires_at
            )

            if not success:
                logger.error(f"❌ [PASSWORD_RESET] Failed to save password reset token for {email}")
                raise Exception("Failed to generate password reset token")

            logger.info(f"✅ [PASSWORD_RESET] Token saved successfully to DB")

            # Send reset email
            from app.config import get_settings
            settings = get_settings()

            logger.debug(f"🔍 [PASSWORD_RESET] Initializing EmailService - SMTP_HOST={settings.SMTP_HOST}, SMTP_PORT={settings.SMTP_PORT}, SMTP_PASSWORD={'[SET]' if settings.SMTP_PASSWORD else '[NOT SET]'}")

            # Initialize EmailService with config
            email_service = EmailService(
                smtp_host=settings.SMTP_HOST,
                smtp_port=settings.SMTP_PORT,
                smtp_username=settings.SMTP_USERNAME,
                smtp_password=settings.SMTP_PASSWORD,
                smtp_use_tls=settings.SMTP_USE_TLS,
                smtp_from_email=settings.SMTP_FROM_EMAIL,
                smtp_from_name=settings.SMTP_FROM_NAME
            )

            user_name = user.get("first_name") if isinstance(user, dict) else user.first_name
            logger.debug(f"🔍 [PASSWORD_RESET] Sending email to {email} with user_name={user_name}")

            email_sent = email_service.send_password_reset_email(
                to_email=email,
                reset_token=reset_token,
                user_name=user_name
            )

            if not email_sent:
                logger.error(f"❌ [PASSWORD_RESET] Failed to send password reset email to {email}")
                # Don't raise exception - token is saved, user can retry
                return False

            logger.info(f"✅ [PASSWORD_RESET] Password reset email sent successfully to {email}")
            return True

        except Exception as e:
            logger.error(f"❌ [PASSWORD_RESET] Password reset request failed for {email}: {str(e)}")
            logger.exception(e)
            raise

    async def confirm_password_reset(
        self,
        reset_token: str,
        new_password: str
    ) -> bool:
        """
        Confirm password reset - Validate token and update password

        Args:
            reset_token: Password reset token (32 chars)
            new_password: New password (min 8 chars)

        Returns:
            bool: True if password reset successful, False otherwise

        Raises:
            Exception: If token invalid/expired or password update fails

        Business Rules:
            1. Token must be valid and not expired
            2. New password must meet strength requirements
            3. Password hashed with bcrypt (12 rounds)
            4. Token cleared after successful reset
            5. Confirmation email sent

        Source: .github/docs-internal/Documentations/Backend/API_REFERENCE.md
        """
        try:
            # Hash the incoming token to match stored hash
            hashed_reset_token = hashlib.sha256(reset_token.encode()).hexdigest()

            # Find user by hashed reset token (with expiration check)
            user_data = await self.user_repo.find_by_reset_token(hashed_reset_token)
            if not user_data:
                logger.warning(f"Invalid or expired password reset token")
                raise Exception("Invalid or expired password reset token")

            user_id = user_data["id"]
            email = user_data["email"]
            first_name = user_data.get("first_name")

            # Validate new password strength
            password_check = self.password_service.check_password_strength(new_password)
            if not password_check["valid"]:
                raise Exception(
                    f"Password is too weak: {', '.join(password_check['issues'])}"
                )

            # Hash new password (async — runs bcrypt in thread executor)
            new_password_hash = await self.password_service.hash_password(new_password)

            # Update password
            password_updated = await self.user_repo.update_password(
                user_id=user_id,
                password_hash=new_password_hash
            )

            if not password_updated:
                logger.error(f"Failed to update password for user {user_id}")
                raise Exception("Failed to update password")

            # Clear reset token
            await self.user_repo.clear_password_reset_token(user_id)

            # Send confirmation email
            from app.config import get_settings
            settings = get_settings()

            email_service = EmailService(
                smtp_host=settings.SMTP_HOST,
                smtp_port=settings.SMTP_PORT,
                smtp_username=settings.SMTP_USERNAME,
                smtp_password=settings.SMTP_PASSWORD,
                smtp_use_tls=settings.SMTP_USE_TLS,
                smtp_from_email=settings.SMTP_FROM_EMAIL,
                smtp_from_name=settings.SMTP_FROM_NAME
            )

            email_service.send_password_reset_confirmation(
                to_email=email,
                user_name=first_name
            )

            # Audit: PASSWORD_RESET
            _safe_create_task(self._audit_auth_event(
                action="PASSWORD_RESET",
                user_id=user_id,
                details={"email": email},
            ))

            logger.info(f"Password reset successful for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Password reset confirmation failed: {str(e)}")
            raise

    # =========================================================================
    # EMAIL VERIFICATION METHODS (MODULE_02)
    # NOTE: send_verification_email() method removed - email verification now handled
    # BEFORE user creation in two-step registration flow (pending_registrations table)
    # =========================================================================

    async def verify_email_code(self, verification_code: str) -> bool:
        """
        Verify email with 6-digit code

        Business Rules:
            1. Code must be valid and not expired (15 minutes)
            2. Email marked as verified
            3. Code cleared after successful verification

        Args:
            verification_code: 6-digit verification code

        Returns:
            bool: True if verification successful, False otherwise

        Source: .github/docs-internal/Documentations/Backend/API_REFERENCE.md
        """
        try:
            # Find user by verification code (with expiration check)
            user_data = await self.user_repo.find_by_verification_code(verification_code)
            if not user_data:
                raise Exception("Invalid or expired verification code")

            user_id = user_data["id"]
            email = user_data["email"]

            # Mark email as verified
            success = await self.user_repo.mark_email_verified(user_id)

            if not success:
                raise Exception("Failed to verify email")

            logger.info(f"Email verified successfully for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Email verification failed: {str(e)}")
            raise

    async def verify_2fa_login(
        self,
        temp_token: str,
        code: str,
    ) -> Dict[str, Any]:
        """
        Verify 2FA code and complete login process

        Args:
            temp_token: Temporary token from initial login
            code: 6-digit TOTP code or 8-char backup code (XXXX-XXXX)

        Returns:
            Dict: Login response with user data and tokens

        Raises:
            Exception: If 2FA verification fails

        Source: TASK-M01-013 (Login 2FA Integration)
        """
        try:
            # Validate temp token (use decode_token, not verify_access_token, since this is a 2fa_temp token)
            token_data = self.jwt_service.decode_token(temp_token)
            if not token_data or token_data.get("type") != "2fa_temp":
                raise Exception("Invalid or expired temporary token")

            user_id = token_data["sub"]
            email = token_data["email"]
            role = token_data["role"]
            remember_me = token_data.get("remember_me", False)
            ip_address = token_data.get("ip_address")
            user_agent = token_data.get("user_agent")

            logger.info(f"Verifying 2FA code for user {email}")

            # Get user to verify 2FA is enabled and get secret
            user_data = await self.user_repo.get_by_id(user_id)
            if not user_data:
                raise Exception("User not found")

            if not user_data.get("two_factor_enabled"):
                raise Exception("2FA is not enabled for this account")

            # Verify 2FA code (TOTP or backup code)
            from app.modules.auth.services.two_factor_service import get_two_factor_service

            two_factor_service = get_two_factor_service()
            is_valid = await two_factor_service.verify_login_code(user_id, code)

            if not is_valid:
                logger.warning(f"Invalid 2FA code for user {email}")
                raise Exception("Invalid or expired 2FA code")

            logger.info(f"2FA verification successful for user {email}")

            # LOCKOUT: Reset failed login attempts on successful 2FA login
            await self.user_repo.reset_failed_login(user_id)

            # Update last login
            await self.user_repo.update_last_login(user_id)

            # Create tokens and session (with extended expiry if remember_me)
            tokens = await self._create_session(
                user_id=user_id,
                email=email,
                role=UserRole(role),
                ip_address=ip_address,
                user_agent=user_agent,
                remember_me=remember_me,
            )

            # Fetch user permissions + RBAC role code (from role + user-specific grants)
            user_permissions = []
            role_code_2fa = None
            try:
                async with db_manager.get_connection() as db:
                    perm_repo = UserPermissionRepository(db)
                    user_permissions = await perm_repo.get_all_permission_names(user_id)
                    logger.debug(f"Loaded {len(user_permissions)} permissions for user {email} (2FA login)")

                    # Resolve RBAC role code from users.role_id → roles.code
                    user_role_id_2fa = user_data.get("role_id")
                    if user_role_id_2fa:
                        row = await db.fetchrow(
                            "SELECT code FROM roles WHERE id = $1", user_role_id_2fa
                        )
                        if row:
                            role_code_2fa = row["code"]
            except Exception as perm_error:
                logger.warning(f"Failed to load permissions for user {email}: {perm_error}")
                # Continue without permissions - user will have role-based access

            # Map user data to UserResponse model
            user = self.user_repo._map_to_model(user_data)

            # Prepare user response
            user_response = UserResponse(
                id=user.id,
                email=user.email,
                role=user.role,
                status=user.status,
                first_name=user.first_name,
                last_name=user.last_name,
                phone_number=user.phone_number,
                address=user.address,
                city=user.city,
                preferred_language=user.preferred_language,
                avatar_url=user.avatar_url,
                created_at=user.created_at,
                updated_at=user.updated_at,
                last_login=datetime.now(timezone.utc),
                email_verified=user.email_verified,
                two_factor_enabled=user.two_factor_enabled,
                role_code=role_code_2fa,
                permissions=user_permissions,
            )

            return {
                **tokens,
                "user": user_response.dict(),
            }

        except Exception as e:
            logger.error(f"2FA login verification failed: {str(e)}")
            raise


# Singleton instance
_auth_service_instance: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    """
    Get auth service singleton instance

    Returns:
        AuthService: Auth service instance
    """
    global _auth_service_instance

    if _auth_service_instance is None:
        _auth_service_instance = AuthService()

    return _auth_service_instance
