"""
Appointment Routes for Citizen-First Flow.

This router handles the NEW workflow where citizens:
1. Complete documents and form review
2. Pay for the service (PAYMENT_PENDING → PAID)
3. Select appointment location and slot AFTER payment
4. Slot is temporarily held during confirmation (15 min)
5. Hold is confirmed automatically
6. Fallback: submit without appointment if no slots available

Flow: DRAFT → DOCUMENTS → REVIEW → PAYMENT_PENDING → PAID → APPOINTMENT → SUBMITTED

Status Validation:
- Appointment selection is ONLY available after payment is initiated
- Allowed statuses: PAYMENT_PENDING, PAID, SUBMITTED, UNDER_REVIEW, APPROVED
- This prevents users from reserving slots before paying
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional, List
from datetime import date, datetime, timedelta
from uuid import UUID
import asyncpg
import logging

from app.database.connection import get_database
from app.modules.auth.middleware.auth_middleware import get_current_user
from app.modules.users.models.user import UserResponse

from ..models.appointments import (
    EntityLocationResponse,
    AvailableSlotResponse,
    AvailableDayResponse,
    AvailableDaysListResponse,
    HoldSlotRequest,
    HoldSlotResponse,
    ConfirmHoldResponse,
    AppointmentHoldStatus,
    SubmitWithoutAppointmentRequest,
    SubmitWithoutAppointmentResponse,
    ReleaseHoldResponse,
    AppointmentLocationsListResponse,
    AppointmentSlotsListResponse,
)
from ..services.appointment_service import appointment_service
from app.core.events import EventBus, EventType

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/service-requests",
    tags=["Service Requests - Appointments"]
)


# =============================================================================
# STATUS VALIDATION HELPER
# =============================================================================

# Statuses that allow appointment selection (after payment is initiated)
APPOINTMENT_ALLOWED_STATUSES: List[str] = [
    'PAYMENT_PENDING',  # Payment initiated, waiting for confirmation
    'PAID',             # Payment completed (for electronic payments)
    'SUBMITTED',        # Request submitted (appointment can be modified)
    'UNDER_REVIEW',     # Agent reviewing (appointment can be viewed)
    'DOSSIER_VALIDE',   # Approved (appointment confirmed)
]


def validate_appointment_access(request_status: str, action: str = "access appointments") -> None:
    """
    Validate that the service request status allows appointment operations.

    Args:
        request_status: Current status of the service request
        action: Description of the action being attempted (for error message)

    Raises:
        HTTPException: If status doesn't allow appointment operations
    """
    if request_status not in APPOINTMENT_ALLOWED_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": f"Cannot {action} in status: {request_status}",
                "message_es": f"No puede acceder a citas en estado: {request_status}. Complete el pago primero.",
                "message_fr": f"Impossible d'accéder aux rendez-vous en statut: {request_status}. Veuillez d'abord effectuer le paiement.",
                "allowed_statuses": APPOINTMENT_ALLOWED_STATUSES,
                "current_status": request_status,
            }
        )


# =============================================================================
# LOCATION ENDPOINTS
# =============================================================================

@router.get(
    "/{request_id}/appointments/locations",
    response_model=AppointmentLocationsListResponse,
    summary="Get available locations for appointment",
    description="""
    Get available locations (Malabo and Bata) for appointment selection.

    Locations are determined by the workflow's entity code:
    - PASAPORTE, DIP → CNEDOGE (Malabo, Bata)
    - CONDUCIR, VEHICULO → DGT (Malabo, Bata)
    - RESIDENCIA, VISA → EXTRANJERIA (Malabo, Bata)
    - FUNCIONARIO, CARNET → MINFP (Malabo, Bata)
    """
)
async def get_appointment_locations(
    request_id: UUID,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user)
):
    """Get available locations for a service request."""
    # Get service request
    request = await db.fetchrow("""
        SELECT id, user_id, workflow_code, status
        FROM service_requests
        WHERE id = $1
    """, request_id)

    if not request:
        raise HTTPException(status_code=404, detail="Service request not found")

    # Verify ownership
    if str(request['user_id']) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")

    # Validate status allows appointment access
    validate_appointment_access(request['status'], "view appointment locations")

    # Get entity code for this workflow
    entity_code = await appointment_service.get_entity_code_for_workflow(
        db, request['workflow_code']
    )
    if not entity_code:
        return []

    # Get locations from entity_locations table via appointment_slot_configs FK
    # Migration 030 moved location data to entity_locations table
    # Note: location_code is generated dynamically (not stored in DB)
    rows = await db.fetch("""
        SELECT DISTINCT ON (el.city, el.location_name)
            el.id,
            el.entity_code,
            el.location_name,
            el.location_address,
            el.city,
            el.region,
            el.phone,
            el.email,
            el.is_main_office
        FROM entity_locations el
        INNER JOIN appointment_slot_configs asc_cfg ON asc_cfg.entity_location_id = el.id
        WHERE el.entity_code = $1
        AND el.is_active = TRUE
        AND asc_cfg.is_active = TRUE
        ORDER BY el.city, el.location_name, el.id
    """, entity_code)

    locations = [
        EntityLocationResponse(
            id=row['id'],
            entity_code=row['entity_code'],
            location_code=f"{row['entity_code']}_{row['city']}".upper(),  # Generated: CNEDOGE_MALABO
            location_name=row['location_name'],
            city=row['city'],
            province=row['city'],  # Province = city for GE (Malabo/Bata are provinces)
            region=row['region'],
            address=row['location_address'],
            phone=row['phone'],
            email=row['email'],
            is_main_office=row['is_main_office'] or (row['city'] == 'Malabo')
        )
        for row in rows
    ]

    return AppointmentLocationsListResponse(
        entity_code=entity_code,
        locations=locations,
        count=len(locations)
    )


# =============================================================================
# SLOT ENDPOINTS
# =============================================================================

@router.get(
    "/{request_id}/appointments/slots",
    response_model=AppointmentSlotsListResponse,
    summary="Get available appointment slots",
    description="""
    Get available appointment slots for a specific location.

    Returns up to 6 available slots, starting from the minimum delay date
    (7 business days by default). Considers both confirmed reservations
    AND active holds when calculating availability.

    Migration 030: Now accepts entity_location_id (UUID) instead of location_name.
    """
)
async def get_available_slots(
    request_id: UUID,
    entity_location_id: UUID = Query(..., description="FK to entity_locations table"),
    from_date: Optional[date] = Query(None, description="Start date (defaults to min delay date)"),
    limit: int = Query(6, ge=1, le=20, description="Max slots to return"),
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user)
):
    """Get available appointment slots for a location."""
    # Get service request
    request = await db.fetchrow("""
        SELECT id, user_id, workflow_code, status
        FROM service_requests
        WHERE id = $1
    """, request_id)

    if not request:
        raise HTTPException(status_code=404, detail="Service request not found")

    # Verify ownership
    if str(request['user_id']) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")

    # Validate status allows appointment access
    validate_appointment_access(request['status'], "view appointment slots")

    # Verify entity_location exists and is active
    location = await db.fetchrow("""
        SELECT entity_code, location_name, city
        FROM entity_locations
        WHERE id = $1 AND is_active = TRUE
    """, entity_location_id)

    if not location:
        raise HTTPException(
            status_code=404,
            detail=f"Entity location not found or inactive: {entity_location_id}"
        )

    # Direct call: entity_location_id UUID → set-based v3 function
    slots = await appointment_service.get_available_slots(
        db=db,
        entity_location_id=entity_location_id,
        from_date=from_date,
        limit=limit
    )

    slot_responses = [
        AvailableSlotResponse(
            slot_date=slot.slot_date,
            slot_time=slot.slot_time,
            location_name=slot.location_name,
            location_address=slot.location_address,
            slots_remaining=slot.slots_remaining,
            city=slot.city or location['city']
        )
        for slot in slots
    ]

    return AppointmentSlotsListResponse(
        entity_code=location['entity_code'],
        location_name=location['location_name'],
        from_date=from_date or date.today(),
        slots=slot_responses,
        count=len(slot_responses),
        has_availability=len(slot_responses) > 0
    )


# =============================================================================
# AVAILABLE DAYS ENDPOINT (Calendar view)
# =============================================================================

@router.get(
    "/{request_id}/appointments/available-days",
    response_model=AvailableDaysListResponse,
    summary="Get days with available slots for calendar view",
    description="""
    Returns dates that have available appointment slots, grouped by day.
    Designed for rendering a calendar where available days are highlighted.
    Use the /slots endpoint with a specific from_date to get time slots for a day.
    """
)
async def get_available_days(
    request_id: UUID,
    entity_location_id: UUID = Query(..., description="FK to entity_locations table"),
    from_date: Optional[date] = Query(None, description="Start of range (defaults to min delay date)"),
    to_date: Optional[date] = Query(None, description="End of range (defaults to from_date + 60 days)"),
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user)
):
    """Get days with available appointment slots for calendar rendering."""
    # Get service request
    request = await db.fetchrow("""
        SELECT id, user_id, workflow_code, status
        FROM service_requests
        WHERE id = $1
    """, request_id)

    if not request:
        raise HTTPException(status_code=404, detail="Service request not found")

    # Verify ownership
    if str(request['user_id']) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")

    # Validate status allows appointment access
    validate_appointment_access(request['status'], "view available days")

    # Verify entity_location exists and is active
    location = await db.fetchrow("""
        SELECT entity_code, location_name, city
        FROM entity_locations
        WHERE id = $1 AND is_active = TRUE
    """, entity_location_id)

    if not location:
        raise HTTPException(
            status_code=404,
            detail=f"Entity location not found or inactive: {entity_location_id}"
        )

    # Get all slots in range (high limit to cover full 60-day window)
    slots = await appointment_service.get_available_slots(
        db=db,
        entity_location_id=entity_location_id,
        from_date=from_date,
        limit=500
    )

    # Group by date
    days_map: dict = {}
    for slot in slots:
        d = slot.slot_date
        if d not in days_map:
            days_map[d] = {"time_slot_count": 0, "total_slots_remaining": 0}
        days_map[d]["time_slot_count"] += 1
        days_map[d]["total_slots_remaining"] += slot.slots_remaining

    # Filter to to_date range if provided
    if to_date:
        days_map = {d: v for d, v in days_map.items() if d <= to_date}

    days = sorted([
        AvailableDayResponse(slot_date=d, **v) for d, v in days_map.items()
    ], key=lambda x: x.slot_date)

    # min_date = earliest bookable date (delay-aware)
    min_date = slots[0].slot_date if slots else None

    effective_from = from_date or (min_date or date.today())
    effective_to = to_date or (effective_from + timedelta(days=59))

    return AvailableDaysListResponse(
        entity_code=location['entity_code'],
        location_name=location['location_name'],
        from_date=effective_from,
        to_date=effective_to,
        days=days,
        count=len(days),
        min_date=min_date
    )


# =============================================================================
# HOLD ENDPOINTS
# =============================================================================

@router.post(
    "/{request_id}/appointments/hold",
    response_model=HoldSlotResponse,
    summary="Hold an appointment slot",
    description="""
    Create a temporary hold on an appointment slot before payment.

    The hold is valid for 15 minutes while user completes payment.
    After 15 minutes without payment, the hold expires automatically.
    Any previous hold for this request is released.

    Migration 030: Now uses entity_location_id FK instead of location_name/address.
    """
)
async def hold_appointment_slot(
    request_id: UUID,
    hold_request: HoldSlotRequest,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user)
):
    """Create a temporary hold on an appointment slot."""
    # Get service request
    request = await db.fetchrow("""
        SELECT id, user_id, workflow_code, status
        FROM service_requests
        WHERE id = $1
    """, request_id)

    if not request:
        raise HTTPException(status_code=404, detail="Service request not found")

    # Verify ownership
    if str(request['user_id']) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")

    # Validate status allows appointment access
    validate_appointment_access(request['status'], "hold appointment slot")

    # Create hold (migration 030: uses entity_location_id)
    result = await appointment_service.hold_slot(
        db=db,
        service_request_id=request_id,
        entity_location_id=hold_request.entity_location_id,
        appointment_date=hold_request.appointment_date,
        appointment_time=hold_request.appointment_time,
        slot_config_id=hold_request.slot_config_id
    )

    if result.success and result.hold:
        # Publish APPOINTMENT_BOOKED event (slot reserved, pending payment)
        try:
            EventBus.publish_nowait(
                EventType.APPOINTMENT_BOOKED,
                {
                    "request_id": str(request_id),
                    "user_id": str(request['user_id']),
                    "user_email": current_user.email,
                    "user_name": f"{current_user.first_name} {current_user.last_name}",
                    "user_phone": getattr(current_user, 'phone_number', None),
                    "preferred_language": getattr(current_user, 'preferred_language', 'es'),
                    "workflow_code": request['workflow_code'],
                    "appointment_date": str(result.hold.appointment_date) if result.hold.appointment_date else None,
                    "appointment_time": str(result.hold.appointment_time) if result.hold.appointment_time else None,
                    "location": result.hold.location_name,
                    "expires_at": str(result.hold.expires_at) if result.hold.expires_at else None,
                    "timestamp": datetime.now().isoformat(),
                }
            )
            logger.info(f"APPOINTMENT_BOOKED event published for request {request_id}")
        except Exception as e:
            logger.error(f"Failed to publish APPOINTMENT_BOOKED event: {e}")

        return HoldSlotResponse(
            success=True,
            hold_id=result.hold.id,
            location_name=result.hold.location_name,
            appointment_date=result.hold.appointment_date,
            appointment_time=result.hold.appointment_time,
            expires_at=result.hold.expires_at,
            expires_in_seconds=result.expires_in_seconds
        )
    else:
        return HoldSlotResponse(
            success=False,
            error=result.error or "Failed to hold appointment slot"
        )


@router.get(
    "/{request_id}/appointments/hold-status",
    response_model=AppointmentHoldStatus,
    summary="Get appointment hold status",
    description="""
    Get the current hold status for a service request.

    Returns whether there's an active hold, its details, and expiry info.
    Used to display hold status in UI and decide next steps.
    """
)
async def get_hold_status(
    request_id: UUID,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user)
):
    """Get the current hold status for a service request."""
    # Get service request
    request = await db.fetchrow("""
        SELECT id, user_id, workflow_code, status
        FROM service_requests
        WHERE id = $1
    """, request_id)

    if not request:
        raise HTTPException(status_code=404, detail="Service request not found")

    # Verify ownership
    if str(request['user_id']) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")

    # Validate status allows appointment access
    validate_appointment_access(request['status'], "check appointment hold status")

    # Get hold status
    hold = await appointment_service.get_hold_status(db, request_id)

    if hold:
        from datetime import datetime, timezone
        now = datetime.now(hold.expires_at.tzinfo) if hold.expires_at.tzinfo else datetime.now(timezone.utc)
        is_expired = hold.status.value == 'expired' or (
            hold.status.value == 'held' and now > hold.expires_at
        )

        return AppointmentHoldStatus(
            has_hold=True,
            status=hold.status.value,
            location_name=hold.location_name,
            city=hold.city,  # Include city from appointment_holds table
            appointment_date=hold.appointment_date,
            appointment_time=hold.appointment_time,
            expires_at=hold.expires_at,
            is_expired=is_expired
        )
    else:
        return AppointmentHoldStatus(
            has_hold=False,
            status=None,
            is_expired=False
        )


@router.delete(
    "/{request_id}/appointments/hold",
    response_model=ReleaseHoldResponse,
    summary="Release appointment hold",
    description="""
    Release a held appointment slot.

    Called when user wants to select a different slot or cancel.
    The slot becomes available for other users.
    """
)
async def release_hold(
    request_id: UUID,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user)
):
    """Release a held appointment slot."""
    # Get service request
    request = await db.fetchrow("""
        SELECT id, user_id, workflow_code, status
        FROM service_requests
        WHERE id = $1
    """, request_id)

    if not request:
        raise HTTPException(status_code=404, detail="Service request not found")

    # Verify ownership
    if str(request['user_id']) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")

    # Validate status allows appointment access
    validate_appointment_access(request['status'], "release appointment hold")

    # Release hold
    released = await appointment_service.release_hold(db, request_id)

    if released:
        return ReleaseHoldResponse(
            success=True,
            message="Appointment hold released successfully"
        )
    else:
        return ReleaseHoldResponse(
            success=False,
            message="No active hold found to release"
        )


# =============================================================================
# FALLBACK ENDPOINTS
# =============================================================================

@router.post(
    "/{request_id}/appointments/fallback",
    response_model=SubmitWithoutAppointmentResponse,
    summary="Submit without appointment (fallback)",
    description="""
    Submit a request without an appointment when no slots are available.

    User selects their preferred location, and an agent will assign
    an appointment later. Used when all slots are booked.

    Migration 030: Now uses entity_location_id FK instead of location name.
    """
)
async def submit_without_appointment(
    request_id: UUID,
    fallback_request: SubmitWithoutAppointmentRequest,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user)
):
    """Submit request without appointment (fallback when no slots)."""
    # Get service request
    request = await db.fetchrow("""
        SELECT id, user_id, workflow_code, status
        FROM service_requests
        WHERE id = $1
    """, request_id)

    if not request:
        raise HTTPException(status_code=404, detail="Service request not found")

    # Verify ownership
    if str(request['user_id']) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")

    # Validate status allows appointment access
    validate_appointment_access(request['status'], "submit without appointment")

    # Submit without appointment (migration 030: uses entity_location_id)
    result = await appointment_service.submit_without_appointment(
        db=db,
        service_request_id=request_id,
        entity_location_id=fallback_request.entity_location_id
    )

    if result.success:
        return SubmitWithoutAppointmentResponse(
            success=True,
            location_name=result.location_name,
            message="Su solicitud ha sido enviada. Un agente le asignará una cita pronto."
        )
    else:
        return SubmitWithoutAppointmentResponse(
            success=False,
            error=result.error or "Failed to submit request"
        )


# =============================================================================
# CONFIRM ENDPOINT (Called by Payment Webhook)
# =============================================================================

@router.post(
    "/{request_id}/appointments/confirm",
    response_model=ConfirmHoldResponse,
    summary="Confirm appointment hold after payment",
    description="""
    Confirm a held appointment after successful payment.

    This endpoint is called by the payment webhook after payment success.
    It creates a permanent reservation and updates the service request
    with cita_date, cita_time, and cita_location.

    Note: This requires elevated permissions (payment webhook or admin).
    """
)
async def confirm_appointment_hold(
    request_id: UUID,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user)
):
    """Confirm appointment hold after payment (webhook endpoint)."""
    # This endpoint should be called by payment webhook
    # For now, allow owner or admin to call it

    # Get service request
    request = await db.fetchrow("""
        SELECT id, user_id, workflow_code, status
        FROM service_requests
        WHERE id = $1
    """, request_id)

    if not request:
        raise HTTPException(status_code=404, detail="Service request not found")

    # Verify ownership or admin/agent (Migration 048: unified 'agent' role)
    is_owner = str(request['user_id']) == str(current_user.id)
    is_staff = current_user.role in ['admin', 'agent']

    if not is_owner and not is_staff:
        raise HTTPException(status_code=403, detail="Access denied")

    # Validate status allows appointment confirmation (payment must be at least pending)
    validate_appointment_access(request['status'], "confirm appointment hold")

    # Confirm hold
    result = await appointment_service.confirm_hold(db, request_id)

    # Publish APPOINTMENT_CONFIRMED event if successful (hold confirmed after payment)
    if result.success:
        try:
            EventBus.publish_nowait(
                EventType.APPOINTMENT_CONFIRMED,
                {
                    "request_id": str(request_id),
                    "user_id": str(request['user_id']),
                    "user_email": current_user.email,
                    "user_name": f"{current_user.first_name} {current_user.last_name}",
                    "user_phone": getattr(current_user, 'phone_number', None),
                    "preferred_language": getattr(current_user, 'preferred_language', 'es'),
                    "workflow_code": request['workflow_code'],
                    "appointment_date": str(result.appointment_date) if result.appointment_date else None,
                    "appointment_time": str(result.appointment_time) if result.appointment_time else None,
                    "location": result.location_name,
                    "timestamp": datetime.now().isoformat(),
                }
            )
            logger.info(f"APPOINTMENT_CONFIRMED event published for request {request_id}")
        except Exception as e:
            logger.error(f"Failed to publish APPOINTMENT_CONFIRMED event: {e}")

    return ConfirmHoldResponse(
        success=result.success,
        appointment_date=result.appointment_date,
        appointment_time=result.appointment_time,
        location_name=result.location_name,
        city=result.city,  # Include city from confirm_appointment_hold function
        error=result.error
    )
