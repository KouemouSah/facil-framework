"""
Permission Registry - Central registry for module permissions

This module provides:
- Permission registration from module files
- Role-permission mapping registration
- Auto-sync to database at startup
"""
from typing import List, Dict, Tuple, Optional, Set, Any
import logging

from app.modules.permissions.repositories.permission_repository import PermissionRepository
from app.modules.permissions.repositories.role_repository import RoleRepository
from app.modules.permissions.models.permission import PermissionCreate

logger = logging.getLogger(__name__)


class PermissionRegistry:
    """
    Central registry for permissions and role-permission mappings

    Modules can register their permissions at startup using this registry.
    The registry will then sync permissions to the database.

    Also handles ROLE_PERMISSIONS mappings to auto-assign permissions to roles.
    """

    # Class-level storage for registered permissions
    _registered_permissions: Dict[str, List[Tuple]] = {}

    # Class-level storage for role-permission mappings
    # Format: {module_name: {role_code: [permission_names]}}
    _registered_role_permissions: Dict[str, Dict[str, List[str]]] = {}

    @classmethod
    def register_module_permissions(
        cls,
        module_name: str,
        permissions: List[Tuple[str, str, str, str, bool]]
    ):
        """
        Register permissions for a module

        This should be called in the module's __init__.py file.

        Args:
            module_name: Name of the module (e.g., "assignment", "declarations")
            permissions: List of tuples (name, resource, action, description, is_critical)

        Example:
            ```python
            # In app/modules/assignment/__init__.py
            from app.modules.permissions.services.permission_registry import PermissionRegistry

            ASSIGNMENT_PERMISSIONS = [
                ("assignment.view", "assignment", "view", "Ver asignaciones", False),
                ("assignment.create", "assignment", "create", "Crear asignación", False),
                ("assignment.reassign_in_progress", "assignment", "reassign_in_progress",
                 "Reasignar tarea EN CURSO", True),
            ]

            PermissionRegistry.register_module_permissions("assignment", ASSIGNMENT_PERMISSIONS)
            ```
        """
        if module_name in cls._registered_permissions:
            logger.warning(f"Module '{module_name}' permissions already registered, overwriting")

        cls._registered_permissions[module_name] = permissions
        logger.info(f"Registered {len(permissions)} permissions for module '{module_name}'")

    @classmethod
    def register_role_permissions(
        cls,
        module_name: str,
        role_permissions: Dict[str, List[str]]
    ):
        """
        Register role-permission mappings for a module

        This should be called after register_module_permissions.

        Args:
            module_name: Name of the module (e.g., "treasury")
            role_permissions: Dict mapping role codes to permission name lists

        Example:
            ```python
            ROLE_PERMISSIONS = {
                "agent_tesoro": [
                    "treasury.view_payment",
                    "treasury.validate_payment",
                ],
                "supervisor_tesoro": [
                    "treasury.view_payment",
                    "treasury.validate_payment",
                    "treasury.manage_settings",
                ],
            }

            PermissionRegistry.register_role_permissions("treasury", ROLE_PERMISSIONS)
            ```
        """
        if module_name in cls._registered_role_permissions:
            # Merge with existing mappings
            existing = cls._registered_role_permissions[module_name]
            for role_code, perms in role_permissions.items():
                if role_code in existing:
                    # Extend existing list, avoiding duplicates
                    existing[role_code] = list(set(existing[role_code] + perms))
                else:
                    existing[role_code] = perms
            logger.info(f"Merged role_permissions for module '{module_name}'")
        else:
            cls._registered_role_permissions[module_name] = role_permissions
            logger.info(
                f"Registered role_permissions for {len(role_permissions)} roles "
                f"in module '{module_name}'"
            )

    @classmethod
    def get_registered_permissions(cls) -> Dict[str, List[Tuple]]:
        """
        Get all registered permissions

        Returns:
            Dict with module names as keys and permission lists as values
        """
        return cls._registered_permissions.copy()

    @classmethod
    def get_module_permissions(cls, module_name: str) -> List[Tuple]:
        """
        Get permissions for a specific module

        Args:
            module_name: Module name

        Returns:
            List of permission tuples or empty list if not found
        """
        return cls._registered_permissions.get(module_name, [])

    @classmethod
    def get_all_permission_names(cls) -> List[str]:
        """
        Get all registered permission names

        Returns:
            List of permission names (e.g., ["assignment.view", "assignment.create", ...])
        """
        names = []
        for permissions in cls._registered_permissions.values():
            for perm in permissions:
                names.append(perm[0])  # perm[0] is the name
        return names

    @classmethod
    async def sync_to_database(cls, db_connection) -> Dict[str, int]:
        """
        Sync all registered permissions to the database

        This should be called at application startup to ensure all permissions
        are present in the database.

        Args:
            db_connection: Database connection

        Returns:
            Dict with sync statistics (created_count, skipped_count, total_count)
        """
        permission_repo = PermissionRepository(db_connection)

        permission_objects = []
        for module_name, permissions in cls._registered_permissions.items():
            for perm in permissions:
                name, resource, action, description, is_critical = perm
                permission_objects.append(
                    PermissionCreate(
                        name=name,
                        resource=resource,
                        action=action,
                        description=description,
                        is_critical=is_critical,
                        module_name=module_name
                    )
                )

        # Bulk create (skips duplicates)
        created = await permission_repo.bulk_create(permission_objects)

        total_count = len(permission_objects)
        created_count = len(created)
        skipped_count = total_count - created_count

        logger.info(
            f"Permission sync completed: {created_count} created, "
            f"{skipped_count} skipped, {total_count} total"
        )

        return {
            "created_count": created_count,
            "skipped_count": skipped_count,
            "total_count": total_count
        }

    @classmethod
    def get_all_role_permissions(cls) -> Dict[str, List[str]]:
        """
        Get aggregated role-permission mappings from all modules

        Returns:
            Dict mapping role_code to list of permission names
        """
        aggregated: Dict[str, Set[str]] = {}

        for module_name, role_perms in cls._registered_role_permissions.items():
            for role_code, perm_names in role_perms.items():
                if role_code == "admin" and perm_names == ["*"]:
                    # Skip wildcard admin - admin gets all permissions separately
                    continue

                if role_code not in aggregated:
                    aggregated[role_code] = set()

                aggregated[role_code].update(perm_names)

        # Convert sets to lists for return
        return {role: list(perms) for role, perms in aggregated.items()}

    @classmethod
    async def sync_role_permissions_to_database(cls, db_connection) -> Dict[str, int]:
        """
        Sync all registered role-permission mappings to the database

        This should be called after sync_to_database to ensure permissions exist.

        Args:
            db_connection: Database connection

        Returns:
            Dict with sync statistics (roles_updated, permissions_assigned, skipped)
        """
        role_repo = RoleRepository(db_connection)
        permission_repo = PermissionRepository(db_connection)

        roles_updated = 0
        permissions_assigned = 0
        skipped = 0
        errors = []

        # Get all role-permission mappings
        all_role_perms = cls.get_all_role_permissions()

        logger.info(f"Syncing role_permissions for {len(all_role_perms)} roles...")

        # Set session user for audit trigger (audit_role_permissions_change)
        # Without this, the trigger uses 00000000-... which violates FK on users
        try:
            admin_row = await db_connection.fetchrow(
                "SELECT id FROM users WHERE role = 'admin' LIMIT 1"
            )
            if admin_row:
                await db_connection.execute(
                    f"SET LOCAL app.current_user_id = '{admin_row['id']}'"
                )
        except Exception:
            pass  # Best effort — trigger may still fail on some DBs

        for role_code, permission_names in all_role_perms.items():
            try:
                # Get role by code
                role = await role_repo.get_by_code(role_code)
                if not role:
                    logger.warning(f"Role '{role_code}' not found in database, skipping")
                    skipped += len(permission_names)
                    continue

                role_id = str(role['id'])
                role_updated = False

                # Assign each permission
                for perm_name in permission_names:
                    try:
                        # Get permission by name
                        permission = await permission_repo.get_by_name(perm_name)
                        if not permission:
                            logger.warning(
                                f"Permission '{perm_name}' not found for role '{role_code}'"
                            )
                            skipped += 1
                            continue

                        permission_id = str(permission['id'])

                        # Assign permission to role (uses ON CONFLICT DO UPDATE)
                        await role_repo.assign_permission(
                            role_id=role_id,
                            permission_id=permission_id,
                            granted=True,
                            created_by=None  # System assignment
                        )
                        permissions_assigned += 1
                        role_updated = True

                    except Exception as e:
                        logger.error(
                            f"Error assigning '{perm_name}' to '{role_code}': {e}"
                        )
                        errors.append(f"{role_code}.{perm_name}: {str(e)}")
                        skipped += 1

                if role_updated:
                    roles_updated += 1

            except Exception as e:
                logger.error(f"Error processing role '{role_code}': {e}")
                errors.append(f"{role_code}: {str(e)}")
                skipped += len(permission_names)

        logger.info(
            f"Role permission sync completed: {roles_updated} roles updated, "
            f"{permissions_assigned} permissions assigned, {skipped} skipped"
        )

        if errors:
            logger.warning(f"Sync errors: {errors[:5]}{'...' if len(errors) > 5 else ''}")

        return {
            "roles_updated": roles_updated,
            "permissions_assigned": permissions_assigned,
            "skipped": skipped,
            "errors": errors[:10]  # Return first 10 errors
        }

    @classmethod
    def clear_registry(cls):
        """
        Clear all registered permissions and role mappings

        This is mainly useful for testing.
        """
        cls._registered_permissions.clear()
        cls._registered_role_permissions.clear()
        logger.info("Permission registry cleared (permissions and role mappings)")

    @classmethod
    def get_stats(cls) -> Dict[str, int]:
        """
        Get statistics about registered permissions and role mappings

        Returns:
            Dict with module_count, permission_count, role_count, role_permission_count
        """
        module_count = len(cls._registered_permissions)
        permission_count = sum(
            len(perms) for perms in cls._registered_permissions.values()
        )

        # Count unique roles and total role-permission mappings
        all_role_perms = cls.get_all_role_permissions()
        role_count = len(all_role_perms)
        role_permission_count = sum(
            len(perms) for perms in all_role_perms.values()
        )

        return {
            "module_count": module_count,
            "permission_count": permission_count,
            "role_count": role_count,
            "role_permission_count": role_permission_count
        }


# Convenience function for checking if a permission is registered
def is_permission_registered(permission_name: str) -> bool:
    """
    Check if a permission name is registered

    Args:
        permission_name: Permission name to check

    Returns:
        True if registered, False otherwise
    """
    return permission_name in PermissionRegistry.get_all_permission_names()


# Function to be called at application startup
async def initialize_permissions(
    db_connection,
    sync_role_permissions: bool = True,
    cleanup_obsolete: bool = False,
    report_obsolete: bool = True,
):
    """
    Initialize permissions at application startup.

    This function:
    1. Loads all module permissions from the registry
    2. Syncs them to the database (permissions table) — UPSERT only, never DELETE
    3. Syncs role-permission mappings to the database (role_permissions table)
    4. Optionally REPORTS obsolete permissions in BD that aren't in the code registry
    5. Optionally DELETES obsolete permissions (DESTRUCTIVE — opt-in only)

    ⚠️ DEFAULT BEHAVIOR (2026-05-04 change) — cleanup_obsolete=False
    --------------------------------------------------------------
    Until 2026-05-04, cleanup_obsolete defaulted to True. This meant any
    permission inserted by a SQL migration but not mirrored in a
    *_permissions.py registry file was DELETED at every app boot.
    Concretely, migrations 316 (dashboards.view_business) and 317
    (dashboards.manage) survived 0 boots because the code registry didn't
    list them.

    The new default is False: boot is non-destructive. New permissions
    introduced by migration are PRESERVED even if no developer has yet
    added the corresponding *_permissions.py entry. Developers can still
    add the entry later (best practice: every BD permission should have
    a code mirror so the role_permissions can be reconciled).

    To actually clean up obsolete permissions, run the explicit CLI:
        python -m app.scripts.cleanup_obsolete_permissions [--dry-run] [--apply]

    Args:
        db_connection: Database connection.
        sync_role_permissions: Whether to UPSERT role-permission mappings
            (default: True). Always non-destructive — only adds rows, never
            removes.
        cleanup_obsolete: If True, DELETE permissions in BD that are not in
            the code registry (default: **False** — opt-in only). Use only
            from the dedicated CLI; never from boot.
        report_obsolete: If True (default), log a warning listing any
            permissions in BD that are not in the code registry, so the
            team has visibility on the drift without anything being
            destroyed. Cheap, safe, informative.

    Returns:
        Dict with sync statistics.
    """
    logger.info("Initializing permissions (non-destructive boot — see initialize_permissions docstring)")

    stats = PermissionRegistry.get_stats()
    logger.info(
        f"Found {stats['permission_count']} permissions "
        f"across {stats['module_count']} modules"
    )
    if stats.get('role_count', 0) > 0:
        logger.info(
            f"Found {stats['role_permission_count']} role-permission mappings "
            f"for {stats['role_count']} roles"
        )

    # Step 1: UPSERT permissions (never DELETE)
    sync_result = await PermissionRegistry.sync_to_database(db_connection)

    logger.info(
        f"Permissions initialized: {sync_result['created_count']} new, "
        f"{sync_result['skipped_count']} existing, "
        f"{sync_result['total_count']} total"
    )

    # Step 2: UPSERT role-permission mappings (additive only)
    if sync_role_permissions and stats.get('role_count', 0) > 0:
        try:
            role_sync_result = await PermissionRegistry.sync_role_permissions_to_database(
                db_connection
            )
            sync_result['role_permissions'] = role_sync_result
            logger.info(
                f"Role permissions initialized: {role_sync_result['roles_updated']} roles, "
                f"{role_sync_result['permissions_assigned']} assignments"
            )
        except Exception as e:
            logger.warning(f"Failed to sync role permissions (non-blocking): {e}")
            sync_result['role_permissions'] = {"error": str(e)}

    # Step 3: Either report (safe) or actually delete (destructive, opt-in)
    if cleanup_obsolete:
        # ⚠️ DESTRUCTIVE — only reachable via explicit CLI flag.
        try:
            cleanup_result = await cleanup_obsolete_permissions(db_connection)
            sync_result['cleanup'] = cleanup_result
            if cleanup_result['deleted_count'] > 0:
                logger.info(
                    f"Cleanup completed: {cleanup_result['deleted_count']} obsolete permissions removed, "
                    f"{cleanup_result['role_permissions_removed']} role assignments removed"
                )
        except Exception as e:
            logger.warning(f"Failed to cleanup obsolete permissions (non-blocking): {e}")
            sync_result['cleanup'] = {"error": str(e)}
    elif report_obsolete:
        # Informative-only: list drift but do not destroy.
        try:
            backend_perms = set(PermissionRegistry.get_all_permission_names())
            db_rows = await db_connection.fetch("SELECT name FROM permissions")
            db_perms = {r['name'] for r in db_rows}
            obsolete_in_db = sorted(db_perms - backend_perms)
            sync_result['drift_report'] = {
                'in_db_not_in_code': obsolete_in_db,
                'count': len(obsolete_in_db),
            }
            if obsolete_in_db:
                logger.warning(
                    f"⚠️  {len(obsolete_in_db)} permission(s) in BD not in code registry "
                    f"(preserved by default — add to *_permissions.py to mirror, or run "
                    f"`scripts/cleanup_obsolete_permissions.py --apply` to remove). "
                    f"Sample: {obsolete_in_db[:5]}"
                )
        except Exception as e:
            logger.warning(f"Failed to compute drift report (non-blocking): {e}")
            sync_result['drift_report'] = {"error": str(e)}

    return sync_result


async def cleanup_obsolete_permissions(db_connection) -> Dict[str, Any]:
    """
    Remove permissions from database that are not defined in the backend registry.

    This ensures the database stays in sync with the backend code and prevents
    admins from accidentally selecting obsolete permissions.

    Process:
    1. Get all permission names from the database
    2. Get all permission names from the registry (backend)
    3. Find permissions in DB but not in registry (obsolete)
    4. Disable audit triggers (to prevent FK violations during CASCADE delete)
    5. Delete permission_audit_log entries
    6. Delete the obsolete permissions (CASCADE handles role/user_permissions)
    7. Re-enable audit triggers

    Args:
        db_connection: Database connection

    Returns:
        Dict with cleanup statistics
    """
    # Get all backend permission names
    backend_permissions = set(PermissionRegistry.get_all_permission_names())

    # Get all database permission names
    db_permissions_rows = await db_connection.fetch(
        "SELECT id, name FROM permissions"
    )
    db_permissions = {row['name']: row['id'] for row in db_permissions_rows}

    # Find obsolete permissions (in DB but not in backend)
    obsolete_names = set(db_permissions.keys()) - backend_permissions

    if not obsolete_names:
        logger.info("No obsolete permissions found - database is in sync with backend")
        return {
            "deleted_count": 0,
            "role_permissions_removed": 0,
            "deleted_permissions": []
        }

    logger.info(f"Found {len(obsolete_names)} obsolete permissions to cleanup")

    # Get IDs of obsolete permissions
    obsolete_ids = [db_permissions[name] for name in obsolete_names]

    audit_log_count = 0
    role_perms_count = 0
    user_perms_count = 0
    perms_count = 0

    try:
        # Step 1: Disable audit triggers to prevent FK violations during CASCADE
        # The trigger trg_audit_role_permissions tries to INSERT into permission_audit_log
        # with the permission_id being deleted, causing FK violation
        # Note: Cannot use DISABLE TRIGGER ALL because it includes system FK triggers
        await db_connection.execute(
            "ALTER TABLE role_permissions DISABLE TRIGGER trg_audit_role_permissions"
        )
        # Check if user_permissions has audit trigger and disable it
        try:
            await db_connection.execute(
                "ALTER TABLE user_permissions DISABLE TRIGGER trg_audit_user_permissions"
            )
        except Exception:
            pass  # Trigger may not exist
        logger.info("Disabled audit triggers on role_permissions")

        # Step 2: Remove permission_audit_log entries for obsolete permissions
        # This table has FK constraint NO ACTION to permissions
        try:
            audit_log_deleted = await db_connection.execute(
                """
                DELETE FROM permission_audit_log
                WHERE permission_id = ANY($1::uuid[])
                """,
                obsolete_ids
            )
            audit_log_count = int(audit_log_deleted.split()[-1]) if audit_log_deleted else 0
            logger.info(f"Deleted {audit_log_count} permission_audit_log entries")
        except Exception as e:
            logger.warning(f"Could not delete from permission_audit_log: {e}")

        # Step 3: Delete the obsolete permissions
        # CASCADE will automatically delete from role_permissions and user_permissions
        perms_deleted = await db_connection.execute(
            """
            DELETE FROM permissions
            WHERE id = ANY($1::uuid[])
            """,
            obsolete_ids
        )
        perms_count = int(perms_deleted.split()[-1]) if perms_deleted else 0

    finally:
        # Step 4: Always re-enable triggers, even if deletion failed
        try:
            await db_connection.execute(
                "ALTER TABLE role_permissions ENABLE TRIGGER trg_audit_role_permissions"
            )
        except Exception as e:
            logger.error(f"Failed to re-enable role_permissions trigger: {e}")
        try:
            await db_connection.execute(
                "ALTER TABLE user_permissions ENABLE TRIGGER trg_audit_user_permissions"
            )
        except Exception:
            pass  # Trigger may not exist
        logger.info("Re-enabled audit triggers")

    # Log what was deleted (first 20 for brevity)
    deleted_list = sorted(list(obsolete_names))[:20]
    logger.info(
        f"Deleted obsolete permissions: {deleted_list}"
        f"{'...' if len(obsolete_names) > 20 else ''}"
    )

    return {
        "deleted_count": perms_count,
        "role_permissions_removed": role_perms_count,
        "user_permissions_removed": user_perms_count,
        "audit_log_removed": audit_log_count,
        "deleted_permissions": sorted(list(obsolete_names))
    }
