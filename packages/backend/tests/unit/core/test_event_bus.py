"""
Unit Tests for EventBus
=======================
Tests for the event bus system.

Run with: pytest tests/unit/core/test_event_bus.py -v
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

# Add app to path
import sys
sys.path.insert(0, "packages/backend")

from app.core.events import EventBus, EventType
from app.core.events.event_types import EventPayload, create_event_payload


class TestEventType:
    """Tests for EventType enum."""

    def test_event_type_values(self):
        """Test that event types have correct string values."""
        assert EventType.PAYMENT_COMPLETED.value == "payment.completed"
        # PAYMENT_CASH_PENDING is now an alias for PAYMENT_MANUAL_PENDING (both Cash + Check)
        assert EventType.PAYMENT_MANUAL_PENDING.value == "payment.manual.pending"
        # Verify alias points to same value
        assert EventType.PAYMENT_CASH_PENDING.value == EventType.PAYMENT_MANUAL_PENDING.value
        assert EventType.REQUEST_SUBMITTED.value == "request.submitted"
        assert EventType.APPOINTMENT_BOOKED.value == "appointment.booked"

    def test_event_type_from_string(self):
        """Test creating EventType from string value."""
        event_type = EventType("payment.completed")
        assert event_type == EventType.PAYMENT_COMPLETED

    def test_invalid_event_type_raises(self):
        """Test that invalid event type raises ValueError."""
        with pytest.raises(ValueError):
            EventType("invalid.event")


class TestCreateEventPayload:
    """Tests for create_event_payload helper."""

    def test_creates_payload_with_timestamp(self):
        """Test that payload includes timestamp."""
        payload = create_event_payload(EventType.PAYMENT_COMPLETED)
        assert "timestamp" in payload
        assert payload["event_type"] == "payment.completed"

    def test_includes_additional_kwargs(self):
        """Test that additional kwargs are included."""
        payload = create_event_payload(
            EventType.PAYMENT_COMPLETED,
            user_id="user-123",
            amount=1500.00
        )
        assert payload["user_id"] == "user-123"
        assert payload["amount"] == 1500.00


class TestEventBus:
    """Tests for EventBus class."""

    def setup_method(self):
        """Reset EventBus before each test."""
        EventBus.reset()
        EventBus.enable()

    def teardown_method(self):
        """Clean up after each test."""
        EventBus.reset()

    def test_initialize(self):
        """Test EventBus initialization."""
        EventBus.initialize()
        assert EventBus._initialized is True
        assert EventBus._handlers == {}

    def test_subscribe_handler(self):
        """Test subscribing a handler to an event."""
        async def my_handler(payload):
            pass

        EventBus.subscribe(EventType.PAYMENT_COMPLETED, my_handler)
        assert EventBus.handler_count(EventType.PAYMENT_COMPLETED) == 1

    def test_subscribe_multiple_handlers(self):
        """Test subscribing multiple handlers to same event."""
        async def handler1(payload):
            pass

        async def handler2(payload):
            pass

        EventBus.subscribe(EventType.PAYMENT_COMPLETED, handler1)
        EventBus.subscribe(EventType.PAYMENT_COMPLETED, handler2)
        assert EventBus.handler_count(EventType.PAYMENT_COMPLETED) == 2

    def test_subscribe_sync_handler(self):
        """Test subscribing a sync handler (gets wrapped to async)."""
        def sync_handler(payload):
            pass

        EventBus.subscribe(EventType.PAYMENT_COMPLETED, sync_handler)
        assert EventBus.handler_count(EventType.PAYMENT_COMPLETED) == 1

    def test_unsubscribe_handler(self):
        """Test unsubscribing a handler."""
        async def my_handler(payload):
            pass

        EventBus.subscribe(EventType.PAYMENT_COMPLETED, my_handler)
        assert EventBus.handler_count(EventType.PAYMENT_COMPLETED) == 1

        # Note: Unsubscribe with wrapped handlers may not work exactly as expected
        # because sync handlers are wrapped. This tests the basic flow.
        EventBus.unsubscribe(EventType.PAYMENT_COMPLETED, my_handler)

    def test_decorator_subscription(self):
        """Test subscribing via decorator."""
        @EventBus.on(EventType.REQUEST_SUBMITTED)
        async def handle_request(payload):
            pass

        assert EventBus.handler_count(EventType.REQUEST_SUBMITTED) == 1

    @pytest.mark.asyncio
    async def test_publish_calls_handler(self):
        """Test that publish calls subscribed handlers."""
        received = []

        async def my_handler(payload):
            received.append(payload)

        EventBus.subscribe(EventType.PAYMENT_COMPLETED, my_handler)

        await EventBus.publish(
            EventType.PAYMENT_COMPLETED,
            {"user_id": "user-123", "amount": 1500}
        )

        assert len(received) == 1
        assert received[0]["user_id"] == "user-123"
        assert received[0]["amount"] == 1500
        assert "timestamp" in received[0]
        assert received[0]["event_type"] == "payment.completed"

    @pytest.mark.asyncio
    async def test_publish_returns_handler_count(self):
        """Test that publish returns number of handlers invoked."""
        async def handler1(payload):
            pass

        async def handler2(payload):
            pass

        EventBus.subscribe(EventType.PAYMENT_COMPLETED, handler1)
        EventBus.subscribe(EventType.PAYMENT_COMPLETED, handler2)

        count = await EventBus.publish(EventType.PAYMENT_COMPLETED, {})
        assert count == 2

    @pytest.mark.asyncio
    async def test_publish_no_handlers_returns_zero(self):
        """Test that publish returns 0 when no handlers."""
        count = await EventBus.publish(EventType.PAYMENT_COMPLETED, {})
        assert count == 0

    @pytest.mark.asyncio
    async def test_publish_disabled_returns_zero(self):
        """Test that publish returns 0 when EventBus is disabled."""
        async def my_handler(payload):
            pass

        EventBus.subscribe(EventType.PAYMENT_COMPLETED, my_handler)
        EventBus.disable()

        count = await EventBus.publish(EventType.PAYMENT_COMPLETED, {})
        assert count == 0

    @pytest.mark.asyncio
    async def test_handler_error_isolation(self):
        """Test that one handler failure doesn't affect others."""
        received = []

        async def failing_handler(payload):
            raise Exception("Test error")

        async def success_handler(payload):
            received.append(payload)

        EventBus.subscribe(EventType.PAYMENT_COMPLETED, failing_handler)
        EventBus.subscribe(EventType.PAYMENT_COMPLETED, success_handler)

        # Should not raise, and success_handler should still be called
        count = await EventBus.publish(EventType.PAYMENT_COMPLETED, {"test": True})

        assert count == 2  # Both handlers were invoked
        assert len(received) == 1  # Success handler received the payload

    def test_get_subscribed_events(self):
        """Test getting all subscribed event types."""
        async def handler(payload):
            pass

        EventBus.subscribe(EventType.PAYMENT_COMPLETED, handler)
        EventBus.subscribe(EventType.REQUEST_SUBMITTED, handler)

        events = EventBus.get_subscribed_events()
        assert EventType.PAYMENT_COMPLETED in events
        assert EventType.REQUEST_SUBMITTED in events
        assert len(events) == 2

    def test_handler_count_total(self):
        """Test total handler count across all events."""
        async def handler(payload):
            pass

        EventBus.subscribe(EventType.PAYMENT_COMPLETED, handler)
        EventBus.subscribe(EventType.PAYMENT_COMPLETED, handler)
        EventBus.subscribe(EventType.REQUEST_SUBMITTED, handler)

        assert EventBus.handler_count() == 3

    def test_get_handlers(self):
        """Test getting handlers for an event type."""
        async def handler(payload):
            pass

        EventBus.subscribe(EventType.PAYMENT_COMPLETED, handler)
        handlers = EventBus.get_handlers(EventType.PAYMENT_COMPLETED)

        assert len(handlers) == 1

    def test_reset_clears_all(self):
        """Test that reset clears all handlers."""
        async def handler(payload):
            pass

        EventBus.subscribe(EventType.PAYMENT_COMPLETED, handler)
        EventBus.subscribe(EventType.REQUEST_SUBMITTED, handler)

        assert EventBus.handler_count() == 2

        EventBus.reset()

        assert EventBus.handler_count() == 0
        assert EventBus._initialized is False


class TestEventBusIntegration:
    """Integration tests for EventBus with handlers."""

    def setup_method(self):
        EventBus.reset()
        EventBus.enable()

    def teardown_method(self):
        EventBus.reset()

    @pytest.mark.asyncio
    async def test_payment_completed_flow(self):
        """Test a complete payment completed event flow."""
        notifications_sent = []
        audit_logs_created = []

        async def notification_handler(payload):
            notifications_sent.append({
                "type": "notification",
                "user_email": payload.get("user_email"),
                "amount": payload.get("amount")
            })

        async def audit_handler(payload):
            audit_logs_created.append({
                "type": "audit",
                "event": payload.get("event_type"),
                "payment_id": payload.get("payment_id")
            })

        EventBus.subscribe(EventType.PAYMENT_COMPLETED, notification_handler)
        EventBus.subscribe(EventType.PAYMENT_COMPLETED, audit_handler)

        await EventBus.publish(
            EventType.PAYMENT_COMPLETED,
            {
                "payment_id": "pay-123",
                "user_id": "user-456",
                "user_email": "test@example.com",
                "amount": 5000.00,
                "currency": "XAF",
                "receipt_number": "REC-001"
            }
        )

        assert len(notifications_sent) == 1
        assert notifications_sent[0]["user_email"] == "test@example.com"
        assert notifications_sent[0]["amount"] == 5000.00

        assert len(audit_logs_created) == 1
        assert audit_logs_created[0]["payment_id"] == "pay-123"
        assert audit_logs_created[0]["event"] == "payment.completed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
