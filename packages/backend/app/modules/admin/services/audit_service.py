"""
Audit Service - Audit Log Business Logic

Service for audit trail management
"""

from typing import Dict, Any, Optional
from loguru import logger
from datetime import datetime, timezone


class AuditService:
    """Service for audit log business logic"""

    def create_audit_entry(
        self,
        user_id: Optional[str],
        entity_type: str,
        entity_id: str,
        action: str,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create audit log entry

        Args:
            user_id: User performing action
            entity_type: Type of entity
            entity_id: Entity ID
            action: Action performed
            old_values: Previous values (for updates)
            new_values: New values (for updates)
            ip_address: IP address
            user_agent: User agent string

        Returns:
            Audit log data
        """
        audit_data = {
            "user_id": user_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "action": action,
            "old_values": old_values,
            "new_values": new_values,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "created_at": datetime.now(timezone.utc),
        }

        logger.info(
            f"Audit: {action} on {entity_type}:{entity_id} by user {user_id}"
        )

        return audit_data

    def sanitize_sensitive_data(
        self,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Remove sensitive data from audit logs

        Args:
            data: Data dictionary

        Returns:
            Sanitized data
        """
        sensitive_fields = [
            "password",
            "password_hash",
            "token",
            "secret",
            "api_key",
        ]

        sanitized = data.copy()

        for field in sensitive_fields:
            if field in sanitized:
                sanitized[field] = "***REDACTED***"

        return sanitized
