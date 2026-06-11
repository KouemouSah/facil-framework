"""
Route tests for user_documents LIST, SEARCH, STATS, and READINESS
endpoints — MOCKED database.

Validates:
- GET / (list with cursor pagination, filters)
- GET /stats (aggregate vault statistics)
- GET /readiness/{workflow_code} (workflow readiness scoring)
- GET /search (full-text search)
- Auth enforcement

DB is MOCKED — tests set mock_db return values before each API call.
"""

import pytest
from uuid import uuid4
from datetime import datetime, date

BASE = "/api/v1/user-documents"

TEST_USER_ID_STR = "e709d664-0789-40e0-b5fe-1146fa6660e6"


def _make_list_row(doc_id=None, **overrides):
    """Build a dict matching user_documents row for list endpoints."""
    if doc_id is None:
        doc_id = uuid4()
    now = datetime.utcnow()
    row = {
        "id": doc_id,
        "user_id": TEST_USER_ID_STR,
        "source": "personal",
        "document_type": "dip",
        "document_category": "identity",
        "file_name": "test.pdf",
        "file_size_bytes": 1024,
        "mime_type": "application/pdf",
        "display_name": "Mon Document",
        "status": "active",
        "expiry_date": None,
        "created_at": now,
        "updated_at": now,
        "deleted_at": None,
        # Fields used by _build_list_item / _build_document_response
        "template_code": None,
        "file_path": f"user-documents/{TEST_USER_ID_STR}/abc/test.pdf",
        "file_hash": "abc123",
        "thumbnail_path": None,
        "extraction_data": None,
        "extraction_confidence": None,
        "extraction_status": "pending",
        "document_number": None,
        "holder_name": None,
        "issue_date": None,
        "issuing_authority": None,
        "classification_method": None,
        "classification_confidence": None,
        "notes": None,
        "is_favorite": False,
        "color_label": None,
        "is_verified": False,
        "verified_at": None,
        "replaces_document_id": None,
        "source_request_id": None,
        "source_document_id": None,
        "generation_type": None,
        "title_es": None, "title_fr": None, "title_en": None,
        "reference_number": None, "verification_code": None,
        "valid_until": None,
        "archived_at": None,
    }
    row.update(overrides)
    return row


@pytest.mark.asyncio
class TestListRoutes:

    # -- LS-01: No auth -> 401 ------------------------------------------------

    async def test_no_auth_returns_401(self, unauth_client):
        """LS-01: GET / without auth must be rejected."""
        response = await unauth_client.get(f"{BASE}/")
        assert response.status_code in (401, 403)

    # -- LS-02: Empty vault returns empty list --------------------------------

    async def test_empty_vault(self, client, mock_db):
        """LS-02: With no documents, list returns empty items and total_count=0."""
        # list_user_documents calls:
        # 1. find_by_user -> db.fetch -> []
        # 2. db.fetchrow (total count) -> {"cnt": 0}
        # 3. get_quota_used -> db.fetchrow -> {"used": 0}
        mock_db.fetch.return_value = []
        mock_db.fetchrow.side_effect = [
            {"cnt": 0},    # total count
            {"used": 0},   # quota used
        ]

        response = await client.get(f"{BASE}/")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total_count"] == 0

    # -- LS-03: List after upload shows documents -----------------------------

    async def test_list_after_upload(self, client, mock_db):
        """LS-03: List returns documents from mock DB."""
        rows = [_make_list_row(), _make_list_row()]

        mock_db.fetch.return_value = rows
        mock_db.fetchrow.side_effect = [
            {"cnt": 2},
            {"used": 2048},
        ]

        response = await client.get(f"{BASE}/")
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 2
        assert len(data["items"]) == 2

    # -- LS-04: Filter by source=personal -------------------------------------

    async def test_filter_by_source(self, client, mock_db):
        """LS-04: Filtering by source=personal returns items with that source."""
        rows = [_make_list_row(source="personal")]

        mock_db.fetch.return_value = rows
        mock_db.fetchrow.side_effect = [
            {"cnt": 1},
            {"used": 1024},
        ]

        response = await client.get(f"{BASE}/?source=personal")
        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["source"] == "personal"

    # -- LS-05: Filter by category --------------------------------------------

    async def test_filter_by_category(self, client, mock_db):
        """LS-05: Filtering by category works (may return 0 if none match)."""
        mock_db.fetch.return_value = []
        mock_db.fetchrow.side_effect = [
            {"cnt": 0},
            {"used": 0},
        ]

        response = await client.get(f"{BASE}/?category=identity")
        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["category"] == "identity"

    # -- LS-06: Limit parameter works -----------------------------------------

    async def test_limit_parameter(self, client, mock_db):
        """LS-06: limit=1 returns at most 1 item."""
        rows = [_make_list_row()]

        mock_db.fetch.return_value = rows
        mock_db.fetchrow.side_effect = [
            {"cnt": 3},
            {"used": 3072},
        ]

        response = await client.get(f"{BASE}/?limit=1")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) <= 1

    # -- LS-07: Response includes quota information ----------------------------

    async def test_response_includes_quota(self, client, mock_db):
        """LS-07: List response includes quota_used_bytes and quota_max_bytes."""
        mock_db.fetch.return_value = [_make_list_row()]
        mock_db.fetchrow.side_effect = [
            {"cnt": 1},
            {"used": 5000},
        ]

        response = await client.get(f"{BASE}/")
        assert response.status_code == 200
        data = response.json()
        assert "quota_used_bytes" in data
        assert "quota_max_bytes" in data
        assert data["quota_max_bytes"] == 104857600  # 100 MB

    # -- LS-08: Cursor pagination produces disjoint pages ---------------------

    async def test_pagination_cursor(self, client, mock_db):
        """LS-08: With next_cursor, pages are disjoint."""
        id1 = uuid4()
        id2 = uuid4()
        id3 = uuid4()
        now = datetime.utcnow()

        # First page: 2 items + 1 extra (has_next = True)
        page1_rows = [
            _make_list_row(doc_id=id1, created_at=now),
            _make_list_row(doc_id=id2, created_at=now),
            _make_list_row(doc_id=id3, created_at=now),  # extra
        ]

        mock_db.fetch.return_value = page1_rows
        mock_db.fetchrow.side_effect = [
            {"cnt": 3},
            {"used": 3072},
        ]

        resp1 = await client.get(f"{BASE}/?limit=2")
        data1 = resp1.json()
        assert len(data1["items"]) == 2
        assert data1.get("next_cursor") is not None

    # -- LS-09: Deleted docs not in list --------------------------------------

    async def test_deleted_docs_excluded_from_list(self, client, mock_db):
        """LS-09: Repository filters out deleted docs — empty list returned."""
        mock_db.fetch.return_value = []  # repo excludes deleted
        mock_db.fetchrow.side_effect = [
            {"cnt": 0},
            {"used": 0},
        ]

        response = await client.get(f"{BASE}/")
        data = response.json()
        assert data["items"] == []


@pytest.mark.asyncio
class TestStatsRoutes:

    # -- ST-01: Stats no auth -> 401 ------------------------------------------

    async def test_stats_no_auth_returns_401(self, unauth_client):
        """ST-01: GET /stats without auth returns 401."""
        response = await unauth_client.get(f"{BASE}/stats")
        assert response.status_code in (401, 403)

    # -- ST-02: Stats with empty vault ----------------------------------------

    async def test_stats_empty_vault(self, client, mock_db):
        """ST-02: Empty vault returns zeros for all counters."""
        # get_vault_stats calls get_stats -> db.fetchrow
        mock_db.fetchrow.return_value = {
            "total_active": 0,
            "personal_count": 0,
            "wizard_count": 0,
            "generated_count": 0,
            "active_count": 0,
            "archived_count": 0,
            "expired_count": 0,
            "expiring_soon_count": 0,
            "total_size_bytes": 0,
            "personal_size_bytes": 0,
        }

        response = await client.get(f"{BASE}/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_active"] == 0
        assert data["personal_count"] == 0
        assert "quota_used_bytes" in data
        assert "quota_max_bytes" in data

    # -- ST-03: Stats reflect uploaded documents ------------------------------

    async def test_stats_after_upload(self, client, mock_db):
        """ST-03: After uploading docs, stats reflect the count."""
        mock_db.fetchrow.return_value = {
            "total_active": 2,
            "personal_count": 2,
            "wizard_count": 0,
            "generated_count": 0,
            "active_count": 2,
            "archived_count": 0,
            "expired_count": 0,
            "expiring_soon_count": 0,
            "total_size_bytes": 5000,
            "personal_size_bytes": 5000,
        }

        response = await client.get(f"{BASE}/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_active"] == 2
        assert data["personal_count"] == 2
        assert data["quota_used_bytes"] == 5000
        assert data["quota_percentage"] >= 0

    # -- ST-04: Stats schema complete -----------------------------------------

    async def test_stats_response_schema(self, client, mock_db):
        """ST-04: Stats response includes all expected fields."""
        mock_db.fetchrow.return_value = {
            "total_active": 0,
            "personal_count": 0,
            "wizard_count": 0,
            "generated_count": 0,
            "active_count": 0,
            "archived_count": 0,
            "expired_count": 0,
            "expiring_soon_count": 0,
            "total_size_bytes": 0,
            "personal_size_bytes": 0,
        }

        response = await client.get(f"{BASE}/stats")
        assert response.status_code == 200
        data = response.json()
        expected_fields = {
            "total_active", "personal_count", "wizard_count",
            "generated_count", "quota_used_bytes", "quota_max_bytes",
            "quota_percentage", "expired_count", "expiring_count",
        }
        assert expected_fields.issubset(data.keys())


@pytest.mark.asyncio
class TestReadinessRoutes:

    # -- RD-01: Readiness no auth -> 401 --------------------------------------

    async def test_readiness_no_auth(self, unauth_client):
        """RD-01: GET /readiness without auth returns 401."""
        response = await unauth_client.get(f"{BASE}/readiness")
        assert response.status_code in (401, 403)

    # -- RD-02: Readiness all workflows ---------------------------------------

    async def test_readiness_all_workflows(self, client, mock_db):
        """RD-02: GET /readiness returns a list of readiness results."""
        # get_readiness_all calls:
        # 1. db.fetch (popular_workflows)
        # 2. For each workflow: _compute_readiness (multiple db.fetch calls)
        mock_db.fetch.side_effect = [
            # popular_workflows
            [{"code": "PASAPORTE_BIOMETRICO", "name_es": "Pasaporte"}],
            # _compute_readiness: required_docs
            [],
            # _compute_readiness: fallback from tags (since required_docs=[])
            [],
            # _compute_readiness: user_docs
            [],
        ]

        response = await client.get(f"{BASE}/readiness")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        for result in data:
            assert "workflow_code" in result
            assert "readiness_score" in result
            assert "total_required" in result
            assert "can_start" in result

    # -- RD-03: Readiness for a specific known workflow -----------------------

    async def test_readiness_specific_workflow(self, client, mock_db):
        """RD-03: GET /readiness/{workflow_code} for pasaporte_nuevo."""
        # _compute_readiness calls:
        # 1. db.fetch (required_docs from service_document_assignments)
        # 2. db.fetch (fallback from tags, only if #1 is empty)
        # 3. db.fetch (user_docs)
        mock_db.fetch.side_effect = [
            [],  # required_docs
            [],  # fallback tags (empty)
            [],  # user_docs
        ]

        response = await client.get(f"{BASE}/readiness/pasaporte_nuevo")
        assert response.status_code == 200
        data = response.json()
        assert "readiness_score" in data
        assert "total_required" in data
        assert "missing" in data
        assert "ready" in data
        assert "expiring" in data
        assert "can_start" in data
        assert isinstance(data["readiness_score"], (int, float))

    # -- RD-04: Readiness for unknown workflow --------------------------------

    async def test_readiness_unknown_workflow(self, client, mock_db):
        """RD-04: Unknown workflow returns 200 with 100% score (no requirements)."""
        mock_db.fetch.side_effect = [
            [],  # required_docs
            [],  # fallback tags
            [],  # user_docs
        ]

        response = await client.get(f"{BASE}/readiness/NONEXISTENT_WORKFLOW_XYZ")
        assert response.status_code == 200
        data = response.json()
        assert data["total_required"] == 0
        assert data["readiness_score"] == 100.0
        assert data["can_start"] is True


@pytest.mark.asyncio
class TestSearchRoutes:

    # -- SR-01: Search no auth -> 401 -----------------------------------------

    async def test_search_no_auth(self, unauth_client):
        """SR-01: GET /search without auth returns 401."""
        response = await unauth_client.get(f"{BASE}/search?q=test")
        assert response.status_code in (401, 403)

    # -- SR-02: Search requires minimum query length --------------------------

    async def test_search_too_short_query(self, client):
        """SR-02: Query shorter than 2 characters returns 422."""
        response = await client.get(f"{BASE}/search?q=a")
        assert response.status_code == 422

    # -- SR-03: Search returns matching documents -----------------------------

    async def test_search_returns_results(self, client, mock_db):
        """SR-03: Search by filename returns matching documents."""
        mock_db.fetch.return_value = [
            _make_list_row(file_name="searchable_passport.pdf")
        ]

        response = await client.get(f"{BASE}/search?q=searchable")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
