"""
Module Permissions - Centralized Permission Definitions

This package contains permission definitions for all modules.
Each module has its own *_permissions.py file that defines:
- PERMISSIONS: List of (name, resource, action, description, is_critical) tuples
- MODULE_NAME: String identifier for the module
- ROLE_PERMISSIONS: (Optional) Dict mapping role codes to permission lists

Permissions are auto-registered at application startup and synced to the database.
Role-permission mappings are also auto-synced if ROLE_PERMISSIONS is defined.

Naming Convention:
    - Format: {resource_singular}.{action}
    - Examples: agent.create, assignment.view, service_request.approve
    - NEVER use plural (agents.create) or colon (agent:create)
"""

import importlib.util
from pathlib import Path
from typing import Dict, List, Tuple
from loguru import logger

from ..services.permission_registry import PermissionRegistry


def discover_and_register_permissions() -> Dict[str, int]:
    """
    Discover all *_permissions.py files and register their permissions.

    Also collects ROLE_PERMISSIONS mappings for auto-sync to database.

    Returns:
        Dict with module names and permission counts
    """
    registered = {}
    module_permissions_dir = Path(__file__).parent

    for permission_file in module_permissions_dir.glob("*_permissions.py"):
        if permission_file.name.startswith("_"):
            continue

        module_name = permission_file.stem  # e.g., "agent_permissions"

        try:
            # Load the module dynamically
            spec = importlib.util.spec_from_file_location(
                module_name,
                permission_file
            )
            if spec is None or spec.loader is None:
                logger.warning(f"Could not load spec for {module_name}")
                continue

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Check required attributes
            if not hasattr(module, "PERMISSIONS") or not hasattr(module, "MODULE_NAME"):
                logger.warning(
                    f"Skipping {module_name}: missing PERMISSIONS or MODULE_NAME"
                )
                continue

            # Validate permission format
            _validate_permissions(module.MODULE_NAME, module.PERMISSIONS)

            # Register permissions with the central registry
            PermissionRegistry.register_module_permissions(
                module_name=module.MODULE_NAME,
                permissions=module.PERMISSIONS
            )

            # Register role-permission mappings if defined
            if hasattr(module, "ROLE_PERMISSIONS"):
                PermissionRegistry.register_role_permissions(
                    module_name=module.MODULE_NAME,
                    role_permissions=module.ROLE_PERMISSIONS
                )
                logger.info(
                    f"   └─ Registered ROLE_PERMISSIONS for {len(module.ROLE_PERMISSIONS)} roles"
                )

            registered[module.MODULE_NAME] = len(module.PERMISSIONS)
            logger.info(
                f"✅ Registered {len(module.PERMISSIONS)} permissions "
                f"for module '{module.MODULE_NAME}'"
            )

        except Exception as e:
            logger.error(f"❌ Failed to load permissions from {module_name}: {e}")
            import traceback
            logger.error(traceback.format_exc())

    return registered


def _validate_permissions(
    module_name: str,
    permissions: List[Tuple[str, str, str, str, bool]]
) -> None:
    """
    Validate permission naming conventions.

    Raises:
        ValueError: If any permission has invalid format
    """
    for perm in permissions:
        name, resource, action, description, is_critical = perm

        # Check format: resource.action
        if ":" in name:
            raise ValueError(
                f"Invalid permission name '{name}' in module '{module_name}': "
                f"Use dot notation (resource.action), not colon (resource:action)"
            )

        parts = name.split(".")
        if len(parts) != 2:
            raise ValueError(
                f"Invalid permission name '{name}' in module '{module_name}': "
                f"Must be exactly 'resource.action'"
            )

        # Check singular (warn if plural)
        # Exception list: system resources and words naturally ending in 's'
        PLURAL_EXCEPTIONS = (
            "status", "process", "address",
            # System RBAC resources (by convention use plural)
            "permissions", "roles", "user_permissions",
        )
        if parts[0].endswith("s") and parts[0] not in PLURAL_EXCEPTIONS:
            # Common plurals that should be singular
            logger.warning(
                f"Permission '{name}' may use plural resource. "
                f"Convention is singular (e.g., 'agent' not 'agents')"
            )


# Export for module introspection
__all__ = ["discover_and_register_permissions"]

# Auto-discovery at import time
# This runs when the module is imported, ensuring all permissions are registered
_registered_modules = discover_and_register_permissions()
