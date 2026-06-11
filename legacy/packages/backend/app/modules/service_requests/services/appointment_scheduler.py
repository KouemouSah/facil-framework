"""
Appointment Scheduler Service.

Automatically calculates and schedules appointments (CITA) for service requests.
Respects hardcoded workflow settings and applies automatic rules only when not defined.
"""
from datetime import date, time, datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
from dataclasses import dataclass
from enum import Enum
import asyncpg

from ..workflows.workflow_interface import PredefinedWorkflow

# All workflows are now v2 (PredefinedWorkflow)
AnyWorkflow = PredefinedWorkflow


class DayOfWeek(int, Enum):
    """Days of week (ISO format: Monday=1, Sunday=7)"""
    MONDAY = 1
    TUESDAY = 2
    WEDNESDAY = 3
    THURSDAY = 4
    FRIDAY = 5
    SATURDAY = 6
    SUNDAY = 7


@dataclass
class TimeSlot:
    """Represents an available time slot"""
    date: date
    start_time: time
    end_time: time
    entity_code: str
    slots_available: int
    is_blocked: bool = False


@dataclass
class AppointmentReservation:
    """Represents a booked appointment"""
    id: UUID
    service_request_id: UUID
    entity_code: str
    appointment_date: date
    appointment_time: time
    appointment_location: Optional[str]
    created_at: datetime
    is_confirmed: bool = False


class AppointmentSchedulerService:
    """
    Service for automatic appointment scheduling.

    Priority order:
    1. Hardcoded workflow settings (appointment_delay_days in workflow class)
    2. Database workflow settings (workflows.appointment_delay_days)
    3. Entity-specific delay rules (appointment_delay_rules table)
    4. Default delay (3 business days)
    """

    DEFAULT_DELAY_DAYS = 3  # Default business days delay
    DEFAULT_SLOT_DURATION_MINUTES = 30
    DEFAULT_SLOTS_PER_HOUR = 2

    async def calculate_appointment_date(
        self,
        db: asyncpg.Connection,
        workflow_code: str,
        validation_date: date,
        entity_code: Optional[str] = None,
        workflow_instance: Optional[AnyWorkflow] = None
    ) -> Tuple[date, time, str]:
        """
        Calculate the next available appointment date and time.

        Args:
            db: Database connection
            workflow_code: The workflow code
            validation_date: Date when dossier was validated
            entity_code: Override entity code (if different from workflow)
            workflow_instance: Optional workflow instance with hardcoded settings

        Returns:
            Tuple of (appointment_date, appointment_time, location)
        """
        # 1. Determine the delay days (priority order)
        delay_days = await self._get_delay_days(
            db=db,
            workflow_code=workflow_code,
            entity_code=entity_code,
            workflow_instance=workflow_instance
        )

        # 2. Get the target entity
        target_entity = await self._get_appointment_entity(
            db=db,
            workflow_code=workflow_code,
            entity_code=entity_code,
            workflow_instance=workflow_instance
        )

        # 3. Calculate minimum date (validation_date + delay_days business days)
        min_date = self._add_business_days(validation_date, delay_days)

        # 4. Find next available slot
        slot = await self._find_next_available_slot(
            db=db,
            entity_code=target_entity,
            from_date=min_date
        )

        if slot:
            return slot.date, slot.start_time, await self._get_entity_location(db, target_entity)

        # Fallback: return min_date at 9:00
        return min_date, time(9, 0), await self._get_entity_location(db, target_entity)

    async def _get_delay_days(
        self,
        db: asyncpg.Connection,
        workflow_code: str,
        entity_code: Optional[str],
        workflow_instance: Optional[AnyWorkflow]
    ) -> int:
        """Get delay days from multiple sources with priority."""

        # Priority 1: Hardcoded workflow settings
        if workflow_instance is not None:
            hardcoded_delay = getattr(workflow_instance, 'appointment_delay_days', None)
            if hardcoded_delay is not None:
                return hardcoded_delay

        # Priority 2: Database workflow settings
        workflow_delay = await db.fetchval("""
            SELECT appointment_delay_days
            FROM workflows
            WHERE code = $1 AND appointment_delay_days IS NOT NULL
        """, workflow_code)

        if workflow_delay is not None:
            return workflow_delay

        # Priority 3: Entity-specific delay rules
        target_entity = entity_code
        if not target_entity:
            target_entity = await db.fetchval("""
                SELECT COALESCE(appointment_entity_code, entity_code)
                FROM workflows
                WHERE code = $1
            """, workflow_code)

        if target_entity:
            entity_delay = await db.fetchval("""
                SELECT default_delay_days
                FROM appointment_delay_rules
                WHERE entity_code = $1 AND is_active = TRUE
            """, target_entity)

            if entity_delay is not None:
                return entity_delay

        # Priority 4: Default
        return self.DEFAULT_DELAY_DAYS

    async def _get_appointment_entity(
        self,
        db: asyncpg.Connection,
        workflow_code: str,
        entity_code: Optional[str],
        workflow_instance: Optional[AnyWorkflow]
    ) -> str:
        """Get the entity responsible for appointments."""

        # Priority 1: Explicit override
        if entity_code:
            return entity_code

        # Priority 2: Hardcoded workflow settings
        if workflow_instance is not None:
            hardcoded_entity = getattr(workflow_instance, 'appointment_entity_code', None)
            if hardcoded_entity:
                return hardcoded_entity

        # Priority 3: Database workflow settings
        entity = await db.fetchval("""
            SELECT COALESCE(appointment_entity_code, entity_code)
            FROM workflows
            WHERE code = $1
        """, workflow_code)

        return entity or 'DEFAULT'

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

    async def _find_next_available_slot(
        self,
        db: asyncpg.Connection,
        entity_code: str,
        from_date: date,
        max_search_days: int = 30
    ) -> Optional[TimeSlot]:
        """Find the next available appointment slot."""

        current_date = from_date
        end_date = from_date + timedelta(days=max_search_days)

        while current_date <= end_date:
            # Skip weekends
            if current_date.weekday() >= 5:
                current_date += timedelta(days=1)
                continue

            # Check if date is blocked
            is_blocked = await self._is_date_blocked(db, entity_code, current_date)
            if is_blocked:
                current_date += timedelta(days=1)
                continue

            # Get slot configuration for this entity and day
            slot_config = await self._get_slot_config(
                db=db,
                entity_code=entity_code,
                day_of_week=current_date.isoweekday()
            )

            if not slot_config or not slot_config.get('is_available', True):
                current_date += timedelta(days=1)
                continue

            # Get available time slots for this date
            available_slot = await self._get_first_available_time_slot(
                db=db,
                entity_code=entity_code,
                target_date=current_date,
                slot_config=slot_config
            )

            if available_slot:
                return available_slot

            current_date += timedelta(days=1)

        return None

    async def _is_date_blocked(
        self,
        db: asyncpg.Connection,
        entity_code: str,
        target_date: date
    ) -> bool:
        """Check if a date is blocked for appointments."""

        # Check entity-specific blocks
        entity_blocked = await db.fetchval("""
            SELECT 1 FROM appointment_blocked_dates
            WHERE entity_code = $1
            AND blocked_date = $2
        """, entity_code, target_date)

        if entity_blocked:
            return True

        # Check global blocks (entity_code = 'ALL')
        global_blocked = await db.fetchval("""
            SELECT 1 FROM appointment_blocked_dates
            WHERE entity_code = 'ALL'
            AND blocked_date = $1
        """, target_date)

        return bool(global_blocked)

    async def _get_slot_config(
        self,
        db: asyncpg.Connection,
        entity_code: str,
        day_of_week: int
    ) -> Optional[Dict[str, Any]]:
        """Get slot configuration for entity and day of week."""

        row = await db.fetchrow("""
            SELECT
                start_time,
                end_time,
                slot_duration_minutes,
                max_slots_per_hour,
                is_available
            FROM appointment_slot_configs
            WHERE entity_code = $1
            AND day_of_week = $2
            AND is_active = TRUE
        """, entity_code, day_of_week)

        if row:
            return dict(row)

        # Return default config if no specific config exists
        return {
            'start_time': time(8, 0),
            'end_time': time(16, 0),
            'slot_duration_minutes': self.DEFAULT_SLOT_DURATION_MINUTES,
            'max_slots_per_hour': self.DEFAULT_SLOTS_PER_HOUR,
            'is_available': True
        }

    async def _get_first_available_time_slot(
        self,
        db: asyncpg.Connection,
        entity_code: str,
        target_date: date,
        slot_config: Dict[str, Any]
    ) -> Optional[TimeSlot]:
        """Find the first available time slot for a date."""

        start_time = slot_config.get('start_time', time(8, 0))
        end_time = slot_config.get('end_time', time(16, 0))
        slot_duration = slot_config.get('slot_duration_minutes', self.DEFAULT_SLOT_DURATION_MINUTES)
        max_slots = slot_config.get('max_slots_per_hour', self.DEFAULT_SLOTS_PER_HOUR)

        current_time = start_time

        while current_time < end_time:
            # Count existing reservations for this slot
            # Migration 030: appointment_reservations uses entity_location_id FK, not entity_code
            reservation_count = await db.fetchval("""
                SELECT COUNT(*)
                FROM appointment_reservations ar
                JOIN entity_locations el ON ar.entity_location_id = el.id
                WHERE el.entity_code = $1
                AND ar.appointment_date = $2
                AND ar.appointment_time = $3
                AND ar.status != 'cancelled'
            """, entity_code, target_date, current_time)

            slots_available = max_slots - (reservation_count or 0)

            if slots_available > 0:
                slot_end = self._add_minutes(current_time, slot_duration)
                return TimeSlot(
                    date=target_date,
                    start_time=current_time,
                    end_time=slot_end,
                    entity_code=entity_code,
                    slots_available=slots_available
                )

            # Move to next slot
            current_time = self._add_minutes(current_time, slot_duration)

        return None

    def _add_minutes(self, t: time, minutes: int) -> time:
        """Add minutes to a time object."""
        dt = datetime.combine(date.today(), t)
        dt += timedelta(minutes=minutes)
        return dt.time()

    async def _get_entity_location(
        self,
        db: asyncpg.Connection,
        entity_code: str
    ) -> str:
        """Get the physical location for an entity."""

        location = await db.fetchval("""
            SELECT location_address
            FROM entities
            WHERE code = $1
        """, entity_code)

        if location:
            return location

        # Default locations by entity
        default_locations = {
            'CNEDOGE': 'CNEDOGE - Malabo, Calle de la República',
            'DGT': 'Dirección General de Tráfico - Malabo',
            'EXTRANJERIA': 'Comisaría de Extranjería - Malabo',
            'MINFP': 'Ministerio de Función Pública - Malabo',
            'ONRC': 'Oficina Nacional de Registro Civil - Malabo'
        }

        return default_locations.get(entity_code, f'Oficina {entity_code} - Malabo')

    async def reserve_appointment(
        self,
        db: asyncpg.Connection,
        service_request_id: UUID,
        workflow_code: str,
        validation_date: date,
        workflow_instance: Optional[AnyWorkflow] = None
    ) -> AppointmentReservation:
        """
        Reserve an appointment slot for a service request.

        This should be called after agent validation (DOSSIER_VALIDE status).
        """

        # Get entity code
        entity_code = await self._get_appointment_entity(
            db=db,
            workflow_code=workflow_code,
            entity_code=None,
            workflow_instance=workflow_instance
        )

        # Get default entity_location_id for this entity (main office)
        # Migration 030: appointment_reservations uses entity_location_id FK
        entity_location = await db.fetchrow("""
            SELECT id, location_name, location_address
            FROM entity_locations
            WHERE entity_code = $1
            AND is_active = TRUE
            ORDER BY is_main_office DESC, created_at ASC
            LIMIT 1
        """, entity_code)

        entity_location_id = entity_location['id'] if entity_location else None
        location = entity_location['location_name'] if entity_location else await self._get_entity_location(db, entity_code)

        # Calculate optimal date/time
        appointment_date, appointment_time, _ = await self.calculate_appointment_date(
            db=db,
            workflow_code=workflow_code,
            validation_date=validation_date,
            workflow_instance=workflow_instance
        )

        # Create reservation
        # Migration 030: Uses entity_location_id FK instead of entity_code/location columns
        row = await db.fetchrow("""
            INSERT INTO appointment_reservations (
                service_request_id,
                entity_location_id,
                appointment_date,
                appointment_time,
                status
            ) VALUES ($1, $2, $3, $4, 'scheduled')
            RETURNING id, service_request_id, entity_location_id, appointment_date,
                      appointment_time, created_at,
                      (status = 'confirmed') as is_confirmed
        """, service_request_id, entity_location_id, appointment_date, appointment_time)

        # Update service_request with appointment info
        await db.execute("""
            UPDATE service_requests
            SET cita_date = $1,
                cita_time = $2,
                cita_location = $3,
                entity_location_id = $4,
                updated_at = NOW()
            WHERE id = $5
        """, appointment_date, appointment_time, location, entity_location_id, service_request_id)

        return AppointmentReservation(
            id=row['id'],
            service_request_id=row['service_request_id'],
            entity_code=entity_code,
            appointment_date=row['appointment_date'],
            appointment_time=row['appointment_time'],
            appointment_location=location,
            created_at=row['created_at'],
            is_confirmed=row['is_confirmed']
        )

    async def get_available_slots(
        self,
        db: asyncpg.Connection,
        entity_code: str,
        from_date: date,
        to_date: Optional[date] = None,
        limit: int = 10
    ) -> List[TimeSlot]:
        """Get list of available appointment slots for an entity."""

        if not to_date:
            to_date = from_date + timedelta(days=30)

        slots = []
        current_date = from_date

        while current_date <= to_date and len(slots) < limit:
            # Skip weekends
            if current_date.weekday() >= 5:
                current_date += timedelta(days=1)
                continue

            # Check if blocked
            if await self._is_date_blocked(db, entity_code, current_date):
                current_date += timedelta(days=1)
                continue

            # Get config
            slot_config = await self._get_slot_config(
                db=db,
                entity_code=entity_code,
                day_of_week=current_date.isoweekday()
            )

            if not slot_config or not slot_config.get('is_available', True):
                current_date += timedelta(days=1)
                continue

            # Get all available slots for this day
            day_slots = await self._get_all_available_time_slots(
                db=db,
                entity_code=entity_code,
                target_date=current_date,
                slot_config=slot_config
            )

            slots.extend(day_slots)
            current_date += timedelta(days=1)

        return slots[:limit]

    async def _get_all_available_time_slots(
        self,
        db: asyncpg.Connection,
        entity_code: str,
        target_date: date,
        slot_config: Dict[str, Any]
    ) -> List[TimeSlot]:
        """Get all available time slots for a date."""

        start_time = slot_config.get('start_time', time(8, 0))
        end_time = slot_config.get('end_time', time(16, 0))
        slot_duration = slot_config.get('slot_duration_minutes', self.DEFAULT_SLOT_DURATION_MINUTES)
        max_slots = slot_config.get('max_slots_per_hour', self.DEFAULT_SLOTS_PER_HOUR)

        slots = []
        current_time = start_time

        while current_time < end_time:
            # Migration 030: appointment_reservations uses entity_location_id FK, not entity_code
            reservation_count = await db.fetchval("""
                SELECT COUNT(*)
                FROM appointment_reservations ar
                JOIN entity_locations el ON ar.entity_location_id = el.id
                WHERE el.entity_code = $1
                AND ar.appointment_date = $2
                AND ar.appointment_time = $3
                AND ar.status != 'cancelled'
            """, entity_code, target_date, current_time)

            slots_available = max_slots - (reservation_count or 0)

            if slots_available > 0:
                slot_end = self._add_minutes(current_time, slot_duration)
                slots.append(TimeSlot(
                    date=target_date,
                    start_time=current_time,
                    end_time=slot_end,
                    entity_code=entity_code,
                    slots_available=slots_available
                ))

            current_time = self._add_minutes(current_time, slot_duration)

        return slots

    async def cancel_appointment(
        self,
        db: asyncpg.Connection,
        service_request_id: UUID,
        reason: Optional[str] = None
    ) -> bool:
        """Cancel an existing appointment reservation."""

        result = await db.execute("""
            UPDATE appointment_reservations
            SET status = 'cancelled',
                cancellation_reason = $2,
                cancelled_at = NOW()
            WHERE service_request_id = $1
            AND status != 'cancelled'
        """, service_request_id, reason)

        # Clear service_request cita fields
        await db.execute("""
            UPDATE service_requests
            SET cita_date = NULL,
                cita_time = NULL,
                cita_location = NULL,
                updated_at = NOW()
            WHERE id = $1
        """, service_request_id)

        return 'UPDATE 1' in result

    async def reschedule_appointment(
        self,
        db: asyncpg.Connection,
        service_request_id: UUID,
        new_date: date,
        new_time: time,
        reason: Optional[str] = None
    ) -> AppointmentReservation:
        """Reschedule an existing appointment to a new date/time."""

        # Get current reservation with entity location details
        # Migration 030: appointment_reservations uses entity_location_id FK
        current = await db.fetchrow("""
            SELECT ar.entity_location_id, el.entity_code, el.location_name
            FROM appointment_reservations ar
            LEFT JOIN entity_locations el ON ar.entity_location_id = el.id
            WHERE ar.service_request_id = $1
            AND ar.status != 'cancelled'
            ORDER BY ar.created_at DESC
            LIMIT 1
        """, service_request_id)

        if not current:
            raise ValueError(f"No active appointment found for service request {service_request_id}")

        # Cancel old reservation
        await self.cancel_appointment(db, service_request_id, f"Rescheduled: {reason or 'User request'}")

        # Create new reservation
        # Migration 030: Uses entity_location_id FK instead of entity_code/location columns
        row = await db.fetchrow("""
            INSERT INTO appointment_reservations (
                service_request_id,
                entity_location_id,
                appointment_date,
                appointment_time,
                status
            ) VALUES ($1, $2, $3, $4, 'scheduled')
            RETURNING id, service_request_id, entity_location_id, appointment_date,
                      appointment_time, created_at,
                      (status = 'confirmed') as is_confirmed
        """, service_request_id, current['entity_location_id'], new_date, new_time)

        # Update service_request
        await db.execute("""
            UPDATE service_requests
            SET cita_date = $1,
                cita_time = $2,
                updated_at = NOW()
            WHERE id = $3
        """, new_date, new_time, service_request_id)

        return AppointmentReservation(
            id=row['id'],
            service_request_id=row['service_request_id'],
            entity_code=current['entity_code'],
            appointment_date=row['appointment_date'],
            appointment_time=row['appointment_time'],
            appointment_location=current['location_name'],
            created_at=row['created_at'],
            is_confirmed=row['is_confirmed']
        )


# Singleton instance
appointment_scheduler = AppointmentSchedulerService()
