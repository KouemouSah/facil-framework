"""
Menu Configuration Service

Generates dynamic menus based on entity workflows or role configuration.
Supports two modes:
- Workflow-based: Auto-generates menus from entity.workflow_codes using mapping rules
- Module-based: Uses explicit menu_config from roles table

Requires database columns (migration 063):
- roles: menu_config, dashboard_config, ui_config
- agent_profiles: menu_overrides, dashboard_overrides

Author: Claude Code Expert
Date: 2026-01-19
Updated: 2026-01-25 - Added caching for performance optimization (Phase 4)
"""
from typing import List, Optional, Dict, Any
from uuid import UUID
from loguru import logger
import json

from app.modules.menu_config.models.menu_config import (
    MenuConfigResponse,
    DashboardConfigResponse,
    AgentMenuConfigResponse,
    MenuItemBase,
    SubMenuItemWithBadge,
    MenuBadgeConfig,
    WidgetConfigBase,
)
from app.modules.permissions.repositories.user_permission_repository import UserPermissionRepository
from app.core.cache import (
    get_menu_cache,
    get_workflow_mappings_cache,
    CacheKeys,
)



def _ensure_json(data: dict, key: str, default: Any = None) -> None:
    """Parse a JSONB field from string if needed, or set default if missing/falsy."""
    val = data.get(key)
    if val:
        if isinstance(val, str):
            data[key] = json.loads(val)
    elif default is not None:
        data[key] = default


def _build_workflow_indexes() -> tuple:
    """
    Build dynamic indexes from workflow_engine registry.

    100% dynamic: reads menu_group, menu_icon, menu_title_key, requires_appointment
    from each PredefinedWorkflow class. Zero hardcoded mapping — adding a new
    workflow class automatically populates all indexes.

    Returns:
        (category_index, icon_index, menu_metadata)
        - category_index: Dict[code, menu_group] for _get_workflow_category()
        - icon_index: Dict[menu_group, icon] for _create_default_menu()
        - menu_metadata: Dict[menu_group, {icon, title_key, has_appointments}] for sync
    """
    from app.modules.service_requests.services.workflow_engine import workflow_engine

    category_index: Dict[str, str] = {}
    icon_index: Dict[str, str] = {}
    menu_metadata: Dict[str, Dict[str, Any]] = {}
    all_workflows = workflow_engine.get_all_workflows()

    for base_code, workflow in all_workflows.items():
        # Get all codes this workflow handles (multi-code via get_all_workflow_codes)
        codes = [c.value for c in workflow.get_all_workflow_codes()]

        # Read properties from workflow class (dynamic, no hardcoding)
        menu_group = workflow.menu_group
        icon = workflow.menu_icon
        title_key = workflow.menu_title_key
        has_appointments = workflow.requires_appointment

        for code in codes:
            category_index[code] = menu_group

        # Build icon and metadata per menu_group (first workflow wins)
        if menu_group not in icon_index:
            icon_index[menu_group] = icon
        if menu_group not in menu_metadata:
            menu_metadata[menu_group] = {
                "icon": icon,
                "title_key": title_key,
                "has_appointments": has_appointments,
            }
        elif has_appointments:
            # If any workflow in the group needs appointments, enable for group
            menu_metadata[menu_group]["has_appointments"] = True

    logger.debug(
        f"Built workflow indexes: {len(category_index)} codes → "
        f"{len(icon_index)} menu groups"
    )
    return category_index, icon_index, menu_metadata


# Lazy-initialized indexes
_workflow_category_index: Optional[Dict[str, str]] = None
_workflow_icon_index: Optional[Dict[str, str]] = None
_workflow_menu_metadata: Optional[Dict[str, Dict[str, Any]]] = None


def get_workflow_category_index() -> Dict[str, str]:
    """Get workflow_code → menu_group mapping (lazy, from workflow_engine)."""
    global _workflow_category_index, _workflow_icon_index, _workflow_menu_metadata
    if _workflow_category_index is None:
        _workflow_category_index, _workflow_icon_index, _workflow_menu_metadata = _build_workflow_indexes()
    return _workflow_category_index


def get_workflow_icon_index() -> Dict[str, str]:
    """Get menu_group → icon mapping (lazy, from workflow_engine)."""
    global _workflow_icon_index
    if _workflow_icon_index is None:
        get_workflow_category_index()  # builds all indexes
    return _workflow_icon_index


def get_workflow_menu_metadata() -> Dict[str, Dict[str, Any]]:
    """Get menu_group → {icon, title_key, has_appointments} (lazy, from workflow_engine)."""
    global _workflow_menu_metadata
    if _workflow_menu_metadata is None:
        get_workflow_category_index()  # builds all indexes
    return _workflow_menu_metadata


def invalidate_workflow_indexes() -> None:
    """Reset all indexes (call after workflow registration changes)."""
    global _workflow_category_index, _workflow_icon_index, _workflow_menu_metadata
    _workflow_category_index = None
    _workflow_icon_index = None
    _workflow_menu_metadata = None


class MenuConfigService:
    """Service for generating and managing menu configurations"""

    # NOTE: Module-based entities are now determined dynamically:
    # If role.menu_config IS NOT NULL → module-based (use role config)
    # Otherwise → workflow-based (generate from entity.workflow_codes)

    async def get_agent_menu_config(
        self,
        agent_profile_id: UUID,
        user_id: UUID,
        db_connection,
        use_cache: bool = True
    ) -> AgentMenuConfigResponse:
        """
        Get complete menu configuration for an agent.

        Process:
        1. Check cache first (if enabled)
        2. Fetch agent profile with entity and role info
        3. Determine if workflow-based or module-based
        4. Generate or fetch menu config accordingly
        5. Add common agent menus (stats, etc.)
        6. Merge with any agent-specific overrides
        7. Fetch dashboard config
        8. Include permissions for frontend filtering
        9. Cache the result

        Args:
            agent_profile_id: Agent profile UUID
            user_id: User UUID (for permissions)
            db_connection: Database connection
            use_cache: Whether to use cache (default: True)

        Returns:
            AgentMenuConfigResponse with all configuration
        """
        cache = get_menu_cache()
        cache_key = CacheKeys.agent_menu_config(str(agent_profile_id))

        # Check cache first
        if use_cache:
            cached = await cache.get(cache_key)
            if cached:
                logger.debug(f"Cache hit for agent menu config: {agent_profile_id}")
                # Reconstruct Pydantic model from cached dict (Redis returns dict, memory may return model)
                if isinstance(cached, dict):
                    try:
                        return AgentMenuConfigResponse.model_validate(cached)
                    except Exception as e:
                        logger.warning(f"Failed to validate cached menu config, rebuilding: {e}")
                elif isinstance(cached, AgentMenuConfigResponse):
                    return cached
                else:
                    logger.warning(f"Invalid cache type for menu config: {type(cached)}")

        # 1. Fetch agent profile with joins
        agent_data = await self._fetch_agent_with_details(agent_profile_id, db_connection)

        if not agent_data:
            raise ValueError(f"Agent profile not found: {agent_profile_id}")

        entity_code = agent_data.get('entity_code')
        entity_name = agent_data.get('entity_name')
        role_code = agent_data.get('role_code')
        role_menu_config = agent_data.get('role_menu_config')
        role_dashboard_config = agent_data.get('role_dashboard_config')
        agent_menu_overrides = agent_data.get('menu_overrides')
        agent_dashboard_overrides = agent_data.get('dashboard_overrides')
        available_workflows = agent_data.get('available_workflows', [])

        # 2. Determine entity type dynamically
        # Module-based: role has explicit menu_config (no workflow generation needed)
        # Workflow-based: generate menus from entity.workflow_codes
        is_module_based = role_menu_config is not None
        entity_type = "module" if is_module_based else "workflow"

        logger.debug(
            f"Agent {agent_profile_id}: entity={entity_code}, type={entity_type}, "
            f"role={role_code}, has_role_menu={role_menu_config is not None}, "
            f"workflows={available_workflows}"
        )

        # 3. Generate or fetch menu config
        if is_module_based:
            # Module-based: use role.menu_config directly
            menu_config = self._parse_menu_config(role_menu_config, "role", role_code=role_code)
            logger.debug(f"Using role menu_config for {role_code}")
        else:
            # Workflow-based: generate from workflows
            menu_config = await self._generate_workflow_menus(
                available_workflows,
                entity_code,
                db_connection,
                is_supervisor=agent_data.get('is_supervisor', False),
            )
            logger.debug(f"Generated workflow menus for entity: {entity_code}")

        # 4. Add common agent menus (stats, etc.) - applies to all entities
        menu_config = self._add_common_agent_menus(menu_config)

        # 5. Apply agent overrides if any
        if agent_menu_overrides:
            menu_config = self._apply_menu_overrides(menu_config, agent_menu_overrides)

        # 6. Get dashboard config
        if is_module_based and role_dashboard_config:
            dashboard_config = self._parse_dashboard_config(role_dashboard_config)
        else:
            dashboard_config = self._get_default_dashboard_config(entity_type)

        if agent_dashboard_overrides:
            dashboard_config = self._apply_dashboard_overrides(
                dashboard_config, agent_dashboard_overrides
            )

        # 7. Derive entity_icon from entity's workflow categories (100% dynamic)
        entity_icon = self._derive_entity_icon(available_workflows)

        # 8. Get user permissions
        perm_repo = UserPermissionRepository(db_connection)
        permissions = await perm_repo.get_all_permission_names(str(user_id))

        # 9. Fetch display configs for agent's workflows (P0-1)
        display_configs: Dict[str, Dict[str, Any]] = {}
        if available_workflows:
            try:
                from app.modules.menu_config.repositories.display_config_repository import DisplayConfigRepository
                display_repo = DisplayConfigRepository(db_connection)
                display_configs = await display_repo.find_configs_for_workflows(available_workflows)
            except Exception as e:
                logger.warning(f"Failed to fetch display configs: {e}")

        result = AgentMenuConfigResponse(
            agent_profile_id=agent_profile_id,
            entity_code=entity_code,
            entity_name=entity_name,
            entity_icon=entity_icon,
            entity_type=entity_type,
            role_code=role_code,
            available_workflows=available_workflows,
            menu_config=menu_config,
            dashboard_config=dashboard_config,
            is_supervisor=agent_data.get('is_supervisor', False),
            permissions=permissions,
            display_configs=display_configs,
            has_role_menu_config=role_menu_config is not None
        )

        # 8. Cache the result (5 min TTL)
        # Serialize to JSON-compatible dict so Redis json.dumps doesn't mangle Pydantic models
        if use_cache:
            await cache.set(cache_key, result.model_dump(mode='json'), ttl=300)
            logger.debug(f"Cached menu config for agent: {agent_profile_id}")

        return result

    async def _fetch_agent_with_details(
        self,
        agent_profile_id: UUID,
        db_connection
    ) -> Optional[Dict[str, Any]]:
        """Fetch agent profile with entity, role, and workflow details"""
        query = """
            SELECT
                ap.id,
                ap.user_id,
                ap.entity_id,
                ap.is_supervisor,
                ap.specializations,
                ap.menu_overrides,
                ap.dashboard_overrides,
                ap.entity_location_id,
                e.code as entity_code,
                e.name as entity_name,
                e.workflow_codes as entity_workflow_codes,
                r.code as role_code,
                r.menu_config as role_menu_config,
                r.dashboard_config as role_dashboard_config,
                u.role_id
            FROM agent_profiles ap
            LEFT JOIN entities e ON ap.entity_id = e.id
            LEFT JOIN users u ON ap.user_id = u.id
            LEFT JOIN roles r ON u.role_id = r.id
            WHERE ap.id = $1 AND ap.is_active = true
        """
        result = await db_connection.fetchrow(query, agent_profile_id)

        if not result:
            return None

        data = dict(result)

        # Parse JSONB fields (asyncpg may return strings for JSON columns)
        _ensure_json(data, 'specializations', default=[])
        _ensure_json(data, 'entity_workflow_codes', default=[])
        _ensure_json(data, 'role_menu_config')
        _ensure_json(data, 'role_dashboard_config')
        _ensure_json(data, 'menu_overrides')
        _ensure_json(data, 'dashboard_overrides')

        # Resolve available workflows
        # Specializations override entity workflows if defined
        specializations = data.get('specializations') or []
        entity_workflows = data.get('entity_workflow_codes') or []
        data['available_workflows'] = specializations if specializations else entity_workflows

        return data

    async def _generate_workflow_menus(
        self,
        workflows: List[str],
        entity_code: str,
        db_connection,
        is_supervisor: bool = False,
    ) -> MenuConfigResponse:
        """Generate menus from workflow codes using mapping rules"""

        if not workflows:
            logger.warning(f"No workflows found for entity {entity_code}")
            return self._get_default_menu_config("workflow")

        # Fetch mapping rules
        mappings = await self._fetch_workflow_mappings(db_connection)

        # Group workflows by category
        workflow_groups: Dict[str, List[str]] = {}
        for workflow_code in workflows:
            category = self._get_workflow_category(workflow_code)
            if category not in workflow_groups:
                workflow_groups[category] = []
            workflow_groups[category].append(workflow_code)

        # Generate menu items
        menus: List[MenuItemBase] = []
        entity_path = entity_code.lower().replace('_', '-') if entity_code else 'default'

        # Always add dashboard first
        menus.append(MenuItemBase(
            id="dashboard",
            titleKey="agent.nav.dashboard",
            href=f"/dashboard/agent/{entity_path}",
            icon="LayoutDashboard"
        ))

        # Track if any workflow group needs appointments or batch
        has_appointments = False
        has_batch = False

        # Generate menu for each workflow group
        for category, category_workflows in sorted(workflow_groups.items()):
            mapping = self._find_mapping_for_category(category, mappings)

            if mapping:
                menu_item = self._create_menu_from_mapping(
                    mapping,
                    category_workflows,
                    entity_code
                )
                menus.append(menu_item)
                # Check if this group needs appointments
                if mapping.get('include_appointments', False):
                    has_appointments = True
                if mapping.get('include_batch', False):
                    has_batch = True
            else:
                # Default menu generation
                menu_item = self._create_default_menu(
                    category,
                    category_workflows,
                    entity_code
                )
                menus.append(menu_item)

        # Add appointments as SEPARATE top-level menu (not submenu)
        # Path: /dashboard/agent/{entity}/appointments (matches original JSON structure)
        if has_appointments:
            menus.append(MenuItemBase(
                id="appointments",
                titleKey="agent.nav.appointments",
                href=f"/dashboard/agent/{entity_path}/appointments",
                icon="Calendar",
                permission="service_request.view_appointments"
            ))

        # Add batch requests as SEPARATE top-level menu
        # Path: /dashboard/agent/{entity}/batch-requests
        if has_batch:
            menus.append(MenuItemBase(
                id="batch-requests",
                titleKey="agent.nav.batchRequests",
                href=f"/dashboard/agent/{entity_path}/batch-requests",
                icon="Layers",
                permission="service_request.view_batch"
            ))

        # Add supervisor section if is_supervisor
        if is_supervisor:
            menus.extend(self._get_supervisor_menu_items())

        return MenuConfigResponse(
            version="1.0",
            source="workflow",
            menus=menus
        )

    def _get_supervisor_menu_items(self) -> List[MenuItemBase]:
        """Generate supervisor-specific menu items for entity supervisors.

        These items are appended to workflow-based menus when the agent
        has is_supervisor=true, providing team management, escalations,
        assignment rules and reporting tools.
        """
        return [
            MenuItemBase(
                id="supervisor-dashboard",
                titleKey="supervisor.nav.dashboard",
                href="/dashboard/supervisor",
                icon="LayoutDashboard",
            ),
            MenuItemBase(
                id="supervisor-team",
                titleKey="supervisor.nav.team",
                icon="Users",
                items=[
                    SubMenuItemWithBadge(
                        id="agents",
                        titleKey="supervisor.nav.agents",
                        href="/dashboard/supervisor/team/agents",
                        icon="User",
                        permission="agent.view",
                    ),
                    SubMenuItemWithBadge(
                        id="workload",
                        titleKey="supervisor.nav.workloadBalance",
                        href="/dashboard/supervisor/team/workload",
                        icon="BarChart2",
                        permission="agent.view_workload",
                    ),
                    SubMenuItemWithBadge(
                        id="performance",
                        titleKey="supervisor.nav.performance",
                        href="/dashboard/supervisor/team/performance",
                        icon="TrendingUp",
                        permission="agent.view_performance",
                    ),
                ],
            ),
            MenuItemBase(
                id="supervisor-escalations",
                titleKey="supervisor.nav.escalations",
                icon="AlertTriangle",
                items=[
                    SubMenuItemWithBadge(
                        id="pending",
                        titleKey="supervisor.nav.pendingEscalations",
                        href="/dashboard/supervisor/escalations/pending",
                        icon="Clock",
                        permission="queue.escalate",
                    ),
                    SubMenuItemWithBadge(
                        id="resolved",
                        titleKey="supervisor.nav.resolvedEscalations",
                        href="/dashboard/supervisor/escalations/resolved",
                        icon="CheckCircle",
                        permission="queue.view",
                    ),
                ],
            ),
            MenuItemBase(
                id="supervisor-assignments",
                titleKey="supervisor.nav.assignments",
                icon="Settings2",
                items=[
                    SubMenuItemWithBadge(
                        id="manual",
                        titleKey="supervisor.nav.manualAssignment",
                        href="/dashboard/supervisor/assignments/manual",
                        icon="UserPlus",
                        permission="assignment.create",
                    ),
                    SubMenuItemWithBadge(
                        id="list",
                        titleKey="supervisor.nav.assignmentsList",
                        href="/dashboard/supervisor/assignments/manual?tab=active",
                        icon="ClipboardList",
                        permission="assignment.list",
                    ),
                    SubMenuItemWithBadge(
                        id="rules",
                        titleKey="supervisor.nav.rules",
                        href="/dashboard/supervisor/assignments/rules",
                        icon="ListChecks",
                        permission="rules.view",
                    ),
                ],
            ),
            MenuItemBase(
                id="supervisor-reports",
                titleKey="supervisor.nav.reports",
                href="/dashboard/supervisor/reports",
                icon="FileBarChart",
                permission="reports.view",
            ),
        ]

    def _derive_entity_icon(self, workflow_codes: List[str]) -> Optional[str]:
        """
        Derive entity icon from its workflow codes.

        Uses the dynamic workflow indexes: workflow_code → menu_group → icon.
        Returns the icon of the first workflow's category. 100% dynamic.
        """
        if not workflow_codes:
            return None
        category_index = get_workflow_category_index()
        icon_index = get_workflow_icon_index()
        for code in workflow_codes:
            menu_group = category_index.get(code)
            if menu_group:
                icon = icon_index.get(menu_group)
                if icon:
                    return icon
        return None

    def _get_workflow_category(self, workflow_code: str) -> str:
        """Get menu category from workflow registry (dynamic)."""
        index = get_workflow_category_index()
        if workflow_code in index:
            return index[workflow_code]
        logger.warning(
            f"Workflow code '{workflow_code}' not found in registry. "
            f"Register it in workflow_engine to enable dynamic menu generation."
        )
        return workflow_code

    async def _fetch_workflow_mappings(self, db_connection) -> List[Dict]:
        """Fetch all active workflow menu mappings (cached for 30 min)"""
        cache = get_workflow_mappings_cache()
        cache_key = CacheKeys.workflow_mappings()

        # Check cache first
        cached = await cache.get(cache_key)
        if cached:
            logger.debug("Cache hit for workflow mappings")
            return cached

        # Fetch from database
        query = """
            SELECT * FROM workflow_menu_mapping
            WHERE is_active = true
            ORDER BY display_order
        """
        results = await db_connection.fetch(query)
        mappings = [dict(r) for r in results]

        # Cache for 30 minutes (workflow mappings rarely change)
        await cache.set(cache_key, mappings, ttl=1800)
        logger.debug(f"Cached {len(mappings)} workflow mappings")

        return mappings

    def _find_mapping_for_category(
        self,
        category: str,
        mappings: List[Dict]
    ) -> Optional[Dict]:
        """Find mapping rule for a workflow category (exact match first, then prefix)."""
        # Pass 1: exact match (e.g. VISADO == VISADO from VISADO_%)
        for mapping in mappings:
            pattern = mapping['workflow_pattern'].replace('%', '').rstrip('_')
            if category == pattern:
                return mapping
        # Pass 2: prefix match (e.g. PASAPORTE startsWith PASAPORTE)
        for mapping in mappings:
            pattern = mapping['workflow_pattern'].replace('%', '').rstrip('_')
            if category.startswith(pattern):
                return mapping
        return None

    def _create_menu_from_mapping(
        self,
        mapping: Dict,
        workflows: List[str],
        entity_code: str
    ) -> MenuItemBase:
        """Create menu item from mapping rule"""
        # Convert underscores to hyphens for URL paths (e.g., CNEDOGE_PASAPORTE -> cnedoge-pasaporte)
        entity_path = entity_code.lower().replace('_', '-') if entity_code else 'default'
        base_path = f"/dashboard/agent/{entity_path}/{mapping['menu_group_id']}"
        permission_prefix = mapping.get('permission_prefix', 'service_requests')

        items: List[SubMenuItemWithBadge] = []

        if mapping.get('include_pending', True):
            items.append(SubMenuItemWithBadge(
                id="pending",
                titleKey="agent.nav.pending",
                href=f"{base_path}/pending",
                icon="Clock",
                permission=f"{permission_prefix}.view_queue",
                badge=MenuBadgeConfig(type="count", source="pending_count")
            ))

        if mapping.get('include_validation', True):
            items.append(SubMenuItemWithBadge(
                id="validation",
                titleKey="agent.nav.validation",
                href=f"{base_path}/validation",
                icon="CheckCircle",
                permission=f"{permission_prefix}.process"
            ))

        # NOTE: Appointments is now added as a SEPARATE top-level menu in _generate_workflow_menus()
        # This ensures the path is /dashboard/agent/{entity}/appointments (not /dashboard/agent/{entity}/{group}/appointments)

        if mapping.get('include_history', True):
            items.append(SubMenuItemWithBadge(
                id="history",
                titleKey="agent.nav.history",
                href=f"{base_path}/history",
                icon="History",
                permission=f"{permission_prefix}.view"
            ))

        if mapping.get('include_escalation', True):
            items.append(SubMenuItemWithBadge(
                id="escalations",
                titleKey="agent.nav.escalations",
                href=f"{base_path}/escalations",
                icon="AlertTriangle",
                permission=f"{permission_prefix}.view_escalations"
            ))

        # Custom sub-items from JSONB (dynamic, admin-configurable)
        custom_items = mapping.get('custom_sub_items', [])
        if isinstance(custom_items, str):
            import json
            custom_items = json.loads(custom_items)

        # Sort custom items by display_order
        sorted_custom = sorted(
            [ci for ci in custom_items if ci.get('is_active', True)],
            key=lambda x: x.get('display_order', 0)
        )
        for ci in sorted_custom:
            filter_params = ci.get('filter_params', {})
            query_string = '&'.join(f"{k}={v}" for k, v in filter_params.items()) if filter_params else ''
            href = f"{base_path}/{ci['action']}"
            if query_string:
                href += f"?{query_string}"

            items.append(SubMenuItemWithBadge(
                id=ci['id'],
                titleKey=ci['title_key'],
                href=href,
                icon=ci.get('icon', 'FileText'),
                permission=f"{permission_prefix}.view"
            ))

        return MenuItemBase(
            id=mapping['menu_group_id'],
            titleKey=mapping['menu_title_key'],
            icon=mapping['menu_icon'],
            permission=f"{permission_prefix}.view",
            items=items
        )

    def _create_default_menu(
        self,
        category: str,
        workflows: List[str],
        entity_code: str
    ) -> MenuItemBase:
        """Create default menu for unmapped workflow category"""
        menu_id = category.lower()
        # Convert underscores to hyphens for URL paths
        entity_path = entity_code.lower().replace('_', '-') if entity_code else 'default'
        base_path = f"/dashboard/agent/{entity_path}/{menu_id}"
        # Dynamic icon lookup from workflow_engine registry
        icon_index = get_workflow_icon_index()
        icon = icon_index.get(category)
        if not icon:
            logger.warning(
                f"No icon found for category '{category}' in workflow registry. "
                f"Register it via PredefinedWorkflow.menu_icon."
            )
            icon = 'FileText'

        # Dynamic title key from workflow_engine registry
        metadata = get_workflow_menu_metadata().get(category)
        if metadata:
            title_key = metadata["title_key"]
        else:
            logger.warning(
                f"No menu metadata found for category '{category}' in workflow registry. "
                f"Register it via PredefinedWorkflow.menu_title_key."
            )
            title_key = f"agent.nav.{menu_id}"

        return MenuItemBase(
            id=menu_id,
            titleKey=title_key,
            icon=icon,
            permission="service_request.view",
            items=[
                SubMenuItemWithBadge(
                    id="pending",
                    titleKey="agent.nav.pending",
                    href=f"{base_path}/pending",
                    icon="Clock",
                    permission="service_request.view_queue"
                ),
                SubMenuItemWithBadge(
                    id="validation",
                    titleKey="agent.nav.validation",
                    href=f"{base_path}/validation",
                    icon="CheckCircle",
                    permission="service_request.process"
                ),
                SubMenuItemWithBadge(
                    id="history",
                    titleKey="agent.nav.history",
                    href=f"{base_path}/history",
                    icon="History",
                    permission="service_request.view"
                )
            ]
        )

    def _parse_menu_config(
        self,
        config: Optional[Dict],
        source: str,
        role_code: Optional[str] = None
    ) -> MenuConfigResponse:
        """
        Parse and validate menu config from JSON.

        Uses Pydantic models for validation with detailed error logging.
        Falls back to default config if validation fails.

        Args:
            config: Raw menu config dict from DB
            source: Menu source type (workflow, role, custom)
            role_code: Role code for error context
        """
        if not config:
            return self._get_default_menu_config(source)

        # Validate required structure
        if not isinstance(config, dict):
            logger.error(
                f"[MenuConfig Validation] Invalid config type for role={role_code}: "
                f"expected dict, got {type(config).__name__}"
            )
            return self._get_default_menu_config(source)

        if 'menus' not in config or not isinstance(config.get('menus'), list):
            logger.error(
                f"[MenuConfig Validation] Missing or invalid 'menus' array for role={role_code}. "
                f"Config keys: {list(config.keys())}"
            )
            return self._get_default_menu_config(source)

        try:
            # Parse and validate each menu item with Pydantic
            menus = []
            for idx, menu_data in enumerate(config.get('menus', [])):
                try:
                    items = None
                    if menu_data.get('items'):
                        items = []
                        for item_idx, item in enumerate(menu_data['items']):
                            try:
                                items.append(SubMenuItemWithBadge(
                                    id=item['id'],
                                    titleKey=item['titleKey'],
                                    href=item['href'],
                                    icon=item['icon'],
                                    permission=item.get('permission'),
                                    badge=MenuBadgeConfig(**item['badge']) if item.get('badge') else None
                                ))
                            except Exception as item_err:
                                logger.warning(
                                    f"[MenuConfig Validation] Invalid sub-item at menus[{idx}].items[{item_idx}] "
                                    f"for role={role_code}: {item_err}. Item data: {item}"
                                )
                                # Continue with other items

                    menus.append(MenuItemBase(
                        id=menu_data['id'],
                        titleKey=menu_data['titleKey'],
                        icon=menu_data['icon'],
                        href=menu_data.get('href'),
                        permission=menu_data.get('permission'),
                        items=items
                    ))
                except Exception as menu_err:
                    logger.warning(
                        f"[MenuConfig Validation] Invalid menu at index {idx} for role={role_code}: "
                        f"{menu_err}. Menu data: {menu_data}"
                    )
                    # Continue with other menus

            if not menus:
                logger.error(
                    f"[MenuConfig Validation] No valid menus parsed for role={role_code}. "
                    f"Original had {len(config.get('menus', []))} items."
                )
                return self._get_default_menu_config(source)

            logger.debug(
                f"[MenuConfig Validation] ✓ Parsed {len(menus)} menus for role={role_code}"
            )

            return MenuConfigResponse(
                version=config.get('version', '1.0'),
                source=config.get('source', source),
                menus=menus
            )
        except Exception as e:
            logger.error(
                f"[MenuConfig Validation] Unexpected error parsing config for role={role_code}: {e}"
            )
            return self._get_default_menu_config(source)

    def _get_default_menu_config(self, source: str) -> MenuConfigResponse:
        """Return default menu config"""
        return MenuConfigResponse(
            version="1.0",
            source=source,
            menus=[
                MenuItemBase(
                    id="dashboard",
                    titleKey="agent.nav.dashboard",
                    href="/dashboard/agent",
                    icon="LayoutDashboard"
                )
            ]
        )

    def _parse_dashboard_config(
        self,
        config: Optional[Dict]
    ) -> DashboardConfigResponse:
        """Parse dashboard config from JSON"""
        if not config:
            return self._get_default_dashboard_config("module")

        try:
            widgets = [
                WidgetConfigBase(
                    id=w['id'],
                    visible=w.get('visible', True),
                    position=w.get('position', 1),
                    size=w.get('size', 'medium'),
                    customConfig=w.get('customConfig')
                )
                for w in config.get('widgets', [])
            ]

            return DashboardConfigResponse(
                version=config.get('version', '1.0'),
                layout=config.get('layout', 'grid'),
                widgets=widgets
            )
        except Exception as e:
            logger.error(f"Failed to parse dashboard config: {e}")
            return self._get_default_dashboard_config("module")

    def _get_default_dashboard_config(self, entity_type: str) -> DashboardConfigResponse:
        """Return default dashboard config based on entity type"""
        if entity_type == "workflow":
            # Widget IDs must match frontend components
            widgets = [
                WidgetConfigBase(id="alerts", visible=True, position=1, size="medium"),
                WidgetConfigBase(id="urgent_requests", visible=True, position=2, size="medium"),
                WidgetConfigBase(id="calendar_slots", visible=True, position=3, size="full"),
                WidgetConfigBase(id="today_appointments", visible=True, position=4, size="medium"),
                WidgetConfigBase(id="workflow_distribution", visible=True, position=5, size="medium"),
            ]
        else:
            # Module-based entities (TESORO, etc.)
            widgets = [
                WidgetConfigBase(id="stats_card", visible=True, position=1, size="medium"),
                WidgetConfigBase(id="recent_activity", visible=True, position=2, size="large"),
            ]

        return DashboardConfigResponse(
            version="1.0",
            layout="grid",
            widgets=widgets
        )

    def _add_common_agent_menus(
        self,
        menu_config: MenuConfigResponse
    ) -> MenuConfigResponse:
        """
        Add common menu items that apply to all agents regardless of entity type.

        Currently adds:
        - My Stats: Personal performance statistics page

        These are added at the end of the menu list.
        """
        # Check if stats menu already exists (to avoid duplicates)
        existing_ids = {menu.id for menu in menu_config.menus}
        if 'my-stats' in existing_ids:
            return menu_config

        # Add My Stats menu
        stats_menu = MenuItemBase(
            id="my-stats",
            titleKey="agent.stats.title",
            href="/dashboard/agent/stats",
            icon="BarChart3",
            permission="agent.view_performance"
        )

        # Insert stats menu after dashboard (position 1) if dashboard exists
        updated_menus = list(menu_config.menus)
        if updated_menus and updated_menus[0].id == "dashboard":
            updated_menus.insert(1, stats_menu)
        else:
            updated_menus.append(stats_menu)

        return MenuConfigResponse(
            version=menu_config.version,
            source=menu_config.source,
            menus=updated_menus
        )

    def _apply_menu_overrides(
        self,
        menu_config: MenuConfigResponse,
        overrides: Dict
    ) -> MenuConfigResponse:
        """
        Apply agent-specific menu overrides.

        Supports:
        - hidden_menus: List of menu IDs to hide
        - additional_menus: List of menu items to add
        """
        if not overrides:
            return menu_config

        # Get hidden menus
        hidden_menus = set(overrides.get('hidden_menus', []))

        # Filter out hidden menus
        filtered_menus = [
            menu for menu in menu_config.menus
            if menu.id not in hidden_menus
        ]

        # Add additional menus if any
        additional = overrides.get('additional_menus', [])
        for menu_data in additional:
            try:
                items = None
                if menu_data.get('items'):
                    items = [
                        SubMenuItemWithBadge(**item)
                        for item in menu_data['items']
                    ]
                filtered_menus.append(MenuItemBase(
                    id=menu_data['id'],
                    titleKey=menu_data['titleKey'],
                    icon=menu_data['icon'],
                    href=menu_data.get('href'),
                    permission=menu_data.get('permission'),
                    items=items
                ))
            except Exception as e:
                logger.warning(f"Failed to add additional menu: {e}")

        return MenuConfigResponse(
            version=menu_config.version,
            source="custom",  # Mark as custom since overrides were applied
            menus=filtered_menus
        )

    def _apply_dashboard_overrides(
        self,
        dashboard_config: DashboardConfigResponse,
        overrides: Dict
    ) -> DashboardConfigResponse:
        """
        Apply agent-specific dashboard overrides.

        Supports:
        - hidden_widgets: List of widget IDs to hide
        - widget_positions: Dict of widget_id -> new position
        """
        if not overrides:
            return dashboard_config

        hidden_widgets = set(overrides.get('hidden_widgets', []))
        widget_positions = overrides.get('widget_positions', {})

        # Filter and update widgets
        updated_widgets = []
        for widget in dashboard_config.widgets:
            if widget.id in hidden_widgets:
                continue

            # Update position if specified
            new_position = widget_positions.get(widget.id, widget.position)
            updated_widgets.append(WidgetConfigBase(
                id=widget.id,
                visible=widget.visible,
                position=new_position,
                size=widget.size,
                customConfig=widget.customConfig
            ))

        # Sort by position
        updated_widgets.sort(key=lambda w: w.position)

        return DashboardConfigResponse(
            version=dashboard_config.version,
            layout=dashboard_config.layout,
            widgets=updated_widgets
        )


# Singleton instance
_menu_config_service: Optional[MenuConfigService] = None


def get_menu_config_service() -> MenuConfigService:
    """Get menu config service singleton"""
    global _menu_config_service
    if _menu_config_service is None:
        _menu_config_service = MenuConfigService()
    return _menu_config_service
