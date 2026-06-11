"""
Appointment Service for Citizen-First Flow.

This service handles the NEW workflow where citizens:
1. Select a location (Malabo or Bata) BEFORE payment
2. Select from available appointment slots BEFORE payment
3. Slot is temporarily held during payment (15 min)
4. Hold is confirmed after payment success
5. Fallback: submit without appointment if no slots available

Different from AppointmentSchedulerService which handles automatic scheduling
by agents AFTER validation.

Flow:
    DRAFT → DOCUMENTS → REVIEW → SELECT_LOCATION → SELECT_SLOT → PAYMENT → SUBMITTED
"""
from datetime import date, time, datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
from dataclasses import dataclass, field
from enum import Enum
import asyncpg
import json
import logging

from app.core.jsonb import ensure_list

logger = logging.getLogger(__name__)


class HoldStatus(str, Enum):
    """Appointment hold status"""
    HELD = "held"
    CONFIRMED = "confirmed"
    EXPIRED = "expired"
    RELEASED = "released"
    FALLBACK = "fallback"


@dataclass
class EntityLocation:
    """Represents a physical location for an entity (from entity_locations table)"""
    id: Optional[UUID] = None
    entity_code: str = ""
    location_name: str = ""
    location_address: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None


@dataclass
class AvailableSlot:
    """Represents an available appointment slot"""
    slot_date: date
    slot_time: time
    location_name: str
    location_address: Optional[str] = None
    slots_remaining: int = 1
    city: Optional[str] = None
    slot_config_id: Optional[UUID] = None
    entity_location_id: Optional[UUID] = None


@dataclass
class AppointmentHold:
    """
    Represents a temporary appointment hold (before payment).

    Migration 030: location_name/location_address/city removed from appointment_holds.
    Now uses entity_location_id FK to entity_locations table.
    """
    id: UUID
    service_request_id: UUID
    slot_config_id: Optional[UUID]
    entity_location_id: Optional[UUID]
    appointment_date: Optional[date]
    appointment_time: Optional[time]
    expires_at: datetime
    status: HoldStatus
    created_at: datetime
    # Resolved from entity_locations table via JOIN
    location_name: Optional[str] = None
    location_address: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    entity_code: Optional[str] = None
    confirmed_at: Optional[datetime] = None
    released_at: Optional[datetime] = None


@dataclass
class HoldResult:
    """Result of a hold operation"""
    success: bool
    hold: Optional[AppointmentHold] = None
    error: Optional[str] = None
    expires_in_seconds: int = 0


@dataclass
class ConfirmResult:
    """Result of confirming a hold after payment"""
    success: bool
    appointment_date: Optional[date] = None
    appointment_time: Optional[time] = None
    location_name: Optional[str] = None
    city: Optional[str] = None
    error: Optional[str] = None


class AppointmentService:
    """
    Service for citizen-first appointment selection.

    Key Methods:
    - get_available_locations(): Get Malabo/Bata options for an entity
    - get_available_slots(): Get 6 available slots for a location
    - hold_slot(): Create temporary hold (15 min) before payment
    - confirm_hold(): Called by payment webhook after success
    - submit_without_appointment(): Fallback when no slots available
    - release_hold(): Release a hold (user changed selection)
    - release_expired_holds(): Cron job to clean up expired holds
    """

    DEFAULT_HOLD_MINUTES = 15
    DEFAULT_SLOTS_LIMIT = 6
    DEFAULT_DELAY_DAYS = 7

    # === PUBLIC METHODS ===

    async def get_available_locations(
        self,
        db: asyncpg.Connection,
        entity_code: str
    ) -> List[EntityLocation]:
        """
        Get available locations for an entity (e.g., Malabo and Bata).

        Args:
            db: Database connection
            entity_code: Entity code (e.g., 'CNEDOGE', 'DGT')

        Returns:
            List of EntityLocation objects with city and region
        """
        # Migration 030: Get locations from entity_locations via FK
        rows = await db.fetch("""
            SELECT DISTINCT ON (el.city, el.location_name)
                el.entity_code,
                el.location_name,
                el.location_address,
                el.city,
                el.region
            FROM entity_locations el
            INNER JOIN appointment_slot_configs asc ON asc.entity_location_id = el.id
            WHERE el.entity_code = $1
            AND el.is_active = TRUE
            AND asc.is_active = TRUE
            ORDER BY el.city, el.location_name
        """, entity_code)

        return [
            EntityLocation(
                entity_code=row['entity_code'],
                location_name=row['location_name'],
                location_address=row['location_address'],
                city=row['city'],
                region=row['region']
            )
            for row in rows
        ]

    async def get_available_slots(
        self,
        db: asyncpg.Connection,
        entity_location_id: UUID,
        from_date: Optional[date] = None,
        limit: int = DEFAULT_SLOTS_LIMIT
    ) -> List[AvailableSlot]:
        """
        Get available appointment slots for a specific location.

        Uses get_available_slots_v3() set-based PostgreSQL function which:
        - Accepts entity_location_id UUID directly (no string resolution)
        - Uses generate_series + LATERAL JOINs (1 query instead of 60 loop iterations)
        - Returns city for display

        Args:
            db: Database connection
            entity_location_id: UUID FK to entity_locations table
            from_date: Start date (defaults to minimum delay date)
            limit: Max slots to return (default 6)

        Returns:
            List of AvailableSlot objects
        """
        # Calculate minimum date based on delay rules
        if from_date is None:
            # Resolve entity_code for delay rules lookup
            entity_code = await db.fetchval("""
                SELECT entity_code FROM entity_locations WHERE id = $1
            """, entity_location_id)
            if entity_code:
                delay_days = await self._get_delay_days(db, entity_code)
            else:
                delay_days = self.DEFAULT_DELAY_DAYS
            from_date = self._add_business_days(date.today(), delay_days)

        # Set-based v3 function: 1 query with generate_series + LATERAL
        rows = await db.fetch("""
            SELECT
                slot_date,
                slot_time,
                location_name,
                location_address,
                city,
                slots_remaining
            FROM get_available_slots_v3($1, $2, $3)
        """, entity_location_id, from_date, limit)

        return [
            AvailableSlot(
                slot_date=row['slot_date'],
                slot_time=row['slot_time'],
                location_name=row['location_name'],
                location_address=row['location_address'],
                slots_remaining=row['slots_remaining'],
                city=row['city']
            )
            for row in rows
        ]

    async def hold_slot(
        self,
        db: asyncpg.Connection,
        service_request_id: UUID,
        entity_location_id: UUID,
        appointment_date: date,
        appointment_time: time,
        slot_config_id: Optional[UUID] = None
    ) -> HoldResult:
        """
        Create a temporary hold on an appointment slot.

        Called when user selects a slot (BEFORE payment).
        Hold expires after 15 minutes if payment not completed.
        Releases any previous hold for this request.

        Migration 030: Uses entity_location_id FK instead of location_name/address.

        Args:
            db: Database connection
            service_request_id: Service request UUID
            entity_location_id: FK to entity_locations table
            appointment_date: Selected date
            appointment_time: Selected time
            slot_config_id: Optional slot config ID (resolved if not provided)

        Returns:
            HoldResult with success status and hold details
        """
        try:
            # If slot_config_id not provided, find matching slot config
            if not slot_config_id:
                day_of_week = appointment_date.weekday()  # 0=Monday, 6=Sunday
                slot_config = await db.fetchrow("""
                    SELECT id FROM appointment_slot_configs
                    WHERE entity_location_id = $1
                    AND day_of_week = $2
                    AND start_time <= $3::time
                    AND end_time > $3::time
                    AND is_active = TRUE
                """, entity_location_id, day_of_week, appointment_time)
                slot_config_id = slot_config['id'] if slot_config else None

            # Call the PostgreSQL function (migration 030 signature)
            row = await db.fetchrow("""
                SELECT * FROM hold_appointment_slot(
                    $1, $2, $3, $4, $5
                )
            """,
                service_request_id,
                slot_config_id,
                appointment_date,
                appointment_time,
                entity_location_id
            )

            if row and row['success']:
                # Get location details for response
                location = await db.fetchrow("""
                    SELECT entity_code, location_name, location_address, city, region
                    FROM entity_locations WHERE id = $1
                """, entity_location_id)

                hold = AppointmentHold(
                    id=row['hold_id'],
                    service_request_id=service_request_id,
                    slot_config_id=slot_config_id,
                    entity_location_id=entity_location_id,
                    appointment_date=appointment_date,
                    appointment_time=appointment_time,
                    expires_at=row['expires_at'],
                    status=HoldStatus.HELD,
                    created_at=datetime.now(timezone.utc),
                    # Resolved from entity_locations
                    location_name=location['location_name'] if location else None,
                    location_address=location['location_address'] if location else None,
                    city=location['city'] if location else None,
                    region=location['region'] if location else None,
                    entity_code=location['entity_code'] if location else None,
                )

                # Calculate seconds until expiry
                now = datetime.now(hold.expires_at.tzinfo) if hold.expires_at.tzinfo else datetime.now(timezone.utc)
                expires_in = (hold.expires_at - now).total_seconds()

                logger.info(
                    f"Appointment slot held: request={service_request_id}, "
                    f"date={appointment_date}, time={appointment_time}, "
                    f"location_id={entity_location_id}, expires_in={expires_in}s"
                )

                return HoldResult(
                    success=True,
                    hold=hold,
                    expires_in_seconds=max(0, int(expires_in))
                )
            else:
                error_msg = row['error_message'] if row else "Failed to create appointment hold"
                return HoldResult(
                    success=False,
                    error=error_msg
                )

        except Exception as e:
            logger.error(f"Error holding slot: {e}")
            return HoldResult(
                success=False,
                error=str(e)
            )

    async def confirm_hold(
        self,
        db: asyncpg.Connection,
        service_request_id: UUID
    ) -> ConfirmResult:
        """
        Confirm a held appointment after payment success.

        Called by payment webhook after successful payment.
        Creates permanent reservation and updates service_request.

        Migration 030: Function now returns table with location_id instead of location_name.

        Args:
            db: Database connection
            service_request_id: Service request UUID

        Returns:
            ConfirmResult with success status and appointment details
        """
        try:
            # Use the PostgreSQL function (migration 030 returns table)
            result = await db.fetchrow("""
                SELECT * FROM confirm_appointment_hold($1)
            """, service_request_id)

            if result and result['success']:
                # Get location details from entity_locations via FK
                location_id = result['location_id']
                location = await db.fetchrow("""
                    SELECT location_name, city, region
                    FROM entity_locations WHERE id = $1
                """, location_id)

                location_name = location['location_name'] if location else None
                city = location['city'] if location else None

                # Also update cita_location for legacy compatibility
                if location_name:
                    await db.execute("""
                        UPDATE service_requests
                        SET cita_location = $2
                        WHERE id = $1
                    """, service_request_id, location_name)

                logger.info(
                    f"Appointment confirmed: request={service_request_id}, "
                    f"date={result['appointment_date']}, time={result['appointment_time']}, "
                    f"location={location_name}, city={city}"
                )

                return ConfirmResult(
                    success=True,
                    appointment_date=result['appointment_date'],
                    appointment_time=result['appointment_time'],
                    location_name=location_name,
                    city=city
                )
            else:
                error_msg = result['error_message'] if result else None

                # Check if hold expired
                if not error_msg:
                    hold = await db.fetchrow("""
                        SELECT status, expires_at
                        FROM appointment_holds
                        WHERE service_request_id = $1
                        ORDER BY created_at DESC
                        LIMIT 1
                    """, service_request_id)

                    if hold and hold['status'] == 'expired':
                        error_msg = "Appointment hold expired. Please select a new slot."
                    elif not hold:
                        error_msg = "No appointment hold found for this request."
                    else:
                        error_msg = f"Hold status is '{hold['status']}', cannot confirm."

                return ConfirmResult(
                    success=False,
                    error=error_msg
                )

        except Exception as e:
            logger.error(f"Error confirming hold: {e}")
            return ConfirmResult(
                success=False,
                error=str(e)
            )

    async def submit_without_appointment(
        self,
        db: asyncpg.Connection,
        service_request_id: UUID,
        entity_location_id: UUID
    ) -> ConfirmResult:
        """
        Submit a request without an appointment (fallback).

        Called when no slots are available.
        Agent will assign appointment later.

        Migration 030: Now uses entity_location_id instead of location_name.

        Args:
            db: Database connection
            service_request_id: Service request UUID
            entity_location_id: FK to entity_locations table

        Returns:
            ConfirmResult with success status
        """
        try:
            # Call the PostgreSQL function (migration 030 returns table)
            result = await db.fetchrow("""
                SELECT * FROM submit_without_appointment($1, $2)
            """, service_request_id, entity_location_id)

            if result and result['success']:
                # Get location details from entity_locations
                location = await db.fetchrow("""
                    SELECT location_name, city, region
                    FROM entity_locations WHERE id = $1
                """, entity_location_id)

                location_name = location['location_name'] if location else None
                city = location['city'] if location else None

                logger.info(
                    f"Request submitted without appointment: request={service_request_id}, "
                    f"location_id={entity_location_id}, location={location_name}"
                )

                return ConfirmResult(
                    success=True,
                    location_name=location_name,
                    city=city,
                    error=None
                )
            else:
                error_msg = result['error_message'] if result else "Failed to submit request without appointment"
                return ConfirmResult(
                    success=False,
                    error=error_msg
                )

        except Exception as e:
            logger.error(f"Error submitting without appointment: {e}")
            return ConfirmResult(
                success=False,
                error=str(e)
            )

    async def release_hold(
        self,
        db: asyncpg.Connection,
        service_request_id: UUID
    ) -> bool:
        """
        Release a held appointment slot.

        Called when user wants to select a different slot.

        Args:
            db: Database connection
            service_request_id: Service request UUID

        Returns:
            True if hold was released
        """
        result = await db.execute("""
            UPDATE appointment_holds
            SET status = 'released',
                released_at = NOW()
            WHERE service_request_id = $1
            AND status = 'held'
        """, service_request_id)

        return 'UPDATE 1' in result

    async def release_expired_holds(
        self,
        db: asyncpg.Connection
    ) -> Tuple[int, List[UUID]]:
        """
        Release all expired holds.

        Should be called by a cron job every minute.

        Args:
            db: Database connection

        Returns:
            Tuple of (released_count, list of service_request_ids)
        """
        row = await db.fetchrow("""
            SELECT released_count, service_request_ids
            FROM release_expired_appointment_holds()
        """)

        released_count = row['released_count'] or 0
        request_ids = ensure_list(row['service_request_ids'])

        if released_count > 0:
            logger.info(f"Released {released_count} expired appointment holds")

        return released_count, request_ids

    async def get_hold_status(
        self,
        db: asyncpg.Connection,
        service_request_id: UUID
    ) -> Optional[AppointmentHold]:
        """
        Get the current hold status for a service request.

        Migration 030: JOINs entity_locations to get location details.

        Args:
            db: Database connection
            service_request_id: Service request UUID

        Returns:
            AppointmentHold if exists, None otherwise
        """
        row = await db.fetchrow("""
            SELECT
                ah.id,
                ah.service_request_id,
                ah.slot_config_id,
                ah.entity_location_id,
                ah.appointment_date,
                ah.appointment_time,
                ah.expires_at,
                ah.status,
                ah.created_at,
                ah.confirmed_at,
                ah.released_at,
                -- Resolved from entity_locations
                el.entity_code,
                el.location_name,
                el.location_address,
                el.city,
                el.region
            FROM appointment_holds ah
            LEFT JOIN entity_locations el ON ah.entity_location_id = el.id
            WHERE ah.service_request_id = $1
            ORDER BY ah.created_at DESC
            LIMIT 1
        """, service_request_id)

        if row:
            return AppointmentHold(
                id=row['id'],
                service_request_id=row['service_request_id'],
                slot_config_id=row['slot_config_id'],
                entity_location_id=row['entity_location_id'],
                appointment_date=row['appointment_date'],
                appointment_time=row['appointment_time'],
                expires_at=row['expires_at'],
                status=HoldStatus(row['status']),
                created_at=row['created_at'],
                confirmed_at=row['confirmed_at'],
                released_at=row['released_at'],
                # Resolved from entity_locations
                entity_code=row['entity_code'],
                location_name=row['location_name'],
                location_address=row['location_address'],
                city=row['city'],
                region=row['region'],
            )

        return None

    async def get_entity_code_for_workflow(
        self,
        db: asyncpg.Connection,
        workflow_code: str
    ) -> Optional[str]:
        """
        Get the appointment entity code for a workflow.

        Resolution order (most specific first):
        1. workflows.appointment_entity_code (explicit override)
        2. Dynamic: entities.workflow_codes JSONB → entity that declares this
           workflow AND has active entity_locations with appointment_slot_configs
        3. workflows.entity_code (general entity for the workflow)

        Args:
            db: Database connection
            workflow_code: Workflow code

        Returns:
            Entity code (e.g., 'CNEDOGE_PASAPORTE', 'DGT') or None
        """
        # Priority 1: Explicit appointment_entity_code override
        appt_entity = await db.fetchval("""
            SELECT appointment_entity_code
            FROM workflows
            WHERE code = $1 AND appointment_entity_code IS NOT NULL
        """, workflow_code)
        if appt_entity:
            return appt_entity

        # Priority 2: Dynamic — find the entity that declares this workflow
        # in its workflow_codes JSONB AND has locations with active slot configs
        dynamic_entity = await db.fetchval("""
            SELECT e.code
            FROM entities e
            INNER JOIN entity_locations el ON el.entity_code = e.code
            INNER JOIN appointment_slot_configs sc
                ON sc.entity_location_id = el.id
            WHERE e.workflow_codes @> $1::jsonb
              AND e.is_active = TRUE
              AND el.is_active = TRUE
              AND sc.is_active = TRUE
            ORDER BY e.code
            LIMIT 1
        """, json.dumps([workflow_code]))
        if dynamic_entity:
            logger.info(
                f"Resolved appointment entity for {workflow_code} "
                f"via entities.workflow_codes: {dynamic_entity}"
            )
            return dynamic_entity

        # Priority 3: Fallback to workflows.entity_code
        entity = await db.fetchval("""
            SELECT entity_code FROM workflows WHERE code = $1
        """, workflow_code)
        if entity:
            logger.info(
                f"Resolved appointment entity for {workflow_code} "
                f"via workflows.entity_code fallback: {entity}"
            )
            return entity

        logger.warning(
            f"No entity_code mapping found for workflow: {workflow_code}"
        )
        return None

    # === PRIVATE METHODS ===

    async def _get_delay_days(
        self,
        db: asyncpg.Connection,
        entity_code: str,
        workflow_code: Optional[str] = None,
        priority: str = 'NORMAL'
    ) -> int:
        """
        Get the delay days for appointment scheduling.

        3-level cascade (most specific wins):
        P1: workflow_code specific
        P2: entity_code specific (workflow_code IS NULL)
        P3: global default (both NULL)
        """

        # Priority 1: Workflow-specific rule
        if workflow_code:
            delay = await db.fetchval("""
                SELECT delay_business_days
                FROM appointment_delay_rules
                WHERE workflow_code = $1
                AND priority = $2
                AND is_active = TRUE
            """, workflow_code, priority)

            if delay is not None:
                return delay

        # Priority 2: Entity-specific rule
        if entity_code:
            delay = await db.fetchval("""
                SELECT delay_business_days
                FROM appointment_delay_rules
                WHERE entity_code = $1
                AND workflow_code IS NULL
                AND priority = $2
                AND is_active = TRUE
            """, entity_code, priority)

            if delay is not None:
                return delay

        # Priority 3: Global default (entity_code IS NULL, workflow_code IS NULL)
        delay = await db.fetchval("""
            SELECT delay_business_days
            FROM appointment_delay_rules
            WHERE entity_code IS NULL
            AND workflow_code IS NULL
            AND priority = $1
            AND is_active = TRUE
        """, priority)

        return delay or self.DEFAULT_DELAY_DAYS

    def _add_business_days(self, start_date: date, days: int) -> date:
        """Add business days to a date (excluding weekends)."""
        current = start_date
        added = 0

        while added < days:
            current += timedelta(days=1)
            # Skip weekends (Saturday=5, Sunday=6 in Python's weekday())
            if current.weekday() < 5:
                added += 1

        return current


# Singleton instance
appointment_service = AppointmentService()
