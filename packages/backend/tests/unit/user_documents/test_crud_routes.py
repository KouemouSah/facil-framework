"""
Route tests for user_documents CRUD endpoints — MOCKED database.

Validates:
- GET /{id}: document detail retrieval, 404 for nonexistent
- PUT /{id}: metadata update (display_name, notes, color_label, category)
- PUT /{id}/archive: archive sets status='archived'
- DELETE /{id}: soft delete
- OWASP A01: User B cannot read/update/delete User A's documents
- Auth enforcement (401 without token)

DB is MOCKED — tests set mock_db return values before each API call.
"""

import pytest
from uuid import uuid4
from datetime import datetime, date

BASE = "/api/v1/user-documents"

# Must match conftest
TEST_USER_ID_STR = "e709d664-0789-40e0-b5fe-1146fa6660e6"
SECOND_USER_ID_STR = "a5cfc4b3-50b4-4473-b6b7-6351b318a313"


def _make_doc_row(doc_id=None, user_id=TEST_USER_ID_STR, **overrides):
    """Build a dict matching user_documents row for mock DB responses."""
    if doc_id is None:
        doc_id = uuid4()
    now = datetime.utcnow()
    row = {
        "id": doc_id,
        "user_id": user_id,
        "source": "personal",
        "document_type": "dip",
        "document_category": "identity",
        "template_code": None,
        "file_path": f"user-documents/{user_id}/abc123/doc.pdf",
        "file_name": "crud_test.pdf",
        "file_size_bytes": 1024000,
        "mime_type": "application/pdf",
        "file_hash": "abc123def456",
        "thumbnail_path": None,
        "extraction_data": None,
        "extraction_confidence": None,
        "extraction_status": "pending",
        "document_number": None,
        "holder_name": None,
        "issue_date": None,
        "expiry_date": None,
        "issuing_authority": None,
        "classification_method": None,
        "classification_confidence": None,
        "display_name": "Mon DIP",
        "notes": None,
        "is_favorite": False,
        "color_label": None,
        "status": "active",
        "is_verified": False,
        "verified_at": None,
        "replaces_document_id": None,
        "source_request_id": None,
        "source_document_id": None,
        "generation_type": None,
        "title_es": None, "title_fr": None, "title_en": None,
        "reference_number": None, "verification_code": None,
        "valid_until": None,
        "created_at": now,
        "updated_at": now,
        "archived_at": None,
        "deleted_at": None,
    }
    row.update(overrides)
    return row


@pytest.mark.asyncio
class TestCrudRoutes:

    # -- CR-01: GET /{id} returns full detail ---------------------------------

    async def test_get_document_detail(self, client, mock_db):
        """CR-01: GET /{id} returns full document detail."""
        doc_id = uuid4()
        doc_row = _make_doc_row(doc_id=doc_id)

        # get_document calls: find_by_id(fetchrow) -> db.fetch(workflow_tags) -> log_access(execute)
        mock_db.fetchrow.return_value = doc_row
        mock_db.fetch.return_value = []  # workflow tags
        mock_db.execute.return_value = "INSERT 0 1"

        response = await client.get(f"{BASE}/{doc_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(doc_id)
        assert data["file_name"] == "crud_test.pdf"
        assert "document_type" in data
        assert "category" in data
        assert "status" in data
        assert "source" in data
        assert "file_size_bytes" in data
        assert "created_at" in data

    # -- CR-02: Non-existent document -> 404 ----------------------------------

    async def test_get_nonexistent_returns_404(self, client, mock_db):
        """CR-02: GET with a UUID that does not exist returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        mock_db.fetchrow.return_value = None  # find_by_id -> not found

        response = await client.get(f"{BASE}/{fake_id}")
        assert response.status_code == 404

    # -- CR-03: OWASP A01 — User B cannot access User A's doc ----------------
    # Note: With mocked DB, we simulate this by having find_by_id return None
    # (the repo filters by user_id, so user_b's ID won't match user_a's doc)

    async def test_owasp_wrong_user_cannot_read(
        self, client_user_b, mock_db
    ):
        """CR-03: OWASP A01 — User B must get 404 when accessing User A's doc."""
        doc_id = uuid4()
        # find_by_id with user_b's ID won't find user_a's doc
        mock_db.fetchrow.return_value = None

        response = await client_user_b.get(f"{BASE}/{doc_id}")
        assert response.status_code == 404

    # -- CR-10: PUT /{id} updates display_name --------------------------------

    async def test_update_display_name(self, client, mock_db):
        """CR-10: PUT /{id} with display_name updates the document."""
        doc_id = uuid4()
        updated_row = _make_doc_row(
            doc_id=doc_id,
            display_name="Mon Passeport Renomme",
        )

        # update_metadata calls fetchrow (RETURNING *)
        mock_db.fetchrow.return_value = updated_row

        response = await client.put(
            f"{BASE}/{doc_id}",
            json={"display_name": "Mon Passeport Renomme"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["display_name"] == "Mon Passeport Renomme"

    # -- CR-11: PUT /{id} updates notes ---------------------------------------

    async def test_update_notes(self, client, mock_db):
        """CR-11: PUT /{id} with notes stores them."""
        doc_id = uuid4()
        updated_row = _make_doc_row(
            doc_id=doc_id,
            notes="Test note integration",
        )
        mock_db.fetchrow.return_value = updated_row

        response = await client.put(
            f"{BASE}/{doc_id}",
            json={"notes": "Test note integration"},
        )
        assert response.status_code == 200

    # -- CR-12: PUT /{id} updates color_label and category --------------------

    async def test_update_color_and_category(self, client, mock_db):
        """CR-12: PUT /{id} updates color_label and category."""
        doc_id = uuid4()
        updated_row = _make_doc_row(
            doc_id=doc_id,
            color_label="green",
            document_category="legal",
        )
        mock_db.fetchrow.return_value = updated_row

        response = await client.put(
            f"{BASE}/{doc_id}",
            json={"color_label": "green", "category": "legal"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["color_label"] == "green"
        assert data["category"] == "legal"

    # -- CR-13: OWASP — User B cannot update User A's doc --------------------

    async def test_update_wrong_user_returns_404(self, client_user_b, mock_db):
        """CR-13: OWASP A01 — User B cannot update User A's doc."""
        doc_id = uuid4()
        mock_db.fetchrow.return_value = None  # update_metadata -> not found

        response = await client_user_b.put(
            f"{BASE}/{doc_id}",
            json={"display_name": "Hacked"},
        )
        assert response.status_code == 404

    # -- CR-14: PUT nonexistent doc -> 404 ------------------------------------

    async def test_update_nonexistent_returns_404(self, client, mock_db):
        """CR-14: PUT on a UUID that doesn't exist returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        mock_db.fetchrow.return_value = None

        response = await client.put(
            f"{BASE}/{fake_id}",
            json={"display_name": "Ghost"},
        )
        assert response.status_code == 404

    # -- CR-16: Archive sets status='archived' --------------------------------

    async def test_archive_document(self, client, mock_db):
        """CR-16: PUT /{id}/archive sets status to 'archived'."""
        doc_id = uuid4()
        # archive_document calls db.execute -> checks "UPDATE 1"
        mock_db.execute.return_value = "UPDATE 1"

        response = await client.put(f"{BASE}/{doc_id}/archive")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["status"] == "archived"

    # -- CR-17: Archive already archived doc -> 404 ---------------------------

    async def test_archive_already_archived_returns_404(self, client, mock_db):
        """CR-17: Archiving an already archived doc returns 404."""
        doc_id = uuid4()
        mock_db.execute.return_value = "UPDATE 0"

        response = await client.put(f"{BASE}/{doc_id}/archive")
        assert response.status_code == 404

    # -- CR-18: Soft delete ---------------------------------------------------

    async def test_delete_document(self, client, mock_db):
        """CR-18: DELETE /{id} soft-deletes (status='deleted')."""
        doc_id = uuid4()
        mock_db.execute.return_value = "UPDATE 1"

        response = await client.delete(f"{BASE}/{doc_id}")
        assert response.status_code == 204

    # -- CR-19: OWASP — User B cannot delete User A's doc --------------------

    async def test_delete_wrong_user_returns_404(self, client_user_b, mock_db):
        """CR-19: OWASP A01 — User B cannot delete User A's doc."""
        doc_id = uuid4()
        mock_db.execute.return_value = "UPDATE 0"

        response = await client_user_b.delete(f"{BASE}/{doc_id}")
        assert response.status_code == 404

    # -- CR-20: Delete already deleted doc -> 404 -----------------------------

    async def test_delete_already_deleted_returns_404(self, client, mock_db):
        """CR-20: Deleting an already soft-deleted doc returns 404."""
        doc_id = uuid4()
        mock_db.execute.return_value = "UPDATE 0"

        response = await client.delete(f"{BASE}/{doc_id}")
        assert response.status_code == 404

    # -- CR-21: Deleted doc not visible via GET --------------------------------

    async def test_deleted_doc_not_visible(self, client, mock_db):
        """CR-21: After soft delete, GET /{id} returns 404."""
        doc_id = uuid4()
        mock_db.fetchrow.return_value = None  # find_by_id filters deleted

        response = await client.get(f"{BASE}/{doc_id}")
        assert response.status_code == 404

    # -- CR-22: No auth on GET -> 401 -----------------------------------------

    async def test_get_no_auth_returns_401(self, unauth_client):
        """CR-22: GET /{id} without auth returns 401."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await unauth_client.get(f"{BASE}/{fake_id}")
        assert response.status_code in (401, 403)

    # -- CR-23: No auth on PUT -> 401 -----------------------------------------

    async def test_update_no_auth_returns_401(self, unauth_client):
        """CR-23: PUT /{id} without auth returns 401."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await unauth_client.put(
            f"{BASE}/{fake_id}",
            json={"display_name": "No auth"},
        )
        assert response.status_code in (401, 403)

    # -- CR-24: No auth on DELETE -> 401 --------------------------------------

    async def test_delete_no_auth_returns_401(self, unauth_client):
        """CR-24: DELETE /{id} without auth returns 401."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await unauth_client.delete(f"{BASE}/{fake_id}")
        assert response.status_code in (401, 403)
