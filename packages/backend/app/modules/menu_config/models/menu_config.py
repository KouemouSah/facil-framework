"""
Menu Configuration Models - Pydantic schemas

These models define the structure for dynamic menu and dashboard configuration
for agents. Supports both workflow-based (auto-generated) and module-based
(explicitly configured) menu systems.
"""
import json
import re
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, field_validator, model_validator


# =============================================================================
# MENU ITEM MODELS
# =============================================================================

class MenuBadgeConfig(BaseModel):
    """Configuration for menu item badge"""
    type: Literal["count", "status"] = Field(..., description="Badge type")
    source: str = Field(..., description="Data source for badge (endpoint or key)")


class SubMenuItemBase(BaseModel):
    """Base model for sub-menu items"""
    id: str = Field(..., min_length=1, max_length=50, description="Unique sub-menu ID")
    titleKey: str = Field(..., min_length=1, description="i18n key for title")
    href: str = Field(..., description="Navigation URL")
    icon: str = Field(..., description="Lucide icon name")
    permission: Optional[str] = Field(None, description="Required permission")


class SubMenuItemWithBadge(SubMenuItemBase):
    """Sub-menu item with optional badge"""
    badge: Optional[MenuBadgeConfig] = Field(None, description="Badge configuration")


class MenuItemBase(BaseModel):
    """Base model for menu items"""
    id: str = Field(..., min_length=1, max_length=50, description="Unique menu ID")
    titleKey: str = Field(..., min_length=1, description="i18n key for title")
    icon: str = Field(..., description="Lucide icon name")
    href: Optional[str] = Field(None, description="Direct navigation URL (if no sub-items)")
    permission: Optional[str] = Field(None, description="Required permission for group")
    items: Optional[List[SubMenuItemWithBadge]] = Field(None, description="Sub-menu items")

    @model_validator(mode='after')
    def validate_href_or_items(self):
        """Ensure menu has either href or items, not both with content"""
        if self.items and len(self.items) > 0 and self.href:
            raise ValueError('Menu item cannot have both href and items')
        return self


# =============================================================================
# MENU CONFIG MODELS
# =============================================================================

class MenuConfigBase(BaseModel):
    """Base menu configuration"""
    version: str = Field("1.0", description="Config version")
    source: Literal["workflow", "role", "custom"] = Field(..., description="Config source type")
    menus: List[MenuItemBase] = Field(..., description="Menu items")


class MenuConfigCreate(MenuConfigBase):
    """Schema for creating menu config"""
    pass


class MenuConfigResponse(MenuConfigBase):
    """Schema for menu config response"""
    pass


# =============================================================================
# DASHBOARD CONFIG MODELS
# =============================================================================

class WidgetConfigBase(BaseModel):
    """Base widget configuration"""
    id: str = Field(..., description="Widget identifier")
    visible: bool = Field(True, description="Is widget visible")
    position: int = Field(..., ge=1, description="Display position")
    size: Literal["small", "medium", "large", "full"] = Field("medium", description="Widget size")
    customConfig: Optional[Dict[str, Any]] = Field(None, description="Custom widget config")


class DashboardConfigBase(BaseModel):
    """Base dashboard configuration"""
    version: str = Field("1.0", description="Config version")
    layout: Literal["grid", "list", "custom"] = Field("grid", description="Layout type")
    widgets: List[WidgetConfigBase] = Field(..., description="Widget configurations")


class DashboardConfigCreate(DashboardConfigBase):
    """Schema for creating dashboard config"""
    pass


class DashboardConfigResponse(DashboardConfigBase):
    """Schema for dashboard config response"""
    pass


# =============================================================================
# CUSTOM SUB-ITEM MODEL (for dynamic admin-configurable sub-menus)
# =============================================================================

class CustomSubItem(BaseModel):
    """
    A custom sub-menu item stored in workflow_menu_mapping.custom_sub_items JSONB.
    Allows admins to add new sub-menus via the UI without SQL migrations.
    """
    id: str = Field(..., min_length=1, max_length=50, pattern=r'^[a-z][a-z0-9_-]*$',
                    description="Unique ID (also used as route segment)")
    title_key: str = Field(..., min_length=1, max_length=100,
                          description="i18n key for title (e.g., agent.nav.completed)")
    icon: str = Field(..., min_length=1, max_length=50,
                     description="Lucide icon name")
    action: str = Field(..., min_length=1, max_length=50, pattern=r'^[a-z][a-z0-9_-]*$',
                       description="Route segment: /{workflowGroup}/{action}")
    filter_params: Dict[str, Any] = Field(default_factory=dict,
                                          description="API filter params passed as query string")
    display_order: int = Field(0, ge=0, description="Display order within sub-menu list")
    is_active: bool = Field(True, description="Toggle activation")


# =============================================================================
# WORKFLOW MENU MAPPING MODELS
# =============================================================================

# Valid Lucide icon names for menu_icon validation
VALID_MENU_ICONS = {
    'Plane', 'Globe', 'Car', 'Truck', 'FileSignature', 'Briefcase',
    'Building2', 'FileText', 'CreditCard', 'Users', 'Shield',
    'Settings', 'AlertTriangle', 'Layers', 'BarChart3', 'CheckCircle2',
    'History', 'Clock', 'UserCheck', 'BadgeCheck', 'Receipt',
    'Home', 'Search', 'Bell', 'Mail', 'Phone', 'MapPin', 'Calendar',
    'Folder', 'File', 'Image', 'Video', 'Music', 'Download', 'Upload',
    'Eye', 'EyeOff', 'Lock', 'Unlock', 'Key', 'Star', 'Heart',
    'ThumbsUp', 'ThumbsDown', 'MessageSquare', 'Send', 'Inbox',
    'Archive', 'Trash2', 'Edit', 'Copy', 'Clipboard', 'Link',
    'ExternalLink', 'Share', 'Bookmark', 'Tag', 'Filter', 'List',
    'Grid', 'Table', 'Database', 'Server', 'Cloud', 'Wifi',
    'Monitor', 'Smartphone', 'Tablet', 'Printer', 'Camera',
    'Mic', 'Volume2', 'Play', 'Pause', 'Square', 'Circle',
    'Triangle', 'Hexagon', 'Zap', 'Activity', 'TrendingUp',
    'TrendingDown', 'PieChart', 'LineChart', 'DollarSign', 'Percent',
    'Hash', 'AtSign', 'Code', 'Terminal', 'Package', 'Box',
    'ShoppingCart', 'ShoppingBag', 'Gift', 'Award', 'Flag',
    'Navigation', 'Compass', 'Map', 'Crosshair', 'Target',
    'Scissors', 'Paperclip', 'RotateCw', 'RefreshCw', 'Repeat',
    'Maximize', 'Minimize', 'Move', 'ArrowRight', 'ArrowLeft',
    'ChevronRight', 'ChevronDown', 'MoreHorizontal', 'MoreVertical',
    'Plus', 'Minus', 'X', 'Check', 'Info', 'HelpCircle',
    'AlertOctagon', 'XCircle', 'CheckCircle', 'MinusCircle', 'PlusCircle',
    'LogIn', 'LogOut', 'UserPlus', 'UserMinus', 'UserX',
    'Hammer', 'Wrench', 'Tool', 'Cog', 'Sliders',
    'Sun', 'Moon', 'CloudRain', 'Umbrella', 'Wind',
    'Loader', 'Save', 'Power', 'Battery', 'Cpu',
    'HardDrive', 'Disc', 'Radio', 'Tv', 'Speaker',
    'Headphones', 'Watch', 'Glasses', 'Feather', 'Pen',
    'Type', 'Bold', 'Italic', 'Underline', 'AlignLeft',
    'AlignCenter', 'AlignRight', 'AlignJustify', 'Columns',
    'Sidebar', 'Layout', 'LayoutDashboard', 'PanelLeft',
}


class WorkflowMenuMappingBase(BaseModel):
    """Base workflow menu mapping"""
    workflow_pattern: str = Field(
        ..., min_length=1, max_length=100,
        description="Workflow pattern (e.g., PASAPORTE_%)"
    )
    menu_group_id: str = Field(
        ..., min_length=1, max_length=50,
        description="Menu group ID"
    )
    menu_title_key: str = Field(
        ..., min_length=1, max_length=100,
        description="i18n key for menu title"
    )
    menu_icon: str = Field(
        ..., min_length=1, max_length=50,
        description="Lucide icon name"
    )
    display_order: int = Field(0, ge=0, description="Display order")
    include_pending: bool = Field(True, description="Include pending sub-menu")
    include_validation: bool = Field(True, description="Include validation sub-menu")
    include_appointments: bool = Field(False, description="Include appointments sub-menu")
    include_history: bool = Field(True, description="Include history sub-menu")
    include_escalation: bool = Field(True, description="Include escalation sub-menu")
    include_batch: bool = Field(False, description="Include batch processing sub-menu")
    custom_sub_items: List[CustomSubItem] = Field(default_factory=list,
                                                   description="Dynamic custom sub-menu items (JSONB)")
    permission_prefix: Optional[str] = Field(None, max_length=50, description="Permission prefix")

    @field_validator('workflow_pattern')
    @classmethod
    def validate_workflow_pattern(cls, v: str) -> str:
        """Validate workflow_pattern matches expected format: UPPERCASE_LETTERS with optional % wildcard"""
        if not re.match(r'^[A-Z][A-Z0-9_]*(%)?$', v):
            raise ValueError(
                'workflow_pattern must start with uppercase letter, '
                'contain only A-Z, 0-9, underscore, and optionally end with %'
            )
        return v

    @field_validator('menu_icon')
    @classmethod
    def validate_menu_icon(cls, v: str) -> str:
        """Validate menu_icon is a known Lucide icon name"""
        if v not in VALID_MENU_ICONS:
            raise ValueError(f'Invalid icon: {v}. Valid: {sorted(VALID_MENU_ICONS)}')
        return v

    @field_validator('custom_sub_items', mode='before')
    @classmethod
    def parse_custom_sub_items(cls, v: Any) -> Any:
        """Parse custom_sub_items from JSON string if needed (asyncpg returns str for JSONB)"""
        if isinstance(v, str):
            return json.loads(v)
        return v


class WorkflowMenuMappingCreate(WorkflowMenuMappingBase):
    """Schema for creating mapping"""
    pass


class WorkflowMenuMappingUpdate(BaseModel):
    """Schema for updating mapping"""
    menu_title_key: Optional[str] = None
    menu_icon: Optional[str] = None
    display_order: Optional[int] = None
    include_pending: Optional[bool] = None
    include_validation: Optional[bool] = None
    include_appointments: Optional[bool] = None
    include_history: Optional[bool] = None
    include_escalation: Optional[bool] = None
    include_batch: Optional[bool] = None
    custom_sub_items: Optional[List[CustomSubItem]] = None
    permission_prefix: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator('menu_icon')
    @classmethod
    def validate_menu_icon(cls, v: Optional[str]) -> Optional[str]:
        """Validate menu_icon is a known Lucide icon name"""
        if v is not None and v not in VALID_MENU_ICONS:
            raise ValueError(f'Invalid icon: {v}. Valid: {sorted(VALID_MENU_ICONS)}')
        return v

    @field_validator('custom_sub_items', mode='before')
    @classmethod
    def parse_custom_sub_items(cls, v: Any) -> Any:
        """Parse custom_sub_items from JSON string if needed"""
        if isinstance(v, str):
            return json.loads(v)
        return v


class WorkflowMenuMappingResponse(WorkflowMenuMappingBase):
    """Schema for mapping response — skips icon validation (data already in DB)"""
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @field_validator('menu_icon')
    @classmethod
    def validate_menu_icon(cls, v: str) -> str:
        """Skip icon validation on response — data already stored in DB is valid."""
        return v

    class Config:
        from_attributes = True


class WorkflowMenuMappingListResponse(BaseModel):
    """Schema for paginated mapping list"""
    items: List[WorkflowMenuMappingResponse]
    total: int
    page: int
    page_size: int
    pages: int


# =============================================================================
# AGENT MENU CONFIG RESPONSE (Combined)
# =============================================================================

class AgentMenuConfigResponse(BaseModel):
    """Complete menu configuration for an agent"""
    # Agent info
    agent_profile_id: UUID
    entity_code: Optional[str] = None
    entity_name: Optional[str] = None
    entity_icon: Optional[str] = None
    entity_type: Literal["workflow", "module"]
    role_code: Optional[str] = None

    # Workflows (for workflow-based agents)
    available_workflows: List[str] = Field(default_factory=list)

    # Menu configuration
    menu_config: MenuConfigResponse

    # Dashboard configuration
    dashboard_config: DashboardConfigResponse

    # Agent flags
    is_supervisor: bool = False

    # Permissions (for frontend filtering)
    permissions: List[str] = Field(default_factory=list)

    # Display configs for agent's workflows (keyed by workflow_code)
    display_configs: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Display configurations keyed by workflow_code (list_columns, preview_sections, labels)"
    )

    # Flag indicating if role has menu_config in DB (for frontend fallback detection)
    has_role_menu_config: bool = Field(
        default=False,
        description="True if role.menu_config is NOT NULL in DB"
    )

    class Config:
        from_attributes = True


# =============================================================================
# WORKFLOW CODE MODELS (for dropdown selection)
# =============================================================================

class WorkflowCodeResponse(BaseModel):
    """Workflow code for dropdown selection"""
    code: str = Field(..., description="Exact workflow code (e.g., PASAPORTE_NUEVO)")
    name_es: str = Field(..., description="Spanish name")
    category: Optional[str] = Field(None, description="Workflow category (e.g., IDENTIDAD)")


class WorkflowCodeListResponse(BaseModel):
    """List of workflow codes"""
    items: List[WorkflowCodeResponse]
    total: int


# =============================================================================
# WORKFLOW DISPLAY CONFIG MODELS
# =============================================================================

class WorkflowDisplayConfigBase(BaseModel):
    """Base workflow display configuration - uses exact workflow_code (not pattern)"""
    workflow_code: str = Field(
        ..., min_length=1, max_length=100,
        description="Exact workflow code (e.g., PASAPORTE_EXPEDICION_ADULTO). Must match service_request_workflows.code."
    )
    list_columns: List[str] = Field(
        default=["reference", "fullName", "createdAt", "priority"],
        description="Column IDs to display in request list"
    )
    preview_sections: List[str] = Field(
        default=["info", "extractedData", "documents", "contact", "appointment"],
        description="Section IDs to display in request preview"
    )
    labels: Optional[Dict[str, str]] = Field(
        default_factory=dict,
        description="Custom label overrides (i18n keys)"
    )


class WorkflowDisplayConfigCreate(WorkflowDisplayConfigBase):
    """Schema for creating display config"""
    pass


class WorkflowDisplayConfigUpdate(BaseModel):
    """Schema for updating display config"""
    list_columns: Optional[List[str]] = None
    preview_sections: Optional[List[str]] = None
    labels: Optional[Dict[str, str]] = None
    is_active: Optional[bool] = None


class WorkflowDisplayConfigResponse(WorkflowDisplayConfigBase):
    """Schema for display config response"""
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorkflowDisplayConfigListResponse(BaseModel):
    """Schema for paginated display config list"""
    items: List[WorkflowDisplayConfigResponse]
    total: int
    page: int
    page_size: int
    pages: int


# =============================================================================
# AVAILABLE COLUMNS MODELS (Dynamic discovery from DB)
# =============================================================================

class AvailableColumn(BaseModel):
    """A column available for display configuration"""
    id: str = Field(..., description="Column identifier (e.g., 'dip.numero_dip', 'certificado_nacimiento.nombre')")
    label_key: str = Field(..., description="i18n key for column label")
    label: str = Field(default="", description="Human-readable label from extraction schema (field_label)")
    source: Literal["system", "extracted"] = Field(
        ..., description="'system' for table columns, 'extracted' for document extraction fields"
    )
    data_type: str = Field(
        default="string",
        description="Data type hint: string, date, number, boolean"
    )
    sample_count: int = Field(
        default=0,
        description="Kept for backwards compatibility, always 0 with schema-based discovery"
    )
    document_code: Optional[str] = Field(
        default=None,
        description="Source document code (e.g., 'dip', 'certificado_nacimiento')"
    )
    document_name_es: Optional[str] = Field(
        default=None,
        description="Spanish name of the source document"
    )


class AvailableColumnsResponse(BaseModel):
    """Response with available columns for a workflow code"""
    workflow_code: str = Field(..., description="The exact workflow code queried")
    total_requests: int = Field(
        default=0,
        description="Kept for backwards compatibility, always 0 with schema-based discovery"
    )
    system_columns: List[AvailableColumn] = Field(
        default_factory=list,
        description="Fixed system columns always available"
    )
    extracted_columns: List[AvailableColumn] = Field(
        default_factory=list,
        description="Columns from document extraction schemas (grouped by document_code)"
    )
    filters_applied: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Filters currently applied (is_minor)"
    )
    available_filters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Available filter values for this workflow (e.g., is_minor: [true, false])"
    )
    suggested_columns: List[str] = Field(
        default_factory=list,
        description="Kept for backwards compatibility, always empty with schema-based discovery"
    )
    document_count: int = Field(
        default=0,
        description="Number of documents with extraction schemas defined"
    )


# =============================================================================
# SAMPLE REQUEST MODEL (for real data preview)
# =============================================================================

class SampleRequestResponse(BaseModel):
    """Sample service request for preview purposes"""
    id: UUID = Field(..., description="Request ID")
    reference: str = Field(..., description="Request reference")
    citizen_name: Optional[str] = Field(None, description="Citizen full name")
    workflow_code: str = Field(..., description="Workflow code")
    status: str = Field(..., description="Request status")
    priority: Optional[str] = Field(None, description="Priority level")
    extracted_data: Optional[Dict[str, Any]] = Field(None, description="Extracted OCR data")
    form_data: Optional[Dict[str, Any]] = Field(None, description="Form submission data")
    created_at: datetime = Field(..., description="Creation timestamp")

    class Config:
        from_attributes = True