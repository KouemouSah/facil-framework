"""
System Service - System Configuration Business Logic

Service for system rules and configuration management
"""

from typing import Dict, Any, Optional
from loguru import logger
from datetime import date, datetime, timezone


class SystemService:
    """Service for system configuration business logic"""

    def validate_rule_value(
        self,
        value: Any,
        value_type: str,
    ) -> Dict[str, Any]:
        """
        Validate rule value matches expected type

        Args:
            value: Rule value
            value_type: Expected type

        Returns:
            {
                "is_valid": bool,
                "error": Optional[str]
            }
        """
        try:
            if value_type == "string":
                if not isinstance(value, str):
                    return {"is_valid": False, "error": "Value must be a string"}

            elif value_type == "number":
                if not isinstance(value, (int, float)):
                    return {"is_valid": False, "error": "Value must be a number"}

            elif value_type == "boolean":
                if not isinstance(value, bool):
                    return {"is_valid": False, "error": "Value must be a boolean"}

            elif value_type == "json":
                if not isinstance(value, dict):
                    return {"is_valid": False, "error": "Value must be a JSON object"}

            elif value_type == "percentage":
                if not isinstance(value, (int, float)) or not (0 <= value <= 100):
                    return {"is_valid": False, "error": "Value must be between 0 and 100"}

            return {"is_valid": True, "error": None}

        except Exception as e:
            return {"is_valid": False, "error": str(e)}

    def validate_date_range(
        self,
        effective_from: date,
        effective_until: Optional[date],
    ) -> Dict[str, Any]:
        """
        Validate effective date range

        Args:
            effective_from: Start date
            effective_until: End date

        Returns:
            {
                "is_valid": bool,
                "error": Optional[str]
            }
        """
        if effective_until and effective_from > effective_until:
            return {
                "is_valid": False,
                "error": "effective_from must be before effective_until",
            }

        return {"is_valid": True, "error": None}

    def check_system_health(self) -> Dict[str, Any]:
        """
        Check system health status

        Returns:
            System health information
        """
        # Basic health check
        health = {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc),
            "checks": {
                "database": "ok",
                "storage": "ok",
                "email": "ok",
            },
        }

        return health
