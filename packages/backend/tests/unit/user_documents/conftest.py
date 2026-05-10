"""
Shared fixtures for user_documents ROUTE tests.

DB is MOCKED (AsyncMock) for speed and reliability — no external deps needed.
Auth is MOCKED (dependency override returns mock user without JWT flow).
Storage, rate limiting, cache: all MOCKED.

Real user IDs from DB used for OWASP cross-user test identity.
"""

import pytest
import pytest_asyncio
from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4
from datetime import datetime, date, timedelta
from typing import AsyncGenerator

import httpx
from httpx import ASGITransport

# ============================================================================
# Stub cv2/numpy/pytesseract BEFORE any app import that might reach
# app.modules.documents (which has a hard dep on cv2).
# ============================================================================
import sys

for _mod_name in (
    "cv2", "numpy", "np", "pytesseract", "pdf2image",
    "PIL", "PIL.Image",
):
    if _mod_name not in sys.modules:
        sys.modules[_mod_name] = MagicMock()

# ============================================================================
# CONSTANTS — Real test user IDs (OWASP cross-user tests)
# ============================================================================

TEST_USER_ID = UUID("e709d664-0789-40e0-b5fe-1146fa6660e6")
TEST_USER_ID_STR = str(TEST_USER_ID)
TEST_USER_EMAIL = "libressay@gmail.com"

SECOND_USER_ID = UUID("a5cfc4b3-50b4-4473-b6b7-6351b318a313")
SECOND_USER_ID_STR = str(SECOND_USER_ID)
SECOND_USER_EMAIL = "user@odoolab.site"


# ============================================================================
# IDENTITY FIXTURES
# ============================================================================

@pytest.fixture
def user_id():
    return TEST_USER_ID


@pytest.fixture
def user_id_b():
    return SECOND_USER_ID


# ============================================================================
# MOCK USER FIXTURES — Match real DB users (UserResponse-compatible)
# ============================================================================

@pytest.fixture
def mock_user():
    """Primary test user (citizen). Matches real Supabase user."""
    user = MagicMock()
    user.id = TEST_USER_ID_STR  # str, matching UserResponse.id type
    user.email = TEST_USER_EMAIL
    user.role = "citizen"
    user.status = "active"
    user.first_name = "libre"
    user.last_name = "Gmil"
    user.preferred_language = "es"
    return user


@pytest.fixture
def mock_user_b():
    """Second test user for OWASP A01 cross-user tests."""
    user = MagicMock()
    user.id = SECOND_USER_ID_STR
    user.email = SECOND_USER_EMAIL
    user.role = "business"
    user.status = "active"
    user.first_name = "User"
    user.last_name = "Odoo"
    user.preferred_language = "es"
    return user


# ============================================================================
# MOCK DATABASE
# ============================================================================

@pytest.fixture
def mock_db():
    """AsyncMock DB connection with all needed methods.

    Tests configure return values via:
        mock_db.fetchrow.return_value = {...}
        mock_db.fetch.return_value = [...]
        mock_db.fetchval.return_value = 0
        mock_db.execute.return_value = "UPDATE 1"

    For multiple sequential calls:
        mock_db.fetchrow.side_effect = [result1, result2, ...]
    """
    db = AsyncMock()
    db.fetch = AsyncMock(return_value=[])
    db.fetchrow = AsyncMock(return_value=None)
    db.fetchval = AsyncMock(return_value=0)
    db.execute = AsyncMock(return_value="UPDATE 1")
    return db


# ============================================================================
# SAMPLE DATA FIXTURES
# ============================================================================

@pytest.fixture
def sample_doc_id():
    return uuid4()


@pytest.fixture
def sample_doc_row(user_id, sample_doc_id):
    """Complete DB row matching user_documents table schema.

    Used to set mock_db.fetchrow.return_value in tests.
    """
    return {
        "id": sample_doc_id,
        "user_id": user_id,
        "source": "personal",
        "document_type": "dip",
        "document_category": "identity",
        "template_code": "dip",
        "file_path": f"user-documents/{user_id}/personal/{sample_doc_id}/doc.pdf",
        "file_name": "doc.pdf",
        "file_size_bytes": 1024000,
        "mime_type": "application/pdf",
        "file_hash": "abc123def456789",
        "thumbnail_path": None,
        "extraction_data": {"numero_dip": "123456789"},
        "extraction_confidence": 0.85,
        "extraction_status": "completed",
        "document_number": "123456789",
        "holder_name": "Test User",
        "issue_date": date(2020, 1, 1),
        "expiry_date": date(2030, 12, 31),
        "issuing_authority": "CNEDOGE",
        "classification_method": "gemini",
        "classification_confidence": 0.9,
        "display_name": "Mon DIP",
        "notes": None,
        "is_favorite": False,
        "color_label": None,
        "status": "active",
        "is_verified": True,
        "verified_at": datetime(2026, 1, 15),
        "replaces_document_id": None,
        "source_request_id": None,
        "source_document_id": None,
        "generation_type": None,
        "title_es": None,
        "title_fr": None,
        "title_en": None,
        "reference_number": None,
        "verification_code": None,
        "valid_until": None,
        "created_at": datetime(2026, 1, 15, 10, 30, 0),
        "updated_at": datetime(2026, 1, 15, 10, 30, 0),
        "archived_at": None,
        "deleted_at": None,
    }


# ============================================================================
# FILE CONTENT FIXTURES — Valid magic bytes for integrity checks
# ============================================================================

@pytest.fixture
def valid_pdf_bytes() -> bytes:
    """Valid PDF magic bytes (passes OWASP A08 integrity check)."""
    return b"%PDF-1.4 test content for integration testing" + b"\x00" * 200


@pytest.fixture
def valid_jpeg_bytes() -> bytes:
    """Valid JPEG magic bytes (SOI marker)."""
    return b"\xff\xd8\xff\xe0" + b"\x00" * 200


@pytest.fixture
def valid_png_bytes() -> bytes:
    """Valid PNG magic bytes (8-byte signature)."""
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 200


# ============================================================================
# PATCH HELPER — All patches needed for route tests
# ============================================================================

def _apply_test_patches():
    """Apply all necessary patches for route tests.

    Returns an ExitStack that manages:
    1. Rate limiting -- always allow (avoids Redis connection).
    2. Firebase storage -- mocked upload + signed URL.
    3. Cache -- returns None to disable (avoids Redis connection).
    """
    stack = ExitStack()

    # 1. Rate limiting -- always allow
    async def _allow_rate_limit(*args, **kwargs):
        return (True, 99)

    stack.enter_context(patch(
        "app.modules.user_documents.api.user_documents_routes.check_rate_limit",
        side_effect=_allow_rate_limit,
    ))

    # 2. Firebase storage mock
    # The routes do lazy imports:
    #   from app.modules.documents.services.storage_service import firebase_storage_service
    # We patch the attribute on the actual module (sys.modules lookup).
    mock_storage = MagicMock()

    async def mock_upload(user_id, application_id, file, metadata=None):
        result = MagicMock()
        result.file_path = f"user-documents/{user_id}/{application_id}/test_file"
        result.file_url = "https://storage.example.com/fake-url"
        result.file_id = "fake-file-id"
        result.file_size = 246
        result.mime_type = "application/pdf"
        result.file_hash = "fakehash123"
        return result

    mock_storage.upload_user_document = AsyncMock(side_effect=mock_upload)

    async def mock_signed_url(file_path, expiration_hours=0.25):
        return f"https://storage.example.com/signed?path={file_path}"

    mock_storage.get_signed_url = AsyncMock(side_effect=mock_signed_url)

    # Patch on the actual Python module object (not the re-exported instance).
    # The __init__.py causes `from ... import storage_service` to resolve to
    # the FirebaseStorageService instance. We need the real module object.
    import importlib
    _mod = importlib.import_module("app.modules.documents.services.storage_service")
    stack.enter_context(patch.object(
        _mod, "firebase_storage_service", mock_storage,
    ))

    # 3. Cache -- return None to disable (avoids Redis "Event loop is closed")
    stack.enter_context(patch(
        "app.modules.user_documents.services.user_documents_service.get_cache",
        return_value=None,
    ))

    return stack


# ============================================================================
# HTTPX CLIENTS — Mocked auth + mocked DB + all patches
# ============================================================================

@pytest_asyncio.fixture
async def client(mock_user, mock_db) -> AsyncGenerator[httpx.AsyncClient, None]:
    """httpx AsyncClient authenticated as primary test user.

    Mocked database (AsyncMock) — routes call mock_db.fetch/fetchrow/execute.
    Auth mocked (get_current_user returns mock_user).
    Firebase storage, rate limiting, cache: all mocked.
    """
    from app.main import app
    from app.modules.auth.middleware.auth_middleware import get_current_user
    from app.database.connection import get_database

    async def override_auth():
        return mock_user

    async def override_get_database():
        yield mock_db

    app.dependency_overrides[get_current_user] = override_auth
    app.dependency_overrides[get_database] = override_get_database

    with _apply_test_patches():
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as c:
            yield c

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client_user_b(mock_user_b, mock_db) -> AsyncGenerator[httpx.AsyncClient, None]:
    """httpx AsyncClient authenticated as second user (OWASP tests).

    Same mock_db instance — tests must set mock_db return values accordingly.
    """
    from app.main import app
    from app.modules.auth.middleware.auth_middleware import get_current_user
    from app.database.connection import get_database

    async def override_auth():
        return mock_user_b

    async def override_get_database():
        yield mock_db

    app.dependency_overrides[get_current_user] = override_auth
    app.dependency_overrides[get_database] = override_get_database

    with _apply_test_patches():
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as c:
            yield c

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def unauth_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """httpx AsyncClient WITHOUT auth (for 401 tests).

    No dependency overrides — real auth middleware rejects requests
    without a valid Bearer token.
    """
    from app.main import app

    app.dependency_overrides.clear()

    with _apply_test_patches():
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as c:
            yield c

    app.dependency_overrides.clear()
