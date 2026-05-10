"""
Unit tests for the `suggest_appointment_slots` chatbot tool (Phase 7 + 7.1).

The tool is a read-only Level 2 capability: it resolves a workflow to
an entity, picks up to 3 active locations (preferred city first), then
calls `appointment_service.get_available_slots` for each location.

We stub `appointment_service` via sys.modules injection (same approach
as the auto_classify tests in Phase 6) because importing the real module
pulls Vertex AI bindings that aren't available offline. We also patch
`check_rate_limit` so we don't depend on a real Redis instance.
"""
from __future__ import annotations

import sys
import types
from dataclasses import dataclass
from datetime import date, time
from typing import Dict, List, Optional
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest


# ---------------------------------------------------------------------------
# sys.modules injection — must happen BEFORE importing the tool module
# ---------------------------------------------------------------------------

@dataclass
class _FakeAvailableSlot:
    slot_date: date
    slot_time: time
    location_name: str
    location_address: str
    city: str
    slots_remaining: int


class _FakeAppointmentService:
    _entity_code_for_workflow: Optional[str] = "CNEDOGE_PASAPORTE"
    # Mapping entity_location_id (UUID) → list of fake slots
    _queued_slots_per_location: Dict[UUID, List[_FakeAvailableSlot]] = {}
    _raises_on_slots: bool = False

    async def get_entity_code_for_workflow(self, db, workflow_code):
        return self._entity_code_for_workflow

    async def get_available_slots(
        self, db, entity_location_id, from_date=None, limit=6
    ):
        if self._raises_on_slots:
            raise RuntimeError("simulated slot query failure")
        return list(self._queued_slots_per_location.get(entity_location_id, []))


_fake_service = _FakeAppointmentService()

_fake_module = types.ModuleType(
    "app.modules.service_requests.services.appointment_service"
)
_fake_module.appointment_service = _fake_service  # type: ignore[attr-defined]
_fake_module.AppointmentService = _FakeAppointmentService  # type: ignore[attr-defined]
sys.modules[
    "app.modules.service_requests.services.appointment_service"
] = _fake_module

from app.modules.chatbot.services import chatbot_tools_authenticated as tools  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_fake_service():
    _fake_service._entity_code_for_workflow = "CNEDOGE_PASAPORTE"
    _fake_service._queued_slots_per_location = {}
    _fake_service._raises_on_slots = False
    yield


@pytest.fixture(autouse=True)
def _rate_limit_allowed():
    """Patch rate limit to always allow unless a test overrides it."""
    with patch(
        "app.core.cache.check_rate_limit",
        new=AsyncMock(return_value=(True, 99)),
    ):
        yield


def _make_db(
    *,
    perm_allowed: bool = True,
    preferred_city: Optional[str] = None,
    location_rows: Optional[List[dict]] = None,
) -> AsyncMock:
    """Build an AsyncMock conn threaded through the query sequence.

    Query sequence:
    1. check_tool_level → fetchval(EXISTS ...) → perm_allowed
    2. check_tool_level success path → execute(UPDATE usage_count)
    3. SELECT preferred_city → fetchval
    4. db.fetch(<locations query>) → location_rows
    """
    db = AsyncMock()
    db.fetchval = AsyncMock(side_effect=[perm_allowed, preferred_city])
    db.fetch = AsyncMock(return_value=location_rows or [])
    db.execute = AsyncMock()
    return db


class TestRequiredInputs:
    @pytest.mark.asyncio
    async def test_requires_user_id(self):
        db = AsyncMock()
        result = await tools.suggest_appointment_slots(
            db, workflow_code="PASAPORTE_NUEVO"
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_requires_workflow_code(self):
        db = AsyncMock()
        result = await tools.suggest_appointment_slots(db, user_id=str(uuid4()))
        assert "error" in result


class TestRateLimit:
    @pytest.mark.asyncio
    async def test_rate_limit_blocks(self):
        db = AsyncMock()
        with patch(
            "app.core.cache.check_rate_limit",
            new=AsyncMock(return_value=(False, 0)),
        ):
            result = await tools.suggest_appointment_slots(
                db,
                user_id=str(uuid4()),
                workflow_code="PASAPORTE_NUEVO",
            )
        assert result["status"] == "rate_limited"


class TestPermissionAndWorkflow:
    @pytest.mark.asyncio
    async def test_permission_denied(self):
        db = _make_db(perm_allowed=False)
        result = await tools.suggest_appointment_slots(
            db, user_id=str(uuid4()), workflow_code="PASAPORTE_NUEVO"
        )
        assert result["status"] == "permission_required"
        assert result["permission_type"] == "suggest_appointments"
        assert result["level"] == 2

    @pytest.mark.asyncio
    async def test_no_entity_for_workflow(self):
        _fake_service._entity_code_for_workflow = None
        db = _make_db(perm_allowed=True)
        result = await tools.suggest_appointment_slots(
            db, user_id=str(uuid4()), workflow_code="UNKNOWN_WORKFLOW"
        )
        assert result["status"] == "no_appointments"


class TestFromDateValidation:
    @pytest.mark.asyncio
    async def test_invalid_from_date_rejected(self):
        db = _make_db(perm_allowed=True)
        result = await tools.suggest_appointment_slots(
            db,
            user_id=str(uuid4()),
            workflow_code="PASAPORTE_NUEVO",
            from_date="not-a-date",
        )
        assert result["status"] == "error"
        assert "YYYY-MM-DD" in result["message"]

    @pytest.mark.asyncio
    async def test_valid_from_date_propagated(self):
        loc_id = uuid4()
        db = _make_db(
            perm_allowed=True,
            preferred_city="Malabo",
            location_rows=[
                {
                    "id": loc_id,
                    "location_name": "CNEDOGE Malabo",
                    "city": "Malabo",
                    "location_address": "Malabo, Bioko Norte",
                    "is_preferred": True,
                }
            ],
        )
        _fake_service._queued_slots_per_location = {
            loc_id: [
                _FakeAvailableSlot(
                    slot_date=date(2026, 5, 1),
                    slot_time=time(9, 0),
                    location_name="CNEDOGE Malabo",
                    location_address="Malabo",
                    city="Malabo",
                    slots_remaining=3,
                )
            ]
        }
        result = await tools.suggest_appointment_slots(
            db,
            user_id=str(uuid4()),
            workflow_code="PASAPORTE_NUEVO",
            from_date="2026-05-01",
        )
        assert result["status"] == "suggested"
        assert result["from_date"] == "2026-05-01"


class TestLocationSelection:
    @pytest.mark.asyncio
    async def test_no_locations_returns_no_locations(self):
        db = _make_db(
            perm_allowed=True, preferred_city="Malabo", location_rows=[]
        )
        result = await tools.suggest_appointment_slots(
            db, user_id=str(uuid4()), workflow_code="PASAPORTE_NUEVO"
        )
        assert result["status"] == "no_locations"
        assert result["entity_code"] == "CNEDOGE_PASAPORTE"

    @pytest.mark.asyncio
    async def test_preferred_city_bubbles_to_top(self):
        """Even though the SQL query uses DISTINCT ON(el.id), the Python
        post-sort must put is_preferred=TRUE rows ahead of others."""
        loc_malabo = uuid4()
        loc_bata = uuid4()
        # Intentionally give the DB rows in the "wrong" order to prove
        # the post-sort works.
        db = _make_db(
            perm_allowed=True,
            preferred_city="Malabo",
            location_rows=[
                {
                    "id": loc_bata,
                    "location_name": "CNEDOGE Bata",
                    "city": "Bata",
                    "location_address": "Bata, Litoral",
                    "is_preferred": False,
                },
                {
                    "id": loc_malabo,
                    "location_name": "CNEDOGE Malabo",
                    "city": "Malabo",
                    "location_address": "Malabo, Bioko Norte",
                    "is_preferred": True,
                },
            ],
        )
        _fake_service._queued_slots_per_location = {
            loc_malabo: [
                _FakeAvailableSlot(
                    slot_date=date(2026, 4, 20),
                    slot_time=time(9, 0),
                    location_name="CNEDOGE Malabo",
                    location_address="Malabo",
                    city="Malabo",
                    slots_remaining=2,
                )
            ],
            loc_bata: [
                _FakeAvailableSlot(
                    slot_date=date(2026, 4, 22),
                    slot_time=time(10, 30),
                    location_name="CNEDOGE Bata",
                    location_address="Bata",
                    city="Bata",
                    slots_remaining=3,
                )
            ],
        }
        result = await tools.suggest_appointment_slots(
            db, user_id=str(uuid4()), workflow_code="PASAPORTE_NUEVO"
        )
        assert result["status"] == "suggested"
        assert result["total_slots"] == 2
        assert len(result["locations"]) == 2
        # Preferred city must come first
        assert result["locations"][0]["city"] == "Malabo"
        assert result["locations"][0]["is_preferred"] is True
        assert result["locations"][1]["city"] == "Bata"
        assert result["locations"][1]["is_preferred"] is False


class TestEmptySlots:
    @pytest.mark.asyncio
    async def test_all_locations_empty_returns_no_slots(self):
        loc_id = uuid4()
        db = _make_db(
            perm_allowed=True,
            preferred_city="Malabo",
            location_rows=[
                {
                    "id": loc_id,
                    "location_name": "CNEDOGE Malabo",
                    "city": "Malabo",
                    "location_address": "Malabo",
                    "is_preferred": True,
                }
            ],
        )
        _fake_service._queued_slots_per_location = {loc_id: []}
        result = await tools.suggest_appointment_slots(
            db, user_id=str(uuid4()), workflow_code="PASAPORTE_NUEVO"
        )
        assert result["status"] == "no_slots"
        assert "locations" in result

    @pytest.mark.asyncio
    async def test_partial_slot_fetch_failure_degrades_gracefully(self):
        """If one location's slot fetch raises, the tool must still
        return data from the other locations (best-effort aggregation)."""
        loc_malabo = uuid4()
        loc_bata = uuid4()
        db = _make_db(
            perm_allowed=True,
            preferred_city="Malabo",
            location_rows=[
                {
                    "id": loc_malabo,
                    "location_name": "CNEDOGE Malabo",
                    "city": "Malabo",
                    "location_address": "Malabo",
                    "is_preferred": True,
                },
                {
                    "id": loc_bata,
                    "location_name": "CNEDOGE Bata",
                    "city": "Bata",
                    "location_address": "Bata",
                    "is_preferred": False,
                },
            ],
        )
        # Only Malabo returns slots; Bata raises. The tool swallows the
        # per-location exception and returns an empty list for Bata.
        original_get = _fake_service.get_available_slots

        async def patched_get(db, entity_location_id, from_date=None, limit=6):
            if entity_location_id == loc_bata:
                raise RuntimeError("simulated location-specific failure")
            return await original_get(
                db, entity_location_id, from_date=from_date, limit=limit
            )

        _fake_service._queued_slots_per_location = {
            loc_malabo: [
                _FakeAvailableSlot(
                    slot_date=date(2026, 4, 20),
                    slot_time=time(9, 0),
                    location_name="CNEDOGE Malabo",
                    location_address="Malabo",
                    city="Malabo",
                    slots_remaining=2,
                )
            ]
        }
        with patch.object(_fake_service, "get_available_slots", side_effect=patched_get):
            result = await tools.suggest_appointment_slots(
                db, user_id=str(uuid4()), workflow_code="PASAPORTE_NUEVO"
            )
        assert result["status"] == "suggested"
        assert result["total_slots"] == 1
        # Bata location is still listed but with an empty slots array
        assert len(result["locations"]) == 2
        bata_loc = next(loc for loc in result["locations"] if loc["city"] == "Bata")
        assert bata_loc["slots"] == []
