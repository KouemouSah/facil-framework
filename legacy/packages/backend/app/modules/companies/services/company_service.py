"""
Company Service - Company Management Business Logic

Service for company CRUD operations and business rules
Tables: companies, user_company_roles
"""

from typing import Dict, Any, Optional, List
from loguru import logger
from decimal import Decimal

from app.modules.companies.models import CompanyMemberRole


class CompanyService:
    """Service for company management business logic"""

    def validate_tax_id(self, tax_id: str, country: str = "GQ") -> Dict[str, Any]:
        """
        Validate company tax ID (NIF) for Equatorial Guinea

        Args:
            tax_id: Tax identification number
            country: Country code (GQ = Equatorial Guinea)

        Returns:
            {
                "is_valid": bool,
                "format": str,
                "errors": list
            }
        """
        errors = []

        # TODO: Implement actual NIF validation for Equatorial Guinea
        # Format: NIF-XXXXXXX (7 digits)
        # Example: NIF-1234567

        if not tax_id:
            errors.append("Tax ID is required")
            return {"is_valid": False, "format": None, "errors": errors}

        # Basic validation
        if len(tax_id) < 5:
            errors.append("Tax ID too short (minimum 5 characters)")

        if len(tax_id) > 50:
            errors.append("Tax ID too long (maximum 50 characters)")

        # Check for NIF prefix (Equatorial Guinea)
        if country == "GQ" and not tax_id.upper().startswith("NIF"):
            errors.append("Tax ID should start with 'NIF' for Equatorial Guinea")

        is_valid = len(errors) == 0

        logger.info(f"Validated tax ID {tax_id}: valid={is_valid}")

        return {
            "is_valid": is_valid,
            "format": "NIF-XXXXXXX" if country == "GQ" else "Unknown",
            "errors": errors,
        }

    def check_duplicate_tax_id(
        self,
        tax_id: str,
        exclude_company_id: Optional[str] = None,
    ) -> bool:
        """
        Check if tax ID already exists (excluding current company)

        Args:
            tax_id: Tax identification number
            exclude_company_id: Company ID to exclude from check

        Returns:
            True if duplicate exists
        """
        # TODO: Implement database check
        # SELECT COUNT(*) FROM companies WHERE tax_id = $1 AND id != $2

        logger.info(f"Checking duplicate tax ID {tax_id}")

        return False  # Mock: no duplicates

    def calculate_company_metrics(
        self,
        company_id: str,
    ) -> Dict[str, Any]:
        """
        Calculate company metrics (declarations, payments, members)

        Args:
            company_id: Company ID

        Returns:
            {
                "total_declarations": int,
                "total_payments": Decimal,
                "pending_declarations": int,
                "member_count": int,
                "last_activity": datetime
            }
        """
        # TODO: Implement actual metrics calculation
        # Query tax_declarations, payments, user_company_roles

        logger.info(f"Calculating metrics for company {company_id}")

        return {
            "total_declarations": 0,
            "total_payments": Decimal("0"),
            "pending_declarations": 0,
            "member_count": 1,
            "last_activity": None,
        }

    def check_authorization(
        self,
        user_role: Optional[str],
        required_role: CompanyMemberRole,
    ) -> bool:
        """
        Check if user role has sufficient permissions

        Role hierarchy: owner > admin > accountant > member

        Args:
            user_role: User's role in company
            required_role: Minimum required role

        Returns:
            True if authorized
        """
        if not user_role:
            return False

        role_hierarchy = {
            CompanyMemberRole.COMPANY_OWNER.value: 4,
            CompanyMemberRole.COMPANY_ADMIN.value: 3,
            CompanyMemberRole.COMPANY_ACCOUNTANT.value: 2,
            CompanyMemberRole.COMPANY_MEMBER.value: 1,
        }

        user_level = role_hierarchy.get(user_role, 0)
        required_level = role_hierarchy.get(required_role.value, 0)

        is_authorized = user_level >= required_level

        logger.debug(f"Authorization check: {user_role} ({user_level}) >= {required_role.value} ({required_level}) = {is_authorized}")

        return is_authorized

    def can_modify_member_role(
        self,
        user_role: str,
        target_role: CompanyMemberRole,
    ) -> bool:
        """
        Check if user can modify a member with target role

        Rules:
        - Owner can modify anyone
        - Admin can modify accountant/member (not owner/admin)
        - Accountant cannot modify roles
        - Member cannot modify roles

        Args:
            user_role: User's role in company
            target_role: Role of member being modified

        Returns:
            True if can modify
        """
        if user_role == CompanyMemberRole.COMPANY_OWNER.value:
            return True

        if user_role == CompanyMemberRole.COMPANY_ADMIN.value:
            return target_role in [CompanyMemberRole.COMPANY_ACCOUNTANT, CompanyMemberRole.COMPANY_MEMBER]

        return False

    def validate_company_data(
        self,
        name: str,
        tax_id: str,
        email: Optional[str] = None,
        phone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Validate company data before creation/update

        Args:
            name: Company name
            tax_id: Tax identification number
            email: Company email
            phone: Company phone

        Returns:
            {
                "is_valid": bool,
                "errors": dict
            }
        """
        errors = {}

        # Name validation
        if not name or len(name) < 2:
            errors["name"] = "Company name must be at least 2 characters"
        if name and len(name) > 200:
            errors["name"] = "Company name too long (max 200 characters)"

        # Tax ID validation
        tax_id_validation = self.validate_tax_id(tax_id)
        if not tax_id_validation["is_valid"]:
            errors["tax_id"] = tax_id_validation["errors"]

        # Phone validation (Equatorial Guinea format)
        if phone:
            # Format: (222|555|551|333)XXXXXX
            if not phone.startswith(("222", "555", "551", "333")) or len(phone) != 9:
                errors["phone"] = "Invalid phone format (must be 222/555/551/333 + 6 digits)"

        is_valid = len(errors) == 0

        logger.info(f"Company data validation: valid={is_valid}, errors={errors}")

        return {
            "is_valid": is_valid,
            "errors": errors,
        }

    def generate_company_report(
        self,
        company_id: str,
        report_type: str = "summary",
    ) -> Dict[str, Any]:
        """
        Generate company report (summary, financial, tax compliance)

        Args:
            company_id: Company ID
            report_type: Type of report (summary, financial, tax_compliance)

        Returns:
            Report data
        """
        # TODO: Implement report generation
        # Query declarations, payments, receipts

        logger.info(f"Generating {report_type} report for company {company_id}")

        if report_type == "summary":
            return {
                "company_id": company_id,
                "report_type": "summary",
                "metrics": self.calculate_company_metrics(company_id),
                "generated_at": None,
            }
        elif report_type == "financial":
            return {
                "company_id": company_id,
                "report_type": "financial",
                "total_payments": Decimal("0"),
                "payment_breakdown": {},
                "generated_at": None,
            }
        elif report_type == "tax_compliance":
            return {
                "company_id": company_id,
                "report_type": "tax_compliance",
                "pending_declarations": 0,
                "overdue_payments": 0,
                "compliance_score": 100,
                "generated_at": None,
            }

        return {}

    def archive_company(
        self,
        company_id: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Archive company (soft delete)

        Args:
            company_id: Company ID
            reason: Archive reason

        Returns:
            Archive details
        """
        # TODO: Implement company archiving
        # UPDATE companies SET archived = true, archived_at = NOW(), archive_reason = $1

        logger.info(f"Archiving company {company_id}: {reason}")

        return {
            "company_id": company_id,
            "archived": True,
            "archived_at": None,
            "reason": reason,
        }

    def restore_company(
        self,
        company_id: str,
    ) -> bool:
        """
        Restore archived company

        Args:
            company_id: Company ID

        Returns:
            True if restored successfully
        """
        # TODO: Implement company restoration
        # UPDATE companies SET archived = false, archived_at = NULL

        logger.info(f"Restoring company {company_id}")

        return True
