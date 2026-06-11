"""
Unit tests for ProactiveAgentService Phase 8 hardening.

Focuses on the consent-aware delivery gate + the new
`_scan_missing_documents_for_workflow` scan.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.modules.user_documents.services.proactive_agent_service import (
    ProactiveAgentService,
)


@pytest.fixture
def service() -> ProactiveAgentService:
    return ProactiveAgentService()


class TestPermissionHelper:
    @pytest.mark.asyncio
    async def test_returns_true_when_row_exists(self, service):
        db = AsyncMock()
        db.fetchval = AsyncMock(return_value=True)
        assert await service._has_proactive_alerts_permission(db, uuid4()) is True

    @pytest.mark.asyncio
    async def test_returns_false_when_missing(self, service):
        db = AsyncMock()
        db.fetchval = AsyncMock(return_value=False)
        assert await service._has_proactive_alerts_permission(db, uuid4()) is False

    @pytest.mark.asyncio
    async def test_coerces_none_to_false(self, service):
        db = AsyncMock()
        db.fetchval = AsyncMock(return_value=None)
        assert await service._has_proactive_alerts_permission(db, uuid4()) is False


class TestDeliveryGate:
    """`_should_deliver_external` is the synchronous tier/consent gate."""

    def test_critical_tiers_always_delivered(self, service):
        assert service._should_deliver_external("expired", has_consent=False) is True
        assert service._should_deliver_external("expiry_7d", has_consent=False) is True

    def test_non_critical_requires_consent(self, service):
        for tier in ("expiry_30d", "expiry_60d", "expiry_90d"):
            assert service._should_deliver_external(tier, has_consent=False) is False
            assert service._should_deliver_external(tier, has_consent=True) is True

    def test_unknown_tier_requires_consent(self, service):
        assert service._should_deliver_external(
            "missing_for_workflow", has_consent=False
        ) is False
        assert service._should_deliver_external(
            "missing_for_workflow", has_consent=True
        ) is True


class TestMissingDocumentsScan:
    @pytest.mark.asyncio
    async def test_no_in_progress_requests_returns_zero(self, service):
        db = AsyncMock()
        db.fetch = AsyncMock(return_value=[])
        result = await service._scan_missing_documents_for_workflow(db)
        assert result == 0

    @pytest.mark.asyncio
    async def test_skips_when_readiness_is_complete(self, service):
        request_id = uuid4()
        user_id = uuid4()
        db = AsyncMock()
        db.fetch = AsyncMock(
            return_value=[
                {
                    "request_id": request_id,
                    "user_id": user_id,
                    "workflow_code": "PASAPORTE_NUEVO",
                    "request_status": "DRAFT",
                    "created_at": None,
                    "user_email": "t@example.com",
                    "user_full_name": "Test",
                    "user_language": "es",
                }
            ]
        )
        db.fetchval = AsyncMock(return_value=None)
        db.execute = AsyncMock()

        with patch(
            "app.modules.user_documents.services.user_documents_service.user_documents_service"
        ) as mock_svc:
            mock_svc.get_readiness = AsyncMock(
                return_value={"missing": [], "ready": [], "readiness_score": 100}
            )
            result = await service._scan_missing_documents_for_workflow(db)

        assert result == 0
        db.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_creates_alert_when_docs_missing(self, service):
        request_id = uuid4()
        user_id = uuid4()
        db = AsyncMock()
        db.fetch = AsyncMock(
            return_value=[
                {
                    "request_id": request_id,
                    "user_id": user_id,
                    "workflow_code": "PASAPORTE_NUEVO",
                    "request_status": "DOCUMENTS_REQUIRED",
                    "created_at": None,
                    "user_email": "t@example.com",
                    "user_full_name": "Test",
                    "user_language": "fr",
                }
            ]
        )
        db.fetchval = AsyncMock(return_value=None)
        db.execute = AsyncMock()

        with patch(
            "app.modules.user_documents.services.user_documents_service.user_documents_service"
        ) as mock_svc:
            mock_svc.get_readiness = AsyncMock(
                return_value={
                    "missing": [
                        {"code": "DIP", "name": "DIP"},
                        {"code": "FOTO", "name": "Foto carnet"},
                    ],
                    "ready": [],
                    "readiness_score": 50,
                }
            )
            with patch.object(
                service,
                "_send_missing_docs_notification",
                new=AsyncMock(),
            ) as notif_mock:
                result = await service._scan_missing_documents_for_workflow(db)

        assert result == 1
        db.execute.assert_awaited_once()
        insert_sql = db.execute.call_args.args[0]
        assert "INSERT INTO user_document_alerts" in insert_sql
        assert "'missing_for_workflow'" in insert_sql
        notif_mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_dedup_skips_recent_duplicate(self, service):
        request_id = uuid4()
        user_id = uuid4()
        db = AsyncMock()
        db.fetch = AsyncMock(
            return_value=[
                {
                    "request_id": request_id,
                    "user_id": user_id,
                    "workflow_code": "PASAPORTE_NUEVO",
                    "request_status": "DRAFT",
                    "created_at": None,
                    "user_email": "t@example.com",
                    "user_full_name": "Test",
                    "user_language": "es",
                }
            ]
        )
        # Dedup: row exists → fetchval returns 1
        db.fetchval = AsyncMock(return_value=1)
        db.execute = AsyncMock()

        with patch(
            "app.modules.user_documents.services.user_documents_service.user_documents_service"
        ) as mock_svc:
            mock_svc.get_readiness = AsyncMock(
                return_value={
                    "missing": [{"code": "DIP", "name": "DIP"}],
                    "ready": [],
                    "readiness_score": 50,
                }
            )
            result = await service._scan_missing_documents_for_workflow(db)

        assert result == 0
        db.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_readiness_exception_is_swallowed(self, service):
        r1 = uuid4()
        r2 = uuid4()
        u1 = uuid4()
        u2 = uuid4()
        db = AsyncMock()
        db.fetch = AsyncMock(
            return_value=[
                {
                    "request_id": r1,
                    "user_id": u1,
                    "workflow_code": "PASAPORTE_NUEVO",
                    "request_status": "DRAFT",
                    "created_at": None,
                    "user_email": "t1@example.com",
                    "user_full_name": "A",
                    "user_language": "es",
                },
                {
                    "request_id": r2,
                    "user_id": u2,
                    "workflow_code": "CONDUCIR_NUEVO",
                    "request_status": "DRAFT",
                    "created_at": None,
                    "user_email": "t2@example.com",
                    "user_full_name": "B",
                    "user_language": "es",
                },
            ]
        )
        db.fetchval = AsyncMock(return_value=None)
        db.execute = AsyncMock()

        calls = {"n": 0}

        async def faulty_readiness(db, user_id, workflow_code):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("boom")
            return {"missing": [{"code": "DIP", "name": "DIP"}]}

        with patch(
            "app.modules.user_documents.services.user_documents_service.user_documents_service"
        ) as mock_svc:
            mock_svc.get_readiness = AsyncMock(side_effect=faulty_readiness)
            with patch.object(
                service,
                "_send_missing_docs_notification",
                new=AsyncMock(),
            ):
                result = await service._scan_missing_documents_for_workflow(db)

        assert result == 1
