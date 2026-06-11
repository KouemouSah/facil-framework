"""
Tests for vault chatbot tools (coffre-fort documentaire).

Tests the 7 chatbot tool functions that operate on the user_documents module:
  - list_vault_documents
  - check_readiness
  - get_expiring_documents
  - get_vault_stats
  - suggest_next_uploads
  - prepare_renewal
  - get_agent_memory

All DB access is mocked via AsyncMock.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.modules.chatbot.services.chatbot_tools_authenticated import (
    list_vault_documents,
    check_readiness,
    get_expiring_documents,
    get_vault_stats,
    suggest_next_uploads,
    prepare_renewal,
    get_agent_memory,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_db():
    """Create an AsyncMock database connection that mimics asyncpg.Connection."""
    db = AsyncMock()
    db.fetch = AsyncMock(return_value=[])
    db.fetchrow = AsyncMock(return_value=None)
    db.fetchval = AsyncMock(return_value=None)
    return db


# =============================================================================
# 9. LIST VAULT DOCUMENTS
# =============================================================================


class TestListVaultDocuments:
    """Test list_vault_documents chatbot tool."""

    @pytest.mark.asyncio
    async def test_requires_user_id(self, mock_db):
        result = await list_vault_documents(mock_db, user_id="")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_empty_vault(self, mock_db):
        mock_db.fetch.return_value = []
        result = await list_vault_documents(mock_db, user_id="test-user-id")
        assert result["count"] == 0
        assert result["documents"] == []
        assert "summary" in result

    @pytest.mark.asyncio
    async def test_with_category_filter(self, mock_db):
        mock_db.fetch.return_value = []
        result = await list_vault_documents(
            mock_db, user_id="test-user-id", category="identity"
        )
        assert result["count"] == 0
        # The SQL should have included the category filter
        call_args = mock_db.fetch.call_args
        sql = call_args[0][0]
        assert "document_category" in sql

    @pytest.mark.asyncio
    async def test_with_workflow_code_filter(self, mock_db):
        mock_db.fetch.return_value = []
        result = await list_vault_documents(
            mock_db, user_id="test-user-id", workflow_code="pasaporte_nuevo"
        )
        assert result["count"] == 0
        call_args = mock_db.fetch.call_args
        sql = call_args[0][0]
        assert "workflow_code" in sql

    @pytest.mark.asyncio
    async def test_with_expiry_status_filter_valid(self, mock_db):
        mock_db.fetch.return_value = []
        result = await list_vault_documents(
            mock_db, user_id="test-user-id", expiry_status="valid"
        )
        assert result["count"] == 0
        call_args = mock_db.fetch.call_args
        sql = call_args[0][0]
        assert "90 days" in sql

    @pytest.mark.asyncio
    async def test_with_expiry_status_filter_expired(self, mock_db):
        mock_db.fetch.return_value = []
        result = await list_vault_documents(
            mock_db, user_id="test-user-id", expiry_status="expired"
        )
        call_args = mock_db.fetch.call_args
        sql = call_args[0][0]
        assert "CURRENT_DATE" in sql

    @pytest.mark.asyncio
    async def test_limit_capped_at_20(self, mock_db):
        """The limit parameter should be capped at 20."""
        mock_db.fetch.return_value = []
        result = await list_vault_documents(
            mock_db, user_id="test-user-id", limit=100
        )
        # The function does min(int(limit), 20), so the SQL LIMIT param
        # should be 20 even though we requested 100
        call_args = mock_db.fetch.call_args
        params = call_args[0][1:]
        # Last positional param is the limit
        assert params[-1] == 20

    @pytest.mark.asyncio
    async def test_default_limit_is_10(self, mock_db):
        mock_db.fetch.return_value = []
        result = await list_vault_documents(mock_db, user_id="test-user-id")
        call_args = mock_db.fetch.call_args
        params = call_args[0][1:]
        assert params[-1] == 10

    @pytest.mark.asyncio
    async def test_summary_includes_count(self, mock_db):
        mock_db.fetch.return_value = []
        result = await list_vault_documents(mock_db, user_id="test-user-id")
        assert "0 documentos" in result["summary"]

    @pytest.mark.asyncio
    async def test_summary_includes_category_when_filtered(self, mock_db):
        mock_db.fetch.return_value = []
        result = await list_vault_documents(
            mock_db, user_id="test-user-id", category="identity"
        )
        assert "identity" in result["summary"]


# =============================================================================
# 10. CHECK READINESS
# =============================================================================


class TestCheckReadiness:
    """Test check_readiness chatbot tool."""

    @pytest.mark.asyncio
    async def test_requires_user_id(self, mock_db):
        result = await check_readiness(mock_db, user_id="", workflow_code="test")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_requires_workflow_code(self, mock_db):
        result = await check_readiness(mock_db, user_id="test-id", workflow_code="")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_requires_both_params(self, mock_db):
        result = await check_readiness(mock_db, user_id="", workflow_code="")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_no_requirements_yields_zero_score(self, mock_db):
        """When no workflow_document_requirements exist, score is 0 and can_start is True."""
        # First call: fetch requirements (empty)
        # Second call: fetch available docs (empty)
        mock_db.fetch.side_effect = [[], []]
        result = await check_readiness(
            mock_db, user_id="test-id", workflow_code="pasaporte_nuevo"
        )
        assert result["readiness_score"] == 0
        assert result["can_start"] is True
        assert result["total_required"] == 0
        assert result["missing_count"] == 0

    @pytest.mark.asyncio
    async def test_all_docs_available(self, mock_db):
        """When all required docs are available, score is 100 and can_start is True."""
        requirements = [
            {"document_code": "dip", "document_name_es": "DIP", "is_required": True, "condition_type": None},
            {"document_code": "photo", "document_name_es": "Photo", "is_required": True, "condition_type": None},
        ]
        available = [
            {"id": "doc-1", "document_type": "dip", "expiry_date": None, "status": "active", "document_code": "dip"},
            {"id": "doc-2", "document_type": "photo", "expiry_date": None, "status": "active", "document_code": "photo"},
        ]
        mock_db.fetch.side_effect = [requirements, available]
        result = await check_readiness(
            mock_db, user_id="test-id", workflow_code="pasaporte_nuevo"
        )
        assert result["readiness_score"] == 100
        assert result["can_start"] is True
        assert result["available"] == 2
        assert result["missing_count"] == 0
        assert len(result["ready"]) == 2

    @pytest.mark.asyncio
    async def test_missing_required_docs(self, mock_db):
        """When required docs are missing, they appear in 'missing' and can_start is False."""
        requirements = [
            {"document_code": "dip", "document_name_es": "DIP", "is_required": True, "condition_type": None},
            {"document_code": "photo", "document_name_es": "Photo", "is_required": True, "condition_type": None},
        ]
        # Only dip is available
        available = [
            {"id": "doc-1", "document_type": "dip", "expiry_date": None, "status": "active", "document_code": "dip"},
        ]
        mock_db.fetch.side_effect = [requirements, available]
        result = await check_readiness(
            mock_db, user_id="test-id", workflow_code="pasaporte_nuevo"
        )
        assert result["readiness_score"] == 50
        assert result["can_start"] is False
        assert result["missing_count"] == 1
        assert result["missing"][0]["code"] == "photo"

    @pytest.mark.asyncio
    async def test_optional_docs_not_in_missing(self, mock_db):
        """Non-required (optional) docs that are absent should NOT appear in missing."""
        requirements = [
            {"document_code": "dip", "document_name_es": "DIP", "is_required": True, "condition_type": None},
            {"document_code": "cert_extra", "document_name_es": "Certificado extra", "is_required": False, "condition_type": None},
        ]
        available = [
            {"id": "doc-1", "document_type": "dip", "expiry_date": None, "status": "active", "document_code": "dip"},
        ]
        mock_db.fetch.side_effect = [requirements, available]
        result = await check_readiness(
            mock_db, user_id="test-id", workflow_code="pasaporte_nuevo"
        )
        # cert_extra is not required, so it's not in missing and can_start is True
        assert result["can_start"] is True
        assert result["missing_count"] == 0

    @pytest.mark.asyncio
    async def test_summary_contains_score(self, mock_db):
        mock_db.fetch.side_effect = [[], []]
        result = await check_readiness(
            mock_db, user_id="test-id", workflow_code="test_wf"
        )
        assert "summary" in result
        assert "0%" in result["summary"]


# =============================================================================
# 11. GET EXPIRING DOCUMENTS
# =============================================================================


class TestGetExpiringDocuments:
    """Test get_expiring_documents chatbot tool."""

    @pytest.mark.asyncio
    async def test_requires_user_id(self, mock_db):
        result = await get_expiring_documents(mock_db, user_id="")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_empty_result(self, mock_db):
        mock_db.fetch.return_value = []
        result = await get_expiring_documents(mock_db, user_id="test-id")
        assert result["count"] == 0
        assert result["critical_count"] == 0
        assert result["expiring_documents"] == []

    @pytest.mark.asyncio
    async def test_default_days_ahead_is_90(self, mock_db):
        mock_db.fetch.return_value = []
        result = await get_expiring_documents(mock_db, user_id="test-id")
        # Check that the SQL was called with days_ahead=90
        call_args = mock_db.fetch.call_args
        params = call_args[0][1:]
        assert params[1] == 90  # second param is days_ahead

    @pytest.mark.asyncio
    async def test_days_ahead_capped_at_365(self, mock_db):
        mock_db.fetch.return_value = []
        result = await get_expiring_documents(
            mock_db, user_id="test-id", days_ahead=999
        )
        call_args = mock_db.fetch.call_args
        params = call_args[0][1:]
        assert params[1] == 365

    @pytest.mark.asyncio
    async def test_summary_contains_count(self, mock_db):
        mock_db.fetch.return_value = []
        result = await get_expiring_documents(mock_db, user_id="test-id")
        assert "0 documentos" in result["summary"]


# =============================================================================
# 12. GET VAULT STATS
# =============================================================================


class TestGetVaultStats:
    """Test get_vault_stats chatbot tool."""

    @pytest.mark.asyncio
    async def test_requires_user_id(self, mock_db):
        result = await get_vault_stats(mock_db, user_id="")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_empty_vault_stats(self, mock_db):
        mock_db.fetchrow.return_value = {
            "total_active": 0,
            "personal_count": 0,
            "wizard_count": 0,
            "generated_count": 0,
            "quota_used_bytes": 0,
            "expired_count": 0,
            "expiring_count": 0,
        }
        result = await get_vault_stats(mock_db, user_id="test-id")
        assert result["total_active"] == 0
        assert result["quota_percentage"] == 0.0
        assert result["quota_used_mb"] == 0.0
        assert result["quota_max_mb"] == 100

    @pytest.mark.asyncio
    async def test_populated_stats(self, mock_db):
        mock_db.fetchrow.return_value = {
            "total_active": 12,
            "personal_count": 8,
            "wizard_count": 3,
            "generated_count": 1,
            "quota_used_bytes": 15_728_640,  # ~15 MB
            "expired_count": 1,
            "expiring_count": 2,
        }
        result = await get_vault_stats(mock_db, user_id="test-id")
        assert result["total_active"] == 12
        assert result["personal"] == 8
        assert result["from_wizard"] == 3
        assert result["generated"] == 1
        assert result["expired"] == 1
        assert result["expiring_soon"] == 2
        assert result["quota_used_mb"] == 15.0
        assert result["quota_percentage"] == 15.0

    @pytest.mark.asyncio
    async def test_quota_percentage_calculation(self, mock_db):
        """Test that quota percentage is calculated correctly."""
        # 50 MB used out of 100 MB = 50%
        mock_db.fetchrow.return_value = {
            "total_active": 5,
            "personal_count": 5,
            "wizard_count": 0,
            "generated_count": 0,
            "quota_used_bytes": 50 * 1024 * 1024,
            "expired_count": 0,
            "expiring_count": 0,
        }
        result = await get_vault_stats(mock_db, user_id="test-id")
        assert result["quota_percentage"] == 50.0

    @pytest.mark.asyncio
    async def test_summary_includes_doc_count(self, mock_db):
        mock_db.fetchrow.return_value = {
            "total_active": 7,
            "personal_count": 7,
            "wizard_count": 0,
            "generated_count": 0,
            "quota_used_bytes": 1024,
            "expired_count": 0,
            "expiring_count": 0,
        }
        result = await get_vault_stats(mock_db, user_id="test-id")
        assert "7 documentos" in result["summary"]

    @pytest.mark.asyncio
    async def test_summary_includes_expiring_warning(self, mock_db):
        mock_db.fetchrow.return_value = {
            "total_active": 5,
            "personal_count": 5,
            "wizard_count": 0,
            "generated_count": 0,
            "quota_used_bytes": 0,
            "expired_count": 0,
            "expiring_count": 3,
        }
        result = await get_vault_stats(mock_db, user_id="test-id")
        assert "3 por vencer" in result["summary"]


# =============================================================================
# 13. SUGGEST NEXT UPLOADS
# =============================================================================


class TestSuggestNextUploads:
    """Test suggest_next_uploads chatbot tool."""

    @pytest.mark.asyncio
    async def test_requires_user_id(self, mock_db):
        result = await suggest_next_uploads(mock_db, user_id="")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_empty_suggestions(self, mock_db):
        mock_db.fetch.return_value = []
        result = await suggest_next_uploads(mock_db, user_id="test-id")
        assert result["count"] == 0
        assert result["suggestions"] == []

    @pytest.mark.asyncio
    async def test_suggestions_returned(self, mock_db):
        mock_db.fetch.return_value = [
            {
                "document_code": "dip",
                "document_name_es": "DIP",
                "needed_for_workflows": ["pasaporte_nuevo", "residencia_primera"],
            },
            {
                "document_code": "photo",
                "document_name_es": "Photo d'identite",
                "needed_for_workflows": ["pasaporte_nuevo"],
            },
        ]
        result = await suggest_next_uploads(mock_db, user_id="test-id")
        assert result["count"] == 2
        assert result["suggestions"][0]["document_code"] == "dip"
        assert result["suggestions"][0]["priority"] == "media"  # 2 workflows, not > 2
        assert result["suggestions"][1]["document_code"] == "photo"

    @pytest.mark.asyncio
    async def test_high_priority_when_needed_for_many_workflows(self, mock_db):
        mock_db.fetch.return_value = [
            {
                "document_code": "dip",
                "document_name_es": "DIP",
                "needed_for_workflows": ["wf1", "wf2", "wf3"],
            },
        ]
        result = await suggest_next_uploads(mock_db, user_id="test-id")
        assert result["suggestions"][0]["priority"] == "alta"

    @pytest.mark.asyncio
    async def test_summary_when_empty(self, mock_db):
        mock_db.fetch.return_value = []
        result = await suggest_next_uploads(mock_db, user_id="test-id")
        assert "completo" in result["summary"]

    @pytest.mark.asyncio
    async def test_summary_when_suggestions_exist(self, mock_db):
        mock_db.fetch.return_value = [
            {
                "document_code": "dip",
                "document_name_es": "DIP",
                "needed_for_workflows": ["pasaporte_nuevo"],
            },
        ]
        result = await suggest_next_uploads(mock_db, user_id="test-id")
        assert "1 documentos recomendados" in result["summary"]


# =============================================================================
# 14. PREPARE RENEWAL
# =============================================================================


class TestPrepareRenewal:
    """Test prepare_renewal chatbot tool."""

    @pytest.mark.asyncio
    async def test_requires_user_id(self, mock_db):
        result = await prepare_renewal(mock_db, user_id="", document_id="doc-id")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_requires_document_id(self, mock_db):
        result = await prepare_renewal(mock_db, user_id="test-id", document_id="")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_requires_both_params(self, mock_db):
        result = await prepare_renewal(mock_db, user_id="", document_id="")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_document_not_found(self, mock_db):
        mock_db.fetchrow.return_value = None
        result = await prepare_renewal(mock_db, user_id="test-id", document_id="missing-id")
        assert "error" in result
        assert "no encontrado" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_pasaporte_maps_to_renovation_workflow(self, mock_db):
        """pasaporte document type should map to pasaporte_renovacion workflow."""
        mock_db.fetchrow.return_value = {
            "id": "doc-id",
            "document_type": "pasaporte",
            "display_name": "Mi Pasaporte",
            "file_name": "passport.pdf",
            "expiry_date": None,
            "document_category": "identity",
            "holder_name": "Juan Test",
        }
        # check_readiness is called inside prepare_renewal; mock the 2 fetch calls
        mock_db.fetch.side_effect = [[], []]

        result = await prepare_renewal(mock_db, user_id="test-id", document_id="doc-id")
        assert result["status"] == "prepared"
        assert result["workflow_code"] == "pasaporte_renovacion"
        assert result["requires_confirmation"] is True

    @pytest.mark.asyncio
    async def test_dip_maps_to_verificacion_funcionario(self, mock_db):
        mock_db.fetchrow.return_value = {
            "id": "doc-id",
            "document_type": "dip",
            "display_name": "Mi DIP",
            "file_name": "dip.pdf",
            "expiry_date": None,
            "document_category": "identity",
            "holder_name": "Juan Test",
        }
        mock_db.fetch.side_effect = [[], []]

        result = await prepare_renewal(mock_db, user_id="test-id", document_id="doc-id")
        assert result["workflow_code"] == "verificacion_funcionario"

    @pytest.mark.asyncio
    async def test_unknown_document_type_no_workflow(self, mock_db):
        """Unknown document type should return no_workflow status."""
        mock_db.fetchrow.return_value = {
            "id": "doc-id",
            "document_type": "factura_electronica",
            "display_name": "Factura",
            "file_name": "factura.pdf",
            "expiry_date": None,
            "document_category": "financial",
            "holder_name": "Juan Test",
        }
        result = await prepare_renewal(mock_db, user_id="test-id", document_id="doc-id")
        assert result["status"] == "no_workflow"

    @pytest.mark.asyncio
    async def test_case_insensitive_document_type(self, mock_db):
        """Document type lookup should be case insensitive."""
        mock_db.fetchrow.return_value = {
            "id": "doc-id",
            "document_type": "PASAPORTE",
            "display_name": "Mi Pasaporte",
            "file_name": "passport.pdf",
            "expiry_date": None,
            "document_category": "identity",
            "holder_name": "Test User",
        }
        mock_db.fetch.side_effect = [[], []]

        result = await prepare_renewal(mock_db, user_id="test-id", document_id="doc-id")
        assert result["status"] == "prepared"
        assert result["workflow_code"] == "pasaporte_renovacion"

    @pytest.mark.asyncio
    async def test_licencia_conducir_maps_to_renovation(self, mock_db):
        mock_db.fetchrow.return_value = {
            "id": "doc-id",
            "document_type": "licencia_conducir",
            "display_name": "Licencia",
            "file_name": "licencia.pdf",
            "expiry_date": None,
            "document_category": "vehicle",
            "holder_name": "Test",
        }
        mock_db.fetch.side_effect = [[], []]

        result = await prepare_renewal(mock_db, user_id="test-id", document_id="doc-id")
        assert result["workflow_code"] == "certificado_conducir_renovacion"

    @pytest.mark.asyncio
    async def test_permiso_residencia_maps_to_renovation(self, mock_db):
        mock_db.fetchrow.return_value = {
            "id": "doc-id",
            "document_type": "permiso_residencia",
            "display_name": "Residencia",
            "file_name": "residencia.pdf",
            "expiry_date": None,
            "document_category": "identity",
            "holder_name": "Test",
        }
        mock_db.fetch.side_effect = [[], []]

        result = await prepare_renewal(mock_db, user_id="test-id", document_id="doc-id")
        assert result["workflow_code"] == "residencia_renovacion"

    @pytest.mark.asyncio
    async def test_carnet_funcionario_maps_correctly(self, mock_db):
        mock_db.fetchrow.return_value = {
            "id": "doc-id",
            "document_type": "carnet_funcionario",
            "display_name": "Carnet",
            "file_name": "carnet.pdf",
            "expiry_date": None,
            "document_category": "identity",
            "holder_name": "Test",
        }
        mock_db.fetch.side_effect = [[], []]

        result = await prepare_renewal(mock_db, user_id="test-id", document_id="doc-id")
        assert result["workflow_code"] == "carnet_funcionario"

    @pytest.mark.asyncio
    async def test_workflow_code_override_via_kwargs(self, mock_db):
        """Explicit workflow_code in kwargs should override the type-based lookup."""
        mock_db.fetchrow.return_value = {
            "id": "doc-id",
            "document_type": "unknown_type",
            "display_name": "Doc",
            "file_name": "doc.pdf",
            "expiry_date": None,
            "document_category": "other",
            "holder_name": "Test",
        }
        mock_db.fetch.side_effect = [[], []]

        result = await prepare_renewal(
            mock_db, user_id="test-id", document_id="doc-id",
            workflow_code="pasaporte_nuevo",
        )
        assert result["status"] == "prepared"
        assert result["workflow_code"] == "pasaporte_nuevo"

    @pytest.mark.asyncio
    async def test_readiness_embedded_in_result(self, mock_db):
        """The readiness check result should be nested inside the renewal result."""
        mock_db.fetchrow.return_value = {
            "id": "doc-id",
            "document_type": "pasaporte",
            "display_name": "Mi Pasaporte",
            "file_name": "passport.pdf",
            "expiry_date": None,
            "document_category": "identity",
            "holder_name": "Test",
        }
        mock_db.fetch.side_effect = [[], []]

        result = await prepare_renewal(mock_db, user_id="test-id", document_id="doc-id")
        assert "readiness" in result
        assert "readiness_score" in result["readiness"]
        assert "can_start" in result["readiness"]


# =============================================================================
# 15. GET AGENT MEMORY
# =============================================================================


class TestGetAgentMemory:
    """Test get_agent_memory transparency tool."""

    @pytest.mark.asyncio
    async def test_requires_user_id(self, mock_db):
        result = await get_agent_memory(mock_db, user_id="")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_empty_memory(self, mock_db):
        # Two fetch calls: one for memories, one for permissions
        mock_db.fetch.side_effect = [[], []]
        result = await get_agent_memory(mock_db, user_id="test-id")
        assert result["memory_count"] == 0
        assert result["memories"] == []
        assert result["permission_count"] == 0
        assert result["permissions"] == []

    @pytest.mark.asyncio
    async def test_with_memories(self, mock_db):
        from uuid import uuid4
        memories = [
            {
                "id": uuid4(),
                "memory_type": "preference",
                "content": "Prefers Spanish",
                "confidence": 0.85,
                "confirmation_count": 3,
                "rejection_count": 0,
                "created_at": "2025-01-01",
                "last_used_at": "2025-12-01",
            },
            {
                "id": uuid4(),
                "memory_type": "fact",
                "content": "Lives in Malabo",
                "confidence": 0.7,
                "confirmation_count": 1,
                "rejection_count": 1,
                "created_at": "2025-06-01",
                "last_used_at": None,
            },
        ]
        permissions = [
            {
                "permission_type": "read_vault",
                "scope": "personal",
                "granted_at": "2025-01-01",
                "usage_count": 5,
                "level": 1,
            },
        ]
        mock_db.fetch.side_effect = [memories, permissions]

        result = await get_agent_memory(mock_db, user_id="test-id")
        assert result["memory_count"] == 2
        assert result["permission_count"] == 1
        assert result["memories"][0]["type"] == "preference"
        assert result["memories"][0]["content"] == "Prefers Spanish"
        assert result["memories"][0]["confidence"] == 0.85
        assert result["memories"][0]["confirmations"] == 3
        assert result["memories"][0]["rejections"] == 0
        assert result["permissions"][0]["type"] == "read_vault"
        assert result["permissions"][0]["level"] == 1

    @pytest.mark.asyncio
    async def test_summary_includes_count(self, mock_db):
        mock_db.fetch.side_effect = [[], []]
        result = await get_agent_memory(mock_db, user_id="test-id")
        assert "summary" in result
        assert "0 cosas" in result["summary"]

    @pytest.mark.asyncio
    async def test_summary_mentions_permissions_if_present(self, mock_db):
        memories = [
            {
                "id": "mem-1",
                "memory_type": "fact",
                "content": "Test",
                "confidence": 0.5,
                "confirmation_count": 0,
                "rejection_count": 0,
                "created_at": "2025-01-01",
                "last_used_at": None,
            },
        ]
        permissions = [
            {
                "permission_type": "read_vault",
                "scope": "personal",
                "granted_at": "2025-01-01",
                "usage_count": 0,
                "level": 1,
            },
        ]
        mock_db.fetch.side_effect = [memories, permissions]
        result = await get_agent_memory(mock_db, user_id="test-id")
        assert "1 permisos activos" in result["summary"]


# =============================================================================
# WORKFLOW MAP COMPLETENESS
# =============================================================================


class TestWorkflowMapCompleteness:
    """Validate the document_type -> workflow_code mapping in prepare_renewal."""

    EXPECTED_MAPPINGS = {
        "dip": "verificacion_funcionario",
        "dip_gq": "verificacion_funcionario",
        "pasaporte": "pasaporte_renovacion",
        "pasaporte_gq": "pasaporte_renovacion",
        "permiso_residencia": "residencia_renovacion",
        "licencia_conducir": "certificado_conducir_renovacion",
        "permiso_conducir": "certificado_conducir_renovacion",
        "carnet_funcionario": "carnet_funcionario",
    }

    @pytest.mark.asyncio
    @pytest.mark.parametrize("doc_type,expected_wf", list(EXPECTED_MAPPINGS.items()))
    async def test_workflow_mapping(self, mock_db, doc_type, expected_wf):
        """Each known document type should map to the correct workflow code."""
        mock_db.fetchrow.return_value = {
            "id": "doc-id",
            "document_type": doc_type,
            "display_name": f"Test {doc_type}",
            "file_name": f"{doc_type}.pdf",
            "expiry_date": None,
            "document_category": "identity",
            "holder_name": "Test User",
        }
        mock_db.fetch.side_effect = [[], []]

        result = await prepare_renewal(mock_db, user_id="test-id", document_id="doc-id")
        assert result["status"] == "prepared", f"Failed for doc_type={doc_type}"
        assert result["workflow_code"] == expected_wf, (
            f"Expected {expected_wf} for doc_type={doc_type}, got {result['workflow_code']}"
        )
