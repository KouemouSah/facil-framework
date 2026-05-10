"""
User models for TaxasGE Backend
Pydantic v2 models for user management and authentication
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, EmailStr, validator, field_validator, ConfigDict
from enum import Enum
import phonenumbers

# User enums (aligned with user_role_enum from DATABASE_SCHEMA_REFERENCE.md)
class UserRole(str, Enum):
    """User role enumeration - MUST match user_role_enum in database

    Database enum values (from DATABASE_SCHEMA_REFERENCE.md lines 439-444):
    - citizen: Regular citizen user
    - business: Business/company user
    - accountant: Professional accountant
    - admin: System administrator
    - agent: Government agent (unified role, supervisors via is_supervisor flag)
    """
    citizen = "citizen"
    business = "business"
    accountant = "accountant"
    admin = "admin"
    agent = "agent"
    funcionario = "funcionario"


class UserStatus(str, Enum):
    """
    User account status enumeration - MUST match user_status_enum in database

    Database enum values (from DATABASE_SCHEMA_REFERENCE.md):
    - active: User account is active and can access the system
    - suspended: User account is temporarily suspended
    - pending_verification: User registered but email not verified yet
    - deactivated: User account is permanently deactivated (soft delete for citizen/business)
    - inactive: Legacy status, treated as deactivated (for backward compatibility)
    """
    active = "active"
    suspended = "suspended"
    pending_verification = "pending_verification"
    deactivated = "deactivated"
    inactive = "inactive"  # Legacy status - treated as deactivated


class UserProfile(BaseModel):
    """
    Base user profile information

    IMPORTANT: Aligned with schema_taxage.sql users table (lines 1044-1078)
    phone_number → database column: phone_number (varchar 20)
    preferred_language → database column: preferred_language (varchar 2)

    Field aliases allow camelCase in API while using snake_case in DB
    """
    first_name: str = Field(..., min_length=2, max_length=50, description="User first name")
    last_name: str = Field(..., min_length=2, max_length=50, description="User last name")
    phone_number: Optional[str] = Field(
        None,
        alias="phone",  # Accept 'phone' in API requests for backward compatibility
        pattern=r"^(222|555|551|333)\d{6}$",
        description="Guinée Équatoriale phone (9 digits: 222/555/551/333 + 6 digits)",
        serialization_alias="phone_number"  # Always return as phone_number
    )
    address: Optional[str] = Field(None, max_length=200, description="User address")
    city: Optional[str] = Field(None, max_length=100, description="City")
    preferred_language: str = Field(
        default="es",
        alias="language",  # Accept 'language' in API requests for backward compatibility
        pattern="^(es|fr|en)$",
        description="Preferred language (es/fr/en)",
        serialization_alias="preferred_language"  # Always return as preferred_language
    )
    avatar_url: Optional[str] = Field(None, description="Profile picture URL")


class CitizenProfile(UserProfile):
    """Citizen-specific profile information"""
    national_id: Optional[str] = Field(None, max_length=20, description="National ID number")
    birth_date: Optional[datetime] = Field(None, description="Date of birth")
    gender: Optional[str] = Field(None, pattern="^(M|F|O)$", description="Gender (M/F/O)")
    marital_status: Optional[str] = Field(
        None,
        pattern="^(single|married|divorced|widowed)$",
        description="Marital status"
    )
    occupation: Optional[str] = Field(None, max_length=100, description="Professional occupation")


class BusinessProfile(UserProfile):
    """Business-specific profile information"""
    business_name: str = Field(..., min_length=2, max_length=100, description="Business name")
    business_type: str = Field(
        ...,
        pattern="^(sole_proprietor|corporation|partnership|cooperative|ngo)$",
        description="Type of business entity"
    )
    tax_id: Optional[str] = Field(None, max_length=20, description="Business tax ID")
    registration_number: Optional[str] = Field(None, max_length=30, description="Business registration number")
    industry: Optional[str] = Field(None, max_length=100, description="Industry sector")
    employee_count: Optional[int] = Field(None, ge=0, le=10000, description="Number of employees")
    annual_revenue: Optional[float] = Field(None, ge=0, description="Annual revenue in XAF")
    website: Optional[str] = Field(None, description="Business website URL")


class UserCreate(BaseModel):
    """Model for user creation"""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, max_length=100, description="User password")
    role: UserRole = Field(default=UserRole.citizen, description="User role")
    profile: UserProfile = Field(..., description="User profile information")

    # Email verification (for two-step registration)
    email_verified: bool = Field(default=True, description="Email verification status (True for verified emails)")

    # NOTE: CitizenProfile and BusinessProfile fields removed
    # Extended profiles will be implemented in MODULE_03 (User Profile Management)
    # For now, only basic user fields exist in the database


class UserUpdate(BaseModel):
    """
    Model for user updates

    Uses phone_number as primary field name (matches DB) with alias for compatibility
    """
    model_config = ConfigDict(populate_by_name=True)

    first_name: Optional[str] = Field(None, min_length=2, max_length=50)
    last_name: Optional[str] = Field(None, min_length=2, max_length=50)
    email: Optional[EmailStr] = Field(None, description="User email address")
    phone_number: Optional[str] = Field(
        None,
        alias="phone",  # Accept 'phone' for backward compatibility
        description="Phone number in E.164 format",
        serialization_alias="phone_number"
    )
    address: Optional[str] = Field(None, max_length=200)
    city: Optional[str] = Field(None, max_length=100)
    preferred_language: Optional[str] = Field(
        None,
        alias="language",  # Accept 'language' for backward compatibility
        pattern="^(es|fr|en)$",
        serialization_alias="preferred_language"
    )
    avatar_url: Optional[str] = None

    # Notification preferences (from users table)
    email_notifications: Optional[bool] = Field(None, description="Enable email notifications")
    push_notifications: Optional[bool] = Field(None, description="Enable push notifications")
    sms_notifications: Optional[bool] = Field(None, description="Enable SMS notifications")

    # Allow status updates for admins
    status: Optional[UserStatus] = None

    @validator('phone_number')
    def validate_phone_e164(cls, v):
        """Validate phone number in E.164 format (+240XXXXXXXXX)"""
        if v is None:
            return v
        try:
            parsed = phonenumbers.parse(v, None)
            if not phonenumbers.is_valid_number(parsed):
                raise ValueError('Invalid phone number')
            # Return formatted E.164 number
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        except phonenumbers.NumberParseException:
            raise ValueError('Phone number must be in E.164 format (e.g., +240XXXXXXXXX)')


class PasswordChange(BaseModel):
    """Model for password change"""
    old_password: str = Field(..., min_length=8, description="Current password")
    new_password: str = Field(..., min_length=8, max_length=100, description="New password")

    @validator('new_password')
    def validate_new_password(cls, v, values):
        """Validate new password is different from old password"""
        if 'old_password' in values and v == values['old_password']:
            raise ValueError('New password must be different from current password')
        return v


class UserResponse(BaseModel):
    """
    Model for user response (public data)

    Field names match database columns (phone_number, preferred_language)
    """
    id: str = Field(..., description="User ID")
    email: EmailStr = Field(..., description="User email")
    role: UserRole = Field(..., description="User role")
    status: UserStatus = Field(..., description="User status")
    first_name: str = Field(..., description="User first name")
    last_name: str = Field(..., description="User last name")
    phone_number: Optional[str] = Field(None, description="Phone number")
    address: Optional[str] = Field(None, description="Address")
    city: Optional[str] = Field(None, description="City")
    preferred_language: str = Field(default="es", description="Preferred language (es/fr/en)")
    avatar_url: Optional[str] = Field(None, description="Profile picture URL")
    created_at: datetime = Field(..., description="Account creation date")
    updated_at: datetime = Field(..., description="Last update date")
    last_login: Optional[datetime] = Field(None, description="Last login date")
    email_verified: Optional[bool] = Field(default=False, description="Email verification status")

    # Notification preferences
    email_notifications: Optional[bool] = Field(default=True, description="Email notifications enabled")
    push_notifications: Optional[bool] = Field(default=True, description="Push notifications enabled")
    sms_notifications: Optional[bool] = Field(default=False, description="SMS notifications enabled")

    # Two-Factor Authentication fields (TASK-M01-011)
    two_factor_enabled: Optional[bool] = Field(default=False, description="Whether 2FA is enabled")
    two_factor_secret: Optional[str] = Field(None, description="TOTP secret (base32 encoded)")
    two_factor_backup_codes: Optional[List[str]] = Field(None, description="Hashed backup codes")

    # Extended profile data based on role
    citizen_profile: Optional[CitizenProfile] = None
    business_profile: Optional[BusinessProfile] = None

    # Funcionario (civil servant) verification fields
    matricula_funcionario: Optional[str] = Field(None, description="Civil servant matricula")
    funcionario_verified_at: Optional[datetime] = Field(None, description="When funcionario was verified")
    funcionario_verified_by: Optional[str] = Field(None, description="Agent who verified funcionario")

    # Funcionario status from verified_identifiers (real-time check)
    funcionario_status: Optional[Dict[str, Any]] = Field(None, description="Real-time funcionario status from verified_identifiers")

    # RBAC role code (from roles table via users.role_id)
    role_code: Optional[str] = Field(None, description="RBAC role code from roles table (e.g. admin_agents, agent_cnedoge_pasaporte)")

    # User permissions (from role + user-specific overrides)
    permissions: Optional[List[str]] = Field(None, description="User's effective permissions (from role and user-specific grants)")


class UserListResponse(BaseModel):
    """Model for paginated user list response"""
    items: List[UserResponse] = Field(..., description="List of users")
    total: int = Field(..., description="Total number of users")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Page size")
    pages: int = Field(..., description="Total number of pages")


class UserSearchFilter(BaseModel):
    """Model for user search and filtering"""
    email: Optional[str] = Field(None, description="Filter by email (partial match)")
    role: Optional[UserRole] = Field(None, description="Filter by user role")
    status: Optional[UserStatus] = Field(None, description="Filter by user status")
    city: Optional[str] = Field(None, description="Filter by city")
    language: Optional[str] = Field(None, description="Filter by language")
    created_after: Optional[datetime] = Field(None, description="Filter by creation date (after)")
    created_before: Optional[datetime] = Field(None, description="Filter by creation date (before)")
    search_query: Optional[str] = Field(None, description="Full-text search query")


class UserStats(BaseModel):
    """Model for user statistics"""
    total_users: int = Field(..., description="Total number of users")
    active_users: int = Field(..., description="Number of active users")
    new_users_this_month: int = Field(..., description="New users this month")
    users_by_role: Dict[str, int] = Field(..., description="User count by role")
    users_by_status: Dict[str, int] = Field(..., description="User count by status")
    users_by_city: Dict[str, int] = Field(..., description="User count by city")


class UserActivity(BaseModel):
    """Model for user activity tracking"""
    user_id: str = Field(..., description="User ID")
    action: str = Field(..., description="Action performed")
    resource: Optional[str] = Field(None, description="Resource affected")
    ip_address: Optional[str] = Field(None, description="IP address")
    user_agent: Optional[str] = Field(None, description="User agent")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Activity timestamp")


class UserNotificationPreferences(BaseModel):
    """Model for user notification preferences"""
    email_notifications: bool = Field(default=True, description="Enable email notifications")
    sms_notifications: bool = Field(default=False, description="Enable SMS notifications")
    push_notifications: bool = Field(default=True, description="Enable push notifications")
    declaration_reminders: bool = Field(default=True, description="Declaration deadline reminders")
    payment_confirmations: bool = Field(default=True, description="Payment confirmations")
    system_updates: bool = Field(default=False, description="System update notifications")
    marketing_communications: bool = Field(default=False, description="Marketing communications")


class AccountDeleteRequest(BaseModel):
    """
    Request body for `DELETE /users/profile`.

    The double-confirmation (current password + literal "DELETE" string) defends
    against accidental account deletion via stolen-session deep links or UI
    misclicks. The backend then soft-deletes (sets `users.deleted_at`) and
    revokes all sessions / refresh tokens for the user.
    """
    password: str = Field(
        ...,
        min_length=1,
        description="Current account password — verified via bcrypt before any state change.",
    )
    confirmation: str = Field(
        ...,
        description="Must be the exact literal string 'DELETE' to confirm intent.",
    )

    @field_validator("confirmation")
    @classmethod
    def _confirmation_literal(cls, value: str) -> str:
        if value != "DELETE":
            raise ValueError("confirmation must be the literal string 'DELETE'")
        return value