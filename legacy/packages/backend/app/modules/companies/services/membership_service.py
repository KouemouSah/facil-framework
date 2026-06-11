"""
Membership Service - Company Member Management

Service for managing company members, roles, and invitations
Tables: user_company_roles, company_invitations (future)
"""

from typing import Dict, Any, Optional, List
from loguru import logger
from datetime import datetime, timezone

from app.modules.companies.models import CompanyMemberRole


class MembershipService:
    """Service for company membership management"""

    def validate_role_change(
        self,
        current_role: CompanyMemberRole,
        new_role: CompanyMemberRole,
        requester_role: CompanyMemberRole,
    ) -> Dict[str, Any]:
        """
        Validate if role change is allowed

        Rules:
        - Owner can change any role (except demoting themselves)
        - Admin can change accountant/member roles
        - Cannot promote above your own role
        - Cannot demote owner

        Args:
            current_role: Current role of member
            new_role: New role to assign
            requester_role: Role of user making the change

        Returns:
            {
                "is_valid": bool,
                "error": Optional[str]
            }
        """
        # Cannot demote company_owner
        if current_role == CompanyMemberRole.COMPANY_OWNER and new_role != CompanyMemberRole.COMPANY_OWNER:
            return {
                "is_valid": False,
                "error": "Cannot demote company owner. Transfer ownership first.",
            }

        # Role hierarchy levels
        role_levels = {
            CompanyMemberRole.COMPANY_OWNER: 4,
            CompanyMemberRole.COMPANY_ADMIN: 3,
            CompanyMemberRole.COMPANY_ACCOUNTANT: 2,
            CompanyMemberRole.COMPANY_MEMBER: 1,
        }

        requester_level = role_levels[requester_role]
        current_level = role_levels[current_role]
        new_level = role_levels[new_role]

        # Requester must have higher level than both current and new roles
        if requester_level <= max(current_level, new_level):
            return {
                "is_valid": False,
                "error": f"Insufficient permissions. {requester_role.value} cannot modify {current_role.value} to {new_role.value}",
            }

        logger.info(f"Role change validation: {current_role.value} → {new_role.value} by {requester_role.value}: VALID")

        return {
            "is_valid": True,
            "error": None,
        }

    def transfer_ownership(
        self,
        company_id: str,
        current_owner_id: str,
        new_owner_id: str,
    ) -> Dict[str, Any]:
        """
        Transfer company ownership to another member

        Process:
        1. Verify new owner is existing member
        2. Demote current owner to admin
        3. Promote new owner to owner
        4. Log ownership transfer

        Args:
            company_id: Company ID
            current_owner_id: Current owner user ID
            new_owner_id: New owner user ID

        Returns:
            Transfer details
        """
        # TODO: Implement ownership transfer
        # BEGIN TRANSACTION
        # UPDATE user_company_roles SET role = 'admin' WHERE company_id = $1 AND user_id = $2
        # UPDATE user_company_roles SET role = 'owner' WHERE company_id = $1 AND user_id = $3
        # UPDATE companies SET owner_user_id = $3 WHERE id = $1
        # INSERT INTO ownership_transfer_log (company_id, from_user_id, to_user_id, transferred_at)
        # COMMIT

        logger.info(f"Transferring ownership of company {company_id} from {current_owner_id} to {new_owner_id}")

        return {
            "company_id": company_id,
            "previous_owner_id": current_owner_id,
            "new_owner_id": new_owner_id,
            "transferred_at": datetime.now(timezone.utc),
            "previous_owner_role": CompanyMemberRole.COMPANY_ADMIN.value,
        }

    def invite_member(
        self,
        company_id: str,
        inviter_user_id: str,
        invitee_email: str,
        role: CompanyMemberRole,
        message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Invite new member to company

        Args:
            company_id: Company ID
            inviter_user_id: User sending invitation
            invitee_email: Email of user to invite
            role: Role to assign
            message: Optional invitation message

        Returns:
            {
                "invitation_id": str,
                "company_id": str,
                "invitee_email": str,
                "role": str,
                "expires_at": datetime,
                "invitation_token": str
            }
        """
        # TODO: Implement member invitation
        # 1. Check if user exists (by email)
        # 2. Generate invitation token
        # 3. INSERT INTO company_invitations (company_id, inviter_id, invitee_email, role, token, expires_at)
        # 4. Send invitation email

        import uuid
        import secrets

        invitation_id = str(uuid.uuid4())
        invitation_token = secrets.token_urlsafe(32)

        logger.info(f"Inviting {invitee_email} to company {company_id} as {role.value}")

        # TODO: Send email notification
        # await email_service.send_company_invitation(
        #     to_email=invitee_email,
        #     company_name=company_name,
        #     inviter_name=inviter_name,
        #     role=role.value,
        #     invitation_link=f"https://taxasge.gq/invitations/{invitation_token}",
        #     message=message
        # )

        return {
            "invitation_id": invitation_id,
            "company_id": company_id,
            "invitee_email": invitee_email,
            "role": role.value,
            "expires_at": None,  # TODO: Set expiration (7 days)
            "invitation_token": invitation_token,
            "status": "pending",
        }

    def accept_invitation(
        self,
        invitation_token: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Accept company invitation

        Args:
            invitation_token: Invitation token
            user_id: User accepting invitation

        Returns:
            Membership details
        """
        # TODO: Implement invitation acceptance
        # 1. Verify token and not expired
        # 2. Verify user email matches invitee_email
        # 3. Add member to company
        # 4. UPDATE company_invitations SET status = 'accepted', accepted_at = NOW()
        # 5. Send notification to company admins

        logger.info(f"User {user_id} accepting invitation {invitation_token}")

        return {
            "company_id": "mock-company-id",
            "user_id": user_id,
            "role": CompanyMemberRole.COMPANY_MEMBER.value,
            "accepted_at": datetime.now(timezone.utc),
        }

    def revoke_invitation(
        self,
        invitation_id: str,
        revoker_user_id: str,
    ) -> bool:
        """
        Revoke pending invitation

        Args:
            invitation_id: Invitation ID
            revoker_user_id: User revoking invitation

        Returns:
            True if revoked successfully
        """
        # TODO: Implement invitation revocation
        # UPDATE company_invitations SET status = 'revoked', revoked_by = $1, revoked_at = NOW()
        # WHERE id = $2 AND status = 'pending'

        logger.info(f"Revoking invitation {invitation_id} by user {revoker_user_id}")

        return True

    def get_member_permissions(
        self,
        role: CompanyMemberRole,
    ) -> Dict[str, bool]:
        """
        Get permissions for a role

        Args:
            role: Member role

        Returns:
            Dict of permissions
        """
        permissions = {
            "can_view_company": True,
            "can_view_members": True,
            "can_create_declarations": False,
            "can_view_all_declarations": False,
            "can_approve_declarations": False,
            "can_manage_payments": False,
            "can_invite_members": False,
            "can_remove_members": False,
            "can_change_roles": False,
            "can_update_company": False,
            "can_delete_company": False,
            "can_transfer_ownership": False,
        }

        if role == CompanyMemberRole.COMPANY_OWNER:
            # Owner has all permissions
            permissions.update({
                "can_create_declarations": True,
                "can_view_all_declarations": True,
                "can_approve_declarations": True,
                "can_manage_payments": True,
                "can_invite_members": True,
                "can_remove_members": True,
                "can_change_roles": True,
                "can_update_company": True,
                "can_delete_company": True,
                "can_transfer_ownership": True,
            })
        elif role == CompanyMemberRole.COMPANY_ADMIN:
            # Admin can manage most things except ownership
            permissions.update({
                "can_create_declarations": True,
                "can_view_all_declarations": True,
                "can_approve_declarations": True,
                "can_manage_payments": True,
                "can_invite_members": True,
                "can_remove_members": True,
                "can_change_roles": True,  # Limited to accountant/member
                "can_update_company": True,
            })
        elif role == CompanyMemberRole.COMPANY_ACCOUNTANT:
            # Accountant focuses on financial operations
            permissions.update({
                "can_create_declarations": True,
                "can_view_all_declarations": True,
                "can_approve_declarations": True,
                "can_manage_payments": True,
            })
        elif role == CompanyMemberRole.COMPANY_MEMBER:
            # Member has basic access
            permissions.update({
                "can_create_declarations": True,
                "can_view_all_declarations": False,  # Only their own
            })

        logger.debug(f"Permissions for {role.value}: {permissions}")

        return permissions

    def check_member_limit(
        self,
        company_id: str,
        current_member_count: int,
        max_members: int = 50,
    ) -> Dict[str, Any]:
        """
        Check if company can add more members

        Args:
            company_id: Company ID
            current_member_count: Current number of members
            max_members: Maximum allowed members

        Returns:
            {
                "can_add": bool,
                "current": int,
                "max": int,
                "remaining": int
            }
        """
        can_add = current_member_count < max_members
        remaining = max(0, max_members - current_member_count)

        logger.info(f"Company {company_id} member limit: {current_member_count}/{max_members} (can_add={can_add})")

        return {
            "can_add": can_add,
            "current": current_member_count,
            "max": max_members,
            "remaining": remaining,
        }

    def get_member_activity(
        self,
        company_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Get member activity summary

        Args:
            company_id: Company ID
            user_id: User ID

        Returns:
            Activity summary
        """
        # TODO: Implement activity tracking
        # Query: declarations created, payments made, last login, etc.

        logger.info(f"Getting activity for user {user_id} in company {company_id}")

        return {
            "company_id": company_id,
            "user_id": user_id,
            "declarations_created": 0,
            "payments_made": 0,
            "last_activity": None,
            "joined_at": None,
        }
