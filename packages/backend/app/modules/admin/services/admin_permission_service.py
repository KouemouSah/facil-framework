"""
Admin Permission Service - Centralized Admin Rights Management

This service ensures that admin users have full access to all modules and features.
It integrates with the permission system to automatically grant all permissions to admins.
"""

from typing import Dict, Any, List, Optional
from loguru import logger

from app.modules.admin.models import UserRole


class AdminPermissionService:
    """Service for centralized admin permission management"""

    # Permissions définies par module
    MODULE_PERMISSIONS = {
        "admin": [
            "admin.run_migrations",
            "admin.view_diagnostics",
            "admin.view_secrets",
            "admin.maintenance",
        ],
        "users": [
            "users.view",
            "users.view_all",
            "users.create",
            "users.update",
            "users.update_any",
            "users.delete",
            "users.manage_roles",
            "users.reset_password",
            "users.unlock_account",
            "users.search",
            "users.view_stats",
            "users.view_activities",
            "users.view_any_activities",
        ],
        "companies": [
            "company.view",
            "company.create",
            "company.update",
            "company.delete",
            "company.manage_members",
            "company.view_all",
        ],
        "agents": [
            "agent.view",
            "agent.create",
            "agent.update",
            "agent.deactivate",
            "assignment.create",
            "agent.view_performance",
            "agent.manage_workload",
        ],
        "assignments": [
            "assignment.view",
            "assignment.create",
            "assignment.update",
            "assignment.list",
            "assignment.reassign",
            "assignment.reassign_in_progress",
            "assignment.view_stats",
        ],
        "queue": [
            "queue.view",
            "queue.assign",
            "queue.complete",
            "queue.escalate",
            "queue.release",
            "queue.add",
        ],
        "declarations": [
            "declaration.view",
            "declaration.create",
            "declaration.update",
            "declaration.delete",
            "declaration.approve",
            "declaration.reject",
            "declaration.view_all",
            "declaration.export",
        ],
        "payments": [
            "payments.view",
            "payments.create",
            "payments.update",
            "payments.delete",
            "payments.process",
            "payments.refund",
            "payments.view_all",
            "payments.export",
        ],
        "documents": [
            "documents.view",
            "documents.view_all",
            "documents.upload",
            "documents.delete",
            "documents.delete_any",
            "documents.download",
            "documents.download_all",
            "documents.process",
            "documents.process_any",
            "documents.view_stats",
        ],
        "audit": [
            "audit.view",
            "audit.export",
            "audit.cleanup",
        ],
        "system": [
            "system.view_config",
            "system.update_config",
            "system.manage_rules",
            "system.run_migrations",
            "system.view_diagnostics",
            "system.maintenance",
        ],
        "fiscal_services": [
            "fiscal_services.view",
            "fiscal_services.create",
            "fiscal_services.update",
            "fiscal_services.delete",
            "fiscal_services.manage",
        ],
        "webhooks": [
            "webhook.view",
            "webhook.create",
            "webhook.update",
            "webhook.delete",
            "webhook.test",
        ],
        "reports": [
            "reports.view",
            "reports.create",
            "reports.export",
            "reports.schedule",
        ],
    }

    def is_admin(self, user_role: str) -> bool:
        """
        Check if user is admin

        Args:
            user_role: User role string

        Returns:
            True if user is admin
        """
        return user_role == UserRole.ADMIN.value

    def has_admin_access(
        self,
        user_role: str,
        permission: Optional[str] = None,
    ) -> bool:
        """
        Check if user has admin access

        Admins automatically have ALL permissions.

        Args:
            user_role: User role
            permission: Optional specific permission (ignored for admins)

        Returns:
            True if user is admin (has all permissions)
        """
        is_admin = self.is_admin(user_role)

        if is_admin and permission:
            logger.debug(f"Admin auto-granted permission: {permission}")

        return is_admin

    def get_all_permissions(self) -> List[str]:
        """
        Get all permissions across all modules

        Returns:
            List of all permission names
        """
        all_perms = []
        for module, perms in self.MODULE_PERMISSIONS.items():
            all_perms.extend(perms)
        return all_perms

    def get_module_permissions(self, module_name: str) -> List[str]:
        """
        Get all permissions for a specific module

        Args:
            module_name: Module name

        Returns:
            List of permissions for the module
        """
        return self.MODULE_PERMISSIONS.get(module_name, [])

    def get_user_effective_permissions(
        self,
        user_role: str,
        granted_permissions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Get effective permissions for a user

        Args:
            user_role: User role
            granted_permissions: Permissions explicitly granted to user

        Returns:
            {
                "is_admin": bool,
                "has_all_permissions": bool,
                "permissions": List[str],
                "total_permissions": int
            }
        """
        is_admin = self.is_admin(user_role)

        if is_admin:
            all_perms = self.get_all_permissions()
            return {
                "is_admin": True,
                "has_all_permissions": True,
                "permissions": all_perms,
                "total_permissions": len(all_perms),
                "message": "Admin users have all permissions automatically",
            }

        return {
            "is_admin": False,
            "has_all_permissions": False,
            "permissions": granted_permissions or [],
            "total_permissions": len(granted_permissions or []),
        }

    def validate_permission_grant(
        self,
        granter_role: str,
        permission: str,
    ) -> Dict[str, Any]:
        """
        Validate if a user can grant a permission

        Args:
            granter_role: Role of user granting permission
            permission: Permission to grant

        Returns:
            {
                "can_grant": bool,
                "reason": Optional[str]
            }
        """
        # Only admins can grant permissions
        if not self.is_admin(granter_role):
            return {
                "can_grant": False,
                "reason": "Only admin users can grant permissions",
            }

        # Check if permission exists
        all_perms = self.get_all_permissions()
        if permission not in all_perms:
            return {
                "can_grant": False,
                "reason": f"Unknown permission: {permission}",
            }

        return {
            "can_grant": True,
            "reason": None,
        }

    def get_permissions_summary(self) -> Dict[str, Any]:
        """
        Get summary of all permissions by module

        Returns:
            Summary of permissions
        """
        summary = {}

        for module, perms in self.MODULE_PERMISSIONS.items():
            summary[module] = {
                "total": len(perms),
                "permissions": perms,
            }

        return {
            "modules": summary,
            "total_modules": len(self.MODULE_PERMISSIONS),
            "total_permissions": len(self.get_all_permissions()),
        }

    def check_module_access(
        self,
        user_role: str,
        module_name: str,
    ) -> bool:
        """
        Check if user has access to a module

        Args:
            user_role: User role
            module_name: Module name

        Returns:
            True if user has access to module
        """
        # Admins have access to all modules
        if self.is_admin(user_role):
            logger.debug(f"Admin granted access to module: {module_name}")
            return True

        # For non-admins, check specific permissions
        # (This would integrate with the regular permission service)
        return False

    def get_admin_capabilities(self) -> List[str]:
        """
        Get list of admin-only capabilities

        Returns:
            List of admin capabilities
        """
        return [
            "Create users (all roles except citizen/business)",
            "Delete users",
            "Manage user roles",
            "Reset user passwords",
            "Unlock user accounts",
            "View all declarations",
            "View all payments",
            "Manage system rules",
            "Run database migrations",
            "View system diagnostics",
            "Manage audit logs",
            "Grant/revoke permissions",
            "Create/delete companies",
            "Manage ministry agents",
            "Reassign in-progress assignments",
            "Export all data",
            "System maintenance operations",
        ]


# Singleton instance
_admin_permission_service: Optional[AdminPermissionService] = None


def get_admin_permission_service() -> AdminPermissionService:
    """Get singleton instance of AdminPermissionService"""
    global _admin_permission_service
    if _admin_permission_service is None:
        _admin_permission_service = AdminPermissionService()
    return _admin_permission_service
