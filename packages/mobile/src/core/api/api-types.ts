/**
 * API Types — Readable aliases over the auto-generated `openapi-types.ts`.
 *
 * Source of truth: `openapi-types.ts` (regenerated via `npm run types:gen`).
 * This file ONLY adds aliases and curates what mobile cares about (citizen + business).
 *
 * Adoption strategy:
 *   - New features → use these aliases directly.
 *   - Existing modules with handcrafted types in `*.types.ts` → migrate progressively
 *     once Pydantic↔TS mismatches are resolved (see Phase 0 critique).
 *
 * If an alias below is missing, it means the backend response is inline / untyped
 * in OpenAPI (Dict, Any, untyped FastAPI return). Add a Pydantic response_model
 * upstream rather than re-typing here.
 *
 * IMPORTANT: do not edit `openapi-types.ts` directly. Re-run `npm run types:gen`
 * (staging) or `npm run types:gen-local` (local backend) after backend changes.
 */

import type { components } from './openapi-types';

type Schemas = components['schemas'];

// ---------------------------------------------------------------------------
// Auth & sessions
// ---------------------------------------------------------------------------
export type LoginRequest = Schemas['LoginRequest'];
export type RegisterRequest = Schemas['RegisterRequest'];
export type TokenResponse = Schemas['TokenResponse'];

// ---------------------------------------------------------------------------
// User profile
// ---------------------------------------------------------------------------
export type UserProfile = Schemas['UserProfile'];
export type UserResponse = Schemas['UserResponse'];

// ---------------------------------------------------------------------------
// Service requests (citizen view)
// ---------------------------------------------------------------------------
export type DetailViewResponse = Schemas['DetailViewResponse'];
export type DashboardSummaryResponse = Schemas['DashboardSummaryResponse'];
export type DashboardSummaryStats = Schemas['DashboardSummaryStats'];

// ---------------------------------------------------------------------------
// Wizard sessions
// ---------------------------------------------------------------------------
export type WizardSessionCreate = Schemas['WizardSessionCreate'];
export type WizardSessionResponse = Schemas['WizardSessionResponse'];
export type WizardSessionStatus = Schemas['WizardSessionStatus'];

// ---------------------------------------------------------------------------
// Appointments (post-creation booking lifecycle)
// ---------------------------------------------------------------------------
export type AppointmentLocationsListResponse =
  Schemas['AppointmentLocationsListResponse'];
export type AppointmentSlotsListResponse = Schemas['AppointmentSlotsListResponse'];
export type AppointmentHoldStatus = Schemas['AppointmentHoldStatus'];
export type AppointmentSelectionRequest = Schemas['AppointmentSelectionRequest'];
export type AppointmentSchedule = Schemas['AppointmentSchedule'];
export type AppointmentItem = Schemas['AppointmentItem'];

// ---------------------------------------------------------------------------
// Fiscal services catalog
// ---------------------------------------------------------------------------
export type FiscalServiceResponse = Schemas['FiscalServiceResponse'];
export type FiscalServiceListResponse = Schemas['FiscalServiceListResponse'];
export type FiscalServiceFilter = Schemas['FiscalServiceFilter'];
export type MinistryItem = Schemas['MinistryItem'];

// ---------------------------------------------------------------------------
// Bundle workflow (OMS)
// ---------------------------------------------------------------------------
export type BundleInitiateRequest = Schemas['BundleInitiateRequest'];
export type BundleInitiateFromUploadRequest =
  Schemas['BundleInitiateFromUploadRequest'];
export type BundleInitiatePaymentRequest = Schemas['BundleInitiatePaymentRequest'];

// ---------------------------------------------------------------------------
// Payments
// ---------------------------------------------------------------------------
export type PaymentCreate = Schemas['PaymentCreate'];

// ---------------------------------------------------------------------------
// Chatbot
// ---------------------------------------------------------------------------
export type ChatRequest = Schemas['ChatRequest'];
export type ChatResponse = Schemas['ChatResponse'];
export type ChatHistoryMessage = Schemas['ChatHistoryMessage'];

// ---------------------------------------------------------------------------
// Companies (CRUD + members)
// ---------------------------------------------------------------------------
export type CompanyCreate = Schemas['CompanyCreate'];
export type CompanyUpdate = Schemas['CompanyUpdate'];
export type CompanyResponse = Schemas['CompanyResponse'];
export type CompanyListResponse = Schemas['CompanyListResponse'];
export type CompanyMember = Schemas['CompanyMember'];
export type CompanyMemberRole = Schemas['CompanyMemberRole'];
export type AddMemberRequest = Schemas['AddMemberRequest'];
export type UpdateMemberRoleRequest = Schemas['UpdateMemberRoleRequest'];
export type CompanyInfo = Schemas['CompanyInfo'];
export type CompanySearchResult = Schemas['CompanySearchResult'];

// ---------------------------------------------------------------------------
// Document Vault (user_documents)
// ---------------------------------------------------------------------------
export type UserDocumentResponse = Schemas['UserDocumentResponse'];
export type UserDocumentListItem = Schemas['UserDocumentListItem'];
export type UserDocumentListResponse = Schemas['UserDocumentListResponse'];
export type UserDocumentStats = Schemas['UserDocumentStats'];
export type UserDocumentUpdate = Schemas['UserDocumentUpdate'];
export type UserDocumentBulkAction = Schemas['UserDocumentBulkAction'];
export type UploadResult = Schemas['UploadResult'];
export type HashCheckResponse = Schemas['HashCheckResponse'];
export type AlertResponse = Schemas['AlertResponse'];
export type GeneratedDocumentResponse = Schemas['GeneratedDocumentResponse'];
export type ReadinessResult = Schemas['ReadinessResult'];
export type ReadinessItem = Schemas['ReadinessItem'];
export type UseVaultDocumentRequest = Schemas['UseVaultDocumentRequest'];
