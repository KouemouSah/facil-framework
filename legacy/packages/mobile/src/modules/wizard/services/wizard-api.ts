/**
 * Wizard Session API — thin wrappers around apiGet/apiPost/apiPut/apiDelete/apiUpload.
 *
 * Backend: app/modules/service_requests/api/wizard_session_routes.py
 * All paths centralized via API_ENDPOINTS.wizardSessions and API_ENDPOINTS.serviceRequests.
 */

import { apiGet, apiPost, apiPut, apiDelete, apiUpload } from '@core/api/client';
import { API_ENDPOINTS } from '@core/api/endpoints';
import type {
  WizardSessionCreate,
  WizardSession,
  WorkflowConfig,
  DocumentPreview,
  DocumentConfirmRequest,
  FormConfig,
  FormDataSaveRequest,
  PreparePaymentResult,
  InitiatePaymentRequest,
  InitiatePaymentResult,
  AppointmentLocationsResponse,
  AvailableDaysResponse,
  AvailableSlotsResponse,
  AppointmentSelectionRequest,
  AvailableSitesResponse,
  SiteSelectionRequest,
} from '../types/wizard.types';
import { Platform } from 'react-native';

// Workflow config (from service-requests router — kept here for proximity to its consumer)
export async function getWorkflowConfig(workflowCode: string): Promise<WorkflowConfig> {
  return apiGet<WorkflowConfig>(API_ENDPOINTS.serviceRequests.workflowDetail(workflowCode));
}

// Session lifecycle
export async function createSession(data: WizardSessionCreate): Promise<WizardSession> {
  return apiPost<WizardSession>(API_ENDPOINTS.wizardSessions.create, data);
}

export async function getSession(sessionId: string): Promise<WizardSession> {
  return apiGet<WizardSession>(API_ENDPOINTS.wizardSessions.get(sessionId));
}

export async function deleteSession(sessionId: string, reason?: string): Promise<void> {
  const base = API_ENDPOINTS.wizardSessions.delete(sessionId);
  const url = reason ? `${base}?reason=${encodeURIComponent(reason)}` : base;
  await apiDelete(url);
}

// Documents
export async function previewDocument(
  sessionId: string,
  documentCode: string,
  fileUri: string,
  fileName: string,
): Promise<DocumentPreview> {
  const formData = new FormData();
  const match = /\.(\w+)$/.exec(fileName);
  const ext = match ? match[1].toLowerCase() : 'jpg';
  // Strict MIME whitelist — backend OWASP magic-bytes check rejects octet-stream.
  const type = ext === 'pdf' ? 'application/pdf'
    : ext === 'jpg' || ext === 'jpeg' ? 'image/jpeg'
    : ext === 'png' ? 'image/png'
    : ext === 'webp' ? 'image/webp'
    : 'image/jpeg';

  formData.append('file', {
    uri: Platform.OS === 'android' ? fileUri : fileUri.replace('file://', ''),
    name: fileName,
    type,
  } as unknown as Blob);

  return apiUpload<DocumentPreview>(
    `${API_ENDPOINTS.wizardSessions.documentPreview(sessionId)}?document_code=${encodeURIComponent(documentCode)}`,
    formData,
  );
}

export async function confirmDocument(
  sessionId: string,
  data: DocumentConfirmRequest,
): Promise<WizardSession> {
  return apiPost<WizardSession>(API_ENDPOINTS.wizardSessions.documentConfirm(sessionId), data);
}

export async function deleteDocument(
  sessionId: string,
  documentCode: string,
): Promise<WizardSession> {
  return apiDelete<WizardSession>(
    API_ENDPOINTS.wizardSessions.documentDelete(sessionId, documentCode),
  );
}

/** Use a document already stored in the user's vault (P2/P4 integration). */
export async function useVaultDocument(
  sessionId: string,
  payload: { vault_document_id: string; document_code: string },
): Promise<WizardSession> {
  // Backend `UseVaultDocumentRequest` expects `vault_document_id` (NOT
  // `document_id`). Mobile P0 declared the wrong field name; fixed in P4
  // before the first real call.
  return apiPost<WizardSession>(
    API_ENDPOINTS.wizardSessions.useVaultDocument(sessionId),
    payload,
  );
}

// Form data
export async function saveFormData(
  sessionId: string,
  data: FormDataSaveRequest,
): Promise<WizardSession> {
  return apiPut<WizardSession>(API_ENDPOINTS.wizardSessions.formData(sessionId), data);
}

export async function getFormConfig(
  sessionId: string,
  stepId: string,
): Promise<FormConfig> {
  return apiGet<FormConfig>(API_ENDPOINTS.wizardSessions.formConfig(sessionId, stepId));
}

// Payment
export async function preparePayment(
  sessionId: string,
): Promise<PreparePaymentResult> {
  return apiPost<PreparePaymentResult>(API_ENDPOINTS.wizardSessions.preparePayment(sessionId));
}

/** Persist the wizard session (commits to DB) before payment initiation. */
export async function persistSession(
  sessionId: string,
  paymentId?: string,
): Promise<unknown> {
  return apiPost(
    API_ENDPOINTS.wizardSessions.persist(sessionId),
    paymentId ? { payment_id: paymentId } : {},
  );
}

export async function initiatePayment(
  sessionId: string,
  data: InitiatePaymentRequest,
): Promise<InitiatePaymentResult> {
  return apiPost<InitiatePaymentResult>(
    API_ENDPOINTS.wizardSessions.initiatePayment(sessionId),
    data,
  );
}

// Site selection
export async function getAvailableSites(
  sessionId: string,
): Promise<AvailableSitesResponse> {
  return apiGet<AvailableSitesResponse>(API_ENDPOINTS.wizardSessions.availableSites(sessionId));
}

export async function selectSite(
  sessionId: string,
  data: SiteSelectionRequest,
): Promise<{ success: boolean; site_selection: WizardSession['site_selection'] }> {
  return apiPost(API_ENDPOINTS.wizardSessions.selectSite(sessionId), data);
}

// Appointments
export async function getAppointmentLocations(
  sessionId: string,
): Promise<AppointmentLocationsResponse> {
  return apiGet<AppointmentLocationsResponse>(
    API_ENDPOINTS.wizardSessions.appointmentLocations(sessionId),
  );
}

export async function getAvailableDays(
  sessionId: string,
  entityLocationId: string,
  fromDate?: string,
  toDate?: string,
): Promise<AvailableDaysResponse> {
  const params: Record<string, string> = { entity_location_id: entityLocationId };
  if (fromDate) params.from_date = fromDate;
  if (toDate) params.to_date = toDate;
  return apiGet<AvailableDaysResponse>(
    API_ENDPOINTS.wizardSessions.appointmentAvailableDays(sessionId),
    params,
  );
}

export async function getAvailableSlots(
  sessionId: string,
  entityLocationId: string,
  fromDate?: string,
  limit?: number,
): Promise<AvailableSlotsResponse> {
  const params: Record<string, string | number> = { entity_location_id: entityLocationId };
  if (fromDate) params.from_date = fromDate;
  if (limit) params.limit = limit;
  return apiGet<AvailableSlotsResponse>(
    API_ENDPOINTS.wizardSessions.appointmentAvailableSlots(sessionId),
    params,
  );
}

export async function selectAppointment(
  sessionId: string,
  data: AppointmentSelectionRequest,
): Promise<{ success: boolean; appointment_data: WizardSession['appointment_data'] }> {
  return apiPost(API_ENDPOINTS.wizardSessions.appointmentSelect(sessionId), data);
}
