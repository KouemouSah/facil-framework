/**
 * Dashboard Types — aligned with backend DashboardSummaryResponse
 */

export interface DashboardStats {
  active: number;
  completed: number;
  pending_action: number;
  total_paid: number;
}

export interface DashboardRecentRequest {
  id: string;
  reference: string;
  workflow_code: string;
  workflow_label: string;
  status: string;
  solicitud_type: string;
  created_at: string;
  updated_at: string;
  total_amount?: number;
}

export interface DashboardRecentPayment {
  id: string;
  service_request_id: string;
  request_reference: string;
  workflow_code: string;
  workflow_label: string;
  amount: number;
  currency: string;
  status: string;
  payment_method?: string;
  created_at: string;
}

export interface CitizenNotification {
  id: string;
  action: string;
  title: string;
  message?: string;
  performed_at: string;
  performer_role: string;
  is_new: boolean;
  new_status?: string;
}

export interface DashboardUpcomingAppointment {
  request_id: string;
  request_reference: string;
  workflow_code: string;
  workflow_label: string;
  appointment_date: string;
  time?: string;
  location?: string;
}

export interface DashboardActionRequired {
  request_id: string;
  reference: string;
  workflow_code: string;
  workflow_label: string;
  status: string;
  message: string;
}

export interface DashboardSummary {
  stats: DashboardStats;
  recent_requests: DashboardRecentRequest[];
  recent_payments: DashboardRecentPayment[];
  notifications: CitizenNotification[];
  unread_count: number;
  upcoming_appointment?: DashboardUpcomingAppointment;
  action_required: DashboardActionRequired[];
}
