"""
Unit tests for service request history functionality.

Tests:
- History models validation
- Repository methods
- API endpoint responses
"""

import pytest
from uuid import uuid4
from datetime import datetime, timezone

from app.modules.service_requests.models.history import (
    HistoryActionType,
    HistoryActionSource,
    PerformerInfo,
    HistoryEntry,
    HistoryFilters,
    HistoryListResponse,
    HistorySummaryItem,
    HistoryListSummaryResponse
)


class TestHistoryModels:
    """Tests for history Pydantic models."""

    def test_history_action_type_enum(self):
        """Test HistoryActionType enum values."""
        assert HistoryActionType.STATUS_CHANGE == "status_change"
        assert HistoryActionType.DOCUMENT_ADDED == "document_added"
        assert HistoryActionType.ASSIGNED == "assigned"
        assert HistoryActionType.CITA_SCHEDULED == "cita_scheduled"
        assert HistoryActionType.VERIFICATION_UPDATED == "verification_updated"

    def test_history_action_source_enum(self):
        """Test HistoryActionSource enum values."""
        assert HistoryActionSource.USER == "user"
        assert HistoryActionSource.AGENT == "agent"
        assert HistoryActionSource.SYSTEM == "system"
        assert HistoryActionSource.WEBHOOK == "webhook"

    def test_performer_info_user(self):
        """Test PerformerInfo for user-initiated action."""
        performer = PerformerInfo(
            user_id=uuid4(),
            full_name="María López",
            email="maria@test.com",
            role="agent",
            is_system=False
        )
        assert performer.is_system is False
        assert performer.role == "agent"
        assert performer.full_name == "María López"

    def test_performer_info_system(self):
        """Test PerformerInfo for system action."""
        performer = PerformerInfo(
            user_id=None,
            full_name="Sistema",
            email=None,
            role="system",
            is_system=True
        )
        assert performer.is_system is True
        assert performer.user_id is None

    def test_history_entry_status_change(self):
        """Test HistoryEntry for status change."""
        entry = HistoryEntry(
            id=uuid4(),
            action=HistoryActionType.STATUS_CHANGE,
            previous_status="SUBMITTED",
            new_status="UNDER_REVIEW",
            details={},
            comment="Dossier pris en charge",
            performed_by=PerformerInfo(
                user_id=uuid4(),
                full_name="Agent Test",
                is_system=False
            ),
            performed_at=datetime.now(timezone.utc)
        )
        assert entry.action == HistoryActionType.STATUS_CHANGE
        assert entry.previous_status == "SUBMITTED"
        assert entry.new_status == "UNDER_REVIEW"

    def test_history_entry_document_added(self):
        """Test HistoryEntry for document upload."""
        entry = HistoryEntry(
            id=uuid4(),
            action=HistoryActionType.DOCUMENT_ADDED,
            details={
                "document_code": "DIP_ANVERSO",
                "file_name": "dip_front.jpg",
                "extraction_confidence": 0.95
            },
            performed_by=None,
            performed_at=datetime.now(timezone.utc)
        )
        assert entry.action == HistoryActionType.DOCUMENT_ADDED
        assert entry.details.get("document_code") == "DIP_ANVERSO"
        assert entry.details.get("extraction_confidence") == 0.95

    def test_history_filters(self):
        """Test HistoryFilters model."""
        filters = HistoryFilters(
            action_types=[HistoryActionType.STATUS_CHANGE, HistoryActionType.ASSIGNED],
            from_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
            to_date=datetime(2026, 1, 31, tzinfo=timezone.utc),
            include_system=False
        )
        assert len(filters.action_types) == 2
        assert filters.include_system is False

    def test_history_list_response(self):
        """Test HistoryListResponse model."""
        response = HistoryListResponse(
            request_id=uuid4(),
            reference="SR-2026-001234",
            workflow_code="PASAPORTE_NUEVO",
            solicitud_type="expedicion",
            citizen_name="Juan García",
            current_status="UNDER_REVIEW",
            entries=[],
            total=15,
            page=1,
            page_size=50,
            total_status_changes=5,
            total_documents=4,
            total_assignments=2,
            first_action_at=datetime(2026, 1, 20, tzinfo=timezone.utc),
            last_action_at=datetime(2026, 1, 27, tzinfo=timezone.utc)
        )
        assert response.reference == "SR-2026-001234"
        assert response.total == 15
        assert response.total_status_changes == 5

    def test_history_summary_item(self):
        """Test HistorySummaryItem model."""
        item = HistorySummaryItem(
            request_id=uuid4(),
            reference="SR-2026-001234",
            workflow_code="PASAPORTE_NUEVO",
            citizen_name="Juan García",
            current_status="COMPLETED",
            last_action=HistoryActionType.STATUS_CHANGE,
            last_action_at=datetime.now(timezone.utc),
            last_performer="María López",
            total_actions=20,
            days_since_created=7,
            is_stale=False
        )
        assert item.total_actions == 20
        assert item.is_stale is False

    def test_history_list_summary_response(self):
        """Test HistoryListSummaryResponse model."""
        response = HistoryListSummaryResponse(
            items=[],
            total=100,
            page=1,
            page_size=20,
            workflow_codes=["PASAPORTE_NUEVO", "PASAPORTE_RENOVACION"],
            status_filter=None
        )
        assert response.total == 100
        assert len(response.workflow_codes) == 2


class TestHistoryFiltersValidation:
    """Tests for history filter validation."""

    def test_empty_filters(self):
        """Test filters with no constraints."""
        filters = HistoryFilters()
        assert filters.action_types is None
        assert filters.include_system is True

    def test_date_range_filters(self):
        """Test date range filtering."""
        filters = HistoryFilters(
            from_date=datetime(2026, 1, 1),
            to_date=datetime(2026, 1, 31)
        )
        assert filters.from_date.year == 2026
        assert filters.to_date.month == 1


class TestHistoryResponseSerialization:
    """Tests for history response JSON serialization."""

    def test_history_entry_json(self):
        """Test HistoryEntry JSON serialization."""
        entry = HistoryEntry(
            id=uuid4(),
            action=HistoryActionType.STATUS_CHANGE,
            previous_status="DRAFT",
            new_status="SUBMITTED",
            details={"wizard_completed": True},
            performed_at=datetime.now(timezone.utc)
        )
        # Convert to dict (simulates JSON serialization)
        data = entry.model_dump()
        assert data["action"] == "status_change"
        assert data["previous_status"] == "DRAFT"
        assert data["new_status"] == "SUBMITTED"

    def test_history_list_response_json(self):
        """Test HistoryListResponse JSON serialization."""
        response = HistoryListResponse(
            request_id=uuid4(),
            reference="SR-2026-001",
            workflow_code="PASAPORTE_NUEVO",
            citizen_name="Test User",
            current_status="SUBMITTED",
            entries=[],
            total=0,
            page=1,
            page_size=50
        )
        data = response.model_dump()
        assert "request_id" in data
        assert "entries" in data
        assert data["total"] == 0


# ═══════════════════════════════════════════════════════════════
# INTEGRATION TESTS (require database)
# ═══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires database connection")
class TestHistoryRepository:
    """Integration tests for history repository methods."""

    async def test_get_request_history(self, db_connection):
        """Test fetching history for a request."""
        from app.modules.service_requests.repositories.service_request_repository import (
            service_request_repository
        )
        # This test requires a real database connection
        # and existing test data
        pass

    async def test_get_history_with_filters(self, db_connection):
        """Test fetching history with filters."""
        pass

    async def test_get_history_pagination(self, db_connection):
        """Test history pagination."""
        pass


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires database connection")
class TestHistoryEndpoints:
    """Integration tests for history API endpoints."""

    async def test_get_request_history_endpoint(self, test_client, auth_headers):
        """Test GET /{request_id}/history endpoint."""
        pass

    async def test_list_requests_with_history_endpoint(self, test_client, auth_headers):
        """Test GET /history endpoint."""
        pass
