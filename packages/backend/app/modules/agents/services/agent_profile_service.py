"""
Agent Profile Service - Business logic for agent profile management

Uses the new agent_profiles table for unified agent management.
Supports ministry_agent and entity_agent types with is_supervisor capability.
"""

from typing import Dict, Any, Optional, List
from uuid import UUID
from loguru import logger
from decimal import Decimal
import asyncio
import asyncpg
import json

from app.modules.agents.repositories.agent_profile_repository import (
    agent_profile_repository,
    AgentProfileRepository,
)
from app.modules.agents.repositories.workload_repository import WorkloadRepository
from app.core.cache import invalidate_user_permissions_cache
from app.modules.agents.models.agent_profile import (
    AgentProfileCreate,
    AgentProfileUpdate,
    AgentListFilters,
    AgentType,
)

# Import MenuConfigService for dynamic menu generation
try:
    from app.modules.menu_config.services.menu_config_service import (
        MenuConfigService,
        get_menu_config_service,
    )
    MENU_CONFIG_AVAILABLE = True
except ImportError:
    MENU_CONFIG_AVAILABLE = False
    logger.warning("MenuConfigService not available - dynamic menus disabled")


class AgentProfileService:
    """Service for agent profile management"""

    def __init__(
        self,
        profile_repository: Optional[AgentProfileRepository] = None,
        workload_repository: Optional[WorkloadRepository] = None,
    ):
        self.profile_repo = profile_repository or agent_profile_repository
        self.workload_repo = workload_repository or WorkloadRepository()

    # ========================================================================
    # CRUD OPERATIONS
    # ========================================================================

    async def create_agent_profile(
        self,
        conn: asyncpg.Connection,
        profile_data: AgentProfileCreate,
        create_workload: bool = True,
    ) -> Dict[str, Any]:
        """
        Create a new agent profile with optional workload initialization.

        Args:
            conn: Database connection
            profile_data: Profile creation data
            create_workload: Whether to create initial workload record

        Returns:
            Created profile with details
        """
        # Validate agent type requirements
        validation = self._validate_profile_data(profile_data)
        if not validation["valid"]:
            raise ValueError(validation["error"])

        # Auto-populate ministry_id from entity if not provided
        if profile_data.entity_id and not profile_data.ministry_id:
            entity_ministry = await conn.fetchval(
                "SELECT ministry_id FROM entities WHERE id = $1",
                profile_data.entity_id,
            )
            if entity_ministry:
                profile_data.ministry_id = entity_ministry

        # Create the profile
        profile = await self.profile_repo.create(conn, profile_data)
        profile_id = profile["id"]

        logger.info(
            f"Created agent profile {profile_id} for user {profile_data.user_id} "
            f"(type: {profile_data.agent_type}, supervisor: {profile_data.is_supervisor})"
        )

        # Create workload record if requested
        if create_workload:
            workload = await self.workload_repo.create_workload_for_profile(
                conn, str(profile_id)
            )
            if workload:
                logger.debug(f"Created workload record for profile {profile_id}")

        # Return profile with details
        return await self.profile_repo.get_with_details(conn, UUID(str(profile_id)))

    async def get_agent_profile(
        self,
        conn: asyncpg.Connection,
        profile_id: UUID,
        include_details: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Get agent profile by ID, optionally with full details."""
        if include_details:
            return await self.profile_repo.get_with_details(conn, profile_id)
        return await self.profile_repo.get_by_id(conn, profile_id)

    async def get_agent_by_user_id(
        self,
        conn: asyncpg.Connection,
        user_id: UUID,
        active_only: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Get agent profile by user ID."""
        profile = await self.profile_repo.get_by_user_id(conn, user_id, active_only)
        if profile:
            return await self.profile_repo.get_with_details(conn, UUID(str(profile["id"])))
        return None

    async def get_agent_with_menu_config(
        self,
        conn: asyncpg.Connection,
        user_id: UUID,
    ) -> Optional[Dict[str, Any]]:
        """
        Get agent profile with dynamic menu and dashboard configuration.

        This method integrates with MenuConfigService to provide:
        - For workflow-based agents: Auto-generated menus from entity.workflow_codes
        - For module-based agents (TESORO): Explicit menus from roles.menu_config

        Args:
            conn: Database connection
            user_id: User UUID

        Returns:
            Agent profile with menu_config, dashboard_config, and permissions
        """
        # First get the agent profile
        profile = await self.profile_repo.get_by_user_id(conn, user_id, active_only=True)
        if not profile:
            return None

        profile_id = UUID(str(profile["id"]))

        # Get full profile details
        profile_details = await self.profile_repo.get_with_details(conn, profile_id)
        if not profile_details:
            return None

        # If MenuConfigService is available, fetch dynamic menu config
        if MENU_CONFIG_AVAILABLE:
            try:
                menu_service = get_menu_config_service()
                menu_config_response = await menu_service.get_agent_menu_config(
                    agent_profile_id=profile_id,
                    user_id=user_id,
                    db_connection=conn
                )

                # Merge menu config into profile response
                profile_details["menu_config"] = menu_config_response.menu_config.model_dump()
                profile_details["dashboard_config"] = menu_config_response.dashboard_config.model_dump()
                profile_details["available_workflows"] = menu_config_response.available_workflows
                profile_details["entity_type"] = menu_config_response.entity_type
                profile_details["permissions"] = menu_config_response.permissions

                logger.debug(
                    f"Menu config loaded for agent {profile_id}: "
                    f"type={menu_config_response.entity_type}, "
                    f"menus={len(menu_config_response.menu_config.menus)}"
                )
            except Exception as e:
                logger.error(f"Failed to load menu config for agent {profile_id}: {e}")
                # Return profile without menu config on error
                profile_details["menu_config"] = None
                profile_details["dashboard_config"] = None
        else:
            profile_details["menu_config"] = None
            profile_details["dashboard_config"] = None

        return profile_details

    async def update_agent_profile(
        self,
        conn: asyncpg.Connection,
        profile_id: UUID,
        update_data: AgentProfileUpdate,
        updated_by: Optional[UUID] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Update an agent profile.

        If rbac_role_id is provided, replaces the user's permissions with the role's permissions.
        """
        # Handle RBAC role change if provided
        rbac_role_id = update_data.rbac_role_id
        if rbac_role_id is not None:
            # Get the profile to find user_id
            current_profile = await self.profile_repo.get_by_id(conn, profile_id)
            if current_profile:
                user_id = UUID(str(current_profile["user_id"]))
                await self._update_user_rbac_role(conn, user_id, rbac_role_id, updated_by)

        # Create a copy of update_data without rbac_role_id (it's not a column in agent_profiles)
        update_dict = update_data.model_dump(exclude_unset=True)
        update_dict.pop('rbac_role_id', None)

        # Only call repository update if there are fields to update
        if update_dict:
            from app.modules.agents.models.agent_profile import AgentProfileUpdate
            filtered_update = AgentProfileUpdate(**update_dict)
            profile = await self.profile_repo.update(conn, profile_id, filtered_update)
            if profile:
                logger.info(f"Updated agent profile {profile_id}")

        return await self.profile_repo.get_with_details(conn, profile_id)

    async def _update_user_rbac_role(
        self,
        conn: asyncpg.Connection,
        user_id: UUID,
        rbac_role_id: UUID,
        granted_by: Optional[UUID] = None,
    ) -> None:
        """
        Update user's RBAC role by setting role_id on users table.

        This is the PRIMARY mechanism for permissions - the user gets permissions
        through role_permissions via their role_id.

        Optionally also copies to user_permissions for per-user overrides.
        """
        # Verify role exists
        role_check = await conn.fetchrow(
            """SELECT id, code FROM roles WHERE id = $1""",
            rbac_role_id
        )
        if not role_check:
            logger.warning(f"RBAC role {rbac_role_id} not found")
            return

        logger.info(f"Updating user {user_id} RBAC role to {role_check['code']}")

        # CRITICAL: Update users.role_id - this is how permissions work via role_permissions
        await conn.execute(
            """UPDATE users SET role_id = $1, updated_at = NOW() WHERE id = $2""",
            rbac_role_id, user_id
        )

        # Remove existing user-specific permissions (from previous RBAC role assignment)
        await conn.execute(
            """DELETE FROM user_permissions WHERE user_id = $1""",
            user_id
        )

        # Batch copy permissions to user_permissions (1 query instead of N round-trips)
        granted_by_str = str(granted_by) if granted_by else None
        result = await conn.execute("""
            INSERT INTO user_permissions (user_id, permission_id, granted, granted_by, granted_at)
            SELECT $1, rp.permission_id, TRUE, $2, NOW()
            FROM role_permissions rp
            WHERE rp.role_id = $3 AND rp.granted = TRUE
            ON CONFLICT (user_id, permission_id) DO UPDATE
            SET granted = TRUE, granted_by = EXCLUDED.granted_by, granted_at = NOW()
        """, user_id, granted_by_str, rbac_role_id)

        # Extract count from result (e.g. "INSERT 0 147")
        perm_count = int(result.split()[-1]) if result else 0
        logger.info(f"RBAC role updated: role_id set + {perm_count} permissions batch-copied to user_permissions")

        # CRITICAL: Invalidate permission cache immediately (not wait 10min TTL)
        try:
            await invalidate_user_permissions_cache(str(user_id))
            logger.info(f"Permission cache invalidated for user {user_id}")
        except Exception as e:
            logger.warning(f"Failed to invalidate permission cache for {user_id}: {e}")

    async def deactivate_agent_profile(
        self,
        conn: asyncpg.Connection,
        profile_id: UUID,
        deactivated_by: UUID,
        reason: Optional[str] = None,
    ) -> bool:
        """Deactivate an agent profile."""
        success = await self.profile_repo.deactivate(
            conn, profile_id, deactivated_by, reason
        )
        if success:
            logger.info(
                f"Deactivated agent profile {profile_id} by {deactivated_by}: {reason}"
            )
        return success

    async def reactivate_agent_profile(
        self,
        conn: asyncpg.Connection,
        profile_id: UUID,
    ) -> bool:
        """Reactivate a deactivated agent profile."""
        success = await self.profile_repo.reactivate(conn, profile_id)
        if success:
            logger.info(f"Reactivated agent profile {profile_id}")
        return success

    # ========================================================================
    # LIST & SEARCH
    # ========================================================================

    async def list_agent_profiles(
        self,
        conn: asyncpg.Connection,
        filters: AgentListFilters,
    ) -> Dict[str, Any]:
        """
        List agent profiles with filters and pagination.

        Returns:
            {
                "items": List of profiles,
                "total": Total count,
                "limit": Page size,
                "offset": Current offset
            }
        """
        profiles, total = await self.profile_repo.list_agents(conn, filters)
        return {
            "items": profiles,
            "total": total,
            "limit": filters.limit,
            "offset": filters.offset,
        }

    async def get_agents_by_ministry(
        self,
        conn: asyncpg.Connection,
        ministry_id: int,
        supervisors_only: bool = False,
        active_only: bool = True,
    ) -> List[Dict[str, Any]]:
        """Get all agents for a ministry."""
        filters = AgentListFilters(
            ministry_id=ministry_id,
            is_supervisor=True if supervisors_only else None,
            is_active=active_only,
            limit=1000,
        )
        profiles, _ = await self.profile_repo.list_agents(conn, filters)
        return profiles

    async def get_agents_by_entity(
        self,
        conn: asyncpg.Connection,
        entity_id: UUID,
        supervisors_only: bool = False,
        active_only: bool = True,
    ) -> List[Dict[str, Any]]:
        """Get all agents for an entity."""
        filters = AgentListFilters(
            entity_id=entity_id,
            is_supervisor=True if supervisors_only else None,
            is_active=active_only,
            limit=1000,
        )
        profiles, _ = await self.profile_repo.list_agents(conn, filters)
        return profiles

    async def get_agents_by_ministry_code(
        self,
        conn: asyncpg.Connection,
        ministry_code: str,
        supervisors_only: bool = False,
        active_only: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Get all agents for a ministry by its code.

        Args:
            conn: Database connection
            ministry_code: Ministry code (e.g., 'HACIENDA', 'JUSTICIA', 'INTERIOR')
            supervisors_only: Only return supervisors
            active_only: Only return active agents

        Returns:
            List of agent profiles for the specified ministry
        """
        # First, get the ministry_id from the ministry_code
        ministry = await conn.fetchrow(
            "SELECT id FROM ministries WHERE ministry_code = $1",
            ministry_code.upper()
        )
        if not ministry:
            logger.warning(f"Ministry with code '{ministry_code}' not found")
            return []

        filters = AgentListFilters(
            ministry_id=ministry["id"],
            is_supervisor=True if supervisors_only else None,
            is_active=active_only,
            limit=1000,
        )
        profiles, _ = await self.profile_repo.list_agents(conn, filters)
        return profiles

    # ========================================================================
    # ASSIGNMENT & AVAILABILITY
    # ========================================================================

    async def get_available_agents_for_assignment(
        self,
        conn: asyncpg.Connection,
        ministry_id: Optional[int] = None,
        entity_id: Optional[UUID] = None,
        min_approval_amount: Optional[Decimal] = None,
        exclude_overloaded: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Get agents available for task assignment.

        Args:
            conn: Database connection
            ministry_id: Filter by ministry
            entity_id: Filter by entity
            min_approval_amount: Minimum approval amount needed
            exclude_overloaded: Exclude overloaded agents

        Returns:
            List of available agents sorted by capacity
        """
        return await self.profile_repo.get_available_agents(
            conn,
            ministry_id=ministry_id,
            entity_id=entity_id,
            min_approval_amount=float(min_approval_amount) if min_approval_amount else None,
            exclude_overloaded=exclude_overloaded,
        )

    async def get_supervisors(
        self,
        conn: asyncpg.Connection,
        ministry_id: Optional[int] = None,
        entity_id: Optional[UUID] = None,
    ) -> List[Dict[str, Any]]:
        """Get supervisor agents."""
        return await self.profile_repo.get_supervisors(
            conn, ministry_id=ministry_id, entity_id=entity_id
        )

    async def find_best_agent_for_task(
        self,
        conn: asyncpg.Connection,
        ministry_id: Optional[int] = None,
        entity_id: Optional[UUID] = None,
        required_amount: Optional[Decimal] = None,
        specialization: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Find the best available agent for a task.

        Returns the agent with lowest workload who meets all requirements.
        """
        agents = await self.get_available_agents_for_assignment(
            conn,
            ministry_id=ministry_id,
            entity_id=entity_id,
            min_approval_amount=required_amount,
        )

        if not agents:
            logger.warning(
                f"No available agents found for ministry={ministry_id}, entity={entity_id}"
            )
            return None

        # Filter by specialization if provided
        if specialization:
            specialized = [
                a for a in agents
                if specialization in (a.get("specializations") or [])
            ]
            if specialized:
                agents = specialized

        # Return agent with lowest capacity (already sorted by repository)
        best_agent = agents[0]
        logger.info(
            f"Best agent for task: {best_agent.get('id')} "
            f"(capacity: {best_agent.get('capacity_percentage')}%)"
        )
        return best_agent

    # ========================================================================
    # STATISTICS
    # ========================================================================

    async def get_ministry_agent_stats(
        self,
        conn: asyncpg.Connection,
        ministry_id: int,
    ) -> Dict[str, int]:
        """Get agent count statistics for a ministry."""
        return await self.profile_repo.count_by_ministry(conn, ministry_id)

    async def get_entity_agent_stats(
        self,
        conn: asyncpg.Connection,
        entity_id: UUID,
    ) -> Dict[str, int]:
        """Get agent count statistics for an entity."""
        return await self.profile_repo.count_by_entity(conn, entity_id)

    # ========================================================================
    # HELPERS
    # ========================================================================

    def _validate_profile_data(
        self,
        profile_data: AgentProfileCreate,
    ) -> Dict[str, Any]:
        """
        Validate profile creation data.

        All agents MUST have entity_id for service_request routing.
        ministry_id is optional (auto-populated from entity's ministry_id
        if the entity belongs to a ministry — used only for dashboard
        filtering and performance stats).
        """
        # entity_id is required for ALL agent types (routing depends on it)
        if not profile_data.entity_id:
            return {
                "valid": False,
                "error": "Agent must be assigned to an entity (entity_id required)",
            }

        return {"valid": True, "error": None}

    # ========================================================================
    # AGENT INVITATION FLOW (2-step: invite → activate)
    # ========================================================================

    async def initiate_agent_invitation(
        self,
        data,  # AgentInviteRequest
        created_by: UUID,
    ) -> Dict[str, Any]:
        """
        Step 1: Initiate agent invitation.

        This method:
        1. Validates the data
        2. Generates a verification code
        3. Stores invitation in pending_registrations with metadata
        4. Sends invitation email to the agent

        The agent must click the link and set their password to complete registration.

        Args:
            data: AgentInviteRequest model (no password)
            created_by: UUID of admin performing the invitation

        Returns:
            Dict with email, message, expires_at
        """
        import secrets
        from app.modules.auth.repositories.pending_registration_repository import PendingRegistrationRepository
        from app.modules.communications.services.email_service import EmailService

        # Validate entity_id is provided (required for routing)
        if not data.entity_id:
            raise ValueError(
                "L'agent doit être assigné à une entité (entity_id requis). "
                "Tous les agents nécessitent une entité pour le routage des demandes."
            )

        # Check if email already exists
        from app.database.connection import db_manager
        existing = await db_manager.execute_single(
            "SELECT id FROM users WHERE email = $1",
            data.user.email.lower()
        )
        if existing:
            raise ValueError(f"Un compte existe déjà avec l'email {data.user.email}")

        # Generate 6-digit verification code
        verification_code = ''.join([str(secrets.randbelow(10)) for _ in range(6)])

        # Prepare user data (without password)
        user_data = {
            'first_name': data.user.first_name,
            'last_name': data.user.last_name,
            'phone_number': data.user.phone_number,
            'preferred_language': data.user.preferred_language,
        }

        # Prepare agent profile data
        agent_data = {
            'agent_type': data.agent_type.value,
            'is_supervisor': data.is_supervisor,
            'entity_id': str(data.entity_id) if data.entity_id else None,
            'entity_location_id': str(data.entity_location_id) if data.entity_location_id else None,
            'ministry_id': data.ministry_id,
            'rbac_role_id': str(data.rbac_role_id) if data.rbac_role_id else None,
            'can_approve_unlimited': data.can_approve_unlimited,
            'max_approval_amount': float(data.max_approval_amount) if data.max_approval_amount else None,
            'can_escalate': data.can_escalate,
            'can_assign_tasks': data.can_assign_tasks,
            'can_reassign': data.can_reassign,
            'specializations': data.specializations or [],
            'working_hours_start': str(data.working_hours_start) if data.working_hours_start else None,
            'working_hours_end': str(data.working_hours_end) if data.working_hours_end else None,
            'working_days': data.working_days or [1, 2, 3, 4, 5],
        }

        # Store in pending_registrations
        pending_repo = PendingRegistrationRepository()
        await pending_repo.create_agent_invitation(
            email=data.user.email.lower(),
            verification_code=verification_code,
            user_data=user_data,
            agent_data=agent_data,
            created_by=str(created_by),
            expires_in_minutes=1440  # 24 hours
        )

        # Send invitation email
        from app.modules.communications.services.email_service import get_email_service
        email_service = get_email_service()
        if email_service:
            try:
                email_service.send_agent_invitation(
                    to_email=data.user.email.lower(),
                    first_name=data.user.first_name,
                    verification_code=verification_code,
                    language=data.user.preferred_language or 'es'
                )
                logger.info(f"Agent invitation email sent to {data.user.email}")
            except Exception as e:
                logger.error(f"Failed to send agent invitation email: {e}")
                # Don't fail the invitation, email can be resent
        else:
            logger.warning("Email service not available — invitation email not sent")

        logger.info(
            f"Agent invitation initiated: email={data.user.email}, "
            f"type={data.agent_type.value}, created_by={created_by}"
        )

        return {
            "email": data.user.email,
            "full_name": f"{data.user.first_name} {data.user.last_name}",
            "message": "Invitation envoyée. L'agent doit valider son email et définir son mot de passe.",
            "expires_in_hours": 24,
        }

    async def finalize_agent_creation(
        self,
        conn,
        email: str,
        verification_code: str,
        password: str,
    ) -> Dict[str, Any]:
        """
        Step 2: Finalize agent creation after email validation.

        This method:
        1. Verifies the code and retrieves stored metadata
        2. Creates the user with the provided password
        3. Creates the agent profile
        4. Assigns RBAC permissions
        5. Creates workload record
        6. Deletes the pending registration

        Args:
            conn: Database connection
            email: Agent's email
            verification_code: 6-digit code from email
            password: Password chosen by the agent

        Returns:
            Dict with user_id, profile_id, tokens, etc.
        """
        import bcrypt
        import traceback
        from app.modules.auth.repositories.pending_registration_repository import PendingRegistrationRepository

        logger.info(f"[AGENT_ACTIVATION] Starting activation for {email}")

        pending_repo = PendingRegistrationRepository()

        # Step 1: Verify code and get metadata
        try:
            metadata = await pending_repo.verify_code_and_get_data(email.lower(), verification_code)
            logger.info(f"[AGENT_ACTIVATION] Step 1 - Metadata retrieved: {list(metadata.keys()) if metadata else 'None'}")
        except Exception as e:
            logger.error(f"[AGENT_ACTIVATION] Step 1 FAILED - verify_code_and_get_data: {type(e).__name__}: {e}")
            logger.error(f"[AGENT_ACTIVATION] Traceback: {traceback.format_exc()}")
            raise

        if not metadata:
            raise ValueError("Code de vérification invalide ou expiré. Veuillez demander une nouvelle invitation.")

        if metadata.get('registration_type') != 'agent':
            raise ValueError("Ce code d'invitation n'est pas valide pour un agent. Vérifiez le type d'invitation.")

        user_data = metadata.get('user_data', {})
        agent_data = metadata.get('agent_data', {})
        created_by = metadata.get('created_by')

        # Log agent_data for debugging
        logger.info(f"[AGENT_ACTIVATION] agent_data keys: {list(agent_data.keys())}")
        logger.info(f"[AGENT_ACTIVATION] agent_type={agent_data.get('agent_type')}, ministry_id={agent_data.get('ministry_id')}, entity_id={agent_data.get('entity_id')}")

        # Validate password strength (same rules as citizen registration)
        from app.modules.auth.services.password_service import PasswordService
        pwd_service = PasswordService()
        pwd_check = pwd_service.check_password_strength(password)
        if not pwd_check["valid"]:
            raise ValueError(f"Mot de passe trop faible: {', '.join(pwd_check['issues'])}")

        # Hash password
        password_hash = bcrypt.hashpw(
            password.encode('utf-8'),
            bcrypt.gensalt(rounds=12)
        ).decode('utf-8')

        try:
            async with conn.transaction():
                # Step 2: Create user with role_id (critical for permissions via role_permissions)
                logger.info(f"[AGENT_ACTIVATION] Step 2 - Creating user...")
                rbac_role_id = UUID(agent_data['rbac_role_id']) if agent_data.get('rbac_role_id') else None

                user_query = """
                    INSERT INTO users (email, password_hash, first_name, last_name,
                                       phone_number, role, role_id, preferred_language, status,
                                       email_verified, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, 'agent', $6, $7, 'active', TRUE, NOW(), NOW())
                    RETURNING id, email, first_name, last_name
                """
                user_row = await conn.fetchrow(
                    user_query,
                    email.lower(),
                    password_hash,
                    user_data.get('first_name'),
                    user_data.get('last_name'),
                    user_data.get('phone_number'),
                    rbac_role_id,  # role_id for permissions via role_permissions
                    user_data.get('preferred_language', 'es'),
                )
                user_id = user_row["id"]
                logger.info(f"[AGENT_ACTIVATION] Step 2 OK - User created: {user_id} with role_id: {rbac_role_id}")

                # Step 3: Create agent profile
                logger.info(f"[AGENT_ACTIVATION] Step 3 - Creating agent profile...")
                entity_id = UUID(agent_data['entity_id']) if agent_data.get('entity_id') else None

                # Validate: entity_id is required for all agents (routing depends on it)
                if not entity_id:
                    raise ValueError(
                        "L'agent doit être assigné à une entité (entity_id requis). "
                        "Veuillez recréer l'invitation avec une entité."
                    )
                entity_location_id = UUID(agent_data['entity_location_id']) if agent_data.get('entity_location_id') else None
                # rbac_role_id already defined above for user creation
                assigned_by = UUID(created_by) if created_by else None

                # Convert time strings back to datetime.time objects for PostgreSQL TIME columns
                from datetime import time as dt_time
                working_hours_start = None
                working_hours_end = None
                if agent_data.get('working_hours_start'):
                    try:
                        parts = agent_data['working_hours_start'].split(':')
                        working_hours_start = dt_time(int(parts[0]), int(parts[1]))
                    except (ValueError, IndexError):
                        working_hours_start = dt_time(8, 0)  # Default 08:00
                if agent_data.get('working_hours_end'):
                    try:
                        parts = agent_data['working_hours_end'].split(':')
                        working_hours_end = dt_time(int(parts[0]), int(parts[1]))
                    except (ValueError, IndexError):
                        working_hours_end = dt_time(17, 0)  # Default 17:00

                # Auto-populate ministry_id from entity if not provided
                effective_ministry_id = agent_data.get('ministry_id')
                if entity_id and not effective_ministry_id:
                    entity_ministry = await conn.fetchval(
                        "SELECT ministry_id FROM entities WHERE id = $1",
                        entity_id,
                    )
                    if entity_ministry:
                        effective_ministry_id = entity_ministry

                logger.info(f"[AGENT_ACTIVATION] Profile params: entity_id={entity_id}, ministry_id={effective_ministry_id}, working_hours={working_hours_start}-{working_hours_end}")

                profile_query = """
                    INSERT INTO agent_profiles (
                        user_id, agent_type, is_supervisor, entity_id, entity_location_id,
                        ministry_id, can_approve_unlimited, max_approval_amount,
                        can_escalate, can_assign_tasks, can_reassign,
                        specializations, working_hours_start, working_hours_end,
                        working_days, is_active, assigned_by, assigned_at
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12::jsonb, $13, $14, $15, TRUE, $16, NOW()
                    )
                    RETURNING id
                """
                profile_row = await conn.fetchrow(
                    profile_query,
                    user_id,
                    agent_data.get('agent_type'),
                    agent_data.get('is_supervisor', False),
                    entity_id,
                    entity_location_id,
                    effective_ministry_id,
                    agent_data.get('can_approve_unlimited', False),
                    agent_data.get('max_approval_amount'),
                    agent_data.get('can_escalate', True),
                    agent_data.get('can_assign_tasks', False),
                    agent_data.get('can_reassign', False),
                    json.dumps(agent_data.get('specializations', [])),
                    working_hours_start,
                    working_hours_end,
                    agent_data.get('working_days', [1, 2, 3, 4, 5]),
                    assigned_by,
                )
                profile_id = profile_row["id"]
                logger.info(f"[AGENT_ACTIVATION] Step 3 OK - Profile created: {profile_id}")

                # Step 4: Assign RBAC role if provided
                if rbac_role_id:
                    logger.info(f"[AGENT_ACTIVATION] Step 4 - Assigning RBAC role {rbac_role_id}...")
                    role_check = await conn.fetchrow(
                        """SELECT id FROM roles WHERE id = $1
                           AND (entity_type IN ('agent', 'ministry_agent', 'entity_agent')
                                OR entity_type IS NULL)""",
                        rbac_role_id
                    )
                    if role_check:
                        # Batch copy permissions (1 query instead of N round-trips)
                        result = await conn.execute("""
                            INSERT INTO user_permissions (user_id, permission_id, granted, granted_by, granted_at)
                            SELECT $1, rp.permission_id, TRUE, $2, NOW()
                            FROM role_permissions rp
                            WHERE rp.role_id = $3 AND rp.granted = TRUE
                            ON CONFLICT (user_id, permission_id) DO UPDATE SET granted = TRUE
                        """, user_id, assigned_by, rbac_role_id)

                        perm_count = int(result.split()[-1]) if result else 0
                        logger.info(f"[AGENT_ACTIVATION] Step 4 OK - RBAC role assigned with {perm_count} permissions (batch)")
                    else:
                        logger.warning(f"[AGENT_ACTIVATION] Step 4 - RBAC role {rbac_role_id} not found or invalid")
                else:
                    logger.info(f"[AGENT_ACTIVATION] Step 4 - No RBAC role to assign")

                # Step 5: Create workload record
                logger.info(f"[AGENT_ACTIVATION] Step 5 - Creating workload record...")
                await conn.execute("""
                    INSERT INTO agent_workloads (agent_profile_id, current_assignments,
                        pending_declarations, in_progress_declarations, max_concurrent_assignments,
                        capacity_percentage, workload_status, availability)
                    VALUES ($1, 0, 0, 0, 10, 0, 'available', 'available')
                """, profile_id)
                logger.info(f"[AGENT_ACTIVATION] Step 5 OK - Workload record created")

        except asyncpg.UniqueViolationError as e:
            logger.error(f"[AGENT_ACTIVATION] FAILED - Duplicate entry: {e}")
            if 'users_email_key' in str(e):
                raise ValueError(f"Un compte existe déjà avec l'email {email}")
            elif 'agent_profiles_user_id_key' in str(e):
                raise ValueError(f"Ce compte utilisateur a déjà un profil agent")
            else:
                raise ValueError(f"Violation de contrainte d'unicité: {e}")
        except asyncpg.ForeignKeyViolationError as e:
            logger.error(f"[AGENT_ACTIVATION] FAILED - Foreign key violation: {e}")
            if 'entity_id' in str(e):
                raise ValueError("L'entité sélectionnée n'existe pas ou a été supprimée")
            elif 'ministry_id' in str(e):
                raise ValueError("Le ministère sélectionné n'existe pas ou a été supprimé")
            else:
                raise ValueError(f"Référence invalide: {e}")
        except asyncpg.CheckViolationError as e:
            logger.error(f"[AGENT_ACTIVATION] FAILED - Check constraint violation: {e}")
            if 'entity_agent' in str(e) and 'ministry' in str(e):
                raise ValueError("Configuration invalide: un agent d'entité ne peut pas être assigné directement à un ministère")
            else:
                raise ValueError(f"Contrainte de validation non respectée: {e}")
        except asyncpg.RaiseError as e:
            # Custom errors raised by triggers
            logger.error(f"[AGENT_ACTIVATION] FAILED - Trigger error: {e}")
            error_msg = str(e)
            if 'entity_agent' in error_msg and 'entity_id' in error_msg:
                raise ValueError("Un agent d'entité doit être assigné à une entité")
            elif 'ministry_agent' in error_msg and 'ministry' in error_msg:
                raise ValueError("Un agent ministériel doit être lié à un ministère")
            else:
                raise ValueError(f"Erreur de validation: {error_msg}")
        except Exception as e:
            logger.error(f"[AGENT_ACTIVATION] FAILED during transaction: {type(e).__name__}: {e}")
            logger.error(f"[AGENT_ACTIVATION] Traceback: {traceback.format_exc()}")
            # Re-raise with a cleaner message for unknown errors
            raise ValueError(f"Erreur lors de la création du compte: {type(e).__name__}")

        # Step 6: Delete pending registration (outside transaction)
        try:
            await pending_repo.delete_by_email(email.lower())
            logger.info(f"[AGENT_ACTIVATION] Step 6 OK - Pending registration deleted")
        except Exception as e:
            logger.warning(f"[AGENT_ACTIVATION] Step 6 - Failed to delete pending registration: {e}")
            # Don't fail the whole process for this

        logger.info(
            f"[AGENT_ACTIVATION] SUCCESS - user={user_id}, profile={profile_id}, "
            f"type={agent_data.get('agent_type')}"
        )

        return {
            "user_id": user_id,
            "user_email": email,
            "user_full_name": f"{user_data.get('first_name')} {user_data.get('last_name')}",
            "profile_id": profile_id,
            "agent_type": agent_data.get('agent_type'),
            "is_supervisor": agent_data.get('is_supervisor', False),
            "message": "Compte agent créé avec succès. Vous pouvez maintenant vous connecter.",
        }

    # ========================================================================
    # ADMIN INVITATION FLOW (2-step: invite → activate)
    # ========================================================================

    async def initiate_admin_invitation(
        self,
        data,  # AdminInviteRequest
        created_by: UUID,
    ) -> Dict[str, Any]:
        """
        Step 1: Initiate admin invitation.

        Similar to agent invitation but for admin users (no profile needed).
        """
        import secrets
        from app.modules.auth.repositories.pending_registration_repository import PendingRegistrationRepository
        from app.modules.communications.services.email_service import EmailService
        from app.database.connection import db_manager

        # Check if email already exists
        existing = await db_manager.execute_single(
            "SELECT id FROM users WHERE email = $1",
            data.email.lower()
        )
        if existing:
            raise ValueError(f"Un compte existe déjà avec l'email {data.email}")

        # Generate 6-digit verification code
        verification_code = ''.join([str(secrets.randbelow(10)) for _ in range(6)])

        # Prepare user data
        user_data = {
            'first_name': data.first_name,
            'last_name': data.last_name,
            'phone_number': data.phone_number,
            'preferred_language': data.preferred_language,
        }

        # Store in pending_registrations
        pending_repo = PendingRegistrationRepository()
        await pending_repo.create_admin_invitation(
            email=data.email.lower(),
            verification_code=verification_code,
            user_data=user_data,
            created_by=str(created_by),
            expires_in_minutes=1440  # 24 hours
        )

        # Send invitation email
        from app.modules.communications.services.email_service import get_email_service
        email_service = get_email_service()
        if email_service:
            try:
                email_service.send_admin_invitation(
                    to_email=data.email.lower(),
                    first_name=data.first_name,
                    verification_code=verification_code,
                    language=data.preferred_language or 'es'
                )
                logger.info(f"Admin invitation email sent to {data.email}")
            except Exception as e:
                logger.error(f"Failed to send admin invitation email: {e}")
        else:
            logger.warning("Email service not available — admin invitation email not sent")

        logger.info(f"Admin invitation initiated: email={data.email}, created_by={created_by}")

        return {
            "email": data.email,
            "full_name": f"{data.first_name} {data.last_name}",
            "message": "Invitation envoyée. L'administrateur doit valider son email et définir son mot de passe.",
            "expires_in_hours": 24,
        }

    async def finalize_admin_creation(
        self,
        conn,
        email: str,
        verification_code: str,
        password: str,
    ) -> Dict[str, Any]:
        """
        Step 2: Finalize admin creation after email validation.
        """
        import bcrypt
        from app.modules.auth.repositories.pending_registration_repository import PendingRegistrationRepository

        pending_repo = PendingRegistrationRepository()

        # Verify code and get metadata
        metadata = await pending_repo.verify_code_and_get_data(email.lower(), verification_code)

        if not metadata:
            raise ValueError("Code de vérification invalide ou expiré. Veuillez demander une nouvelle invitation.")

        if metadata.get('registration_type') != 'admin':
            raise ValueError("Ce code d'invitation n'est pas valide pour un administrateur. Vérifiez le type d'invitation.")

        user_data = metadata.get('user_data', {})

        # Validate password strength (same rules as citizen registration)
        from app.modules.auth.services.password_service import PasswordService
        pwd_service = PasswordService()
        pwd_check = pwd_service.check_password_strength(password)
        if not pwd_check["valid"]:
            raise ValueError(f"Mot de passe trop faible: {', '.join(pwd_check['issues'])}")

        # Hash password
        password_hash = bcrypt.hashpw(
            password.encode('utf-8'),
            bcrypt.gensalt(rounds=12)
        ).decode('utf-8')

        # Create user with admin role
        user_query = """
            INSERT INTO users (email, password_hash, first_name, last_name,
                               phone_number, role, preferred_language, status,
                               email_verified, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, 'admin', $6, 'active', TRUE, NOW(), NOW())
            RETURNING id, email, first_name, last_name
        """
        user_row = await conn.fetchrow(
            user_query,
            email.lower(),
            password_hash,
            user_data.get('first_name'),
            user_data.get('last_name'),
            user_data.get('phone_number'),
            user_data.get('preferred_language', 'es'),
        )

        # Delete pending registration
        await pending_repo.delete_by_email(email.lower())

        logger.info(f"Admin creation finalized: user={user_row['id']} ({email})")

        return {
            "user_id": user_row["id"],
            "email": email,
            "full_name": f"{user_data.get('first_name')} {user_data.get('last_name')}",
            "role": "admin",
            "message": "Compte administrateur créé avec succès. Vous pouvez maintenant vous connecter.",
        }

    # ========================================================================
    # PRE-SUBMIT VALIDATION
    # ========================================================================

    async def validate_agent_data(self, data) -> Dict[str, Any]:
        """
        Validate agent invitation data without creating anything.
        Runs all checks in parallel and returns errors + warnings.

        Args:
            data: AgentValidateRequest model

        Returns:
            Dict with valid (bool), errors (list), warnings (list)
        """
        from app.database.connection import db_manager
        from app.modules.agents.models.agent_profile import (
            AgentValidationIssue,
        )

        errors: List[AgentValidationIssue] = []
        warnings: List[AgentValidationIssue] = []

        async def check_email():
            """Check if email is already taken"""
            row = await db_manager.execute_single(
                "SELECT id FROM users WHERE email = $1",
                data.email.lower(),
            )
            if row:
                errors.append(AgentValidationIssue(
                    field="email",
                    message=f"Un compte existe déjà avec l'email {data.email}.",
                    severity="error",
                ))

        async def check_entity():
            """Check entity exists, is active, and type"""
            if not data.entity_id:
                errors.append(AgentValidationIssue(
                    field="entity_id",
                    message="L'agent doit être assigné à une entité.",
                    severity="error",
                ))
                return None
            row = await db_manager.execute_single(
                "SELECT id, entity_type, is_active, workflow_codes FROM entities WHERE id = $1",
                data.entity_id,
            )
            if not row:
                errors.append(AgentValidationIssue(
                    field="entity_id",
                    message="L'entité sélectionnée n'existe pas.",
                    severity="error",
                ))
                return None
            if not row["is_active"]:
                errors.append(AgentValidationIssue(
                    field="entity_id",
                    message="L'entité sélectionnée est inactive.",
                    severity="error",
                ))
            return row

        async def check_location():
            """Check location belongs to entity (if provided)"""
            if not data.entity_location_id or data.entity_location_id == "ALL_SITES":
                return
            if not data.entity_id:
                return
            # We need entity code to check locations
            entity_row = await db_manager.execute_single(
                "SELECT code FROM entities WHERE id = $1",
                data.entity_id,
            )
            if not entity_row:
                return
            loc_row = await db_manager.execute_single(
                "SELECT id FROM entity_locations WHERE id = $1 AND entity_code = $2",
                data.entity_location_id,
                entity_row["code"],
            )
            if not loc_row:
                errors.append(AgentValidationIssue(
                    field="entity_location_id",
                    message="Le site sélectionné n'appartient pas à cette entité.",
                    severity="error",
                ))

        async def check_rbac_role():
            """Check RBAC role exists"""
            if not data.rbac_role_id:
                errors.append(AgentValidationIssue(
                    field="rbac_role_id",
                    message="Un rôle RBAC est obligatoire.",
                    severity="error",
                ))
                return None
            row = await db_manager.execute_single(
                "SELECT id, code FROM roles WHERE id = $1",
                data.rbac_role_id,
            )
            if not row:
                errors.append(AgentValidationIssue(
                    field="rbac_role_id",
                    message="Le rôle RBAC sélectionné n'existe pas.",
                    severity="error",
                ))
                return None
            return row

        # Run all checks in parallel
        results = await asyncio.gather(
            check_email(),
            check_entity(),
            check_location(),
            check_rbac_role(),
            return_exceptions=True,
        )

        # Process exceptions from gather
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Validation check {i} failed: {result}")

        # Extract entity and role results for cross-checks
        entity_row = results[1] if not isinstance(results[1], Exception) else None
        role_row = results[3] if not isinstance(results[3], Exception) else None

        # Cross-check: department entity requires location
        if entity_row and isinstance(entity_row, dict) and entity_row.get("entity_type") == "department":
            if not data.entity_location_id or data.entity_location_id == "ALL_SITES":
                errors.append(AgentValidationIssue(
                    field="entity_location_id",
                    message="Les agents de département doivent être assignés à un site spécifique.",
                    severity="error",
                ))

        # Cross-check: supervisor + incompatible role
        if data.is_supervisor and role_row and isinstance(role_row, dict):
            role_code = role_row.get("code", "")
            if "supervisor" not in role_code:
                warnings.append(AgentValidationIssue(
                    field="rbac_role_id",
                    message=f"Le rôle '{role_code}' n'est pas un rôle superviseur. Vérifiez que c'est intentionnel.",
                    severity="warning",
                ))

        return {
            "valid": len(errors) == 0,
            "errors": [e.model_dump() for e in errors],
            "warnings": [w.model_dump() for w in warnings],
        }


# Singleton instance
agent_profile_service = AgentProfileService()
