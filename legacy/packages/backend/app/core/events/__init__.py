"""
Event Bus System
================
Event-driven architecture for decoupled notifications and audit logging.

Usage:
    from app.core.events import EventBus, EventType

    # Subscribe a handler
    EventBus.subscribe(EventType.PAYMENT_COMPLETED, my_handler)

    # Publish an event
    await EventBus.publish(EventType.PAYMENT_COMPLETED, {
        "user_id": user_id,
        "payment_id": payment_id,
        "amount": amount
    })
"""

from .event_types import EventType, EventPayload
from .event_bus import EventBus

__all__ = ["EventType", "EventPayload", "EventBus"]
