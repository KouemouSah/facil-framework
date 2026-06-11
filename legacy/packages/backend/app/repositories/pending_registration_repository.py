"""
Legacy Pending Registration Repository - Backwards Compatibility

Re-exports from app.modules.auth.repositories.pending_registration_repository
"""

from app.modules.auth.repositories.pending_registration_repository import PendingRegistrationRepository

__all__ = ["PendingRegistrationRepository"]
