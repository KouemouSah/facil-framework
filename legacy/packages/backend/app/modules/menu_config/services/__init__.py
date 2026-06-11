"""
Menu Configuration Services
"""

from app.modules.menu_config.services.menu_config_service import (
    MenuConfigService,
    get_menu_config_service,
)

__all__ = [
    "MenuConfigService",
    "get_menu_config_service",
]
