"""
Route tests for user_documents AGENT PERMISSIONS and MEMORY
endpoints — MOCKED database.

Validates:
- POST /agent/permissions: grant permission (upsert)
- GET /agent/permissions: list active permissions
- DELETE /agent/permissions/{id}: revoke (soft)
- GET /agent/memory: list active memories
- DELETE /agent/memory: reset all memories
- DELETE /agent/memory/{id}: delete specific memory
- Input validation (invalid permission_type, level out of range)
- Auth enforcement

DB is MOCKED — tests set mock_db return values before each API call.
"""

import pytest
from uuid import uuid4
from datetime import datetime

BASE = "/api/v1/user-documents"

TEST_USER_ID_STR = "e709d664-0789-40e0-b5fe-1146fa6660e6"


@pytest.mark.asyncio
class TestAgentPermissionsRoutes:

    # -- AG-01: List permissions (initially empty) ----------------------------

    async def test_list_permissions_initially_empty(self, client, mock_db):
        """AG-01: With no permissions granted, list returns empty."""
        mock_db.fetch.return_value = []

        response = await client.get(f"{BASE}/agent/permissions")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    # -- AG-02: Grant permission -> 201 ---------------------------------------

    async def test_grant_permission(self, client, mock_db):
        """AG-02: Grant a valid permission. Expect 201."""
        perm_id = uuid4()
        now = datetime.utcnow()
        # The route does db.fetchrow (INSERT ... ON CONFLICT ... RETURNING *)
        mock_db.fetchrow.return_value = {
            "id": perm_id,
            "permission_type": "prepare_renewal",
            "scope": None,
            "level": 1,
            "usage_count": 0,
            "last_used_at": None,
            "is_active": True,
            "granted_at": now,
        }

        response = await client.post(
            f"{BASE}/agent/permissions",
            json={"permission_type": "prepare_renewal", "level": 1},
        )
        assert response.status_code == 201, (
            f"Expected 201, got {response.status_code}: {response.text}"
        )
        data = response.json()
        assert data["permission_type"] == "prepare_renewal"
        assert data["level"] == 1
        assert data["is_active"] is True
        assert "id" in data
        assert "granted_at" in data

    # -- AG-03: Invalid permission_type -> 400 --------------------------------

    async def test_invalid_permission_type_rejected(self, client):
        """AG-03: Invalid permission_type returns 400."""
        response = await client.post(
            f"{BASE}/agent/permissions",
            json={"permission_type": "invalid_type", "level": 1},
        )
        assert response.status_code == 400

    # -- AG-04: List after grant shows the permission -------------------------

    async def test_list_after_grant(self, client, mock_db):
        """AG-04: After granting, the permission appears in the list."""
        perm_id = uuid4()
        now = datetime.utcnow()
        mock_db.fetch.return_value = [
            {
                "id": perm_id,
                "permission_type": "proactive_alerts",
                "scope": None,
                "level": 2,
                "usage_count": 0,
                "last_used_at": None,
                "is_active": True,
                "granted_at": now,
            }
        ]

        response = await client.get(f"{BASE}/agent/permissions")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        types = [p["permission_type"] for p in data]
        assert "proactive_alerts" in types

    # -- AG-05: Revoke permission -> is_active=False --------------------------

    async def test_revoke_permission(self, client, mock_db):
        """AG-05: Revoke sets is_active=False."""
        perm_id = uuid4()
        # revoke calls db.execute -> checks "UPDATE 1"
        mock_db.execute.return_value = "UPDATE 1"

        response = await client.delete(f"{BASE}/agent/permissions/{perm_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["is_active"] is False

    # -- AG-06: Revoke nonexistent permission -> 404 --------------------------

    async def test_revoke_nonexistent_returns_404(self, client, mock_db):
        """AG-06: Revoking a non-existent permission returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        mock_db.execute.return_value = "UPDATE 0"

        response = await client.delete(f"{BASE}/agent/permissions/{fake_id}")
        assert response.status_code == 404

    # -- AG-07: Revoked permission no longer in active list -------------------

    async def test_revoked_not_in_list(self, client, mock_db):
        """AG-07: After revoking, permission not in active list."""
        # List returns empty (the revoked one is filtered by is_active=TRUE)
        mock_db.fetch.return_value = []

        response = await client.get(f"{BASE}/agent/permissions")
        data = response.json()
        assert data == []

    # -- AG-08: Upsert (re-grant) updates existing permission -----------------

    async def test_upsert_updates_level(self, client, mock_db):
        """AG-08: Granting the same type again updates the level (upsert)."""
        perm_id = uuid4()
        now = datetime.utcnow()

        # Re-grant with level 2 — upsert returns same ID with updated level
        mock_db.fetchrow.return_value = {
            "id": perm_id,
            "permission_type": "prepare_request",
            "scope": None,
            "level": 2,
            "usage_count": 0,
            "last_used_at": None,
            "is_active": True,
            "granted_at": now,
        }

        response = await client.post(
            f"{BASE}/agent/permissions",
            json={"permission_type": "prepare_request", "level": 2},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["level"] == 2
        assert data["id"] == str(perm_id)

    # -- AG-09: Grant with scope ----------------------------------------------

    async def test_grant_with_scope(self, client, mock_db):
        """AG-09: Grant permission with a workflow scope."""
        perm_id = uuid4()
        now = datetime.utcnow()
        mock_db.fetchrow.return_value = {
            "id": perm_id,
            "permission_type": "prepare_renewal",
            "scope": "PASAPORTE_BIOMETRICO",
            "level": 2,
            "usage_count": 0,
            "last_used_at": None,
            "is_active": True,
            "granted_at": now,
        }

        response = await client.post(
            f"{BASE}/agent/permissions",
            json={
                "permission_type": "prepare_renewal",
                "level": 2,
                "scope": "PASAPORTE_BIOMETRICO",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["scope"] == "PASAPORTE_BIOMETRICO"
        assert data["level"] == 2

    # -- AG-10: Level 0 -> 422 (below minimum) --------------------------------

    async def test_level_below_minimum_rejected(self, client):
        """AG-10: Level 0 is below minimum (1) and should be rejected."""
        response = await client.post(
            f"{BASE}/agent/permissions",
            json={"permission_type": "prepare_renewal", "level": 0},
        )
        assert response.status_code == 422

    # -- AG-11: Level 3 -> 422 (above maximum) --------------------------------

    async def test_level_above_maximum_rejected(self, client):
        """AG-11: Level 3 is above maximum (2) and should be rejected."""
        response = await client.post(
            f"{BASE}/agent/permissions",
            json={"permission_type": "prepare_renewal", "level": 3},
        )
        assert response.status_code == 422

    # -- AG-12: No auth -> 401 ------------------------------------------------

    async def test_no_auth_list_returns_401(self, unauth_client):
        """AG-12: GET /agent/permissions without auth returns 401."""
        response = await unauth_client.get(f"{BASE}/agent/permissions")
        assert response.status_code in (401, 403)

    # -- AG-13: No auth on grant -> 401 ---------------------------------------

    async def test_no_auth_grant_returns_401(self, unauth_client):
        """AG-13: POST /agent/permissions without auth returns 401."""
        response = await unauth_client.post(
            f"{BASE}/agent/permissions",
            json={"permission_type": "prepare_renewal", "level": 1},
        )
        assert response.status_code in (401, 403)


@pytest.mark.asyncio
class TestAgentMemoryRoutes:

    # -- AM-01: Empty memory list ---------------------------------------------

    async def test_empty_memory(self, client, mock_db):
        """AM-01: With no memories, GET returns empty list."""
        mock_db.fetch.return_value = []

        response = await client.get(f"{BASE}/agent/memory")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    # -- AM-02: Memory list with items ----------------------------------------

    async def test_memory_list(self, client, mock_db):
        """AM-02: Memories returned by GET /agent/memory."""
        mem_id = uuid4()
        now = datetime.utcnow()
        mock_db.fetch.return_value = [
            {
                "id": mem_id,
                "memory_type": "preference",
                "content": "User prefers Spanish",
                "content_key": None,
                "confidence": 0.8,
                "confirmation_count": 0,
                "rejection_count": 0,
                "learned_from": "explicit_feedback",
                "is_active": True,
                "last_used_at": None,
                "created_at": now,
                "updated_at": now,
            }
        ]

        response = await client.get(f"{BASE}/agent/memory")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["memory_type"] == "preference"
        assert data[0]["content"] == "User prefers Spanish"

    # -- AM-03: Filter by memory_type -----------------------------------------

    async def test_filter_by_memory_type(self, client, mock_db):
        """AM-03: Filter by memory_type=behavioral."""
        mem_id = uuid4()
        now = datetime.utcnow()
        mock_db.fetch.return_value = [
            {
                "id": mem_id,
                "memory_type": "behavioral",
                "content": "User usually uploads in morning",
                "content_key": None,
                "confidence": 0.7,
                "confirmation_count": 0,
                "rejection_count": 0,
                "learned_from": "pattern_detected",
                "is_active": True,
                "last_used_at": None,
                "created_at": now,
                "updated_at": now,
            }
        ]

        response = await client.get(f"{BASE}/agent/memory?memory_type=behavioral")
        assert response.status_code == 200
        data = response.json()
        for mem in data:
            assert mem["memory_type"] == "behavioral"

    # -- AM-04: Invalid memory_type -> 400 ------------------------------------

    async def test_invalid_memory_type_rejected(self, client):
        """AM-04: Invalid memory_type filter returns 400."""
        response = await client.get(f"{BASE}/agent/memory?memory_type=invalid")
        assert response.status_code == 400

    # -- AM-05: Delete specific memory ----------------------------------------

    async def test_delete_specific_memory(self, client, mock_db):
        """AM-05: DELETE /agent/memory/{id} deactivates the memory."""
        mem_id = uuid4()
        mock_db.execute.return_value = "UPDATE 1"

        response = await client.delete(f"{BASE}/agent/memory/{mem_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["is_active"] is False

    # -- AM-06: Delete nonexistent memory -> 404 ------------------------------

    async def test_delete_nonexistent_memory_returns_404(self, client, mock_db):
        """AM-06: DELETE /agent/memory/{fake_id} returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        mock_db.execute.return_value = "UPDATE 0"

        response = await client.delete(f"{BASE}/agent/memory/{fake_id}")
        assert response.status_code == 404

    # -- AM-07: Reset all memories -> 200 -------------------------------------

    async def test_reset_all_memories(self, client, mock_db):
        """AM-07: DELETE /agent/memory resets all active memories."""
        mock_db.execute.return_value = "UPDATE 3"

        response = await client.delete(f"{BASE}/agent/memory")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["memories_deactivated"] == 3

    # -- AM-08: No auth -> 401 ------------------------------------------------

    async def test_no_auth_memory_returns_401(self, unauth_client):
        """AM-08: GET /agent/memory without auth returns 401."""
        response = await unauth_client.get(f"{BASE}/agent/memory")
        assert response.status_code in (401, 403)

    # -- AM-09: No auth on reset -> 401 ---------------------------------------

    async def test_no_auth_reset_returns_401(self, unauth_client):
        """AM-09: DELETE /agent/memory without auth returns 401."""
        response = await unauth_client.delete(f"{BASE}/agent/memory")
        assert response.status_code in (401, 403)

    # -- AM-10: Memory response schema ----------------------------------------

    async def test_memory_response_schema(self, client, mock_db):
        """AM-10: Memory response includes all expected fields."""
        mem_id = uuid4()
        now = datetime.utcnow()
        mock_db.fetch.return_value = [
            {
                "id": mem_id,
                "memory_type": "context",
                "content": "User has 3 passports",
                "content_key": "passport_count",
                "confidence": 0.8,
                "confirmation_count": 1,
                "rejection_count": 0,
                "learned_from": "conversation_analysis",
                "is_active": True,
                "last_used_at": None,
                "created_at": now,
                "updated_at": now,
            }
        ]

        response = await client.get(f"{BASE}/agent/memory")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        mem = data[0]
        expected_fields = {
            "id", "memory_type", "content", "content_key",
            "confidence", "confirmation_count", "rejection_count",
            "learned_from", "is_active", "created_at", "updated_at",
        }
        assert expected_fields.issubset(mem.keys())
