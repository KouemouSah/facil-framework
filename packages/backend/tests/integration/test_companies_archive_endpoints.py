# -*- coding: utf-8 -*-
"""
Validation tests for the companies soft-delete (archive) endpoints
introduced by migration 314.

Same posture as ``test_users_export_endpoint.py``: we don't bootstrap a full
DB session — instead we assert the **route shape and auth gate** plus the
fact that the endpoints are correctly registered in the OpenAPI spec.

Endpoints under test:
  POST   /api/v1/companies/{id}/archive
  POST   /api/v1/companies/{id}/unarchive
  DELETE /api/v1/companies/{id}                    (now hard-delete admin only)

End-to-end behaviour with real DB rows (409 on blockers, owner gate, audit
log persistence, citizen list filtering) is exercised at staging via the
manual smoke script in ``.claude/plans/SOFT_DELETE_COMPANIES_PLAN.md``.
"""

from fastapi.testclient import TestClient

from app.main import app

# A well-formed UUID — never matches a real row, but enough to make FastAPI
# accept the path parameter so we reach the auth dependency.
DUMMY_UUID = "00000000-0000-0000-0000-000000000001"


class TestArchiveEndpointShape:
    """Citizen archive route exists and demands auth."""

    def test_archive_unauthenticated_returns_403(self):
        """No Bearer ⇒ HTTPBearer dependency rejects with 401/403."""
        client = TestClient(app)
        response = client.post(f"/api/v1/companies/{DUMMY_UUID}/archive")
        assert response.status_code in (401, 403), (
            f"Expected 401/403 without auth, got {response.status_code}: "
            f"{response.text}"
        )

    def test_archive_invalid_token_returns_401_or_403(self):
        client = TestClient(app)
        response = client.post(
            f"/api/v1/companies/{DUMMY_UUID}/archive",
            headers={"Authorization": "Bearer not-a-real-jwt"},
        )
        assert response.status_code in (401, 403), (
            f"Expected 401/403 with junk token, got {response.status_code}: "
            f"{response.text}"
        )

    def test_archive_route_registered_in_openapi(self):
        client = TestClient(app)
        spec = client.get("/openapi.json").json()
        path = "/api/v1/companies/{company_id}/archive"
        assert path in spec["paths"], (
            f"Expected {path} to be registered. Got "
            f"{[p for p in spec['paths'] if 'compan' in p][:10]}"
        )
        assert "post" in spec["paths"][path]


class TestUnarchiveEndpointShape:
    """Admin unarchive route exists and demands auth + permission."""

    def test_unarchive_unauthenticated_returns_403(self):
        client = TestClient(app)
        response = client.post(f"/api/v1/companies/{DUMMY_UUID}/unarchive")
        assert response.status_code in (401, 403)

    def test_unarchive_route_registered_in_openapi(self):
        client = TestClient(app)
        spec = client.get("/openapi.json").json()
        path = "/api/v1/companies/{company_id}/unarchive"
        assert path in spec["paths"]
        assert "post" in spec["paths"][path]


class TestHardDeleteGate:
    """DELETE is now admin-permission-gated (was citizen owner-only before)."""

    def test_delete_unauthenticated_returns_403(self):
        client = TestClient(app)
        response = client.delete(f"/api/v1/companies/{DUMMY_UUID}")
        assert response.status_code in (401, 403)

    def test_delete_invalid_token_returns_401_or_403(self):
        client = TestClient(app)
        response = client.delete(
            f"/api/v1/companies/{DUMMY_UUID}",
            headers={"Authorization": "Bearer not-a-real-jwt"},
        )
        assert response.status_code in (401, 403)

    def test_delete_route_still_registered(self):
        client = TestClient(app)
        spec = client.get("/openapi.json").json()
        path = "/api/v1/companies/{company_id}"
        assert path in spec["paths"]
        assert "delete" in spec["paths"][path]
