"""
Menu Configuration Module

Provides dynamic menu and dashboard configuration for agents based on:
- Workflow-based entities: Auto-generated menus from entity.workflow_codes
- Module-based entities: Configured menus from roles.menu_config
"""

from app.modules.menu_config.services.menu_config_service import (
    MenuConfigService,
    get_menu_config_service,
)

__all__ = [
    "MenuConfigService",
    "get_menu_config_service",
]
