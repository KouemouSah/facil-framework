"""
Company Services for TaxasGE Backend
Business logic for company management and membership

Services:
- CompanyService: Company CRUD and business logic
  - Company creation with automatic owner membership
  - Member management (add, remove, role updates)
  - Authorization checks (owner, admin, accountant, member)
  - Tax ID validation for Equatorial Guinea

- MembershipService: Member role management and invitations
  - Role-based permissions (owner > admin > accountant > member)
  - Member invitations with email notifications
  - Membership transfer and ownership handoff

Tables: companies, user_company_roles
"""

from app.modules.companies.services.company_service import CompanyService
from app.modules.companies.services.membership_service import MembershipService

__all__ = ["CompanyService", "MembershipService"]
