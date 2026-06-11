"""
Menu Configuration Models

Pydantic schemas for menu and dashboard configuration.
"""

from app.modules.menu_config.models.menu_config import (
    # Sub-menu items
    SubMenuItemBase,
    SubMenuItemWithBadge,
    MenuItemBase,
    # Menu config
    MenuConfigBase,
    MenuConfigCreate,
    MenuConfigResponse,
    # Dashboard config
    WidgetConfigBase,
    DashboardConfigBase,
    DashboardConfigCreate,
    DashboardConfigResponse,
    # Workflow menu mappings
    WorkflowMenuMappingBase,
    WorkflowMenuMappingCreate,
    WorkflowMenuMappingUpdate,
    WorkflowMenuMappingResponse,
    WorkflowMenuMappingListResponse,
    # Agent menu config response
    AgentMenuConfigResponse,
)

__all__ = [
    # Sub-menu items
    "SubMenuItemBase",
    "SubMenuItemWithBadge",
    "MenuItemBase",
    # Menu config
    "MenuConfigBase",
    "MenuConfigCreate",
    "MenuConfigResponse",
    # Dashboard config
    "WidgetConfigBase",
    "DashboardConfigBase",
    "DashboardConfigCreate",
    "DashboardConfigResponse",
    # Workflow menu mappings
    "WorkflowMenuMappingBase",
    "WorkflowMenuMappingCreate",
    "WorkflowMenuMappingUpdate",
    "WorkflowMenuMappingResponse",
    "WorkflowMenuMappingListResponse",
    # Agent menu config response
    "AgentMenuConfigResponse",
]
