/**
 * Agent Appointments API
 * API client for agent dashboard appointments operations
 *
 * @module agent-dashboard/services/appointments-api
 * @date 2026-01-26
 */

import { getAuthData } from '@/core/auth/storage';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const API_VERSION = '/api/v1';

// =============================================================================
// TYPES
// =============================================================================

export interface LocationInfo {
  id: string;
  name: string;
  city: string;
}

export interface SlotTimeDetail {
  time: string;
  available: number;
  booked: number;
  capacity: number;
  isAvailable: boolean;
}

export interface DaySlotDetail {
  date: string;
  dayName: string;
  dayNumber: number;
  isToday: boolean;
  isPast: boolean;
  isBlocked: boolean;
  slots: SlotTimeDetail[];
  totalAvailable: number;
  totalBooked: number;
  totalCapacity: number;
}

export interface SlotsCalendarResponse {
  weekStart: string;
  weekEnd: string;
  entityCode: string;
  location: LocationInfo | null;
  locationsAvailable: LocationInfo[];
  days: DaySlotDetail[];
  totalAvailable: number;
  totalCapacity: number;
}

export interface TodayAppointmentDetail {
  id: string;
  requestId: string;
  reference: string;
  workflowCode: string;
  citizenName: string;
  citizenEmail: string | null;
  citizenPhone: string | null;
  appointmentTime: string;
  status: string;
  locationName: string;
  locationId: string;
  notes: string | null;
  createdAt: string;
}

export interface TodayAppointmentsListResponse {
  date: string;
  entityCode: string;
  location: LocationInfo | null;
  appointments: TodayAppointmentDetail[];
  total: number;
  completed: number;
  pending: number;
  cancelled: number;
}

export interface AgentBookingRequest {
  requestId: string;
  entityLocationId: string;
  appointmentDate: string;
  appointmentTime: string;
}

export interface AgentBookingResponse {
  success: boolean;
  reservationId?: string;
  appointmentDate?: string;
  appointmentTime?: string;
  locationName?: string;
  error?: string;
}

export interface RescheduleRequest {
  newDate: string;
  newTime: string;
  reason?: string;
}

export interface RescheduleResponse {
  success: boolean;
  oldDate?: string;
  oldTime?: string;
  newDate?: string;
  newTime?: string;
  error?: string;
}

export interface ExistingAppointmentInfo {
  reservationId: string;
  date: string;
  time: string;
  locationName: string | null;
  status: string;
}

export interface AssignedRequestForAppointment {
  id: string;
  reference: string;
  citizenName: string;
  workflowCode: string;
  status: string;
  createdAt: string;
  existingAppointment: ExistingAppointmentInfo | null;
}

export interface AssignedRequestsListResponse {
  requests: AssignedRequestForAppointment[];
  total: number;
}

export interface AppointmentDetail {
  id: string;
  requestId: string;
  reference: string;
  workflowCode: string;
  citizen: {
    name: string;
    email: string | null;
    phone: string | null;
  };
  appointment: {
    date: string;
    time: string | null;
    status: string;
  };
  location: {
    id: string;
    name: string;
    address: string | null;
    city: string;
    entityCode: string;
  };
  notes: string | null;
  createdAt: string;
  updatedAt: string | null;
}

// Backend response types (snake_case)
interface BackendSlotTimeDetail {
  time: string;
  available: number;
  booked: number;
  capacity: number;
  is_available: boolean;
}

interface BackendDaySlotDetail {
  date: string;
  day_name: string;
  day_number: number;
  is_today: boolean;
  is_past: boolean;
  is_blocked: boolean;
  slots: BackendSlotTimeDetail[];
  total_available: number;
  total_booked: number;
  total_capacity: number;
}

interface BackendSlotsCalendarResponse {
  week_start: string;
  week_end: string;
  entity_code: string;
  location: { id: string; name: string; city: string } | null;
  locations_available: Array<{ id: string; name: string; city: string }>;
  days: BackendDaySlotDetail[];
  total_available: number;
  total_capacity: number;
}

interface BackendTodayAppointmentDetail {
  id: string;
  request_id: string;
  reference: string;
  workflow_code: string;
  citizen_name: string;
  citizen_email: string | null;
  citizen_phone: string | null;
  appointment_time: string;
  status: string;
  location_name: string;
  location_id: string;
  notes: string | null;
  created_at: string;
}

interface BackendTodayAppointmentsListResponse {
  date: string;
  entity_code: string;
  location: { id: string; name: string; city: string } | null;
  appointments: BackendTodayAppointmentDetail[];
  total: number;
  completed: number;
  pending: number;
  cancelled: number;
}

interface BackendExistingAppointmentInfo {
  reservation_id: string;
  date: string;
  time: string;
  location_name: string | null;
  status: string;
}

interface BackendAssignedRequest {
  id: string;
  reference: string;
  citizen_name: string;
  workflow_code: string;
  status: string;
  created_at: string;
  existing_appointment: BackendExistingAppointmentInfo | null;
}

interface BackendAssignedRequestsListResponse {
  requests: BackendAssignedRequest[];
  total: number;
}

// =============================================================================
// TRANSFORM FUNCTIONS
// =============================================================================

function transformSlotTimeDetail(slot: BackendSlotTimeDetail): SlotTimeDetail {
  return {
    time: slot.time,
    available: slot.available,
    booked: slot.booked,
    capacity: slot.capacity,
    isAvailable: slot.is_available,
  };
}

function transformDaySlotDetail(day: BackendDaySlotDetail): DaySlotDetail {
  return {
    date: day.date,
    dayName: day.day_name,
    dayNumber: day.day_number,
    isToday: day.is_today,
    isPast: day.is_past,
    isBlocked: day.is_blocked,
    slots: day.slots.map(transformSlotTimeDetail),
    totalAvailable: day.total_available,
    totalBooked: day.total_booked,
    totalCapacity: day.total_capacity,
  };
}

function transformSlotsCalendar(response: BackendSlotsCalendarResponse): SlotsCalendarResponse {
  return {
    weekStart: response.week_start,
    weekEnd: response.week_end,
    entityCode: response.entity_code,
    location: response.location,
    locationsAvailable: response.locations_available,
    days: response.days.map(transformDaySlotDetail),
    totalAvailable: response.total_available,
    totalCapacity: response.total_capacity,
  };
}

function transformTodayAppointment(appt: BackendTodayAppointmentDetail): TodayAppointmentDetail {
  return {
    id: appt.id,
    requestId: appt.request_id,
    reference: appt.reference,
    workflowCode: appt.workflow_code,
    citizenName: appt.citizen_name,
    citizenEmail: appt.citizen_email,
    citizenPhone: appt.citizen_phone,
    appointmentTime: appt.appointment_time,
    status: appt.status,
    locationName: appt.location_name,
    locationId: appt.location_id,
    notes: appt.notes,
    createdAt: appt.created_at,
  };
}

function transformTodayAppointmentsList(response: BackendTodayAppointmentsListResponse): TodayAppointmentsListResponse {
  return {
    date: response.date,
    entityCode: response.entity_code,
    location: response.location,
    appointments: response.appointments.map(transformTodayAppointment),
    total: response.total,
    completed: response.completed,
    pending: response.pending,
    cancelled: response.cancelled,
  };
}

function transformAssignedRequest(req: BackendAssignedRequest): AssignedRequestForAppointment {
  return {
    id: req.id,
    reference: req.reference,
    citizenName: req.citizen_name,
    workflowCode: req.workflow_code,
    status: req.status,
    createdAt: req.created_at,
    existingAppointment: req.existing_appointment ? {
      reservationId: req.existing_appointment.reservation_id,
      date: req.existing_appointment.date,
      time: req.existing_appointment.time,
      locationName: req.existing_appointment.location_name,
      status: req.existing_appointment.status,
    } : null,
  };
}

function transformAssignedRequestsList(response: BackendAssignedRequestsListResponse): AssignedRequestsListResponse {
  return {
    requests: response.requests.map(transformAssignedRequest),
    total: response.total,
  };
}

// =============================================================================
// API CLIENT
// =============================================================================

class AgentAppointmentsApiClient {
  private baseUrl: string;

  constructor() {
    this.baseUrl = `${API_BASE_URL}${API_VERSION}/agent/service-requests`;
  }

  private getToken(): string | null {
    if (typeof window === 'undefined') return null;
    const authData = getAuthData();
    return authData?.access_token || null;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const token = this.getToken();
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    };

    const url = `${this.baseUrl}${endpoint}`;

    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      let errorMessage = `API Error: ${response.status}`;
      if (errorData.detail) {
        errorMessage = typeof errorData.detail === 'string'
          ? errorData.detail
          : errorData.detail.message || JSON.stringify(errorData.detail);
      }
      console.error(`[AgentAppointmentsApi] Error: ${errorMessage}`);
      throw new Error(errorMessage);
    }

    return response.json();
  }

  /**
   * Get assigned requests for appointment scheduling dropdown
   */
  async getMyAssignedRequests(
    entityCode: string,
    includeWithAppointment: boolean = false
  ): Promise<AssignedRequestsListResponse> {
    const params = new URLSearchParams();
    params.append('entity_code', entityCode);
    params.append('include_with_appointment', includeWithAppointment.toString());

    const response = await this.request<BackendAssignedRequestsListResponse>(
      `/appointments/my-assigned?${params.toString()}`
    );

    return transformAssignedRequestsList(response);
  }

  /**
   * Get today's appointments for an entity
   */
  async getTodayAppointments(
    entityCode: string,
    locationId?: string
  ): Promise<TodayAppointmentsListResponse> {
    const params = new URLSearchParams();
    params.append('entity_code', entityCode);
    if (locationId) params.append('location_id', locationId);

    const response = await this.request<BackendTodayAppointmentsListResponse>(
      `/appointments/today-list?${params.toString()}`
    );

    return transformTodayAppointmentsList(response);
  }

  /**
   * Get detailed slots calendar for scheduling
   */
  async getSlotsDetailed(
    entityCode: string,
    weekOffset: number = 0,
    locationId?: string
  ): Promise<SlotsCalendarResponse> {
    const params = new URLSearchParams();
    params.append('entity_code', entityCode);
    params.append('week_offset', weekOffset.toString());
    if (locationId) params.append('location_id', locationId);

    const response = await this.request<BackendSlotsCalendarResponse>(
      `/appointments/slots-detailed?${params.toString()}`
    );

    return transformSlotsCalendar(response);
  }

  /**
   * Book appointment for citizen (agent action)
   */
  async bookForCitizen(booking: AgentBookingRequest): Promise<AgentBookingResponse> {
    interface BackendResponse {
      success: boolean;
      reservation_id?: string;
      appointment_date?: string;
      appointment_time?: string;
      location_name?: string;
      error?: string;
    }

    const response = await this.request<BackendResponse>('/appointments/book-for-citizen', {
      method: 'POST',
      body: JSON.stringify({
        request_id: booking.requestId,
        entity_location_id: booking.entityLocationId,
        appointment_date: booking.appointmentDate,
        appointment_time: booking.appointmentTime,
      }),
    });

    return {
      success: response.success,
      reservationId: response.reservation_id,
      appointmentDate: response.appointment_date,
      appointmentTime: response.appointment_time,
      locationName: response.location_name,
      error: response.error,
    };
  }

  /**
   * Reschedule an existing appointment
   */
  async reschedule(
    reservationId: string,
    data: RescheduleRequest
  ): Promise<RescheduleResponse> {
    interface BackendResponse {
      success: boolean;
      old_date?: string;
      old_time?: string;
      new_date?: string;
      new_time?: string;
      error?: string;
    }

    const response = await this.request<BackendResponse>(
      `/appointments/${reservationId}/reschedule`,
      {
        method: 'PATCH',
        body: JSON.stringify({
          new_date: data.newDate,
          new_time: data.newTime,
          reason: data.reason,
        }),
      }
    );

    return {
      success: response.success,
      oldDate: response.old_date,
      oldTime: response.old_time,
      newDate: response.new_date,
      newTime: response.new_time,
      error: response.error,
    };
  }

  /**
   * Get appointment details
   */
  async getAppointmentDetail(reservationId: string): Promise<AppointmentDetail> {
    const response = await this.request<{
      id: string;
      request_id: string;
      reference: string;
      workflow_code: string;
      citizen: { name: string; email: string | null; phone: string | null };
      appointment: { date: string; time: string | null; status: string };
      location: { id: string; name: string; address: string | null; city: string; entity_code: string };
      notes: string | null;
      created_at: string;
      updated_at: string | null;
    }>(`/appointments/${reservationId}`);

    return {
      id: response.id,
      requestId: response.request_id,
      reference: response.reference,
      workflowCode: response.workflow_code,
      citizen: response.citizen,
      appointment: response.appointment,
      location: {
        id: response.location.id,
        name: response.location.name,
        address: response.location.address,
        city: response.location.city,
        entityCode: response.location.entity_code,
      },
      notes: response.notes,
      createdAt: response.created_at,
      updatedAt: response.updated_at,
    };
  }

  /**
   * Cancel an appointment
   */
  async cancelAppointment(
    reservationId: string,
    reason?: string
  ): Promise<{ message: string }> {
    return this.request(`/appointments/${reservationId}/cancel`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    });
  }

  /**
   * Mark appointment as completed
   */
  async completeAppointment(
    reservationId: string
  ): Promise<{ message: string }> {
    return this.request(`/appointments/${reservationId}/complete`, {
      method: 'POST',
    });
  }
}

// Export singleton instance
export const agentAppointmentsApi = new AgentAppointmentsApiClient();
