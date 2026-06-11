"""
Admin Models - System Administration

Based on DATABASE_SCHEMA_REFERENCE.md tables:
- users (for admin user management)
- audit_logs (for audit trail)
- system_rules (for system configuration)
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime, date
from enum import Enum
from decimal import Decimal


# ============================================================================
# ENUMS (from DATABASE_SCHEMA_REFERENCE.md)
# ============================================================================

# Import UserRole and UserStatus from users module (single source of truth)
from app.modules.users.models.user import UserRole, UserStatus


class AuditAction(str, Enum):
    """Audit log actions"""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    PASSWORD_CHANGE = "password_change"
    PASSWORD_RESET = "password_reset"
    STATUS_CHANGE = "status_change"
    ROLE_CHANGE = "role_change"
    VIEW = "view"
    EXPORT = "export"
    IMPORT = "import"


class SystemRuleCategory(str, Enum):
    """System rule categories"""
    TAX = "tax"
    APPROVAL = "approval"
    PAYMENT = "payment"
    NOTIFICATION = "notification"
    SECURITY = "security"
    WORKFLOW = "workflow"
    GENERAL = "general"


class SystemRuleValueType(str, Enum):
    """System rule value types"""
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    JSON = "json"
    DATE = "date"
    PERCENTAGE = "percentage"


# ============================================================================
# USER MANAGEMENT MODELS
# ============================================================================

class UserBase(BaseModel):
    """Base user fields"""
    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone_number: Optional[str] = Field(None, max_length=20)
    document_type: Optional[str] = Field(None, max_length=20)
    document_number: Optional[str] = Field(None, max_length=50)
    role: UserRole = UserRole.citizen  # Updated to lowercase to match users module
    status: UserStatus = UserStatus.active  # Updated to lowercase to match users module
    preferred_language: str = Field(default="es", max_length=2)
    email_notifications: bool = True
    push_notifications: bool = True
    address: Optional[str] = None
    city: Optional[str] = Field(None, max_length=100)
    avatar_url: Optional[str] = None
    matricule: Optional[str] = Field(None, max_length=50)


class UserCreate(UserBase):
    """Create user (admin only - cannot create citizen/business via admin)"""
    password: str = Field(..., min_length=8)

    class Config:
        schema_extra = {
            "example": {
                "email": "agent@dgi.gq",
                "password": "SecurePass123!",
                "first_name": "Jean",
                "last_name": "Dupont",
                "phone_number": "222123456",
                "document_type": "DNI",
                "document_number": "12345678",
                "role": "dgi_agent",
                "status": "active",
                "preferred_language": "es",
                "city": "Malabo"
            }
        }


class UserUpdate(BaseModel):
    """Update user"""
    email: Optional[EmailStr] = None
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone_number: Optional[str] = Field(None, max_length=20)
    document_type: Optional[str] = Field(None, max_length=20)
    document_number: Optional[str] = Field(None, max_length=50)
    role: Optional[UserRole] = None
    status: Optional[UserStatus] = None
    preferred_language: Optional[str] = Field(None, max_length=2)
    email_notifications: Optional[bool] = None
    push_notifications: Optional[bool] = None
    address: Optional[str] = None
    city: Optional[str] = Field(None, max_length=100)
    avatar_url: Optional[str] = None
    matricule: Optional[str] = Field(None, max_length=50)


class UserResponse(UserBase):
    """User response"""
    id: str
    full_name: Optional[str] = None
    email_verified: bool = False
    phone_verified: bool = False
    last_login: Optional[datetime] = None
    failed_login_attempts: int = 0
    locked_until: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """Paginated user list response"""
    items: List[UserResponse]
    total: int
    page: int
    page_size: int
    pages: int


class UserStats(BaseModel):
    """User statistics"""
    total_users: int
    by_role: Dict[str, int]
    by_status: Dict[str, int]
    active_users: int
    verified_users: int
    new_users_last_30_days: int
    locked_users: int


# ============================================================================
# AUDIT LOG MODELS
# ============================================================================

class AuditLogBase(BaseModel):
    """Base audit log fields"""
    entity_type: Optional[str] = Field(None, max_length=50)
    entity_id: Optional[str] = Field(None, max_length=50)
    action: str = Field(..., max_length=50)
    old_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class AuditLogCreate(AuditLogBase):
    """Create audit log"""
    user_id: Optional[str] = None


class AuditLogResponse(AuditLogBase):
    """Audit log response"""
    id: str
    user_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogFilter(BaseModel):
    """Audit log filter"""
    user_id: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    action: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


# ============================================================================
# SYSTEM RULES MODELS
# ============================================================================

class SystemRuleBase(BaseModel):
    """Base system rule fields"""
    rule_code: str = Field(..., max_length=100)
    rule_category: SystemRuleCategory
    name_es: str
    name_fr: Optional[str] = None
    name_en: Optional[str] = None
    description: Optional[str] = None
    rule_value: Dict[str, Any]
    value_type: SystemRuleValueType
    applies_to: Optional[str] = Field(None, max_length=50)
    effective_from: date = Field(default_factory=date.today)
    effective_until: Optional[date] = None
    is_active: bool = True


class SystemRuleCreate(SystemRuleBase):
    """Create system rule"""
    created_by: Optional[str] = None


class SystemRuleUpdate(BaseModel):
    """Update system rule"""
    rule_code: Optional[str] = Field(None, max_length=100)
    rule_category: Optional[SystemRuleCategory] = None
    name_es: Optional[str] = None
    name_fr: Optional[str] = None
    name_en: Optional[str] = None
    description: Optional[str] = None
    rule_value: Optional[Dict[str, Any]] = None
    value_type: Optional[SystemRuleValueType] = None
    applies_to: Optional[str] = Field(None, max_length=50)
    effective_from: Optional[date] = None
    effective_until: Optional[date] = None
    is_active: Optional[bool] = None


class SystemRuleResponse(SystemRuleBase):
    """System rule response"""
    id: int
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None

    class Config:
        from_attributes = True


class SystemRuleListResponse(BaseModel):
    """Paginated system rule list"""
    items: List[SystemRuleResponse]
    total: int
    page: int
    page_size: int


# ============================================================================
# SYSTEM DIAGNOSTICS & MIGRATIONS
# ============================================================================

class SystemDiagnostics(BaseModel):
    """System diagnostics information"""
    database_status: str
    redis_status: Optional[str] = None
    storage_status: str
    email_service_status: str
    total_users: int
    total_declarations: int
    total_payments: int
    system_version: str
    environment: str
    uptime_seconds: Optional[int] = None


class MigrationResult(BaseModel):
    """Database migration result"""
    success: bool
    migration_name: str
    records_affected: int
    message: str
    errors: Optional[List[str]] = None


class PasswordResetRequest(BaseModel):
    """Admin password reset for user"""
    user_id: str
    new_password: str = Field(..., min_length=8)
    force_change_on_login: bool = True


class BulkUserOperation(BaseModel):
    """Bulk user operation"""
    user_ids: List[str]
    operation: str  # activate, deactivate, suspend, delete
    reason: Optional[str] = None


class UserActivityLog(BaseModel):
    """User activity log"""
    user_id: str
    action: str
    resource: str
    resource_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    timestamp: datetime


class SystemConfigUpdate(BaseModel):
    """System configuration update"""
    config_key: str
    config_value: Any
    description: Optional[str] = None


class EmailTemplate(BaseModel):
    """Email template configuration"""
    template_name: str
    subject_es: str
    subject_fr: Optional[str] = None
    subject_en: Optional[str] = None
    body_html: str
    body_text: Optional[str] = None
    variables: Optional[List[str]] = None


class SystemMetrics(BaseModel):
    """System performance metrics"""
    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    disk_usage: Optional[float] = None
    active_connections: Optional[int] = None
    requests_per_minute: Optional[int] = None
    avg_response_time_ms: Optional[float] = None
    error_rate: Optional[float] = None
