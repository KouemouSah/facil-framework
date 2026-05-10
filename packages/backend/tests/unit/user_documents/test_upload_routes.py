"""
Route tests for user_documents UPLOAD endpoint — MOCKED database.

Validates:
- File upload creates record via mock DB
- MIME type validation (OWASP A08)
- Magic bytes integrity check
- Dangerous extension blocking
- Empty file rejection
- Auth enforcement (401 without token)
- Duplicate detection
- Response schema

DB is MOCKED — tests set mock_db return values before each API call.
"""

import pytest
from io import BytesIO
from uuid import uuid4
from datetime import datetime

BASE = "/api/v1/user-documents"


def _make_doc_row(
    doc_id=None,
    user_id="e709d664-0789-40e0-b5fe-1146fa6660e6",
    file_name="test.pdf",
    source="personal",
    document_type="unknown",
    document_category="other",
    status="processing",
    file_size_bytes=246,
    mime_type="application/pdf",
    file_hash="abc123",
    **overrides,
):
    """Build a dict matching the user_documents DB row shape (RETURNING *)."""
    if doc_id is None:
        doc_id = uuid4()
    now = datetime.utcnow()
    row = {
        "id": doc_id,
        "user_id": user_id,
        "source": source,
        "document_type": document_type,
        "document_category": document_category,
        "template_code": None,
        "file_path": f"user-documents/{user_id}/{file_hash[:12]}_{file_name}",
        "file_name": file_name,
        "file_size_bytes": file_size_bytes,
        "mime_type": mime_type,
        "file_hash": file_hash,
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
        "display_name": None,
        "notes": None,
        "is_favorite": False,
        "color_label": None,
        "status": status,
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


def _setup_upload_mocks(mock_db, created_row, duplicate_row=None):
    """Configure mock_db for a standard upload flow.

    Upload route calls fetchrow 3 times:
      1. get_quota_used -> {"used": 0}
      2. find_duplicate -> None or duplicate_row
      3. create_document -> created_row (RETURNING *)
    Then execute for log_access.
    """
    mock_db.fetchrow.side_effect = [
        {"used": 0},     # get_quota_used
        duplicate_row,    # find_duplicate
        created_row,      # create_document -> RETURNING *
    ]
    mock_db.execute.return_value = "INSERT 0 1"  # log_access


@pytest.mark.asyncio
class TestUploadRoutes:

    # -- UP-01: No auth -> 401 -----------------------------------------------

    async def test_no_auth_returns_401(self, unauth_client):
        """UP-01: Upload without auth token must be rejected."""
        response = await unauth_client.post(f"{BASE}/upload")
        assert response.status_code in (401, 403), (
            f"Expected 401/403, got {response.status_code}"
        )

    # -- UP-02: Valid PDF upload -> 201 ---------------------------------------

    async def test_valid_pdf_upload_creates_document(
        self, client, valid_pdf_bytes, mock_db
    ):
        """UP-02: Upload a valid PDF. Expect 201 with correct response."""
        doc_id = uuid4()
        created_row = _make_doc_row(
            doc_id=doc_id,
            file_name="test_integration.pdf",
            status="processing",
        )
        _setup_upload_mocks(mock_db, created_row)

        files = {
            "file": ("test_integration.pdf", BytesIO(valid_pdf_bytes), "application/pdf")
        }
        response = await client.post(f"{BASE}/upload", files=files)

        assert response.status_code == 201, (
            f"Expected 201, got {response.status_code}: {response.text}"
        )
        data = response.json()
        assert data["file_name"] == "test_integration.pdf"
        assert data["status"] == "processing"
        assert "id" in data

    # -- UP-03: Upload with type hint populates document_type -----------------

    async def test_upload_with_type_hint(
        self, client, valid_pdf_bytes, mock_db
    ):
        """UP-03: Upload with document_type_hint stores the type."""
        doc_id = uuid4()
        created_row = _make_doc_row(
            doc_id=doc_id,
            file_name="passport.pdf",
            document_type="passport",
            document_category="identity",
        )
        _setup_upload_mocks(mock_db, created_row)

        files = {
            "file": ("passport.pdf", BytesIO(valid_pdf_bytes), "application/pdf")
        }
        response = await client.post(
            f"{BASE}/upload?document_type_hint=passport",
            files=files,
        )
        assert response.status_code == 201

    # -- UP-04: Upload JPEG also works ----------------------------------------

    async def test_valid_jpeg_upload(self, client, valid_jpeg_bytes, mock_db):
        """UP-04: Upload a valid JPEG image creates a record."""
        doc_id = uuid4()
        created_row = _make_doc_row(
            doc_id=doc_id,
            file_name="photo_id.jpg",
            mime_type="image/jpeg",
        )
        _setup_upload_mocks(mock_db, created_row)

        files = {
            "file": ("photo_id.jpg", BytesIO(valid_jpeg_bytes), "image/jpeg")
        }
        response = await client.post(f"{BASE}/upload", files=files)

        assert response.status_code == 201
        data = response.json()
        assert data["file_name"] == "photo_id.jpg"

    # -- UP-05: Empty file -> 400 ---------------------------------------------

    async def test_empty_file_rejected(self, client):
        """UP-05: An empty file (0 bytes) must be rejected with 400."""
        files = {"file": ("empty.pdf", BytesIO(b""), "application/pdf")}
        response = await client.post(f"{BASE}/upload", files=files)
        assert response.status_code == 400

    # -- UP-06: File too small (< 4 bytes) -> 400 -----------------------------

    async def test_tiny_file_rejected(self, client):
        """UP-06: A file smaller than 4 bytes fails magic byte detection."""
        files = {"file": ("tiny.pdf", BytesIO(b"AB"), "application/pdf")}
        response = await client.post(f"{BASE}/upload", files=files)
        assert response.status_code == 400

    # -- UP-07: Dangerous extension .exe -> 400 --------------------------------

    async def test_dangerous_extension_exe_rejected(self, client):
        """UP-07: .exe extension blocked (OWASP A08)."""
        files = {
            "file": (
                "malware.exe",
                BytesIO(b"MZ" + b"\x00" * 100),
                "application/pdf",
            )
        }
        response = await client.post(f"{BASE}/upload", files=files)
        assert response.status_code == 400

    # -- UP-08: Dangerous extension .bat -> 400 --------------------------------

    async def test_dangerous_extension_bat_rejected(self, client):
        """UP-08: .bat extension blocked (OWASP A08)."""
        files = {
            "file": (
                "script.bat",
                BytesIO(b"%PDF-1.4 fake" + b"\x00" * 100),
                "application/pdf",
            )
        }
        response = await client.post(f"{BASE}/upload", files=files)
        assert response.status_code == 400

    # -- UP-09: Invalid MIME text/html -> 400 ----------------------------------

    async def test_invalid_mime_html_rejected(self, client):
        """UP-09: text/html is not in the allowed MIME types."""
        files = {
            "file": (
                "page.html",
                BytesIO(b"<html></html>" + b"\x00" * 50),
                "text/html",
            )
        }
        response = await client.post(f"{BASE}/upload", files=files)
        assert response.status_code == 400

    # -- UP-10: Invalid MIME application/json -> 400 ---------------------------

    async def test_invalid_mime_json_rejected(self, client):
        """UP-10: application/json is not an allowed MIME type."""
        files = {
            "file": (
                "data.json",
                BytesIO(b'{"key":"value"}' + b"\x00" * 50),
                "application/json",
            )
        }
        response = await client.post(f"{BASE}/upload", files=files)
        assert response.status_code == 400

    # -- UP-11: Magic byte mismatch (declared PDF, actual JPEG) ----------------

    async def test_magic_bytes_mismatch_rejected(self, client, valid_jpeg_bytes):
        """UP-11: Declared MIME is PDF but actual bytes are JPEG (spoofed Content-Type)."""
        files = {
            "file": ("fake.pdf", BytesIO(valid_jpeg_bytes), "application/pdf")
        }
        response = await client.post(f"{BASE}/upload", files=files)
        assert response.status_code == 400

    # -- UP-12: Duplicate upload returns duplicate info ------------------------

    async def test_duplicate_upload_returns_duplicate_info(
        self, client, valid_pdf_bytes, mock_db
    ):
        """UP-12: Uploading a file with same hash signals duplicate."""
        first_id = uuid4()
        doc_id = uuid4()

        existing_dup = _make_doc_row(doc_id=first_id, file_name="doc_orig.pdf")
        created_row = _make_doc_row(doc_id=doc_id, file_name="doc_copy.pdf")

        _setup_upload_mocks(mock_db, created_row, duplicate_row=existing_dup)

        files = {
            "file": ("doc_copy.pdf", BytesIO(valid_pdf_bytes), "application/pdf")
        }
        response = await client.post(f"{BASE}/upload", files=files)
        assert response.status_code == 201
        data = response.json()
        assert data["duplicate"] is not None
        assert data["duplicate"]["existing_document_id"] == str(first_id)

    # -- UP-14: Response fields match UploadResult schema ----------------------

    async def test_upload_response_schema(
        self, client, valid_pdf_bytes, mock_db
    ):
        """UP-14: Response must include id, status, file_name, file_size_bytes."""
        doc_id = uuid4()
        created_row = _make_doc_row(
            doc_id=doc_id,
            file_name="schema_test.pdf",
            file_size_bytes=246,
        )
        _setup_upload_mocks(mock_db, created_row)

        files = {
            "file": ("schema_test.pdf", BytesIO(valid_pdf_bytes), "application/pdf")
        }
        resp = await client.post(f"{BASE}/upload", files=files)
        assert resp.status_code == 201
        data = resp.json()

        assert "id" in data
        assert data["status"] == "processing"
        assert data["file_name"] == "schema_test.pdf"
        assert isinstance(data["file_size_bytes"], int)
        assert data["file_size_bytes"] > 0
