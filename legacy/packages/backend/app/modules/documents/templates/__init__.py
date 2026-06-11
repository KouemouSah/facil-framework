"""
Document Templates Module
Stores JSON templates for form extraction

Author: Claude Code
Date: 2025-11-13
Version: 2.0 - Template-based extraction system
"""

from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent
DECLARATIONS_DIR = TEMPLATES_DIR / "declarations"
FISCAL_SERVICES_DIR = TEMPLATES_DIR / "fiscal_services"

__all__ = ["TEMPLATES_DIR", "DECLARATIONS_DIR", "FISCAL_SERVICES_DIR"]
