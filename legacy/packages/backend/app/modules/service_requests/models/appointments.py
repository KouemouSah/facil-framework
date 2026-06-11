"""
Pydantic models for Appointment (Citizen-First Flow).

This module handles the new workflow where citizens:
1. Select a location (Malabo or Bata) BEFORE payment
2. Select from available appointment slots BEFORE payment
3. Slot is temporarily held during payment (15 min)
4. Hold is confirmed after payment success
5. Fallback: submit without appointment if no slots available

Flow: DRAFT → DOCUMENTS → REVIEW → SELECT_LOCATION → SELECT_SLOT → PAYMENT → SUBMITTED
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date, time
from uuid import UUID


class EntityLocationResponse(BaseModel):
    """
    Location available for appointments.

    NOTE: Data comes from entity_locations table (migration 030).
    appointment_slot_configs references entity_locations via FK.

    Entity codes: CNEDOGE, DGT, EXTRANJERIA, MINFP, ONRC, MINHV
    Cities: Malabo (capital, insular) or Bata (continental)
    """
    id: UUID
    entity_code: str = Field(..., description="Entity code (CNEDOGE, DGT, etc.)")
    location_code: str = Field(..., description="Unique code (e.g., CNEDOGE_MALABO)")
    location_name: str = Field(..., description="Display name (e.g., 'CNEDOGE Malabo')")
    city: str = Field(..., description="City (Malabo or Bata)")
    province: Optional[str] = Field(None, description="Province (Bioko Norte or Litoral)")
    region: Optional[str] = Field(None, description="Region (Insular or Continental)")
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    is_main_office: bool = Field(False, description="True for main office (typically Malabo)")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "entity_code": "CNEDOGE",
                "location_code": "CNEDOGE_MALABO",
                "location_name": "CNEDOGE Malabo",
                "city": "Malabo",
                "province": "Bioko Norte",
                "region": "Insular",
                "address": "Malabo, Bioko Norte",
                "is_main_office": True
            }
        }


class AvailableSlotResponse(BaseModel):
    """
    Available appointment slot for citizen selection.

    Returns the next 6 available slots (considering reservations + holds).
    Minimum 7 business days from payment date.
    """
    slot_date: date = Field(..., description="Available appointment date")
    slot_time: time = Field(..., description="Available appointment time")
    location_name: str = Field(..., description="Location name")
    location_address: Optional[str] = None
    slots_remaining: int = Field(1, description="Remaining slots at this time", ge=0)
    city: Optional[str] = Field(None, description="City (Malabo or Bata)")

    class Config:
        json_schema_extra = {
            "example": {
                "slot_date": "2025-01-15",
                "slot_time": "09:00:00",
                "location_name": "CNEDOGE Malabo",
                "location_address": "Malabo, Bioko Norte",
                "slots_remaining": 5
            }
        }


class AvailableDayResponse(BaseModel):
    """A date with available appointment slots (for calendar rendering)."""
    slot_date: date = Field(..., description="Date with availability")
    time_slot_count: int = Field(..., description="Number of distinct time slots available")
    total_slots_remaining: int = Field(..., description="Sum of all slots remaining across time slots")


class AvailableDaysListResponse(BaseModel):
    """Available days for calendar view."""
    entity_code: str
    location_name: str
    from_date: date
    to_date: date
    days: List[AvailableDayResponse]
    count: int
    min_date: Optional[date] = Field(None, description="Earliest bookable date (after delay)")


class HoldSlotRequest(BaseModel):
    """
    Request to hold an appointment slot before payment.

    The hold is valid for 15 minutes while user completes payment.
    After 15 minutes without payment, the hold expires automatically.

    Migration 030: Now uses entity_location_id FK instead of location_name/address.
    """
    entity_location_id: UUID = Field(
        ...,
        description="FK to entity_locations table"
    )
    slot_config_id: Optional[UUID] = Field(
        None,
        description="Optional slot_config_id from appointment_slot_configs table"
    )
    appointment_date: date = Field(
        ...,
        description="Selected appointment date"
    )
    appointment_time: time = Field(
        ...,
        description="Selected appointment time"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "entity_location_id": "550e8400-e29b-41d4-a716-446655440000",
                "slot_config_id": "550e8400-e29b-41d4-a716-446655440001",
                "appointment_date": "2025-01-15",
                "appointment_time": "09:00:00"
            }
        }


class HoldSlotResponse(BaseModel):
    """
    Response after holding an appointment slot.

    On success, contains hold details and expiry time.
    User has `expires_in_seconds` to complete payment.
    """
    success: bool
    hold_id: Optional[UUID] = Field(None, description="Hold record ID")
    location_name: Optional[str] = None
    appointment_date: Optional[date] = None
    appointment_time: Optional[time] = None
    expires_at: Optional[datetime] = Field(None, description="When the hold expires")
    expires_in_seconds: int = Field(0, description="Seconds until hold expires", ge=0)
    error: Optional[str] = Field(None, description="Error message if failed")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "hold_id": "550e8400-e29b-41d4-a716-446655440000",
                "location_name": "CNEDOGE Malabo",
                "appointment_date": "2025-01-15",
                "appointment_time": "09:00:00",
                "expires_at": "2025-01-08T10:15:00Z",
                "expires_in_seconds": 900
            }
        }


class ConfirmHoldResponse(BaseModel):
    """
    Response after confirming appointment hold (called by payment webhook).

    On success, appointment is permanently booked and
    service_request is updated with cita_date, cita_time, cita_location, selected_city.
    """
    success: bool
    appointment_date: Optional[date] = None
    appointment_time: Optional[time] = None
    location_name: Optional[str] = None
    city: Optional[str] = Field(None, description="City (Malabo or Bata)")
    error: Optional[str] = Field(None, description="Error message if failed")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "appointment_date": "2025-01-15",
                "appointment_time": "09:00:00",
                "location_name": "CNEDOGE Malabo"
            }
        }


class AppointmentHoldStatus(BaseModel):
    """
    Current status of an appointment hold for a service request.

    Used to display hold status in UI and decide next steps.
    """
    has_hold: bool = Field(False, description="Whether there's an active hold")
    status: Optional[str] = Field(
        None,
        description="Hold status: held, confirmed, expired, released, fallback"
    )
    location_name: Optional[str] = None
    city: Optional[str] = Field(None, description="City (Malabo or Bata)")
    appointment_date: Optional[date] = None
    appointment_time: Optional[time] = None
    expires_at: Optional[datetime] = None
    is_expired: bool = Field(False, description="True if hold has expired")

    class Config:
        json_schema_extra = {
            "example": {
                "has_hold": True,
                "status": "held",
                "location_name": "CNEDOGE Malabo",
                "appointment_date": "2025-01-15",
                "appointment_time": "09:00:00",
                "expires_at": "2025-01-08T10:15:00Z",
                "is_expired": False
            }
        }


class SubmitWithoutAppointmentRequest(BaseModel):
    """
    Request to submit without appointment (fallback when no slots available).

    User selects preferred location, agent will assign appointment later.

    Migration 030: Now uses entity_location_id FK instead of location name.
    """
    entity_location_id: UUID = Field(
        ...,
        description="FK to entity_locations table"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "entity_location_id": "550e8400-e29b-41d4-a716-446655440000"
            }
        }


class SubmitWithoutAppointmentResponse(BaseModel):
    """Response after submitting without appointment (fallback)"""
    success: bool
    location_name: Optional[str] = None
    message: str = Field(
        "",
        description="Informative message for user"
    )
    error: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "location_name": "CNEDOGE Bata",
                "message": "Su solicitud ha sido enviada. Un agente le asignará una cita."
            }
        }


class ReleaseHoldResponse(BaseModel):
    """Response after releasing an appointment hold"""
    success: bool
    message: str = ""


class AppointmentLocationsListResponse(BaseModel):
    """List of locations for an entity"""
    entity_code: str
    locations: List[EntityLocationResponse]
    count: int


class AppointmentSlotsListResponse(BaseModel):
    """List of available slots for a location"""
    entity_code: str
    location_name: str
    from_date: date
    slots: List[AvailableSlotResponse]
    count: int
    has_availability: bool = Field(
        ...,
        description="True if any slots available"
    )
