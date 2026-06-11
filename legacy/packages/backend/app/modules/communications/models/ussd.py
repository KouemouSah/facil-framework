"""
USSD Configuration Models

Pydantic models for USSD menu configurations for mobile operators
in Equatorial Guinea (Getesa, Muni, Other API SMS)
"""

from enum import Enum
from typing import Optional, Dict, Any, List, Union
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, validator


class UssdOperator(str, Enum):
    """Mobile operators in Equatorial Guinea"""
    GETESA = "getesa"
    MUNI = "muni"
    OTHER_API_SMS = "other_api_sms"


class MenuActionType(str, Enum):
    """Types of actions a menu option can trigger"""
    BALANCE_CHECK = "balance"
    PAYMENT = "payment"
    TAX_INFO = "tax_info"
    SERVICE_SEARCH = "service_search"
    DECLARATION_STATUS = "declaration_status"
    SUPPORT = "support"
    CUSTOM = "custom"


class MenuOption(BaseModel):
    """Single menu option within a menu node"""
    key: str = Field(..., description="Option key (e.g., '1', '2', '*', '#')", max_length=5)
    label_es: str = Field(..., description="Option label in Spanish", min_length=1, max_length=100)
    label_fr: Optional[str] = Field(None, description="Option label in French", max_length=100)
    label_en: Optional[str] = Field(None, description="Option label in English", max_length=100)

    # Navigation: either navigate to next menu OR trigger an action
    next_menu: Optional[str] = Field(None, description="ID of next menu to navigate to")
    action: Optional[MenuActionType] = Field(None, description="Action to trigger")
    action_params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Parameters for action")

    @validator('key')
    def validate_key(cls, v):
        """Validate key is alphanumeric or special character"""
        if not v or not all(c.isalnum() or c in ['*', '#'] for c in v):
            raise ValueError("Key must be alphanumeric or special character (* or #)")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "key": "1",
                "label_es": "Consultar Saldo",
                "label_fr": "Vérifier le solde",
                "label_en": "Check Balance",
                "action": "balance"
            }
        }


class MenuNode(BaseModel):
    """Menu node in USSD menu tree"""
    id: str = Field(..., description="Unique menu ID", max_length=50)
    title_es: str = Field(..., description="Menu title in Spanish", min_length=1, max_length=160)
    title_fr: Optional[str] = Field(None, description="Menu title in French", max_length=160)
    title_en: Optional[str] = Field(None, description="Menu title in English", max_length=160)
    options: List[MenuOption] = Field(..., description="Menu options", min_items=1)
    is_root: bool = Field(False, description="Whether this is the root/main menu")
    parent_menu: Optional[str] = Field(None, description="ID of parent menu")

    @validator('options')
    def validate_options(cls, v):
        """Validate options have unique keys"""
        keys = [opt.key for opt in v]
        if len(keys) != len(set(keys)):
            raise ValueError("Menu options must have unique keys")
        return v

    @validator('options')
    def validate_navigation(cls, v):
        """Validate each option has either next_menu OR action"""
        for opt in v:
            if not opt.next_menu and not opt.action:
                raise ValueError(f"Option '{opt.key}' must have either next_menu or action")
            if opt.next_menu and opt.action:
                raise ValueError(f"Option '{opt.key}' cannot have both next_menu and action")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "id": "main",
                "title_es": "Bienvenido a Facil",
                "title_fr": "Bienvenue à Facil",
                "title_en": "Welcome to Facil",
                "is_root": True,
                "options": [
                    {
                        "key": "1",
                        "label_es": "Consultar Saldo",
                        "action": "balance"
                    },
                    {
                        "key": "2",
                        "label_es": "Pagar Impuesto",
                        "next_menu": "payment_menu"
                    }
                ]
            }
        }


class UssdConfigCreate(BaseModel):
    """Request model for creating USSD configuration"""
    operator_name: UssdOperator = Field(..., description="Mobile operator name")
    operator_code: str = Field(..., description="Operator identification code", max_length=50)
    short_code: str = Field(..., description="USSD short code (e.g., *123#)", max_length=20)
    api_endpoint: Optional[str] = Field(None, description="API endpoint URL", max_length=500)
    auth_config: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Authentication configuration (API keys, tokens, etc.)"
    )
    menu_structure: List[MenuNode] = Field(..., description="Menu tree structure", min_items=1)
    session_timeout_seconds: int = Field(180, description="Session timeout in seconds", ge=30, le=600)
    max_input_length: int = Field(160, description="Maximum input length", ge=1, le=500)
    is_active: bool = Field(True, description="Whether configuration is active")

    @validator('short_code')
    def validate_short_code(cls, v):
        """Validate short code format (*XXX#)"""
        if not v.startswith('*') or not v.endswith('#'):
            raise ValueError("Short code must start with * and end with #")
        return v

    @validator('menu_structure')
    def validate_menu_structure(cls, v):
        """Validate menu structure has exactly one root menu"""
        root_menus = [menu for menu in v if menu.is_root]
        if len(root_menus) != 1:
            raise ValueError("Menu structure must have exactly one root menu")

        # Validate all menu IDs are unique
        menu_ids = [menu.id for menu in v]
        if len(menu_ids) != len(set(menu_ids)):
            raise ValueError("Menu IDs must be unique")

        # Validate all next_menu references exist
        all_menu_ids = set(menu_ids)
        for menu in v:
            for option in menu.options:
                if option.next_menu and option.next_menu not in all_menu_ids:
                    raise ValueError(f"Menu '{menu.id}' references non-existent menu '{option.next_menu}'")

        return v

    class Config:
        json_schema_extra = {
            "example": {
                "operator_name": "getesa",
                "operator_code": "GETESA_EG",
                "short_code": "*123#",
                "api_endpoint": "https://api.getesa.gq/ussd",
                "auth_config": {
                    "api_key": "YOUR_API_KEY",
                    "api_secret": "YOUR_SECRET"
                },
                "menu_structure": [
                    {
                        "id": "main",
                        "title_es": "Bienvenido a Facil",
                        "is_root": True,
                        "options": [
                            {"key": "1", "label_es": "Consultar Saldo", "action": "balance"},
                            {"key": "2", "label_es": "Pagar Impuesto", "next_menu": "payment"}
                        ]
                    }
                ],
                "session_timeout_seconds": 180,
                "max_input_length": 160,
                "is_active": True
            }
        }


class UssdConfigUpdate(BaseModel):
    """Request model for updating USSD configuration"""
    operator_name: Optional[UssdOperator] = None
    operator_code: Optional[str] = Field(None, max_length=50)
    short_code: Optional[str] = Field(None, max_length=20)
    api_endpoint: Optional[str] = Field(None, max_length=500)
    auth_config: Optional[Dict[str, Any]] = None
    menu_structure: Optional[List[MenuNode]] = None
    session_timeout_seconds: Optional[int] = Field(None, ge=30, le=600)
    max_input_length: Optional[int] = Field(None, ge=1, le=500)
    is_active: Optional[bool] = None

    @validator('short_code')
    def validate_short_code(cls, v):
        """Validate short code format if provided"""
        if v and (not v.startswith('*') or not v.endswith('#')):
            raise ValueError("Short code must start with * and end with #")
        return v

    @validator('menu_structure')
    def validate_menu_structure(cls, v):
        """Validate menu structure if provided"""
        if v:
            root_menus = [menu for menu in v if menu.is_root]
            if len(root_menus) != 1:
                raise ValueError("Menu structure must have exactly one root menu")

            menu_ids = [menu.id for menu in v]
            if len(menu_ids) != len(set(menu_ids)):
                raise ValueError("Menu IDs must be unique")

            all_menu_ids = set(menu_ids)
            for menu in v:
                for option in menu.options:
                    if option.next_menu and option.next_menu not in all_menu_ids:
                        raise ValueError(f"Menu '{menu.id}' references non-existent menu '{option.next_menu}'")

        return v


class UssdConfigResponse(BaseModel):
    """Response model for USSD configuration"""
    id: int
    operator_name: UssdOperator
    operator_code: str
    short_code: str
    api_endpoint: Optional[str]
    auth_config: Dict[str, Any]
    menu_structure: List[MenuNode]
    session_timeout_seconds: int
    max_input_length: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]
    created_by: Optional[UUID] = None

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "operator_name": "getesa",
                "operator_code": "GETESA_EG",
                "short_code": "*123#",
                "api_endpoint": "https://api.getesa.gq/ussd",
                "auth_config": {"masked": True},
                "menu_structure": [
                    {
                        "id": "main",
                        "title_es": "Bienvenido a Facil",
                        "is_root": True,
                        "options": [
                            {"key": "1", "label_es": "Consultar Saldo", "action": "balance"}
                        ]
                    }
                ],
                "session_timeout_seconds": 180,
                "max_input_length": 160,
                "is_active": True,
                "created_at": "2025-12-12T10:00:00Z",
                "updated_at": "2025-12-12T10:00:00Z",
                "created_by": 1
            }
        }


class UssdConfigListResponse(BaseModel):
    """Response model for listing USSD configurations"""
    configs: List[UssdConfigResponse]
    total: int
    page: int
    page_size: int


class MenuValidationResult(BaseModel):
    """Result of menu structure validation"""
    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    menu_count: int
    option_count: int
    max_depth: int
