"""
User Service - User Management Business Logic

Service for admin user management operations
"""

from typing import Dict, Any, Optional, List
from loguru import logger

from app.modules.admin.models import UserRole, UserStatus


class UserService:
    """Service for user management business logic"""

    def validate_user_creation(
        self,
        email: str,
        role: UserRole,
    ) -> Dict[str, Any]:
        """
        Validate user creation

        Args:
            email: User email
            role: User role

        Returns:
            {
                "is_valid": bool,
                "errors": List[str]
            }
        """
        errors = []

        # Prevent admin from creating citizen or business users
        if role in [UserRole.CITIZEN, UserRole.BUSINESS]:
            errors.append(
                "Cannot create citizen or business users via admin. "
                "These users must self-register via /api/auth/register"
            )

        # Email format validation (basic)
        if not email or "@" not in email:
            errors.append("Invalid email format")

        is_valid = len(errors) == 0

        logger.debug(f"User creation validation: {is_valid}, errors: {errors}")

        return {
            "is_valid": is_valid,
            "errors": errors,
        }

    def validate_role_change(
        self,
        current_role: UserRole,
        new_role: UserRole,
        requester_role: UserRole,
    ) -> Dict[str, Any]:
        """
        Validate role change

        Args:
            current_role: Current user role
            new_role: New role to assign
            requester_role: Role of admin making the change

        Returns:
            {
                "is_valid": bool,
                "error": Optional[str]
            }
        """
        # Only admin can change roles
        if requester_role != UserRole.ADMIN:
            return {
                "is_valid": False,
                "error": "Only admin users can change roles",
            }

        # Cannot change admin to non-admin
        if current_role == UserRole.ADMIN and new_role != UserRole.ADMIN:
            return {
                "is_valid": False,
                "error": "Cannot demote admin users",
            }

        return {
            "is_valid": True,
            "error": None,
        }

    def validate_user_deletion(
        self,
        user_role: UserRole,
    ) -> Dict[str, Any]:
        """
        Validate user deletion

        Args:
            user_role: Role of user to delete

        Returns:
            {
                "can_delete": bool,
                "reason": Optional[str]
            }
        """
        # Cannot delete admin users
        if user_role == UserRole.ADMIN:
            return {
                "can_delete": False,
                "reason": "Cannot delete admin users",
            }

        return {
            "can_delete": True,
            "reason": None,
        }

    def generate_temp_password(self) -> str:
        """Generate temporary password for user"""
        import secrets
        import string

        alphabet = string.ascii_letters + string.digits + "!@#$%"
        password = ''.join(secrets.choice(alphabet) for _ in range(12))

        return password
