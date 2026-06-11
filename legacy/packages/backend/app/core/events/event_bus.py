"""
Event Bus
=========
Central event bus for publishing and subscribing to events.

Features:
- Async-first design
- Multiple handlers per event type
- Error isolation (one handler failure doesn't affect others)
- Logging for debugging
- Type-safe payloads

@module core/events/event_bus
"""

import asyncio
import logging
from typing import (
    Dict,
    List,
    Callable,
    Awaitable,
    Any,
    Optional,
    Set,
    Union
)
from datetime import datetime, timezone
from functools import wraps

from .event_types import EventType, EventPayload

logger = logging.getLogger(__name__)

# Type alias for event handlers
EventHandler = Callable[[EventPayload], Awaitable[None]]
SyncEventHandler = Callable[[EventPayload], None]


class EventBus:
    """
    Singleton event bus for application-wide event handling.

    Usage:
        # Subscribe
        EventBus.subscribe(EventType.PAYMENT_COMPLETED, handle_payment)

        # Subscribe with decorator
        @EventBus.on(EventType.PAYMENT_COMPLETED)
        async def handle_payment(payload):
            ...

        # Publish
        await EventBus.publish(EventType.PAYMENT_COMPLETED, {"user_id": "..."})

        # Publish fire-and-forget (non-blocking)
        EventBus.publish_nowait(EventType.PAYMENT_COMPLETED, {"user_id": "..."})
    """

    _handlers: Dict[EventType, List[EventHandler]] = {}
    _initialized: bool = False
    _enabled: bool = True  # Can be disabled for testing

    @classmethod
    def initialize(cls) -> None:
        """
        Initialize the event bus. Call this at application startup.
        """
        if cls._initialized:
            return

        cls._handlers = {}
        cls._initialized = True
        logger.info("EventBus initialized")

    @classmethod
    def reset(cls) -> None:
        """
        Reset the event bus. Useful for testing.
        """
        cls._handlers = {}
        cls._initialized = False
        logger.info("EventBus reset")

    @classmethod
    def enable(cls) -> None:
        """Enable event publishing."""
        cls._enabled = True

    @classmethod
    def disable(cls) -> None:
        """Disable event publishing (useful for testing)."""
        cls._enabled = False

    @classmethod
    def subscribe(
        cls,
        event_type: EventType,
        handler: Union[EventHandler, SyncEventHandler]
    ) -> None:
        """
        Subscribe a handler to an event type.

        Args:
            event_type: The type of event to subscribe to
            handler: Async or sync function to call when event is published

        Example:
            async def my_handler(payload: EventPayload):
                print(f"Received: {payload}")

            EventBus.subscribe(EventType.PAYMENT_COMPLETED, my_handler)
        """
        if not cls._initialized:
            cls.initialize()

        # Wrap sync handlers to make them async
        if not asyncio.iscoroutinefunction(handler):
            original_handler = handler

            @wraps(original_handler)
            async def async_wrapper(payload: EventPayload) -> None:
                original_handler(payload)

            handler = async_wrapper

        if event_type not in cls._handlers:
            cls._handlers[event_type] = []

        cls._handlers[event_type].append(handler)
        logger.debug(
            f"Handler subscribed to {event_type.value}: {handler.__name__}"
        )

    @classmethod
    def unsubscribe(
        cls,
        event_type: EventType,
        handler: EventHandler
    ) -> bool:
        """
        Unsubscribe a handler from an event type.

        Args:
            event_type: The type of event
            handler: The handler to remove

        Returns:
            True if handler was found and removed, False otherwise
        """
        if event_type not in cls._handlers:
            return False

        try:
            cls._handlers[event_type].remove(handler)
            logger.debug(
                f"Handler unsubscribed from {event_type.value}: {handler.__name__}"
            )
            return True
        except ValueError:
            return False

    @classmethod
    def on(
        cls,
        event_type: EventType
    ) -> Callable[[EventHandler], EventHandler]:
        """
        Decorator to subscribe a handler to an event type.

        Example:
            @EventBus.on(EventType.PAYMENT_COMPLETED)
            async def handle_payment_completed(payload):
                ...
        """
        def decorator(handler: EventHandler) -> EventHandler:
            cls.subscribe(event_type, handler)
            return handler
        return decorator

    @classmethod
    async def publish(
        cls,
        event_type: EventType,
        payload: Optional[Dict[str, Any]] = None,
        *,
        wait: bool = True
    ) -> int:
        """
        Publish an event to all subscribed handlers.

        Args:
            event_type: The type of event to publish
            payload: The event payload data
            wait: If True, wait for all handlers to complete

        Returns:
            Number of handlers that were invoked

        Example:
            await EventBus.publish(
                EventType.PAYMENT_COMPLETED,
                {
                    "user_id": "user-123",
                    "payment_id": "pay-456",
                    "amount": 1500.00
                }
            )
        """
        if not cls._enabled:
            logger.debug(f"EventBus disabled, skipping {event_type.value}")
            return 0

        if not cls._initialized:
            cls.initialize()

        handlers = cls._handlers.get(event_type, [])
        if not handlers:
            logger.debug(f"No handlers for {event_type.value}")
            return 0

        # Ensure payload has timestamp and event_type
        full_payload: EventPayload = {
            "event_type": event_type.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **(payload or {})
        }

        logger.info(
            f"Publishing {event_type.value} to {len(handlers)} handler(s)"
        )

        # Create tasks for all handlers
        tasks = [
            cls._invoke_handler(handler, event_type, full_payload)
            for handler in handlers
        ]

        if wait:
            await asyncio.gather(*tasks, return_exceptions=True)
        else:
            # Fire and forget - create background tasks
            for task in tasks:
                asyncio.create_task(task)

        return len(handlers)

    @classmethod
    def publish_nowait(
        cls,
        event_type: EventType,
        payload: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Publish an event without waiting for handlers to complete.
        Use this for fire-and-forget scenarios.

        Args:
            event_type: The type of event to publish
            payload: The event payload data
        """
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(cls.publish(event_type, payload, wait=False))
        except RuntimeError:
            # No running loop - log warning
            logger.warning(
                f"Cannot publish_nowait {event_type.value}: no running event loop"
            )

    @classmethod
    async def _invoke_handler(
        cls,
        handler: EventHandler,
        event_type: EventType,
        payload: EventPayload
    ) -> None:
        """
        Invoke a single handler with error isolation.
        """
        handler_name = getattr(handler, "__name__", str(handler))
        try:
            await handler(payload)
            logger.debug(
                f"Handler {handler_name} completed for {event_type.value}"
            )
        except Exception as e:
            # Log error but don't propagate - other handlers should continue
            logger.error(
                f"Handler {handler_name} failed for {event_type.value}: {e}",
                exc_info=True
            )

    @classmethod
    def get_handlers(cls, event_type: EventType) -> List[EventHandler]:
        """
        Get all handlers for an event type (for testing/debugging).
        """
        return list(cls._handlers.get(event_type, []))

    @classmethod
    def get_subscribed_events(cls) -> Set[EventType]:
        """
        Get all event types that have handlers subscribed.
        """
        return set(cls._handlers.keys())

    @classmethod
    def handler_count(cls, event_type: Optional[EventType] = None) -> int:
        """
        Get the number of handlers.

        Args:
            event_type: If provided, count handlers for this event type only.
                       If None, count all handlers.
        """
        if event_type:
            return len(cls._handlers.get(event_type, []))
        return sum(len(handlers) for handlers in cls._handlers.values())
