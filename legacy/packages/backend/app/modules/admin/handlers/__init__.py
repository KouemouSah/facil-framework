"""
Event Handlers for Admin/Audit
==============================
Handlers that respond to events and create audit log entries.
"""

from .audit_handler import AuditEventHandler, register_audit_handlers

__all__ = ["AuditEventHandler", "register_audit_handlers"]
