"""Admin repositories"""

from app.modules.admin.repositories.user_repository import UserRepository
from app.modules.admin.repositories.audit_repository import AuditRepository
from app.modules.admin.repositories.system_repository import SystemRepository

__all__ = ["UserRepository", "AuditRepository", "SystemRepository"]
