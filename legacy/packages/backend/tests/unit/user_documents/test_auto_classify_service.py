"""
Unit tests for auto_classify_service (Phase 6).

Covers the critical branches:
- Permission check query shape
- _infer_category mapping for 4 categories + fallback
- Background task: classifier disabled → skip, empty result → skip,
  error result → no persist
- Idempotency guard (UPDATE scoped by document_type='unknown')
"""
from __future__ import annotations

import sys
import types
from dataclasses import dataclass
from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.user_documents.services import auto_classify_service


# ---------------------------------------------------------------------------
# Test isolation: the real `batch_requests.services.document_classifier` module
# imports Vertex AI bindings that aren't available in the unit test env. We
# inject a stub module into sys.modules BEFORE the service-under-test tries to
# import it, so the lazy `from ... import batch_document_classifier` inside
# `_auto_classify_impl` picks up our controlled fake.
# ---------------------------------------------------------------------------

@dataclass
class _FakeClassificationResult:
    file_path: str
    file_name: str
    mime_type: str
    document_type: Optional[str] = None
    confidence: float = 0.0
    person_name: Optional[str] = None
    identifier: Optional[str] = None
    identifier_type: Optional[str] = None
    error: Optional[str] = None


class _FakeClassifier:
    enabled: bool = True
    _queued_results: List[_FakeClassificationResult] = []

    async def classify_documents(self, documents, workflow_code):
        return list(self._queued_results)


_fake_classifier = _FakeClassifier()

_fake_module = types.ModuleType(
    "app.modules.batch_requests.services.document_classifier"
)
_fake_module.batch_document_classifier = _fake_classifier  # type: ignore[attr-defined]
_fake_module.ClassificationResult = _FakeClassificationResult  # type: ignore[attr-defined]
sys.modules["app.modules.batch_requests.services.document_classifier"] = _fake_module


@pytest.fixture(autouse=True)
def _reset_classifier_between_tests():
    """Reset the fake classifier state between tests for isolation."""
    _fake_classifier.enabled = True
    _fake_classifier._queued_results = []
    yield
    _fake_classifier.enabled = True
    _fake_classifier._queued_results = []


class TestHasAutoClassifyPermission:
    @pytest.mark.asyncio
    async def test_returns_true_when_row_exists(self):
        db = AsyncMock()
        db.fetchval = AsyncMock(return_value=True)
        result = await auto_classify_service.has_auto_classify_permission(db, uuid4())
        assert result is True
        db.fetchval.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_false_when_no_row(self):
        db = AsyncMock()
        db.fetchval = AsyncMock(return_value=False)
        result = await auto_classify_service.has_auto_classify_permission(db, uuid4())
        assert result is False

    @pytest.mark.asyncio
    async def test_coerces_none_to_false(self):
        db = AsyncMock()
        db.fetchval = AsyncMock(return_value=None)
        result = await auto_classify_service.has_auto_classify_permission(db, uuid4())
        assert result is False


class TestShouldSpawnClassify:
    """Combines permission check + rate limit (Phase 6 hardening)."""

    @pytest.mark.asyncio
    async def test_no_permission_skips_rate_check(self):
        db = AsyncMock()
        db.fetchval = AsyncMock(return_value=False)
        with patch(
            "app.core.cache.check_rate_limit",
            new=AsyncMock(return_value=(True, 20)),
        ) as rate_mock:
            result = await auto_classify_service.should_spawn_classify(db, uuid4())
        assert result is False
        rate_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_permission_granted_rate_limit_ok(self):
        db = AsyncMock()
        db.fetchval = AsyncMock(return_value=True)
        with patch(
            "app.core.cache.check_rate_limit",
            new=AsyncMock(return_value=(True, 15)),
        ):
            result = await auto_classify_service.should_spawn_classify(db, uuid4())
        assert result is True

    @pytest.mark.asyncio
    async def test_permission_granted_but_rate_limited_returns_false(self):
        db = AsyncMock()
        db.fetchval = AsyncMock(return_value=True)
        with patch(
            "app.core.cache.check_rate_limit",
            new=AsyncMock(return_value=(False, 0)),
        ):
            result = await auto_classify_service.should_spawn_classify(db, uuid4())
        assert result is False


class TestInferCategory:
    """The inference helper now lives in utils.category_inference
    (extracted during Phase 6 hardening so routes + service share one
    implementation). Returns "other" for unknowns (the enum fallback)
    instead of None."""

    def test_identity_documents(self):
        from app.modules.user_documents.utils.category_inference import infer_category
        assert infer_category("pasaporte") == "identity"
        assert infer_category("DIP") == "identity"
        assert infer_category("nie_extranjero") == "identity"
        assert infer_category("CEDULA_DE_IDENTIDAD") == "identity"

    def test_vehicle_documents(self):
        from app.modules.user_documents.utils.category_inference import infer_category
        assert infer_category("carnet_conducir") == "vehicle"
        assert infer_category("itv_certificate") == "vehicle"
        assert infer_category("matriculacion_vehiculo") == "vehicle"

    def test_legal_documents(self):
        from app.modules.user_documents.utils.category_inference import infer_category
        assert infer_category("contrato_onrc") == "legal"
        assert infer_category("certificado_residencia") == "legal"
        assert infer_category("acta_notarial") == "legal"

    def test_financial_documents(self):
        from app.modules.user_documents.utils.category_inference import infer_category
        assert infer_category("solvencia") == "financial"
        assert infer_category("nota_ingreso_tesoro") == "financial"
        assert infer_category("factura_cliente") == "financial"

    def test_unknown_returns_other(self):
        from app.modules.user_documents.utils.category_inference import infer_category
        assert infer_category("random_type") == "other"
        assert infer_category("") == "other"
        assert infer_category(None) == "other"


def _make_pool_with_conn(conn: AsyncMock) -> MagicMock:
    """Build a pool mock whose `async with pool.acquire() as conn` yields the given conn."""
    pool = MagicMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=ctx)
    return pool


class TestAutoClassifyBackground:
    @pytest.mark.asyncio
    async def test_classifier_disabled_skips(self):
        """If the classifier service is down, the task skips silently."""
        _fake_classifier.enabled = False
        spy = AsyncMock(side_effect=_fake_classifier.classify_documents)
        _fake_classifier.classify_documents = spy  # type: ignore[method-assign]
        pool = MagicMock()
        await auto_classify_service.auto_classify_background(
            doc_id=uuid4(),
            user_id=uuid4(),
            content=b"dummy",
            mime_type="image/jpeg",
            file_name="test.jpg",
            db_pool=pool,
        )
        spy.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_result_is_swallowed(self):
        _fake_classifier._queued_results = []
        pool = MagicMock()
        # Must not raise
        await auto_classify_service.auto_classify_background(
            doc_id=uuid4(),
            user_id=uuid4(),
            content=b"dummy",
            mime_type="image/jpeg",
            file_name="test.jpg",
            db_pool=pool,
        )

    @pytest.mark.asyncio
    async def test_error_result_does_not_persist(self):
        _fake_classifier._queued_results = [
            _FakeClassificationResult(
                file_path="x",
                file_name="x",
                mime_type="image/jpeg",
                error="gemini_rate_limited",
            )
        ]
        conn = AsyncMock()
        pool = _make_pool_with_conn(conn)
        await auto_classify_service.auto_classify_background(
            doc_id=uuid4(),
            user_id=uuid4(),
            content=b"dummy",
            mime_type="image/jpeg",
            file_name="test.jpg",
            db_pool=pool,
        )
        conn.fetchval.assert_not_awaited()
        conn.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_success_updates_and_logs(self):
        _fake_classifier._queued_results = [
            _FakeClassificationResult(
                file_path="test.jpg",
                file_name="test.jpg",
                mime_type="image/jpeg",
                document_type="pasaporte",
                confidence=0.92,
            )
        ]
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=uuid4())
        conn.execute = AsyncMock()
        pool = _make_pool_with_conn(conn)

        await auto_classify_service.auto_classify_background(
            doc_id=uuid4(),
            user_id=uuid4(),
            content=b"dummy",
            mime_type="image/jpeg",
            file_name="test.jpg",
            db_pool=pool,
        )

        conn.fetchval.assert_awaited_once()
        update_sql = conn.fetchval.call_args.args[0]
        assert "UPDATE user_documents" in update_sql
        assert "document_type = 'unknown'" in update_sql
        conn.execute.assert_awaited_once()
        audit_sql = conn.execute.call_args.args[0]
        assert "INSERT INTO user_document_access_log" in audit_sql
        assert "'reclassify'" in audit_sql

    @pytest.mark.asyncio
    async def test_idempotency_when_already_tagged_skips_audit(self):
        _fake_classifier._queued_results = [
            _FakeClassificationResult(
                file_path="x",
                file_name="x",
                mime_type="image/jpeg",
                document_type="pasaporte",
                confidence=0.9,
            )
        ]
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=None)
        conn.execute = AsyncMock()
        pool = _make_pool_with_conn(conn)

        await auto_classify_service.auto_classify_background(
            doc_id=uuid4(),
            user_id=uuid4(),
            content=b"dummy",
            mime_type="image/jpeg",
            file_name="test.jpg",
            db_pool=pool,
        )

        conn.fetchval.assert_awaited_once()
        conn.execute.assert_not_awaited()
