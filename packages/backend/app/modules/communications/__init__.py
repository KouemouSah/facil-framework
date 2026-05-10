"""
Communications Module - Centralized communication management

Handles all types of communications:
- Email (SMTP)
- SMS (future)
- Push notifications (future)
- Webhooks (future)

Architecture: 3-tier (Routes → Services → Repositories)
"""

from app.modules.communications.services.email_service import EmailService
from app.modules.communications.services.communication_service import CommunicationService

__all__ = [
    "EmailService",
    "CommunicationService",
]
