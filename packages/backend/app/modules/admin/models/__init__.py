"""Admin models"""

from app.modules.admin.models.admin import (
    UserRole,
    UserStatus,
    AuditAction,
    SystemRuleCategory,
    SystemRuleValueType,
    UserCreate,
    UserUpdate,
    UserResponse,
    UserListResponse,
    UserStats,
    AuditLogBase,
    AuditLogCreate,
    AuditLogResponse,
    AuditLogFilter,
    SystemRuleBase,
    SystemRuleCreate,
    SystemRuleUpdate,
    SystemRuleResponse,
    SystemRuleListResponse,
    SystemDiagnostics,
    MigrationResult,
)

# Aliases for backward compatibility
AuditLog = AuditLogResponse
SystemRule = SystemRuleResponse

__all__ = [
    "UserRole",
    "UserStatus",
    "AuditAction",
    "SystemRuleCategory",
    "SystemRuleValueType",
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "UserListResponse",
    "UserStats",
    "AuditLog",
    "AuditLogBase",
    "AuditLogCreate",
    "AuditLogResponse",
    "AuditLogFilter",
    "SystemRule",
    "SystemRuleBase",
    "SystemRuleCreate",
    "SystemRuleUpdate",
    "SystemRuleResponse",
    "SystemRuleListResponse",
    "SystemDiagnostics",
    "MigrationResult",
]
