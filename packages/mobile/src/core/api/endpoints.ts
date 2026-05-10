/**
 * API Endpoint Constants — Single Source of Truth (SoT)
 *
 * Centralized endpoint definitions for the Facil backend API.
 * All endpoints are relative to the base URL configured in appConfig.
 *
 * Organized by module to match the backend router structure.
 * Dynamic segments use functions for type-safe URL generation.
 *
 * IMPORTANT — KEEP IN SYNC WITH:
 *   - packages/backend/app/main.py (router registrations, lines 1224-1743)
 *   - .claude/plans/MOBILE_USER_PHASE_0_DETAILED.md (audit & decisions)
 *
 * Verified against backend OpenAPI staging on 2026-04-27.
 *
 * Conventions:
 *   - Paths are RELATIVE to /api/v1 (the base URL adds /api/{version}).
 *   - Functions for paths with dynamic segments. Use template literal types when possible.
 *   - Only paths exposed to citizen + business roles are listed here.
 *     Agent/admin/supervisor/cron paths are intentionally excluded.
 */

export const API_ENDPOINTS = {
  // -------------------------------------------------------------------------
  // Authentication & Sessions
  //   Backend: app/modules/auth/api/auth_routes.py (prefix /api/v1/auth)
  // -------------------------------------------------------------------------
  auth: {
    info: '/auth/',
    login: '/auth/login',
    register: '/auth/register',
    refresh: '/auth/refresh',
    logout: '/auth/logout',
    /** @deprecated Use `users.profile` instead. Both paths return UserResponse,
     *  but `users.profile` is the canonical citizen path (matching the web
     *  pattern). Legacy `/auth/profile` (auth_routes.py:829) is kept on the
     *  backend for back-compat — do not introduce new consumers. */
    profile: '/auth/profile',
    sessions: '/auth/sessions',
    requestVerificationCode: '/auth/request-verification-code',
    passwordResetRequest: '/auth/password/reset/request',
    passwordResetConfirm: '/auth/password/reset/confirm',
    passwordChange: '/auth/password/change',
    passwordChangeVerify: '/auth/password/change/verify',
    emailVerify: '/auth/email/verify',
    emailResend: '/auth/email/resend',
    /** Complete login when 2FA is required (separate from 2FA setup verify) */
    login2faVerify: '/auth/login/2fa-verify',
    twoFactorEnable: '/auth/2fa/enable',
    twoFactorVerify: '/auth/2fa/verify',
    twoFactorDisable: '/auth/2fa/disable',
    twoFactorStatus: '/auth/2fa/status',
  },

  // -------------------------------------------------------------------------
  // User Profile
  //   Backend: app/modules/users/api/user_routes.py (prefix /api/v1/users)
  // -------------------------------------------------------------------------
  users: {
    profile: '/users/profile',
    updateProfile: '/users/profile',
    changePassword: '/users/profile/change-password',
    uploadAvatar: '/users/profile/avatar',
    deleteAvatar: '/users/profile/avatar',
    /** Register a push notification device token (FCM/APNs). NEW — required for P1. */
    deviceToken: '/users/profile/device-token',
    /** DELETE — RGPD soft-delete. Body: { password, confirmation: "DELETE" }. */
    deleteAccount: '/users/profile',
    /** GET — RGPD art. 20 data export. Returns JSON with Content-Disposition. */
    exportData: '/users/profile/export',
  },

  // -------------------------------------------------------------------------
  // Service Requests (Citizen view)
  //   Backend: app/modules/service_requests/api/routes.py (prefix /api/v1)
  // -------------------------------------------------------------------------
  serviceRequests: {
    list: '/service-requests/',
    detail: (id: string) => `/service-requests/${id}` as const,
    detailView: (id: string) => `/service-requests/${id}/detail-view` as const,
    summaryPdf: (id: string) => `/service-requests/${id}/summary/pdf` as const,
    dashboardSummary: '/service-requests/dashboard-summary',
    workflows: '/service-requests/workflows',
    /** Detail of a workflow definition (config, steps, documents, tariff). */
    workflowDetail: (code: string) => `/service-requests/workflows/${code}` as const,
    /**
     * Paginated citizen notifications across all SRs (audit trail of agent
     * decisions, payments, doc requests, etc.). Backend returns
     * `{ items, total, total_unread, page, page_size }`. The mobile inbox
     * (MMKV ring buffer) only holds push receptions; this endpoint is the
     * authoritative server-side view (ensures notifications pushed while the
     * device was offline are still visible). Web parity:
     * `web/.../dashboard/notifications/page.tsx`.
     */
    notifications: '/service-requests/notifications',
  },

  // -------------------------------------------------------------------------
  // Service Request Appointments (post-creation booking lifecycle)
  //   Backend: app/modules/service_requests/api/appointment_routes.py (prefix /api/v1/service-requests)
  //   NOTE: distinct from wizard-sessions appointments (which are in-wizard).
  // -------------------------------------------------------------------------
  appointments: {
    locations: (requestId: string) =>
      `/service-requests/${requestId}/appointments/locations` as const,
    availableDays: (requestId: string) =>
      `/service-requests/${requestId}/appointments/available-days` as const,
    availableSlots: (requestId: string) =>
      `/service-requests/${requestId}/appointments/slots` as const,
    hold: (requestId: string) => `/service-requests/${requestId}/appointments/hold` as const,
    holdStatus: (requestId: string) =>
      `/service-requests/${requestId}/appointments/hold-status` as const,
    releaseHold: (requestId: string) =>
      `/service-requests/${requestId}/appointments/hold` as const,
    fallbackSubmit: (requestId: string) =>
      `/service-requests/${requestId}/appointments/fallback` as const,
    confirm: (requestId: string) =>
      `/service-requests/${requestId}/appointments/confirm` as const,
  },

  // -------------------------------------------------------------------------
  // Wizard Sessions (Cache-First, Multi-step request creation)
  //   Backend: app/modules/service_requests/api/wizard_session_routes.py
  //            (router prefix /wizard-sessions, included with /api/v1)
  // -------------------------------------------------------------------------
  wizardSessions: {
    create: '/wizard-sessions',
    get: (id: string) => `/wizard-sessions/${id}` as const,
    delete: (id: string) => `/wizard-sessions/${id}` as const,
    formData: (id: string) => `/wizard-sessions/${id}/form-data` as const,
    /** step_id is a STRING (e.g. "form_review_1", "form_review_representantes"), not a number. */
    formConfig: (id: string, stepId: string) =>
      `/wizard-sessions/${id}/form-config/${stepId}` as const,
    documentPreview: (id: string) =>
      `/wizard-sessions/${id}/documents/preview` as const,
    documentConfirm: (id: string) =>
      `/wizard-sessions/${id}/documents/confirm` as const,
    documentDelete: (id: string, documentCode: string) =>
      `/wizard-sessions/${id}/documents/${documentCode}` as const,
    /** Use a document already stored in the user's vault. NEW — for P2/P4. */
    useVaultDocument: (id: string) =>
      `/wizard-sessions/${id}/documents/use-vault` as const,
    preparePayment: (id: string) => `/wizard-sessions/${id}/prepare-payment` as const,
    /** Persist the wizard session before payment (commits to DB). NEW. */
    persist: (id: string) => `/wizard-sessions/${id}/persist` as const,
    initiatePayment: (id: string) =>
      `/wizard-sessions/${id}/initiate-payment` as const,
    availableSites: (id: string) => `/wizard-sessions/${id}/available-sites` as const,
    selectSite: (id: string) => `/wizard-sessions/${id}/select-site` as const,
    appointmentLocations: (id: string) =>
      `/wizard-sessions/${id}/appointments/locations` as const,
    appointmentAvailableDays: (id: string) =>
      `/wizard-sessions/${id}/appointments/available-days` as const,
    appointmentAvailableSlots: (id: string) =>
      `/wizard-sessions/${id}/appointments/available-slots` as const,
    appointmentSelect: (id: string) =>
      `/wizard-sessions/${id}/appointments/select` as const,
  },

  // -------------------------------------------------------------------------
  // Fiscal Services Catalog
  //   Backend: app/modules/fiscal_services/api/fiscal_service_routes.py
  //            (prefix /api/v1/fiscal-services)
  // -------------------------------------------------------------------------
  fiscalServices: {
    list: '/fiscal-services',
    detail: (id: string) => `/fiscal-services/${id}` as const,
    details: (id: string) => `/fiscal-services/${id}/details` as const,
    documents: (id: string) => `/fiscal-services/${id}/documents` as const,
    procedures: (id: string) => `/fiscal-services/${id}/procedures` as const,
    /** Public POST search with filters (free-text + facets). */
    search: '/fiscal-services/search',
    /** Authenticated DB-level search with raw query semantics. */
    searchDb: '/fiscal-services/search-db',
    /** Authenticated tariff calculation (POST). */
    calculate: '/fiscal-services/calculate',
    popular: '/fiscal-services/popular/list',
    recent: '/fiscal-services/recent/list',
    ministries: '/fiscal-services/ministries',
    sectors: '/fiscal-services/sectors',
    categories: '/fiscal-services/categories',
  },

  // -------------------------------------------------------------------------
  // Service Bundles (catalog of pre-defined commerce bundles)
  //   Backend: app/modules/fiscal_services/api/bundle_routes.py
  //            (router prefix /service-bundles, included with /api/v1)
  // -------------------------------------------------------------------------
  serviceBundles: {
    /**
     * Trailing slash matters — backend exposes `GET "/"` so a request to
     * `/service-bundles` without slash triggers a 307 redirect (and possibly
     * loses the Authorization header on some middleware stacks).
     */
    list: '/service-bundles/',
    detail: (id: string) => `/service-bundles/${id}` as const,
    pricing: (id: string) => `/service-bundles/${id}/pricing` as const,
    matrix: (id: string) => `/service-bundles/${id}/matrix` as const,
    documents: (id: string) => `/service-bundles/${id}/documents` as const,
    installmentPreview: (id: string) =>
      `/service-bundles/${id}/installment-preview` as const,
    byService: (fiscalServiceId: string) =>
      `/service-bundles/by-service/${fiscalServiceId}` as const,
    zones: '/service-bundles/zones',
    commerceTypes: '/service-bundles/commerce-types',
    simulator: '/service-bundles/simulator',
  },

  // -------------------------------------------------------------------------
  // Bundle Workflow (OMS — operational user-facing flow)
  //   Backend: app/modules/fiscal_services/api/bundle_workflow_routes.py
  //            (router prefix /bundle-workflow, included with /api/v1)
  // -------------------------------------------------------------------------
  bundleWorkflow: {
    myCompanies: '/bundle-workflow/my-companies',
    myCompanyDetail: (companyId: string) =>
      `/bundle-workflow/my-companies/${companyId}` as const,
    myCompanyPayments: (companyId: string) =>
      `/bundle-workflow/my-companies/${companyId}/payments` as const,
    myCompanyLicensePdf: (companyId: string) =>
      `/bundle-workflow/my-companies/${companyId}/license-pdf` as const,
    searchCompany: '/bundle-workflow/search-company',
    initiate: '/bundle-workflow/initiate',
    classifyPreview: '/bundle-workflow/classify-preview',
    initiateFromUpload: '/bundle-workflow/initiate-from-upload',
    validateSelection: '/bundle-workflow/validate-selection',
    initiatePayment: '/bundle-workflow/initiate-payment',
  },

  // -------------------------------------------------------------------------
  // Companies (business users — manage own companies)
  //   Backend: app/modules/companies/api/company_routes.py (prefix /api/v1/companies)
  // -------------------------------------------------------------------------
  companies: {
    list: '/companies',
    create: '/companies',
    detail: (id: string) => `/companies/${id}` as const,
    update: (id: string) => `/companies/${id}` as const,
    /** @deprecated Use {@link archive} from the citizen surface. The backend
     *  DELETE route now requires `company.hard_delete` (admin) AND a prior
     *  archive — kept for back-office tooling only. */
    delete: (id: string) => `/companies/${id}` as const,
    /** Soft-delete (archive) — owner only. Backend may return 409 with a
     *  `blockers` payload when active dependencies prevent the archive. */
    archive: (id: string) => `/companies/${id}/archive` as const,
    members: (id: string) => `/companies/${id}/members` as const,
    addMember: (id: string) => `/companies/${id}/members` as const,
    updateMemberRole: (id: string, memberUserId: string) =>
      `/companies/${id}/members/${memberUserId}/role` as const,
    removeMember: (id: string, memberUserId: string) =>
      `/companies/${id}/members/${memberUserId}` as const,
  },

  // -------------------------------------------------------------------------
  // Public Company Directory (annuaire — no auth required, rate-limited)
  //   Backend: app/modules/companies/api/company_public_routes.py
  //            (prefix /api/v1/public/companies)
  // -------------------------------------------------------------------------
  publicCompanies: {
    search: '/public/companies/search',
    zones: '/public/companies/zones',
    sectors: '/public/companies/sectors',
    provincias: '/public/companies/provincias',
    ciudades: '/public/companies/ciudades',
    formasJuridicas: '/public/companies/formas-juridicas',
  },

  // -------------------------------------------------------------------------
  // User Documents (Vault / Coffre-fort) — P2 module
  //   Backend: app/modules/user_documents/api/user_documents_routes.py
  //            (prefix /api/v1/user-documents)
  // -------------------------------------------------------------------------
  userDocuments: {
    upload: '/user-documents/upload',
    bulkUpload: '/user-documents/bulk-upload',
    checkHash: (fileHash: string) => `/user-documents/check-hash/${fileHash}` as const,
    list: '/user-documents/',
    detail: (id: string) => `/user-documents/${id}` as const,
    thumbnail: (id: string) => `/user-documents/${id}/thumbnail` as const,
    download: (id: string) => `/user-documents/${id}/download` as const,
    update: (id: string) => `/user-documents/${id}` as const,
    archive: (id: string) => `/user-documents/${id}/archive` as const,
    delete: (id: string) => `/user-documents/${id}` as const,
    permanentDelete: (id: string) => `/user-documents/${id}/permanent` as const,
    reclassify: (id: string) => `/user-documents/${id}/reclassify` as const,
    /** SSE stream: AI processing status (Gemini extraction progress). */
    processingStatus: (id: string) => `/user-documents/${id}/processing-status` as const,
    versions: (id: string) => `/user-documents/${id}/versions` as const,
    alerts: '/user-documents/alerts',
    alertRead: (alertId: string) => `/user-documents/alerts/${alertId}/read` as const,
    alertDismiss: (alertId: string) =>
      `/user-documents/alerts/${alertId}/dismiss` as const,
    generated: '/user-documents/generated',
    readinessAll: '/user-documents/readiness',
    readiness: (workflowCode: string) =>
      `/user-documents/readiness/${workflowCode}` as const,
    forWorkflow: (workflowCode: string) =>
      `/user-documents/for-workflow/${workflowCode}` as const,
    search: '/user-documents/search',
    stats: '/user-documents/stats',
    bulkAction: '/user-documents/bulk-action',
    exportStart: '/user-documents/export',
    exportStatus: (exportId: string) =>
      `/user-documents/export/${exportId}/status` as const,
    exportDownload: (exportId: string) =>
      `/user-documents/export/${exportId}/download` as const,
    /** Agent permission catalog (citizen-side: list of permissions an agent can request). */
    agentPermissionCatalog: '/user-documents/agent/permission-catalog',
    agentPermissions: '/user-documents/agent/permissions',
    revokeAgentPermission: (permissionId: string) =>
      `/user-documents/agent/permissions/${permissionId}` as const,
    agentMemory: '/user-documents/agent/memory',
    deleteAgentMemory: (memoryId: string) =>
      `/user-documents/agent/memory/${memoryId}` as const,
  },

  // -------------------------------------------------------------------------
  // Payments
  //   Backend: app/modules/payments/api/payment_routes.py (prefix /api/v1/payments)
  // -------------------------------------------------------------------------
  payments: {
    list: '/payments',
    create: '/payments',
    detail: (id: string) => `/payments/${id}` as const,
    update: (id: string) => `/payments/${id}` as const,
    createPlan: (id: string) => `/payments/${id}/plan` as const,
    planDetail: (planId: string) => `/payments/plans/${planId}` as const,
    /**
     * Poll the payment status for a service request after a Mobile Money payment
     * has been initiated via the wizard. Used by `wizard/payment-result` and the
     * payments detail screen for in-flight transactions.
     *
     * Backend: app/modules/service_requests/api/routes.py:1204 (PaymentStatusResponse).
     */
    serviceRequestStatus: (requestId: string) =>
      `/service-requests/${requestId}/payment/status` as const,
    /**
     * List the payment methods that can be used to settle a given SR.
     * Backend dynamically builds the list from `payment_processor_registry`
     * (BANGE Mobile Money, card, bank transfer, cash, check). Mobile must read
     * this rather than hardcode "BANGE only" — extending the catalogue server
     * side then becomes a zero-mobile-change rollout.
     *
     * Backend: routes.py:1258 (PaymentMethodsResponse).
     */
    serviceRequestPaymentMethods: (requestId: string) =>
      `/service-requests/${requestId}/payment/methods` as const,
    /**
     * Re-initiate a payment for a SR (used by the "Try again" CTA when a
     * previous payment failed/expired without going through the wizard).
     * Web parity: same path under `/dashboard/service-requests/[id]`.
     *
     * Backend: routes.py:1317 (PaymentInitiateRequest -> PaymentInitiateResponse).
     */
    serviceRequestInitiatePayment: (requestId: string) =>
      `/service-requests/${requestId}/payment/initiate` as const,
  },

  // -------------------------------------------------------------------------
  // Public Verification (receipts, requests, licenses, certificates)
  //   Backend: app/modules/payments/api/verify_routes.py (prefix /api/v1/verify)
  //   No auth required, but token (?t=) is validated for tamper-proofing.
  // -------------------------------------------------------------------------
  verify: {
    request: (reference: string) => `/verify/request/${reference}` as const,
    receipt: (receiptNumber: string) => `/verify/${receiptNumber}` as const,
    license: (licenseRef: string) => `/verify/license/${licenseRef}` as const,
    certificate: (certificateNumber: string) =>
      `/verify/certificate/${certificateNumber}` as const,
  },

  // -------------------------------------------------------------------------
  // AI Chatbot (RAG + Gemini)
  //   Backend: app/modules/chatbot/api/chatbot_routes.py (prefix /api/v1/chatbot)
  // -------------------------------------------------------------------------
  chatbot: {
    info: '/chatbot/',
    status: '/chatbot/status',
    chat: '/chatbot/chat',
    stream: '/chatbot/chat/stream',
    executeConfirmed: '/chatbot/execute-confirmed',
    search: '/chatbot/search',
    recommend: '/chatbot/recommend',
    analyzeDocument: '/chatbot/analyze-document',
    translate: '/chatbot/translate',
    guide: '/chatbot/guide',
    validate: '/chatbot/validate',
    feedback: '/chatbot/feedback',
    conversation: (id: string) => `/chatbot/conversations/${id}` as const,
  },

  // -------------------------------------------------------------------------
  // Support Tickets
  //   Backend: app/modules/support/api/support_routes.py
  //            (router prefix /support, included with /api/v1)
  // -------------------------------------------------------------------------
  support: {
    /** GET — categories visible to the current user (target_role-filtered server-side). */
    categories: '/support/categories',
    categoryDetail: (id: number) => `/support/categories/${id}` as const,
    /** GET admin — all tickets ; POST — create a new ticket. */
    tickets: '/support/tickets',
    /** Alias kept for the citizen-facing client. */
    createTicket: '/support/tickets',
    /** GET — paginated list of the current user's tickets. */
    myTickets: '/support/tickets/my',
    /** GET / PUT — single ticket. BD verified: support_tickets.id is INTEGER. */
    ticket: (id: number) => `/support/tickets/${id}` as const,
    ticketDetail: (id: number) => `/support/tickets/${id}` as const,
    ticketByNumber: (ticketNumber: string) =>
      `/support/tickets/by-number/${ticketNumber}` as const,
    ticketUpdate: (id: number) => `/support/tickets/${id}` as const,
    /** POST — owner or admin can close. */
    closeTicket: (id: number) => `/support/tickets/${id}/close` as const,
    ticketClose: (id: number) => `/support/tickets/${id}/close` as const,
    /** GET / POST — message thread. */
    ticketMessages: (id: number) => `/support/tickets/${id}/messages` as const,
  },

  // -------------------------------------------------------------------------
  // Documents (legacy, request-scoped — distinct from user-documents vault)
  //   Backend: app/modules/documents/api/document_routes.py (prefix /api/v1/documents)
  // -------------------------------------------------------------------------
  documents: {
    upload: '/documents/upload',
    list: '/documents/list',
    detail: (id: string) => `/documents/${id}` as const,
    download: (id: string) => `/documents/${id}/download` as const,
  },

  // -------------------------------------------------------------------------
  // Translations & i18n
  //   Mobile UI strings (3 locales) are bundled in src/core/i18n/locales/*.json
  //   and loaded statically at boot — see core/i18n/index.ts. This is by design:
  //   instant startup, works offline, no version drift between APK and server.
  //
  //   Only DYNAMIC backend-managed translations (workflow keys whose values
  //   live in the database and may evolve without an APK release) are fetched
  //   at runtime. If we ever want OTA updates for plain UI strings, add a
  //   dedicated namespace here (e.g. GET /translations/frontend/export/mobile)
  //   and a hook that merges with the bundled JSON — do NOT resurrect a
  //   `frontend(lang)` shortcut that does not exist on the backend.
  // -------------------------------------------------------------------------
  translations: {
    /** Workflow strings keyed by `wf.<workflow_code>.*` (used by the wizard). */
    systemWorkflow: '/translations/system/export/workflow',
  },

  // -------------------------------------------------------------------------
  // Homepage / Public landing data
  //   Backend: app/modules/homepage/api/homepage_routes.py (prefix /api/v1/homepage)
  // -------------------------------------------------------------------------
  homepage: {
    /** Trailing slash matters — backend issues 307 redirect to /homepage/ otherwise. */
    data: '/homepage/',
    /** Aliased on the homepage router (POST). Used by mobile fiscal-services search. */
    search: '/homepage/search',
  },

  // Communications endpoints are intentionally not exposed here — they are
  // server-internal (transactional emails/SMS sent on behalf of other flows).
  // Citizen apps never call them directly. Re-add only when a specific UI
  // need arises and the consumer is implemented in the same change.

  // -------------------------------------------------------------------------
  // Legal — Privacy Policy + Terms of Service versions and acceptance
  //   Backend: app/modules/legal/api/legal_routes.py (prefix /api/v1/legal)
  //   Phase 10/B — Mobile sign-up acceptance + post-login modal for existing
  //   users with stale (NULL or "1.0.0-legacy") versions. Web V1 unchanged.
  // -------------------------------------------------------------------------
  legal: {
    /** Public — current Privacy/Terms/Cookies versions + last-updated dates */
    versions: '/legal/versions',
    /** Auth required — record acceptance for current user (citizen/business/accountant only) */
    accept: '/legal/accept',
  },
} as const;

/**
 * Type helper: extracts the return type of an endpoint.
 * For static endpoints it's a string literal; for dynamic ones it's the function's return type.
 */
export type EndpointUrl<T> = T extends (...args: never[]) => infer R ? R : T;
